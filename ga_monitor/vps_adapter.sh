#!/usr/bin/env bash
# vps_adapter.sh — VPS 升级状态轮询适配器
#
# SSH 轮询 11 台 VPS 的 OS/内核/dpkg 锁/升级进程，
# 通过 task_report.sh 更新 task_status.json。
#
# 用法:
#   ./vps_adapter.sh --init                     # 注册所有 VPS 任务（pending）
#   ./vps_adapter.sh --poll                     # 单轮轮询全部主机
#   ./vps_adapter.sh --poll --host jpkab        # 仅单台
#   ./vps_adapter.sh --daemon                   # 守护模式（每 300s 轮询）
#   ./vps_adapter.sh --daemon --interval 120    # 自定义间隔（秒）
#
# 兼容: bash 4+ (需要 declare -A)
# 依赖: ssh, task_report.sh (同目录)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORT_SCRIPT="$SCRIPT_DIR/task_report.sh"

# ─── 配置 ──────────────────────────────────────────────────────────────────────
SSH_BASE="root@%s.20122102.xyz"
SSH_OPTS=(
  -o StrictHostKeyChecking=no
  -o ConnectTimeout=8
  -o BatchMode=yes
  -o ServerAliveInterval=3
  -o ServerAliveCountMax=2
)

# VPS 列表（按地域分组，仅供可读性）
VPS_AMT=(amtaa amtab amtac)
VPS_JPK=(jpkaaa jpkab jpkac jpkbc)
VPS_KRK=(krkab krkac krkad krkca)
VPS_ALL=("${VPS_AMT[@]}" "${VPS_JPK[@]}" "${VPS_KRK[@]}")

# SSH 远程命令（一次连接获取全部信息）
REMOTE_CMDS=(
  'echo "---LSB_RELEASE---"'
  'lsb_release -d 2>/dev/null || echo "N/A"'
  'echo "---UNAME---"'
  'uname -r 2>/dev/null'
  'echo "---DPKG_LOCK---"'
  'if lsof /var/lib/dpkg/lock-frontend 2>/dev/null; then echo "LOCKED:frontend";'
  'elif fuser /var/lib/dpkg/lock 2>/dev/null; then echo "LOCKED:lock";'
  'elif lsof /var/lib/apt/lists/lock 2>/dev/null; then echo "LOCKED:apt-lists";'
  'else echo "FREE"; fi'
  'echo "---DO_RELEASE_UPGRADE---"'
  'if pgrep -a do-release-upgrade 2>/dev/null; then echo "RUNNING";'
  'elif [ -f /var/log/do-release-upgrade.log ]; then'
  '  tail -3 /var/log/do-release-upgrade.log 2>/dev/null | head -1;'
  '  echo "LOG_EXISTS";'
  'else echo "NOT_RUNNING"; fi'
  'echo "---UPTIME---"'
  'uptime -p 2>/dev/null || uptime 2>/dev/null'
  'echo "---LOAD---"'
  'cat /proc/loadavg 2>/dev/null'
)
REMOTE_SCRIPT=$(IFS=$'\n'; echo "${REMOTE_CMDS[*]}")

# ─── 工具函数 ──────────────────────────────────────────────────────────────────

# 构建 SSH 主机名
ssh_host() {
  local host="$1"
  printf "$SSH_BASE" "$host"
}

# 执行远程检查，返回原始输出
remote_check() {
  local host="$1"
  ssh "${SSH_OPTS[@]}" "$(ssh_host "$host")" bash <<<"$REMOTE_SCRIPT" 2>&1 || {
    echo "---SSH_ERROR---"
    echo "exit_code:$?"
    return 1
  }
}

# 解析远程输出为关联数组
parse_remote_output() {
  local raw="$1"
  local -n _result="$2"

  local section=""
  local content=""

  while IFS= read -r line; do
    if [[ "$line" =~ ^---([A-Z_]+)---$ ]]; then
      if [[ -n "$section" ]]; then
        _result["$section"]="$(echo "$content" | sed '/^$/d' | head -c 500)"
      fi
      section="${BASH_REMATCH[1]}"
      content=""
    else
      content+="$line"$'\n'
    fi
  done <<< "$raw"

  # 最后一段
  if [[ -n "$section" ]]; then
    _result["$section"]="$(echo "$content" | sed '/^$/d' | head -c 500)"
  fi
}

