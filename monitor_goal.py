#!/usr/bin/env python3
"""Goal agent monitor - logs progress every 5 minutes."""
import subprocess, time, os, re, sys
from datetime import datetime

GOAL_PID = 49036
LOG_FILE = "goal_progress.log"
SESSION_FILE = "temp/model_responses/model_responses_544774.txt"
OC2API_DIR = "/home/moclaw/projects/oc2api"
START_TIME = time.time()
BUDGET_SEC = 30 * 60

def check():
    now = time.time()
    elapsed_m = int((now - START_TIME) / 60)
    remaining_m = max(0, int((BUDGET_SEC - (now - START_TIME)) / 60))
    ts = datetime.now().strftime('%H:%M:%S')
    
    # Process alive?
    alive = os.path.exists(f"/proc/{GOAL_PID}")
    
    lines = [f"--- Check at {ts} (elapsed: {elapsed_m}m, remain: {remaining_m}m) ---"]
    lines.append(f"Process alive: {alive}")
    
    if alive:
        try:
            ps = subprocess.run(['ps', '-p', str(GOAL_PID), '-o', 'pid,etime,%cpu,%mem,args'],
                              capture_output=True, text=True, timeout=5)
            lines.append(f"Process: {ps.stdout.strip()}")
        except:
            pass
    
    # Session stats
    try:
        with open(SESSION_FILE) as f:
            text = f.read()
        parts = text.split('=== Response ===')
        turn_count = len(parts) - 1
        lines.append(f"Session turns: {turn_count}")
        
        if len(parts) > 1:
            last = parts[-1]
            # Get thinking
            m = re.search(r'<thinking>(.*?)</thinking>', last, re.DOTALL)
            if m:
                thinking = m.group(1).strip()[:400]
                lines.append(f"Thinking: {thinking}")
            else:
                # Get last meaningful line
                clean = re.sub(r'<[^>]+>', '', last).strip()
                clines = [l.strip() for l in clean.split('\n') if l.strip()]
                if clines:
                    lines.append(f"Last: {clines[-1][:200]}")
    except Exception as e:
        lines.append(f"Session read error: {e}")
    
    # Modified Go files
    try:
        result = subprocess.run(['find', OC2API_DIR, '-cmin', '-6', '-name', '*.go', '-type', 'f'],
                              capture_output=True, text=True, timeout=5)
        mods = [l for l in result.stdout.strip().split('\n') if l]
        if mods:
            lines.append("Modified Go files:")
            for f in mods[:5]:
                lines.append(f"  {f}")
        else:
            lines.append("Modified Go files: (none)")
    except:
        pass
    
    # Write log
    with open(LOG_FILE, 'a') as f:
        f.write('\n'.join(lines) + '\n\n')
    
    return lines

# First check immediately
check()

# Then every 5 minutes (but also check if process died)
while True:
    time.sleep(300)
    lines = check()
    final = not os.path.exists(f"/proc/{GOAL_PID}")
    if final:
        with open(LOG_FILE, 'a') as f:
            f.write(f"=== Process {GOAL_PID} terminated at {datetime.now().strftime('%H:%M:%S')} ===\n")
        break
