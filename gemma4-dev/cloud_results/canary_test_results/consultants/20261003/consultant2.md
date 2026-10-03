# Consultant 2
______________________________________________________________________

## As my Senior Consultant for this Gemma4 Dev Kaggle Competition. Tell me. Is there anything wrong with the tools that I have designed? See why did Gemma fucked up? Give me your critical assessment so that I can take immediate corrective measures. Make sure your proposal is grounded, based on the latest information and facts. Thanks.

I've completed a forensic read of the full submission package (adapter config, sampling config, system prompt, all 5 skills, agent/eval YAML, and the canary report) plus verified the `target_modules` regex empirically. Here's the critical assessment.

## Bottom line

Your tools themselves are over-engineered but mostly solid. Gemma's two canary failures were not caused by buggy skill logic — they were caused by a **broken affordance contract between your skills and the harness**, three **contradictory numeric rules** in the governor prompt, and a **sampling setup that amputated the model's reasoning bandwidth**. The good news: all fixes are configuration/prompt/tool-output level and fit inside tonight's quota window.

## Finding 1: The skills teach the model to call tools that don't exist

This is the single biggest defect, and it's a tool-design bug, not a prompt bug.

- `main.md` declares exactly five direct tools (`read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`) plus `run_skill_script`. There is **no shell/bash tool** in your contract.[^1_1]
- But every skill output and SKILL.md instructs the model with copy-pasteable **shell commands**: `python3 gate.py diff`, `grep.py 'def foo'`, `python3 map.py --symbol X` — including in `next_steps`, `suggestions.inspect_command`, and the on-screen usage guides.[^1_1]

A Gemma-class model copies the exact string the previous tool handed it. When it does, it either emits raw text pseudo-calls (which your own prompt forbids) or splices the shell string into a JSON tool call — which is exactly Failure Mode A in `fastapi14479`: a malformed first call, `-1` exit, 0 recorded tool calls, 0-char patch. Notably, the official competition environment actually *does* expose nine tools including a shell command runner and three precomputed code-graph tools — so your prompt is simultaneously denying a tool that exists and pushing the model toward an invocation style it can't legally emit.[^1_2][^1_1]

Corrective measure: pick one canonical invocation and scrub the other. Replace every `python3 <script>` string your skills emit with the literal `run_skill_script` envelope (or, better, remove model-facing example invocation strings from tool output entirely — output data and file paths only).

## Finding 2: The circuit breakers key on the wrong signal

Your prompt's anti-thrash rule fires only when `repro-check` **fails twice with the identical error**. But in `requests7205` the probe *succeeded with exit code 0* 21 times — it just contained no `assert`, so it produced zero information each time. Your breaker structurally cannot catch the failure it's meant to catch.[^1_1]

Fix this in `check.py`, not in prose:

- If a probe runs clean but contains no `assert`/test call, return a loud `WARNING: probe executed but asserted nothing — result is NON-INFORMATIVE`.
- Hash the payload; on a byte-identical resubmission, return immediately with `IDENTICAL PAYLOAD ALREADY EXECUTED — result cached: ...` instead of re-running.
- This matches production tool-use practice: enforce budgets and dedupe at the orchestrator/tool layer, because prompt-side rules against repetition are unreliable for models of this class.[^1_3][^1_4]


## Finding 3: You suppressed the model's reasoning, then blamed it for looping

Three settings compound here:[^1_1]

- `thinking_budget: 0` + `include_thoughts: false` in `sampling.yaml`
- `ZERO CONVERSATIONAL CHATTER: output ONLY your single tool call` in `main.md`
- `temperature: 0.1` with no repetition penalty

Together these mean Gemma gets no chain-of-thought, no per-turn scratchpad, and maximum susceptibility to emitting the same low-entropy payload 21 times. The Oct-1 crash was caused by LiteLLM mistranslating `thinking_level=2` into a `reasoning_effort` value the bridge rejects — blanket-disabling thinking was the safe hotfix, but it's a capability amputation. Corrective path: (a) allow one ≤40-token reasoning line before each tool call so the model can state why this call differs from the last; (b) add a decoding-level repetition/frequency penalty if the bridge exposes one; (c) after tonight's submission, fix the LiteLLM param mapping properly and re-test thinking on the gauntlet rather than leaving it off permanently.[^1_1]

