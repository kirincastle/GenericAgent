---
type: sop
title: "Pre-task SOP Scanner — 自动匹配相关SOP"
tags: [workflow, automation, okf, search]
intent: "用户给任务后，自动提取关键词搜 memory/ SOP，提前加载最相关的 1-2 个到工作记忆"
---

# Pre-task SOP Scanner

## 行为规则（每次用户给新任务时自动执行）

### 1. 触发条件
用户提出了一个**非 trivial 的任务**（排除：yes/no 回答、简单确认、闲聊）。

### 2. 关键词提取
从任务描述中提取 1-3 个核心名词/动词：
- "部署 cf worker" → `deploy worker`
- "改 git 配置" → `git config`
- "查 oc2api 节点" → `oc2api node`

### 2.5. Lessons 匹配（行为矫正）
在搜 SOP 的同时，用相同关键词匹配 `memory/lessons.jsonl`：
```bash
bash ../memory/lessons_search.sh <关键词>
```
- 如果命中 lessons → 把 `rule` 字段注入**当前工作记忆**作为行为约束
- 同一 lesson 在本会话已触发过 → 跳过（防重复注入）
- 注入格式: `[LESSON] <rule>`

## 并行搜索

### 3. SOP 搜索
```bash
bash ../memory/sop_search.sh <关键词>
# 或
python3 ../temp/.agents/skills/okf-frontmatter/scripts/find_docs.py \
  --repo /home/moclaw/projects/external/genericagent find <关键词>
```

### 4. 读取
如果搜索结果命中 ≥1 个 SOP：
- 读命中 SOP 的 **前 5 行**（frontmatter + intent）
- 如果 intent 明显匹配任务，把文件名加入**当前工作记忆 (key_info)**
- 如果多个 SOP 匹配，选 intent 最相关的 1-2 个

### 5. 执行任务
带着 SOP 的知识执行任务。如果过程中发现需要更深读某 SOP，再完整读。

### 6. 不匹配时
搜不到相关 SOP → 直接执行，事后考虑是否要创建新 SOP。

## 豁免项
以下不需要自动搜索：
- 断词/极简代码（is_even, hello world）
- 纯文件读写（cat, mv, rename）
- 聊天/闲聊
- 对 GA 系统的配置命令（/goal, /hive 等）

## 验证
每次用户给明显可匹配的任务后，检查我是否自动搜了相关 SOP。如果没搜，说明忘记执行此 SOP 了。
