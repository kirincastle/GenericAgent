#!/bin/bash
# choose_mode.sh — 模式分析器（非交互式）
# 输出 JSON，供 GenericAgent 程序化调用
# 
# Usage:
#   ./choose_mode.sh "给35个SOP补tags"
#   ./choose_mode.sh "建git hook" --budget 15min
#   ./choose_mode.sh --parse  # 从stdin读JSON任务描述
#
# 输出: {"mode":"hive","reason":"...","subtasks":[...],...}

set -euo pipefail

# Parse task from args
if [ $# -ge 1 ] && [ "$1" != "--parse" ]; then
    TASK="$*"
elif [ "$1" = "--parse" ]; then
    TASK="$(cat)"
else
    echo '{"error":"no task provided","usage":"choose_mode.sh <task description>"}'
    exit 1
fi

# Extract key signals from task name
TASK_LOWER="$(echo "$TASK" | tr '[:upper:]' '[:lower:]')"

# Count subtask indicators
SUBTASK_COUNT=0
for word in $(echo "$TASK_LOWER" | grep -oP '\d+'); do
    if [ "$word" -gt 1 ] 2>/dev/null; then
        SUBTASK_COUNT=$word
    fi
done

# Heuristic mode detection
MODE="direct"
REASON="单一清晰任务"
LAUNCH_CMD=""
EXECUTION="foreground"

# Subagent signals: clear single task that doesn't need me
if echo "$TASK_LOWER" | grep -qE '(创建|写入|生成|补全|添加|删除|修改|检查|验证|脚本)'; then
    MODE="subagent"
    REASON="明确的后台脚本任务"
    LAUNCH_CMD="subagent_launch"
    EXECUTION="background"
fi

# Hive signals: multiple independent items
if echo "$TASK_LOWER" | grep -qE '(多个|多个独立|全部|每个|逐个|批量|所有.*都|补全.*35|遍历)'; then
    MODE="hive"
    REASON="多个独立子任务可并行"
    LAUNCH_CMD="hive_launch"
    EXECUTION="background"
fi

# Conductor signals: strict order, pipeline, multi-step
if echo "$TASK_LOWER" | grep -qE '(依次|先.*再.*然后|流水线|依赖|步骤|阶段[0-9])'; then
    MODE="conductor"
    REASON="多步骤有依赖关系"
    LAUNCH_CMD="conductor_launch"
    EXECUTION="background"
fi

# Goal signals: unclear result, exploration, time budget
if echo "$TASK_LOWER" | grep -qE '(探索|优化|改进|持续|自驱|找问题|挖掘)'; then
    MODE="goal"
    REASON="开放式探索需要自驱迭代"
    LAUNCH_CMD="goal_launch"
    EXECUTION="background"
fi

echo "{\"mode\":\"$MODE\",\"reason\":\"$REASON\",\"task\":\"$TASK\",\"execution\":\"$EXECUTION\",\"launch\":\"$LAUNCH_CMD\"}"