# 根据检查结果判定状态
determine_status() {
  local -n _d_data="$1"

  local lsb_release="${_d_data[LSB_RELEASE]:-}"
  local dplock="${_d_data[DPKG_LOCK]:-}"
  local upgrade="${_d_data[DO_RELEASE_UPGRADE]:-}"

  # SSH 失败
  if [[ -n "${_d_data[SSH_ERROR]:-}" ]]; then
    echo "stuck"
    return
  fi

  # dpkg 锁 → 可能正在安装包（升级中或卡住）
  if [[ "$dplock" == LOCKED:* ]]; then
    if [[ "$upgrade" == RUNNING ]]; then
      echo "running"
    else
      # 有锁但没升级进程 → 可能卡住或手动操作
      echo "running"
    fi
    return
  fi

  # do-release-upgrade 正在运行
  if [[ "$upgrade" == RUNNING ]]; then
    echo "running"
    return
  fi

  # 已升级到 24.04
  if [[ "$lsb_release" == *"24.04"* ]]; then
    echo "completed"
    return
  fi

  # 有升级日志但进程不在运行
  if [[ "$upgrade" == *"LOG_EXISTS"* ]]; then
    echo "stuck"
    return
  fi

  # 默认：等待执行
  echo "pending"
}

# 构造人类可读的消息
build_message() {
  local -n _b_data="$1"

  local os="${_b_data[LSB_RELEASE]:-N/A}"
  local kernel="${_b_data[UNAME]:-N/A}"
  local dplock="${_b_data[DPKG_LOCK]:-unknown}"
  local upgrade="${_b_data[DO_RELEASE_UPGRADE]:-unknown}"
  local load="${_b_data[LOAD]:-}"
  local ssh_err="${_b_data[SSH_ERROR]:-}"

  if [[ -n "$ssh_err" ]]; then
    echo "SSH unreachable: $ssh_err"
    return
  fi

  local msg=""
  msg+="OS: $(echo "$os" | head -1) | "
  msg+="kernel: $kernel | "
  msg+="dpkg: $dplock | "
  msg+="upgrade: $(echo "$upgrade" | head -1)"

  if [[ -n "$load" ]]; then
    msg+=" | load: $(echo "$load" | head -c 30)"
  fi

  echo "$msg"
}

# 通过 task_report.sh 更新任务状态，带降级
update_task() {
  local id="$1"
  shift
  local args=("$@")

  if [[ -x "$REPORT_SCRIPT" ]]; then
    "$REPORT_SCRIPT" --id "$id" "${args[@]}" 2>&1 || {
      echo "WARN: task_report.sh failed for $id, fallback to direct JSON write"
      direct_json_update "$id" "${args[@]}"
    }
  else
    echo "WARN: task_report.sh not found, direct JSON write"
    direct_json_update "$id" "${args[@]}"
  fi
}

