# SWE-Gemma / Gemma 4 Developer Agent: Master Architectural & Track 2 LoRA Review Packet

> **Canonical Ground Truth Notice**: This self-contained technical packet is synchronized 100% with
> `training/research_dossier/00_CONSULTANT_PROMPT.md` through `07_INTERNAL_RESEARCH_FINDINGS.md` and
> verified directly against the local competition checkpoint (`models/gemma-4-31b-it-qat-w4a16-ct/`),
> live submission artifacts (`submissions/track1_live/`), and scored Kaggle leaderboard traces.

---

## Section 1: Executive Context & Locked Architecture

### 1.1 Competition Runtime & Two-Container Evaluation Harness
- **Competition**: Kaggle `gemma-4-developer-agent` (129 Python software engineering tasks across
  `fastapi/fastapi` [67], `Textualize/rich` [48], `psf/requests` [13], and `encode/httpx` [1]).
- **Serving Runtime**: `google/gemma-4-31b-it-qat-w4a16-ct` served via vLLM (`tensor_parallel_size=4`,
  `max_model_len=32768`, `gpu_memory_utilization=0.90`) on 4x NVIDIA L4 GPUs (96 GB total VRAM).
- **Container A (Agent Sandbox)**: The Google ADK agent interacts with `/workspace` (checked-out repo at
  `base_commit`). When the agent finishes or calls `submit_patch`, the harness extracts the patch via:
  ```bash
  git add -N . && git diff HEAD
  ```
  Any untracked scratch file left in `/workspace` is swept into the patch diff and corrupts grading.
- **Container B (Isolated Grading Sandbox)**: Applies the extracted patch to a clean checkout, applies
  `test_patch` (which resets any agent edits to test files), and runs `FAIL_TO_PASS` and `PASS_TO_PASS`
  pytest targets. A task resolves (`resolved: true`) if and only if `test_exit_code == 0`.

### 1.2 Single-Agent Monolith & Task-Global Budget (`eval_config.yaml`)
- **Agent Topology (`submissions/track1_live/agent.yaml`)**: Single monolithic `LlmAgent` (`name: main`,
  `model: gemma-4-31b-it-qat-w4a16-ct`) with zero sub-agents.
- **Task-Global Budget (`submissions/track1_live/eval_config.yaml`)**:
  - `max_tool_calls: 40` (strictly global across the entire task; `get_status` and `submit_patch` are free).
  - `max_time_seconds: 270` (4.5 minutes per task wall-clock limit).
  - `max_llm_turns: 100`.
- **Sampling Configuration (`submissions/track1_live/configs/sampling.yaml`)**:
  - `temperature: 0.15`, `top_p: 0.9`, `max_output_tokens: 4096`, `thinking_budget: 2048`,
    `include_thoughts: true`.

### 1.3 Strictly 5 Direct Tools + 5 Pre-Installed Skills (`ZERO run_command`)
The production agent exposes **5 direct file/lifecycle tools** and **5 pre-installed structured skills**
invoked exclusively through the Google ADK `SkillToolset` meta-tool `run_skill_script`:

| Layer | Name | Invocation / File Path | Role & Safety Guarantees |
| :--- | :--- | :--- | :--- |
| **Direct Tool 1** | `read_file` | Native ADK tool | Line-windowed file inspection (`start_line`, `end_line`). |
| **Direct Tool 2** | `edit_file` | Native ADK tool | Surgical exact-string replacement on existing source files. |
| **Direct Tool 3** | `write_file` | Native ADK tool | Creation of brand-new files required by the issue. |
| **Direct Tool 4** | `get_status` | Native ADK tool (Free) | Inspects modified/untracked files in `/workspace`. |
| **Direct Tool 5** | `submit_patch` | Native ADK tool (Free) | Finalizes patch and terminates loop. |
| **Skill 1** | `fast-grep` | `run_skill_script` (`grep.py`) | Token/sliding-window code search. |
| **Skill 2** | `code-map` | `run_skill_script` (`map.py`) | AST call graph, outline, inheritance. |
| **Skill 3** | `code-oracle` | `run_skill_script` (`oracle.py`) | 2s evaluator (`--eval`, `--syntax`). |
| **Skill 4** | `repro-check` | `run_skill_script` (`check.py`) | Isolated `/tmp` runner (15s, 1GB RAM). |
| **Skill 5** | `test-gate` | `run_skill_script` (`gate.py`) | Distance-1 pytest & read-only diff. |

