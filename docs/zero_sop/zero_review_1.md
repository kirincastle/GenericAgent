# Zero SOP AI Reply — Review

> Review of `zero_ai_reply1.txt` — an AI-generated rewrite of the Zero Mode SOP
> Reviewer: GenericAgent (GA) system maintainer
> Date: 2026-06-24

---

## Executive Summary

The AI correctly diagnosed the original problem ("SOP tells AI *what* to call, not *how* to judge/discover/verify") but then wrote a 580-line SOP that repeats the same fallacy in richer detail. The core assumption — that a longer, more procedurally detailed prompt will make AI find more bugs — is not supported by evidence.

**Rating: Structural redesign needed, not incremental refinement.**

---

## 1. Core Contradiction

| AI's own diagnosis | AI's solution |
|---|---|
| "原版 SOP 告诉 AI '调什么'，但没告诉 AI '怎么判断、怎么发现、怎么验证'" | Writes a 580-line SOP telling AI *exactly what steps to follow* |

The solution does not address the diagnosis. The problem is **not** that steps are insufficiently described — it's that **code defect detection is a capability AI does not robustly have**, and no amount of procedural instruction creates that capability.

---

## 2. Seven Structural Problems

### P1. False Precision (False Sense of Rigor)

The SOP mandates a detailed JSON tracker schema:

```json
{
  "expected_behavior": ["POST /api/auth/login with {email, password}", "..."],
  "code_location": ["src/routes/auth.ts:14-45"],
  "errors": [{"category": "security", "severity": "high", "description": "..."}]
}
```

This creates the appearance of systematic testing. But the critical step — reading code and finding bugs — is **entirely dependent on the AI's unaided ability**. A beautifully formatted empty result is still empty.

Every bug report in the tracker is **self-reported by the AI**. There is no independent verification, no reproduction step, no automated assertion that fails.

### P2. Zero Automation Integration

| Category | What SOP asks AI to do | What it should use instead |
|----------|----------------------|---------------------------|
| Input validation | "Read code and check" | linter, type checker, zod/yup schema validation |
| N+1 queries | "Check for queries in loops" | ORM query profiler, n+1 detector |
| Error handling | "Search try/catch" | TypeScript strict mode, eslint-plugin-unicorn |
| Testing | AI manually "traces paths" | pytest / jest / existing test suite |
| Edge cases | "Think about edge cases" | fuzzer, property-based testing (Hypothesis/QuickCheck) |
| Regressions | AI re-reads fixed code | snapshot testing, CI pipeline |
| Security | "Check auth middleware" | SAST (semgrep, CodeQL), dependency audit |

The entire SOP is **manual code reading with no tooling layer**.

### P3. Token Budget Problem

580 lines of SOP consumed before the AI even opens the first source file. The SOP defines 5 Phases, 20+ steps, 100+ checklist items. This creates a direct trade-off:

- **More SOP detail** → Less context for source code → Worse defect detection
- **Less SOP detail** → More context for source code → Better defect detection, but less guidance

The SOP chose the wrong side of this trade-off. Critical information (anti-patterns, mode selection tables) competes with source code for limited context.

### P4. Self-Verification Loop (No Objective Gates)

Every "Completion Criteria" block is a self-checked checkbox:

```
- [ ] Every route/endpoint has a corresponding feature entry
- [ ] Every feature has expected_behavior with at least 2 items
- [ ] Auth boundaries are explicitly called out
```

The AI asks itself "did I do this?" and answers itself. There is no:
- Independent measurement
- Reproducible test run
- External diff/validation
- Integration with CI

This is equivalent to a student grading their own homework.

### P5. Mode Selection is Not Actionable

The SOP spends significant space on when to use goal/hive/conductor mode (lines 98-134). But the decision matrix requires the AI to already understand the codebase size, feature count, and complexity — which is the discovery Phase 1 is supposed to produce.

This is a circular dependency: **you need to finish Phase 1 to decide the mode, but you need to decide the mode to execute Phase 1 efficiently.**

### P6. Phase 2 ↔ Phase 3 Isolation is Wrong

The SOP mandates "Complete ALL of Phase 2 before starting Phase 3" (Anti-pattern #5). While this avoids losing the full picture, it creates a practical problem:

- In a large project, Phase 2 may produce 50+ bugs
- Phase 3 then must fix 50+ bugs without re-testing earlier ones
- Fix 1 may change code that Fix 2 depends on
- Fix 30 may break something Fix 10 fixed

The **regression loop** (Phase 4) is supposed to catch this, but the regression loop is also entirely manual AI re-reading. This is slow, expensive, and misses cross-feature interactions.

### P7. "Why can't AI find bugs" is Never Answered

The user's original complaint: **"用 zero 都找不出 project 里面的问题"**

The AI reply interprets this as "the SOP is not detailed enough" and provides more detail. It never analyzes root causes:

- Is the AI's code reading capability insufficient for this codebase? (likely, for non-trivial projects)
- Is the context window too small for full-project analysis? (always)
- Is the problem that there's no test oracle — no way to know what "correct" means? (common)
- Does the project need static analysis, not AI reading? (often yes)
- Is the AI hallucinating correctness when it doesn't find bugs? (probable)

Until these questions are answered, no SOP change will reliably improve outcomes.

---

## 3. What the AI Reply Got Right

Not everything is wrong. The SOP has genuinely good elements:

1. **Tool discovery bootstrap** (lines 35-95) — verifying tools exist before proceeding is essential and rarely done
2. **Context window management** (lines 127-134) — acknowledging the constraint and checkpointing to disk is pragmatic
3. **Anti-patterns catalog** (lines 566-582) — useful reference, especially #8 (impact analysis before fixing) and #9 (holding state only in memory)
4. **Hard dependency on tracker as source of truth** — the JSONL-based checkpoint design prevents total loss on context reset
5. **Tying code_location to every bug** — traceability to exact file:line is non-negotiable

These are good **process** rules, but they don't solve the **capability** problem.

---

## 4. Recommended Direction

Instead of a more detailed SOP, consider:

1. **Replace manual checks with tools.** A linter catches input validation bugs faster and more reliably than an AI reading code. A test runner with real assertions is actual QA.

2. **Shift from "full sweep" to "diff-based incremental audit."** AI is better at finding bugs in new/changed code than in a full codebase. Compare HEAD against a known-good baseline.

3. **Make the AI write tests, not read code.** Instead of "trace the happy path," have it generate a test, run it, and observe the result. This produces an objective pass/fail.

4. **Shorten the SOP, load it per-phase.** Phase 1 SOP is loaded → execute → checkpoint. Phase 2 SOP is loaded → execute → checkpoint. Never load the full 580 lines at once.

5. **Add an objective quality gate at the end:** run the project's actual test suite, check code coverage, run linter with strict rules. If these pass, the sweep produced value. If not, the sweep missed things regardless of the SOP.

---

## 5. Conclusion

The AI reply is a well-structured, internally consistent document that fails to address the user's actual problem. It treats a **capability gap** as a **process gap** and prescribes more process, which will produce more token consumption but not more bugs found.

**Verdict: Do not adopt as-is. Redesign around tools + tests + diff, not manual code reading with better formatting.**
