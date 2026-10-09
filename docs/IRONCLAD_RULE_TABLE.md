# Ironclad Rule Table — machine-checkable constraints

Single source of truth for all 16 submission gates.
All 16 gates implemented in `scripts/check_submission.py` and verified by `scripts/baseline_gate.py`.
Origin is `HARNESS_README.md` unless marked PROJECT (derived in this repo).
Status: Fully implemented, unit-tested (99 tests in `tests/`), and actively enforced.
## Config values (`my_submission/configs/sampling.yaml`)

| key | rule | value now | gate / asserted today? |
|---|---|---|---|
| `max_output_tokens` | `<= 4096` — PROJECT: at 16384 prompt is starved vs `token_threshold 14336` | 4096 pass | `g_sampling_output_cap` (PASS) |
| `thinking_budget` | `>= 1` if present (0 rejected by ADK validator) | 2048 pass | `g_sampling_output_cap` (PASS) |
| `thinking_config.thinking_level` | key MUST BE ABSENT (README:149) | absent pass | `g_sampling_no_thinking_level` (PASS) |
| `include_thoughts` | must be boolean | true pass | `g_sampling_output_cap` (PASS) |
| `max_output_tokens + thinking_budget` | `<= 32768` (README:128,178) | 6144 <= 32768 pass | `g_sampling_output_cap` (PASS) |
| `temperature` | `>= 0.0` (README:151) | 0.15 pass | `g_sampling_output_cap` (PASS) |
| `top_p` | `0.0..1.0` (README:151) | 0.9 pass | `g_sampling_output_cap` (PASS) |

## Model identity (`my_submission/agent.yaml` + `sub_agents/*.yaml`)

| rule | source | value now | gate / asserted? |
|---|---|---|---|
| all `model:` values identical after provider-prefix strip | README:177,185 | single pass | `g_required_files` (PASS) |
| model in allowlist `{gemma-4-31b-it-qat-w4a16-ct}` | README:185 | pass | `g_adapter_base_model` / policy (PASS) |
| exactly one root config at zip root | README:72,97 | pass | `g_zip_root_layout` (PASS) |
| no `agent.py` anywhere | README:69 | pass | `g_disallowed_extensions` (PASS) |
| all advertised skill scripts exist | PROJECT | 23 scripts pass | `g_prompt_skill_scripts_exist` (PASS) |
| source files match locked 0.13 baseline | PROJECT | 14 files pass | `g_baseline_whitelist` (PASS) |

## Budgets (`my_submission/eval_config.yaml`)

| rule | source | value now | gate / asserted? |
|---|---|---|---|
| `timeout_seconds <= 300` | README:381 | 300 pass | `g_tool_budget_parity` (PASS) |
| `max_tool_calls >= 20` | README:371 | 40 pass | `g_tool_budget_parity` (PASS) |
| **every budget number in prompt prose matches `max_tool_calls`** | PROJECT | 40 == 40 pass | `g_tool_budget_parity` (PASS) |
| prompt turn ladder internally consistent | PROJECT | monotone ladder pass | `g_prompt_ladder_consistency` (PASS) |

## Tools

| rule | source | asserted? |
|---|---|---|
| tool names subset of the 9 permitted | README:30,365 | no |
| `read_file` 150 lines / 10K chars | README:436,547-548 | no |
| `max_stdout_chars = 5000` | README:382,546 | no |

## Adapters

| rule | source | value now | gate / asserted? |
|---|---|---|---|
| declared `adapter:` implies `adapters/<n>/adapter_model.safetensors` in zip | README:145,203 | none declared (pass) | `g_adapter_declared`, `g_adapter_present` (PASS) |
| adapter base model matches served model | README:204 | none declared (pass) | `g_adapter_base_model` (WARN policy) |
| `.safetensors` only, no `.bin`/`.pt`/`.pth` | README:145 | pass | `g_disallowed_extensions` (PASS) |

## Packaging / size (`submission.zip`)

| rule | source | value now | gate / asserted? |
|---|---|---|---|
| extension allowlist `.yaml .yml .md .txt .py .json .safetensors` | README:144 | all 14 files pass | `g_disallowed_extensions` (PASS) |
| `.DS_Store` / `._*` / `.pyc` / `__pycache__` count == 0 | CHANGELOG | 0 pass | `g_disallowed_extensions` (PASS) |
| **unpacked** size `< 3 GiB` | README:134 | 0.5 MB pass | `g_submission_size_unpacked` (PASS) |
| zip file set == directory file set, byte-identical (sha256) | PROJECT | 14/14 byte-identical | `g_zip_directory_drift` (PASS) |
| required files sit at archive root | README:72 | all at root pass | `g_zip_root_layout` (PASS) |
| historical run health | PROJECT | post-run check | `g_run_health` (NON-GATING) |
| no large embedded code literals in docs | PROJECT | doc hygiene check | `g_no_embedded_code_in_docs` (NON-GATING) |

## Kernel runtime (`scripts/build_kaggle_kernel.py`)

| rule | why | line | asserted? |
|---|---|---|---|
| `MODEL_PATH.exists()` asserted, not printed | silent wrong-model | :153-157 | no |
| `/health` + `/v1/models` probed before eval | unready server | — | **absent entirely** |
| warm-up completion, assert `completion_tokens > 0` | 0/129 would be caught | — | **absent entirely** |
| adapter manifest printed + `enable_lora` asserted | silent base model | no step | **absent entirely** |
| `litellm.drop_params` False, or dropped list reported | silent param discard | :149 | no |
| per-task exception persisted to `task_results.jsonl` | swallowed by `except Exception` | :288 | no |
| `kernel_health.json` written | no machine-readable health | — | **absent entirely** |