- **Withheld Tools by Design**: `run_command`, `get_code_neighbors`, `search_similar_code`, and
  `get_code_subgraph` are intentionally omitted from `agent.yaml`.
- **Empirical Proof of `run_skill_script`**: `run_skill_script` is a verified Google ADK `SkillToolset`
  meta-tool in the competition container (proven on real Gemma 4 cloud traces such as
  `cloud_results/results/traces/trace_fastapi_14962.json:36-60` and 4,196 invocations across `run_B39`).

---

## Section 2: Historical Score Provenance & Failure Forensics

### 2.1 Complete Leaderboard & Local Run Ledger

| Run / Ref ID | Date | Served Model | Adapter | Score | Forensic Summary |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ref `56883026`** | Oct 6 | `gemma-4-31b-it-qat-w4a16-ct` | None | **`0.13` LB** | Locked Track 1 baseline (`10e32ceb9b...`). |
| **Ref `56765397`** | Oct 2 | `gemma-4-31b-it-qat-w4a16-ct` | Rank-8 LoRA | **`0.03` LB** | Early pre-hardening tree (`667472e`). |
| **Ref `56810465`** | Oct 4 | `gemma-4-31b-it-qat-w4a16-ct` | 90MB BnB NF4 | **`0.00` LB** | BnB NF4 on `w4a16-ct` (`111/129` `tc=0`). |
| **Local `run_B39`** | Oct 4 | `stealth/space-bunny-alpha` | None | `56/129` (`43.4%`) | Proxy model (teacher trajectories only). |
| **Local `run_B40`** | Oct 5 | `stealth/space-bunny-alpha` | None | `50/77` (`64.9%`) | Proxy model on 77 Tier-1 subset. |

- **Ref `56883026` (`0.13` Public Leaderboard Score — Oct 6)**: Locked Track 1 adapter-less baseline
  (`submissions/track1_live/`, SHA-256 `10e32ceb9b...`). Uses 5 direct tools + 5 skills via
  `run_skill_script`, zero `run_command`, `temperature: 0.15, top_p: 0.9, max_output_tokens: 4096,
  thinking_budget: 2048, include_thoughts: true`. Outperforms `0.08`–`0.12` public starter baselines.
- **Ref `56765397` (`0.03` Public Leaderboard Score — Oct 2)**: Early pre-hardening tree (`667472e`) prior
  to skill/prompt fixes.
- **Ref `56810465` (`0.00` Public Leaderboard Score — Oct 4)**: Shipped a 90MB LoRA adapter trained on
  `unsloth/gemma-4-31B-it-unsloth-bnb-4bit` (BitsAndBytes NF4) mounted onto Kaggle's `w4a16-ct`
  (`compressed-tensors` INT4 packed) vLLM runtime, causing immediate logit/generation collapse (`111/129`
  tasks had `tool_calls == 0`, `77/95` traces had `0` completion tokens; `18/95` live traces ran tool
  loops before mid-run server degradation ~7.15h later).
- **Local `run_B39` (`56/129 = 43.4%`) & `run_B40` (`50/77 = 64.9%`)**: Executed on a LiteRouter proxy
  (`stealth/space-bunny-alpha`), NOT Gemma 4. Used strictly as teacher trajectories for 5-skill protocol
  distillation.
### 2.2 129-Task Benchmark Stratification (`tasks.jsonl`)
- **Repository Distribution**: FastAPI (`67`), Rich (`48`), Requests (`13`), HTTPX (`1`).
- **Tier 1 — Core Capture Target (77 tasks, 59.7%)**: Single-file solvable bug fixes:
  - **Shard A (47 tasks)**: Micro-fixes with `<= 6` lines of churn.
  - **Shard B (30 tasks)**: Localized single-file fixes with `7–60` lines of churn.
- **Tier 2 — Moderate Multi-File (15 tasks, 11.6%)**: Coordinated 2-file changes (e.g., `fastapi_14986`).
- **Tier 3 — Poison Pills (37 tasks, 28.7%)**: Massive multi-file refactors and synthetic traps that
  cannot be solved reliably within a 40-call budget (e.g., `rich_3930` with 12k lines of generated data,
  `fastapi_14609` with 2k lines, `fastapi_15661` release script generator, `fastapi_15280` April Fools
  joke, `httpx_3672` HTTP/2 async lock). Training filters out Tier 3; inference still attempts all 129
  tasks because budgets are isolated per task.

---

## Section 3: The 7 Hard Negative Constraints

