# 02 — Dataset: 129 Tasks, Where the Weight Is

> Verified by `python3 -c` on `tasks.jsonl` (2026-09-28). No code changed.

## 1. Counts (`tasks.jsonl`)

```bash
python3 -c "import json,collections; rows=[json.loads(l) for l in open('tasks.jsonl')]; \
  print(len(rows)); print(collections.Counter(r['repo'].split('/')[-1] for r in rows))"
```

- Total: **129** tasks.
- By repo (short name): **fastapi 67, rich 48, requests 13, httpx 1**.
- Full ids: `fastapi/fastapi` 67, `Textualize/rich` 48, `psf/requests` 13,
  `encode/httpx` 1.
- `hints_text`: **0 / 129 non-empty** (all `""`) — prompt §2 Hints never fires.

## 2. Schema (keys per row)

- Keys (8): `instance_id, repo, base_commit, patch, test_patch,
  problem_statement, hints_text, created_at`.
- Roles: `problem_statement` = issue text → Container A prompt;
  `base_commit` = snapshot anchor (40-hex SHA); `patch` = gold fix
  (held out, never shown to agent); `test_patch` = applied only in
  Container B before hermetic pytest.

## 3. Example row (truncated)

- `instance_id`: `fastapi_15661` | `repo`: `fastapi/fastapi` |
  `base_commit`: `ee22a4b8…8d8be2` | `created_at`: `2026-05-31T16:00:39Z`.
- `problem_statement` (1025 chars, head): `👷 Automate release preparation
  | ## Pull Request | … start with a GitHub Discussion …`.
- `patch` (6966 chars, head): `--- a/scripts/prepare_release.py … +"""Prepare
  a release by updating the package version…"""`.
- `test_patch` (7796 chars, head): `--- a/tests/test_prepare_release.py …
  +from scripts.prepare_release import (RELEASE_NOTES_HEADER, BumpType, …`.

## 4. Sidecars: graphs + embeddings

- `graphs/`: **127** `.json` (2 tasks lack graph data).
- `embeddings/`: **127** `.npz` (same 127; one `.npz` per graphed task).
- Harness appends the Code-Intelligence prompt section only when both files
  exist and are >100 bytes (`HARNESS_README.md:333-340`).

## 5. Takeaway

- Weight is fastapi + rich (115 / 129 ≈ 89%). Strategy work should
  prioritize those two repos' conventions; requests/httpx are the long tail.