# 降级：直接写 task_status.json（与 task_report.sh 相同逻辑）
direct_json_update() {
  local id="$1"
  shift
  local title="" type="" host="" phase="" status="" progress="" msg=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title)    title="$2";    shift 2 ;;
      --type)     type="$2";     shift 2 ;;
      --host)     host="$2";     shift 2 ;;
      --phase)    phase="$2";    shift 2 ;;
      --status)   status="$2";   shift 2 ;;
      --progress) progress="$2"; shift 2 ;;
      --msg)      msg="$2";      shift 2 ;;
      *) shift 1 ;;
    esac
  done

  # Pass vars via env for safety, heredoc for script body (no shell expansion)
  (
    flock -x 200 2>/dev/null || { echo "WARN: cannot acquire lock for $id"; exit 1; }

    _DIRECT_ID="$id" \
    _DIRECT_TITLE="$title" \
    _DIRECT_TYPE="$type" \
    _DIRECT_HOST="$host" \
    _DIRECT_PHASE="$phase" \
    _DIRECT_STATUS="$status" \
    _DIRECT_PROGRESS="$progress" \
    _DIRECT_MSG="$msg" \
    _DIRECT_JSON_FILE="$JSON_FILE" \
    python3 << 'PYEOF'
import json, os, sys
from datetime import datetime, timezone

json_file = os.environ["_DIRECT_JSON_FILE"]
task_id   = os.environ.get("_DIRECT_ID", "")
title     = os.environ.get("_DIRECT_TITLE", "")
task_type = os.environ.get("_DIRECT_TYPE", "")
host      = os.environ.get("_DIRECT_HOST", "")
phase     = os.environ.get("_DIRECT_PHASE", "")
status    = os.environ.get("_DIRECT_STATUS", "")
progress  = os.environ.get("_DIRECT_PROGRESS", "")
msg       = os.environ.get("_DIRECT_MSG", "")

if not task_id:
    print("FATAL: no task_id", file=sys.stderr)
    sys.exit(1)

if os.path.exists(json_file) and os.path.getsize(json_file) > 0:
    with open(json_file) as f:
        data = json.load(f)
else:
    data = {"tasks": {}, "types": {}, "last_updated": ""}

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
task = data["tasks"].get(task_id, {})
is_new = task_id not in data["tasks"]

if is_new:
    task = {"id": task_id, "started_at": now}

if title:      task["title"] = title
if task_type:  task["type"] = task_type
if host:       task["host"] = host
if phase:      task["phase"] = phase
if status:     task["status"] = status
if progress:   task["progress_pct"] = int(progress)
if msg:        task["message"] = msg

task["last_update"] = now
data["tasks"][task_id] = task

# Rebuild types index
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

tmp = json_file + ".tmp"
with open(tmp, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
os.replace(tmp, json_file)
print("OK: task [{}] updated (direct)".format(task_id))
PYEOF

  ) 200>"$LOCK_FILE"
}
# ─── 核心函数 ──────────────────────────────────────────────────────────────────

# 初始化：注册所有 VPS 任务
init_tasks() {
  echo "=== Registering $HOST_COUNT VPS upgrade tasks ==="
  local host
  for host in "${VPS_ALL[@]}"; do
    local task_id="upgrade-${host}"
    local title="VPS Upgrade - ${host^^}"

    echo "  + Registering [$task_id] ($host)..."
    update_task "$task_id" \
      --title "$title" \
      --type "vps_upgrade" \
      --host "$host.20122102.xyz" \
      --phase "pending" \
      --status "pending" \
      --progress 0 \
      --msg "Task registered, awaiting first poll"
  done
  echo "=== All $HOST_COUNT tasks registered ==="
}

# 轮询单台主机
poll_host() {
  local host="$1"
  local task_id="upgrade-${host}"

  echo "  → [$host] Checking..."

  # 执行远程检查
  local raw_output
  raw_output="$(remote_check "$host" 2>&1)" || true

  # 解析输出
  declare -A data=()
  parse_remote_output "$raw_output" data

  # 判断状态和消息
  local status
  status="$(determine_status data)"
  local message
  message="$(build_message data)"

  # 计算进度
  local progress=0
  case "$status" in
    completed) progress=100 ;;
    running)   progress=50  ;;
    stuck)     progress=25  ;;
    pending)   progress=0   ;;
  esac

  # 确定阶段
  local phase="unknown"
  local lsb_release="${data[LSB_RELEASE]:-}"
  local dplock="${data[DPKG_LOCK]:-}"
  local upgrade="${data[DO_RELEASE_UPGRADE]:-}"

  if [[ -n "${data[SSH_ERROR]:-}" ]]; then
    phase="ssh-unreachable"
  elif [[ "$dplock" == LOCKED:* ]] && [[ "$upgrade" == RUNNING ]]; then
    phase="installing-packages"
  elif [[ "$upgrade" == RUNNING ]]; then
    phase="do-release-upgrade"
  elif [[ "$dplock" == LOCKED:* ]]; then
    phase="dpkg-lock-held"
  elif [[ "$lsb_release" == *"24.04"* ]]; then
    phase="completed"
  elif [[ "$lsb_release" == *"22.04"* ]] || [[ "$lsb_release" == *"20.04"* ]]; then
    phase="pending-upgrade"
  fi

  # 提取 OS/内核摘要用于标题增强
  local os_summary
  os_summary="$(echo "${data[LSB_RELEASE]:-}" | sed 's/Description:\s*//' | head -c 40)"
  local kernel="${data[UNAME]:-}"

  local title="VPS Upgrade - ${host^^}"
  [[ -n "$os_summary" ]] && title+=" ($os_summary)"
  [[ -n "$kernel" ]] && title+=" [${kernel}]"

  # 更新 task_status.json
  update_task "$task_id" \
    --title "$title" \
    --type "vps_upgrade" \
    --host "$host.20122102.xyz" \
    --phase "$phase" \
    --status "$status" \
    --progress "$progress" \
    --msg "$message"

  echo "    status=$status phase=$phase progress=$progress"
}

