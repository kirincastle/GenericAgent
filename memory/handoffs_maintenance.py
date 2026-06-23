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

def mark_progress(hs, handoff_id, user_confirmed):
    """Called by L1 'continue' flow. User picks handoff -> in_progress."""
    for h in hs:
        if h['id'] == handoff_id and h.get('status') == 'active':
            h['status'] = 'in_progress' if user_confirmed else 'active'
            return h['id']
    return None

def close_session(hs, session_topic, completed):
    """Called by /neat. Finds in_progress for this session_topic."""
    out = []
    for h in hs:
        if (h.get('status') == 'in_progress' and
            h.get('session_topic') == session_topic):
            if completed:
                h['status'] = 'superseded'
                out.append(('superseded', h['id']))
            else:
                h['status'] = 'active'
                out.append(('active', h['id']))
    return out

def update_index(hs, dry):
    active = [h for h in hs if h.get('status') == 'active']
    in_progress = [h for h in hs if h.get('status') == 'in_progress']
    lines = ['---', 'type: index', 'title: "Handoffs Index"',
             'date: 2026-06-23', 'tags: [handoffs, index]',
             'intent: "Central registry of session handoffs"',
             '---', '', '# Handoffs Index', '', '## Active']
    if active:
        for h in active:
            tag = f"[{h.get('session_topic', 'general')}]"
            lines.append(f'- {tag} [{h.get("title", h["id"])}]({h.get("file", "")})')
    else:
        lines.append('*(no active handoffs)*')
    lines.append('')
    lines.append('## In Progress')
    if in_progress:
        for h in in_progress:
            tag = f"[{h.get('session_topic', 'general')}]"
            lines.append(f'- {tag} [{h.get("title", h["id"])}]({h.get("file", "")})  *(picked up)*')
    else:
        lines.append('*(none)*')
    lines.append('')
    lines.append('## Recently Completed')
    for h in hs:
        if h.get('status') in ('completed', 'done', 'superseded'):
            lines.append(f'- ~~[{h.get("title", h["id"])}]({h.get("file", "")})~~')
    if not dry:
        with open(INDEX_FILE, 'w') as f:
            f.write('\n'.join(lines))
    return lines

def main():
    dry = '--dry-run' in sys.argv
    hs = load()
    print(f'Loaded {len(hs)} handoffs')
    active_self = [h for h in hs if h.get('status') == 'active']
    in_progress = [h for h in hs if h.get('status') == 'in_progress']
    active_other = [h for h in hs if h.get('status') == 'active' and h not in active_self]
    print(f'  Active (self): {len(active_self)}')
    print(f'  Active (other): {len(active_other)}')
    if in_progress:
        print(f'  In-progress (pending resolution): {len(in_progress)}')
        for h in in_progress:
            print(f'    {h["id"]}: {h.get("title","")}')
    update_index(hs, dry)
    save(hs, dry)
    print('OK' if not dry else 'DRY RUN - no changes made')

if __name__ == '__main__': main()
