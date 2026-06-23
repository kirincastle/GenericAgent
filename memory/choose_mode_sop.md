---
type: sop
title: "Choose Mode SOP — /choose-mode 工作流"
tags: [ga-mode, choose, workflow]
intent: "分析任务特征 → 推荐执行模式(Gaal/Hive/Conductor/直接) → 用户确认 → 自动启动"
---

# Choose Mode SOP

## 触发
用户说 `/choose-mode <任务描述>` 或语境表明需要选择执行模式。

## 流程

### Step 1 — 分析（我自动做）
从对话上下文提取 4 个信号：
- **子任务数**: 1 个 / 多个独立 / 多个有依赖
- **目标清晰度**: 明确结果 / 开放探索
- **时间预算**: 有 / 无
- **任务类型**: 改代码 / 改行为 / 信息收集

### Step 2 — 决策树（我自动判断）
```
1. 必须改我自身行为逻辑？        → 前台直接做 ⚡
2. 简单清晰、无需我持续干预？     → Subagent 🧑‍💻 后台
3. 开放探索 / 长期优化？          → Goal 🎯 后台
4. 大量独立同构子任务？           → Hive 🐝 后台
5. 多步骤有严格依赖顺序？         → Conductor 🏭 后台
```

### Step 3 — 启动
| 推荐模式 | 启动命令 | 执行位置 |
|---------|---------|---------|
| 直接做 | 当前对话直接执行 | 前台 |
| Goal   | `agentmain --reflect reflect/goal_mode.py` | 后台 (nohup) |
| Hive   | 按 goal_hive_sop 启动 BBS + workers | 后台 |
| Conductor | `python frontends/conductor.py <plan>` | 后台 |

### Step 4 — 进度追踪
- Goal: `cat temp/goal_state.json`
- Hive: `curl http://127.0.0.1:<PORT>/board`
- Conductor: 读 temp/conductor*/ 日志

## 快速参考
```bash
# 分析任务
bash memory/choose_mode.sh "<任务描述>"

# 快速启动 Goal (sp)
goal_launch() {
  local obj="$1" budget="$2"
  echo '{"objective":"'$obj'","budget_seconds":'$budget',...}' > temp/goal_state.json
  GOAL_STATE=temp/goal_state.json nohup python agentmain.py --reflect reflect/goal_mode.py &
}
```
