# CONTEXT.md — Domain glossary for `gemma4`

Vocabulary for the Google Gemma 4 Developer Agent Kaggle submission harness in this repo.
Every term below is grounded in a file:line citation. `HARNESS_README.md` (671 lines) is the
harness source of truth (`AGENTS.md:6`); `scripts/gate_policy.yaml` is the gate-*value* source of
truth; `scripts/check_submission.py` owns gate names and categories. Items marked
**(not in `HARNESS_README.md`)** are real in this repo but documented elsewhere — cited to the file
that actually defines them.

---

## 1. The submission artifact

A submission is a **directory** packaged as `submission.zip`, consumed by `scripts/inference.py`
Stage 1 which emits `submission.parquet` (`HARNESS_README.md:72`). Layout
(`HARNESS_README.md:75-95`):

| Path | What it is |
| --- | --- |
| `agent.yaml` | **REQUIRED** root agent config; `agent.yml`, `root_agent.yaml`, `root_agent.yml` also accepted. Exactly one must exist — zero raises `MissingRootConfigError`, more than one raises `MultipleRootConfigsError` (`HARNESS_README.md:76`, `:97`). Ours: `my_submission/agent.yaml`. |
| `prompts/*.md` | System instructions, pulled in via the sandboxed `!include` directive — `.md`/`.txt` load as raw UTF-8 strings (`HARNESS_README.md:80-82`, `:99-100`). Ours: `prompts/main.md`. |
| `sub_agents/*.yaml` | Optional sub-agent or `AgentTool` configs (`HARNESS_README.md:83-84`); referenced as `{config_path: ...}` (`HARNESS_README.md:115`). Not present in `my_submission/` today. |
| `configs/*.yaml` | Optional generation parameters, loaded via `!include` (`HARNESS_README.md:78-79`). Ours: `configs/sampling.yaml`. |
| `skills/<name>/SKILL.md` | Optional ADK Skill directories, one `SKILL.md` each (`HARNESS_README.md:92-94`); attached to an agent by relative path under `skills:` (`HARNESS_README.md:114`, `my_submission/agent.yaml:11-15`). |
| `adapters/<name>/` | **Optional** PEFT LoRA adapters — `adapter_config.json` + `adapter_model.safetensors` (`HARNESS_README.md:85-91`, `:201-203`). **Not required** — see §8. Not present in `my_submission/` today. |
| `eval_config.yaml` | Optional per-task budget overrides under `evaluation:` — `timeout_seconds`, `max_tool_calls`, `max_time_minutes`, `max_turns` (`HARNESS_README.md:77`, `:98`, `:528-537`). Ours: `my_submission/eval_config.yaml`. |

**Declarative-only security model.** No `agent.py` / `agent_fn` is submitted. `adk-submission`
replaces ADK's `from_config()` with a sandboxed YAML compiler, `compile_submission`, resolving
everything against closed registries — `ToolRegistry`, `ModelRegistry`, `SkillRegistry`,
`CallbackRegistry` (`HARNESS_README.md:68-69`).

**`!include`** embeds external files in YAML: depth ≤ 10, cycle detection; absolute paths, null
bytes, `..` traversal, and escaping symlinks raise `PathTraversalError` (`HARNESS_README.md:99-102`).

**Hard size constraint.** Total unpacked submission `< 3 GiB` (`3,221,225,472` bytes), *including*
`adapters/` (`HARNESS_README.md:134`). Everything else in `SubmissionLimits` is a
runaway-recursion guard, not a competition rule (`HARNESS_README.md:128`).

**Single base model.** Every agent declares exactly one model, and under Kaggle scoring it must be
`gemma-4-31b-it-qat-w4a16-ct` (`HARNESS_README.md:183-185`; `scripts/gate_policy.yaml:6-9`).

---

## 2. Skills: `run_skill_script` and `SkillToolset`

**(not in `HARNESS_README.md`)** — grepping it for `run_skill_script`, `SkillToolset`, `skill_name`
returns zero hits. Real sources:

