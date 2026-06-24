#!/usr/bin/env python3
"""
lessons_maintenance.py — Lessons lifecycle management
Run as part of /neat (neat-freak skill).

Operations:
1. effectiveness scoring -> demote weak/dormant
2. merge similar lessons
3. conflict detection
4. quality check (flag trivial lessons)
5. archive superseded

Usage:
    python3 memory/lessons_maintenance.py [--dry-run] [--verbose]
"""
import json, os, re, sys
from datetime import datetime, timezone
from collections import defaultdict

LESSONS_FILE = os.path.join(os.path.dirname(__file__), 'lessons.jsonl')

# ── Quality check patterns (reject trivial lessons) ────────────────────

TRIVIAL_PATTERNS = [
    r'\btypo\b', r'\bmisspel', r'type\s+wrong',
    r'be\s+more\s+careful', r'don\'?t\s+make\s+this\s+mistake',
    r'check\s+before\s+submit', r'double.?check',
]

def is_trivial(lesson):
    """Return (True, reason) if lesson is too trivial to keep."""
    title = lesson.get('title', '')
    rule = lesson.get('rule', '')
    for pat in TRIVIAL_PATTERNS:
        if re.search(pat, title, re.I) or re.search(pat, rule, re.I):
            return True, f'matches trivial pattern: {pat}'
    return False, ''

# ── Load/Save ──────────────────────────────────────────────────────────

def load_lessons():
    """Load lessons with schema migration (ensure last_used field)."""
    lessons = []
    skipped = 0
    seen_ids = {}
    with open(LESSONS_FILE) as f:
        next_id = 1
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                L = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  [WARN] Line {lineno}: JSON parse error — {e.msg}", file=sys.stderr)
                skipped += 1
                continue
            # Migrate: ensure last_used field
            if 'last_used' not in L:
                L['last_used'] = L.get('last_match', L.get('created'))
            # Warn on duplicate IDs
            lid = L.get('id')
            if lid is not None:
                if lid in seen_ids:
                    print(f"  [WARN] Duplicate id={lid} (line {lineno}) — '{L.get('title', '')[:50]}'", file=sys.stderr)
                else:
                    seen_ids[lid] = lineno
            next_id = max(next_id, (L.get('id') or 0) + 1)
            lessons.append(L)
    if skipped:
        print(f"  [WARN] {skipped} line(s) skipped due to JSON errors", file=sys.stderr)
    return lessons

def save_lessons(lessons, dry_run=False):
    """Save lessons to a temp file then rename for atomic write."""
    if dry_run:
        return
    
    import tempfile, shutil
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(LESSONS_FILE), suffix='.jsonl')
    try:
        with os.fdopen(fd, 'w') as f:
            for L in lessons:
                out = {k: v for k, v in L.items() if not k.startswith('_')}
                f.write(json.dumps(out, ensure_ascii=False) + '\n')
        # Atomic rename
        shutil.move(tmp, LESSONS_FILE)
    except Exception:
        # Cleanup temp file on error
        try: os.unlink(tmp)
        except OSError: pass
        raise

# ── Effectiveness scoring ──────────────────────────────────────────────

def score_lesson(L):
    """Update status based on effectiveness & recency (30d weak / 60d dormant)."""
    current = L.get('status', 'active')
    if current == 'archived':
        return
    
    pc = L.get('prevent_count', 0)
    fc = L.get('fail_count', 0)
    mc = L.get('match_count', 0)
    
    # Save original status for retirement detection
    if '_original_status' not in L:
        L['_original_status'] = current
    
    effectiveness = pc / (pc + fc + 0.01)
    
    # Weak: high match but never prevented + has failures
    if mc >= 5 and fc > 0 and pc == 0:
        L['status'] = 'weak'
        return
    
    # Dormant: never helped, only failed
    if fc >= 3 and pc == 0 and mc >= 3:
        L['status'] = 'dormant'
        return
    
    # Time-based: check last_used (or fallback to last_match)
    last_used = L.get('last_used') or L.get('last_match')
    if last_used and isinstance(last_used, str):
        try:
            lu = datetime.fromisoformat(last_used)
            if lu.tzinfo is None:
                lu = lu.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days = (now - lu).days
            
            # 60+ days → dormant
            if days > 60:
                L['status'] = 'dormant'
                return
            # 30+ days → weak
            if days > 30 and current == 'active':
                L['status'] = 'weak'
                return
        except (ValueError, AttributeError):
            pass
    
    # Default
    if current not in ('archived', 'dormant', 'weak'):
        L['status'] = 'active'


