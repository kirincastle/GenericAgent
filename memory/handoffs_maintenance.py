#!/usr/bin/env python3
"""Handoff lifecycle management. Run as part of /neat."""
import json, sys, os
HANDOFFS_FILE = os.path.join(os.path.dirname(__file__), 'handoffs', 'handoffs.jsonl')
INDEX_FILE = os.path.join(os.path.dirname(__file__), 'handoffs', 'index.md')

def load(): 
    if not os.path.exists(HANDOFFS_FILE): return []
    with open(HANDOFFS_FILE) as f: return [json.loads(l) for l in f if l.strip()]

def save(hs, dry):
    if not dry:
        with open(HANDOFFS_FILE, 'w') as f:
            for h in hs: f.write(json.dumps(h, ensure_ascii=False) + '\n')

def supersede(hs):
    out = []
    for h in hs:
        if h.get('status') == 'active':
            h['status'] = 'superseded'
            out.append(h['id'])
    return out

def update_index(hs, dry):
    active = [h for h in hs if h.get('status') == 'active']
    lines = ['---', 'type: index', 'title: "Handoffs Index"', 'date: 2026-06-23',
             'tags: [handoffs, index]', 'intent: "Central registry of session handoffs"',
             '---', '', '# Handoffs Index', '', '## Active']
    if active:
        for h in active:
            lines.append(f'- [{h.get("title", h["id"])}]({h.get("file", "")})')
    else:
        lines.append('*(no active handoffs)*')
    lines.append('')
    lines.append('## Recently Completed')
    for h in hs:
        if h.get('status') in ('completed', 'done'):
            lines.append(f'- ~~[{h.get("title", h["id"])}]({h.get("file", "")})~~')
    if not dry:
        with open(INDEX_FILE, 'w') as f:
            f.write('\n'.join(lines))
    return lines

def main():
    dry = '--dry-run' in sys.argv
    hs = load()
    print(f'Loaded {len(hs)} handoffs')
    active_before = [h for h in hs if h.get('status') == 'active']
    if active_before:
        for h in active_before: print(f'  Active: {h["id"]}')
    sups = supersede(hs)
    if sups: print(f'  Superseded: {len(sups)}')
    for s in sups: print(f'    -> {s}')
    save(hs, dry)
    update_index(hs, dry)
    print('OK' if not dry else 'DRY RUN - no changes made')
if __name__ == '__main__': main()
