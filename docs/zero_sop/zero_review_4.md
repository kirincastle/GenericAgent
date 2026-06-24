# Zero SOP AI Reply #4 — Review

> Review of `zero_ai_reply4.txt` — AI structurally rewrites Zero architecture addressing all Review #3 criticisms
> Reviewer: GenericAgent (GA) system maintainer
> Date: 2026-06-24
> Read: Full 1335 lines

---

## Verdict: Accept with modifications

This is the first response that **qualifies as a production-ready architecture**.

Reply #1 was "write a longer SOP". Reply #2 was "add industry checklists". Reply #3 was "shift from reading code to writing tests." Reply #4 is the first one that **actually addressed the structural problems identified in review**, not just the surface symptoms.

---

## Executive Summary

Reply #4 transforms the Zero Mode from a monolithic SOP into a **modular, phase-gated QA system**:

| Before (Reply #3) | After (Reply #4) |
|----|----|
| 2447-line monolithic SOP | 200-line controller + ≤150 per phase + ≤100 per oracle |
| Self-verification | Independent agent verification (Phase 6) |
| No cross-sweep learning | `zero_lessons.jsonl` with FP rate tracking |
| Single mindset per sweep | Phase 3 (pentest) / Phase 4 (domain) structurally separated |
| `codegraph` as hard dependency | 3-layer fallback: codegraph → grep → file-path |
| "blocked" is a failure | `blocked_environment` is a valid outcome with degraded mode |
| Oracle files are hypothetical | CWE25 oracle is complete and executable |

This is not just a rewrite. It's a **paradigm shift from prompting to tooling**.

---

## What This Reply Gets Right (in detail)

### 1. Modular architecture with strict line limits

The single best design decision in this response:

- **Controller** (`zero_active/main.sop`): ≤200 lines, loads/unloads phases
- **Phase SOPs**: ≤150 lines each, loaded on-demand
- **Oracle files**: ≤100 lines, loaded per-batch

This solves the token budget problem from Review #3. The agent never holds more than ~300 lines in context at any point (controller + one phase + one oracle). Instead of 35%+ of context burned on SOP, it's ~5%.

The "unload before loading next" instruction is critical — whether the agent follows it depends on implementation discipline, but the design makes it possible.

### 2. Evidence-driven architecture (fully realized)

Every piece of data in this system has a **provenance**:

- Triage hits → grep output file (`zero_artifacts/triage/*.txt`)
- Feature discovery → `zero_tracker.py add` with JSON record
- Test results → saved stdout with `EXIT:$?`
- Bug confirmation → JSON with `evidence_type`, `evidence_artifact`, `reproduce_cmd`
- Fix verification → re-run of original failing oracle

There is no "the agent felt like it found a bug." Everything is traceable to a file artifact.

### 3. Cross-sweep learning (finally)

`zero_lessons.jsonl` with structured fields:

```jsonl
{"category":"general","oracle":"business_logic/financial",
 "lesson":"Float arithmetic check is high signal — any parseFloat is a real bug risk",
 "false_positive_rate":"low","signal_quality":"high",
 "action":"confirm_immediately_on_hit"}
```

Key design decisions:
- Lessons are **oracle-scoped** (not project-scoped), enabling reuse across projects
- `false_positive_rate` and `signal_quality` let future sweeps **weight oracles differently**
- `action` field tells the agent *what to do* with this lesson

The sync mechanism (`--sync-lessons`) connects local findings to a global lesson database. This is essential for a system that learns over time.

### 4. Tool-agnostic triage with multi-layer fallback

The three-layer discovery:

```
1. codegraph_callers → 2. grep -rn → 3. file-path heuristics
```

Each layer has different strengths:
- `codegraph`: precise call chain, but custom tool
- `grep`: universal, but no semantic understanding
- `file-path`: naming patterns, fragile but independent

Fallback is explicit and tested in the oracle file (see CWE-22 oracle which uses `grep -l` + `grep` chaining when codegraph is unavailable).

### 5. Oracle self-validation (underappreciated)

Phase 4.1 (Oracle Self-Validation) is a small but important addition:

Before running any state machine oracle:
```
- "I found N states: [list them]"
- "I found M transitions: [list them]"
- "The terminal states are: [list them]"
- "Transitions I could NOT find in code: [list them]"
```

This forces the agent to demonstrate understanding before generating tests. If the agent can't answer all four questions, it must mark the feature as `needs_manual_domain_review`. This prevents **misparse propagation** — the most dangerous failure mode in AI-driven analysis.

### 6. Independent verification as a first-class phase

Phase 6.5 mandates: **"Launch a separate agent instance. Do NOT self-verify."**

The independent agent receives:
- `zero_tracker.jsonl` (read-only)
- List of verified features
- `reproduce_cmd` for each bug

And is tasked to:
1. Re-run each reproduce_cmd
2. Check for weak evidence on pass_evidenced features
3. Report discrepancies

Each discrepancy found by the verifier reduces confidence score by 10%. This is a **game theory improvement**: the main agent can't cheat because a second agent gets paid to find its mistakes.

### 7. Environment realism

Phase 0 explicitly acknowledges that environments are imperfect:

- `codegraph` missing → grep fallback
- No test framework → `needs_oracle` status (not broken)
- No DB/infra → `blocked_environment` is valid outcome
- Each missing tool reduces confidence score but doesn't halt the sweep

This is critical for real-world deployment. Most quality tools fail on "what if there's no CI?" Reply #4 has an answer for every missing dependency.

---

## Structural Problems (remaining)

### P1. Independent verification is well-specified but not implementable

The SOP says "launch a separate agent instance" but:
- **No communication protocol** — how does the main agent pass data to the verifier? Files? IPC? Network?
- **No authentication** — any agent can claim to be the verifier
- **No timeout/retry** — what if the verifier hangs?
- **No degraded mode** — "mandatory" with no fallback
- **No verification of the verifier** — who audits the auditor?

This is the weakest part of an otherwise solid architecture. It needs at minimum:
```json
{
  "verifier_protocol": "subagent call via boss.sh --verify",
  "timeout_seconds": 300,
  "artifact_path": "zero_artifacts/verification/",
  "degraded_mode": "self-verify with explicit caveat in report"
}
```

### P2. No generated test lifecycle management

Tests are generated in Phase 3 and Phase 4. The good ones get committed. The rest stay in `zero_artifacts/`.

Problems:
- **Orphaned test files** accumulate across sweeps
- **No deduplication** — same test could be generated next sweep if the lesson was forgotten
- **No versioning** — if source code changes between sweeps, old generated tests become stale
- **No cleanup protocol** — there's a `--sync-lessons` but no `--clean-tests`

Need: `zero_artifacts/` should be cleared at the start of each sweep, and tests worth keeping should be explicitly committed (which Phase 5 does partially, but doesn't define cleanup).

### P3. The controller has no error handling

The controller SOP (`zero_active/main.sop`) defines the phase sequence:

```
Phase 0 (Bootstrap) → Phase 1 (Triage) → Phase 2 (Inventory) →
Phase 3 (Batch Loop) → Phase 4 (BL Audit) → Phase 5 (Regression) →
Phase 6 (Confidence + Verification)
```

But what if:
- Phase 0 crashes → skip to Phase 1 with degraded tools?
- Phase 2 finds 500 features → Phase 3 batch loop will run for hours?
- Phase 4 has no applicable oracles → skip?
- Phase 5 gate fails 3 times → what happens then?

The architecture assumes linear execution, but real quality sweeps have branches, skips, and early exits. The controller needs **state machine logic** for phase transitions, not a linear sequence.

### P4. Lessons sync is write-only

Lessons are recorded at the end of each sweep via `--sync-lessons`. But:

1. **When are lessons injected?** The SOP says "Phase 0 injects historical lessons" but doesn't specify how or which ones
2. **What if `zero_lessons.jsonl` grows to 500 entries?** No pruning strategy
3. **How are stale lessons detected?** A lesson from 6 months ago about a framework version that's been updated is worse than no lesson
4. **No conflict resolution** — what if the same oracle has contradicting lessons from different projects?

### P5. Oracle completeness gap

The only complete oracle is `oracles/triage/cwe25.oracle`. The remaining oracles referenced in the architecture:

| Oracle | Status in Reply #4 |
|--------|-------------------|
| triage/cwe25 | ✅ Complete (full CWE Top 25 grep patterns) |
| triage/code_smells | ❌ Template only |
| triage/config | ❌ Template only |
| security/authn | ❌ Referenced but not written |
| security/authz | ❌ Referenced but not written |
| security/inpval | ❌ Referenced but not written |
| business_logic/crud | ❌ Referenced but not written |
| business_logic/financial | ❌ Referenced but not written |
| business_logic/state_machine | ❌ Referenced but not written |
| business_logic/concurrency | ❌ Referenced but not written |
| business_logic/temporal | ❌ Referenced but not written |
| test_templates/* | ❌ All 5 referenced but not written |

The architecture is sound but only ~8% complete in terms of executable oracle code. The remaining oracles would add 500-1000 lines of executable content.

### P6. No quantitative threshold validation

Phase 6 has a confidence formula:

```python
score = sum(weight_i * oracle_score_i) / sum(weight_i) * 100
```

But there's no **threshold for what constitutes "good enough"**:
- Is 60% acceptable for a low-risk project?
- Is 90% required for a financial application?
- What happens when confidence is 40% — reject the sweep?

The system computes a number but doesn't define how to **act on it**. This reduces confidence to a vanity metric.

### P7. Mode Selection is still heuristic

Phase 2 says "Mode decision made (boss.sh called or heuristic applied)" — but the "heuristic" path is undefined. In the controller, the mode selection is:

> "Use goal mode for projects >50 features or multi-repo. Use default sequential for smaller projects."

This is arbitrary. A 40-feature microservices project is harder than a 60-feature monolith. The heuristic should be based on **complexity metrics** (number of subsystems, external dependencies, concurrency level) not just feature count.

---

## Comparison Table

| Dimension | Reply #1 | Reply #2 | Reply #3 | Reply #4 |
|-----------|----------|----------|----------|----------|
| Tokens to load SOP | 580 lines | 322 lines | 2447 lines | ~200 (controller) |
| Tool integration | None | grep only | Test runner | Test + grep + codegraph + lessons |
| Bug detection method | Agent reads code | OWASP checklist | Write tests | Write tests + trace + verify |
| Business logic coverage | None | None | Separate phase | Separate phase with self-validation |
| Objectivity | Low (opinion) | Medium (grep artifact) | High (test pass/fail) | High (artifact + verify) |
| Cross-sweep learning | None | None | None | `zero_lessons.jsonl` |
| Independent verification | None | None | None | Separate agent (specified) |
| Degraded mode | None | None | None | Explicit per tool |
| Oracle completeness | N/A | Partial | Template | CWE25 complete, others template |
| Adaptability to different contexts | Low | Low | Medium | High (framework-agnostic through INCLUDE/EXCLUDE) |

---

## What I Would Take From This

### Keep as-is:
1. **Modular architecture** — controller + phases + oracles with strict line limits
2. **Three-layer fallback** — codegraph → grep → file-path
3. **Oracle self-validation** (Phase 4.1) — prevents misparse propagation
4. **Lessons with oracle-scoped FP rate** — enables cross-sweep learning
5. **Batch isolation** — independent artifact directories per batch
6. **Risk-weighted confidence formula** — honest coverage assessment

### Needs refinement:
1. **Independent verification protocol** — needs communication spec, timeout, degraded mode
2. **Controller error handling** — needs state machine with retry/skip/abort transitions
3. **Lesson lifecycle** — needs pruning, staleness detection, conflict resolution
4. **Test lifecycle** — needs cleanup, dedup across sweeps
5. **Confidence threshold** — needs action policy per score range
6. **Mode selection** — needs complexity-based heuristic, not feature count
7. **Oracle completeness** — business logic oracles need to be written

### Missing entirely:
1. **Rollback** — no way to undo a sweep's changes if Phase 5 gate fails
2. **Concurrent sweep safety** — what if two sweeps run on the same project?
3. **Sweep cancellation** — no abort mechanism mid-sweep
4. **User notification** — no channel to inform the user of discovered bugs

---

## Summary for arena.ai

### Reply #4's core contribution:
> **"A QA system should be a modular architecture, not a prompt."**

This is the first response that understands the problem isn't "write better instructions for the AI" but "design a system where the AI plays a **defined role within a verifiable pipeline**."

### What it proves:
- The AI can critically respond to structural feedback (mapped every Review #3 issue to a concrete solution)
- Modular phase loading solves the token budget problem
- Cross-sweep learning is feasible with structured JSONL records
- Independent verification is possible in theory (implementation details pending)
- Degraded modes make the system robust to imperfect environments

### What it still leaves open:
- Implementation of the independent verifier is hand-wavy
- Oracle completeness is ~8% — the architecture is designed but not built
- Error handling and state transitions in the controller are absent
- Lesson lifecycle management is underspecified
- No rollback or cancellation mechanisms

### Verdict:
**Architecture: Ready for implementation. Content: 8% complete. Do not deploy without completing business logic oracles and verifier protocol.**

This is the response worth keeping. The others were iterations toward this.
