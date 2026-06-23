---
type: sop
title: "Treehouse SOP — 隔离 worktree 池"
tags: ["skill", "worktree", "git", "isolation"]
intent: "需要在隔离环境并行运行多个 agent 任务，或让每个 agent 有独立干净的工作目录。"
---
# Treehouse SOP — 隔离 worktree 池

## 何时使用

需要在隔离环境并行运行多个 agent 任务，或让每个 agent 有独立干净的工作目录。

## 安装

```bash
curl -fsSL https://kunchenguid.github.io/treehouse/install.sh | sh
# 或 nix
nix run github:kunchenguid/treehouse
```

## 常用命令

```bash
# 初始化 worktree 池（在 git 仓库根目录执行）
treehouse init

# 获取一个 worktree，进入 subshell
treehouse get
# → 在子 shell 中工作，exit 后 worktree 归还到池

# 查看池状态
treehouse status

# 手动归还
treehouse return

# 清理废弃 worktree
treehouse prune

# 删除指定 worktree
treehouse destroy <path>
```

## 工作原理

- 维护一个 `.treehouse/` 池，内含多个 git worktree
- 每个 `get` 取出一个，`exit`（或 `return`）归还
- 池化复用：node_modules、.next、build 等缓存跨任务保留 → 避免重复安装
- 自动检测 worktree 冲突

## 与其他 SOP 联动

- 在 `gnhf_sop.md` 的迭代循环中：自动调 `treehouse get` 取隔离环境
- 在 `firstmate` 多 agent 场景：每个 crewmate 分配独立 worktree
