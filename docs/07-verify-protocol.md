# 07 — Verify-Before-Submit Protocol

Source: HARNESS_README §8 + sample `system.md` §3–4 + locked decision #5.

## Rule: never submit an unverified or polluted patch

## 1. Repro lives in /tmp only
- Scratch repro via `run_command`: `python3 /tmp/repro.py` or `python3 -c "..."`.
- NEVER `write_file` a repro into `/workspace` — `submit_patch` runs
  `git add -N . && git diff --binary HEAD`, so any `/workspace/repro.py`
  pollutes the patch (gotcha #3).

## 2. Targeted single-file pytest only
- Form: `pytest tests/test_target.py -k test_feature -q` (one file, `-k` filter).
- NEVER bare `pytest`, `pytest .`, or `unittest discover` — full sweeps
  take minutes, burn the 50-call / 30-min budget, risk timeout.
- Broken unrelated tests are expected; ignore them, never fix test files.

## 3. Cleanup before submit
- `run_command`: `rm -f /workspace/repro.py` + `git status --porcelain`.
- Confirm only intended source files are dirty.
- Test-file edits (`test_*`, `tests/`, `conftest.py`, `pytest.ini`,
  `pyproject.toml`) are force-reset in Container B — patch must touch
  library code only.

## 4. submit_patch LAST (it is free)
- `submit_patch` + `get_status` cost 0 tool calls; loop exits right after.
- Order: verify → cleanup → `submit_patch` → check
  `patch_size > 0` + `files_changed > 0` → final summary text.

## Failure modes
| Symptom | Cause | Fix |
|---|---|---|
| Empty patch | only test files edited | edit source, resubmit |
| Bloated patch | repro left in /workspace | rm, resubmit |
| Timeout | bare pytest | single-file rerun |
