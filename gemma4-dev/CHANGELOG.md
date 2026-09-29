# Changelog

All notable changes to the SWE-Gemma Autonomous Developer Agent submission architecture and evaluation harness.

## [Unreleased] - 2026-09-30

### Fixed & Hardened (Red-Team Audit Remediations)
- **Prompt Generalization (`my_submission/prompts/main.md`)**:
  - Purged task-specific overfitting and contamination (`rich_4076`, `Text.from_ansi`, `splitlines()`).
  - Added generalized technical keyword decomposition guidance for issue statements.
  - Mandated assertion discipline for `repro-check` (requiring explicit assertions on public APIs).
  - Enforced periodic `get_status()` self-metering (every 4–5 turns).
  - Implemented strict 15-call delegation ceiling (hard max 18) leaving $\ge 10\text{--}15$ calls for Supervisor.
  - Established strict structured handoff contract schema for delegating to `supervisor(request="...")`.

- **Supervisor Diff Visibility & Emergency Circuit Breaker (`my_submission/prompts/supervisor.md`, `agent.yaml`, `sub_agents/supervisor.yaml`)**:
  - Registered `diff-inspect` skill in `agent.yaml` and `sub_agents/supervisor.yaml`.
  - Documented `run_skill_script(skill_name="diff-inspect", file_path="diff.py")` to inspect workspace diff and detect scratch file pollution.
  - Enforced emergency low-budget circuit breaker: if `tool_calls_remaining <= 5` or `tool_calls_used >= 45`, Supervisor halts all expensive tools and calls `submit_patch()` immediately.
  - Strictly prohibited conversational apologies and markdown explanations when blocked.

- **Skills Concurrency Hardening & New Diff Skill (`my_submission/skills/`)**:
  - Created `skills/diff-inspect/` (`SKILL.md` and `diff.py` mirrored across `scripts/` and root) to run `git status --short` and `git diff` against `_swegemma_baseline` / `HEAD` (capped at 100 lines).
  - Eliminated the `/tmp/swegemma_sandbox_*` mtime globbing race condition across all 6 skills (`check.py`, `grep.py`, `test_blast.py`, `find_refs.py`, `map.py`, `diff.py`).
  - Implemented deterministic workspace resolution hierarchy (`_orig_cwd` $\to$ `SWEGEMMA_WORKSPACE` $\to$ `/workspace` $\to$ repo marker search $\to$ `cwd().resolve()`).
  - Purged all `/tmp/brun` hardcoded paths from `test_blast.py`, using dynamic `sys.executable` and `shutil.which`.
  - Synchronized root and `scripts/` Python files across all skill packages.

- **Pydantic v2 Schema Enforcement (`scripts/run_eval.py`, `scripts/preflight_check.py`)**:
  - Upgraded CLI argument parsing, runtime data pipelines, and serialization to 100% Pydantic v2 `BaseModel` schemas (`EvalRunConfig`, `TaskEvalResult`, `RunSummary`).
  - Upgraded preflight diagnostics and reporting to Pydantic v2 models (`CheckResult`, `PreflightReport`).
  - Verified 100% compatibility across Python 3.14 and Pydantic v2.13.5.
