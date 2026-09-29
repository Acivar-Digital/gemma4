# 01 — Competition: Metric, Lifecycle, Protocol

> Source of truth: `HARNESS_README.md` (671 lines). No YAML drafted here.

## 1. Metric: Resolution Rate

- Per-task binary: `resolved = True` (score `1.0`) iff hermetic `pytest`
  returns `exit_code == 0` **and** JUnit XML validates (`passed_tests > 0`,
  `failures == 0`, `errors == 0`, all `FAIL_TO_PASS` / `PASS_TO_PASS` nodes
  passed, none skipped) — `HARNESS_README.md:606-609`.
- Aggregate: `Resolution Rate = Resolved / Total ∈ [0.0, 1.0]`, computed by
  `score()` in `scripts/metric.py` — `HARNESS_README.md:610-611`.
- Diagram form: `exit_code == 0 & JUnit XML valid → Resolution Rate` —
  `HARNESS_README.md:61`.

## 2. Two-phase lifecycle

### Container A — agent sandbox (`HARNESS_README.md:216-237`)

1. Start sandbox, stage wheels, extract repo snapshot at `base_commit`
   (fresh `git fast-import` on branch `main`; zero future history —
   `HARNESS_README.md:262-263`).
2. Append artifact patterns to `.git/info/exclude`,
   `pip install -e /workspace --no-deps`, stream cached site-packages,
   write standard `pytest.ini` + hermetic `conftest.py`
   (`HARNESS_README.md:264-280`).
3. Baseline commit: `git add -A && git commit -m "baseline"`
   (`HARNESS_README.md:280-283`). The generated `pytest.ini`/`conftest.py`
   are inside `HEAD` — do not touch them (`HARNESS_README.md:284-285`).
4. Agent loop runs tools against `/workspace` (`TEST_TMPDIR=/tmp`,
   `network_mode="none"`, 4 GiB, 2 vCPUs — `HARNESS_README.md:248-253`).
5. Patch extraction: submitted patch, else fallback
   `git add -N . && git diff HEAD` (`HARNESS_README.md:235, 667`).

### Container B — verification (`HARNESS_README.md:238-244, 586-605`)

1. Fresh sandbox, repeat bootstrap, commit `eval_baseline`.
2. Apply `agent_patch` (4-pass resilient `git apply`).
3. Reset test files (`git checkout HEAD`, `git clean -f`), then apply
   task `test_patch` — agent edits to tests are discarded.
4. Run hermetic `pytest … --junitxml=… -p no:anyio` (`HARNESS_README.md:600-605`).
5. `exit_code == 0` → `resolved = True` (`HARNESS_README.md:243`).

## 3. Harness prompt (7 sections, `HARNESS_README.md:298-342`)

1. Task header + `problem_statement` (`:301-307`).
2. `Hints` — only if `hints_text` non-empty (`:308-312`).
3. Task Budget: time / tool-calls / turns / cost (`:313-320`).
4. Env rules (`:321-329`): single-command timeout **300 s**, output cap
   **5000 chars**, `read_file` cap **150 lines / 10000 chars**, offline
   (no `pip install`).
5. Standard instructions 0–5: stay under `/workspace`, verify, call
   `submit_patch`, return final text (`:330-332`).
6. Code-intelligence tools — only if graph `.json` + embedding `.npz`
   exist (`:333-340`).
7. Workspace layout: `find . -maxdepth 3`, first 150 entries (`:341-342`).

## 4. Session state + termination

- `session.state`: `problem_description = task.problem_statement`;
  `hints = task.hints_text.strip()` (only if non-empty). ADK interpolates
  `{problem_description}` / `{hints}` in instructions
  (`HARNESS_README.md:291-296`).
- `submit_patch()` is **free** (`count_tool_call=False`); `get_status()` is
  also free. Once a turn ends with `patch_submitted == True`, the loop
  terminates immediately — verify first, clean `/workspace` scratch, call
  last (`HARNESS_README.md:346-348, 670-671`).
- 3 nudges (`HARNESS_README.md:349-359`): text-only turn without
  `submit_patch` → resend `Please continue … or call submit_patch …`;
  `MAX_TOKENS` / unclosed `<|tool_call|>` variants shorten reasoning and
  emit the next call immediately. `consecutive_nudges > 3` ends session.

## 5. Local eval budgets (reference)

- Sample `eval_config.yaml` is 10 calls / 1 min (debug only).
- Real local test: `swegemma eval --max-tool-calls 50 --max-time-minutes 30`
  (`HARNESS_README.md:621-631`). Defaults table at `:541`.
