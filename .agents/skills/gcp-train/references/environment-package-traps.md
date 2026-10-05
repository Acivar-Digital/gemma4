# Environment, Package Mismatches & Container Traps Reference

This reference documents the historical package mismatches, outdated image libraries, and container environment collisions encountered across the competition runner, evaluation containers, and GCP Deep Learning VMs.

---

## 1. Missing Test Dependencies in Container A (The "False Failure" Trap)

### Problem
In the SWE-Gemma evaluation container (**Container A**), target repositories under test often rely on third-party test dependencies that are **not** pre-installed in the evaluation image:
* **FastAPI:** Multiple expansion tasks failed during test collection because `inline-snapshot==0.21.1` and `executing==2.2.0` were missing.
  ```text
  ModuleNotFoundError: No module named 'inline_snapshot'
  ```
* **Offline Barrier:** Because Container A runs completely air-gapped without internet access, commands like `pip install inline-snapshot` fail immediately.

### The Agent Trap
When Gemma observed test collection failures, it frequently diagnosed the issue as broken codebase code, wasting 10–20 tool calls attempting pip installs or searching tutorials. Eventually, the agent would edit files in `tests/`, `conftest.py`, or `pyproject.toml` to bypass the missing fixture.

### Container B Discard Policy
**Container B strictly enforces `git checkout HEAD` and `git clean -f` on all test and config paths** before applying the official held verification patch.
* Any edits made to test files or runner configs are completely erased.
* If the agent did not repair the production source in `/workspace`, Container B fails the task with `resolved = False`.

### Remediation Protocol
* Treat all test files as strictly **read-only oracles**.
* Never attempt `pip install` inside evaluation containers.
* Distinguish between test harness setup failures and true functional assertions.

---

## 2. Python Import Path Collision (`site-packages` vs `/workspace`)

### Problem
In repositories using a `src/` layout (e.g. `requests`, `httpx`), the base Python environment in Container A already contained pre-installed versions of these libraries in `/usr/local/lib/python3.12/dist-packages/requests`.
* When an agent edited `/workspace/src/requests/utils.py` and ran a reproducer:
  ```bash
  python3 -c "import requests; ..."
  ```
  Python's default `sys.path` loaded the **system distribution**, completely ignoring the edited code in `/workspace/src/`.
* The agent saw identical error behavior after editing, concluded the patch failed, and entered thrashing loops editing the file 20+ times.

### Remediation Protocol
Always set explicit Python path isolation when executing commands in `run_command`:
```bash
PYTHONPATH=/workspace/src:/workspace PYTHONSAFEPATH=1 python3 -c "..."
```

---

## 3. Organizer Wheelhouse Conflicts & Offline Constraints

### Problem
The competition organizers provided `gemma-4-developer-agent-wheelhouse`, but several wheels clashed directly with Kaggle’s base Python 3.12 image:
* Conflicting ancillary pins for `opentelemetry`, `prometheus-fastapi-instrumentator`, and `xgrammar 0.2.6`.
* Naive `pip install` commands attempted unconstrained upgrades that broke the base `torch 2.10.0` / CUDA 12.8 / 13.0 GPU driver stack.

### Remediation Protocol
* Construct a locked, hash-verified supplementary wheel bundle (`gemma-reproducibility-wheels`, 35 wheels).
* Use strict constraint manifests (`runtime-overlay-constraints.txt`).
* Always install with `--no-index` and `--constraint`:
  ```bash
  python3 -m pip install --no-index --constraint runtime-overlay-constraints.txt --find-links /kaggle/input/gemma-reproducibility-wheels adk-submission==0.2.11 google-adk==1.36.1 google-genai==2.11.0
  ```

---

## 4. Bridge & Host Library Bugs (`LiteLLM` and `google-adk`)

### LiteLLM Thinking Budget Mistranslation
* **Symptom:** On Oct 1, an evaluation run crashed with a 400 API schema rejection.
* **Root Cause:** LiteLLM mistranslated `thinking_level=2` into a `reasoning_effort` string that the Google ADK/vLLM bridge rejected.
* **Workaround:** Blanket-disabled thinking in sampling configs as an immediate hotfix (`thinking_budget: 0`), and calibrated single-line reasoning constraints in prompts.

### ADK `SkillToolset` Tool Hallucination (`ValueError: Tool '<name>' not found`)
* **Symptom:** Agent tool calls to `fast-grep(...)` failed with `ValueError: Tool 'fast-grep' not found`.
* **Root Cause:** In Google ADK `1.36.1`, skills are managed under the experimental `FeatureName.SKILL_TOOLSET` and are **not** exposed as top-level tools.
* **Remediation Protocol:** Prompts must instruct the model to use meta-tools, describing the three parameters as plain key/value pairs rather than a Python-style call:
  ```json
  {
    "skill_name": "fast-grep",
    "file_path": "grep.py",
    "args": ["--pattern", "..."]
  }
  ```
  The parameter is `file_path`, **not** `script_name`. Presenting it as `run_skill_script(skill_name="...", file_path="...", args=[...])` inside a JSON block teaches the 4-bit quantized model to splice Python call syntax into JSON keys, which is the documented cause of the malformed-payload loop (see `cloud_results/canary_test_results/consultants/20261003/consultant3.md`, Failure Mode A).

---

## 5. GCP Deep Learning VM & Unsloth Driver/Kernel Quirks

### CUDA 13.0 and PyTorch 2.9.1+cu129
On the GCP DLVM image (`pytorch-2-9-cu129-ubuntu-2204-nvidia-580`):
* Unsloth emitted deprecation warnings:
  ```text
  'has_cuda' is deprecated, please use 'torch.backends.cuda.is_built()'
  ```
* Batch configuration error:
  ```text
  Unsloth: Not an error, but Gemma4ForConditionalGeneration does not accept `num_items_in_batch`.
  ```
* **Response Loss Masking Discrepancy:**
  * Unsloth's `train_on_responses_only` failed to match `<start_of_turn>model\n` because Gemma 4's tokenizer tokenizes `\n` differently depending on whether it follows a special turn token or regular text.
  * Attempting strict response-only masking caused a complete training failure. The script safely fell back to full multi-turn sequence loss.

---

## 6. The Cross-Quantization Mismatch Trap (QAT vs. BNB-NF4)

### The 0.03 Public Leaderboard Autopsy
* On Oct 2, submission `56765397` scored **0.03** on the leaderboard.
* **Root Cause:** The agent mounted an adapter trained on `unsloth/gemma-4-31B-it-unsloth-bnb-4bit` (BitsAndBytes NormalFloat4) onto the competition's production base model: **`gemma-4-31b-it-qat-w4a16-ct`** (compressed-tensors INT4 QAT).
* **The "Quality Tax":**
  1. NF4 and QAT have completely different numeric weight distributions.
  2. LoRA deltas $\Delta W = A \cdot B$ calibrated against NF4 linear layers degrade severely when hooked into QAT base layers.
  3. The model suffers from repetition loops, corrupted JSON schemas, and immediate turn-1 crashes.

### The Mandatory Promotion Gate (`projects-48w`)
* **Never** mount an adapter to `my_submission/agent.yaml` without verifying it on the local 14-task gauntlet.
* Target adapter resolution rate must be $\ge 43.4\%$ (beating Track 1 baseline).
* The candidate must resolve the two known canary failure modes (`fastapi_14479` syntax splice recovery and `requests_7205` probe thrashing).
