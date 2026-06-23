---
type: sop
title: "no-mistakes SOP — Git push 质量门禁"
tags: [git, quality, discipline]
intent: "需要保证推送到关键分支的代码经过 AI review → 测试 → lint → CI 全流程验证。"
---
# no-mistakes SOP — Git push 质量门禁

## 何时使用

需要保证推送到关键分支的代码经过 AI review → 测试 → lint → CI 全流程验证。

## 安装

```bash
# 通过 Go 安装
go install github.com/kunchenguid/no-mistakes@latest

# 或 brew
brew install no-mistakes
```

## 初始化

```bash
cd /path/to/repo
no-mistakes init
no-mistakes doctor    # 检查环境
```

## 用法

```bash
# 推送到 no-mistakes 代理（代替直接 push origin）
git push no-mistakes

# no-mistakes 会自动：
# 1. 创建 disposable worktree
# 2. 提取代码变更意图（读取 agent session 日志）
# 3. 跑 pipeline: review → test → docs → lint → CI
# 4. auto-fix 安全修改，用户确认修改意图
# 5. 全部通过 → push + 开 PR
```

## 核心概念

- **Intent extraction**: 自动读取 Claude Code/Codex/OpenCode 等 session 日志，理解用户原始意图
- **Three-tier approval**: auto-fix（机械修改自动应用）→ approve（请求确认）→ reject（驳回）
- **CI passthrough**: 等待 GitHub Actions 等 CI 通过后才最终合入

## 本系统整合

- 写 PR 前的标准步骤：`git push no-mistakes`
- 与 code review SOP 配合，把 intent extraction 概念融入审查流程
