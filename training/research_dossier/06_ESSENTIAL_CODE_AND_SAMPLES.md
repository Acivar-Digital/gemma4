# 06. Essential Code & Sample SFT Trajectories

This file provides the exact training code, dataset builder logic, live agent YAML, and verbatim SFT training samples so you have the complete technical context without downloading multi-megabyte JSONL files.

---

## 1. Current Training Script (`training/notebooks/train_gemma4_lora_minimal.ipynb`)

```python
# ==============================================================================
# CELL 2: MODEL INITIALIZATION & RANK-8 PEFT CONFIGURATION
# ==============================================================================
import torch
from unsloth import FastLanguageModel
from pathlib import Path

max_seq_length = 6144
dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
load_in_4bit = True

candidate_model_dirs = [
    Path('/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'),
    Path('/kaggle/input/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'),
    *sorted(Path('/kaggle/input').glob('**/*gemma-4-31b-it-qat-w4a16-ct*')),
]
model_name = None
for cand in candidate_model_dirs:
    if cand.exists() and cand.is_dir():
        model_name = str(cand)
        break
if not model_name:
    model_name = 'google/gemma-4-31b-it' # <-- DEFECT: Should be google/gemma-4-31B-it-qat-q4_0-unquantized

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=max_seq_length,
    dtype=dtype,
    load_in_4bit=load_in_4bit,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=8,
    target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj'],
    lora_alpha=8,
    lora_dropout=0.05,
    bias='none',
    use_gradient_checkpointing='unsloth',
    random_state=42,
)

# ==============================================================================
# CELL 3: SFT TRAINING WITH ASSISTANT-ONLY LOSS MASKING
# ==============================================================================
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth.chat_templates import train_on_responses_only

train_dataset = load_dataset('json', data_files=str(train_path), split='train')
val_dataset = load_dataset('json', data_files=str(val_path), split='train')

training_args = TrainingArguments(
    output_dir=str(OUTPUT_DIR),
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    warmup_steps=3,
    max_steps=25, # <-- DEFECT: Stops after 25 steps (200 samples), not full epochs
    learning_rate=2.0e-4,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    logging_steps=2,
    eval_strategy='steps',
    eval_steps=5,
    optim='adamw_8bit',
    weight_decay=0.05,
    lr_scheduler_type='cosine',
    neftune_noise_alpha=5,
    seed=42,
    report_to='none',
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
    dataset_text_field='text',
    max_seq_length=max_seq_length,
    dataset_num_proc=2,
    packing=False,
    args=training_args,
)

# Mask instruction/prompt tokens so cross-entropy loss is computed ONLY on model turns
trainer = train_on_responses_only(
    trainer,
    instruction_part='<start_of_turn>user\n',
    response_part='<start_of_turn>model\n',
)

train_stats = trainer.train()

# ==============================================================================
# CELL 4: EXPORT LORA ADAPTER WEIGHTS
# ==============================================================================
ADAPTER_DIR = WORKING_DIR / 'submission' / 'adapters' / 'main_lora'
ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
model.save_pretrained(str(ADAPTER_DIR))
tokenizer.save_pretrained(str(ADAPTER_DIR)) # <-- NOTE: Saves 33MB tokenizer into adapter dir
```

---

## 2. Current Dataset Builder (`scripts/build_unsloth_dataset.py` Excerpt)

```python
SYSTEM_PROMPT = (
    "You are the Autonomous Software Developer fixing Python defects in /workspace.\n"
    "Tools: read_file, edit_file, write_file, get_status, submit_patch.\n"
    "Skills: fast-grep, code-map, code-oracle, repro-check, test-gate."
)

def slice_trajectory_decisions(
    task_id: str,
    repo: str,
    user_prompt: str,
    messages: List[Dict[str, Any]],
    tokenizer: Any = None
) -> List[Dict[str, Any]]:
    """Slices a full trajectory into high-density decision windows centered on assistant actions."""
    samples: List[Dict[str, Any]] = []

    for i, m in enumerate(messages):
        if m.get("role") != "assistant":
            continue
        if is_banned_turn(m):
            continue
        if not m.get("content") and not m.get("tool_calls"):
            continue

        window = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        # Include up to 2 preceding interaction turns (e.g., prior assistant action + tool result)
        start_ctx = max(0, i - 2)
        for ctx_idx in range(start_ctx, i):
            window.append(messages[ctx_idx])

        # Target assistant turn
        window.append(m)

        samples.append({
            "task_id": task_id,
            "repo": repo,
            "messages": window,
            "target_turn_index": i,
            "target_tools": [tc.get("function", {}).get("name") for tc in m.get("tool_calls", [])],
            "estimated_tokens": tok_len,
        })
    return samples

def render_gemma_chat_turns(messages: List[Dict[str, Any]]) -> str:
    """Renders structured messages into Gemma turn markers."""
    turns: List[str] = []
    for msg in messages:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        tool_calls = msg.get("tool_calls", [])

        if role == "system":
            turns.append(f"<start_of_turn>system\n{content}<end_of_turn>")
        elif role == "user":
            turns.append(f"<start_of_turn>user\n{content}<end_of_turn>")
        elif role == "assistant":
            parts = []
            if content:
                parts.append(content)
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    fn_args = fn.get("arguments")
                    parts.append(f"<|tool_call|>call:{fn_name}{fn_args}<|tool_call|>")
            asst_body = "\n".join(parts)
            turns.append(f"<start_of_turn>model\n{asst_body}<end_of_turn>")
        elif role == "tool":
            turns.append(f"<start_of_turn>tool\n{content}<end_of_turn>")
    return "\n".join(turns)
```