1. **NO `run_command` or Raw Shell Execution**:
   - Exposing raw `run_command` to 4-bit quantized Gemma 4 causes three fatal failure modes:
     (a) un-scoped `pytest` sweeps that hang until the 300s harness kill (`test_exit_code: 124`),
     (b) scratch reproduction scripts written into `/workspace` that pollute `git add -N . && git diff HEAD`,
     and (c) multi-line bash heredoc quoting/escaping corruption across JSON tool call boundaries.
   - `repro-check` (`/tmp` isolation, 15s process-group timeout, mandatory assertion enforcement) and
     `test-gate` (distance-1 neighbor pytest, read-only diff check, test-file mutation guard) invoked via
     `run_skill_script` completely replace raw shell access. Omitting `run_command` NEVER caused the
     historical `0.03` or `0.00` scores (`0` `run_command` errors exist across all cloud traces).
2. **NO Multi-Agent or Sub-Agent Chains**:
   - The SWE-Gemma harness enforces a single task-global `max_tool_calls: 40` counter with zero
     per-sub-agent rationing. Sub-agent pipelines (e.g., Scout -> Coder -> Breaker) exhaust the 40-call
     budget during exploration before the main agent can execute `edit_file` or `submit_patch`.
3. **NO BitsAndBytes NF4 (`unsloth-bnb-4bit`) or `load_in_4bit=True` on `w4a16-ct`**:
   - `google/gemma-4-31b-it-qat-w4a16-ct` is already quantized with `compressed-tensors` (`format:
     "pack-quantized"`, INT4 group-32 symmetric). Passing `load_in_4bit=True` on `w4a16-ct` raises a
     `ValueError` or collides with BitsAndBytes NF4 quantization scales. Never train on
     `unsloth/gemma-4-31B-it-unsloth-bnb-4bit`.
4. **NO Gemma 2/3 `<start_of_turn>` Tags, Symmetric `<|tool_call|>`, or `<|thought|>`**:
   - Gemma 4 uses `<|turn>model\n` (`105`), `<turn|>` (`106`), `<|channel>thought\n...<channel|>`
     (`100`/`101`), and asymmetric `<|tool_call>...<tool_call|>` (`48`/`49`). Token `<|thought|>` does
     not exist in the 262,144-token vocabulary.
5. **NO `max_seq_length > 3072` or `eval_strategy="steps"` on Single 24GB L4 GPU**:
   - Running `trainer.evaluate()` (`eval_strategy="steps"`) materializes `[1, 3072, 262144]` FP32 logits
     (`7.50 GiB`), spiking VRAM to `27.81 GiB > 22.494 GiB` usable L4 memory and crashing at Step 5.
     Keep `max_seq_length=3072` and `eval_strategy="no"`.
6. **NO MLP Layers, Vision Tower Layers, `k_proj`, NEFTune, or Tokenizer Files in LoRA Export**:
   - Adapt strictly `["q_proj", "v_proj", "o_proj"]` on the language model (`finetune_vision_layers=False`,
     `finetune_mlp_modules=False`, `neftune_noise_alpha=None`). Ship ONLY `adapter_config.json` and
     `adapter_model.safetensors` inside `submissions/track1_live/adapters/main_lora/` (shipping
     `tokenizer.model` fails `g_disallowed_extensions` in `scripts/check_submission.py`).
7. **NO Training on or Reverse-Engineering `tasks.jsonl` Gold Patches**:
   -Reverse-engineering gold diffs from the 129 benchmark tasks is benchmark contamination that overfits
     to public tasks and collapses on private evaluation repositories.

---

## Section 4: Verified Gemma 4 (`models/gemma-4-31b-it-qat-w4a16-ct/`) Chat Template & Prefix-Delta Loss Masking

### 4.1 Verified Control Token ID Table (`tokenizer.json`, Vocab Size = `262,144`)

| Token String | Token ID | Role / Config Key in `tokenizer_config.json` |
| :--- | :--- | :--- |
| `<\|tool>` | `46` | Tool declaration block open (`stc_token`) |
| `<tool\|>` | `47` | Tool declaration block close (`etc_token` for declaration) |
| `<\|tool_call>` | `48` | Model tool call open |
| `<tool_call\|>` | `49` | Model tool call close (asymmetric closer) |
| `<\|tool_response>` | `50` | Tool response open & intermediate model stop cue |
| `<tool_response\|>` | `51` | Tool response close |
| `<\|"\|>` | `52` | String delimiter inside tool call / response dicts (`escape_token`) |
| `<\|think\|>` | `98` | System header thinking mode activation (`think_token`) |
| `<\|channel>` | `100` | Reasoning channel open (`soc_token`, followed by `thought\n`) |
| `<channel\|>` | `101` | Reasoning channel close (`eoc_token`) |
| `<\|turn>` | `105` | Turn open (`sot_token`, followed by `system\n`, `user\n`, or `model\n`) |
| `<turn\|>` | `106` | Turn close (`eot_token`) |

