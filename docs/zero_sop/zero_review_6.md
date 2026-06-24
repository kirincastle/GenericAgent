# Zero SOP AI Reply #6 — Review

> Review of `zero_ai_reply6.txt` — AI fills final 5 gaps: inpval.oracle, rollback, subagent probe, CI check, multi-env lock
> Reviewer: GenericAgent (GA) system maintainer
> Date: 2026-06-24

---

## Executive Summary

**Reply #6 is the last reply you need from this AI.**

All 5 gaps from Review #5 are filled. The inpval.oracle is production-quality (12 checks, grep commands, test templates). Rollback is sound (git stash with 3-attempt loop). CI gate is real (exit codes, GA YAML, configurable thresholds). Lock method is thorough (file/env/redis, NFS-safe).

The system is now architecturally complete. **The next step is not more design — it's implementation.**

---

## Gap-by-Gap Assessment

### 1. inpval.oracle ✅ COMPLETE

| Aspect | Rating | Notes |
|--------|--------|-------|
| Check coverage | 9/10 | 12 checks cover OWASP INPVAL top categories |
| Auto-confirm ability | 3/12 | Only INPVAL-06/08/09/11 can be grep-confirmed |
| Test templates | 4/10 | Only 4 of 12 checks have test code |
| Severity guide | ✅ | Critical → Medium mapped with rationale |
| Self-validation | ✅ | "If zero routes → skip" prevents false positives |

**Concern**: 9/12 checks are "Suspected (require trace or test)" — meaning 75% of the oracle still depends on AI reading code and reasoning about intent. This is the same limitation that zero had from the start. The oracle is honest about it (gives grep commands to narrow down candidates), but it doesn't solve the root problem — **the oracle itself cannot confirm most of its own checks automatically.**

### 2. Rollback ✅ COMPLETE

- Stash on first gate fail
- Up to 3 retry cycles
- On 3rd fail: drop all zero stashes, git checkout ., still run P6 for gap report
- Explicit logging at every step

**Concern**: `git checkout .` discards all uncommitted changes, including legitimate work that existed before the sweep. A better approach would be `git stash apply` on the FIRST stash (pre-sweep state), not stashing each attempt. If a Phase 3 fix introduced a regression, the rollback should restore the pre-sweep state, not pop the latest stash (which might be a partial fix that doesn't compile).

### 3. Subagent Capability Probe ✅ COMPLETE

- Boss.sh capability check with smoke test fallback
- VERIFIER_MODE: independent_agent vs self_verify_degraded
- Confidence penalty (-15%) on degraded mode

**Concern**: VERIFIER_MODE is exported but **never validated downstream**. The controller state machine (from Reply #5) doesn't check this variable before attempting subagent launch. If SUBAGENT_CAPABLE=false but the controller code still calls `bash $BOSS_SH spawn ...`, it will fail silently.

### 4. zero_ci_check.sh ✅ COMPLETE

| Check | What it measures | Effect |
|-------|-----------------|--------|
| Confidence score | >= min threshold (default 70%) | fail |
| Unresolved severity | Issues at >= fail-on level | fail |
| Baseline maintained | Tests passing >= baseline | fail |
| High-risk coverage | Warnings for uninsured features | warn (fail on strict) |
| Sweep completeness | Status == complete? | fail (suspended/aborted) |

**Concerns**:
- `find / -name zero_tracker.py` is fragile — searches entire filesystem. Should use known path.
- Requires zero_tracker.py to support `get-confidence`, `count-issues`, `get-meta`, `summary` — these are not documented API endpoints.
- No `--help` or usage validation for conflicting flags.

### 5. ZERO_LOCK_METHOD ✅ COMPLETE

| Method | Use Case | Safety |
|--------|----------|--------|
| file | Local dev | PID check, stale timeout (4h) |
| env | CI/NFS | ZERO_LOCK_HOLDER env var |
| redis | Distributed | SET NX EX atomic, TTL auto-expire |

**Concerns**:
- `redis-cli -u <URL>` — the `-u` URI format is Redis 6+; Redis 5 needs `-h -p -a`. No version detection.
- `kill -0` on file lock is NOT NFS-safe (PID reuse). The stale timeout (4h) mitigates but doesn't eliminate race conditions.

---

## Quantitative Evolution (Reply 1 → 6)

| Metric | R1 | R2 | R3 | R4 | R5 | R6 |
|--------|----|----|----|----|----|----|
| Lines | 580 | 322 | 2447 | 1335 | 1174 | 880 |
| Tools integrated | 0 | grep | grep+tests | grep+tests+git | +subagent | +redis+CI |
| State machine | ❌ | ❌ | ❌ | Linear | ✅ Error states | ✅ Lock/unlock |
| Self-verify | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ (independent) |
| CI integration | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ GitHub Actions |
| Cross-sweep learn | ❌ | ❌ | ❌ | ❌ | ✅ Lessons | ✅ Lessons+FP rate |
| Complete oracle coverage | 0% | Triaged | CWE25 only | 3 triage | 8 oracles | 12 oracles |

The most interesting trend: **lines decreased** while **completeness increased**. That's a sign of good architecture — each iteration removed bloat and added payload.

---

## What's Still Missing (after 6 rounds)

These are NOT architecture gaps — they are engineering decisions:

| Gap | Impact | Mitigation |
|-----|--------|------------|
| **No self-test** | Who tests zero itself? | Add `zero_smoke_test.sh` that runs zero against a known-bad toy project |
| **Oracle confidence gap** | 9/12 inpval checks need AI reasoning | Add dynamic test generation (AI writes test → runs it → records pass/fail) |
| **Rollback non-atomic** | git checkout . destroys non-zero work | Use `git stash push -u` (include untracked) and `git stash apply` not `checkout` |
| **No containerized mode** | Assumes dev env with full toolchain | Add Docker fallback in Phase 0 |
| **Tracker API not versioned** | CI script depends on undocumented endpoints | Add `--help` to zero_tracker.py or use JSONL directly |
| **Lessons schema not validated** | Corrupted lessons.jsonl causes silent failure | Add `lessons validate` subcommand to zero.sh |

---

## Summary for arena.ai

### What Reply #6 gets right

- **Stopped designing, started delivering** — all 5 gaps filled with actionable code
- **inpval.oracle is the best oracle in the set** — self-validation, discovery, confirmed/suspected split, test templates, severity guide
- **CI integration is real** — YAML example, exit codes, configurable thresholds
- **Lock method covers all deployment scenarios** — file (local), env (CI), redis (distributed)
- **Explicit gap closure table** — maps back to Review #5, no excuses

### The one remaining architectural issue

Zero still depends heavily on **AI reasoning about code** for 75% of its checks. The oracles narrow the scope but don't eliminate the dependency. The ultimate solution is what Reply #3 started: **AI writes tests, runs them, records results.** Every suspected check should generate a test file — if the test passes, the check is green. If the test fails, the bug is confirmed with evidence.

This is the next tier of quality: not "grep for patterns and think about intent" but "write a test, execute it, read the result."

### Verdict

**Build it. Zero is design-complete.** The next iteration should produce files in the repository, not more text in a conversation.

