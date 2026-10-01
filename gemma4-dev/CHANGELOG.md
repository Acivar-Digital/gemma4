# Changelog

All notable changes to the SWE-Gemma Autonomous Developer Agent submission architecture and evaluation harness.

## [Unreleased] - 2026-10-01 (5-Skill Architecture: Code-Oracle, Test-Gate, Repro-Check Deep Diagnostics)

### 5-Skill Architecture: Code-Oracle, Test-Gate, Repro-Check & Integration (projects-57i, projects-x9g, projects-rdn, projects-6x4)
- **Built `skills/code-oracle` (`projects-57i`)**:
  - Implemented zero-dependency multi-domain oracle tool (`oracle.py` & `scripts/oracle.py`) resolving 5 core competition nuances without repo-specific overfitting.
  - Multi-mode CLI interface:
    - `--eval <expr>`: Safe Python expression evaluation in a sandboxed runtime; outputs type, `repr()`, and length.
    - `--hex <text>`: Formatted byte & escape code inspector; decodes ANSI CSI SGR colors/resets, OSC 8 hyperlinks, lone `\r` carriage returns, and invisible zero-width characters (`\u200b`, `\u200d`, `\ufe0f`).
    - `--width <text>`: Calculates exact terminal cell display width for monospaced terminals (CJK East Asian Wide `W`/`F` = 2, emoji ZWJ sequences = 2, combining marks = 0, ANSI = 0) vs `len(text)`.
    - `--html-esc <snippet>`: Inspects HTML/template strings for entity escaping (`&lt;`, `&gt;`, `&amp;`), tag balance, and script tag injection safety (OWASP `<script>` breakout prevention).
    - `--schema <file_or_json>`: Inspects JSON Schema / OpenAPI schema structure; validates `$defs` vs `definitions`, local `$ref` pointer resolution, `anyOf` nullability (`{"type": "null"}` vs invalid `"None"`), and schema tree health.
    - `--syntax <file>`: Validates AST syntax (`ast.parse`), catches regex lookbehind errors, and verifies top-level module imports without executing side-effects (cleanly absorbing legacy `syntax-guard`).
    - Empty invocation: Overview mode with copy-pasteable example commands tailored to SWE-Gemma agents (exit code 0).
  - Byte-for-byte synchronization verified via `cmp`.
  - Comprehensive unit test suite in `tests/test_code_oracle.py` (9/9 passed).
- **Enhanced `skills/repro-check` (`projects-rdn`)**:
  - Upgraded isolated reproduction test runner (`check.py` & `scripts/check.py`) with **Deep Assertion Diagnostics**.
  - On assertion failure, automatically dissects operands:
    - *String Mismatches*: Prints `Actual` and `Expected` with `repr()`, lengths, character index of first divergence (`Diff at index <i>: actual='...' (hex: 0x...) vs expected='...' (hex: 0x...)`), and ANSI escape / control character breakdown.
    - *Dict / JSON Mismatches*: Dissects missing keys, extra keys, and value mismatches for shared keys.
    - *Sequence / List Mismatches*: Details length divergence and identifies first differing element.
    - *Actionable Guidance*: Emits `💡 ROOT CAUSE HINT FOR LLM:` summarizing the defect mechanism.
  - Retained outer quote stripping, `--b64` mode, AST pre-parsing, and hermetic `/tmp` execution.
  - Unit test suite in `tests/test_repro_check_diagnostics.py` (7/7 passed).
- **Consolidated `skills/test-gate` (`projects-x9g`)**:
  - Unified regression testing (`blast-radius`), safe diff inspection (`diff-inspect`), and pre-submit syntax validation (`syntax-guard`) into a single authoritative `skills/test-gate/gate.py` tool.
  - Multi-mode CLI interface supporting `--blast` (distance-1 neighbor regression test runner via AST import graph), `--diff` (safe read-only git diff viewer with hard forbidden test-file modification assertion), `--status` (syntax verification on touched files + readiness recommendation), and `--json` structured telemetry.
  - Enforced Container B compliance: emits loud `🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE` warning and remediation instructions (`git checkout -- <file>`) if any test files are touched.
  - Byte-for-byte synchronization between `my_submission/skills/test-gate/gate.py` and `scripts/gate.py`.
  - Comprehensive unit test suite in `tests/test_test_gate.py` verifying all operational modes (7/7 passed).
- **Architecture Streamlining & Obsolete Skill Retirement (`projects-6x4`)**:
  - Wired authoritative 5-skill lean architecture into `my_submission/agent.yaml`: `code-map`, `fast-grep`, `code-oracle`, `repro-check`, and `test-gate`.
  - Retired obsolete directories `skills/syntax-guard/`, `skills/blast-radius/`, and `skills/diff-inspect/`.
  - Purged all `__pycache__` and `.pyc` artifacts from `my_submission/`.
  - Updated `my_submission/prompts/main.md` with concise 5-phase lifecycle (Search, Inspection, Fix, Domain Nuance & Regression, Patch Inspection) and domain guidance (ANSI, Unicode widths, HTML, Schema).
  - Fixed Google ADK template injection break in `skills/repro-check/SKILL.md` where unescaped braces `{i}` broke `inject_session_state`.
  - Passed 6/6 preflight validation checks in `scripts/preflight_check.py` with 100% compliance.

