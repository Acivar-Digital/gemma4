# 09 — Gated Roadmap

Scope: theory-first. Code/YAML only after explicit approval.

## Phase 0 — Theory (docs 01–08) — **✅ COMPLETED**
- Finish 01–08 design docs from HARNESS_README + sample_submission.
- Gate: user approves theory before any YAML draft.

## Phase 1 — YAML draft (after approval) — **✅ COMPLETED (Superseded by single-agent 5-tool + 5-skill monolith in `submissions/track1_live/`)**
- Mirror `sample_submission` filenames (`agent.yaml`, `eval_config.yaml`,
  `configs/sampling.yaml`, `prompts/system.md` + `analyzer.md`,
  `sub_agents/code_analyzer.yaml`).
- Keep sample `sampling.yaml` (0.2 / 16384 / 4096); single model
  `gemma-4-31b-it-qat-w4a16-ct`; hybrid main + searcher via
  `agent_tool skip_summarization:true`.
- No LoRA adapters v1.

## Phase 2 — Local test + iterate — **❌ DROPPED / 🔄 SUPERSEDED 2026-10-05, never executable**

The original Phase 2 said "run locally, inspect traces, iterate until patches
resolve". **There is no local Gemma 4.** The competition model
`gemma-4-31b-it-qat-w4a16-ct` is served only by Kaggle, at
`google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2` on 4× NVIDIA L4 24 GB with
vLLM `tp=4`. Everything runnable locally resolves through a LiteRouter proxy and
records `model_name: stealth/space-bunny-alpha`.

Consequences, all measured:
- **0 tasks have ever been resolved on the real model** — 0/129 with exit-code
  histogram `{-1:115, 1:6, 2:5, 124:3}`, plus 0/2 and 0/3 canaries.
- Every historical baseline in this repo (**43.4% / 45.7% / 64.9%**, runs
  B35/B37/B39/B40) is a proxy number. `grep 'gemma-4-31b-it-qat' results/` → 0
  hits. **No number this repo has ever produced is a Gemma 4 number.**
- Therefore local iteration cannot gate anything. It can only validate syntax
  and plumbing. The single measuring instrument is one Kaggle kernel run.

## Phase 2b — Kaggle kernel bring-up (settled; the actual blocker) — **✅ COMPLETED**

Iteration is blocked by getting the harness to import at all. Three kernel
versions were spent here, and the fault was always *plumbing*, never the agent:

|Ver|Reached|Failure|
|---|---|---|
|v2|Phase 2 (11 s)|`ModuleNotFoundError: adk_submission`|
|v3|Phase 1|tag filter worked; `flashinfer-python` needs `apache-tvm-ffi`, which is cp312-only, so pip could not resolve it|
|v4|queued|wheelhouse scoring + announced `--no-deps` retry|

Two durable lessons from v3, both now encoded in
`kaggle_baseline_v1/baseline_v1.ipynb` Phase 1:

1. **The wheelhouse kernel is cp312; the kernel interpreter is CPython 3.13.**
   When wheels are passed to pip as explicit file paths, one incompatible wheel
   aborts the **whole batch**, so a partial install silently becomes *no*
   install. Filter with `packaging.tags.sys_tags()`. Never substring-match
   `cp312` — that also discards `cp38-abi3` / `cp39-abi3` / `cp310-abi3` wheels
   that a newer interpreter loads fine.
2. **Kaggle mounts a second wheel directory the notebook was ignoring.**
   `/kaggle/input/competitions/<comp>/wheels` (124 wheels) sits beside the
   attached wheelhouse dataset (41). `discover_wheelhouse()` sorted candidates
   by whether the path contained the literal string `"wheelhouse"`, so it picked
   the cp312 set by *name* while a better-fitting one was mounted. Selection is
   now **measured**: score every candidate by how many wheels this interpreter
   can load plus whether it can supply `adk_submission`, install from the winner,
   and print the scoring table so the choice is auditable in the log.

## Phase 3 — Measure (Track 1 Baseline) — **✅ COMPLETED (Scored 0.13 on Public Leaderboard, ref `56883026`; locked in `configs/baseline_registry.json`)**

Kernel `francisclyap/gemma4-baseline-v1` v4 is queued. On completion, read the
output in this order and stop at the first failure:

1. **Phase 3** — printed `submission.zip` sha256 must equal the pinned
   `bd4f31cd7971ef4df6910f6c5324259d8d337cc527b2f67549340a2f0745b05e`. A
   mismatch means the run measured something unshipped.
2. **Phase 4.5** — preflight: no `thinking_level` in `sampling.yaml`, no
   `adapter:` in `agent.yaml`, corpus task count is 129.
3. **Phase 4.6** — non-degeneracy verdict.
4. If non-degenerate: `exit_code_histogram.json` → `tasks_with_tokens` /
   `total_tasks` (expect ≥ 18/20), `tasks_with_tool_calls`,
   `tasks_with_nonempty_patch`.

**A `DEGENERATE` verdict is a serving-path fault, not a model result.** Report
it and stop. Do not escalate to GCP on the first zero; §5 of the recovery plan
prices GCP at $2–30 per identical run for no added fidelity.

