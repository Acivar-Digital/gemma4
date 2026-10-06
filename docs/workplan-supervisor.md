# 📋 OpenCode Execution Plan: Record Integrity & Root-Cause Attunement (Gemma 4 Submission)

**Author:** Supervisor / Senior Staff Engineer
**Date:** 2026-10-05
**Verdict this plan addresses:** REJECT of the "submit T1" proposal (see prior audit)
**Status:** PLAN ONLY — no code, no files modified, no submissions made.

---

## 0. Answers to the two questions the audit skipped

The audit template §6 asks these explicitly. I failed to answer them; here they are, **measured not assumed**:

### "Scripts 100% pydantic v2.0 upwards?" — **YES (v2 idiom), but UNDECLARED**

| Script | v1 markers (`.dict()`, `.json()`, `parse_obj`, `__fields__`, `@validator`, `@root_validator`, `class Config`, `BaseSettings`) | v2 markers |
|---|---|---|
| `skills/code-map/scripts/map.py` | **0** | `ConfigDict` |
| `skills/code-oracle/scripts/oracle.py` | **0** | n/a (no pydantic) |
| `skills/fast-grep/scripts/grep.py` | **0** | `BaseModel` |
| `skills/repro-check/scripts/check.py` | **0** | `BaseModel` |
| `skills/test-gate/scripts/gate.py` | **0** | `ConfigDict`, `model_config` (6 hits) |

System `pydantic` is **2.13.0**. No v1 API surface anywhere in the shipped scripts.

### "LLM scripts 100% pydantic-ai v2.0 upwards?" — **NOT APPLICABLE, none used**

`grep` across `my_submission/` and `scripts/`: **zero** references to `pydantic_ai` / `pydantic-ai`. The five shipped scripts are deterministic AST/grep/oracle utilities driven by the harness's tool loop, not agent-framework code. `google-adk` owns the agent loop server-side. **No pydantic-ai surface exists to audit.** (Note: `/tmp/g4venv` has no `pydantic_ai` installed, so adopting it would be a new dependency in an offline env — do not.)

- **Exploration Tools:** ⚠️ **Template deviation, declared.** This environment has no `/search`, `/investigate`, or codebase-indexing tool — it has `bash`, `read`, `edit`, `write`, and `xd://ast_*`. I substituted direct verification against the repo. No AST tool was needed because **no slice modifies code** (see below).
- **Codebase Indexing:** `gate_policy.yaml` schema (`adapter.required`, `allowed_file_extensions`); `HARNESS_README.md:144-150` (GenerationConstraints).
- **AST Pre-Check:** **None required.** No slice modifies the 5 skill scripts. S3 is a *recommendation to the user*, not an edit — AST mapping is deferred until/unless a change is authorised.


## 1b. 🚫 ORCHESTRATION DECLINED — the skill's own threshold is not met

`skill://orchestrator` states plainly:

> **Do not use it** when: the work is fewer than ~3 genuinely independent slices. […] Orchestration overhead […] costs more than the work it saves when slices are not actually independent. **Say so and do the work directly.**

**This work does not meet that threshold.** It is **~4 `bd forget` calls + 3 line edits in `docs/workplan.md`** — one small, strictly-ordered, non-parallelisable slice:


The user asked me to use the skill. **Following the skill means declining to orchestrate.** Ticket ceremony, subagent dispatch, and merge-audit would cost more than the fix and would add a collision surface to the most destructive operation in this session.

**This plan is therefore executed inline, serially, in this thread** — S1 immediately (it is blocking and tiny), S2/S4/S5 inline as read-only checks, S3 escalated to the user as a decision.


---

## 1. 🔍 Context, Tooling & AST Strategy

*Map out the codebase before writing a single line of code.*

- **Target Files:**
  - `docs/workplan.md` (lines 36, 119, 130) — three confirmed false claims
  - bd memory keys: `isolation-sequence-isolated-test-workflow-2026-10-05`, `null-structure-corrected-final-2026-10-05-supersedes`, `measurement-corrections-2026-10-05-four-of-my`
  - `my_submission/skills/*/scripts/*.py` (5 files) — undeclared pydantic dependency
  - `docs/FINDINGS.md` F2b/F2c — two refuted claims still stated as CONFIRMED
