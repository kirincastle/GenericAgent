#!/usr/bin/env python3
"""Kill old monitor, start new one"""
import subprocess, os, time, sys

# Kill old instances
subprocess.run(['pkill', '-f', 'server.py.*10000'], capture_output=True, timeout=5)
time.sleep(0.5)

devnull = open(os.devnull, 'w')
p = subprocess.Popen(
    ['python3', '/home/moclaw/projects/external/genericagent/ga_monitor/server.py', '10000'],
    stdout=devnull, stderr=devnull)
time.sleep(1)

# Verify
r = subprocess.run(['pgrep', '-af', 'server.py.*10000'], capture_output=True, text=True, timeout=5)
for line in r.stdout.strip().splitlines():
    if '10000' in line and 'server.py' in line:
        print(f"RUNNING: {line.strip()}")
        break
else:
    print("DEAD")

# Quick API test
import urllib.request
try:
    resp = urllib.request.urlopen('http://localhost:10000/api/status', timeout=3)
    print(f"API OK ({len(resp.read())} bytes)")
except Exception as e:
    print(f"API FAIL: {e}")
