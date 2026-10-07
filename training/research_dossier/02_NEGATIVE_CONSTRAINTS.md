# 02. Negative Constraints & Architectural Rejections

To avoid repeating previous failure modes, this document codifies what we **MUST NOT DO** and the empirical reasoning behind each exclusion.

---

## 1. NO Heterogeneous / Second LLM Architectures
- **The Constraint:** We will NOT attempt to route between multiple LLMs (e.g., using GPT-4 for planning and Gemma for coding, or running a 7B router alongside 31B).
- **Why:**
  1. **Strict Competition Rules:** The Kaggle scoring container has zero internet connectivity. All external model APIs (OpenAI, Anthropic, Gemini, Vertex AI) are physically blocked at the network interface.
  2. **Single-Process Server Architecture:** The Kaggle evaluation runtime spins up a single local vLLM instance serving `gemma-4-31b-it-qat-w4a16-ct` across 4× L4 GPUs (`--tensor-parallel-size 4`).
  3. **ADK Declarative Constraint:** All sub-agents declared in `sub_agents/*.yaml` share this identical local vLLM backend. Any architectural proposal relying on a second model is physically impossible in the scoring runtime.

---

## 2. NO Omitting `run_command`
- **The Constraint:** We will NOT remove or suppress the `run_command` tool.
- **Why:**
  1. **The 0.03 Root Cause:** In Track 1 v2, removing `run_command` dropped our score from the ~0.12 baseline envelope down to 0.03.
  2. **Feedback Loop Absence:** Without `run_command`, the agent cannot execute `python -m py_compile <file>`, cannot run ad-hoc reproducers in `/tmp/repro.py`, and cannot run `pytest -x -q -k <name>`. It is forced to guess edit correctness purely in-memory.
  3. **The 0.12 Baseline Proof:** Both Roman Rozen (0.12) and S2 (0.08) center their entire agent prompt around:
     `Reproduce in /tmp/repro.py -> edit_file -> python -m py_compile -> pytest -> submit_patch`.

---

## 3. NO BitsAndBytes NF4 / Mismatched Quantization Lineage
- **The Constraint:** We will NOT use `unsloth/gemma-4-31B-it-unsloth-bnb-4bit` or standard HuggingFace BnB NF4 for LoRA training.
- **Why:**
  1. **The Oct-4 0.00 Disaster:** On Oct 4, our submission shipped an adapter trained against BnB NF4. Kaggle's vLLM backend runs Google's official QAT 4-bit checkpoint (`google/gemma-4-31b-it-qat-w4a16-ct`).
  2. **Quantization Scale Clashes:** BnB NF4 and QAT W4A16 use fundamentally incompatible scale packing and rounding math. When vLLM loaded the BnB LoRA onto the QAT base, weight decompression produced NaNs, causing 77 out of 95 traces to emit 0 completion tokens on Turn 1.
  3. **Mandatory Lineage:** LoRA training must strictly mount **`google/gemma-4-31B-it-qat-q4_0-unquantized`** (the exact official sibling checkpoint published by Google for fine-tuning).

---

## 4. NO Single-Turn "Unified Diff" SFT Datasets
- **The Constraint:** We will NOT train on static `(problem_statement) -> (git diff)` prompt-response pairs.
- **Why:**
  1. **Harness Execution Mismatch:** SWE-Gemma is an interactive ADK environment. The agent must emit structured function calls (`read_file`, `edit_file`, `run_command`, `submit_patch`), parse tool return values, and iteratively isolate bugs.
  2. **Action Collapse:** Models trained on single-turn diffs hallucinate markdown diff blocks in plain text instead of executing ADK tool calls, leading to 0 extracted patches in Container A.
  3. **Mandatory Schema:** SFT data must consist of multi-turn conversational tool trajectories with assistant-only loss masking (`train_on_responses_only`).

---

## 5. NO Runaway Context / Unbounded Thinking Budgets
- **The Constraint:** We will NOT configure `max_output_tokens: 16384` with unpruned observation histories.
- **Why:**
  1. **Hard 32K Boundary:** The serving model has a fixed 32,768 context limit.
  2. **Real-Harness Death Proof:** In S2 traces, task `rich_3772` crashed with:
     `litellm.ContextWindowExceededError: prompt contains at least 30721 tokens + requested 2048 output tokens > 32768`.
  3. **Mandatory Ceiling:** Trajectories must be bounded, repetitive tool outputs (like full directory trees or huge file reads) must be compacted, and sampling must stay frugal (`max_output_tokens: 4096-8192`, `thinking_budget: 4096`, `include_thoughts: false`).

---

## 6. NO LoRA on MLPs or High Rank ($r > 8$)
- **The Constraint:** We will NOT train adapters on MLP projections (`gate_proj`, `up_proj`, `down_proj`) and will NOT exceed Rank 8.
- **Why:**
  1. **Catastrophic Forgetting:** Fine-tuning dense 31B MLP layers on a few hundred SWE tasks destroys general Python syntax understanding.
  2. **Artifact Bloat:** Adapting MLPs balloons adapter size from ~15 MB to >90 MB, risking vLLM loading latencies and memory limits.
  3. **Attention Focus:** Target modules must be restricted to attention projections: `q_proj`, `v_proj`, `o_proj` (Rank 8, Alpha 16).

---

## 7. NO Scratch Files in `/workspace`
- **The Constraint:** We will NEVER allow the agent to create reproducers or temp files in `/workspace`.
- **Why:**
  1. **Container A Diff Extraction:** The submission patch is extracted via:
     `git add -N . && git diff HEAD`.
  2. **Container B Rejection:** Any file left in `/workspace` becomes part of the diff. Hidden tests in Container B will reject the patch or fail with untracked file conflicts.
  3. **Mandatory Scratchpad:** All repro scripts and scratch files must strictly reside in `/tmp`.