- **Exploration Tools:** `/investigate` on `scripts/preflight_check.py` (6 checks), `scripts/check_submission.py` (15 gates). `/search` for `g_`, `adapter.required`, `final_metrics`.
- **Codebase Indexing:** `gate_policy.yaml` schema (`adapter.required`, `allowed_file_extensions`); `HARNESS_README.md:144-150` (GenerationConstraints).
- **AST Pre-Check:** The 5 skill scripts need AST mapping **before** any pydantic hardening — specifically to confirm whether `BaseModel` subclasses are constructed at import time (top-level) or lazily inside functions. That distinction determines whether an undeclared-pydantic failure is *one* skill or *three of five*. **Do not hand-edit these; they ship.**

**Resolved gates** (persisted as `orch-gates`): lint **NONE**, typecheck **NONE**, test `/tmp/g4venv/bin/pytest tests/ -q`, submission `python3 scripts/check_submission.py` (only `submission`-category FAILs gate; the known non-gating `g_run_health` FAIL is tolerated), evaluation `./start.sh` **user-only**.

---

## 2. 🎯 Scope & Key Decisions to Lock (`bd`)

- **Objective:** Restore a trustworthy diagnosis record and make the undeclared-dependency risk explicit, so a future session inheriting `bd prime` cannot re-ingest retracted claims or ship a skill that dies on an offline env.
- **Architecture Decisions:**
  1. **Single source of truth for the null-bucket structure** — one bd memory (`null-bucket-structure-single-source-of-truth-2026`), all others deleted, not annotated. *Rationale: `bd prime` prints leading text; appended corrections are invisible.*
  2. **Delete, don't supersede.** `bd supersede` is issue-only; `bd forget` is the memory delete path. *Verified by capability probe.*
  3. **No manifest ships without explicit sign-off.** Adding `requirements.txt` to a 14-file zip changes the artifact under a gate that governs allowed extensions. *This is a user decision, not an agent decision.*
  4. **Do not run `./start.sh`.** All evaluation is user-executed per `AGENTS.md`.

### S3 verifiability — named interpreter (gap closed)

An earlier draft left S3 unverifiable: `/tmp/g4venv` has **no pydantic**, and `check_submission.py` is **stdlib-only** (`argparse, ast, hashlib, json, os, sys, zipfile, dataclasses, typing`) so it never executes a skill script. Under that draft, any S3 change to the shipped scripts would have shipped **unvalidated**.

**Resolved by measurement — a working gate does exist:**

```bash
python3 -c "import zipfile,tempfile,subprocess,sys,os; \
  z=zipfile.ZipFile('submission.zip'); d=tempfile.mkdtemp(); z.extractall(d); \
  r=subprocess.run([sys.executable, os.path.join(d,'skills/fast-grep/scripts/grep.py'),'--help'],capture_output=True); \
  print(r.returncode)"
# → exit 0
```

**The interpreter that can actually run the skill scripts is `python3` (system), pydantic 2.13.0 — NOT `/tmp/g4venv/bin/python`.** S3's output is therefore constrained to one of:

- **(a) system-`python3` verified** — any change to a skill script is re-gated with the above harness, asserting exit 0, before the zip is repacked; or
- **(b) explicitly out of scope for this cycle** — if it cannot be verified that way, it is not made now.

There is no third option. An unverified edit to a shipped artifact does not happen.

- **Context Lock-in:** 🛑 `bd remember` executed — `orch-gates` (done). `orch-plan` at dispatch.

---

## 3. 🛡️ Pre-Mortem & Threat Model

- **Input Edge Cases:** `final_metrics.total_completion_tokens` **does not exist at top level** — I read the absent key and defaulted to 0 across 95 files, inventing a 95/95 figure. *Mandatory pre-check: confirm the field path exists before quoting any metric.*
- **UX Feedback Loop:** Fail loud. A retracted claim must be **absent**, not annotated — a future reader who greps for it must get zero hits.
- **Concurrency & State:** Concurrent `bd remember` on the same key silently clobbers. One writer per key. `bd forget` is destructive and unrecoverable — **list before deleting, and confirm each key is genuinely false.**
- **Trust model:** I produced **four** wrong mechanisms this session. Any claim from me without a re-read is unverified. Subagent outputs require the same standard.