*(Note: There is NO `<|thought|>` token and NO `<start_of_turn>` token in Gemma 4.)*

### 4.2 Six Canonical `chat_template.jinja` Invariants
Verified directly against `models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja`:

1. **Single-Turn Multi-Step Continuation**: Gemma 4 keeps an entire multi-step tool-calling loop inside a
   SINGLE open `<|turn>model\n` turn without emitting `<turn|>` until the final text response.
2. **Turn 1 vs Turn 2+ Prefix Asymmetry (`chat_template.jinja:388`)**:
   - On **Turn 1** (immediately after `user`), `prefix_text` (`add_generation_prompt=True`) ends with
     `<|turn>model\n`, and the assistant completion starts with `<|channel>thought\n`.
   - On **Turn 2+** (immediately after a `tool` response), line 388 executes:
     ```jinja2
     {%- if ns.prev_message_type == 'tool' -%}{%- if enable_thinking -%}<|channel>thought
     {%- endif -%}{%- endif -%}
     ```
     Thus `prefix_text` (`add_generation_prompt=True`) ALREADY ends with `<tool_response|><|channel>thought\n`,
     and the assistant completion starts directly with the reasoning text! Consequently, string-matching
     `train_on_responses_only("<|turn>model\n")` fails on every Turn 2+ step.
3. **Turn 2+ Non-Empty Reasoning Requirement (`chat_template.jinja:241` vs `388`)**:
   - When `add_generation_prompt=False` (`full_text`), line 241 only emits `<|channel>thought\n...<channel|>`
     if `message['reasoning']` or `message['reasoning_content']` is non-empty. Because line 388
     unconditionally appends `<|channel>thought\n` to `prefix_text` on Turn 2+ when `enable_thinking=True`,
     every supervised Turn 2+ assistant step MUST have non-empty `reasoning`, or
     `full_text.startswith(prefix_text)` fails.
4. **`strip_thinking()` Trap (`chat_template.jinja:326`)**:
   - The template macro `strip_thinking()` strips any `<|channel>...<channel|>` blocks placed inside
     `message["content"]`. Reasoning MUST be stored in `message["reasoning"]` (or `reasoning_content`).
5. **Structured Dict Tool Arguments (`chat_template.jinja:16-36, 250-264`)**:
   - `tool_calls[].function.arguments` MUST be a Python `dict` (passing a JSON string raises a Jinja
     exception at line 258). Keys are formatted unquoted via `dictsort` and string values are wrapped in
     token `52` (`<|"|>`):
     ```text
     <|tool_call>call:read_file{end_line:150,path:<|"|>rich/ansi.py<|"|>,start_line:120}<tool_call|>
     ```
6. **Stop Cues**:
   - Intermediate tool-calling steps end with `<|tool_response>` (token `50`) as the generation stop cue;
     only the final text response closes the turn with `<turn|>\n` (token `106`).

### 4.3 Reference Implementation: Prefix-Delta Loss Masking (`build_supervised_step_sample`)