- **`SkillToolset`** is a Google ADK (1.36.1) experimental feature (`FeatureName.SKILL_TOOLSET`).
  Skills are managed *under* it and are **not** top-level tools in `tools_dict`
  (`.agents/skills/gcp-train/references/environment-package-traps.md:75-78`;
  `.agents/skills/kaggle-submit/SKILL.md:50-51`).
- **`run_skill_script`** is the ADK **meta-tool** that invokes a skill's script
  (`.agents/skills/kaggle-submit/SKILL.md:51`). Proven live: 34 real calls in
  `results/run_B40/logs/fastapi_11194.log`. ADK also exposes `list_skills`, `load_skill`,
  `load_skill_resource` (`kaggle-submit/SKILL.md:51`); this repo's prompt calls those a wasted tool
  call (`my_submission/prompts/main.md:15`).
- **Skills are NOT top-level tools.** Calling `fast-grep(...)` directly makes ADK raise
  `ValueError: Tool 'fast-grep' not found` and abort the turn (`kaggle-submit/SKILL.md:49-52`).

**The three real parameters** of a skill call (`kaggle-submit/SKILL.md:53`):

| Parameter | Type | Value here |
| --- | --- | --- |
| `skill_name` | string | `"fast-grep"`, `"code-map"`, … |
| `file_path` | string | script filename inside the skill dir, e.g. `"grep.py"` |
| `args` | list of strings | e.g. `["--symbol", "APIRouter"]` |

`script_name` is **not** a real parameter and yields a rejected payload (`kaggle-submit/SKILL.md:53`).

### The five shipped skills

Declared at `my_submission/agent.yaml:11-15`; each described by its own `SKILL.md:3`.

| Skill | Script | What it is for |
| --- | --- | --- |
| `fast-grep` | `grep.py` | Ranked AST-aware keyword/regex search across `/workspace`, with definition prioritization and clean code blocks for `edit_file`. |
| `code-map` | `map.py` | AST code structure, class hierarchies, symbol call-graph tracing via `--symbol` / `--file`. |
| `code-oracle` | `oracle.py` | Multi-domain oracle: Python expression eval, ANSI/hex inspection, terminal cell width, HTML escaping/tag balance, JSON Schema/OpenAPI validation, AST syntax check. |
| `repro-check` | `check.py` | Runs an isolated Python assertion with workspace `PYTHONPATH` to confirm the defect before editing and the fix after. |
| `test-gate` | `gate.py` | Consolidated gatekeeper: distance-1 neighbor regression tests, safe `git diff` viewer with test-file mutation assertions, and patch-readiness check. |

---

## 3. The nine harness tools

Registered by `SwegemmaContext.create_tools()` into `ToolRegistry`; an agent attaches any subset by
name under `tools:` (`HARNESS_README.md:365`; `AGENTS.md:11`).

| # | Tool | Billed? | Citation |
| --- | --- | --- | --- |
| 1 | `run_command(command)` | yes | `HARNESS_README.md:378` |
| 2 | `submit_patch()` | **no** | `HARNESS_README.md:398-400` |
| 3 | `get_status()` | **no** | `HARNESS_README.md:407-409` |
| 4 | `read_file(filepath, start_line, end_line)` | yes | `HARNESS_README.md:433` |
| 5 | `edit_file(filepath, old_string, new_string, allow_multiple)` | yes | `HARNESS_README.md:450` |
| 6 | `write_file(filepath, content)` | yes | `HARNESS_README.md:470` |
| 7 | `get_code_neighbors(node, edge_type, max_neighbors)` | yes | `HARNESS_README.md:484` |
| 8 | `search_similar_code(query, k)` | yes | `HARNESS_README.md:494` |
| 9 | `get_code_subgraph(nodes)` | yes | `HARNESS_README.md:508` |

"Free" means `@budget_gated(count_tool_call=False)` — it does not consume `tool_calls`. Tools 1–6
are workspace/execution tools (`HARNESS_README.md:376`, `:429`); tools 7–9 are code-intelligence
graph tools backed by pre-computed `.json` graphs and `.npz` embeddings
(`HARNESS_README.md:480-482`).

---

## 4. The two containers

Every task is evaluated in **two completely separate sandbox lifecycles** (`HARNESS_README.md:216`).

