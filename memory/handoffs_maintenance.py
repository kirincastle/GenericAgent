#!/usr/bin/env python3
"""Handoff lifecycle management. Run as part of /neat.
v2 — Added structured checklist with auto-verify.
"""
import json, sys, os, subprocess

HANDOFFS_FILE = os.path.join(os.path.dirname(__file__), 'handoffs', 'handoffs.jsonl')
INDEX_FILE = os.path.join(os.path.dirname(__file__), 'handoffs', 'index.md')

def load():
    if not os.path.exists(HANDOFFS_FILE): return []
    with open(HANDOFFS_FILE) as f: return [json.loads(l) for l in f if l.strip()]

def save(hs, dry):
    if not dry:
        with open(HANDOFFS_FILE, 'w') as f:
            for h in hs: f.write(json.dumps(h, ensure_ascii=False) + '\n')

def mark_progress(hs, handoff_id, user_confirmed, dry=False):
    for h in hs:
        if h['id'] == handoff_id and h.get('status') == 'active':
            h['status'] = 'in_progress' if user_confirmed else 'active'
            save(hs, dry)
            return h['id']
    return None

# ── Checklist verification ──────────────────────────────────────

VERIFY_TYPES = {
    'file_exists': '目标文件是否存在',
    'code_search': '代码中是否含特定模式',
    'dir_search':  '目录下是否有匹配文件',
    'git_log':     'Git 提交记录（某目录有改动）',
    'manual':      '必须人工确认',
}

def verify_checklist_item(item, project_root=None):
    """Auto-verify a single checklist item.
    Returns True (pass) | False (fail) | None (needs human / not applicable).
    """
    vtype = item.get('verify', 'manual')
    target = item.get('target', '')
    search_for = item.get('search_for', '')
    
    # Resolve path
    if project_root and target and not target.startswith('/'):
        path = os.path.join(project_root, target)
    else:
        path = target

    try:
        if vtype == 'file_exists':
            return os.path.exists(path) if path else False

        elif vtype == 'code_search':
            if not path or not os.path.exists(path):
                return False
            r = subprocess.run(['grep', '-q', search_for, path],
                               capture_output=True, timeout=10)
            return r.returncode == 0

        elif vtype == 'dir_search':
            if not path or not os.path.isdir(path):
                return False
            pattern = search_for or '*'
            r = subprocess.run(['find', path, '-maxdepth', '2', '-name', pattern],
                               capture_output=True, timeout=10)
            return len(r.stdout.strip()) > 0

        elif vtype == 'git_log':
            since = item.get('since', '')
            cwd = project_root or os.getcwd()
            cmd = ['git', 'log', '--oneline']
            if since:
                cmd.extend(['--since', since])
            if target:
                cmd.append('--')
                cmd.append(target)
            r = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=10)
            return len(r.stdout.strip().split(b'\n')) > 0

        elif vtype == 'manual':
            return None

        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

def verify_handoff_checklist(h):
    """Run verification on all checklist items in a handoff. Returns summary dict."""
    checklist = h.get('checklist', [])
    if not checklist:
        return {'checked': 0, 'passed': 0, 'failed': 0, 'manual': 0, 'items': []}

    project_root = h.get('project_root', '')
    results = []
    passed = failed = manual = 0

    for item in checklist:
        result = verify_checklist_item(item, project_root)
        old_status = item.get('status', 'pending')
        
        if result is True:
            item['status'] = 'verified'
            passed += 1
        elif result is False:
            item['status'] = old_status if old_status != 'verified' else 'pending'
            failed += 1
        else:
            manual += 1
            # keep existing status for manual items
        
        results.append({
            'id': item.get('id', '?'),
            'desc': item.get('desc', ''),
            'verify': item.get('verify', 'manual'),
            'status': item['status'],
            'auto_passed': result,
        })

    return {
        'checked': len(checklist),
        'passed': passed,
        'failed': failed,
        'manual': manual,
        'items': results,
    }

def set_checklist_item(hs, hid, item_id, status='verified', dry=False):
    """Manually set a checklist item's status (e.g. after design review approval).
    Used by `verify-item` CLI subcommand.
    """
    for h in hs:
        if h['id'] == hid:
            checklist = h.get('checklist', [])
            for item in checklist:
                if item['id'] == item_id:
                    item['status'] = status
                    if not dry:
                        save(hs, dry)
                    return {'id': hid, 'item_id': item_id, 'status': status}
            return {'error': f'Item {item_id} not found in handoff {hid}'}
    return {'error': f'Handoff {hid} not found'}