```python
from typing import Any, Dict, List


def build_supervised_step_sample(
    tokenizer: Any,
    messages: List[Dict[str, Any]],
    step_index: int,
    tools: List[Dict[str, Any]],
) -> Dict[str, List[int]]:
    """Build input_ids and prefix-delta masked labels for one assistant step.

    Args:
        tokenizer: Loaded Gemma 4 tokenizer with canonical chat_template.jinja.
        messages: Full conversation history up to and including step_index.
        step_index: Index of the target assistant message in `messages`.
        tools: List of 6 tool schemas (read_file, edit_file, write_file,
            get_status, submit_patch, run_skill_script).
    """
    target_msg = messages[step_index]
    assert target_msg["role"] == "assistant", f"Expected assistant at {step_index}"
    reasoning = (
        target_msg.get("reasoning")
        or target_msg.get("reasoning_content")
        or ""
    ).strip()
    assert len(reasoning) > 0, (
        f"Turn {step_index} has empty reasoning; violates Turn 2+ prefix invariant"
    )
    target_msg_dict = dict(target_msg)
    target_msg_dict["reasoning"] = reasoning

    prefix_messages = messages[:step_index]
    full_messages = messages[:step_index] + [target_msg_dict]

    prefix_text = tokenizer.apply_chat_template(
        prefix_messages,
        tools=tools,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True,
        preserve_thinking=True,
    )
    full_text = tokenizer.apply_chat_template(
        full_messages,
        tools=tools,
        tokenize=False,
        add_generation_prompt=False,
        enable_thinking=True,
        preserve_thinking=True,
    )

    # For intermediate tool-calling steps, append <|tool_response> stop cue
    if target_msg_dict.get("tool_calls"):
        if not full_text.endswith("<|tool_response>"):
            full_text = full_text + "<|tool_response>"

    assert full_text.startswith(prefix_text), (
        f"Prefix mismatch at step {step_index}:\n"
        f"PREFIX TAIL: {prefix_text[-120:]!r}\n"
        f"FULL AT PREFIX LEN: {full_text[len(prefix_text)-60:len(prefix_text)+60]!r}"
    )

    prefix_ids = tokenizer.encode(prefix_text, add_special_tokens=False)
    full_ids = tokenizer.encode(full_text, add_special_tokens=False)
    assert full_ids[: len(prefix_ids)] == prefix_ids, (
        f"Token boundary BPE merge mismatch at step {step_index}"
    )

    labels = [-100] * len(prefix_ids) + full_ids[len(prefix_ids) :]
    return {
        "input_ids": full_ids,
        "attention_mask": [1] * len(full_ids),
        "labels": labels,
    }
```

---

## Section 5: 5-Skill SFT Dataset Audit & Remediation (`scripts/build_unsloth_dataset.py`)

### 5.1 Quantitative Profile of `training/sft_data/unsloth_sft_train.jsonl`
- **Row & Task Counts**: `885` train windows and `222` validation windows (`1,107` total step windows)
  distilled across `40` resolved teacher trajectories (`FastAPI`, `Rich`, `Requests`).
- **Token Length Distribution (`max_seq_length=3072` Fit)**:
  - **Min**: `665` tokens
  - **Median (P50)**: `1,162` tokens
  - **P90**: `1,686` tokens
  - **Max**: `2,822` tokens (`100.0%` of windows are `<= 2,822` tokens -> zero truncation at `3,072`).
- **Tool Call Distribution Across 596 Tool-Calling Train Windows (`639` Total Tool Calls)**:

| Tool Name | Call Count | Share (%) | Role in 5-Skill Architecture |
| :--- | :--- | :--- | :--- |
| `run_skill_script` | `411` | `64.3%` | Executes `fast-grep`, `code-map`, `code-oracle`, `repro-check`, `test-gate` |
| `read_file` | `110` | `17.2%` | Targeted line-window code inspection |
| `edit_file` | `71` | `11.1%` | Surgical source modification |
| `submit_patch` | `44` | `6.9%` | Final patch submission |
| `write_file` | `3` | `0.5%` | New file creation |
| `run_command` | `0` | `0.0%` | **Strictly zero** (withheld by design) |

### 5.2 Four Dataset Builder Bugs in `scripts/build_unsloth_dataset.py` & Exact Fixes

1. **Bug 1 — Legacy Gemma 2/3 `<start_of_turn>` Formatting (`lines 303-336`)**:
   - *Defect*: Manually formats strings with `<start_of_turn>user`, `<start_of_turn>model`, `<|thought|>`,
     and symmetric `<|tool_call|>` tags instead of invoking Gemma 4's `apply_chat_template`.
   - *Fix*: Replace manual string concatenation with `build_supervised_step_sample()` using the canonical
     `models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja` and Python `dict` tool arguments.
2. **Bug 2 — `289/885` (`32.66%`) `target_tools: []` Dead-Thought Rows**:
   - *Defect*: Emits standalone supervised examples for assistant turns that contain only reasoning and
     zero tool calls (`289` of `885` train rows), training Gemma 4 to stop generating after emitting a
     thought without invoking a tool.
   - *Fix*: Merge consecutive thought-only assistant turns into the immediately following tool-calling
     turn's `reasoning` field, and drop any trailing orphan thought-only turns (`885 -> 596` clean,
     100% tool-calling windows).
3. **Bug 3 — `100%` `task_id` Overlap Between Train and Validation Splits**:
   - *Defect*: Splits step windows randomly across rows rather than grouping by `task_id`, leaking all
     `40/40` tasks into both `unsloth_sft_train.jsonl` and `unsloth_sft_val.jsonl`.
   - *Fix*: Group all windows by `task_id` prior to splitting (e.g., `34` train tasks / `6` val tasks,
     enforcing `0.0%` `task_id` overlap).