## Phase 4 — Track 2 LoRA Master Plan (2026-10-08 — **ACTIVE**, Epic `gemma4-wzlk`)
- Full specification and phase status ledger published in **[`docs/workplan.md` §7](workplan.md#7-track-2-lora-master-plan-2026-10-08--active-workplan-epic-gemma4-wzlk)**.
- **Phase 4.1a (🔄 SUPERSEDED):** Initial 1,500-sample Source B draft (`500 swe_smith`, `500 swe_rebench`, `500 swe_zero`) superseded after empirical audit showed `swe_rebench` averages 51 tool calls (98.9% $>30$ calls, teaching budget thrashing) and multi-file diffs cause trajectory wandering.
- **Phase 4.1b (✅ COMPLETED — `sha256: 971ea376...` / `80ffa4e5...`):** Zero-leakage multi-turn SFT dataset (`scripts/build_unsloth_dataset.py`, `scripts/sft_data_filters.py`, `scripts/extract_source_b.py`) built and verified on disk (`data/unsloth_sft/train.jsonl`: **1,194 samples across 98 tasks**; `data/unsloth_sft/val.jsonl`: **306 samples across 27 disjoint tasks**; **1,500 total samples**, `750 swe_smith` + `750 swe_zero`, max `3,070 <= 3,072` tokens): (1) **100% single-file `.py` fixes**, (2) **$< 20$ clean tool calls AND $< 20$ negative tool calls** ($< 40$ total budget), (3) **Two-Kind Negative Call Filter**: keep **endgame-pivoting negative calls** (Red-to-Green test/repro failures or hypothesis-disconfirming probes that pivot to the fix) and exclude/scrub **dumb/stupid negative calls** (failed edits, bad paths/syntax, thrashing), (4) **`swe_smith` + `swe_zero` only** (`swe_rebench` dropped), (5) **Thinking MUST BE TURNED OFF during SFT** (`enable_thinking=False` in `chat_template.jinja`, ZERO `<|channel>thought` tokens in completions, direct `<|tool_call>call:` invocation with Turn-0 boundary reconciliation), and (6) **Official 262,144-Token Gemma 4 Vocabulary, Natural Template & Role Invariants**: formatted exclusively via `AutoTokenizer` + `apply_chat_template` from `models/gemma-4-31b-it-qat-w4a16-ct/` with `"role": "assistant"` preserved and `add_special_tokens=False` single-`<bos>` prefix-ID alignment (`full_ids[:len(prefix_ids)] == prefix_ids`).
- **Phase 4.2 (✅ COMPLETED (2026-10-08), Epic `gemma4-wzlk.6`):** Training script and template alignment completed and synchronized across `scripts/train_gemma4_unsloth_cloud.py`, `gcp/deploy_gemma4_lora.sh`, `scripts/build_unsloth_notebook.py`, and `scripts/build_unsloth_training_kernel.py`: (1) **Dual-Path Base Model Loader**: `google/gemma-4-31b-it-qat-w4a16-ct` primary path loaded natively via `compressed-tensors` + `llm-compressor` (`load_in_4bit=False, use_exact_model_name=True`); `google/gemma-4-31B-it-qat-q4_0-unquantized` fallback path with `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="fp4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=False)` to prevent scale drift; (2) **Inline vLLM Adapter Normalization Hook**: embedded `normalize_adapter_for_vllm()` hook rewriting keys to `base_model.model.language_model.model.layers.*` (340 BF16 tensors $\le 35.0$ MB); (3) **170 Attention Modules** (`["q_proj", "v_proj", "o_proj"]`, `k_proj` omitted per `attention_k_eq_v=True`, MLPs frozen); (4) **Strict BF16 Enforcement** (`bf16=True, fp16=False`); (5) **Pre-tokenized Prefix-Delta Masking** (`labels[:K] = -100` with `add_special_tokens=False`); and (6) **Automated Test Gate**: 6/6 tests passing in `tests/test_unsloth_sft_dataset.py`.
- **Phase 4.3 (✅ SCRIPT COMPLETED / ⏸️ RUN PENDING):** Post-training vLLM multimodal key normalization via `scripts/normalize_adapter_vllm.py` (`base_model.model.language_model.model.layers.*`, 340 BF16 tensors $<35\text{ MB}$).
- **Phase 4.4 (⏸️ PENDING):** Staging verification on Kaggle Compute under authentic vLLM `w4a16-ct`: **1–2 task cross-quantization adapter-loading smoke check** first, followed by the **14-task gauntlet (`gemma4-9r1`)** before any promotion to `submission.zip`.

## Do-NOT list
- NO `my_submission/` without explicit user approval.
- NO `agent.py` — declarative YAML only (`compile_submission`).
- NO bare `pytest` in agent instructions; NO test-file edits.
- NO repro files in `/workspace`; NO LoRA v1; NO `..` in `!include`.
- **NO treating a proxy score as a Gemma 4 result.** If a run did not record
  `gemma-4-31b-it-qat-w4a16-ct`, its number is not a quality signal — including
  the 43.4% / 45.7% / 64.9% figures that predate this correction.
- NO local iteration as a quality gate (see Phase 2 — it cannot be executed).
- NO selecting a wheelhouse or any runtime artifact by **name**; select it by
  measured compatibility with the interpreter that will actually load it.
- NO shipping an adapter until a real Gemma 4 baseline exists.
