#!/bin/bash
# lessons_search.sh — 从 lessons.jsonl 匹配教训规则
# Usage: ./lessons_search.sh <keyword1> [keyword2...]
# Output: JSONL lines where tags/trigger/title match any keyword
# 
# 注意: 如果有多个 > 20个结果, 用head 20输出
# 自动记录搜索日志到 lessons_search_log.jsonl

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LESSONS_FILE="$SCRIPT_DIR/lessons.jsonl"
SEARCH_LOG="$SCRIPT_DIR/lessons_search_log.jsonl"

if [ $# -eq 0 ]; then
    # 无参数: 输出所有活跃规则
    cat "$LESSONS_FILE"
    exit 0
fi

# Build grep pattern from all args
pattern=""
for arg in "$@"; do
    if [ -n "$pattern" ]; then
        pattern="$pattern|$arg"
    else
        pattern="$arg"
    fi
done

# Perform search
RESULTS=$(grep -i -E "$pattern" "$LESSONS_FILE" 2>/dev/null || echo "")

# Extract matched IDs and count hits
HIT_COUNT=0
MATCHED_IDS="[]"
if [ -n "$RESULTS" ]; then
    HIT_COUNT=$(echo "$RESULTS" | grep -c .)
    # Extract IDs: format is {"id": N, ...}
    MATCHED_IDS=$(echo "$RESULTS" | python3 -c "
import json, sys
ids = []
for line in sys.stdin:
    line = line.strip()
    if line:
        try:
            d = json.loads(line)
            ids.append(d.get('id'))
        except json.JSONDecodeError:
            pass
print(json.dumps(ids))
")
fi

# Log search
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_ENTRY=$(python3 -c "
import json
entry = {
    'timestamp': '$TIMESTAMP',
    'keywords': [$(for a in "$@"; do echo -n "\"$a\","; done | sed 's/,$//')],
    'hits': $HIT_COUNT,
    'matched_ids': $MATCHED_IDS,
    'follow_up': None,
}
print(json.dumps(entry, ensure_ascii=False))
")
echo "$LOG_ENTRY" >> "$SEARCH_LOG"

# Update last_match/last_used for matched lessons
if [ "$HIT_COUNT" -gt 0 ]; then
    python3 -c "
import json, sys
LESSONS_FILE = '$LESSONS_FILE'
ids = $MATCHED_IDS
now = '$TIMESTAMP'
lessons = []
with open(LESSONS_FILE) as f:
    for line in f:
        line = line.strip()
        if line:
            L = json.loads(line)
            if L.get('id') in ids:
                L['last_match'] = now
                L['last_used'] = now
                L['match_count'] = L.get('match_count', 0) + 1
            lessons.append(L)
with open(LESSONS_FILE, 'w') as f:
    for L in lessons:
        f.write(json.dumps(L, ensure_ascii=False) + '\n')
" 2>/dev/null || true
fi

# If no hits, optionally suggest creating a new lesson
if [ "$HIT_COUNT" -eq 0 ]; then
    if command -v python3 &>/dev/null; then
        python3 "$SCRIPT_DIR/lessons_suggester.py" match "$@" 2>/dev/null || true
    fi
fi

# Output results (limited to 20)
echo "$RESULTS" | head -20
