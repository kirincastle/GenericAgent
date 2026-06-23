#!/usr/bin/env python3
"""
lessons_maintenance.py — Lessons lifecycle management
Run as part of /neat (neat-freak skill).

Operations:
1. effectiveness scoring → demote weak/dormant
2. merge similar (same tags, overlapping trigger)
3. conflict detection (same tags, opposite rules)
4. archive superseded lessons

Usage:
    python3 memory/lessons_maintenance.py [--dry-run] [--verbose]
"""
import json, os, re, sys
from collections import defaultdict
from datetime import datetime, timezone

LESSONS_FILE = os.path.join(os.path.dirname(__file__), 'lessons.jsonl')

# ── Helpers ────────────────────────────────────────────────────────────

def load_lessons():
    lessons = []
    with open(LESSONS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                lessons.append(json.loads(line))
    return lessons

def save_lessons(lessons, dry_run=False):
    if dry_run:
        return
    with open(LESSONS_FILE, 'w') as f:
        for L in lessons:
            f.write(json.dumps(L, ensure_ascii=False) + '\n')

def tagset(lesson):
    return frozenset(t.lower() for t in lesson.get('tags', []))

def trigger_keywords(lesson):
    """Extract keywords from trigger field."""
    t = lesson.get('trigger', '')
    return set(w.lower().strip('.,;:()[]{}') for w in t.split() if len(w) > 3)

def rule_direction(rule):
    """Classify rule direction: positive (do X) vs negative (don't do X)."""
    neg = ['not', 'avoid', "don't", 'never', '禁止', '不要', '别']
    first_word = rule.strip().lower().split()[0] if rule.strip() else ''
    is_neg = any(first_word.startswith(n) for n in neg) or rule.startswith('When') and 'not' in rule.split()[:5]
    return 'negative' if is_neg else 'positive'

def normalize_rule(rule):
    """Normalize rule for comparison: lowercase, collapse whitespace, remove filler."""
    r = rule.lower().strip()
    r = re.sub(r'\s+', ' ', r)
    return r

# ── Scoring ────────────────────────────────────────────────────────────

def score_lesson(L):
    """Calculate effectiveness and determine status."""
    p = L.get('prevent_count', 0)
    f = L.get('fail_count', 0)
    eff = p / (p + f + 0.01)
    
    L['effectiveness'] = round(eff, 3)
    
    # Status transitions
    current = L.get('status', 'active')
    last_match = L.get('last_match', L.get('created', ''))
    match_count = L.get('match_count', 0)
    
    # Archived if superseded
    if L.get('superseded_by'):
        L['status'] = 'archived'
        return
    
    # Dormant: never prevented, multiple failures
    if f >= 3 and p == 0 and match_count >= 3:
        L['status'] = 'dormant'
        return
    
    # Weak: low effectiveness
    if eff < 0.3 and match_count >= 5:
        L['status'] = 'weak'
        return
    
    # Dormant: no match in 90 days
    if last_match and isinstance(last_match, str):
        try:
            lm = datetime.fromisoformat(last_match)
            days = (datetime.now(timezone.utc) - lm.replace(tzinfo=timezone.utc)).days
            if days > 90:
                L['status'] = 'dormant'
                return
        except (ValueError, AttributeError):
            pass
    
    # Default
    if current not in ('archived', 'dormant', 'weak'):
        L['status'] = 'active'

# ── Merge similar ──────────────────────────────────────────────────────

def merge_similar(lessons, dry_run, verbose):
    """Merge lessons with same tagset and overlapping trigger keywords."""
    groups = defaultdict(list)
    for L in lessons:
        if L.get('status') == 'archived':
            groups[f'archived'].append(L)
            continue
        groups[tagset(L)].append(L)
    
    merged = []
    merged_ids = set()
    
    for ts, group in groups.items():
        if ts == 'archived':
            merged.extend(group)
            continue
            
        if len(group) <= 1:
            merged.extend(group)
            continue
        
        # Check if triggers overlap
        merged_flag = False
        for i in range(len(group)):
            if group[i].get('id') in merged_ids:
                continue
            for j in range(i+1, len(group)):
                if group[j].get('id') in merged_ids:
                    continue
                    
                kw_i = trigger_keywords(group[i])
                kw_j = trigger_keywords(group[j])
                overlap = kw_i & kw_j
                
                if len(overlap) >= 2:
                    # Merge j into i
                    if verbose:
                        print(f"  MERGE: #{group[i]['id']} ← #{group[j]['id']}")
                    group[i]['match_count'] = max(group[i].get('match_count', 0), group[j].get('match_count', 0))
                    group[i]['prevent_count'] = max(group[i].get('prevent_count', 0), group[j].get('prevent_count', 0))
                    group[i]['fail_count'] = max(group[i].get('fail_count', 0), group[j].get('fail_count', 0))
                    group[i]['trigger'] = group[i].get('trigger', '') + ' | ' + group[j].get('trigger', '')
                    merged_ids.add(group[j]['id'])
                    merged_flag = True
        
        if not merged_flag:
            merged.extend(group)
        else:
            for L in group:
                if L['id'] not in merged_ids:
                    merged.append(L)
    
    return merged

# ── Conflict detection ─────────────────────────────────────────────────

def detect_conflicts(lessons, verbose):
    """Find lessons with same tags but opposite rule directions."""
    conflicts = []
    by_tags = defaultdict(list)
    for L in lessons:
        if L.get('status') in ('archived', 'dormant'):
            continue
        by_tags[tagset(L)].append(L)
    
    for ts, group in by_tags.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i+1, len(group)):
                dir_i = rule_direction(group[i].get('rule', ''))
                dir_j = rule_direction(group[j].get('rule', ''))
                if dir_i != dir_j and ts:
                    conflict = {
                        'a': group[i]['id'], 'b': group[j]['id'],
                        'tags': list(ts),
                        'reason': f"opposite direction: {dir_i} vs {dir_j}"
                    }
                    conflicts.append(conflict)
                    if verbose:
                        print(f"  CONFLICT: #{group[i]['id']} vs #{group[j]['id']} ({', '.join(ts)})")
    
    return conflicts

