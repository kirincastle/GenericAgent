---
type: sop
title: "Lessons System SOP"
tags: [memory, lessons, quality, lifecycle]
intent: "Complete lifecycle for lessons.jsonl — what becomes a lesson, how it's injected, how it's maintained"
---

# Lessons System SOP

## 1. What Becomes a Lesson

### Quality Gate — ALL must pass

1. **Multiple attempts**: I tried ≥2 different approaches before succeeding
2. **Root cause**: There's a why, not just a what (platform limitation, encoding, architecture)
3. **Generalizable**: Applies to >1 scenario, not one exact string match
4. **Not fixable by "be more careful"**: Typo, memory lapse, simple check → not a lesson

### Classification

| Type | Criteria | Storage |
|------|----------|---------|
| **Lesson** | Single behavior correction, 2+ attempts, root cause | `lessons.jsonl` (status:active) |
| **SOP** | Repeatable flow, multiple steps, stable process | `memory/*_sop.md` |
| **Skill** | Knowledge system, requires context + judgment | `memory/*/SKILL.md` |

### When NOT to write

- One-time fix, single attempt
- Pure typo / spelling (just fix it)
- Environment-specific that won't recur
- Can be prevented by existing rule/check

## 2. Lesson Format

```jsonl
{
  "id": 1,
  "title": "Short description",
  "tags": ["keyword1", "keyword2"],
  "trigger": "When user asks about X or I see Y",
  "rule": "Concrete behavior change — what to do instead",
  "created": "2026-06-23",
  "last_match": null,
  "match_count": 0,
  "prevent_count": 0,
  "fail_count": 0,
  "status": "active",
  "superseded_by": null
}
```

## 3. Injection Mechanism

Not tied to any mode. Permanent behavior rule in L1:

> **Lessons 自动匹配**：本会话内，每次用户给非闲聊请求，自动提取关键词，运行 `bash ../memory/lessons_search.sh <关键词>`，将匹配的 `rule` 注入工作记忆。不依赖任何特定模式。

## 4. Maintenance — /neat lifecycle

Run via `lessons_maintenance.py` as part of neat-freak:

| Operation | Description |
|-----------|-------------|
| **Quality check** | Flag trivial lessons (status → weak) |
| **Scoring** | effectiveness = prevent / (prevent + fail + 0.01) |
| **Demote** | effectiveness < 0.3 → weak. fail≥3 & prevent=0 → dormant |
| **Time-based demote** | `last_match` >30 days → weak; >60 days → dormant |
| **Merge** | Same tags + similar trigger → merge, keep stronger rule |
| **Conflict** | Same tags, opposite rules → flag for user review |
| **Archive** | Dormant >60 days → archived, or superseded_by set |

## 5. Writing Flow

When I encounter a new insight:
1. Does it pass the Quality Gate? (2+ attempts, root cause, generalizable)
2. Is it a Lesson, SOP, or Skill? (use Classification table)
3. If Lesson → append to `lessons.jsonl`
4. If SOP → write `memory/*_sop.md`
5. If Skill → write `memory/*/SKILL.md`

## 6. Auto-Suggestion (lessons_suggester.py)

When `lessons_search.sh` gets 0 hits, it calls `lessons_suggester.py match <keyword>` to detect fix trajectories from recent context.

### Flow
1. User reports fix/hard-won solution
2. Suggester checks FIX_SIGNALS (trial/error/wrong/finally patterns)
3. If trajectory detected + no existing matching lesson → suggestion output
4. Agent uses `--interactive` flag → gets ask_user-ready prompt
5. User confirms → `lessons_suggester.py save "title" "rule" tag1 tag2` writes to lessons.jsonl

### Commands
| Command | Purpose |
|---------|---------|
| `suggest [--context TEXT]` | Analyze context for fix trajectory |
| `suggest --interactive` | Output structured ask_user prompt |
| `match <keyword...>` | Check if keyword matches existing lessons |
| `save <title> <rule> [tags...]` | Save a new lesson (after user confirm) |

### Dedup Rules
- Same title → skip (likely duplicate)
- Title substring match → skip (too similar)

## 7. Usage Statistics (lessons_stats.py)

Every `lessons_search.sh` call logs to `lessons_search_log.jsonl`:
```json
{"timestamp": "...", "keywords": [...], "hits": N, "matched_ids": [...], "follow_up": null}
```

### Commands
| Command | Purpose |
|---------|---------|
| `report` | Summary: total searches, hit rate, top keywords, never-matched lessons |
| `export <format>` | Export stats (e.g. json) |
| `mark-followup <keyword>` | Mark that user followed up on a search result |
| `trim-log [keep=N]` | Trim search log to N entries (default 50) |

### Effectiveness Metrics
- `match_count`: times lesson matched a search
- `prevent_count`: times lesson prevented a mistake
- `fail_count`: times lesson failed to help
- Effectiveness = prevent / (prevent + fail + 0.01)
