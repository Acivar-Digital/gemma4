# 02 — Graph Truth (lead-owned, 2026-09-28)

Method: lead opened 2 graphs + embeddings directly. 127 graphs / 127 npz / 129 snapshots (2 base_commits shared — full coverage).

| graph | nodes | lib | noise (test/tutorial/docs/example) |
|---|---|---|---|
| fastapi_016ab76 | 4287 | 566 (13.2%) | 3721 (86.8%) — tutorialXXX dominates |
| rich_01b85ac11 | 1925 | 1105 (57.4%) | 820 (42.6%) — tests.* + examples |

Node schema: `{name, text, id}` only — NO file path field. Id is dotted symbol (`tests.test_bar.test_render`, `path_operation_advanced_configuration.tutorial004_py310.Item`). Embeddings: 256-dim float32 per symbol, 1:1 with nodes (4287 vecs).

Verdict: AST-first is viable as candidate generator but NOT as primary locator.
- Fastapi: 7:1 noise; unfiltered `search_similar_code` returns tutorial symbols.
- Searcher prompt must enforce: symbol-names-not-sentences, filter `tutorial|tests\.|examples\.|benchmarks\.`, k=10, then `read_file` confirm.
- `read_file` stays mandatory fallback in Main (hybrid), not optional. Pure-delegate dies on noise.