---

## 4. 🛠️ Step-by-Step Implementation

- [ ] **Phase 1: Purge false records (BLOCKING — do first)**
  - **Action:** `bd forget` three keys: `isolation-sequence-isolated-test-workflow-2026-10-05` (advertises revoked T2 with the refuted "4096 wasted tokens" rationale), `null-structure-corrected-final-2026-10-05-supersedes` (duplicate authority), `measurement-corrections-2026-10-05-four-of-my` (overlaps/contradicts surviving authority). **Retain** `retracted-2026-10-05-two-of-my-own` (valid run_B39 retraction, distinct scope). Fix `workplan.md:36` (delete the "never sees back" claim, point to the E2 revocation), `:119` (demote "mechanism is" to "observed pattern, unattributed"), `:130` (repoint at surviving key, drop the three dead key names). Re-`bd remember` one isolation-sequence memory matching §3.
  - **Validation:** `bd memories` grep for `P2/P3|process died|T2 include_thoughts|wrong-fix, not search|sequential phase` returns **zero** hits. `check_submission.py` unaffected.
  - 🛑 **Context Lock:** `bd remember "decision-record-purge: …"`.

- [ ] **Phase 2: AST-map the pydantic import surface (read-only)**
  - **Action:** Determine via AST whether `BaseModel` subclass construction is top-level or lazy in the 5 shipped scripts. Output: a blast-radius statement — "missing pydantic breaks N of 5 skills" vs "breaks 1".
  - **Validation:** AST report, no file modified. Confirm 0 v1 markers.
  - 🛑 **Context Lock:** `bd remember "pydantic-blast-radius: …"`.

- [ ] **Phase 3: Dependency decision (BLOCKED on user)**
  - **Action:** Present the blast radius + offline-env constraint + "no manifest may ship without sign-off" to the user. Options: (a) leave as-is and accept the risk, (b) add a guarded `try/except ImportError` fallback shim inside the scripts, (c) add a manifest (changes the artifact — needs sign-off). **Recommend (b)**: it degrades one skill instead of three, ships inside the existing `.py` allowance, and touches no config.
  - **Validation:** AST-confirmed failure-mode test; `check_submission.py` exit unchanged; `g_disallowed_extensions` still passes.
  - 🛑 **Context Lock:** `bd remember "decision-pydantic-dependency: …"`.

- [ ] **Phase 4: Restore observability (gates T1)**
  - **Action:** All 129 run logs are **0 bytes** — the next cycle is unreadable without this. Determine why logs are empty and whether we can capture the endpoint's failure signal (429/500/OOM) into the local run.
  - **Validation:** A local non-eval dry-run writes non-empty logs. **Not** `./start.sh`.
  - 🛑 **Context Lock:** `bd remember "decision-observability: …"`.

- [ ] **Phase 5: Resolve F10 (gates any submission)**
  - **Action:** Determine what the Kaggle scoring runtime actually mounts. F10 reports the canary loaded an adapter from a side-channel dataset. If the runtime mounts an adapter we don't control, the submission we package may not be the one that is scored.
  - **Validation:** Documented answer with source. **This is the gate on spending quota.**
  - 🛑 **Context Lock:** `bd remember "decision-f10-runtime-mount: …"`.

---

## 5. 🔄 The OpenCode Test & Resolution Protocol

- **Initial Test Phase:** `/tmp/g4venv/bin/pytest tests/ -q` (baseline 87 passed) + `python3 scripts/check_submission.py` (baseline: 0 gating FAILs, 1 tolerated non-gating).
- **Failure Protocol:** On any failure, I will **halt** direct modification.
- **AST & Subagent Escalation:**
  1. Halt direct modification.
  2. Spawn a subagent / use `xd://ast_edit` + `xd://ast_grep` to structurally diagnose before any edit.
  3. Apply the fix only after AST confirms the root cause; re-test with captured exit codes.