# ── Close session (modified) ────────────────────────────────────

def close_session(hs, session_topic, completed, dry=False):
    """Called by /neat. Finds in_progress for this session_topic.
    Runs auto-verification on checklist items.
    """
    out = []
    for h in hs:
        if h.get('status') == 'in_progress' and h.get('session_topic') == session_topic:
            
            # ── Auto-verify checklist ──
            checklist = h.get('checklist', [])
            if checklist:
                summary = verify_handoff_checklist(h)
                print(f"\n╔══ Checklist Verification: {h['id']} ══╗")
                for r in summary['items']:
                    icon = '✅' if r['auto_passed'] is True else ('❌' if r['auto_passed'] is False else '⏳')
                    print(f"  {icon} [{r['id']}] {r['desc']}  ({r['status']})")
                print(f"  ── {summary['passed']} passed / {summary['failed']} failed / {summary['manual']} manual")
                if summary['failed'] > 0:
                    print(f"  ⚠️  {summary['failed']} auto-checks FAILED — manual review needed")
                print(f"╚════════════════════════════════════════╝")
            
            # ── Status transition ──
            if completed:
                h['status'] = 'superseded'
                out.append(('superseded', h['id']))
            else:
                h['status'] = 'active'
                out.append(('active', h['id']))
    
    if not dry:
        save(hs, dry)
    return out

# ── Index ───────────────────────────────────────────────────────

def update_index(hs, dry):
    active = [h for h in hs if h.get('status') == 'active']
    in_progress = [h for h in hs if h.get('status') == 'in_progress']
    lines = [
        '---', 'type: index', 'title: "Handoffs Index"',
        'date: 2026-06-26', 'tags: [handoffs, index]',
        'intent: "Central registry of session handoffs"',
        '---', '', '# Handoffs Index', '', '## Active'
    ]
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

# ── CLI ─────────────────────────────────────────────────────────

def main():
    dry = '--dry-run' in sys.argv
    hs = load()

    # mark <handoff_id>
    if len(sys.argv) >= 3 and sys.argv[1] == 'mark':
        hid = sys.argv[2]
        res = mark_progress(hs, hid, user_confirmed=True, dry=dry)
        if res:
            print(f'Marked {res} as in_progress')
        else:
            print(f'Handoff not found or not active: {hid}', file=sys.stderr)
            sys.exit(1)
        return

    # verify <handoff_id>
    if len(sys.argv) >= 3 and sys.argv[1] == 'verify':
        hid = sys.argv[2]
        for h in hs:
            if h['id'] == hid:
                summary = verify_handoff_checklist(h)
                print(json.dumps(summary, indent=2, ensure_ascii=False))
                save(hs, dry)
                return
        print(f'Handoff not found: {hid}', file=sys.stderr)
        sys.exit(1)

    # verify-item <handoff_id> <item_id> [--status verified|pending]
    if len(sys.argv) >= 4 and sys.argv[1] == 'verify-item':
        hid = sys.argv[2]
        item_id = sys.argv[3]
        status = 'verified'
        if '--status' in sys.argv:
            idx = sys.argv.index('--status')
            if idx + 1 < len(sys.argv):
                status = sys.argv[idx + 1]
        res = set_checklist_item(hs, hid, item_id, status, dry=dry)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        save(hs, dry)
        return

    # close <session_topic> [--not-done]
    if len(sys.argv) >= 3 and sys.argv[1] == 'close':
        topic = sys.argv[2]
        completed = '--not-done' not in sys.argv
        results = close_session(hs, topic, completed, dry=dry)
        for status, hid in results:
            print(f'{hid} -> {status}')
        update_index(hs, dry)
        save(hs, dry)
        return

    # list status
    print(f'Loaded {len(hs)} handoffs')
    active_hs = [h for h in hs if h.get('status') == 'active']
    in_progress_hs = [h for h in hs if h.get('status') == 'in_progress']
    print(f'  Active: {len(active_hs)}')
    print(f'  In-progress: {len(in_progress_hs)}')
    for h in in_progress_hs:
        cl = h.get('checklist', [])
        cl_info = f' ({len(cl)} checklist items)' if cl else ''
        print(f'    {h["id"]}: {h.get("title","")}{cl_info}')
    for h in active_hs:
        print(f'    {h["id"]}: {h.get("title","")}')
    update_index(hs, dry)
    save(hs, dry)
    print('OK' if not dry else 'DRY RUN - no changes made')

if __name__ == '__main__':
    main()
