# 07 — Internal Research Findings & Ground-Truth Verification Reference

**Document Role**: Authoritative internal engineering reference documenting all findings verified directly against the local competition checkpoint (`models/gemma-4-31b-it-qat-w4a16-ct/`: `tokenizer.json`, `chat_template.jinja`, `config.json`, and `model.safetensors`) and the SFT dataset (`training/sft_data/unsloth_sft_train.jsonl`). Every claim in this document is proven by direct file inspection or execution against the local artifacts.

---

## Part 1: Native Gemma 4 Control Tokens (`models/gemma-4-31b-it-qat-w4a16-ct/tokenizer.json`)

Direct inspection of `models/gemma-4-31b-it-qat-w4a16-ct/tokenizer.json` (`vocab_size = 262,144`) and `tokenizer_config.json` establishes the exact special token IDs used by Gemma 4 and vLLM's `gemma4` parser:

| Token ID | Literal Token String | Role in `tokenizer_config.json` / `chat_template.jinja` | Notes & Asymmetry Invariant |
| :--- | :--- | :--- | :--- |
| **`1`** | `<eos>` | `eos_token` (primary) | Primary end-of-sequence token (`config.json:13-16` sets `eos_token_id: [1, 106]`). |
| **`2`** | `<bos>` | `bos_token` | Prepended once at the start of the conversation (`chat_template.jinja:188`). |
| **`46`** | `<|tool>` | ` sot_tool` (tool declaration opener) | Opens each tool schema declaration in the system block (`chat_template.jinja:209`). |
| **`47`** | `<tool|>` | `eot_tool` (tool declaration closer) | Closes each tool schema declaration (`chat_template.jinja:211`). **Asymmetric** (`<|tool>` vs `<tool|>`). |
| **`48`** | `<|tool_call>` | `stc_token` (tool call opener) | Opens a model tool invocation (`chat_template.jinja:248`). |
| **`49`** | `<tool_call|>` | `etc_token` (tool call closer) | Closes a model tool invocation (`chat_template.jinja:264`). **Asymmetric** (`<|tool_call>` vs `<tool_call|>`). |
| **`50`** | `<|tool_response>` | `str_token` (tool response opener / stop cue) | Opens a tool response block (`chat_template.jinja:169`) and acts as the **intermediate generation stop cue** when a tool call is emitted (`chat_template.jinja:370`). |
| **`51`** | `<tool_response|>` | `etr_token` (tool response closer) | Closes a tool response block (`chat_template.jinja:180`). |
| **`52`** | `<\|"\|>` | `escape_token` (string delimiter) | Wraps all string literals inside tool declarations, tool calls, and tool responses (`chat_template.jinja:128, 138`). |
| **`98`** | `<|think|>` | `think_token` (system thinking header) | Injected at the top of `<|turn>system\n` when `enable_thinking=True` (`chat_template.jinja:193-195`). |
| **`100`** | `<|channel>` | `soc_token` (start of channel) | Opens reasoning blocks as `<|channel>thought\n` (`chat_template.jinja:242, 388`). |
| **`101`** | `<channel|>` | `eoc_token` (end of channel) | Closes reasoning blocks (`chat_template.jinja:242, 385`). |
| **`105`** | `<|turn>` | `sot_token` (start of turn) | Opens a `system`, `user`, or `model` turn (`chat_template.jinja:191, 234, 383`). |
| **`106`** | `<turn|>` | `eot_token` (end of turn / secondary EOS) | Closes a turn (`chat_template.jinja:215, 373`). |

**Critical Negative Proofs**:
1. **NO `<|thought|>` or `<thought|>` Token**: Searching `tokenizer.json` for `<|thought` or `thought|>` returns **zero matches**. Gemma 4 represents internal reasoning exclusively via `<|channel>thought\n...<channel|>` (tokens `100` and `101`).
2. **NO `<start_of_turn>` or `<end_of_turn>` Token**: Gemma 2/3 turn markers do not exist as control tokens in Gemma 4 (`<|turn>` `105` and `<turn|>` `106` replaced them).
3. **NO Symmetric `<|tool_call|>` Token**: Emitting `<|tool_call|>` on both sides (as `scripts/build_unsloth_dataset.py:319` did) produces an unknown tag fragmented into ordinary text pieces, breaking vLLM's `Gemma4ToolParser`.

---

## Part 2: Six Canonical `chat_template.jinja` Invariants & Prefix-Delta Loss Masking

Executing `models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja` directly via Jinja2 reveals six structural invariants that govern multi-turn tool-calling SFT:

### Invariant 1 — Single-Turn Multi-Step Continuation (`chat_template.jinja:232-236, 363-374`)
Unlike OpenAI ChatML or Gemma 2/3 (which open and close a new `assistant` turn for every tool call), Gemma 4 keeps an entire multi-step agentic tool loop inside a **single open `<|turn>model\n` turn**:
- At line `232`: `{%- set continue_same_model_turn = (role == 'model' and ns.prev_non_tool_role == 'assistant') -%}`.
- When `continue_same_model_turn` is `True` (every assistant step after a tool response), line `234` **suppresses `<|turn>model\n`**.
- Similarly, at lines `363-374`, `<turn|>\n` is suppressed whenever a tool call or continuation follows. `<turn|>\n` is only emitted at the end of the final text-only assistant turn.

### Invariant 2 — Turn 1 vs. Turn 2+ Prefix Asymmetry (`chat_template.jinja:381-390`)
Look at the generation-prompt block at the bottom of `chat_template.jinja` (lines `381-390`):
```jinja2
{%- if add_generation_prompt -%}
    {%- if ns.prev_message_type != 'tool_response' and ns.prev_message_type != 'tool_call' -%}
        {{- '<|turn>model\n' -}}
        {%- if not enable_thinking -%}
            {{- '<|channel>thought\n<channel|>' -}}
        {%- endif -%}
    {%- elif ns.prev_message_type == 'tool_response' and enable_thinking -%}
        {{- '<|channel>thought\n' -}}
    {%- endif -%}
{%- endif -%}
```
This creates a profound asymmetry between Turn 1 and Turn 2+ when `enable_thinking=True`:
- **On Turn 1 (immediately after `user`)**:
  - `prefix_text` (`add_generation_prompt=True`) ends with `<|turn>model\n`.
  - The supervised completion (`full_text[len(prefix_text):]`) begins with `<|channel>thought\n{reasoning}\n<channel|><|tool_call>...`.
- **On Turn 2+ (immediately after `tool` / `<tool_response|>`)**:
  - Because `ns.prev_message_type == 'tool_response'` and `enable_thinking == True`, **line `388` appends `<|channel>thought\n` directly to `prefix_text`**!
  - Furthermore, `<|turn>model\n` does **not** appear before the Turn 2+ step at all (Invariant 1).
  - Therefore, Unsloth's string-matching `train_on_responses_only(instruction_part=..., response_part="<|turn>model\n")` is **mathematically incapable of masking Turn 2+ windows**: either it leaves the Turn 1 assistant step + tool response unmasked in the loss, or it fails to locate a response boundary after `<tool_response|>`.

### Invariant 3 — Turn 2+ Empty-Reasoning Trap & `preserve_thinking=True` (`chat_template.jinja:239-243, 388`)
In `full_text` (`add_generation_prompt=False`), lines `239-243` render the assistant's thought block conditionally:
```jinja2
{%- set thinking_text = message.get('reasoning') or message.get('reasoning_content') -%}
{%- set thinking_gate = (loop.index0 > ns_turn.last_user_idx) or (preserve_thinking and message.get('tool_calls')) -%}
{%- if thinking_text and thinking_gate -%}
    {{- '<|channel>thought\n' + thinking_text + '\n<channel|>' -}}
{%- endif -%}
```
Compare this with line `388` (`add_generation_prompt=True`), which **unconditionally** appends `<|channel>thought\n` after a tool response whenever `enable_thinking=True`:
- If a supervised Turn 2+ target message has an empty `reasoning` field (`""` or `None`), `prefix_text` ends with `<tool_response|><|channel>thought\n`, whereas `full_text` skips line `242` and jumps straight to `<tool_response|><|tool_call>call:...`!
- Consequently, `full_text.startswith(prefix_text)` evaluates to **`False`**!
- **Mandatory Rule**: Every supervised target assistant turn in the SFT dataset MUST have a non-empty `reasoning` string, and both `apply_chat_template` calls (`prefix_text` and `full_text`) MUST pass `enable_thinking=True, preserve_thinking=True`.

### Invariant 4 — The `strip_thinking()` Trap (`chat_template.jinja:156-166, 326`)
At line `326`, `chat_template.jinja` runs `strip_thinking(message['content'])`, which strips any `<|channel>...<channel|>` block placed inside `message["content"]`. Reasoning MUST be passed in `message["reasoning"]` (or `message["reasoning_content"]`), never inside `message["content"]`.

### Invariant 5 — Structured Dict Tool Arguments & `<|"|>` Escaping (`chat_template.jinja:16-36, 124-155, 248-264`)
At lines `249-263`, `chat_template.jinja` inspects `function['arguments']`:
- If `function['arguments']` is a `mapping` (Python `dict`), it iterates over `function['arguments'] | dictsort` (alphabetically sorted, unquoted keys) and formats values via `format_argument(value, escape_keys=False)` (strings wrapped in `<|"|>...<|"|>`).
- If `function['arguments']` is a JSON `str` (standard OpenAI format), lines `258-262` **raise a fatal Jinja `TemplateRuntimeError`**:
  `"chat_template: tool_calls[].function.arguments must be a JSON object (mapping), not a string. Deserialize arguments before passing to the template."`