- **Container A — agent sandbox.** `/workspace` with snapshot extraction at `base_commit` (zero
  future git history), editable install, hermetic test config, and the `baseline` commit; the
  compiled ADK agent runs here and all nine tools execute here (`HARNESS_README.md:49`, `:225-235`).
- **Container B — verification sandbox.** A *fresh* `/workspace` repeating steps 1–5 (commit
  `eval_baseline`), then `agent_patch` is applied, `task.test_patch` applied, and hermetic `pytest`
  runs (`HARNESS_README.md:50`, `:238-241`, `:582`).

**Test-file edits are discarded in Container B.** `_is_protected_test_or_config_path` identifies
protected test files (`test_*.py`, `*_test.py`, `.py` under `tests/`, `test/`, `testing/`) and runner
configs (`conftest.py`, `pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg`, `*.pth`) touched by
`agent_patch`, and resets them with `git checkout HEAD -- <files>` + `git clean -f -- <files>` before
`task.test_patch` is applied (`HARNESS_README.md:590-593`). Any agent edit to a test file or runner
config **is discarded**; the fix must be to library code (`HARNESS_README.md:596-597`).

---

## 5. Patch

**The patch (`agent_patch`) is the git diff of the working tree in Container A**, produced by
`submit_patch()` or, if the agent never called it, by a harness fallback before teardown
(`HARNESS_README.md:569-570`, `:576-577`). `git add -N .` (`--intent-to-add`) is what makes new
untracked files appear in the diff alongside modifications (`HARNESS_README.md:575`).

> **Contradiction, reported not smoothed.** `AGENTS.md:12` and project shorthand say the patch is
> `git add -N . && git diff HEAD`. `HARNESS_README.md:572-573` actually specifies
> `git diff --binary _swegemma_baseline 2>/dev/null || git diff --binary HEAD`, preferring a
> `_swegemma_baseline` ref. The documented bootstrap commits are `baseline` (`HARNESS_README.md:238`)
> and `eval_baseline` (`:582`) — `_swegemma_baseline` is never introduced anywhere, so in practice
> the first branch always misses and it falls through to `git diff HEAD`. Use the project shorthand;
> cite `:572-573` when precision matters.

Practical corollary: scratch repro scripts left untracked in `/workspace` land in the patch — put
them in `/tmp` (`HARNESS_README.md:667`).

---

## 6. Resolution Rate and "resolved"

A task is **`resolved = True`** (`score = 1.0`) **if and only if** `pytest` exits `0` **and**
`_validate_junit_xml` confirms the report exists with `passed_tests > 0`, `failures == 0`,
`errors == 0`, and every required test node (`FAIL_TO_PASS`, `PASS_TO_PASS`, or test functions
extracted from `test_patch`) explicitly passed without being skipped
(`HARNESS_README.md:606-609`).

**Resolution Rate** is the competition metric returned by `score()` in `scripts/metric.py`:

$$\text{Resolution Rate} = \frac{\text{Resolved Tasks}}{\text{Total Tasks in the Evaluation Split}} \in [0.0, 1.0]$$

(`HARNESS_README.md:610-611`; the metric this project optimizes, `AGENTS.md:4`.)

`submit_patch()` returning success is **not** resolution — it only marks the patch submitted and
ends the agent loop (`HARNESS_README.md:401`). A patch that fails to apply in Container B scores
`resolved = False` outright (`HARNESS_README.md:589`).

---

## 7. Gates

`scripts/check_submission.py` registers 15 gates in `PRE_SUBMISSION_GATES` and 2 in
`POST_RUN_GATES`, concatenated into `ALL_GATES`. Threshold *values* live in
`scripts/gate_policy.yaml`, never in the checker.

**Gate categories** — exactly one per gate, asserted as a bijection at import time:

| Category | Meaning | Veto? |
| --- | --- | --- |
| `submission` | a FAIL is a real defect in the artifact being shipped | **YES** — sets exit 1 |
| `post_run` | a verdict about a historical run's health, not about this artifact | no — reported, labelled `NON-GATING` |
| `hygiene` | repository hygiene, irrelevant to the shipped artifact | no — reported, labelled `NON-GATING` |