**Explicitly forbidden:** blind `test > fix > repeat`; patching from a conversational assertion; reporting an unrun check as passing.

---

## 6. 🚀 Deployment, Testing & Rollback Strategy

- **Pre-Flight Checks:** `bd memories` grep returns zero retracted claims; `pytest tests/ -q` exit 0; `check_submission.py` 0 gating FAILs; `git status` reviewed (pre-existing dirty: `check-status.sh`, `docs/09-roadmap.md`, `kaggle_adapter_dataset/*` [86 MB safetensors — never stage], `kaggle_baseline_v1/*.ipynb`, `scripts/push_kernel_safe.sh`).
- **Cutover Strategy:** None required. Phases 1–2 and 4–5 are docs/memory/read-only. Phase 3 may alter shipped `.py` files; if taken, re-pack and re-gate before any submission.
- **Deployment Testing & Anti-Bloat:** evaluation is `./start.sh`, **user-executed only**. If a cycle fails, AST-diagnose first, then delegate the fix — never blind-patch in the main thread.
- **Rollback Steps:**
  1. `git revert <sha>` for tracked files (last pushed gate fix: `665d352`).
  2. `bd forget` the offending key and `bd remember` the corrected text — memories are not version-controlled.
  3. Re-pack: `scripts/submit_safe.sh` rebuilds `submission.zip` in seconds; never commit the zip (`AGENTS.md`: `.gitignore`d, ~80 MB per commit in history if tracked).
- 🛑 **Final Context Lock:** `bd remember` the completed state, prune transient `orch-*` keys.

---

## 7. Orchestration Workplan

**Objective:** Restore record integrity (S1) and de-risk the undeclared pydantic dependency (S2), gating any future submission on F10 + observability.
**Repo:** `/home/vps466a/arthityap/gemma4`  **Gates:** see `orch-gates`

| Batch | Slice | Target | Depends on | Collision risk | Mode |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | S1 | bd memories + `workplan.md` lines 36/119/130 | — | **S1 owns all bd writes — exclusive** | parallel |
| 1 | S2 | AST map of 5 shipped skill scripts | — | read-only, none | parallel |
| 2 | S3 | pydantic fallback decision | S2 | S3 needs S2's blast radius | sequential |
| 2 | S4 | Observability: why 0-byte logs | — | none | parallel |
| 2 | S5 | F10 runtime-mount question | — | none (external research) | parallel |

**Acceptance**
- S1 — retracted claims return **zero** grep hits across `bd memories` and `workplan.md`; surviving keys cross-reference correctly.
- S2 — AST report naming top-level vs lazy `BaseModel` use per script; 0 v1 markers confirmed.
- S3 — decision recorded, or explicitly blocked on user.
- S4 — documented cause of empty logs; remediation proposal.
- S5 — documented answer with source, or explicitly unresolved.

---

## 8. Orchestrator Boundary (declared, per skill)

The skill requires the conductor to **never implement**. I am operating with execution tools available, so I will **enforce the boundary by preference and say so plainly** — S2/S4/S5 are read-only and will be delegated to `scout`; S1 is a small, ordered, destructive-memory sequence that is safer done serially in the main thread than fanned out. **I am not claiming the boundary was harness-enforced; it was not.**

---

## 🏁 Verdict

**APPROVE WITH CONDITIONS** — for this plan (not for the submission).

Conditions, in order:
1. **S1 before anything else.** A rejected submission was partly rejected because the record asserted three retracted claims. Fixing that is Phase 1.
2. **No submission until S5 (F10) and S4 (observability) resolve.** We do not know what the scoring runtime loads, and the last run produced zero diagnostics. Spending a possibly-unrecoverable cycle before both are answered is how we get a second 0/129 we cannot explain.
3. **S3 is a user decision.** I will not add a manifest to the shipped artifact without explicit sign-off.

**On the original "submit T1" proposal: still REJECT**, on the same grounds — 86% of the last run failed for reasons we have not identified, and we currently cannot observe or attribute them.
