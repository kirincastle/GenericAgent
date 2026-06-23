---
type: sop
title: "Code Review SOP — 带意图回溯的审查流程"
tags: ["code", "review", "quality", "ga-mode"]
intent: "Code Review Quality Ga-Mode SOP for GA system"
---
# Code Review SOP — 带意图回溯的审查流程

## 流程

### Step 1: 提取原始意图（Intent Extraction）

在审查代码之前，先回溯 agent 的 session 日志，理解"用户本来想要什么"。

```bash
# 找最近的 session 日志
ls -t temp/model_responses/ | head -5

# 从日志中提取：
# - 用户的原始需求描述
# - 关键约束和边界条件
# - 用户明确说过"不要"什么
```

如果 session 日志不可用，直接从 git commit message 和 PR description 推断意图。

### Step 2: 意图 vs 实现 对比

问：
- 代码满足了用户的**原始意图**吗？
- 有没有实现了一些用户没要求的东西（scope creep）？
- 有没有遗漏了用户明确要求的点？
- 实现方式跟用户举例/期望的一致吗？

### Step 3: 三层判定

参考 no-mistakes 的三级审批模型：

| 级别 | 判定 | 处理 |
|------|------|------|
| **Auto-fix** | 格式化/import/命名不一致/死代码/拼写/纯机械问题 | 直接修复，无需确认 |
| **Approve** | 逻辑正确但可改进（性能/风格/可读性） | 标注建议，等待确认 |
| **Reject** | 逻辑错误/违反需求/安全风险/架构退化 | 打回，附理由 |

### Step 4: 审查角度

1. **正确性**：逻辑有无边界情况没处理？有无并发问题？
2. **可维护性**：结构清晰吗？依赖方向对吗？变化半径有多大？
3. **一致性**：跟项目已有代码风格一致吗？用了同样的模式吗？
4. **安全性**：有注入/SQL/XSS/敏感信息泄露风险吗？
5. **测试覆盖**：有测试吗？测了对的点和边界吗？

### Step 5: 输出审查摘要

```markdown
## 审查: <PR/commit hash>
- 意图 vs 实现: ✅ 匹配 / ⚠️ 有偏差
- Auto-fix: N 项（已修复）
- 待确认: N 项
- 驳回: N 项
- 总体: 通过 / 有条件通过 / 驳回
```

## 与本系统集成

- 配合 `no_mistakes_sop.md`：关键分支用 `git push no-mistakes` 自动门禁
- 配合 `plan_sop.md`：在 PR 创建前增加 review 步骤
