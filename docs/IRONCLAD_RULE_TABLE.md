# Ironclad Rule Table — machine-checkable constraints

Single source of truth for G1/G2. Each row is an assertion a gate can make.
Origin is `HARNESS_README.md` unless marked PROJECT (derived in this repo).
`?` = not currently asserted by any check in this repo.

## Config values (`my_submission/configs/sampling.yaml`)

| key | rule | value now | asserted today? |
|---|---|---|---|
| `max_output_tokens` | `<= 4096` — PROJECT: at 16384 prompt is starved vs `token_threshold 14336` | 16384 FAIL | no |
| `thinking_budget` | `>= 1` if present (0 rejected by ADK validator, CHANGELOG:21) | 4096 pass | no |
| `thinking_config.thinking_level` | key MUST BE ABSENT (README:149) | absent pass | no |
| `include_thoughts` | PROJECT: `false` per `gotcha-litellm-reasoning-effort-rejection` | true FAIL | no |
| `max_output_tokens + thinking_budget` | `<= 32768` (README:128,178) | 20480 pass | no |
| `temperature` | `>= 0.0` (README:151) | 0.15 pass | no |
| `top_p` | `0.0..1.0` (README:151) | 0.95 pass | no |

## Model identity (`my_submission/agent.yaml` + `sub_agents/*.yaml`)

| rule | source | value now | asserted? |
|---|---|---|---|
| all `model:` values identical after provider-prefix strip | README:177,185 | single pass | ? |
| model in allowlist `{gemma-4-31b-it-qat-w4a16-ct}` | README:185 | pass | no |
| exactly one root config at zip root | README:72,97 | pass | yes (G1) |
| no `agent.py` anywhere | README:69 | pass | ? |
| `agent_class` in 4 supported types | README:105-125 | pass | ? |
| `instruction` per agent `<= 1e6` chars, total `<= 1e7` | README:112,139 | ? | no |
| `max_agents <= 500`, `max_sub_agent_depth <= 50` | README:140-141 | ? | no |

## Budgets (`my_submission/eval_config.yaml`)

| rule | source | value now | asserted? |
|---|---|---|---|
| `timeout_seconds <= 300` | README:381 | 60 pass | no |
| `max_tool_calls >= 20` (else budget warning never fires) | README:371 | 40 pass | no |
| **every budget number stated in prompt prose `<=` `max_tool_calls`** | PROJECT — catches `main.md:59` saying 50 | 50 > 40 FAIL | no |
| keys subset of the 4 allowed under `evaluation:` | README:98,528 | pass | ? |

## Tools

| rule | source | asserted? |
|---|---|---|
| tool names subset of the 9 permitted | README:30,365 | no |
| `read_file` 150 lines / 10K chars | README:436,547-548 | no |
| `max_stdout_chars = 5000` | README:382,546 | no |

## Adapters

| rule | source | value now | asserted? |
|---|---|---|---|
| declared `adapter:` implies `adapters/<n>/adapter_model.safetensors` **in the zip** | README:145,203 | none declared | PARTIAL — dir/zip split |
| ~~adapter base must equal served model~~ | **RETRACTED (fabricated)** — see `SHARED_UNDERSTANDING.md:192` | never was a rule | n/a |
| `r <= 128` | README:169,204 | 8 pass | no |
| adapter count `<= 8` | README:169,204 | 0 pass | no |
| `.safetensors` only, no `.bin`/`.pt`/`.pth` | README:145 | pass | yes |

## Packaging / size (`submission.zip`)

| rule | source | value now | asserted? |
|---|---|---|---|
| extension allowlist `.yaml .yml .md .txt .py .json .safetensors` | README:144 | `.DS_Store` on disk FAIL | partial |
| `.DS_Store` / `._*` / `.pyc` / `__pycache__` count == 0 | CHANGELOG:12 | zip clean pass | yes |
| **unpacked** size `< 3 GiB` | README:134 | gate uses COMPRESSED — WRONG METRIC | FAIL (bug) |
| `max_file_count <= 10000` | README:135 | 19 pass | no |
| `max_yaml_files <= 1000`, YAML `<= 50 MiB`, skill dir `<= 50 MiB` | README:136-138 | pass | no |
| `!include` depth `<= 10`, no `..`, no abs path, no symlink escape, ext in `.md .txt .yaml .yml` | README:100-102 | pass | ? |
| zip file set == directory file set, byte-identical (sha256) | PROJECT — the missing drift check | unverifiable | **no** |
| `skills/<n>/<n>.py` == `skills/<n>/scripts/<n>.py` | PROJECT — dead-duplicate check | both exist | **no** |
| `compile_submission` runs on the zip, not the directory | PROJECT | runs on dir | **no** |

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