# ── Main ───────────────────────────────────────────────────────────────

def main():
    dry_run = '--dry-run' in sys.argv
    verbose = '--verbose' in sys.argv
    
    if not os.path.exists(LESSONS_FILE):
        print(f"ERROR: {LESSONS_FILE} not found")
        sys.exit(1)
    
    lessons = load_lessons()
    print(f"Loaded {len(lessons)} lessons")
    
    # 1. Score all
    for L in lessons:
        score_lesson(L)
    active = sum(1 for L in lessons if L.get('status') == 'active')
    weak = sum(1 for L in lessons if L.get('status') == 'weak')
    dormant = sum(1 for L in lessons if L.get('status') == 'dormant')
    archived = sum(1 for L in lessons if L.get('status') == 'archived')
    print(f"  Status: {active} active, {weak} weak, {dormant} dormant, {archived} archived")
    
    # 2. Merge similar
    before = len(lessons)
    lessons = merge_similar(lessons, dry_run, verbose)
    after = len(lessons)
    if after < before:
        print(f"  Merged: {before - after} lessons removed")
    
    # 3. Detect conflicts
    conflicts = detect_conflicts(lessons, verbose)
    if conflicts and not dry_run:
        # Flag both sides
        for c in conflicts:
            for L in lessons:
                if L['id'] in (c['a'], c['b']):
                    L.setdefault('conflict_with', [])
                    other = c['b'] if L['id'] == c['a'] else c['a']
                    if other not in L['conflict_with']:
                        L['conflict_with'].append(other)
    
    # 4. Save
    save_lessons(lessons, dry_run)
    
    print(f"\nResults: {len(lessons)} lessons saved")
    if conflicts:
        print(f"  Conflicts flagged: {len(conflicts)}")
    print("OK" if not dry_run else "DRY RUN - no changes made")

if __name__ == '__main__':
    main()
