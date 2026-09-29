# 04 — Five Baseline Killers (Theory)

Each killer: cause → harness mechanism → v1 mitigation pointer. No code; see `07-verify-protocol.md` for procedures.

## (a) Context Compaction Overflow

- **Cause:** Long trajectories (repeated full-file reads, verbose reasoning, raw graph dumps) push the prompt past the compaction point; summarized history loses exact `old_string` text needed for `edit_file`.
- **Harness mechanism:** `EventsCompactionConfig` (interval 5, overlap 2, `token_threshold 14336`, retention 5) auto-summarizes old events well before the 32K `max_model_len`. After compaction, previously read file contents are paraphrases, not byte-exact quotes.
- **v1 mitigation:** Main agent keeps `read_file` for short slices only; graph tools delegated to searcher via `agent_tool skip_summarization: true`; searcher returns strict schema (file, lines, root cause, minimal change, confidence) — no raw dumps. Re-read the exact target block immediately before each edit.

## (b) `<|tool_call|>` Truncation on Big `edit_file`

- **Cause:** A single huge `edit_file`/`write_file` payload plus long chain-of-thought exceeds `max_output_tokens`; the response is cut mid-tag so no tool executes that turn.
- **Harness mechanism:** Turn exits with unclosed `<|tool_call|>` → harness injects nudge: *"token limit before the tool call finished closing — do NOT repeat reasoning, emit next tool call immediately, split edit_file/write_file into smaller incremental edits."* Repeated hits burn `max_nudges = 3` and tool budget.
- **v1 mitigation:** Cap `max_output_tokens` 16384 / `thinking_budget` 4096 (sum ≪ 32K); keep reasoning to a few sentences before each call; split large rewrites into sequential small `edit_file` steps, one per turn.

## (c) `/workspace` Repro Pollution in Diff

- **Cause:** Scratch repro/verification scripts written inside the repo get swept into the submitted patch.
- **Harness mechanism:** `submit_patch` (and the no-submit fallback) runs `git add -N . && git diff HEAD` over ALL of `/workspace` — every new untracked file is included. `__pycache__`/`*.pyc`/`.pytest_cache` are excluded via `.git/info/exclude`, but `repro_*.py` scripts are not.
- **v1 mitigation:** All scratch repro goes in `/tmp` (never `/workspace`); only intended source-file edits remain in the diff. Check `get_status` (`files_changed`, `patch_size`) before submitting.

## (d) Test-File Edits Discarded in Container B

- **Cause:** Agent "fixes" the bug by editing tests, `conftest.py`, `pytest.ini`, or `pyproject.toml` instead of library code.
- **Harness mechanism:** Phase 2 `_is_protected_test_or_config_path` resets every file in `task.test_patch` plus `test_*.py` / `*_test.py` / `tests/` / `conftest.py` / `pytest.ini` / `pyproject.toml` / `tox.ini` / hooks via `git checkout HEAD -- <files>; git clean -f` BEFORE applying `test_patch`. Test edits silently vanish; the underlying bug remains → `resolved = False`.
- **v1 mitigation:** Never touch test or runner-config paths. Fix only library source under `/workspace`; treat tests as read-only oracles.

## (e) Bare `pytest` Timeouts + Broken Pre-Existing Tests

- **Cause:** Running the full suite (`pytest` with no target) exceeds the 300 s `run_command` timeout or trips over pre-existing failures unrelated to the issue, wasting the tool budget and masking the signal.
- **Harness mechanism:** `run_command` kills at `min(300 s, remaining_time)` → `TimeoutExceeded`; output truncated at 5,000 chars, so a full-suite log also overflows. Phase 2 itself runs only targeted `<pytest_targets>` with `-q -p no:anyio`, and requires `exit_code == 0` plus JUnit `passed > 0, failures = errors = 0` on exactly the FAIL_TO_PASS / PASS_TO_PASS nodes.
- **v1 mitigation:** Reproduce in `/tmp` first, then run a single targeted `pytest <file>::<test>` (one file max) mirroring the harness flags. Ignore unrelated red tests; optimize only for the FAIL_TO_PASS → pass transition without breaking PASS_TO_PASS.
