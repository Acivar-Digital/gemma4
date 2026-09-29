# Changelog

All notable changes to the SWE-Gemma Autonomous Developer Agent submission architecture and evaluation harness.

## [Unreleased] - 2026-09-30

### Changed (Single-Agent Lean Monolith Migration)
- **Omnivorous Tools Overhaul (`my_submission/skills/`)**:
  - **`fast-grep`**:
    - **Multi-Argument Ingestion**: Accepts any number of arguments; searches all passed terms concurrently (`term1 | term2 | term3`).
    - **Intelligent Path vs Token Separation**: Automatically checks if any argument is an existing path; treats all other tokens as search terms.
    - **Spam Filtering**: Automatically excludes `benchmarks/`, `docs/`, `build/`, `dist/`, `.tox/`, `venv/`, and non-code telemetry files (`*.lock`, `*.json`, `*.csv`) to eliminate commit-hash spam.
    - **Dual Regex/Literal Engine**: Extended regex (`-E`) with silent fallback to fixed-strings (`-F`) for unescaped code snippets.
    - **Full Decorator AST Scopes**: Captures `@app.get`, `@property`, `@classmethod` in start lines.
  - **`repro-check`**:
    - **AST Auto-Assertion Rewriter**: Automatically transforms bare comparison expressions (e.g. `a == b` or `func() == 3`) into assertions (`assert a == b, ...`).
    - **Auto-Runner for Test Functions**: Automatically discovers and invokes uncalled top-level test functions (`def test_...():`).
    - **Markdown Fence & Escape Stripper**: Cleanly strips ` ```py `, ` ```python `, and unescapes newlines without errors.
    - **Hermetic Sandbox Isolation**: Runs child processes strictly inside `/tmp` with `PYTHONPATH=/workspace/src:/workspace` and `PYTHONSAFEPATH=1`, guaranteeing zero git pollution in `/workspace`.
    - **Accurate Defect Classification**: Clearly distinguishes between `DEFECT CONFIRMED (Assertion Failed)`, `DEFECT REPRODUCED (Workspace Runtime Exception)`, `PASSED`, and `PROBE EXECUTION`.
- **Git State Branching**:
  - Created persistent git branch `supervisor` (commit `d51b186`) preserving the full 2-agent architecture, supervisor subagent, and handoff contracts for archival and rollback.
- **Architectural Simplification (`my_submission/`)**:
  - Dropped `supervisor` subagent (`my_submission/sub_agents/supervisor.yaml` and `my_submission/prompts/supervisor.md`).
  - Promoted `submit_patch` directly to `main` agent in `my_submission/agent.yaml`.
  - Consolidated full task ownership into a single autonomous agent, eliminating diffusion of responsibility and delegation starvation.
- **Modus Operandi & Mouse-Reading Elimination (`my_submission/prompts/main.md`)**:
  - **Surgical Line Offsets**: Strictly banned calling `read_file` from line 1 of large files (>100 lines); mandated specifying `start_line` and `end_line` centered around hits (e.g. `start_line = max(1, target - 25)`, `end_line = target + 25`) to prevent burning tool calls reading license headers and boilerplate imports.
  - **Batched Test Matrices (`repro-check`)**: Mandated running multi-hypothesis and multi-module checks in a single script assertion matrix (e.g. testing candidate 1 and candidate 2 in 1 call) rather than sequential 1-assertion calls.
  - **Bare-Symbol Search Queries (`search_similar_code`)**: Constrained queries to bare identifiers (`split_lines`, `AnsiDecoder`) without Python syntax (`def `, `class `, `()`) or conversational English.
  - **Action Bias & Mutation Ceiling**: Enforced maximum 3 investigative calls before formulating a hypothesis; mandated calling `edit_file` within the first 6 tool calls.
  - **Post-Verification Immediate Submission**: Post-edit `repro-check` $\to$ `diff-inspect` $\to$ immediate `submit_patch()` without redundant test loops.
- **Diagnostics & Preflight (`scripts/preflight_check.py`)**:
  - Updated preflight live diagnostic check to support lean monolith single-agent architectures, validating that the model directly recognizes its full toolbelt, skills, surgical offset discipline, and submission authority.
  - Verified 6/6 preflight checks passing (100% watertight).

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
