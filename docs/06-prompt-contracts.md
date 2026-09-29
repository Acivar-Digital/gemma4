# 06 — Prompt Contracts: Tool Split + Return Schema

> Goal: two agents, zero tool overlap on exploration, one strict handoff shape.

## 1. Exact tool split

| Tool | Main (Executor) | Searcher (Investigator) |
|---|---|---|
| `run_command` | ✅ (tests, `/tmp` repro) | ❌ |
| `read_file` | ✅ confirm-only (1–2 calls) | ✅ free exploration |
| `edit_file` | ✅ | ❌ (read-only) |
| `write_file` | ✅ (source only) | ❌ |
| `get_status` | ✅ (free) | ❌ |
| `submit_patch` | ✅ (free, LAST call) | ❌ |
| `search_similar_code` | ❌ | ✅ |
| `get_code_neighbors` | ❌ | ✅ |
| `get_code_subgraph` | ❌ | ✅ |
| `agent_tool` (`skip_summarization:true`) | ✅ owns searcher ref | — |

Main holds 6 tools + 1 delegation ref. Searcher holds 4 (3 graph + `read_file`).

## 2. Searcher strict return schema

Every searcher reply MUST be exactly these 5 fields, ≤15 lines, no raw dumps:

```
file: <exact path, e.g. fastapi/routing.py>
lines: <start-end, e.g. 120-165>
root_cause: <1–2 sentences, mechanism not symptoms>
minimal_change: <1–3 sentences, function + edit direction>
confidence: <high | medium | low + 5-word reason>
```

Forbidden: full file contents, neighbor lists, subgraph JSON, multi-file essays.
If uncertain: return best candidate with `confidence: low` + what to check next.

## 3. Main delegation rule

- MUST call `ask_search_subagent` (the `agent_tool` ref) BEFORE any broad read
  when the issue gives no exact file+line, or when >2 files are candidates.
- Allowed root `read_file`: confirm the returned `file:lines` range only.
- After schema arrives: plan → incremental `edit_file` → `/tmp` repro →
  targeted single-file pytest → `submit_patch`.

## 4. Anti-patterns (auto-fail or budget-burn)

1. **No test edits**: never touch `tests/`, `test_*.py`, `conftest.py`,
   `pytest.ini` — Container B resets them; edits = wasted patch bytes.
2. **No `/workspace` scratch**: repro scripts go in `/tmp` (gotcha #3);
   `git add -N . && git diff HEAD` ships everything under `/workspace`.
3. **Incremental edits only**: small `edit_file` payloads (gotcha #1);
   big thought + big edit in one turn truncates `<|tool_call>`.
4. **No full-suite pytest**: never bare `pytest`; always one target file
   (`pytest tests/test_x.py -k test_y`). Existing breakages are ignored.
5. **No root graph wandering**: root calling graph tools directly defeats
   `skip_summarization` isolation — delegate or don't search.
6. **`submit_patch` last**: it is free but terminates the loop; verify
   (`patch_size > 0`, targeted test green) and clean `/workspace` first.