def retirement_report(lessons):
    """List lessons proposed for demotion with reasons. Returns list of dicts."""
    now = datetime.now(timezone.utc)
    report = []
    for L in lessons:
        if L.get('status') == 'archived':
            continue
        original = L.get('_original_status', L.get('status', 'active'))
        new_status = L.get('status', 'active')
        if new_status == original:
            continue
        reason = ''
        if new_status == 'weak':
            last_used = L.get('last_used') or L.get('last_match')
            if last_used:
                try:
                    lu = datetime.fromisoformat(last_used)
                    if lu.tzinfo is None:
                        lu = lu.replace(tzinfo=timezone.utc)
                    days = (now - lu).days
                    if 30 < days <= 60:
                        reason = f"未使用 {days} 天 (>30天)"
                    else:
                        reason = "低有效性评分"
                except (ValueError, AttributeError):
                    reason = "低有效性评分"
            else:
                reason = "低有效性评分"
        elif new_status == 'dormant':
            last_used = L.get('last_used') or L.get('last_match')
            if last_used:
                try:
                    lu = datetime.fromisoformat(last_used)
                    if lu.tzinfo is None:
                        lu = lu.replace(tzinfo=timezone.utc)
                    days = (now - lu).days
                    reason = f"未使用 {days} 天 (>60天)"
                except (ValueError, AttributeError):
                    reason = "从未命中 / 仅失败"
            else:
                reason = "从未使用"
        report.append({
            'id': L.get('id'),
            'title': L.get('title', ''),
            'original_status': original,
            'new_status': new_status,
            'reason': reason,
        })
    return report

# ── Merge similar ─────────────────────────────────────────────────────

def tagset(L):
    return '::'.join(sorted(L.get('tags', [])))

def trigger_keywords(L):
    t = L.get('trigger', '')
    kw = set(w.lower().strip('.,;:!?') for w in t.split() if len(w) > 2)
    kw.update(w.lower().strip('.,;:!?') for w in L.get('title', '').split() if len(w) > 2)
    return kw

def merge_similar(lessons, dry_run, verbose):
    """Merge lessons with same tagset and overlapping trigger keywords."""
    groups = defaultdict(list)
    for L in lessons:
        if L.get('status') == 'archived':
            groups['archived'].append(L)
            continue
        groups[tagset(L)].append(L)
    
    merged = []
    merged_ids = set()
    
    for ts, group in groups.items():
        if ts == 'archived':
            merged.extend(group)
            continue
            
        # Check for merge candidates within group
        consumed = set()
        keep = []
        for i in range(len(group)):
            if group[i].get('id') in consumed:
                continue
            keep.append(group[i])
            for j in range(i+1, len(group)):
                if group[j].get('id') in consumed:
                    continue
                kw_i = trigger_keywords(group[i])
                kw_j = trigger_keywords(group[j])
                overlap = kw_i & kw_j
                if len(overlap) >= 2:
                    if verbose:
                        print(f"  MERGE: #{group[i]['id']} <- #{group[j]['id']}")
                    group[i]['match_count'] = max(group[i].get('match_count', 0), group[j].get('match_count', 0))
                    group[i]['prevent_count'] = max(group[i].get('prevent_count', 0), group[j].get('prevent_count', 0))
                    group[i]['fail_count'] = max(group[i].get('fail_count', 0), group[j].get('fail_count', 0))
                    group[i]['trigger'] = group[i].get('trigger', '') + ' | ' + group[j].get('trigger', '')
                    consumed.add(group[j]['id'])
                    merged_ids.add(group[j]['id'])
        merged.extend(keep)
    
    return merged

# ── Conflict detection ─────────────────────────────────────────────────

RULE_SIGN_KEYWORDS = {
    'use': '+', 'run': '+', 'do': '+', 'prefer': '+', 'always': '+',
    'don\'t': '-', 'avoid': '-', 'never': '-', 'skip': '-', 'not': '-',
}

