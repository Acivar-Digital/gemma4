# 03 — Baseline Kill-Log (lead-owned, 2026-09-28)

Baseline: `sample_submission/agent.yaml:1-18` root holds ALL 9 tools + agent_tool; `code_analyzer.yaml:6-10` duplicates 3 graph + read_file. `system.md:4` says finish in 8–10 turns; sample eval_config ships 10 calls (HARNESS:533,541) vs CLI recipe 50.

Top 3 kill patterns (lead read, file:line):
1. Root self-explores (no isolation benefit). Root owns `search_similar_code/get_code_neighbors/get_code_subgraph` (agent.yaml:12-14) so raw graph JSON lands in root history despite `skip_summarization:true` wrapper (agent.yaml:15-17). With fastapi 86.8% tutorial noise (02), 2–3 dumps = compaction cliff. HARNESS:668-669 blesses delegation; baseline doesn't use it.
2. /workspace repro pollution + test edits. `submit_patch` = `git add -N . && git diff HEAD` (HARNESS:663-667); `system.md:31-35` bans test edits, §18-23 bans bare pytest. One `repro.py` in /workspace or one `tests/` edit = failed patch.
3. <|tool_call|> truncation on mega-edits. `system.md:14` minimal fix, HARNESS gotcha #1: thinking 4096 + output 16384; 155-hunk compat patch (fastapi_14609) cannot be one edit_file — must split.

Always-delegate cost (your Q6): +1 root `agent_tool` hop per investigation. Inner searcher calls run under same 50-call budget (no free-pass except submit_patch/get_status — HARNESS:400,409). Pays only if it prevents ≥2 root re-reads. On trivial single-file (rich_4077, requests_6589) it's pure overhead. On noisy multi-file it saves the trajectory. Verdict: Always-delegate is affordable at 50 calls, fatal at sample 10 calls — another reason Q1 50/30 was correct.