4. **Bug 4 — 3-Line Stub System Prompt Instead of Production `prompts/main.md`**:
   - *Defect*: Training examples prepend a 3-line generic system prompt stub instead of the production
     5-skill system prompt (`submissions/track1_live/prompts/main.md`) and the 6 ADK tool declarations.
   - *Fix*: Embed verbatim `submissions/track1_live/prompts/main.md` and the exact 6 tool schemas
     (`read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `run_skill_script`) so SFT
     prefixes match vLLM inference prefixes token-for-token.

---

## Section 6: Single L4 (24GB) Unsloth LoRA Training, Geometry & Packaging Specification

### 6.1 Base Checkpoint Architecture & Dual-Path Loading Contract
- **Local Verified Checkpoint (`models/gemma-4-31b-it-qat-w4a16-ct/`)**:
  - `23,265,352,448` bytes across `2,009` tensors (`model.safetensors`).
  - `quant_method: "compressed-tensors"`, `format: "pack-quantized"`, INT4 group-32 symmetric on the 60
    language model layers (`model.language_model.layers.0..59`, `19.36 GB`), BF16 on the vision tower
    (`model.vision_tower.*`, `1.15 GB`, listed in `ignore`).
- **Primary Loading Path (`w4a16-ct` Direct via Unsloth)**:
  ```python
  model, tokenizer = FastModel.from_pretrained(
      model_name="google/gemma-4-31b-it-qat-w4a16-ct",
      max_seq_length=3072,
      dtype=torch.bfloat16,
      load_in_4bit=False,          # Mandatory: already pack-quantized compressed-tensors
      use_exact_model_name=True,   # Mandatory: prevents Unsloth remapping to BnB NF4
      text_only=False,             # Mandatory: preserves base_model.model.language_model.* prefix
  )
  ```
- **Contingency Fallback Path (If Unsloth Blocks Backprop on `Int4PackedLinear`)**:
  - Load `google/gemma-4-31B-it-qat-q4_0-unquantized` (the official BF16 QAT twin) with
    `load_in_4bit=True, dtype=torch.bfloat16, text_only=False` for training, then rewrite
    `"base_model_name_or_path": "google/gemma-4-31b-it-qat-w4a16-ct"` in `adapter_config.json` on export.

### 6.2 Exact LoRA Geometry (`attention_k_eq_v=True` on 10 Global Full-Attention Layers)
- **PEFT Configuration**:
  ```python
  model = FastModel.get_peft_model(
      model,
      r=8,
      lora_alpha=16,
      lora_dropout=0.0,
      bias="none",
      finetune_vision_layers=False,
      finetune_language_layers=True,
      finetune_attention_modules=True,
      finetune_mlp_modules=False,
      target_modules=["q_proj", "v_proj", "o_proj"],
      use_gradient_checkpointing="unsloth",
      random_state=3407,
  )
  ```
- **Why `170` Adapted Modules (`340` Tensors) Instead of `180`**:
  - Gemma 4's 60 language layers consist of **50 sliding-window attention layers** (which have `q_proj`,
    `k_proj`, `v_proj`, `o_proj`) and **10 global full-attention layers** configured with
    `attention_k_eq_v=True` (where `k_proj` serves as both key and value, so `v_proj` is omitted).
  - Adapting `["q_proj", "v_proj", "o_proj"]` yields `60 (q_proj) + 50 (v_proj) + 60 (o_proj) = 170`
    adapted linear modules (`340` LoRA `A`/`B` matrices), totaling exactly **`18,124,800` trainable
    parameters** (`34.57 MiB` in BF16).

### 6.3 Component-by-Component 24GB NVIDIA L4 (`22.494 GiB` Usable) VRAM Budget
Training hyperparameters: `max_seq_length=3072`, `per_device_train_batch_size=1`,
`gradient_accumulation_steps=8`, `optim="paged_adamw_8bit"`, `learning_rate=1e-4`, `num_train_epochs=1`,
`max_grad_norm=0.3`, `neftune_noise_alpha=None`, `eval_strategy="no"`.

| VRAM Component | Memory (GiB) | Notes |
| :--- | :--- | :--- |
| Base Checkpoint Weights (`w4a16-ct` language + BF16 vision) | `17.77 GiB` | Static resident model footprint |
| LoRA Parameters + BF16 Gradients (`18,124,800` params) | `0.07 GiB` | `34.57 MiB` weights + `34.57 MiB` grads |
| Optimizer States (`paged_adamw_8bit`) | `0.04 GiB` | 8-bit first/second moments + CPU paging |
| Checkpointed Activations + Cut Cross-Entropy (`seq_len=3072`) | `1.58 GiB` | Avoids 262K FP32 logit tensor |
| CUDA Context / Triton / PyTorch Allocator Reserve | `0.85 GiB` | Runtime kernel workspace |
| **Total Peak Training VRAM** | **`20.31 GiB`** | **`+2.18 GiB` safe headroom** under `22.494 GiB` L4 limit |
| *(Forbidden `eval_strategy="steps"` FP32 Logit Spike)* | *(`+7.50 GiB`)* | *(`[1, 3072, 262144]` -> `27.81 GiB` OOM)* |

### 6.4 Strict 2-File Export & 15-Gate Verification Contract
- **Export Directory (`submissions/track1_live/adapters/main_lora/`)**:
  1. `adapter_config.json` (with `"base_model_name_or_path": "google/gemma-4-31b-it-qat-w4a16-ct"`).
  2. `adapter_model.safetensors` (`~34.6 MiB`, every key matching
     `base_model.model.language_model.layers.{i}.self_attn.{q,v,o}_proj.lora_{A,B}.weight`; zero
     `vision_tower` keys).
  3. **Zero tokenizer files**: Do NOT save `tokenizer.json`, `tokenizer.model`, or `special_tokens_map.json`
     into `adapters/main_lora/`.
- **Verification Command**:
  ```bash
  python3 scripts/check_submission.py && python3 scripts/baseline_gate.py verify --mode=compute --check-zip
  ```

---

## Section 7: Concrete Review Questions for External Consultants (Q1–Q4)

Please provide concrete, deeply technical, code-level answers to the following four questions
(synchronized 100% with `training/research_dossier/00_CONSULTANT_PROMPT.md`):

### Q1: Gemma 4 Native Chat Template & Prefix-Delta Loss Masking
We verified directly against `models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja` that Gemma 4 keeps
an entire multi-step tool-calling loop inside a **single open `<|turn>model\n` block** without emitting
`<turn|>` until the final text response. Furthermore:
- On **Turn 1** (immediately after `user`), `prefix_text` (`add_generation_prompt=True`) ends with
  `<|turn>model\n`, and `completion_text` starts with `<|channel>thought\n`.
- On **Turn 2+** (immediately after `tool`), `chat_template.jinja:388`
  (`{%- if ns.prev_message_type == 'tool' -%}{%- if enable_thinking -%}<|channel>thought\n{%- endif -%}`)
  appends `<|channel>thought\n` to `prefix_text` **before** the completion begins, while line 241
  (`add_generation_prompt=False`) only emits `<|channel>thought\n...<channel|>` in `full_text` when
  `reasoning` / `reasoning_content` is non-empty.
- Consequently, standard substring splitters like Unsloth's
  `train_on_responses_only(response_part="<|turn>model\n")` fail on Turn 2+. We replaced it with
  **prefix-delta loss masking** (`full_text[len(prefix_text):]`) with `enable_thinking=True,
  preserve_thinking=True` and a hard assertion that every supervised Turn 2+ step has non-empty
  `reasoning` (`assert full_text.startswith(prefix_text)`).

**Questions for Q1**:
1. Audit our prefix-delta masking implementation against `chat_template.jinja`. Are there any BPE
   boundary token-merging ("token-healing") edge cases in Gemma 4's SentencePiece/BPE tokenizer
   (`vocab_size=262,144`) when slicing token IDs via `full_ids[len(prefix_ids):]` right after
   `<|channel>thought\n` (where `\n` is followed by plain-text reasoning)?
2. Should we compute the `-100` label mask using character-offset mapping
   (`tokenizer(full_text, return_offsets_mapping=True, add_special_tokens=False)`) against
   `len(prefix_text)` rather than `len(prefix_ids)`, and how should the boundary token be handled if BPE
   merges the trailing `\n` of `<|channel>thought\n` with the first character of the reasoning string?

### Q2: Unsloth `w4a16-ct` Int4PackedLinear Training vs `q4_0-unquantized` Fallback & vLLM Serving Parity
Kaggle serves `google/gemma-4-31b-it-qat-w4a16-ct` (`quant_method: "compressed-tensors"`, `format:
"pack-quantized"`, INT4 group-32 symmetric on `model.language_model.layers.0..59`, BF16 on
`model.vision_tower`) under vLLM (`tp=4`, `--enable-lora`). Our primary training load passes
`FastModel.from_pretrained("google/gemma-4-31b-it-qat-w4a16-ct", max_seq_length=3072,
dtype=torch.bfloat16, load_in_4bit=False, use_exact_model_name=True, text_only=False)` with
`finetune_vision_layers=False`. If Unsloth/PyTorch blocks gradient backpropagation through
`compressed-tensors` `Int4PackedLinear` kernels, our fallback loads the official unquantized QAT sibling
`google/gemma-4-31B-it-qat-q4_0-unquantized` with `load_in_4bit=True` and rewrites
`base_model_name_or_path` to `"google/gemma-4-31b-it-qat-w4a16-ct"` on export.

**Questions for Q2**:
1. Verify our Unsloth loading contract and fallback mechanics. When training on `q4_0-unquantized` with
   `load_in_4bit=True`, does the QAT-trained weight geometry align closely enough with `w4a16-ct`
   `pack-quantized` INT4 group-32 weights at `r=8, lora_alpha=16` to prevent the logit collapse observed
   when mounting a non-QAT `unsloth-bnb-4bit` adapter?
2. Verify our vLLM `--enable-lora` tensor-name and module-count parity: across 60 language layers (50
   sliding-attention layers with `q/k/v/o_proj` and 10 global full-attention layers where
   `attention_k_eq_v=True` omits `v_proj`), targeting `["q_proj", "v_proj", "o_proj"]` yields
   `60 + 50 + 60 = 170` adapted modules (`340` LoRA A/B tensors) named
   `base_model.model.language_model.layers.{i}.self_attn.{q,v,o}_proj.lora_{A,B}.weight`. Are any
   additional key transformations or `adapter_config.json` fields required by vLLM's `Gemma4ForCausalLM`
   / multimodal wrapper?

### Q3: 5-Skill SFT Dataset Curation, Filtering, and Overfitting Prevention
Our teacher dataset (`training/sft_data/unsloth_sft_train.jsonl`, `885` train / `222` val windows across
`40` resolved teacher trajectories from `run_B39`/`run_B40`) reduces to **`596` valid tool-calling train
windows** (`639` tool calls: `run_skill_script` `64.3%`, `read_file` `17.2%`, `edit_file` `11.1%`,
`submit_patch` `6.9%`, `write_file` `0.5%`, `run_command` `0.0%`) after merging the `289` (`32.66%`)
`target_tools: []` dead-thought windows into subsequent action turns and splitting strictly by `task_id`
(`0%` task overlap).

**Questions for Q3**:
1. With `18,124,800` trainable parameters and `596` decision windows (~`75,000`–`90,000` supervised
   completion tokens), what is the optimal sample-weighting or window-filtering strategy so the adapter
   masters high-leverage transition boundaries (`repro-check` -> `edit_file` -> `test-gate` ->
   `submit_patch`) rather than over-allocating capacity to repetitive early-turn `fast-grep` calls?
2. Audit our regularization and optimization hyperparameters (`lr=1e-4`, `1` epoch, `warmup_ratio=0.10`,
   `weight_decay=0.01`, `max_grad_norm=0.3`, `lora_dropout=0.0`, `neftune_noise_alpha=None`). How do we
   prevent the Rank-8 adapter from memorizing FastAPI/Rich/Requests file paths and repository-specific
   symbol names?

### Q4: Contamination-Free 5-Skill Trajectory Augmentation
Our 40 resolved teacher trajectories come from `fastapi` (`21` tasks), `rich` (`13` tasks), and
`requests` (`6` tasks). Under Invariant 3, we will **never** extract or train on gold patches from
`tasks.jsonl`. Under Invariant 1, we will **never** synthesize `run_command` calls.

**Questions for Q4**:
1. If `596` clean decision windows are insufficient or require augmentation, what is the
   highest-leverage, 100% contamination-free method to synthesize or harvest additional 5-skill
   trajectories (`fast-grep` -> `code-map` -> `read_file` -> `repro-check` -> `edit_file` -> `test-gate`
   -> `submit_patch`) — for example, using external open-source commits/PRs or negative-to-positive
   self-correction loops (`repro-check` assertion failure -> `edit_file` fix -> `test-gate` pass)?
2. What exact offline validation gate (e.g., held-out task exact-match tool syntax rate, `<|"|>`
   delimiter validity, `submit_patch` termination rate, and perplexity on held-out `task_id`s) should
   govern whether the trained Track 2 LoRA adapter is promoted to our Kaggle Compute staging kernel
   before touching the 1/day Leaderboard quota?
