#!/bin/bash
# lessons_search.sh — 从 lessons.jsonl 匹配教训规则
# Usage: ./lessons_search.sh <keyword1> [keyword2...]
# Output: JSONL lines where tags/trigger/title match any keyword
# 
# 注意: 如果有多个 > 20个结果, 用head 20输出

if [ $# -eq 0 ]; then
    # 无参数: 输出所有活跃规则
    cat "$(cd "$(dirname "$0")" && pwd)/lessons.jsonl"
    exit 0
fi

LESSONS_FILE="$(cd "$(dirname "$0")" && pwd)/lessons.jsonl"

# Build grep pattern from all args
pattern=""
for arg in "$@"; do
    if [ -n "$pattern" ]; then
        pattern="$pattern|$arg"
    else
        pattern="$arg"
    fi
done

# Case-insensitive search across title, tags, trigger, rule
grep -i -E "$pattern" "$LESSONS_FILE" 2>/dev/null || echo ""