### Omnivorous & Forgiving Skill Hardening (projects-1ff, projects-7yz)
- **`skills/fast-grep` Hardened & Restored (`projects-1ff`)**:
  - *Restored AST Fuzzy Suggestions*: Restored fuzzy symbol suggestions (`FuzzySuggestion`) during 0-match events with AST kind, file location, and similarity score, so the LLM immediately knows valid symbols when exact match fails.
  - *Smart Compound Queries & Stopword Filtering*: Preserves exact compound phrases for primary search; falls back to non-stopword tokens if the full phrase fails (preventing runaway keyword OR explosion).
  - *Regex & Metacharacter Resilience*: Automatically sanitizes unescaped regex metacharacters (`()[]{}\\$^*+?|.`), using extended regex (`-E`) -> fixed strings (`-F`) -> pure Python scanner fallback.
  - *Path Tolerance & LLM Guidance*: If a non-existent target path is provided, warns the LLM with `⚠️ TARGET PATH NOT FOUND`, suggests closest matching files, and gracefully falls back to `/workspace` search instead of aborting.
  - *Zero Crash Loops & Backtracking Elimination*: Added `followlinks=False`, 50K file limit, 500KB file size skips, and replaced greedy nested regexes in `score_match` with token extraction to prevent catastrophic backtracking.
- **`skills/code-map` Hardened & Forgiving Auto-Detection (`projects-7yz`)**:
  - *Forgiving Positional Argument Auto-Detection*: Seamlessly infers whether a positional argument is a symbol name (`args=["APIRouter"]`), a file path (`args=["fastapi/routing.py"]` or extensionless `args=["routing"]`), or a directory (`args=["fastapi"]`), without crashing if `--symbol` or `--file` flags are omitted.
  - *Zero-Crash Overview Mode*: Calling `map.py` with no arguments, `.`, or `/workspace` executes Repository Overview Mode (exit code 0), displaying top-level structure, discovered packages, and actionable copy-pasteable example commands tailored to the repo.
  - *Restored Class Hierarchies*: Recovers base classes (`bases`) and subclass relationships (`subclasses`) in AST reference tracing.
  - *Loop-Safe & Cycle-Free Traversal*: Implemented `safe_walk()` with `followlinks=False`, depth bounding (max 15), and inode/device tracking `(st_dev, st_ino)` to eliminate symlink cycles. Guarded AST recursive extraction with depth limit (max 8) and `RecursionError` handlers.
  - *Actionable LLM Diagnostics*: Unknown symbols trigger fuzzy matching + workspace top-level public symbol lists; unknown files trigger closest existing path recommendations.

## [2026-10-01] - (Monolithic Toolset Streamline & Run B37 Hardening)

### Lean Tool Consolidation & Dual-Modality Elimination
- **Killed `search_similar_code`**: Dropped from `my_submission/agent.yaml` tools to resolve Turn 1 search hesitation and split-brain tool competition. Established `fast-grep` as the authoritative single search tool.
- **Unified `skills/code-map` (`projects-8fx`)**:
  - Merged `code-graph` (75% win rate when tracing symbols) and `repo-map` (0% win rate panic dumps) into a single disciplined skill `skills/code-map/`.
  - Supports `--symbol <name>` for AST caller/callee/definition graph traces and `--file <path>` for compact file skeletons.
  - Strictly rejects `args=None` and empty calls with exit code 1 to permanently prevent token-budget-killing whole-repo dumps.
  - Pruned obsolete `skills/code-graph` and `skills/repo-map` directories.
- **Hardened `skills/repro-check` (`projects-o23`)**:
  - Implemented automatic quote sanitization (stripping outer enclosing quotes, markdown blocks, normalizing double-escaped `\"` and `\'`).
  - Added AST pre-parse syntax validation (`ast.parse()`) with clean `SYNTAX_ERROR` diagnostics, preventing unhandled `JSONDecodeError: Expecting ',' delimiter` crashes that regressed `rich_3521`, `rich_3676`, and `fastapi_14258`.
  - Added `--b64` / `--base64` flag allowing shell/JSON quote-free execution of complex assertion payloads.
- **Refactored `skills/fast-grep`**:
  - Eliminated fuzzy Levenshtein symbol hallucinations on zero matches that misled the model into investigating unrelated utility functions.
  - Replaced the middle-fold truncation trap (>100 lines) with a target-centered sliding window ($[\text{match\_line} - 15, \text{match\_line} + 25]$), ensuring the buggy line and immediate context are always visible.
  - Added dedicated unadorned `[CLEAN CODE FOR edit_file (EXACT INDENTATION)]` block for the #1 match to prevent line-number prefixes from polluting `edit_file`.
  - Capped full scope flashes from 3 to 2 to conserve context tokens.
- **Declarative Synchronization (`projects-y8e`)**:
  - Updated `my_submission/agent.yaml` and `my_submission/prompts/main.md` with the 6-skill lean monolithic toolset (`fast-grep`, `blast-radius`, `repro-check`, `syntax-guard`, `diff-inspect`, `code-map`).
  - Preflight environment and submission compilation checks verified 6/6 passing with 100% watertight compliance.

### Run B35 Full Benchmark Results (129 Tasks at Concurrency 15)
- **Scorecard**: **58 / 129 Resolved (44.96%)** across 15 concurrent Docker sandboxes in 47 minutes (avg 284s / task).
- **Repository Breakdown**:
  - `psf/requests`: 8 / 13 (61.54%) — Strongest performer across synchronous HTTP and URL adapter defects.
  - `fastapi/fastapi`: 32 / 67 (47.76%) — Solid performance on core routing, dependency injection, and query parsing.
  - `Textualize/rich`: 18 / 48 (37.50%) — Significant bottleneck driven by character-exact ANSI rendering and whitespace assertions.
  - `encode/httpx`: 0 / 1 (0.00%) — Single defect failed due to missing `httpx.Stream` top-level module export.