- Furthermore, lines `288-292` resolve `tool_call_id` to `tc['function']['name']` when rendering `<|tool_response>response:{name}{...}<tool_response|>`.

### Invariant 6 — Intermediate Stop Cue (`<|tool_response>`, Token `50`, `chat_template.jinja:369-374`)
When the final message in `window_messages` is an assistant tool call (`ns.prev_message_type == 'tool_call'` and `not ns_tr_out.flag`), lines `369-370` append `<|tool_response>` (token `50`) — **not** `<turn|>\n` (token `106`) — immediately after `<tool_call|>`. Supervising `full_ids[len(prefix_ids):]` trains the model to emit `<tool_call|><|tool_response>` and halt generation cleanly for the harness tool executor.

### Verified Prefix-Delta Loss Masking Implementation
```python
def build_supervised_step_sample(tokenizer, window_messages, tools_schema, max_seq_length=3072):
    assert window_messages[-1]["role"] == "assistant" and window_messages[-1].get("tool_calls")
    assert (window_messages[-1].get("reasoning") or "").strip(), "Non-empty reasoning required on Turn 2+"

    prefix_text = tokenizer.apply_chat_template(
        window_messages[:-1],
        tools=tools_schema,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True,
        preserve_thinking=True,
    )
    full_text = tokenizer.apply_chat_template(
        window_messages,
        tools=tools_schema,
        tokenize=False,
        add_generation_prompt=False,
        enable_thinking=True,
        preserve_thinking=True,
    )
    assert full_text.startswith(prefix_text)

    prefix_ids = tokenizer.encode(prefix_text, add_special_tokens=False)
    full_ids = tokenizer.encode(full_text, add_special_tokens=False)
    assert len(full_ids) <= max_seq_length and full_ids[: len(prefix_ids)] == prefix_ids

    labels = [-100] * len(prefix_ids) + full_ids[len(prefix_ids) :]
    return {"input_ids": full_ids, "attention_mask": [1] * len(full_ids), "labels": labels}
```

---

## Part 3: Dataset Audit & Remediation Specification (`training/sft_data/unsloth_sft_train.jsonl`)

### 3.1 Quantitative Audit of Current SFT Files (`885` Train / `222` Val Windows)
- **Source**: Distilled from `40` unique resolved teacher trajectories (`results/run_B40` and `results/run_B39`) that passed outlier filters (`patch_lines <= 150`, `tool_calls <= 35`) and 90% `difflib` patch deduplication.
- **Token Length Distribution (`estimated_tokens` across `885` train windows)**:
  - **Min**: `665` tokens
  - **Median (P50)**: `1,162` tokens
  - **90th Percentile (P90)**: `1,686` tokens
  - **Max**: `2,822` tokens (`100.0%` of windows are `<= 2,822` tokens -> fits inside `max_seq_length = 3072` with **zero truncation**).
- **Target Turn & Tool Distribution (`885` train windows)**:
  - **Tool-Calling Windows**: `596 / 885` (`67.34%`), containing `639` total tool calls:
    - `run_skill_script`: **`411`** (`64.3%`) — invokes `fast-grep`, `code-map`, `code-oracle`, `repro-check`, `test-gate`
    - `read_file`: **`110`** (`17.2%`)
    - `edit_file`: **`71`** (`11.1%`)
    - `submit_patch`: **`44`** (`6.9%`)
    - `write_file`: **`3`** (`0.5%`)
    - `run_command`: **`0`** (`0.0%` — **by design**, matching the 5-tool + 5-skill production contract)
  - **Dead-Thought (`target_tools: []`) Windows**: **`289 / 885` (`32.66%`)** contain zero tool calls!

### 3.2 Four Dataset Bugs & Exact Remediation
1. **Bug 1 — Legacy Gemma 2/3 `<start_of_turn>` & JSON-String Arguments**:
   - *Fix*: Delete `render_gemma_chat_turns()`. Keep `tool_calls[].function.arguments` as a Python `dict`, move thoughts to `message["reasoning"]`, and format exclusively via `tokenizer.apply_chat_template(..., enable_thinking=True, preserve_thinking=True)` with `build_supervised_step_sample()`.
