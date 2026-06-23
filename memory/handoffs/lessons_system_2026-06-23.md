---
type: handoff
title: "Lessons system — complete lifecycle (2026-06-23)"
date: "2026-06-23"
status: "active"
tags: [lesson, maintenance, neat, lifecycle]
---

# Lessons System — Complete Lifecycle

## What was built

### 1. Lessons JSONL (`memory/lessons.jsonl`)
6 lessons, each with lifecycle fields:
- `status`: active | weak | dormant | archived
- `prevent_count`, `fail_count`: effectiveness tracking
- `last_match`, `match_count`: usage tracking
- `superseded_by`: conflict resolution

### 2. L1 permanent behavior rule (`global_mem_insight.txt`)
```text
Lessons 自动匹配：本会话内，每次用户给非闲聊请求，
自动提取关键词，运行 lessons_search.sh <关键词>，
将匹配的 rule 注入工作记忆。不依赖任何特定模式。
```

### 3. Lessons Maintenance (`memory/lessons_maintenance.py`)
Run as part of `/neat`:
- effectiveness scoring → demote weak/dormant
- merge similar (same tags + same trigger)
- conflict detection (same tags, opposite rules)
- **quality check**: auto-flag trivial lessons (typos, "be more careful")

### 4. Lessons SOP (`memory/lessons_sop.md`)
Quality criteria for when to write a lesson:
- Multiple attempts before success → Lesson
- One-shot success → not lesson-worthy
- Stable repeatable flow → SOP / Skill
- Classification table: Lesson vs SOP vs Skill

### 5. Integrated into `/neat` (`memory/neat-freak/SKILL.md`)
GA extra step: runs `lessons_maintenance.py` during neat

### 6. Lessons search injector (`memory/lessons_search.sh`)
Keyword → grep matching rules

## New files

| File | Purpose |
|------|---------|
| `memory/lessons.jsonl` | Lesson database (6 active) |
| `memory/lessons_maintenance.py` | Lifecycle management |
| `memory/lessons_sop.md` | SOP: what becomes a lesson |
| `memory/sops_index.jsonl` | SOP metadata index (38 records) |
| `memory/handoffs/handoffs.jsonl` | Handoff registry (18 records) |
| `memory/mode_rules.jsonl` | Mode decision rules (7 records) |

## Architecture

```
User task → L1 behavior rule → lessons_search.sh <keywords>
                                ↓
                           Matching lessons' rule injected to working memory

User runs /neat → lessons_maintenance.py
                   ├─ quality check (flag trivial)
                   ├─ effectiveness scoring
                   ├─ merge similars
                   ├─ conflict detection
                   └─ demote/archive
```

## Handoff to /neat

When user runs `/neat`, it should:
1. Run `memory/lessons_maintenance.py` (quality check, scoring, merge, conflict)
2. Rebuild `memory/sops_index.jsonl` if needed
3. Verify lessons system integrity

## Sessions after neat

New session → L1 → lessons_search runs on every non-trivial task
