# 01. Current Situation & Architectural Baseline

## 1. Context & Objective
We are competing in the **Google Gemma 4 Developer Agent** Kaggle competition.
- **Metric:** SWE-bench style Resolution Rate across 129 hidden benchmark tasks (67 FastAPI, 48 Rich, 13 Requests, 1 HTTPX).
- **Current Public Leaderboard:**
  - Rank 1 (Solo Leader): **Yurnero — 0.24** (31 / 129 tasks resolved).
  - Ranks 2–5: **0.18** (23 / 129 tasks).
  - Ranks 6–20: **0.17** (22 / 129 tasks).
  - Starter Baselines: **0.08 – 0.12** (~10 – 16 tasks resolved).
- **Core Pivot:** Pure declarative prompt and tool engineering tops out between **0.17 and 0.18** because base Gemma 31B lacks internal fine-grained domain knowledge of complex FastAPI lifespan protocols and Rich render hierarchies. To reach $\ge 0.20$ and challenge 0.24, an adapter (Track 2) is required.

---

## 2. Score History & Hard Post-Mortem Evidence

| Run / Submission | Public Score | Key Characteristics | Root Cause / Post-Mortem Finding |
|---|---|---|---|
| **Oct-4 Shipped Tree** (`@8f96a94`) | **0.00** (0/129) | Shipped `adapter: main_lora` (90 MB) trained via Unsloth BnB NF4 | **Mismatched LoRA Lineage:** Base model was `unsloth/gemma-4-31B-it-unsloth-bnb-4bit` while Kaggle vLLM served `google/gemma-4-31b-it-qat-w4a16-ct`. Quantization scales clashed, crashing inference (77/95 traces emitted 0 completion tokens on Turn 1). |
| **Track 1 v2** | **0.03** (4/129) | Adapter-less; restricted 5 tools; no `run_command` | Agent had no shell access to run `/tmp/repro.py`, `python -m py_compile`, or `pytest`. Flying blind without execution feedback. |
| **Sample 2 (`prvsiyan`)** | **0.08** (10/129) | Adapter-less; all 9 tools; `reviewer` sub-agent; sampling 2048/2048/thoughts false | Proved that pure Gemma 31B with all 9 tools resolves ~8–10 tasks. Traces showed context limit deaths (`rich_3772` prompt reached 30,721 tokens). |
| **Starter Baseline (`ryanholbrook` / Roman)** | **0.12** (15/129) | All 9 tools; `code_analyzer` sub-agent (`skip_summarization: true`); dummy QAT adapter | Proved that the served vLLM container successfully loads and serves LoRA adapters if the base lineage is identical (`google/gemma-4-31b-it-qat-w4a16-ct`). |
| **Local Runs B01–B40** | *Quarantined* | 56/129 (43.4%) in B39; 50/77 (64.9%) in B40 | **Proxy Contamination:** Traces proved these runs were served by LiteRouter proxy (`stealth/space-bunny-alpha`), NOT Gemma 4. Completely quarantined. |

---

## 3. Current Live Track 1 State (`submissions/track1_live/`)
- **Model:** `gemma-4-31b-it-qat-w4a16-ct`
- **Adapter:** None (`enable_lora: false` / no adapter declared).
- **Tools (9 total):** `run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `search_similar_code`, `get_code_neighbors`, `get_code_subgraph`.
- **Pre-installed Skills (5 total):** `code-map`, `fast-grep`, `code-oracle`, `repro-check`, `test-gate`.
- **Validation Gates:** 14/15 PASS in `scripts/check_submission.py` (0 gating failures).
- **Archive:** Packaged `submission.zip` (124 KB, clean, zero pyc, zero dangling adapter weights).

---

## 4. The Track 2 Imperative
Track 1 is locked and verified as our safety floor. However, pure prompt engineering on an untuned base model cannot cross the 0.18 barrier.
We are now entering **Track 2: Unsloth LoRA Fine-Tuning**, targeting the specific failure modes of base Gemma 31B on SWE tasks.
