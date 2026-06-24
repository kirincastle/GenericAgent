# Zero Mode — Final Architecture Review

> Complete review of arena.ai conversation (7 rounds): from "SOP not detailed enough" to a modular, evidence-driven quality assurance system.
> 
> **Date:** 2026-06-24  
> **Reviewer:** GenericAgent system maintainer  
> **Audience:** arena.ai review

---

## Executive Summary

The conversation started with a real problem: **Zero Mode couldn't find bugs in projects.** The initial hypothesis was "the SOP needs more detail." After 7 rounds of iteration, the true root cause emerged:

> **Zero asked AI agents to "read code and form opinions" without objective tooling, automated tests, or independent verification.**

The solution is not a longer SOP — it's a fundamentally different architecture: a modular, evidence-driven pipeline where AI writes and runs tests, tools produce objective evidence, and independent verification closes the self-supervision loop.

---

## The Evolution (R1 → R7)

| Round | Proposal | Key Flaw | Verdict |
|-------|----------|----------|---------|
| R1 | "SOP not detailed enough" → 580-line linear SOP | More detail doesn't fix AI's code-reading ceiling | ❌ |
| R2 | "Add OWASP/CWE checklists + grep commands" | Grep finds ~30% of real bugs; zero business logic coverage | ⚠️ |
| R3 | "Write tests instead of reading code" (2447 lines) | Correct direction, but SOP itself consumes 35%+ of token budget | ✅ direction |
| R4 | "Modular architecture: controller + phase SOPs + oracles" | 7 structural gaps (no verifier, no state machine, no rollback) | ✅✅ |
| R5 | "Fill the 7 gaps with state machine, verifier protocol, lesson lifecycle" | 5 implementation bugs (non-atomic rollback, Redis compat, etc.) | ✅✅✅ |
| R6 | "Fix 5 implementation bugs + inpval.oracle + CI script + lock" | 6 edge cases (rollback destroys uncommitted work, no self-test) | ✅✅✅✅ |
| R7 | "Fix all 6 edge cases: atomic rollback, VERIFIER_MODE enforcement, documented API, Redis fallback, smoke test, suspected→test conversion" | **None.** Ready to build. | ✅✅✅✅✅ |

---

## The Final Architecture

### Core Principle
> **No opinion without evidence. No fix without a test. No claim without independent verification.**

### System Components

```
┌──────────────────────────────────────────────────────────────┐
│                   Controller (≤200 lines)                     │
│  State machine: P0→P1→P2→P3→P4→P5→P6→done                    │
│  On-demand phase loading, error handling, lock, lessons       │
└──────┬───────────────────────────────────────────────┬───────┘
       │                                               │
       ▼                                               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Phase SOPs   │  │   Oracles    │  │   Verifier   │  │     CI       │
│ (6× ≤150 ln) │  │ (7× ≤100 ln) │  │ Independent  │  │  0_ci_check  │
│ on-demand    │  │ authn/authz  │  │ agent or     │  │  5 gates     │
│ loaded       │  │ inpval/CRUD  │  │ self-verify  │  │  exit codes  │
│ P0-P6        │  │ concurrency  │  │ degraded     │  │  GitHub Act. │
│              │  │ temporal     │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

### Phase Flow

| Phase | Name | Key Output | Load Policy |
|-------|------|-----------|-------------|
| P0 | Bootstrap | Lock, tool discovery, env check, pre-sweep stash | First load only |
| P1 | Triage | Risk-weighted feature inventory + oracle dispatch | On-demand |
| P2 | Batch Test | per-batch test results, evidence artifacts | On-demand |
| P3 | Fix Loop | Fixes with impact analysis, gate retry (max 3) | On-demand |
| P4 | Business Logic | State machine, financial, temporal audit | On-demand |
| P5 | Regression Gate | Baseline comparison, rollback on failure | On-demand |
| P6 | Confidence | Independent verification + risk-weighted score | End only |

### Key Mechanisms

1. **Evidence, not opinion** — Every claim backed by tool output, test result, or trace
2. **Suspected→Test conversion** — No suspected issue exits P3 without a generated test
3. **Independent Verifier** — Separate agent instance disputes self-verified claims
4. **Atomic Rollback** — Pre-sweep stash + max 3 retries + git reset
5. **Cross-sweep Learning** — `zero_lessons.jsonl` with false-positive rate per oracle
6. **Lock** — File/env/Redis with NFS-safe stale detection (4h TTL)
7. **CI Integration** — 5-gate check script with configurable thresholds

---

## What's Been Solved vs What Remains

### Solved (from original problem)
- ✅ **No objective evidence** → Tools + tests + traces
- ✅ **Self-verification loop** → Independent agent disputes
- ✅ **Business logic blindness** → State machine, financial, temporal oracles
- ✅ **Token budget exhaustion** → Modular loading, ≤150 lines per phase
- ✅ **No rollback from bad fixes** → Pre-sweep stash + 3-attempt gate
- ✅ **No cross-sweep memory** → Lessons persistence with FP rate tracking
- ✅ **Environment fragility** → Degraded modes, triple tool fallback
- ✅ **No CI integration** → zero_ci_check.sh with 5 gates

### Remaining (acceptable gaps)
- ⬜ **Framework specificity** — Existing oracles target JS/TS; Python/Rust need adaptation
- ⬜ **Self-test maturity** — Smoke test covers 6 bugs, should grow over time
- ⬜ **Oracle coverage** — 7 oracles are complete; financial, state-machine oracles are templates
- ⬜ **Codegraph dependency** — Architecture assumes codegraph exists; non-GA projects use grep fallback (less accurate)
- ⬜ **SIGKILL lock leak** — Stale detection (4h TTL) vs trap-based cleanup; known OS limitation

---

## Verdict

**Build it. Stop iterating on spec, start iterating on execution.**

The architecture has converged after 7 rounds. The remaining gaps are edge cases and framework adaptation — they should be resolved in implementation, not in another spec iteration.

### Recommended Implementation Order

1. **Tracker API** — Add 6 subcommands to zero_tracker.py (get-confidence, count-issues, get-meta, list-issues, export-verified, summary)
2. **zero_sop.md** — Rewrite to reflect modular architecture, state machine, oracle pattern
3. **zero.sh** — Add lock mechanism and new tracker subcommand dispatch
4. **zero_ci_check.sh** — CI gate script (standalone, no dependency on boss.sh)
5. **zero_smoke_test.sh** — Self-test with known-bad fixture project
6. **Phase SOPs + Oracles** — Generate from templates in this conversation
7. **Verifier Protocol** — Boss.sh integration for independent verification (requires subagent infra)

---

*This review covers 7 AI replies, ~9,000 lines of generated content, across 6 rounds of structural iteration.*
