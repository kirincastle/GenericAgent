---
type: reference
title: "Handoff Document Template"
tags: [handoffs, template, convention]
intent: "Template and guide for writing standardized session handoff documents."
---

# Handoff Document Template

## 何时创建 Handoff
- `/neat` 命令结束时自动触发
- 长时间任务中途暂停时
- 跨 session 工作交接时

## 文件命名
`kebab-case-summary-YYYY-MM-DD.md`

放在 `memory/handoffs/` 目录下。

## 标准结构

```markdown
---
type: handoff
title: "项目名 — 工作摘要 (YYYY-MM-DD)"
date: "YYYY-MM-DD"
status: "active"  # active | in_progress | superseded
tags: [tag1, tag2, tag3]
# Optional:
supersedes: ["older-handoff.md"]
session_topic: "topic-name"  # used for grouping related handoffs
superseded_by: ["newer-handoff.md"]
project_root: "/path/to/project"  # 项目根路径，用于 checklist 自动验证
checklist:
  - id: "unique-item-id"
    desc: "可读描述"
    verify: "file_exists | code_search | git_log | manual"
    target: "相对 project_root 的文件路径"
    search_for: "grep 搜索词（仅 code_search）"
    status: "pending | verified"
---

# {Title} ({YYYY-MM-DD})

## 完成的工作

### {Major Work Area 1}
- {完成项 1}
- {完成项 2}
- {决策点或关键变更}

### {Major Work Area 2}
- ...

## 未处理 / 待办

### 高优先级
- {必须尽快完成的事项}

### 低优先级
- {非阻塞事项}

## 技术决策
- {关键决策 1}: {理由}
- {关键决策 2}: {理由}

## 已修改文件
| 文件 | 变更类型 |
|------|---------|
| `path/to/file.ext` | 新增/修改/删除 |

## 部署状态
{如果适用: 版本号, 短哈希, 部署节点, 健康状态}
```

## 状态字段说明

| 状态 | 含义 | 使用时机 |
|------|------|---------|
| `active` | 待认领，尚未开始 | 刚创建 |
| `in_progress` | 正在推进 | 用户通过 `/continue` 选中后 |
| `superseded` | 已完成或被替代 | 用户确认完成，或新 handoff 替代旧 handoff |

## Checklist 字段（结构化验证）

每个 handoff 可含 `checklist` 数组，用于 /neat 时自动判断完成度。

### 条目结构

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 唯一标识，如 `phase-a` |
| `desc` | ✅ | 人读的描述 |
| `verify` | ✅ | 验证方式（见下表） |
| `target` | ✅ | 相对 `project_root` 的路径 |
| `search_for` | 仅 code_search | grep 搜索词 |
| `status` | ✅ | `pending` / `verified`（自动更新） |

### 验证方式

| verify 类型 | 判定逻辑 | 适用场景 |
|-------------|---------|----------|
| `file_exists` | 目标文件存在 | "解析器文件已创建" |
| `code_search` | 目标文件含 `search_for` 符号 | "DeviceCommands 字段已实现" |
| `dir_search` | 目录下存在匹配文件 | "所有生成的报告文件" |
| `git_log` | 自创建日期后有 commits 触及目标 | "某目录有后续改动" |
| `manual` | 需人工判断 | "设计文档已审查" / "部署验证" |

### 示例

```yaml
checklist:
  - id: data-model
    desc: "后端数据模型 + Input 解析器"
    verify: "code_search"
    target: "tools/customcli.go"
    search_for: "DeviceCommands"
    status: "pending"
  - id: design-review
    desc: "设计文档 AI cross-check"
    verify: "manual"
    status: "pending"
```

### /neat 流程

1. 扫描所有 `in_progress` handoff
2. 对每条 checklist（`verify != manual`）自动验证
3. 输出报告：`✅ 通过 / ❌ 未找到 / ⏳ 人工待审`
4. 全部 auto-check 通过 → 建议 supersede
5. 有失败项 → 提示用户哪些未完成

## 文件命名规范
- 格式：`<topic>-<date>.md`
- 主题用英文小写，单词间用 `-` 分隔
- 日期用 `YYYY-MM-DD` 格式
- 示例：`oc2api-fix-429-2026-06-22.md`, `migration-dashboard-phase2-2026-06-23.md`
- 注意：统一使用连字符 `-`，避免下划线 `_`
- 若命名与已有文件冲突，在日期后加 `-v2`, `-v3` 等

## 内容规范
- 标题用 `##` (H2) 分段，`###` (H3) 分子段
- 中英文均可，保持同一文件内语言一致
- **技术决策** 单独成节，便于回顾
- +1. 每次创建 handoff 后，用 `file_patch` 更新 `memory/handoffs/index.md`
- +2. 若 handoff 替代了旧 handoff，在旧文件中添加 `superseded_by` 字段<br><br>

## 历史 Handoff 兼容指南
现有 handoff 使用非标准节标题，以下映射表帮助你导航：

| 标准节标题 | 历史等价标题 |
|-----------|------------|
| ## 完成的工作 / ## Completed | ## 本次完成, ## 解决的问题, ### 已完成的步骤, ## 设计决策, 各 `###` 子节 |
| ## 未处理/待办 / ## Pending | ## 未处理, ## 待办, ### 剩余的步骤, ## 高优先级, ## 低优先级 |
| ## 技术决策 / ## Decisions | ## 决策, ## 设计决策, ## 关键技术决策 |
| ## 已修改文件 / ## Files Changed | ## 已修改文件, ## 文件, 内联 `**文件**:` 引用 |
| ## 部署状态 / ## Deployment | ## 部署, ## 状态, status: 字段 |
| ## 本次完成 | 散落于 `###` 子节 |