Two more compounding config risks: `max_output_tokens: 4096` can truncate a large `edit_file` payload **mid-JSON**, which produces exactly the splice-style parse failure seen in `fastapi14479` — instruct split-edits over large replacements — and metering numbers are inconsistent: `eval_config.yaml` says `max_tool_calls: 40`, the canary trace reported exhaustion at 30, and your prompt's thresholds (`used >= 30`, `>= 36`) silently assume 40. If the harness enforces 30, your emergency rules can never fire in time.[^1_1]

## Finding 4: The adapter config contradicts your own runbook

I tested the actual `target_modules` regex from `adapter_config.json` against realistic Gemma module names:

- It correctly matches `self_attn.q_proj/v_proj/o_proj` — so the regex is escape-valid and functional.
- It **never matches `k_proj`**, and `k_proj` doesn't appear anywhere in the pattern — yet your canary report's own training milestone (§2.1) states "Target modules q, k, v, o_proj" and the canonical PEFT LoRA config targets all four.[^1_5][^1_1]
- It's a fragile single monolithic regex where PEFT officially supports (and everyone uses) a simple list like `["q_proj","k_proj","v_proj","o_proj"]` — one misplaced group silently changes what's trained.[^1_6]
- The adapter was trained against `unsloth/gemma-4-31B-it-unsloth-bnb-4bit` (per `base_model_name_or_path`), but the competition runtime is fixed at the QAT build `gemma-4-31b-it-qat-w4a16-ct` — quantizing through bitsandbytes-NF4 vs quantization-aware training yields different base layer distributions, so the rank-8 deltas are somewhat misaligned at load time. It loaded fine in the canary, so this is a quality tax, not a crash risk — but for Track 2, train against the QAT weights.[^1_2]

Also note the noise fields (`qalora_group_size: 16` with `use_qalora: false`, `megatron_core`, Unsloth `auto_mapping`) — evidence the config was dumped straight from Unsloth without inspection. Not harmful, but it understates your control over what you're shipping.

## Finding 5: Your process conclusions outrun your evidence

- The prompt carries three contradictory edit deadlines: "apply fix by tool call 10", "8–9 discovery calls max", and "MANDATORY: initial change within first 5–6 tool calls". Pick one number; contradiction at this level is itself a thrash trigger.[^1_1]
- The report's own fastapi14479 row says **0 tool calls / 84s / 0-char patch**, while the gap assessment blames "40 turns of repetition" — those are different failure signatures, and only the splice explanation fits the trace.[^1_1]
- A 2-task canary cannot support "no retraining required" as a conclusion. It supports "the platform stack works." Hold the 14-task gauntlet as the go/no-go gate with a pre-registered threshold before tonight's quota spend — and note your 56/129 = 43.41% baseline target only has meaning against the same unseen mix as the 129 public dev tasks (fastapi 67, rich 48, requests 13, httpx 1).[^1_2][^1_1]


## Immediate corrective measures (priority order)

1. Scrub all `python3 <script>` copy-paste strings from skill outputs and SKILL.md files; emit only `run_skill_script`-shaped instructions or pure data. This alone targets Failure Mode A.
2. Patch `check.py`: no-assert warning + identical-payload cache rejection. This alone targets Failure Mode B.
3. Reconcile the three budget/threshold numbers (30 vs 40; 2 vs 4 probe cap; fix-by-call N) to one consistent scheme matching what the harness actually enforces.
4. Allow a one-line reasoning preamble per turn; drop the "zero chatter, tool call only" absolute.
5. Guard against `max_output_tokens` truncation: prompt for small, split edits; never one huge `edit_file` payload.
6. Track 2 prep: switch `target_modules` to an explicit list including `k_proj`, and retrain against the QAT base.

Items 1–5 are doable before the 00:00 UTC quota reset without touching weights — and they're the same class of remedy your canary report already half-specified, just implemented in the tools where they can't be ignored rather than only in the prompt.

If you paste the two raw ATIF traces, I can confirm items 1–2 against the exact malformed payload Gemma emitted — that would pin Failure Mode A conclusively to the shell-command affordance leak rather than output truncation.