**"Gating" means exactly this**: `partition_fails` splits FAILs into `(gating, non_gating)` by
category — a FAIL is gating only when its gate is in `submission`. WARN never affects the exit code
in any category. Selecting a non-`submission` category explicitly via `--category` makes its FAILs
exit non-zero too.

The two non-submission gates are `g_run_health` (post_run; detects a degenerate run and reports
`INFRASTRUCTURE FAILURE, NOT A QUALITY RESULT`) and `g_no_embedded_code_in_docs` (hygiene; lints
`docs/*.md`).

**Phase is a separate axis from category.** `--pre-pack` skips the zip-dependent gates, because
before a pack their verdict is about an absent artifact.

---

## 8. The two submission modes, and the adapter obligation

The vocabulary has exactly two modes, `submit` and `local_test` (`scripts/gate_policy.yaml:66-67`).
Precedence: `--mode` CLI flag > `GATE_SUBMISSION_MODE` env var > policy `adapter.submission_mode`.

**The adapter is OPTIONAL.** Every mention of `adapters/` is marked Optional
(`HARNESS_README.md:38`, `:85`, `:110`), and `:128`/`:134` impose only a 3 GiB unpacked-size
*ceiling* that an adapter must fit inside — a ceiling is not a presence requirement. `:201-203` are
if-used placement instructions, conditional on shipping one at all. An adapter-less submission is
therefore **valid**, and the gates do not veto it (`scripts/check_submission.py` `g_adapter_declared`,
`g_adapter_present`).

What the gates still enforce is **consistency**, in both modes:

| Situation | Verdict |
| --- | --- |
| No `adapter:` key declared, no `adapters/` dir | **PASS** — adapter is optional |
| `adapters/` present but empty | **PASS** — ships no adapter |
| `adapter:` declared with a **wrong** name (≠ policy `declared_name`) | **FAIL** — packaging defect |
| `adapters/` **populated** but containing no `adapter_model.safetensors` | **FAIL** — a broken adapter is worse than none |
| `local_test` mode with an `adapter:` key still declared | **FAIL** — the local path must not pretend to use an adapter it lacks |

Two obligations are *not* mode-scoped: `adapter.required_base_model` is **advisory only** —
`g_adapter_base_model` WARNs and never FAILs (`scripts/gate_policy.yaml:12-19`); and `thinking_level`
is a forbidden sampling key (`scripts/gate_policy.yaml:76-80`).

---

## 9. The two tracks

**Not from `HARNESS_README.md`** — the harness has no notion of "tracks". This is the project's
operational vocabulary from `AGENTS.md:31-33`:

- **Track 1 (declarative submission)** — lock in a verified `submission.zip` on the Kaggle
  leaderboard. Our `my_submission/` is the active Track 1 baseline: a declarative ADK agent with
  5 pre-installed skills.
- **Track 2 (LoRA adapter)** — train a Rank-8 LoRA and mount it as `adapter: main_lora`. Shape of a
  Track 2 tree is defined by `HARNESS_README.md:200-206`.

> **Measurement caveat.** The commonly-quoted baselines in this repo (43.4% / 45.7% / 64.9%) record
> `model_name: stealth/space-bunny-alpha`, a LiteRouter proxy — **not** the competition model
> (`docs/FINDINGS.md:21`, `:272-274`). Zero local runs have served
> `gemma-4-31b-it-qat-w4a16-ct`, so the true Gemma 4 Resolution Rate is **unknown and bounded above
> by 12/129**. Do not cite a proxy number as a capability measurement.

---

## 10. Naming cautions

- `edit` is not a tool; the tool is `edit_file` (`my_submission/prompts/main.md:16`).
- `script_name` is not a skill parameter; it is `file_path` (`.agents/skills/kaggle-submit/SKILL.md:53`).
- The container-setup identifiers are `baseline` (Container A HEAD) and `eval_baseline`
  (Container B HEAD); `_swegemma_baseline` appears in the diff command but is never defined.
- Do not write Python-call syntax to show a JSON tool call — not in prompts, and **not in the
  `--help`/usage strings that skill scripts print**. The 4-bit quantisation merges kwargs into JSON
  keys; the model copies whatever a tool just handed it.