# 轮询所有主机（并发）
poll_all() {
  local specific_host="${1:-}"
  local host

  echo "=== VPS Upgrade Poll Cycle ==="
  echo "  Targets: ${specific_host:-ALL ${#VPS_ALL[@]} hosts}"
  echo ""

  if [[ -n "$specific_host" ]]; then
    poll_host "$specific_host"
  else
    # 并行轮询，每台独立进程
    local pids=()
    local host_i=0
    for host in "${VPS_ALL[@]}"; do
      ((host_i++))
      (poll_host "$host") &
      pids+=("$!")
      # 每 3 台错开 0.5 秒，避免 SSH thundering herd
      if (( host_i % 3 == 0 )); then
        sleep 0.3
      fi
    done

    # 等待全部完成
    local failed=0
    for pid in "${pids[@]}"; do
      wait "$pid" 2>/dev/null || ((failed++))
    done

    echo ""
    if (( failed > 0 )); then
      echo "  ⚠ $failed host(s) had errors"
    fi
  fi

  echo "=== Poll cycle complete ==="
}

# 守护模式
run_daemon() {
  local interval="${1:-300}"

  echo "=== VPS Adapter Daemon Mode ==="
  echo "  Interval: ${interval}s"
  echo "  Hosts: ${#VPS_ALL[@]}"
  echo "  PID: $$"
  echo ""

  # 首次自动 init（如果任务不存在）
  local json_file="$SCRIPT_DIR/task_status.json"
  if [[ ! -f "$json_file" ]] || ! grep -q "vps_upgrade" "$json_file" 2>/dev/null; then
    echo "  [daemon] No VPS tasks found, running init..."
    init_tasks
  fi

  while true; do
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "  Cycle started at $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════"
    poll_all
    echo "  Next poll in ${interval}s (Ctrl+C to stop)"
    sleep "$interval"
  done
}

# ─── 主入口 ─────────────────────────────────────────────────────────────────────
HOST_COUNT=${#VPS_ALL[@]}

show_help() {
  cat <<EOF
VPS Upgrade Status Polling Adapter

Usage:
  $0 --init                          Register all VPS tasks
  $0 --poll                          Poll all hosts once
  $0 --poll --host <name>            Poll single host
  $0 --daemon                        Run continuously
  $0 --daemon --interval <sec>       Custom poll interval (default: 300)
  $0 --help                          This help

Hosts ($HOST_COUNT total):
  AMT:  ${VPS_AMT[*]}
  JPK:  ${VPS_JPK[*]}
  KRK:  ${VPS_KRK[*]}
EOF
}

# 无参数
if [[ $# -eq 0 ]]; then
  show_help
  exit 0
fi

MODE=""
INTERVAL=300
SINGLE_HOST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --init)     MODE="init";     shift ;;
    --poll)     MODE="poll";     shift ;;
    --daemon)   MODE="daemon";   shift ;;
    --host)     SINGLE_HOST="$2"; shift 2 ;;
    --interval) INTERVAL="$2";   shift 2 ;;
    --help|-h)  show_help;      exit 0 ;;
    *) echo "Unknown option: $1"; show_help; exit 1 ;;
  esac
done

case "$MODE" in
  init)
    init_tasks
    ;;
  poll)
    poll_all "$SINGLE_HOST"
    ;;
  daemon)
    run_daemon "$INTERVAL"
    ;;
  *)
    echo "Error: no mode specified (--init / --poll / --daemon)"
    show_help
    exit 1
    ;;
esac