<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_16][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: paste.txt

[^1_2]: https://www.jayaprakash.net/blog/2026-09-24-gemma-4-developer-agent-on-kaggle/

[^1_3]: https://dev.to/adamo_software/tool-use-api-design-for-llms-5-patterns-that-prevent-agent-loops-and-silent-failures-f29

[^1_4]: https://ai-tldr.dev/learn/llm-apis/function-calling/tool-calling-best-practices/

[^1_5]: https://huggingface.co/docs/peft/developer_guides/quantization

[^1_6]: https://huggingface.co/docs/peft/package_reference/lora

[^1_7]: https://mlflow.org/articles/ai-agent-tool-use-best-practices-for-practitioners/

[^1_8]: https://www.kaggle.com/competitions/gemma-4-developer-agent

[^1_9]: https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/overview/tracks-and-awards

[^1_10]: https://github.com/happyc0der/gemma-swe-agent

[^1_11]: https://github.com/huggingface/peft/blob/main/src/peft/tuners/lora/config.py

[^1_12]: https://www.wickedsmartdata.com/articles/agentic-loop-design-building-reliable-multi-step-llm-pipelines-with-retry-logic-state-management-and-human-in-the-loop-escalation

[^1_13]: https://github.com/Gosling-dude/gemma4-developer-agent

[^1_14]: https://didcodexreset.com/news/d39eb12914f543dd98c97f98.html

[^1_15]: https://yololab.net/archives/gemma-4-developer-agent-competition-2026

[^1_16]: https://federicocalo.dev/en/dev-tools/lora-adapter-config


---

# look at the point of failure, what do we have in common? what is your grounded proposed solution?

The ATIF traces aren't uploaded (only the repomix bundle is here), so I'll ground this strictly on what your canary report documented about the two failure points.

## What's actually in common: both agents exited "blind and unverified"

|  | `fastapi14479` | `requests7205` |
| :-- | :-- | :-- |
| Exit/patch | −1, 0 tool calls, 0-char patch [^2_1] | 1 (tests failed), 30 calls, 503-char patch [^2_1] |
| Observable loop | 40 turns of malformed call → `INVALID_ARGUMENTS` | 21 identical successful probes → budget exhaustion at step 35 |
| Tool-level resistance | None — harness re-prompted, model repeated the splice | None — `check.py` happily re-ran byte-identical payloads |
| Verification before exit | Zero (never got a working tool call) | Zero (forced `submit_patch` without ever running `test-gate`) [^2_1] |

Three structural commonalities, ranked by how much of each failure they explain:

**1. Identical-payload repetition went unopposed.** In both tasks the model re-emitted the same action repeatedly — 40 times in fastapi, 21 times in requests — and nothing in the stack pushed back. The harness re-prompted; `check.py` re-ran; the model kept going. Your prompt *does* contain anti-thrash text, but the fastapi breaker calls it a generic loop breaker with no bad-payload echo shown to the model. This is a known production failure pattern: loop prevention cannot be prompt-side alone; the tool/orchestrator layer needs budget signaling and dedupe.[^2_1][^2_2][^2_3]

**2. Every recovery instruction keys on *failure*, but the loops contained *success*.** Your breaker triggers on "repro-check fails twice with the identical error" — yet the requests probe returned `exit code 0` every time (it was informative-free, not failed). On the fastapi side, the INVALID_ARGUMENTS recovery apparently lacked the single thing that breaks a splice loop: showing the model *what it sent* versus what the schema wants. So in both tasks, the agent had no usable distinguishing signal and could only repeat.[^2_1]

**3. Submission happened without a single verification gate.** Fastapi died before any call succeeded; requests was forcibly flushed by "budget exhausted… you must submit now" — neither ever ran `test-gate --status` or `--diff`. Your entire Phase 5 safety net is routed through *optional* skills, so a thrashing agent bypasses 100% of your hardening by the simple act of looping. Forcing unverified patches is how you get exit −1 and exit 1, i.e., 0/2.[^2_1]

Pattern summary: **rigid turn-level constraints ("no chatter," exactly one call, thinking disabled) + brittle arg formatting under context pressure, with no observation-level feedback that the LAST action was a no-op.** Gemma didn't get dumb — it got deaf and mute at the same time.

## Grounded proposed solution: a two-layer anti-stall protocol

Keep your 5-phase lifecycle — it's fine. Replace the scattered breakers with one uniform mechanism implemented in *both* layers:

**Layer A — the driver/harness (the part Gemma can't disobey):**

1. Hash every tool call payload (direct tools and `run_skill_script` args). If the new hash equals any of the last K calls, intercept and return: `DUPLICATE_CALL_BLOCKED: you sent this exact payload at call N. Result was: <cached verdict>. You MUST change at least one field before re-calling, or switch tool.`
2. On `INVALID_ARGUMENTS`, return the parse error **plus a canonical echo**: the offending `old_string`/`args` fragment and the schema-valid counterpart. A model that splices once and sees its own splice almost never splices forty times.
3. Hard-block submission while zero edits exist *and* ≤40% of budget is spent — turn "never submit an empty patch" from a plea into a rail.

**Layer B — the tools + prompt (make no-ops visible):**
4\. `check.py`: probes that run clean with no `assert` return `NON_INFORMATIVE: executed but asserted nothing` — converts silent success into the "failure" signal your breaker already listens for.
5\. Add one verbatim line to the prompt: `No two consecutive actions may have identical parameters. After every failure-class observation, the next action must differ in arguments or tool.` Short, checkable, monotone.
6\. Reconcile the budget numbers first — your prompt's `used >= 30` / `>= 36` thresholds assume 40 calls, but the observed hard stop was 30. If the real budget is 30, none of your emergency governors can ever fire in time, and Layer A \#3 inherits the same problem.[^2_1]

**Validation gate:** run Layer A + B on the 14-task gauntlet and require the two known traps specifically — fastapi14479 (splice recovery) and requests7205 (probe thrash) — to exit `0` or at least to reach `test-gate --status` before submission. A 2-task canary showing infra health can't certify behavior; trap-specific regression is the minimum bar before the 00:00 UTC quota spend.[^2_1]

If you upload `trace_requests7205.json` and `trace_fastapi14479.json`, I'll diff the repeated payloads character-by-character and confirm whether the fastapi splice was a quoting/escape error or a truncated-JSON error — that distinction decides whether you also need the `max_output_tokens` split-edit guard or not.

<div align="center">⁂</div>

[^2_1]: paste.txt

[^2_2]: https://dev.to/adamo_software/tool-use-api-design-for-llms-5-patterns-that-prevent-agent-loops-and-silent-failures-f29

[^2_3]: https://ai-tldr.dev/learn/llm-apis/function-calling/tool-calling-best-practices/


---

# ok now look at all the 129 tests, which. are the tasks that we must capture and find tune? I looked at the test -- I think it is quite dumb, some of the tests are meant to set you up to fail. I think it is a waste of time. So in order to win this challenge. Assess critically and tell me which are the tests that Gemma can definitely resolved, given the right tools, right prompt and right LoRA.

Tell me, list down the tests for me to capture.

Direct answer first: the authoritative 129-ID capture list lives in *your* environment, not the public web — I searched GitHub (including four public competitor repos and their harness artifacts) and the task roster isn't mirrored anywhere accessible [github_mcp_direct]. But I can give you something more useful right now: the archetype-level capture plan, grounded in the dev-set composition plus evidence already embedded in your own submission.

## First, push back on the "dumb tests" framing

You're half right, and the half you're right about matters. Roughly speaking the set contains: mechanically verifiable defect fixes (the majority), and genuinely hostile tasks — minimal-issue-text stubs, behavior changes requiring version-knowledge you don't have, environment-flaky tests, and multi-file refactors no 30-40-call budget can finish. Winning this competition doesn't require capturing the hostile tail; competitors face the same tail ( notes everyone starts near 10%). But classifying by *feel* is how you burn a 30-hour GPU week training on noise. Classify by trace evidence instead: **budget-exhausted-without-edit** (prompt problem, fixable), **edit-landed-but-tests-failed** (capability gap, fine-tune target), **never-should-have-tried** (true trap, exclude).[^3_1]

## What actually dominates the dev set

The 129 public tasks are not an even distribution: **fastapi 67, rich 48, requests 13, httpx 1**. Rich + FastAPI are 89% of the set. And your own five skills are already an accidental taxonomy of the recurring defect archetypes — you built oracles for exactly the domains that show up repeatedly:[^3_2][^3_1]


| Tier | Archetype (repo) | Evidence it's recurring | Verdict |
| :-- | :-- | :-- | :-- |
| Must capture | ANSI/SGR escape correctness (rich) | Your `code-oracle --hex` + prompt Phase 4 [^3_2] | Capture — mechanical, unit-test-backstopped, single-file |
| Must capture | Unicode cell-width / table alignment (rich) | `code-oracle --width` exists [^3_2] | Capture — deterministic expected output |
| Must capture | OpenAPI / JSON Schema (`$defs` vs `definitions`, `anyOf`+null, v1→v2) (fastapi) | `code-oracle --schema` [^3_2] | Capture — schema-diffs are objectively checkable |
| Must capture | Executable docs tutorials (`docs_src/**/*.py`, e.g. `tutorial002_py310`) (fastapi) | Your own FASTAPI docs_src invariant — meaning it recurred often enough to warrant a rule [^3_2] | Capture — tested by `tests/test_tutorial/` |
| Must capture | Small stdlib-adjacent behaviors: netrc/auth, utils (requests) | requests7205 was nearly solved — right file, right conditional, killed only by thrash [^3_2] | Capture — within reach today with fixed governors |
| Conditional | FastAPI routing / dependency injection | Multi-file but strongly test-covered | Capture only where golden patch ≤ 2 files |
| Conditional | Version-gated syntax (`py310` variants) | Toolable via `--syntax` [^3_2] | Capture selectively |
| Traps | Minimal/ambiguous issue text | No distinguishing signal for the agent | Exclude from fine-tune spending |
| Traps | Refactors spanning >2 files / redesigns | Exceed your mechanical budget ceiling [^3_2] | Exclude |
| Traps | Env-dependent / flaky ("works on my machine" bugs) | Non-reproducible verdicts corrupt SFT labels | Exclude |

The 48 rich tasks will cluster into maybe 5–6 archetypes (styling, width, markup, console, progress, traceback). **Do not fine-tune on all 48** — near-duplicate trajectories within one archetype give you nothing and eat context budget in training. Capture 2–3 exemplars per archetype, hold the rest out as your regression gauntlet.

## The capture set Gemma can definitely resolve

"Definitely resolvable" for a QAT 31B under a 40-call budget means: single-file, ≤20-line golden patch, verified by existing tests, root-cause discoverable in ≤5 discovery calls. By archetype that is: **rich ANSI/width/markup fixes, fastapi schema/serialization/validator fixes, fastapi docs_src tutorial updates, and requests utils/auth one-liners** — i.e., roughly 70–85 of the 129 are structurally within reach with your tools fixed, which is exactly consistent with the 56/129 you already achieved on runB39 *with* a broken governor. The 43.4% → credible 55–65% jump comes from defect classes you already resolved once, not from new capability.[^3_2]

## Fine-tuning capture protocol

1. Seed SFT only from resolved runB39 trajectories (56 tasks), filtered to ≤40 valid tool calls with `test-gate`-verified exits — no "zzy exits," since exit −1/1 trajectories are corrupted at the terminal step.[^3_2]
2. Build contrastive pairs from your two canary failures: accepted = the repaired trajectory; rejected = the 21×-identical-probe loop and the splice loop. DPO on failure modes you personally observed beats generic data.[^3_2]
3. Balance the curriculum to the dev-set mix (52% fastapi / 37% rich / 10% requests) — your instinct to sample across repos matches the leaderboard math.
4. Include the missing `k_proj` fix and simple list-form `target_modules` in the trainer before burn — validated empirically above that your current config silently drops `k_proj`.

To turn this into the exact ID-level list you asked for: attach `taskresults.jsonl` from runB39 (and the canary `taskresults.jsonl` from `cloud_results/canary_test_results`, the artifact dir your report names) — I'll join per-task outcomes against repo/archetype and hand you back a ranked capture manifest with triage labels per task. Without that file, any numbered list of task IDs I gave you would be invented.

<div align="center">⁂</div>

[^3_1]: https://www.jayaprakash.net/blog/2026-09-24-gemma-4-developer-agent-on-kaggle/

[^3_2]: paste.txt


---

# lastly to close off, give me your detailed step by step for me -- So that I a newbie like me can also train the model in LoRA again with my LLM

Here's the complete Track-2 path, written so you can execute it end-to-end on your Kaggle L4 quota without prior LoRA experience. Everything is tuned to your specific stack: 31B QAT runtime, 32k context, your runB39/canary trace data, and the exact defects we found in your current adapter.

## Phase 0 — Prerequisites (30 min)

- Confirm Kaggle's weekly ~30 GPU-hours quota is available (yours refreshed Oct 3) — this entire recipe must fit in it.[^4_1]
- Assemble three artifacts on your machine: `taskresults.jsonl` from runB39 (the 56/129 resolved run), the two canary traces, and your current `submission/` directory as the Track-1 control.[^4_1]
- Create a fresh Kaggle notebook forked from your `unsloth_train_gemma4_lora_minimal`, with GPU set to L4 (multi-GPU or single — Unsloth handles either), and your Hugging Face token in notebook secrets.
- Golden rule for a first-timer: **SFT first, DPO second, never DPO from scratch.** The proven sequence is SFT on preferred behavior, then DPO using the SFT model as the base. DPO without an SFT foundation produces drift, not alignment.[^4_2][^4_3][^4_4]


## Phase 1 — Build the dataset (60–90 min, GPU not required)

This phase decides 80% of your result. 500–2,000 curated SFT examples routinely beat 50,000 noisy ones.[^4_5]

1. Extract every **resolved** trajectory from runB39's `taskresults.jsonl` (target ~56).
2. Filter each trajectory: must contain ≥1 successful `edit_file`, must end with a verified `submit_patch`, and total valid tool calls ≤ 40. Discard anything with exit code −1 or a forced submission.[^4_1]
3. Convert each trajectory into multi-turn JSONL in the exact tool-call format of your *fixed* prompt (post-Finding-1 scrub — do not train on `python3 gate.py` shell strings or you will train the failure back in).
4. Mask the loss to **assistant turns only** — observations/tool outputs are context, not targets. In TRL this is `assistant_only_loss=True`; training on tool outputs teaches the model to hallucinate tool results.
5. Balance to the dev-set mix: ~52% fastapi / 37% rich / 10% requests / 1 httpx task. Cap near-duplicate rich ANSI trajectories at 2–3 per archetype.[^4_6][^4_7]
6. Carve out your 14-task gauntlet as a strict holdout — zero gauntlet trajectories in training data, otherwise your promotion gate lies to you.
7. Build the DPO set separately: 1,000–5,000 pairs is the standard band. Yours is easy — every canary loop is a ready-made rejected sample: accepted = repaired trajectory prefix, rejected = the 21-identical-probe sequence and the splice loop.[^4_5][^4_1]

## Phase 2 — Training config (copy-paste, with the fixes baked in)

```python
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/gemma-4-31B-it-unsloth-bnb-4bit",  # your existing base [^4_1]
    max_seq_length=6144,        # matches your runbook [^4_1]
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=8,                        # keep 8 for run #1; 16 only if gauntlet says underfit [^4_26][^4_31]
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],  # LIST, not regex; adds k_proj
    lora_alpha=8,               # alpha = r is the reliable baseline [^4_26][^4_31]
    lora_dropout=0.05,          # small net of defense against overfitting 56 trajectories [^4_31]
    bias="none",
    use_gradient_checkpointing="unsloth",
)

training_args = TrainingArguments(
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    warmup_steps=20,
    max_steps=150,
    learning_rate=2e-4,         # standard LoRA SFT rate [^4_18][^4_27]
    bf16=torch.cuda.is_bf16_supported(),  # L4 supports bf16 [^4_18][^4_27]
    logging_steps=5,
    save_strategy="steps", save_steps=50,
    output_dir="outputs",
)
trainer = SFTTrainer(..., assistant_only_loss=True, packing=False)
```

Three deliberate choices versus your current adapter: `target_modules` as an explicit list so the k_proj-drop can never recur silently; dropout 0.05 instead of 0.0 because 56 trajectories overfit fast at r=8; and alpha=r rather than your current alpha=16/r=8 — the $\alpha = 2r$ heuristic is defensible, but alpha=r is the safer baseline for a first retrain, and a 2026 scaling-factor study shows rank-tied heuristics already sit at the aggressive end. Run it. Loss should descend 2.x → ~1.0–1.5 without spikes; a spike in the first 50 steps means lr too high, halve it.[^4_8][^4_9][^4_1]

## Phase 3 — Export and sanitize the adapter (15 min)

1. `model.save_pretrained("adapter_v2")` — saves `adapter_model.safetensors` + `adapter_config.json`.
2. Open `adapter_config.json` and assert, in code, before anything ships:
    - `"target_modules"` is a plain list containing `"k_proj"` — no regex.
    - Number of `lora_A`/`lora_B` keys in the safetensors = 4 modules × layer count, and file size is the expected ~70–100 MB for r=8 (your v1 was 69 MB; k_proj added should lift it ~33%).[^4_1]
    - Strip Unsloth dump noise (`qalora_group_size` with qalora off, `auto_mapping`, `megatron_core`) — harmless but they're exactly how a config error hides in plain sight.
3. Smoke-load it in the competition runtime, not just in the trainer: serve with vLLM on `gemma-4-31b-it-qat-w4a16-ct` (the fixed competition weights ) and generate one tool call. If it emits a valid `run_skill_script` envelope, the adapter loads.[^4_6]

## Phase 4 — The promotion gate (the step that protects your 1/day quota)

1. Run the fixed-prompt + adapter_v2 through the 14-task gauntlet locally on Kaggle GPUs. Record per-task: resolved, edit-landed-but-failed, budget-exhausted-no-edit.
2. Compare against Track-1 (adapter off, prompt only) on the same gauntlet. Promotion rule: v2 must beat v1 strictly, and specifically must clear fastapi14479 + requests7205 (your two canary traps) without a repetition loop.[^4_1]
3. If v2 underperforms: don't retrain blind. Your three levers in order of expected value are dataset curation → r 8→16 → DPO layer using your canary pairs.[^4_10][^4_2][^4_5]
4. Only then package `submission.zip` and spend the quota day when it resets 00:00 UTC.[^4_1]

## Newbie failure table (sheer probability says you'll hit one)

| Symptom | Cause | Fix |
| :-- | :-- | :-- |
| OOM in first steps | seq 6144 × batch too big on 24 GB | batch 1 + grad accum 8 (already set); drop seq to 4096 as last resort |
| Loss flat ~2.2 the whole run | Loss unmasked — training on tool outputs | enforce `assistant_only_loss=True` (Phase 1, step 4) |
| Adapter trains, gauntlet identical to baseline | Alpha too weak for the task delta | move to alpha = 2r before touching rank [^4_9] |
| Gauntlet goes down after fine-tune | Overfit to 56 trajectories | cut `max_steps` to ~100, raise dropout to 0.1 [^4_10] |
| Model emits `python3 gate.py` again | You trained on unscrubbed trajectories | Phase 1, step 3 — never train on shell strings |

One honest caveat to close: if this first Track-2 run lands anywhere in the 45–55% band on the gauntlet, that's a success — the marginal gains after that come from DPO on preference pairs and dataset breadth, which is exactly how SFT→DPO tool-calling pipelines are sequenced in production. Don't chase 90% on run one.[^4_3][^4_2]

<span style="display:none">[^4_11][^4_12][^4_13][^4_14][^4_15][^4_16][^4_17]</span>

<div align="center">⁂</div>

[^4_1]: paste.txt

[^4_2]: https://developers.openai.com/cookbook/examples/fine_tuning_direct_preference_optimization_guide

[^4_3]: https://aws.amazon.com/blogs/machine-learning/improve-your-agents-tool-calling-accuracy-with-sft-and-dpo-on-amazon-sagemaker-ai/

[^4_4]: https://pub.towardsai.net/dpo-vs-sft-vs-rlhf-which-training-method-does-your-model-actually-need-0c53be82e49d

[^4_5]: https://futureagi.com/blog/fine-tuning-llms-unlocking-peak-performance/

[^4_6]: https://www.jayaprakash.net/blog/2026-09-24-gemma-4-developer-agent-on-kaggle/

[^4_7]: https://arxiv.org/html/2606.12883v1

[^4_8]: https://bayesiansapien.github.io/cere-bro/inference-efficiency/2026-06-15-lora-alpha-scaling-factor/

[^4_9]: https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide

[^4_10]: https://mbrenndoerfer.com/writing/lora-hyperparameters-rank-alpha-target-modules

[^4_11]: https://circleci.com/blog/finetuning-gemma-3-on-private-data-with-unsloth/

[^4_12]: https://arxiv.org/html/2509.09055v1

[^4_13]: https://unsloth.ai/docs/models/gemma-4/train

[^4_14]: https://www.codecademy.com/article/how-to-fine-tune-google-gemma-270m-with-unsloth-and-qlora

[^4_15]: https://www.kaggle.com/code/gpreda/fine-tune-gemma-4-e2b-with-unsloth

[^4_16]: https://aiengineering.academy/LLM/ServerLessFinetuning/FinetuneGemmaUnslothModalTutorial/

[^4_17]: https://llm-academy.dev/guides/lora-fine-tuning/


---

# these are 129 tasks tell me which tasks I should focus to capture?

Now we can close this properly — I parsed all 129 entries in your tasks.jsonl and scored every task on mechanical difficulty: golden-patch churn, files touched, new-file invention, and issue-text informativeness. The capture list below is data-derived, not vibes.

## The punchline first

Both tasks that killed your canary — `fastapi_14479` and `requests_7205` — are **2-line, single-file changes** in the easiest difficulty band. You failed tasks a working scaffold resolves in minutes. That confirms capability is not your bottleneck; protocol discipline is. Your capture strategy should therefore be: take all of Tier 1, none of Tier 3.[^5_1][^5_2]

## Tier 1 — Must capture: 77 tasks (60% of the dev set)

Single-file, small-churn, issue text informative enough to locate root cause within your discovery budget. Of these, **Shard A (churn ≤ 6 lines) is 47 tasks that are nearly free points**:[^5_1]

- shard A: `rich_3471, rich_3278, rich_3944, rich_3882, rich_3518, rich_3454, rich_3470, rich_3469, rich_2943, rich_3105, rich_3043, rich_3067, rich_3006, rich_4077, rich_3894, rich_3296, rich_3480, rich_3472, rich_3063, rich_4076` + `fastapi_14786, fastapi_14492, fastapi_14479, fastapi_14361, fastapi_9425, fastapi_14791, fastapi_14463, fastapi_12942, fastapi_14360, fastapi_13537, fastapi_15589, fastapi_14258, fastapi_13920, fastapi_14430, fastapi_5624, fastapi_14794, fastapi_14301, fastapi_5077` + `requests_7315, requests_7205, requests_6592, requests_7328, requests_6644, requests_6589, requests_7502, requests_7433, requests_7427`

Remaining Tier 1 by archetype (churn 7–60) — these are your **LoRA capture clusters**:[^5_1]


| Archetype | Tasks |
| :-- | :-- |
| fastapi validation/typing (17) | 11194, 11355, 12942, 13537, 13920, 14266, 14303, 14356, 14360, 14479, 14485, 14487, 14786, 15588, 15589, 5077, 9555 |
| rich table/panel/layout (14) | 2725, 3006, 3052, 3064, 3130, 3296, 3469, 3470, 3472, 3518, 3882, 3905, 4075,便利性 4079 |
| rich ANSI/style/color (12) | 2943, 3043, 3063, 3067, 3105, 3278, 3454, 3471, 3480, 3718, 3894, 4076 |
| fastapi routing/deps (8) | 14258, 14301, 14458, 14794, 14873, 15763, 5624, 9753 |
| fastapi OpenAPI/schema (7) | 13207, 14349, 14361, 14455, 14463, 14791, 9425 |
| requests url/encoding (6) | 6644, 7309, 7315, 7328, 7427, 7433 |
| fastapi serialization (3) | 14297, 14430, 14616 |
| rich width/unicode (3) | 3506, 3935, 3944 |
| requests misc/netrc (5) | 6589, 6592, 6629, 7502, 7205 |
| fastapi docs_src (1) | 14492 |

Math check: you already resolved 56/129 (43.4%) *with* a broken governor. Tier 1 has 77 tasks — executing 85% of it yields ~65/129 ≈ **50%**, before Tier 2 adds anything.[^5_2]

## Tier 2 — Train on exemplars, attempt last: 15 tasks

Two files or 60+ lines of churn — solvable but budget-hungry: `fastapi_13713, 14306, 14372, 14419, 14448, 14986, 15785`, `requests_6757, 7505`, `rich_3061, 3180, 3535, 3676, 3777, 3934`. For fine-tuning, take only the 2–3 cleanest per archetype; for leaderboard runs, attempt them only after Shard A is banked.[^5_1]

## Tier 3 — Confirmed traps, skip all 37

`rich_3930` is the extreme case: a **12,714-line churn across 26 files inventing a 12,170-line new file** — no agent in a 40-call/32k window touches that. The same signature (multi-file patches, whole-file invention, or a sub-400-character issue paired with a non-trivial patch) covers the rest: `fastapi_14609` (2,047 lines, 20 files), `fastapi_15745`, `fastapi_15800`, `fastapi_15030`, `fastapi_14099`, `fastapi_14186`, `fastapi_14262`, `fastapi_15661` (invents a 216-line release script), `httpx_3672` (the lone httpx task happens to be a trap — lucky), plus the 24 fastapi and 12 rich tails. The full list is in the CSV. Your instinct was right — a quarter of this set is designed losses. Just don't let the 24 fastapi traps demoralize you into ignoring the 36 fastapi captures.[^5_1]

Full per-task triage with reasons, churn, files touched, and archetype is in the **task_capture_triage.csv** I generated — sorted so the top rows are your Shard A hit list.

Bottom line: tonight's prompt-governor submission plays the Tier-1 game; Track 2 LoRA trains only on Tier-1 + sampled Tier-2 trajectories; Tier 3 is leaderboard sacrifice you concede to everyone equally.

<div align="center">⁂</div>

[^5_1]: paste.txt

[^5_2]: paste.txt