---

## 3. Live Agent Configuration (`submissions/track1_live/agent.yaml`)

```yaml
name: main
model: gemma-4-31b-it-qat-w4a16-ct
instruction: !include prompts/main.md
tools:
  - run_command
  - read_file
  - edit_file
  - write_file
  - get_status
  - submit_patch
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
skills:
  - skills/code-map
  - skills/fast-grep
  - skills/code-oracle
  - skills/repro-check
  - skills/test-gate
generate_content_config: !include configs/sampling.yaml
```

---

## 4. Verbatim Sample from `training/sft_data/unsloth_sft_train.jsonl`

Below is an actual decision-window sample (`rich_3905`, target tool `edit_file`):

```json
{
  "task_id": "rich_3905",
  "repo": "Textualize/rich",
  "target_turn_index": 15,
  "target_tools": ["edit_file"],
  "estimated_tokens": 1142,
  "messages": [
    {
      "role": "system",
      "content": "You are the Autonomous Software Developer fixing Python defects in /workspace.\nTools: read_file, edit_file, write_file, get_status, submit_patch.\nSkills: fast-grep, code-map, code-oracle, repro-check, test-gate."
    },
    {
      "role": "user",
      "content": "You are evaluating a software engineering task for repository Textualize/rich.\n\nProblem Statement:\nUpdate progress.py\n\nDon't output extraneous blank line when progress display is disabled..."
    },
    {
      "role": "assistant",
      "tool_calls": [
        {
          "id": "call_7",
          "type": "function",
          "function": {
            "name": "run_skill_script",
            "arguments": "{\"skill_name\": \"fast-grep\", \"args\": [\"disable\", \"tests/test_progress.py\"], \"file_path\": \"grep.py\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_7",
      "name": "run_skill_script",
      "content": "{\"skill_name\": \"fast-grep\", \"file_path\": \"grep.py\", \"stdout\": \"[fast-grep] Search: 'disable' (5 matches, top 2 scopes flashed)...\", \"stderr\": \"\", \"status\": \"success\"}"
    },
    {
      "role": "assistant",
      "tool_calls": [
        {
          "id": "call_9",
          "type": "function",
          "function": {
            "name": "edit_file",
            "arguments": "{\"filepath\": \"rich/progress.py\", \"old_string\": \"def stop(self) -> None:\\n        \\\"\\\"\\\"Stop the progress display.\\\"\\\"\\\"\\n        self.live.stop()\\n        if not self.console.is_interactive and not self.console.is_jupyter:\\n            self.console.print()\", \"new_string\": \"def stop(self) -> None:\\n        \\\"\\\"\\\"Stop the progress display.\\\"\\\"\\\"\\n        self.live.stop()\\n        if (\\n            not self.disable\\n            and not self.console.is_interactive\\n            and not self.console.is_jupyter\\n        ):\\n            self.console.print()\"}"
          }
        }
      ]
    }
  ],
  "text": "<start_of_turn>system\nYou are the Autonomous Software Developer fixing Python defects in /workspace.\nTools: read_file, edit_file, write_file, get_status, submit_patch.\nSkills: fast-grep, code-map, code-oracle, repro-check, test-gate.<end_of_turn>\n<start_of_turn>user\n...<end_of_turn>\n<start_of_turn>model\n<|tool_call|>call:run_skill_script{\"skill_name\": \"fast-grep\", \"args\": [\"disable\", \"tests/test_progress.py\"], \"file_path\": \"grep.py\"}<|tool_call|><end_of_turn>\n<start_of_turn>tool\n...<end_of_turn>\n<start_of_turn>model\n<|tool_call|>call:edit_file{\"filepath\": \"rich/progress.py\", \"old_string\": \"def stop(self) -> None:\\n        \\\"\\\"\\\"Stop the progress display.\\\"\\\"\\\"\\n        self.live.stop()\\n        if not self.console.is_interactive and not self.console.is_jupyter:\\n            self.console.print()\", \"new_string\": \"def stop(self) -> None:\\n        \\\"\\\"\\\"Stop the progress display.\\\"\\\"\\\"\\n        self.live.stop()\\n        if (\\n            not self.disable\\n            and not self.console.is_interactive\\n            and not self.console.is_jupyter\\n        ):\\n            self.console.print()\"}<|tool_call|><end_of_turn>"
}
```
