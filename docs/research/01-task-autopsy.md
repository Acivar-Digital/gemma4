# 01 — Task Autopsy (lead-owned, 2026-09-28)

Sample: 6 tasks (2 fastapi / 2 rich / 1 requests / 1 httpx). Method: parsed `tasks.jsonl` +++ lines + hunks + test defs. Verified by lead shell, not subagent.

| id | prob chars | patch files/hunks | test target | single/multi |
|---|---|---|---|---|
| fastapi_14492 | 159 | 1 / 1 — docs_src only | tests/test_tutorial/test_metadata/test_tutorial001_1.py::test_openapi_schema | single, docs-only |
| fastapi_14609 | 144 | 20 / 155 — fastapi/_compat/* | tests/test_compat.py + params_v1 + datetime | multi, compat shim |
| rich_4077 | 66 | 1 / 2 — rich/file_proxy.py | tests/test_file_proxy.py::test_new_lines, test_isatty | single, ideal |
| rich_3930 | 1224 | 26 / 31 — unicode tables | tests/test_cells.py, test_text.py, test_unicode_data.py | multi, data-heavy |
| requests_6589 | 237 | 1 / 2 — src/requests/utils.py | tests/test_requests.py (3 tests) | single, ideal |
| httpx_3672 | 243 | 7 / 36 — src/httpx + src/ahttpx mirror | tests/test_parsers.py | multi, mirrored tree |

Facts:
- hints_text empty 6/6 (matches 129/129 claim in docs/02).
- Patch range is bimodal: 231B–271B single-file vs 100KB–308KB multi-file vendor/compat dumps.
- Test patch always names exact file+function — grounding signal stronger than problem_statement.
- fastapi_14492 warns: gold patch can be docs_src-only; test-file-reset rule still applies.
- httpx mirror (src/httpx + src/ahttpx) means single logical fix appears as 7 files.

Verdict on strict 5-field schema:
- Fits 3/6 single-file cases cleanly.
- Fails 3/6 multi-file: file+lines singular forces a guess; compat/unicode/mirror need file LIST, not one file.
- Fix: extend schema to `files[]` (max 3) + `primary_file`, or allow two searcher calls (primary + related). Your Always-delegate (Q6) survives only if schema allows multi-file.
