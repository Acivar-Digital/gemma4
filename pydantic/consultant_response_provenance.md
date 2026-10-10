# Consultant Clarification: Candidate Trajectory Provenance & Audit Scope
**Document:** `pydantic/consultant_response_provenance.md`  
**In Response To:** Consultant Inquiry regarding Execution-Verified vs. Templated SWE-Zero/SWE-Smith Candidates  
**Date:** 2026-10-10  
**Repository:** `Acivar-Digital/gemma4`  

---

## 1. Direct Answer to the Fork

> **The 1,500 candidate tasks are TEMPLATED FROM SWE-ZERO / SWE-SMITH AS RELEASED, NOT execution-verified in our own SWE-Gemma harness.**

Specifically:
- Extracted via `pydantic/extract_gold_candidates.py` from raw upstream parquet shards:
  - `data/source_b/swe_zero/*.parquet` (SWE-Zero by SWE-bench / OpenHands team)
  - `data/source_b/swe_smith/*.parquet` (SWE-Smith synthetic/real trajectory corpus)
- They were **NOT re-executed** in our Docker evaluation containers (`swegemma_sandbox_*`).
- The observations (`observation`, `pytest` outputs, `grep` matches) embedded in the raw steps are the **historical stdout/stderr strings** recorded by the upstream agents (Claude 3.5 Sonnet / OpenHands) during their original runs.
- Our translation pipeline (`pydantic/translate_sft_dag.py`) is an **offline symbolic and token-alignment compiler**: it reconciles upstream actions and observations into our 5 declarative tools + 5 skills, formats them via Gemma 4's `chat_template.jinja`, and validates token prefix-delta alignment against `models/gemma-4-31b-it-qat-w4a16-ct`.

---

## 2. Implications for the Consultant's Audits

Because we are on the **Templated from Upstream as Released** branch, the audit narrows to the following specific failure modes and verifications:

### Fork A: Contamination & Leakage Audit (What Bites Hardest)

1. **Instance ID Exclusion vs. Repo Distribution:**
   - **Status:** Complete programmatic exclusion against `tasks.jsonl` (129 tasks: 67 fastapi, 48 rich, 13 requests, 1 httpx). No candidate has a matching `task_id` (`instance_id`).
   - **Audit Point for Consultant:** 
     - *Repo-level Overlap:* SWE-Zero / SWE-Smith contain tasks from Python repositories across GitHub (e.g., `scipy`, `django`, `sympy`, `flask`, `pytest`).
     - *Question:* Should we strictly enforce a **cross-repo train/val split** where any task belonging to `fastapi`, `rich`, `requests`, or `httpx` is completely purged from the 1,500 SFT candidates to prevent repo-specific stylistic leakage? (Currently, candidate tasks from other repos dominate, but repo distribution must be audited).

2. **Gold Patch Leakage in Prompts & Observations:**
   - **Status:** In SWE-Zero/SWE-Smith as released, tasks use the canonical SWE-bench `problem_statement` as the initial user message.
   - **Audit Point for Consultant:**
     - In some synthetic datasets (e.g. certain SWE-Smith shards), problem statements or comments occasionally include synthesized diff hints.
     - *Action:* Run an automated regex filter over `problem_statement` for diff syntax (`--- a/`, `+++ b/`, commit SHAs) to ensure zero unintentional leakage.

---

### Fork B: Pivot-Coverage & Observation Parity Audit (What Bites Hardest)

Because the translated trajectory is **not re-executed** in our sandbox during SFT data generation:

1. **Synthetic vs Real Skill Observations:**
   - Upstream trajectories executed raw bash commands (e.g. `python -m pytest tests/test_foo.py` or `grep -rn "pattern"`).
   - Our DAG translates `python -m pytest` into `run_skill_script(skill_name="repro-check", file_path="check.py", args=["..."])`.
   - In `ReconcileObservationsNode`, the returned observation is the **historical pytest output** from the upstream run.
   - **The Gap:** In our live sandbox, `run_skill_script` wraps output in a specific JSON/CLI envelope emitted by `check.py` or `gate.py`.
   - **Audit Question:** Does the mismatch between raw upstream pytest stdout and our skill runner's exact stdout wrapper create a minor format shift at test time?

2. **Upstream Pivot Quality (Red-to-Green Frequency):**
   - Since trajectories are templated as released, we inherit whatever pivot behaviors Claude/OpenHands exhibited.
   - **The Risk:** In many successful SWE-Zero runs, the agent:
     - Found the bug on Step 2.
     - Modified the file on Step 3.
     - Ran the test on Step 4 (passed).
     - Submitted on Step 5.
   - In these runs, the agent **never saw a failing test** during its own execution because it wrote the test after the fix or only ran the test once at the end.
   - **Consultant Audit Metric:** 
     - Parse `raw_steps` in `raw_candidates_1500.jsonl` to measure: *In how many of the 1,500 candidates does a test or assertion return a failure exit code BEFORE the final passing test?*
     - If this number is low ($<20\%$), the SFT dataset will teach the model that tests always pass on first execution.

---

## 3. Concrete Verification Data for the Consultant

To enable you to narrow your advice, here are the empirical characteristics of `pydantic/gold/raw_candidates_1500.jsonl`:

| Metric | Measured Value |
|---|---|
| **Total Candidates** | 1,500 |
| **Source Split** | 750 `swe_zero` / 750 `swe_smith` |
| **Benchmark Overlap with `tasks.jsonl`** | **0** (0.00%) |
| **Single-File Python Patch Invariant** | 1,500 / 1,500 (100.0%) |
| **Max Diff Lines** | $\le 300$ lines |
| **Raw Step Count Range** | Min: 7, Max: 38, Avg: 19.4, Median: 19 |
| **Tasks with $>30$ raw steps** | 30 / 1,500 (2.0%) |
| **Tasks with $>40$ raw steps** | 0 / 1,500 (0.0%) |

---

## 4. Key Questions for Consultant Advice

Given that the dataset is **templated from upstream as released**:

1. **Synthetic Skill Injection:**
   Should our translation DAG synthesize explicit pre-edit failing `repro-check` turns for trajectories that only ran tests post-edit, ensuring 100% of SFT trajectories exhibit the Red-to-Green pivot pattern?
2. **Observation Wrapper Alignment:**
   Should `ReconcileObservationsNode` normalize upstream bash outputs into the exact JSON envelope emitted by our production `check.py` and `gate.py` scripts (`{"exit_code": 1, "stdout": "...", "stderr": "..."}`)?
3. **Repo-Level Segregation:**
   Should we strictly eliminate all candidate tasks from `fastapi`, `rich`, `requests`, and `httpx` to guarantee zero intra-repo style bias, or does keeping them help the agent learn repository idiomatic conventions?

---
*Published to GitHub remote `gemma4 main` under `pydantic/consultant_response_provenance.md`.*