def rule_sign(rule):
    """Approximate polarity of a rule."""
    plus = sum(1 for kw in RULE_SIGN_KEYWORDS if kw in rule.lower() and RULE_SIGN_KEYWORDS[kw] == '+')
    minus = sum(1 for kw in RULE_SIGN_KEYWORDS if kw in rule.lower() and RULE_SIGN_KEYWORDS[kw] == '-')
    return plus - minus

def detect_conflicts(lessons, verbose=False):
    """Find lessons with same tags but opposite rules."""
    conflicts = []
    for i in range(len(lessons)):
        if lessons[i].get('status') in ('archived', 'dormant'):
            continue
        for j in range(i+1, len(lessons)):
            if lessons[j].get('status') in ('archived', 'dormant'):
                continue
            if tagset(lessons[i]) == tagset(lessons[j]):
                sig_i = rule_sign(lessons[i].get('rule', ''))
                sig_j = rule_sign(lessons[j].get('rule', ''))
                if sig_i * sig_j < 0:
                    conflicts.append({'a': lessons[i]['id'], 'b': lessons[j]['id'], 'sign_a': sig_i, 'sign_b': sig_j})
                    if verbose:
                        print(f"  CONFLICT: #{lessons[i]['id']} vs #{lessons[j]['id']} (sign {sig_i} vs {sig_j})")
    return conflicts

# ── Quality check ─────────────────────────────────────────────────────

def quality_check(lessons, dry_run, verbose):
    """Flag trivial lessons as weak."""
    flagged = 0
    for L in lessons:
        if L.get('status') == 'archived':
            continue
        trivial, reason = is_trivial(L)
        if trivial:
            if verbose:
                print(f"  TRIVIAL #{L['id']}: {L['title']} - {reason}")
            if not dry_run:
                L['status'] = 'weak'
            flagged += 1
    return flagged

# ── Main ───────────────────────────────────────────────────────────────

def main():
    dry_run = '--dry-run' in sys.argv
    verbose = '--verbose' in sys.argv
    
    if not os.path.exists(LESSONS_FILE):
        print(f"ERROR: {LESSONS_FILE} not found")
        sys.exit(1)
    
    lessons = load_lessons()
    print(f"Loaded {len(lessons)} lessons")
    
    # 1. Quality check (flag trivial before scoring)
    trivial_count = quality_check(lessons, dry_run, verbose)
    if trivial_count:
        print(f"  Quality: {trivial_count} trivial lessons flagged")
    
    # 2. Score all + generate retirement report
    for L in lessons:
        # Save original status before scoring for comparison
        if '_original_status' not in L:
            L['_original_status'] = L.get('status', 'active')
        score_lesson(L)
    
    # Retirement report
    retired = retirement_report(lessons)
    if retired:
        print(f"\n  ⚠ Retirements proposed ({len(retired)}):")
        for r in retired:
            print(f"    #{r['id']} \"{r['title'][:50]}\"  ({r['original_status']} → {r['new_status']})  {r['reason']}")
    
    active = sum(1 for L in lessons if L.get('status') == 'active')
    weak = sum(1 for L in lessons if L.get('status') == 'weak')
    dormant = sum(1 for L in lessons if L.get('status') == 'dormant')
    archived = sum(1 for L in lessons if L.get('status') == 'archived')
    print(f"  Status: {active} active, {weak} weak, {dormant} dormant, {archived} archived")
    
    # 3. Merge similar
    before = len(lessons)
    lessons = merge_similar(lessons, dry_run, verbose)
    after = len(lessons)
    if after < before:
        print(f"  Merged: {before - after} lessons removed")
    
    # 4. Detect conflicts
    conflicts = detect_conflicts(lessons, verbose)
    if conflicts and not dry_run:
        for c in conflicts:
            for L in lessons:
                if L['id'] in (c['a'], c['b']):
                    L.setdefault('conflict_with', [])
                    other = c['b'] if L['id'] == c['a'] else c['a']
                    if other not in L['conflict_with']:
                        L['conflict_with'].append(other)
    
    # 5. Save
    save_lessons(lessons, dry_run)
    
    print(f"\nResults: {len(lessons)} lessons saved")
    if conflicts:
        print(f"  Conflicts flagged: {len(conflicts)}")
    print("OK" if not dry_run else "DRY RUN - no changes made")

if __name__ == '__main__':
    main()
