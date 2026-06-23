---
type: sop
title: "gnhf SOP — 自主迭代循环"
tags: [skill, iteration, loop]
intent: "需要 agent 无人值守地持续迭代一个目标，每次迭代 commit，失败自动回滚。"
---
# gnhf SOP — 自主迭代循环

## 何时使用

需要 agent 无人值守地持续迭代一个目标，每次迭代 commit，失败自动回滚。

比 `/goal` 模式更成熟：有 commit checkpoint、失败回滚、退出总结。

## 安装

```bash
# 零安装，直接 npx
npx gnhf "你的目标"
```

## 用法

```bash
# 基本用法
npx gnhf "优化数据库查询性能"

# 限制迭代次数
npx gnhf "重构用户模块" --max-iterations 10

# 限制 token 消耗
npx gnhf "写单元测试" --max-tokens 5000000

# 推送策略
npx gnhf "加新功能" --push-policy on-success
```

## 工作原理

1. 创建 disposable git worktree
2. 循环：agent 执行 → 结构化输出（success/summary/changes/learnings）
3. 成功 → git commit + 更新 run notes
4. 失败 → `git reset --hard` 回滚
5. 达到限制/agent 请求停止 → exit summary
6. 输出：分支名、耗时、迭代数、token消耗、diff统计

## 关键参数

| 参数 | 作用 |
|------|------|
| `--max-iterations` | 最大迭代次数 |
| `--max-tokens` | 最大 token 消耗 |
| `--push-policy` | `never` / `on-success` / `always` |
| `--meteor-frequency` | 每 N 次迭代强制用户确认 |

## 本系统整合

- 替代 `/goal` 模式：当目标明确且需长时间自主迭代时
- 与 `treehouse_sop` 配合：每次 get 一个 worktree 跑 gnhf
- gnhf 本身不依赖任何特定 agent，直接通过 CLI 调用
