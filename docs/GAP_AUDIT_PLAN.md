# GAP AUDIT — PLAN, COVERAGE MATRIX, AND COMPLETENESS GATE

Status: ACTIVE. Owner: lead. Last updated: 2026-10-04.

## 0. Objective (locked)

Raise Resolution Rate on the **full 129-task suite** (`test_all.txt`).

**True baseline: 45.7% (run_B37, 59/129).** NOT 43.4% (B39) and NOT 64.9% (B40).
B40 is a cherry-picked 77-task subset — `test.txt` holds exactly 77 IDs, `test_all.txt` holds 129.
Proof: on B40's own 77 tasks, B35/B37/B39 already scored ~64%. Nothing improved; hard tasks were removed.

Success = a shipped change that measurably beats 59/129 on the full suite.

---

## 1. Coverage matrix — the completeness contract

Work is NOT done until every row is `covered`. A row with no owner or no verifier is a gap.

| # | Artifact class | Must answer | Owner | Verifier | Status |
|---|---|---|---|---|---|
| R1 | `HARNESS_README.md`, `EXTERNAL_REVIEW_PACKET.md` | Every hard constraint, file:line | qa | reviewer | reported |
| R2 | `results/run_B01..B40` | Config delta per run → score; is B40 a subset? | scout | builder | in progress |
| R3 | `my_submission/**` (every file) | What it does; every defect found | scout | reviewer | in progress |
| R4 | `results/run_B39` failures (73) | Categorized + counted + trace evidence | builder | **unassigned** | reported, UNVERIFIED |
| R5 | Fix proposals | Exact diff, gain range, regression risk | reviewer | builder | in progress |
| R6 | **Verification of R4 claims** | Is each headline statistic actually true? | **unassigned** | lead | NOT STARTED |
| R7 | **Coverage-gap audit** | What did we never look at? | **unassigned** | lead | NOT STARTED |

R6 and R7 are the rows my original plan omitted. They are the reason this plan was weak.

---

## 2. Dependency graph (the error in v1)

```
v1 (WRONG):   R1 ──┐
               R2 ──┼──> R4 ──> R5        R4 started before R1/R2 landed
                       └───────────────>   ⇒ ungrounded conclusions

v2 (CORRECT): R1 ──┐
               R2 ──┴──> R4 ──> R6 ──> R5
                                    ▲
                    R7 audits coverage of all rows
```

Rule: **R5 (fixes) may not be finalized until R6 verifies R4.** Unverified statistics must not
propagate into a diff that a human approves.

---

## 3. Unverified claims carried forward (must be checked before any diff ships)

From the builder's report. None of these are trusted yet.

| Claim | Needs |
|---|---|
| zero-match grep turns: 0 → 65% resolved, 6+ → 8% | recompute from traces, confirm denominators |
| first source edit ≤6 → 62%, 26+ → 5% (1/20) | confirm n and bucket boundaries |
| patch ≤1200B → 66%; >6000B → 0% (0/12) | confirm 0/12 is not a small-n artifact |
| 44 turns truncated at exactly 4096 thinking tokens | confirm from trace metrics, not inferred |
| `get_status` used in 31/129 tasks | confirm total tool-call count denominator |
| 3 graph tools called 0 times | confirm they are actually absent from `agent.yaml` |
| 0 test-file edits across 129 | high-stakes negative — confirm scan actually ran |
| `fast-grep` SKILL.md zero-match block is at :16-24 | confirm exact lines |

---

## 4. Write permissions (shared tree — worktree isolation FAILED)

Teammates may write ONLY to `docs/FINDINGS.md` (append their own section).
`my_submission/`, `sample_submission/`, `results/`, `scripts/`, `docs/*` otherwise READ-ONLY.
No one runs `./start.sh` or any evaluation. That is the user's alone.

---

## 5. Evidence store — so nothing is ever re-searched

`docs/FINDINGS.md` is append-only, one section per claim, each with a `file:line` or trace path.
Answering a later question = a lookup in that file, not a fresh sweep of the repo.

This exists specifically so that no question requires "going searching high and low."