2. **Bug 2 — `289/885` (`32.66%`) Dead-Thought (`target_tools: []`) Rows**:
   - *Root Cause*: When the teacher model emitted a reasoning-only message on step $t$ followed by a tool call on step $t+1$, `slice_trajectory_decisions()` made step $t$ a standalone training target ending in `<turn|>`, teaching Gemma 4 to stop after one thought without calling any tool (`1/3` of all steps).
   - *Fix*: Coalesce consecutive thought-only assistant turns into the next tool-calling turn's `reasoning` field and drop trailing tool-less turns, yielding **`596` clean 100%-tool-calling windows**.
3. **Bug 3 — `100%` `task_id` Overlap Between Train and Validation**:
   - *Root Cause*: `build_unsloth_dataset.py:475-490` shuffled individual windows rather than grouping by `task_id`, putting all `40` tasks into both `train` and `val`.
   - *Fix*: Group windows by `task_id` before splitting (`34` train tasks / `6` val tasks, stratified by repository = **`0.0%` task overlap**).
4. **Bug 4 — 3-Line Stub System Prompt**:
   - *Root Cause*: `build_unsloth_dataset.py:50-54` trained on a 3-line stub (`29` tokens) while inference injects `submissions/track1_live/prompts/main.md` (`~1,850` tokens).
   - *Fix*: Inject the verbatim production `submissions/track1_live/prompts/main.md` (and canonical 6-tool declarations: 5 direct tools + `run_skill_script`) into every training window's system block.

---

## Part 4: Hardware, `w4a16-ct` Checkpoint Census & Single-L4 VRAM Budget

### 4.1 `models/gemma-4-31b-it-qat-w4a16-ct/` Physical & Quantization Audit
- **Disk Footprint**: `23,265,352,448` bytes (`2,009` tensors in `model.safetensors`).
  - Language model (`model.language_model.layers.0..59`): `19.36 GB` (`83.2%`), quantized with `quant_method: "compressed-tensors"`, `format: "pack-quantized"`, INT4 symmetric group-32 (`weight_packed` `int32`, `weight_scale` `bfloat16`, `weight_shape`).
  - Tied embeddings (`model.language_model.embed_tokens.weight`): `2.82 GB` (`12.1%`), `262,144 x 5,376` in `bfloat16`.
  - Vision tower (`model.vision_tower.*`): `1.15 GB` (`4.9%`), explicitly ignored by `quantization_config` and stored in `bfloat16`.

### 4.2 Binary Header Layer Census & `attention_k_eq_v=True` (`170` Adapted Modules)
In `config.json:257-340`, `num_hidden_layers = 60` alternates 5 sliding-attention layers (`head_dim=256, num_key_value_heads=16`) with 1 full-attention global layer (`global_head_dim=512, num_global_key_value_heads=4, attention_k_eq_v=True`):
- **50 Sliding-Attention Layers**: Have `q_proj`, `k_proj`, `v_proj`, and `o_proj`.
- **10 Full-Attention Layers** (`layers.{5,11,17,23,29,35,41,47,53,59}`): Set `attention_k_eq_v=True` (`K=V`) and **physically omit `v_proj`** in `model.safetensors`.
- **Total Tensor Count in `model.safetensors`**: `60 q_proj`, `60 k_proj`, `50 v_proj`, `60 o_proj`.
- **Target Modules (`["q_proj", "v_proj", "o_proj"]`, `r=8, lora_alpha=16`)**:
  - Adapts **`60 q_proj + 50 v_proj + 60 o_proj = 170` linear modules** (`340` LoRA A/B tensors).
  - Total trainable parameters: **`18,124,800` parameters (`34.57 MiB` in BF16)**.

### 4.3 Single 24 GB NVIDIA L4 (`22.494 GiB` Usable) VRAM Budget (`max_seq_length=3072`)
- **Base Weights**: `17.77 GiB`
- **LoRA Weights + BF16 Gradients**: `0.07 GiB`
- **8-bit Paged Optimizer States (`paged_adamw_8bit`)**: `0.04 GiB`
- **Unsloth Checkpointed Activations + Fused Cut-Cross-Entropy (`3072` tokens)**: `1.60 GiB`
- **CUDA / Triton Context & Caching Allocator Reserve**: `0.85 GiB`
- **Peak Training Footprint (`eval_strategy="no"`)**: **`20.31 GiB`** (`+2.18 GiB` safety margin below `22.494 GiB`).
- **Why `eval_strategy="no"` is Mandatory**: Running `Trainer.evaluate()` (`eval_strategy="steps"`) bypasses Unsloth's fused Cut-Cross-Entropy and allocates raw `[1, 3072, 262144]` FP32 logits (`3.00 GiB` + `4.50 GiB` upcast/reduction buffers = **`+7.50 GiB` spike** -> `27.81 GiB > 22.494 GiB` immediate CUDA OOM).