- **Integrity Milestone**: **0% Test Tampering** across all 124 submitted patches (100% adherence to Rule #1 test-file immutability; zero patches discarded in Container B).
- **Forensic Failure Taxonomy (71 Unresolved Tasks)**:
  - *Pytest Assertion & Formatting Mismatches (46 tasks / 64.8%)*: 27 in `rich` where subtle ANSI escape resets, box border characters, or trailing space padding differed; 16 in `fastapi` on error response JSON shapes.
  - *Collection & Import Breakages / Exit Code 2 (8 tasks / 11.3%)*: Unclosed syntax (`fastapi_14482`), missing module exports (`httpx_3672`), wrong new file name (`fastapi_15661`), or circular imports (`fastapi_15785`).
  - *Phantom ADK Exec Wrapper Contamination (73 / 129 tasks affected)*: Discovered that `fast-grep` matched `.adk_exec_<hash>.py` wrapper scripts generated in the workspace root, reporting the agent's own search query in `sys.argv` as top-ranked code scopes.
  - *ADK Sandbox JSON Delimiter Crashes (4 tasks / 5.6%)*: Unescaped quotes in multi-line python test code strings passed into `repro-check` caused unhandled `JSONDecodeError: Expecting ',' delimiter` inside ADK.
  - *Tool Budget Cap (50 calls) Exhausted (3 tasks / 4.2%)*: Agents got trapped in exploratory loops between `fast-grep` and `repro-check`.
  - *Required Test Node Skipped [Exit Code 0] (2 tasks / 2.8%)*: In `fastapi_14605` and `fastapi_14583`, pytest passed but the required test node was skipped due to Pydantic v1 deprecation warnings, failing the harness requirement.

### Orchestrated Architecture & Harness Upgrades
- **Evaluation Concurrency Scaled to 30**:
  - Configured `SWEGEMMA_CONCURRENCY=30` default factory in `scripts/run_eval.py` and exported `SWEGEMMA_CONCURRENCY="${SWEGEMMA_CONCURRENCY:-30}"` in `start.sh` for high-throughput 30-sandbox parallel execution.
- **Skill Isolation & Phantom ADK Filter (`projects-1he`)**:
  - Completely blacklisted `.adk_exec*` and `.adk_exec_*.py` across `fast-grep`, `repo-map`, `code-graph`, and `diff-inspect` (in both root and `scripts/` directories).
  - Added `:(exclude)*.adk_exec*` pathspecs to all `git grep`, `git ls-files`, and `git status` calls to prevent self-referential search pollution.
- **System Prompt Hardening (`my_submission/prompts/main.md`, `projects-4kh`)**:
  - *Compact 3–5 Line Anchors*: Mandated small 2–4 line unique context anchors for `edit_file` to eliminate the 22.1% edit mismatch failure rate.
  - *Mandatory Pre-Submit Smoke Check*: Required running `syntax-guard` or import checks before `submit_patch()` to eliminate Exit Code 2 collection breakages.
  - *Safe JSON Delimiter Hygiene*: Instructed safe quote escaping and concise single-line strings in `repro-check` arguments to prevent ADK JSON parser crashes.
  - *Precision Rendering Invariance*: Added explicit rendering heuristics protecting whitespace, column widths, and ANSI styling sequences in formatting libraries.

## [Unreleased] - 2026-10-01 (Run B34 Post-Mortem & Prompt Hardening: 14-Task Gauntlet)

### Run B34 Evaluation Results (14 Tasks at Concurrency 8)
- **Scorecard**: **9 / 14 Resolved (64.29%)** across 8 concurrent Docker sandboxes with 0 container leaks or port deadlocks.
- **Repository Breakdown**:
  - `psf/requests`: 3 / 4 (75.0%) — `requests_6589`, `requests_7328`, `requests_7433` resolved.
  - `fastapi/fastapi`: 4 / 6 (66.7%) — `fastapi_5077`, `fastapi_14786`, `fastapi_14794`, `fastapi_14986` resolved.
  - `Textualize/rich`: 2 / 4 (50.0%) — `rich_3278`, `rich_4077` resolved.
- **Forensic Failure Analysis (5 Tasks)**:
  - `requests_7315`: Solved 100% correctly in `src/requests/adapters.py`, but agent modified `tests/test_adapters.py`, causing `git apply` collision in Container B (`test_patch` rejected with `does not match index`).
  - `fastapi_14258`: Correct file, method, and condition identified, but raised `RuntimeError` instead of framework-standard `AssertionError`, failing `pytest.raises(AssertionError)`.
  - `rich_4076`: Replaced `splitlines()` with `split("\n")` in `rich/ansi.py`, mishandling trailing newline and empty string boundary conditions.
  - `fastapi_15588` & `rich_3894`: Crashed by unhandled `json.decoder.JSONDecodeError` inside Google ADK / LiteLLM `lite_llm.py:1730` (`json.loads(tool_call.function.arguments)`), triggered by unescaped characters in multi-line tool arguments.

### Prompt Hardening (`my_submission/prompts/main.md`)
- **Absolute Test File Immutability**:
  - Enforced strict prohibition against editing, writing, or modifying any test file (`tests/*`, `test_*.py`, `conftest.py`).
  - Explained the mechanism: Container B applies the oracle test patch on top of pristine tests; modifying test files causes git patch collisions and an immediate 0% score.
  - Added mandatory zero-test-files audit in `diff-inspect` before `submit_patch()`.
- **Strict JSON Argument Hygiene & Escape Safety**:
  - Added explicit instructions for compact, valid JSON arguments in tool calls.
  - Prohibited complex multi-line blocks with nested triple quotes or unescaped control characters in `repro-check` to eliminate unhandled ADK parser crashes.
- **Framework-Native Assertion Idioms**:
  - Instructed agents that internal routing integrity and configuration checks in FastAPI/Starlette standardly use `assert <condition>, "<informative message>"` rather than `raise RuntimeError(...)`.
- **String Splitting & Newline Delimiter Preservation**:
  - Warned against naive `split("\n")` which introduces spurious trailing empty elements; instructed use of `splitlines(keepends=True)` or explicit delimiter handling.

## [Unreleased] - 2026-10-01 (Run B34 Prep: 14-Task Expanded Gauntlet Evaluation)

### Benchmark Expansion & Archetypal Coverage (`test.txt`, `tests.txt`, `docs/research/05-gauntlet-suite.md`)
- **Expanded Gauntlet Suite from 8 to 14 Vetted Tasks**:
  - Maintained the original 8 core anchor tasks (`rich_4076`, `requests_6589`, `requests_7328`, `fastapi_15588`, `rich_4077`, `fastapi_14986`, `fastapi_14794`, `fastapi_14786`).
  - Added 6 new vetted tasks from the exact same defect archetypes, pre-screened to avoid zero-spec documentation PR traps, external dead links, and flaky environments:
    - **`rich_3278`**: Strip problematic private ANSI escape sequences (`re_ansi` in `rich/ansi.py`).
    - **`rich_3894`**: Handle unusual `__qualname__` types during object introspection (`rich/_inspect.py`).
    - **`requests_7315`**: Preserve leading slashes in request `path_url` for S3 presigned URLs (`src/requests/adapters.py`).
    - **`requests_7433`**: Stream detection in `prepare_body` for `__getattr__`-based file wrappers (`src/requests/models.py`).
    - **`fastapi_14258`**: Prevent recursive `APIRouter` self-inclusion with clear `AssertionError` (`fastapi/routing.py`).
    - **`fastapi_5077`**: Support wrapped functions (`@functools.wraps`) with forward references in `get_typed_signature` (`fastapi/dependencies/utils.py`).
  - All 14 tasks verified with complete snapshots (`snapshots/*.tgz`), code graphs (`graphs/*.json`), embeddings (`embeddings/*.npz`), and 100% green hermetic Container B test runs.
  - Retained all 129 ground-truth task definitions in `tasks.jsonl`.
  - Configured evaluation runner concurrency at 8.

## [Unreleased] - 2026-10-01 (Run B33 Post-Mortem: OWASP Security Hardening & Gauntlet Realism)

### Web Security & Serialization Hardening (`my_submission/prompts/main.md`)
- **OWASP HTML-Safe JSON Serialization**:
  - Injected standard OWASP/Python web security guidelines into Section 6 for serializing JSON data inside HTML `<script>` tags, HTML attributes, and web UI templates (Swagger UI, ReDoc, OpenAPI dashboards).
  - Explicitly instructs escaping `<`, `>`, and `&` to unicode escape sequences:
    `json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")`
  - Explains the dual necessity: prevents `<script>` breakout and XSS injection (such as `<img src=x onerror=alert(1)>`) without corrupting or breaking client-side JavaScript `JSON.parse()`.
  - Warns against naive partial replacements (like `.replace("</", "<\\/")`).
- **Surgical Encoder Discipline**:
  - Instructs agents to resolve serialization security issues at the data serialization helper layer rather than generating massive 150-line diffs with blanket attribute escaping or importing external markup libraries.

### Gauntlet Curation & Benchmark Integrity (`test.txt`, `tests.txt`, `docs/research/05-gauntlet-suite.md`)
- **Swapped Zero-Spec Doc Trap `fastapi_15023` for Realistic Bugfix `fastapi_14794`**:
  - Removed `fastapi_15023` (an ambiguous documentation PR that repeated a 1-sentence title twice with 0 issue body and burned 47 tool calls searching across 450 tutorial files) from the active 8-task gauntlet.
  - Replaced with **`fastapi_14794`** ("Allow `Response` type hint as dependency annotation", Fixes #10127, resolving `AssertionError: Cannot specify Depends for type Response` in `analyze_param`).
  - Updated `docs/research/05-gauntlet-suite.md` Matrix Overview and Category 4 specification.
  - Preserved `tasks.jsonl` with all 129 tasks 100% intact.

## [Unreleased] - 2026-10-01 (Run B32 Post-Mortem: Gauntlet De-Noising & Precision Tuning)

### Gauntlet Curation & Benchmark Integrity
- **Swapped Unsolvable `fastapi_15661` for Clean RFC 6750 Bugfix `fastapi_14786` (`test.txt`, `tests.txt`)**:
  - Eliminated `fastapi_15661` (a zero-specification PR linking to an unreachable external URL that burned 49 tool calls guessing 7 unseen symbol names) from the active 8-task gauntlet.
  - Replaced with `fastapi_14786` ("Strip whitespaces from `Authorization` header credentials" per RFC 6750) — a well-specified, concrete, solvable bugfix.
  - Preserved `tasks.jsonl` with all 129 tasks intact.

### Prompt Hygiene & Token Efficiency (`my_submission/prompts/main.md`)
- **Purged Ad-Hoc Export-Aliasing Bloat**:
  - Deleted the `NEW SCRIPT EXPORT ALIASING` rule from Section 7, which was added solely to chase `fastapi_15661` and wasted input tokens on every turn.
- **Composite Exception Phrasing**:
  - Updated Section 6 exception guidelines to use composite phrasing (`constraint description + specific condition`, e.g. `raise ValueError(f"SSE '{field_name!s}' must be a single line: must not contain newlines or null characters")`) so that both rigid test regexes (`match="must be a single line"`) and style conventions match reliably.
- **Low-Level Parser/Decoder Search Discipline**:
  - Added explicit guidance to Section 3 instructing the agent to search for low-level ingestion/decoding functions (`from_ansi`, `decode`, `read_image`) when issues describe behavior, rather than editing high-level renderers (`__rich_console__`).

### Tool Hardening (`my_submission/skills/fast-grep/`)
- **Definition-First Match Ranking (`grep.py`)**:
  - Added a dedicated definition bonus (+60 for signatures, +75 for exact target symbol matches, +50 for substrings) to boost `def `, `async def `, and `class ` lines to the very top of search results.
  - In `rich_4076`, `def from_ansi` now ranks as #1 with a score of +310, preventing the agent from overlooking target functions due to high-volume call sites.
  - Maintained byte-for-byte synchronization between `grep.py` and `scripts/grep.py`.

### Environment Compatibility (`/tmp/brun/venv`)
- **Resolved Host Python 3.14 Port `-1` Crash in Werkzeug**:
  - Handled `ValueError` from Python 3.14's `urllib.parse` in `werkzeug/urls.py` when parsing negative ports, allowing `requests_6589` tests (`test_redirecting_to_bad_url`) to cleanly receive the redirect and pass `InvalidURL` assertions.
  - Verified `requests_6589` passes all 322 tests with exit code 0 in 31.28s.

## [Unreleased] - 2026-10-01 (Run B31 Post-Mortem & Gauntlet Hardening)

### Fixed & Hardened (Blast-Radius Smart-Blast Defusal)
- **Defused False-Green Pre-Fix Conflict Verdict (`my_submission/skills/blast-radius/`)**:
  - Eliminated the dangerous `GATE PASSED (PRE-FIX BASELINE CONFLICT DETECTED)` auto-pass logic that previously set `passed = True` when direct unit tests failed.
  - Now strictly sets `passed = False` and `status = "FAILED_DIRECT_TESTS_SUSPECTED_CONFLICT"` with an advisory warning whenever direct tests fail, preventing agents from prematurely submitting bad patches on incorrect files (e.g. `rich_4076`).
  - Maintained byte-for-byte synchronization between `test_blast.py` and `scripts/test_blast.py`.
  - Updated `SKILL.md` to document strict non-passing status for direct test failures.

### Fixed & Verified (Evaluation Environment & Test Harness)
- **Resolved Requests Test Fixture Crash (`/tmp/brun/venv`)**:
  - Installed `pytest-httpbin` (v2.1.0) and `httpbin` (v0.10.4) into `/tmp/brun/venv`.
  - Resolved `recursive dependency involving fixture 'httpbin' detected` which previously caused 187 setup errors in `tests/test_requests.py`.
  - Directly verified on `requests_6589` snapshot: test now passes cleanly in 0.69s with exit code 0, recovering `requests_6589` into a verified resolved task.

### Prompt Hardening (`my_submission/prompts/main.md`)
- **FastAPI `docs_src` Invariant**:
  - Clarified that in FastAPI, issue titles referencing "Update docs..." target executable tutorial Python code in `docs_src/**/*.py` (tested by `tests/test_tutorial/`), never English markdown files in `docs/en/docs/*.md`.
- **Exception Message Conformance**:
  - Instructed the agent to inspect nearby exception conventions and mirror exact phrasing style to satisfy rigid test regexes (e.g. `fastapi_15588`).
- **New Script Export Aliasing**:
  - Required exporting both common naming variants for constants and functions (e.g. `RELEASE_NOTES_HEADER = LATEST_CHANGES_HEADER = ...`) when writing new modules (e.g. `fastapi_15661`).
- **PR Text Disambiguation**:
  - Required distinguishing between an author's aspirational future wishes and the required minimal non-breaking fix.

### Concurrency & Performance
- **Concurrency Scaled to 8 (`scripts/run_eval.py`)**:
  - Verified 8 parallel task evaluations across isolated containers with 0 Docker crashes and 0 LiteRouter 429 timeouts, completing the 8-Task Gauntlet in ~7 minutes wall-clock time.

## [Unreleased] - 2026-10-01 (Run B29 Post-Mortem & Anti-Runaway Hardening)

### Model Swap (Frontier Model Restoration)
- **Swapped Evaluation Model Back to Frontier `stealth/space-bunny-alpha`**:
  - Replaced `thinkingmachines/inkling-small:free` with `stealth/space-bunny-alpha` across `scripts/run_eval.py`, `scripts/preflight_check.py`, and `scripts/test_agents_diagnostic.py`.
  - Swapped out the reasoning/thinking model in favor of the frontier model with superior native function calling, instruction following, and tool-use precision.
  - Updated `scripts/test_agents_diagnostic.py` to gracefully handle lean monolith architectures without subagents.

### Fixed & Hardened (Token Runaway Elimination & Context Hygiene)
- **Fast-Grep Context Protection (`my_submission/skills/fast-grep/`)**:
  - Expanded `SKIP_DIRS` with `benchmarks`, `benchmark`, `results`, `docs`, `doc`, `htmlcov`, `site-packages` to prevent scanning noisy benchmark results and documentation trees.
  - Expanded `SKIP_EXTENSIONS` with non-code and data formats: `.json`, `.csv`, `.log`, `.xml`, `.txt`, `.yaml`, `.yml`, `.md`, `.rst`.
  - Prevents raw JSON dumps (such as 110 benchmark result files on numeric searches) from polluting agent context and confusing function-calling parsers.
  - Mirrored byte-for-byte between `grep.py` and `scripts/grep.py`.
- **Sampling Generation Ceiling (`my_submission/configs/sampling.yaml`)**:
  - Capped `max_output_tokens` from 16,384 to 4,096 tokens as an aggressive circuit breaker.
  - Retained `thinking_budget: 4096` and `temperature: 0.15` while preventing multi-minute 16K runaway loops on repetition attractors.
- **Tool Calling Interface Defense (`my_submission/prompts/main.md`)**:
  - Hardened Section 1 with a strict negative constraint forbidding inline JSON tool representations (`{"name": "...", "args": ...}`) or pseudo-code function calls in conversational text.
  - Clarified that tool calls must only be executed through the environment's native structured tool-calling interface, and that textual JSON leaks will be treated as wasted turns without execution.

## [Unreleased] - 2026-10-01 (Model- & Test-Agnostic Sanitization Pass)

### Removed & Sanitized (Zero Task Leakage / Anti-Overfitting Gate)
- **Prompt Sanitization (`my_submission/prompts/main.md`)**:
  - Completely purged task-specific string splitting and delimiter logic (`re.split`, `rstrip("\r\n")`, `.splitlines()`, `if line == "": continue`).
  - Replaced Section 6 with universal **Boundary & Edge-Case Engineering Principles**: reasoning about degenerate inputs (empty values, null, 0, single elements, boundary delimiters), respecting container and sequence contracts, and prohibiting ad-hoc element suppression filters.
  - Retained the general SWE-bench distinction between True Regressions (unhandled exceptions, distance-1 consumer failures) and Pre-Fix Test Conflicts (baseline tests asserting pre-fix behavior) without citing specific variable names or string snippets.
- **Diagnostic Tool Neutralization (`my_submission/skills/repro-check/`)**:
  - Removed all hardcoded string splitting and newline heuristics from `check.py`.
  - Replaced with neutral, task-agnostic structural diff diagnostics (boundary mismatch, line count differences, suffix/whitespace differences).
  - Maintained byte-for-byte synchronization with `scripts/check.py`.
- **Advisory Generalization (`my_submission/skills/blast-radius/`)**:
  - Purged specific examples (`such as if line == "": continue`, `preserving trailing newlines/tokens`) from `PREFIX_CONFLICT_ADVISORY` in `test_blast.py`.
  - Generalized advisory to advise that unpatched baseline unit tests in Container A may assert pre-fix behavior, cautioning against ad-hoc suppressions if consumer tests pass and the change directly aligns with the issue requirements.
  - Maintained byte-for-byte synchronization with `scripts/test_blast.py`.

## [Unreleased] - 2026-10-01 (Run B28 Post-Mortem)

### Fixed & Hardened (First-Principles Pre-Fix Test Conflict Handling)
- **True Regressions vs Pre-Fix Test Conflicts (`my_submission/prompts/main.md`)**:
  - Distinguished between True Regressions (unhandled exceptions, crashes, distance-1 consumer failures) and Pre-Fix Test Assertion Conflicts (where unpatched baseline unit tests assert old, pre-fix buggy behavior that the issue explicitly asked to change).
  - Enforced Anti-Suppression Rule: strictly forbids adding suppression hacks (such as `if line == "": continue`) or reverting when distance-1 consumer tests pass and the unit test difference matches the intended bug fix.
  - Updated Section 8 `blast-radius` submission gate to unblock patch submission when the only mismatch is a pre-fix unit test expecting the old omitted/stripped behavior.
- **Pre-Fix Test Conflict Advisory in Regression Triage (`my_submission/skills/blast-radius/`)**:
  - Enhanced `test_blast.py` to identify when an assertion failure occurs on the direct unit test of the modified file and emit `💡 PRE-FIX TEST CONFLICT ADVISORY` to prevent the agent from destroying its fix.
  - Mirrored byte-for-byte between `test_blast.py` and `scripts/test_blast.py`.
- **Empty Line Anti-Suppression Guidance (`my_submission/skills/repro-check/`)**:
  - Enhanced `check.py` to explicitly warn against adding `if line == "": continue` during lookbehind regex splitting (`re.split(r"(?<=\n)", text)`), reminding that empty string chunks are necessary representations of empty lines.
  - Mirrored byte-for-byte between `check.py` and `scripts/check.py`.

## [Unreleased] - 2026-10-01 (Run B26 Post-Mortem)

### Fixed & Hardened (Run B26 Post-Mortem: Anti-Chaining, Lookbehind Delimiter Semantics & Continuation Defense)
- **Prompt Anti-Chaining & Single-Tool Protocol (`my_submission/prompts/main.md`)**:
  - Enforced strict `EXACTLY ONE TOOL CALL PER TURN` rule, explicitly forbidding batching, chaining, or concatenating multiple tool JSONs in a single response. Eliminates the 3x 16,384-token runaway loops observed in Run B26.
  - Updated Turn 1 search discipline: call either `search_similar_code` OR `fast-grep` on Turn 1 (never both at once).
  - Added lookbehind delimiter semantics in Section 6: clarified that `re.split(r"(?<=\n)", text)` retains the trailing delimiter on each chunk (`['foo\n', '']`), mandating `chunk.rstrip("\r\n")` to prevent doubled newlines (`\n\n`) when joined.
  - Added Continuation Nudge Defense in Section 8: strictly forbids calling `submit_patch()` upon receiving a harness continuation nudge unless `blast-radius` has verified 0 regressions on disk.
- **Lookbehind Delimiter Stripping Hints (`my_submission/skills/repro-check/`)**:
  - Enhanced string diff remediation hints in `check.py` and `scripts/check.py` to explicitly remind agents that `re.split(r"(?<=\n)", text)` chunks must be stripped via `chunk.rstrip('\n')` before line joining.
  - Mirrored byte-for-byte between `check.py` and `scripts/check.py`.
- **Lookbehind Delimiter Stripping Hints (`my_submission/skills/blast-radius/`)**:
  - Enhanced boundary failure remediation in `test_blast.py` and `scripts/test_blast.py` to instruct stripping trailing delimiters when handling lookbehind splits.
  - Mirrored byte-for-byte between `test_blast.py` and `scripts/test_blast.py`.
- **Synchronization & Validation (`my_submission/skills/diff-inspect/`)**:
  - Verified `diff.py` and `scripts/diff.py` byte-for-byte parity and clean Pydantic v2 JSON serialization under multi-file diffs.

## [Unreleased] - 2026-09-30

### Fixed & Hardened (Run B25 Post-Mortem & Multi-File / read_file Hardening)
- **Prompt Negative Priming Removal & Single-File Barrier (`my_submission/prompts/main.md`)**:
  - Removed negative example `Calling start_line=700, end_line=30...` that caused the LLM to burn 18 tool calls (36% of budget) repeating `start_line > end_line` errors.
  - Instructed omitting `end_line` (tool automatically reads 150 lines safely from `start_line`) or calculating `start_line + 40`.
  - Added Single-File Edit Barrier: strictly forbid modifying a second file until `blast-radius` passes on the first; mandate immediate rollback on regression.
  - Added Mandatory `blast-radius` gate before calling `diff-inspect` or `submit_patch`.
  - Added Boundary Testing & Python string splitting guidance: documented that `splitlines(True)` drops trailing empty tokens, recommending `re.split(r"(?<=\n)", text)`.
- **Multi-File Contamination Warning (`my_submission/skills/diff-inspect/`)**:
  - Added `MULTI_FILE_CONTAMINATION` warning when `total_files_modified > 1`, advising on reverting secondary edits.
  - Mirrored identically between `diff.py` and `scripts/diff.py`.
- **Trailing Newline & Boundary Remediation Hints (`my_submission/skills/repro-check/`)**:
  - Added deterministic remediation hints when strings differ by trailing newlines or empty boundaries (`""` vs `"\n"`), advising on `re.split(r"(?<=\n)", text)` vs `splitlines(True)`.
  - Mirrored identically between `check.py` and `scripts/check.py`.
- **Multi-File Diff Detection & Boundary Triage (`my_submission/skills/blast-radius/`)**:
  - Added workspace-wide multi-file diff detection and cautionary banner.
  - Added boundary assertion failure diagnostics explaining collapsed empty lines or stripped trailing newlines.
  - Mirrored identically between `test_blast.py` and `scripts/test_blast.py`.

### Added & Hardened (Deterministic Explanatory Diagnostics Overhaul across all 6 Skills)
- **`repro-check` (`my_submission/skills/repro-check/`)**:
  - Implemented AST assertion introspection via `__repro_assert__` and bytecode frame examination.
  - Extracts `actual` and `expected` values with raw escape codes (`\n`, `\r\n`, spaces) and lengths.
  - Computes character-level `ndiff` and unified diffs showing exact mismatch locations.
  - Generates plain-English diagnostic explanations (e.g., `MISMATCH: Actual string ('hello', 5 chars) is missing trailing '\n' present in Expected string ('hello\n', 6 chars)`).
  - Introspects and dumps all local variables in the failing scope with lengths and types.
  - 100% Pydantic v2 schemas (`AssertionDiagnostic`, `VariableInfo`, `DiagnosticReport`, `ReproCheckOutput`).
- **`blast-radius` (`my_submission/skills/blast-radius/`)**:
  - Full pytest failure block parsing with `-vv --tb=short`, eliminating 1-line truncation.
  - Extracts exact failing assertions, comparisons, line numbers, and captured stdout/stderr.
  - Deterministic regression root cause diagnosis (e.g. unexpected extra trailing newlines/whitespace, truncated strings, exception types).
  - Modified repo file & AST symbol correlation: directly links failing tests to modified repository files.
  - Groups common failures caused by shared underlying regressions across multiple tests.
  - 100% Pydantic v2 schemas (`TestFailureDetail`, `FailureDiagnosis`, `BlastRadiusResult`).
- **`fast-grep` (`my_submission/skills/fast-grep/`)**:
  - Deterministic zero-match diagnostics reporting total searchable files across `/workspace`.
  - Automatic case-insensitive fallback search: immediately reports matches when case is ignored.
  - AST identifier fuzzy candidate suggestions: recommends top 5 closest symbols via sequence similarity matching.
  - Plain-English regex syntax diagnostics: catches `re.error`, explains syntax issues, and suggests safe escaped patterns.
  - 100% Pydantic v2 schemas (`FastGrepResult`, `MatchExplanation`, `FuzzySuggestion`, `RegexErrorDiagnostic`).
- **`diff-inspect` (`my_submission/skills/diff-inspect/`)**:
  - Deterministic empty-diff explanation: warns when working tree is clean relative to baseline HEAD.
  - Untracked scratch file scanner: detects dangerous temporary scripts in `/workspace` (`repro.py`, `scratch*.py`, `tmp*.py`) that would pollute the official git patch, blocking submission and advising cleanup.
  - File-by-file line additions/deletions stats and forbidden harness file warnings (`pytest.ini`, `conftest.py`).
  - 100% Pydantic v2 schemas (`DiffWarning`, `FileDiffStat`, `DiffInspectResult`).
- **`repo-map` (`my_submission/skills/repo-map/`)**:
  - Missing path diagnosis: explains why path is missing and recommends closest fuzzy directories and files.
  - Top-level repository layout overview rendered when paths are missing.
  - AST `SyntaxError` and `IndentationError` diagnostics with line, column, and visual caret pointers.
  - 100% Pydantic v2 schemas (`MapDiagnostic`, `SymbolItem`, `ModuleSummary`, `RepoMapResult`).
- **`code-graph` (`my_submission/skills/code-graph/`)**:
  - Missing symbol explanation across graph topology and live AST scanning.
  - Fuzzy symbol ranking: suggests top 5 closest symbol names with similarity scores.
  - Specialized inspection hints for internal/private symbols (`_`) and dotted imports (`.`).
  - Caller/callee reachability diagnostics reporting inbound callers and outbound callees.
  - 100% Pydantic v2 schemas (`CodeGraphResult`, `ReferenceDetail`, `SymbolSuggestion`, `CallerCalleeConnection`).
- **Sampling Budget (`my_submission/configs/sampling.yaml`)**:
  - Set `max_output_tokens: 16384` and `thinking_budget: 4096` to eliminate mid-thought tool truncation on thinking models.

### Fixed & Hardened (Run B20 Post-Mortem & Model Migration)
- **Model Migration (`scripts/`)**:
  - Swapped default evaluation model from `stealth/space-bunny-alpha` to `thinkingmachines/inkling-small:free` across `scripts/run_eval.py`, `scripts/preflight_check.py`, and `scripts/test_agents_diagnostic.py`.
  - Verified 0 remaining references to `space-bunny-alpha` and confirmed clean live connection to LiteRouter.
- **Probe Budget Limiter & Circuit Breaker (`my_submission/skills/repro-check/`)**:
  - Added active probe execution tracking via `/tmp/.swegemma_repro_probe_count`.
  - Implemented circuit breaker: triggers warning after 2 exploratory probes without assertion failure or defect reproduction, forcing the model to cease open-ended probing and formulate an edit.
  - Automatic counter reset to 0 upon defect confirmation (`AssertionError` / runtime exception) or successful verification (`✅ PASSED`).
  - Mirrored identically between `my_submission/skills/repro-check/scripts/check.py` and `my_submission/skills/repro-check/check.py`, and updated `SKILL.md`.
- **Terse Issue Search & String/Buffer Verb Expansion (`my_submission/skills/fast-grep/`)**:
  - Enhanced `score_match` with dedicated boosts for string/buffer transformation methods (`splitlines`, `split`, `rstrip`, `strip`, `lstrip`, `replace`, `join`, `partition`, `decode`, `encode`, `from_ansi`).
  - Added buffer receiver detection (`terminal_text`, `buffer`, `text`, `line`) boosting method call-sites (+40) and receivers (+30).
  - Added visual call-site tags (`[CALL-SITE: string/buffer transform]`) and scope headers in AST search results.
  - Added heuristic expansion of terse keywords (e.g., `newlines`, `whitespace`) into core Python string operations to avoid comment/docstring spam.
  - Verified on `snapshots/rich_4076.tgz`: `splitlines` search ranks `rich/ansi.py:135` as TOP 1.
  - Mirrored identically between `my_submission/skills/fast-grep/scripts/grep.py` and `my_submission/skills/fast-grep/grep.py`, and updated `SKILL.md`.
- **Prompt Operational Gates & Bounds Safety (`my_submission/prompts/main.md`)**:
  - **Pre-Submission Gate**: Strictly forbade calling `submit_patch()` if `files_changed == 0` or patch size is 0 bytes; mandated applying best surgical edit via `edit_file` before submitting under low-budget emergencies (`tool_calls_remaining <= 5` or `tool_calls_used >= 45`).
  - **Strict 2-Probe Cap**: Enforced maximum 2 exploratory probes before transitioning to code analysis and editing.
  - **Terse Issue Search Mandate**: Mandated decomposing short issue statements (<20 words) into core Python string/buffer operations and searching test suites.
  - **Bounds Safety & Offset Clamping**: Strictly forbade line number guessing past EOF, mandated `start_line < end_line`, and instructed relying directly on `fast-grep` function snippets over redundant `read_file` calls.

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
