---
type: skill
name: neat-freak
description: >
  End-of-session knowledge cleanup. Syncs memory, runs lessons_maintenance, manages handoffs. Triggered by /neat command.
trigger: "user says /neat"
---

# Neat-Freak — Knowledge Base Cleanup

Cross-platform knowledge sync skill. Primary target: GenericAgent's memory system. Also applies to Claude Code / Codex / OpenCode projects that use memory/docs/agent config separation.

## When to Trigger

- User says `/neat` → **ALWAYS** run full workflow
- End-of-session → auto-trigger if `/boss` or `/autonomous` just completed
- After any task that modified files outside `temp/` → **MUST** run

## Core Workflow

### Step 1: Snapshot — Read Current State

Before ANY modification, capture the baseline:

```
# GenericAgent
wc -l memory/global_mem.txt memory/global_mem_insight.txt
ls memory/*.md | wc -l
ls memory/neat-freak/

# Cross-platform 
wc -l CLAUDE.md AGENTS.md 2>/dev/null
ls docs/ 2>/dev/null | wc -l
```

**Iron Rule**: If you don't know the current file sizes, you can't detect bloat. Read first, edit second.

### Step 2: Extract — Distill Session Knowledge

Review this session's tool calls — focus on **results**, not attempts:

| Extraction Target | What to Look For |
|------------------|------------------|
| **Facts** | Ports, paths, domain names, timezones, versions |
| **Lessons** | Bugs, workarounds, config fixes |
| **Process** | Multi-step workflows, SOP improvements |
| **Triggers** | Keywords that activate skills/modes |

**REFUSE** to extract trivia. A password reset email address is NOT a lesson. An API rate-limit retry strategy IS.

### Step 3: Write — Apply Changes (Priority Order)

```
1. Lessons first → memory/lessons*.json (minimal, deduplicated)
2. L2 facts → memory/global_mem.txt (patch only, NEVER overwrite)
3. L3 SOPs → memory/*_sop.md (patch only)
4. L1 index → memory/global_mem_insight.txt (last, after all changes confirmed)
```

**GA-ONLY rules**:
- `memory/lessons_maintenance.py` **MUST** run before any handoff step
- It merges similar lessons, downgrades weak/dormant ones, detects conflicts
- Output conflict/downgrade summary for user to confirm

**Edit Principles**:
- **Deletion > Addition**: CLAUDE.md/AGENTS.md net growth >30 lines = red flag. You're writing narrative, not rules.
- **Merge > Append**: New info updates an existing entry. `grep` for the keyword first.
- **Graduate > Rearrange**: Stable knowledge in memory → move to docs/ or CLAUDE.md, leave a 1-line pointer.
- **Precise > Verbose**: One memory entry = one fact. Not three.
- **Absolute Time**: `2026-04-29` always. NEVER "today", "recently".
- **Audience**: docs/ reader is "someone new to this project with 5 minutes". Write for them.

### Step 4: Handoff — Verify Existing + Create New

**GA-ONLY** — this step is skipped for non-GA projects.

```
1. For each handoff with status: in_progress:
   python3 memory/handoffs_maintenance.py verify <id>
   → If checklist complete: mark superseded
   → If incomplete: status stays in_progress

2. Create handoff for THIS session:
   Summarize body with: (a) core achievements (b) pending items (c) technical decisions
   
   python3 memory/handoffs/handoff_auto.py \
     --title "..." \
     --topic <project-name> \
     --tags "a,b" \
     --status active < body.txt
   
   → If same-topic active handoff exists: mark old as superseded, new record sets supersedes field
```

### Step 5: Report — Summary for User

Only list entries with actual changes:

```
## Neat Complete

### Memory Changes
- Updated: xxx (reason)
- Added: xxx
- Removed: xxx (reason)

### SOP Changes
- xxx_sop.md — section updated

### Handoffs
- ✓ verified: <topic> (completed)
- ✓ created: <topic> (current session)

### Skipped / Needs Input
- xxx (why)
```
Never report "nothing changed" sections.

## Special Cases

| Situation | Action |
|-----------|--------|
| **No new facts in session** | Still review memory for staleness/conflicts — review itself is valuable |
| **Memory conflict** | List in "Needs Input" — **ONLY** case requiring user decision |
| **Cross-project session** | Run Step 1 for EACH project. Especially upstream-downstream docs (integration guides, API contracts) |
| **Stale references found** | Fix them. Past omissions are your problem too |
| **Project has no docs yet** | Code running? → Create. Still vibe stage → Skip, note in report |

## Completion Checklist

Before declaring `/neat` done:

- [ ] Step 1 run: all target files have known sizes
- [ ] No-op sections deleted from ALL modified files (not just added to)
- [ ] Each modified file's net change: if CLAUDE.md/AGENTS.md >+30 lines, prune back
- [ ] L1 index ≤30 lines (`wc -l` verify)
- [ ] No relative time remnants (`grep -E "today|yesterday|recently|just.now"` → 0)
- [ ] GA: `lessons_maintenance.py` ran, output reviewed
- [ ] GA: handoffs verified and current-session handoff created
- [ ] Language check: `grep -cP '[\x{4e00}-\x{9fff}]'` on all modified files → **0**
- [ ] All pointers in L1 point to existing files
- [ ] No Chinese in any SOP/skill file (exception: user explicitly requested Chinese docs)

## References

- `memory/neat-freak/SKILL.md` — this file
- `memory/memory_management_sop.md` — GA memory layer specification
- `memory/handoffs/handoff_auto.py` — auto-create/purge handoffs
- `memory/lessons_maintenance.py` — lesson dedup/downgrade tool
- `references/agent-paths.md` — platform config paths (if exists)
- `references/sync-matrix.md` — change-type → file mapping (if exists)
