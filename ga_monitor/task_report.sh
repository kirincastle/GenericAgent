#!/usr/bin/env bash
# task_report.sh — Shell wrapper for task status reporting
# Uses flock for concurrency safety on task_status.json
#
# Usage:
#   ./task_report.sh --id <task_id> \
#     --title "Task Title" --type <type> --host <host> \
#     --phase <phase> --status <status> --progress <0-100> --msg "Message"
#
#   # Minimal update (only change progress and message):
#   ./task_report.sh --id upgrade-jpkab --progress 60 --msg "Running..."
#
#   # Mark complete:
#   ./task_report.sh --id upgrade-jpkab --status completed --progress 100
#
# Status enum: pending running completed failed stuck cancelled

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JSON_FILE="$SCRIPT_DIR/task_status.json"
LOCK_FILE="$JSON_FILE.lock"

# ---- Defaults ----
ID=""
TITLE=""
TYPE=""
HOST=""
PHASE=""
STATUS=""
PROGRESS=""
MSG=""

# ---- Parse CLI args ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --id)        ID="$2";        shift 2 ;;
        --title)     TITLE="$2";     shift 2 ;;
        --type)      TYPE="$2";      shift 2 ;;
        --host)      HOST="$2";      shift 2 ;;
        --phase)     PHASE="$2";     shift 2 ;;
        --status)    STATUS="$2";    shift 2 ;;
        --progress)  PROGRESS="$2";  shift 2 ;;
        --msg)       MSG="$2";       shift 2 ;;
        *) echo "Error: Unknown option '$1'"; exit 1 ;;
    esac
done

if [[ -z "$ID" ]]; then
    echo "Error: --id is required"
    exit 1
fi

# ---- Acquire flock and update ----
(
    flock -x 200 || { echo "Error: cannot acquire lock"; exit 1; }

    # Pass values via env vars to avoid quoting/escaping issues
    export _TASK_ID="$ID"
    export _TASK_TITLE="$TITLE"
    export _TASK_TYPE="$TYPE"
    export _TASK_HOST="$HOST"
    export _TASK_PHASE="$PHASE"
    export _TASK_STATUS="$STATUS"
    export _TASK_PROGRESS="$PROGRESS"
    export _TASK_MSG="$MSG"
    export _JSON_FILE="$JSON_FILE"

    python3 -c '
import json, os
from datetime import datetime, timezone

json_file = os.environ["_JSON_FILE"]
task_id  = os.environ["_TASK_ID"]
title    = os.environ["_TASK_TITLE"]
task_type = os.environ["_TASK_TYPE"]
host     = os.environ["_TASK_HOST"]
phase    = os.environ["_TASK_PHASE"]
status   = os.environ["_TASK_STATUS"]
progress = os.environ["_TASK_PROGRESS"]
msg      = os.environ["_TASK_MSG"]

# Read existing JSON
if os.path.exists(json_file) and os.path.getsize(json_file) > 0:
    with open(json_file) as f:
        data = json.load(f)
else:
    data = {"tasks": {}, "types": {}, "last_updated": ""}

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# Get or create task
task = data["tasks"].get(task_id, {})
is_new = task_id not in data["tasks"]

if is_new:
    task = {"id": task_id, "started_at": now}

# Update only non-empty fields
if title:      task["title"] = title
if task_type:  task["type"] = task_type
if host:       task["host"] = host
if phase:      task["phase"] = phase
if status:     task["status"] = status
if progress:   task["progress_pct"] = int(progress)
if msg:        task["message"] = msg

task["last_update"] = now
data["tasks"][task_id] = task

# Recalculate types index
types_index = {}
for tid, t in data["tasks"].items():
    ttype = t.get("type", "unknown")
    tstatus = t.get("status", "unknown")
    if ttype not in types_index:
        types_index[ttype] = {"total": 0, "running": 0, "completed": 0, "failed": 0,
                              "pending": 0, "stuck": 0, "cancelled": 0}
    types_index[ttype]["total"] += 1
    if tstatus in types_index[ttype]:
        types_index[ttype][tstatus] += 1

data["types"] = types_index
data["last_updated"] = now

# Write atomically: tmp then replace
tmp = json_file + ".tmp"
with open(tmp, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
os.replace(tmp, json_file)
print("OK: task [{}] updated".format(task_id))
' || { echo "Error: Python update failed"; exit 1; }

) 200>"$LOCK_FILE"

exit 0
