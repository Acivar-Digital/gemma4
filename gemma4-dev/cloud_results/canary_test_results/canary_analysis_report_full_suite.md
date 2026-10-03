This file is a merged representation of a subset of the codebase, containing files not matching ignore patterns, combined into a single document by Repomix.

# File Summary

## Purpose
This file contains a packed representation of a subset of the repository's contents that is considered the most important context.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Files matching these patterns are excluded: *.safetensors
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Files are sorted by Git change count (files with more changes are at the bottom)

# Directory Structure
`````
submission/
  adapters/
    main_lora/
      adapter_config.json
      adapter_model.safetensors
  configs/
    sampling.yaml
  prompts/
    main.md
  skills/
    code-map/
      scripts/
        map.py
      map.py
      SKILL.md
    code-oracle/
      scripts/
        oracle.py
      oracle.py
      SKILL.md
    fast-grep/
      scripts/
        grep.py
      grep.py
      SKILL.md
    repro-check/
      scripts/
        check.py
      check.py
      SKILL.md
    test-gate/
      scripts/
        gate.py
      gate.py
      SKILL.md
  agent.yaml
  eval_config.yaml
CANARY_ANALYSIS_REPORT.md
`````

# Files

## File: submission/adapters/main_lora/adapter_config.json
`````json
{
  "alora_invocation_tokens": null,
  "alpha_pattern": {},
  "arrow_config": null,
  "auto_mapping": {
    "base_model_class": "Gemma4ForConditionalGeneration",
    "parent_library": "transformers.models.gemma4.modeling_gemma4",
    "unsloth_fixed": true
  },
  "base_model_name_or_path": "unsloth/gemma-4-31B-it-unsloth-bnb-4bit",
  "bias": "none",
  "corda_config": null,
  "ensure_weight_tying": false,
  "eva_config": null,
  "exclude_modules": null,
  "fan_in_fan_out": false,
  "inference_mode": true,
  "init_lora_weights": true,
  "kasa_config": null,
  "layer_replication": null,
  "layers_pattern": null,
  "layers_to_transform": null,
  "loftq_config": {},
  "lora_alpha": 16,
  "lora_bias": false,
  "lora_dropout": 0.0,
  "lora_ga_config": null,
  "megatron_config": null,
  "megatron_core": "megatron.core",
  "modules_to_save": null,
  "monteclora_config": null,
  "peft_type": "LORA",
  "peft_version": "0.21.2",
  "qalora_group_size": 16,
  "r": 8,
  "rank_pattern": {},
  "revision": null,
  "target_modules": "(?:.*?(?:language|text).*?(?:self_attn|attention|attn|mixer|mlp|feed_forward|ffn|dense|mixer).*?\\.(?:q_proj|v_proj|o_proj))|(?:\\bmodel\\.layers\\.[\\d]{1,}(?!.*\\.experts\\.\\d)\\..*?(?:self_attn|attention|attn|mixer|mlp|feed_forward|ffn|dense|mixer).*?\\.(?:(?:q_proj|v_proj|o_proj)))",
  "target_parameters": null,
  "task_type": "CAUSAL_LM",
  "trainable_token_indices": null,
  "use_bdlora": null,
  "use_dora": false,
  "use_qalora": false,
  "use_rslora": false,
  "velora_config": null
}
`````

## File: submission/configs/sampling.yaml
`````yaml
temperature: 0.1
top_p: 0.95
max_output_tokens: 4096
thinking_config:
  include_thoughts: false
  thinking_budget: 0
`````

## File: submission/prompts/main.md
`````markdown
<SYSTEM_DIRECTIVE_CRITICAL>
# CRITICAL RULE: NEVER CALL `load_skill`, `list_skills`, OR `load_skill_resource`
All 5 skills (`fast-grep`, `code-map`, `code-oracle`, `repro-check`, `test-gate`) are ALREADY pre-loaded into your environment.
Calling `load_skill` or `list_skills` is a WASTED TOOL CALL that consumes your task budget and causes evaluation failure.
Execute skills directly via `run_skill_script(skill_name="...", file_path="...", args=[...])`.

You are the Autonomous Software Developer fixing Python defects in /workspace.

## ROLE & AUTONOMY
- You own the ENTIRE task lifecycle: locate the root cause, inspect the code, apply surgical edits via `edit_file` (or `write_file` for new files), run verification tests, and submit your patch with `submit_patch()`.
- You have direct access to `submit_patch()`. There is NO supervisor or subagent. Once verified, you submit directly.

## TOOLS & CAPABILITIES
- Direct tools: `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`.
- Skill execution: `run_skill_script(skill_name="...", file_path="...", args=[...])`.
- NOTE: `get_status()` is a 100% FREE tool (it does NOT consume your tool-call budget).
- NOTE: The code editing tool name is `edit_file`. NEVER call `edit(...)` directly—`edit` does not exist as a tool name.

## PRE-INSTALLED SKILLS (INVOKE VIA run_skill_script):
1. `fast-grep`: Fast, ranked AST-aware keyword and regex search across the workspace. Flashes the top enclosing functions centered on the target match line, and outputs `[CLEAN CODE FOR edit_file (EXACT INDENTATION)]` with exact indentation.
   Invoke via: run_skill_script(skill_name="fast-grep", file_path="grep.py", args=["<pattern>"])
2. `code-map`: AST code structure, class hierarchies, and symbol call-graph tracer. Query with `--symbol <name>` to trace callers/callees/definitions across the repo, or `--file <path>` for a compact file outline.
   Invoke via: run_skill_script(skill_name="code-map", file_path="map.py", args=["--symbol", "<symbol_name>"]) or args=["--file", "<file_path>"]
3. `code-oracle`: Multi-domain coding oracle for Python expression evaluation (`--eval`), ANSI/hex inspection (`--hex`), terminal cell display width (`--width`), HTML entity & tag balance (`--html-esc`), JSON Schema / OpenAPI validation (`--schema`), and AST syntax check (`--syntax`).
   Invoke via: run_skill_script(skill_name="code-oracle", file_path="oracle.py", args=["--eval", "<expr>"]) or args=["--hex", "<text>"] or args=["--width", "<text>"] or args=["--html-esc", "<html_or_file>"] or args=["--schema", "<json_or_file>"] or args=["--syntax", "<file>"]
4. `repro-check`: Runs an isolated Python assertion in /tmp with workspace PYTHONPATH to verify a defect or test hypothesis. For missing-validator defects, use `--expect-exception <ExceptionType>`. For complex assertions or tricky quotes, use `--b64 <payload>` to bypass shell escaping.
   Invoke via: run_skill_script(skill_name="repro-check", file_path="check.py", args=["<python_assertion_code>"]) or args=["--expect-exception", "<ExceptionType>", "<python_code>"] or args=["--b64", "<base64_string>"]
5. `test-gate`: Authoritative gatekeeper consolidating distance-1 neighbor regression tests (`--blast` or default), safe git diff viewer with test-file mutation assertion (`--diff`), and full patch submission readiness (`--status`).
   Invoke via: run_skill_script(skill_name="test-gate", file_path="gate.py") (runs neighbor regression tests) or args=["--diff"] or args=["--status"]

## CONCISE 5-PHASE LIFECYCLE

### Phase 1: Search & Structural Mapping
- On Turn 1, execute `fast-grep` with concrete technical search terms (function names, class names, error types, specific identifiers):
  `run_skill_script(skill_name="fast-grep", file_path="grep.py", args=["<pattern>"])`
- If you need symbol caller/callee relationships, class inheritance, or structural definitions, use `code-map`:
  `run_skill_script(skill_name="code-map", file_path="map.py", args=["--symbol", "<symbol_name>"])`
- If search in source files is ambiguous or returns many results, search the test suite: `run_skill_script(skill_name="fast-grep", file_path="grep.py", args=["<term>", "tests/"])`. Existing unit tests are the fastest, most precise map of where a feature or behavior is defined and tested.
- DISCOVERY & HYPOTHESIS BUDGET: Maximum 8–9 discovery tool calls total across search, mapping, and file inspection before applying your initial fix. You MUST apply your initial code fix via `edit_file` by tool call 10 at the latest.

### Phase 2: Targeted Inspection & Hypothesis
- Single Rule for `read_file`: ALWAYS omit `end_line`! The harness automatically reads 150 lines from `start_line` without bounds errors. Center `start_line` around the line number found by `fast-grep`: `read_file(filepath="pkg/module.py", start_line=110)`. Never pass `end_line`.
- If testing a hypothesis or missing validator, run an isolated probe in `/tmp` via `repro-check`:
  `run_skill_script(skill_name="repro-check", file_path="check.py", args=["<assertion_code>"])`
- DYNAMIC SCRATCHPAD BUDGET & ANTI-THRASHING GUARD:
  - You may use `repro-check` up to 4 times to formulate and verify your hypothesis.
  - ANTI-THRASHING CIRCUIT BREAKER: If `repro-check` fails twice with the identical error without progress, STOP probing immediately. Pivot to `code-map` or `read_file` to re-examine the source structure rather than looping in the scratchpad.
  - BUDGET EXHAUSTION GUARD: If `tool_calls_remaining <= 10` or `tool_calls_used >= 30`, immediately stop investigating and apply your best surgical fix via `edit_file`. Never exhaust your budget without applying an edit!
  - (Note: Post-edit domain checks and regression verification in Phase 4 are EXEMPT from pre-edit scratchpad ceilings).

### Phase 3: Surgical Fix Implementation
- Mandatory tool for modifying existing code: `edit_file`.
  `edit_file(filepath="<path>", old_string="<exact_lines>", new_string="<replacement_lines>")`
- Provide compact 3–5 line anchors in `old_string`. NEVER include line-number prefixes!
- If creating a brand-new file explicitly requested by the issue, use `write_file`.
- MANDATORY IMPLEMENTATION CEILING: Apply your initial change within your first 5–6 tool calls.
- Codebase Consistency & Idiomatic Alignment: When adding validations or error messages, strictly mirror the concise, canonical phrasing already established in the surrounding codebase and docstrings (e.g. follow existing exception messages in the same module). Avoid overly verbose or conversational explanations.

### Phase 4: Multi-Domain Nuance & Regression Verification
- Verify domain-specific nuances using `code-oracle`:
  - **ANSI Styling & Sequences**: Use `code-oracle --hex` to inspect raw escape codes. Preserve exact CSI/SGR styling sequences and ensure proper `\x1b[0m` reset termination without stray escapes.
  - **Unicode Terminal Cell Width**: Use `code-oracle --width` when dealing with console output, table columns, or string padding. CJK Wide characters (`W`/`F`) and emojis take 2 terminal cells, combining marks take 0, and ANSI escapes take 0. Strictly preserve cell width calculations to prevent table border misalignment.
  - **HTML Entity Escaping & Web Security**: Use `code-oracle --html-esc` to verify HTML templates and script injection. Standard OWASP/Python web security requires escaping `<`, `>`, and `&` to `\u003c`, `\u003e`, `\u0026` inside HTML `<script>` tags to prevent XSS breakout. Ensure all HTML tags are balanced.
  - **JSON Schema & OpenAPI Conformance**: Use `code-oracle --schema` when modifying OpenAPI generation or schemas. Check `$defs` vs `definitions`, resolve local `$ref` pointers, and ensure `anyOf` with `null` aligns with Pydantic v1 vs v2 contracts.
- Run distance-1 neighbor regression tests using `test-gate`:
  `run_skill_script(skill_name="test-gate", file_path="gate.py")`
- Distinguish true regressions vs pre-fix test assertion conflicts:
  - **True Regression**: Unhandled exceptions (`AttributeError`, `TypeError`, `KeyError`), crashes, or broken distance-1 consumer tests. Fix these before submitting.
  - **Pre-Fix Test Assertion Conflict**: A unit test in `tests/` asserts the old buggy behavior. In Container B, the evaluation harness applies an updated test patch. If distance-1 consumers pass and the failure is solely that an unpatched test expects the old pre-fix output, do NOT suppress or revert!
  - **NEVER EDIT TEST FILES**: Under NO circumstances edit test files in `/workspace`!

### Phase 5: Patch Inspection & Submission
- Step 1: Run read-only diff inspection and safety assertion:
  `run_skill_script(skill_name="test-gate", file_path="gate.py", args=["--diff"])`
  - Verifies that ZERO test files (`tests/*`, `test_*.py`, `conftest.py`) were modified.
  - Verifies no dangerous untracked scratch files (`repro.py`, `tmp*.py`) exist in `/workspace`.
- Step 2: Run patch readiness check:
  `run_skill_script(skill_name="test-gate", file_path="gate.py", args=["--status"])`
  - Validates Python AST syntax across all touched files and verifies `[✓ READY]` recommendation.
- Step 3: Call `submit_patch()`.
  - Calling `submit_patch()` completes the task. Never submit an empty patch!

## STRICT OPERATIONAL DISCIPLINE
1. EXACTLY ONE TOOL CALL PER TURN (NO BATCHING / NO CHAINING):
- You MUST emit EXACTLY ONE tool call per response.
- NEVER attempt to call multiple tools, chain tools, or concatenate JSON objects in a single turn. The harness executes strictly ONE tool call at a time.
- After emitting your tool call, STOP immediately and wait for the tool execution observation.
- ZERO CONVERSATIONAL CHATTER: Output ONLY your single tool call. Do NOT emit explanations, apologies, plans, or conversational commentary.
- STRICT NEGATIVE CONSTRAINT ON RAW JSON & TEXT TOOL CALLS: You must ONLY emit tool calls through the native tool-calling interface. NEVER write raw JSON tool objects or pseudo-code function calls into plain text or markdown blocks.
- STRICT JSON ARGUMENT HYGIENE & ESCAPE SAFETY: Format tool arguments cleanly to prevent unescaped double-quote syntax errors that crash the JSON parser. For complex strings in `repro-check`, pass base64 via `--b64 <payload>`.

2. ABSOLUTELY FORBIDDEN: NEVER TOUCH TEST FILES OR WRITE SCRATCH SCRIPTS IN /WORKSPACE:
- ABSOLUTELY FORBIDDEN: NEVER modify, edit, or write to ANY test file (`tests/*`, `test_*.py`, `*_test.py`, `conftest.py`)!
- If a pre-existing unit test fails because it asserts old buggy behavior, LEAVE IT UNTOUCHED. Container B applies the official test patch; modifying test files causes git patch conflicts and instant 0% evaluation score!
- ABSOLUTELY FORBIDDEN: NEVER write temporary scripts, probe files, or test runners into `/workspace` (e.g. `repro.py`, `scan.py`, `test.py`). Any scratch file in `/workspace` is captured by `git diff HEAD` and pollutes the patch! Use `repro-check` to run Python verification snippets safely in `/tmp`.

3. FASTAPI `docs_src` INVARIANT:
- In FastAPI tasks, problem statements mentioning 'Update docs...', 'docs for responses', or tutorial features NEVER target markdown files in `docs/en/docs/*.md`. In FastAPI, documentation examples are executable Python tutorial files in `docs_src/**/*.py` (e.g. `docs_src/stream_data/tutorial002_py310.py`) tested by `tests/test_tutorial/`. Locate and modify the corresponding Python code in `docs_src/`.

4. SURGICAL EDITS & SCOPE BOUNDARY:
- Most tasks require editing only ONE file. Never edit a secondary file without running verification on the primary file.
- If tests fail after your edit and cannot be refined, REVERT the file using `edit_file` (swap `old_string` and `new_string`).
- If `edit_file` fails (target string not found), call `read_file` centered around the target lines to inspect the exact indentation and whitespace before retrying.
- MAXIMUM 2 CONSECUTIVE EDIT ATTEMPTS: Never fail `edit_file` more than 2 consecutive times on the same target lines. On a third attempt, switch to a wider 8–10 line anchor or select an alternate surrounding block to break exact-match whitespace drift loops.

5. ACTIVE BUDGET SELF-METERING:
- Call `get_status()` periodically to check `tool_calls_used` and `tool_calls_remaining` (FREE tool, 0 cost).
- If `tool_calls_remaining <= 10` or `tool_calls_used >= 30`: Immediately cease open-ended discovery/probing and focus exclusively on surgical code edits via `edit_file`.
- If `tool_calls_remaining <= 4` or `tool_calls_used >= 36`: Emergency wrap-up! Apply your best surgical fix via `edit_file` immediately and invoke `submit_patch()`. Never submit an empty patch!
</SYSTEM_DIRECTIVE_CRITICAL>

<USER_ISSUE_BELOW>
Pay attention to the user query that immediately follows this block:
`````

## File: submission/skills/code-map/scripts/map.py
`````python
#!/usr/bin/env python3
"""code-map: AST code structure and symbol call-graph tracer.

Unified skill combining:
1. Symbol call-graph and reference reachability tracer (--symbol <name>, -s, --callers, --callees):
   - Traces definitions, imports, calls, attribute accesses, callers, and callees across repo.
   - Detects class hierarchies: base classes and subclasses inheriting from the queried symbol.
   - Omnivorous: queries precomputed codebase graphs (NetworkX node-link JSON) when available,
     and falls back to / combines with live AST analysis.
   - Provides fuzzy matching suggestions and diagnostics when symbols are missing or private.
   - When a symbol is not found, displays available top-level symbols in the repo and copy-pasteable next steps.
2. Compact AST file and directory skeleton generator (--file <path>, -f, -d, --dir, -t, --tree):
   - Extracts classes, base classes, functions, arguments, return type annotations, docstrings,
     and line ranges [start-end] for a target Python file or directory.
   - For directories, extracts skeletons across modules up to max_lines budget.
   - Diagnoses syntax errors with exact line, column, snippet, and caret pointer.
   - Output-capped to prevent context flooding in 32K token windows.
3. Forgiving positional fallback:
   - If argument is an existing directory or ends in .py, treated as file mode.
   - If argument matches an existing file with .py appended, treated as file mode.
   - If argument contains path separators (/ or \\), treated as file mode.
   - Otherwise, treated as symbol mode.
4. Omnivorous workspace overview on empty args, '.', '/workspace', or -o/--overview:
   - Explains the workspace structure, discovered packages, and key modules.
   - Provides tailored, copy-pasteable example invocations for the current repository.
   - Never crashes or exits 1 on empty calls or unrecognized flags.

100% Pydantic v2 schemas for all structured outputs.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True

# Protect against deeply nested ASTs or deep recursions without stack overflow
try:
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4000))
except Exception:
    pass

from pydantic import BaseModel, ConfigDict, Field

# Directories to skip when scanning repositories
SKIP_DIRS: Set[str] = {
    "__pycache__",
    "build",
    "dist",
    ".git",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    ".eggs",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "wheels",
    "site-packages",
    ".adk_exec",
}


# ==============================================================================
# Pydantic v2 Models: Symbol Tracing (--symbol)
# ==============================================================================


class ReferenceDetail(BaseModel):
    """Detailed location and context for a symbol reference, definition, or import."""

    model_config = ConfigDict(extra="ignore")

    file_path: str = Field(description="Relative file path where the reference occurs")
    line_number: int = Field(description="1-based line number of the reference")
    kind: str = Field(
        description="Reference kind: 'class', 'function', 'method', 'import', 'call', 'attribute', 'subclass', or 'text'"
    )
    context: str = Field(default="", description="Source preview, import statement, or call context")
    caller: Optional[str] = Field(default=None, description="Enclosing caller function/method if applicable")
    callee: Optional[str] = Field(default=None, description="Target callee symbol if applicable")
    bases: Optional[List[str]] = Field(default=None, description="Base classes if symbol is a class definition")
    subclasses: Optional[List[str]] = Field(default=None, description="Subclasses inheriting from this symbol")


class SymbolSuggestion(BaseModel):
    """Candidate symbol suggestion for a missing or misspelled query."""

    model_config = ConfigDict(extra="ignore")

    symbol: str = Field(description="Candidate symbol name or fully qualified path")
    similarity: float = Field(description="Fuzzy match similarity score (0.0 to 1.0)")
    kind: Optional[str] = Field(default=None, description="Inferred or known kind (function, class, method, node)")
    location: Optional[str] = Field(default=None, description="File path or defining location if known")
    reason: Optional[str] = Field(default=None, description="Why this candidate was suggested")
    inspect_command: Optional[str] = Field(
        default=None, description="Exact copy-pasteable command to inspect this candidate symbol"
    )
    file_command: Optional[str] = Field(
        default=None, description="Exact copy-pasteable command to inspect containing file"
    )


class GraphStatus(BaseModel):
    """Diagnostic status of precomputed codebase graph loading."""

    model_config = ConfigDict(extra="ignore")

    graph_loaded: bool = Field(description="Whether a precomputed codebase graph JSON was found and loaded")
    graph_path: Optional[str] = Field(default=None, description="Filesystem path of the loaded graph JSON")
    node_count: int = Field(default=0, description="Total node count in loaded graph")
    edge_count: int = Field(default=0, description="Total edge count in loaded graph")
    fallback_mode: str = Field(default="live_ast", description="Analysis mode ('precomputed_graph', 'live_ast', or 'hybrid')")
    diagnostic_message: Optional[str] = Field(default=None, description="Explanation of graph availability or fallback instructions")


class CodeGraphResult(BaseModel):
    """Complete structured output for code graph symbol tracing and reachability analysis."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="symbol", description="Analysis mode: 'symbol'")
    query: str = Field(description="Queried symbol or text pattern")
    found: bool = Field(description="Whether the symbol was identified in graph or AST")
    resolved_symbol: Optional[str] = Field(default=None, description="Resolved canonical or node identifier")
    focus: Optional[str] = Field(default=None, description="Optional focus filter: 'callers' or 'callees'")
    explanation: str = Field(description="Deterministic explanation of search outcome")
    inspection_hint: Optional[str] = Field(default=None, description="Guidance for private/internal or imported symbols")
    graph_status: GraphStatus = Field(description="Graph loading diagnostics and fallback details")
    definitions: List[ReferenceDetail] = Field(default_factory=list, description="Symbol definitions")
    imports: List[ReferenceDetail] = Field(default_factory=list, description="Symbol imports")
    calls: List[ReferenceDetail] = Field(default_factory=list, description="Direct call sites and attribute accesses")
    subclasses: List[ReferenceDetail] = Field(default_factory=list, description="Classes inheriting from this symbol")
    text_occurrences: List[ReferenceDetail] = Field(default_factory=list, description="Textual matches across files")
    callers: List[str] = Field(default_factory=list, description="Inbound callers invoking this symbol")
    callees: List[str] = Field(default_factory=list, description="Outbound callees invoked by this symbol")
    caller_callee_summary: Optional[str] = Field(default=None, description="Summary of call graph reachability")
    suggestions: List[SymbolSuggestion] = Field(default_factory=list, description="Closest matching candidates")
    did_you_mean: List[str] = Field(default_factory=list, description="List of top suggested symbol names")
    available_top_symbols: List[str] = Field(
        default_factory=list, description="Available top-level public symbols in the repository"
    )
    next_steps: List[str] = Field(default_factory=list, description="Actionable next commands for the LLM")


# ==============================================================================
# Pydantic v2 Models: File Skeleton (--file) & Repository Overview
# ==============================================================================


class MapDiagnostic(BaseModel):
    """Diagnostic explanation for missing paths, syntax errors, or parsing anomalies."""

    model_config = ConfigDict(extra="ignore")

    level: str = Field(default="error", description="Severity level: 'error', 'warning', or 'info'")
    category: str = Field(
        ...,
        description="Category: 'missing_path', 'syntax_error', 'unparseable_file', 'empty_target', 'encoding_error', 'permission_denied', 'recursion_limit_exceeded'",
    )
    message: str = Field(..., description="Primary explanatory message for the agent")
    target_path: Optional[str] = Field(default=None, description="Target file or directory path where issue occurred")
    line: Optional[int] = Field(default=None, description="1-based line number for AST syntax errors")
    column: Optional[int] = Field(default=None, description="1-based column offset for AST syntax errors")
    snippet: Optional[str] = Field(default=None, description="Source code snippet showing the syntax error location and caret pointer")
    suggestions: List[str] = Field(default_factory=list, description="Closest valid paths or recommended actions")
    guidance: Optional[str] = Field(default=None, description="Deterministic guidance instructions for the agent")


class SymbolItem(BaseModel):
    """Extracted Python symbol (class, function, method, async function)."""

    model_config = ConfigDict(extra="ignore")

    kind: str = Field(..., description="Symbol kind: 'class', 'def', 'async def'")
    name: str = Field(..., description="Identifier name of the symbol")
    signature: str = Field(..., description="Formatted symbol signature including arguments, return type, and line range")
    start_line: int = Field(..., description="Starting line number in source file (1-based)")
    end_line: int = Field(..., description="Ending line number in source file (1-based)")
    docstring: Optional[str] = Field(default=None, description="Formatted one-line docstring summary if present")


class ModuleSummary(BaseModel):
    """AST structure summary for a single Python module file."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Workspace-relative path to the Python source file")
    symbols: List[SymbolItem] = Field(default_factory=list, description="List of extracted symbols in document order")
    symbol_count: int = Field(default=0, description="Total number of extracted symbols in this module")
    syntax_error: Optional[MapDiagnostic] = Field(default=None, description="AST syntax error diagnostic if module could not be parsed")


class RepoLayoutItem(BaseModel):
    """Top-level repository layout item for orienting the agent."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Entry name (directory or file name)")
    rel_path: str = Field(..., description="Workspace-relative path")
    is_dir: bool = Field(..., description="True if directory, False if file")
    summary: str = Field(..., description="Formatted human-readable layout summary entry")


class FileSkeletonResult(BaseModel):
    """Complete structured output for file skeleton mapping session."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="file", description="Analysis mode: 'file'")
    target: str = Field(..., description="Target file or directory path requested by the agent")
    workspace_root: str = Field(..., description="Absolute workspace root path")
    success: bool = Field(default=True, description="Whether mapping completed successfully without path resolution failures")
    modules: List[ModuleSummary] = Field(default_factory=list, description="List of mapped module summaries")
    total_files: int = Field(default=0, description="Number of successfully mapped Python files")
    total_symbols: int = Field(default=0, description="Total number of symbols across all modules")
    diagnostics: List[MapDiagnostic] = Field(default_factory=list, description="List of diagnostics, syntax errors, or warnings")
    top_level_layout: List[RepoLayoutItem] = Field(default_factory=list, description="Top-level repository structure")
    is_truncated: bool = Field(default=False, description="True if output was truncated to honor max_lines cap")
    rendered_text: str = Field(default="", description="Human/LLM-readable text output")
    next_steps: List[str] = Field(default_factory=list, description="Actionable next commands for the LLM")


class WorkspaceOverviewResult(BaseModel):
    """Complete structured output for workspace repository overview and usage guide."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="overview", description="Analysis mode: 'overview'")
    workspace_root: str = Field(..., description="Absolute workspace root path")
    success: bool = Field(default=True, description="Whether overview was generated successfully")
    top_level_layout: List[RepoLayoutItem] = Field(default_factory=list, description="Top-level repository structure")
    discovered_packages: List[str] = Field(default_factory=list, description="Discovered Python packages/subdirectories")
    key_modules: List[str] = Field(default_factory=list, description="Key Python module files in workspace")
    sample_symbols: List[str] = Field(default_factory=list, description="Sample discovered public classes and functions")
    copy_pasteable_commands: List[str] = Field(default_factory=list, description="Copy-pasteable invocations tailored to this repo")
    rendered_text: str = Field(default="", description="Human/LLM-readable text output")


# ==============================================================================
# Internal CLI Arguments Schema
# ==============================================================================


class ParsedArgs(BaseModel):
    """Structured internal representation of forgiving CLI arguments."""

    model_config = ConfigDict(extra="ignore")

    symbol: Optional[str] = None
    file: Optional[str] = None
    dir: Optional[str] = None
    target: Optional[str] = None
    overview: bool = False
    tree: bool = False
    callers: Optional[Any] = None
    callees: Optional[Any] = None
    focus: Optional[str] = None
    json: bool = False
    graph: Optional[str] = None
    max_lines: int = 120
    notices: List[str] = Field(default_factory=list)


# ==============================================================================
# Workspace & Target Resolution (Loop-Safe & Symlink-Safe)
# ==============================================================================


def should_skip_dir(name: str) -> bool:
    """Return True if directory should be skipped during walk."""
    if name.startswith(".") or name.startswith("__") or ".adk_exec" in name or name.startswith(".adk_exec"):
        return True
    lower = name.lower()
    if lower in SKIP_DIRS:
        return True
    if "egg-info" in lower:
        return True
    return False


def should_skip_path(p: pathlib.Path, ws: pathlib.Path) -> bool:
    """Return True if path contains any skipped directory components."""
    if ".adk_exec" in p.name or p.name.startswith(".adk_exec"):
        return True
    try:
        rel = p.relative_to(ws)
    except ValueError:
        rel = p
    for part in rel.parts:
        if should_skip_dir(part) or ".adk_exec" in part or part.startswith(".adk_exec"):
            return True
    return False


def safe_walk(
    root_path: pathlib.Path,
    ws_root: pathlib.Path,
    max_depth: int = 15,
    max_dirs: int = 1000,
) -> Any:
    """Cycle-safe, symlink-safe, and depth-bounded generator over directory tree.

    Prevents infinite loops from circular symlinks, directory junctions, runaway depth,
    and massive directory trees.
    """
    visited_inodes: Set[Tuple[int, int]] = set()
    visited_realpaths: Set[str] = set()
    dirs_count = 0

    try:
        real_root = os.path.realpath(str(root_path))
        visited_realpaths.add(real_root)
    except Exception:
        pass

    for dirpath, dirnames, filenames in os.walk(str(root_path), followlinks=False):
        dirs_count += 1
        if dirs_count > max_dirs:
            dirnames.clear()
            return

        curr_p = pathlib.Path(dirpath)
        try:
            real_dir = os.path.realpath(dirpath)
            if real_dir in visited_realpaths and dirpath != str(root_path):
                dirnames.clear()
                continue
            visited_realpaths.add(real_dir)

            stat_res = curr_p.stat()
            inode_key = (stat_res.st_dev, stat_res.st_ino)
            if inode_key in visited_inodes:
                dirnames.clear()
                continue
            visited_inodes.add(inode_key)
        except (OSError, PermissionError):
            dirnames.clear()
            continue

        try:
            rel = curr_p.relative_to(ws_root)
            if len(rel.parts) > max_depth:
                dirnames.clear()
                continue
        except ValueError:
            pass

        # In-place directory filtering: skip ignored dirs and symlink directories
        filtered_dirs: List[str] = []
        for d in dirnames:
            if should_skip_dir(d):
                continue
            full_sub = os.path.join(dirpath, d)
            try:
                if os.path.islink(full_sub):
                    continue
            except (OSError, PermissionError):
                continue
            filtered_dirs.append(d)
        dirnames[:] = filtered_dirs

        yield dirpath, dirnames, filenames


def get_workspace_dir() -> pathlib.Path:
    """Robustly and deterministically locate the active target repository workspace directory."""
    # a) Check caller stack frame for _orig_cwd (set by ADK in _materialize_and_run)
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals and f.f_locals["_orig_cwd"]:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                    or (p / ".git").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    # b) Check environment variable overrides
    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    # c) Standard competition container workspace (/workspace)
    for p_str in ("/workspace", "/workspace/repo", "/repo", "/app"):
        p = pathlib.Path(p_str)
        if p.is_dir() and (
            (p / "pyproject.toml").exists()
            or (p / "setup.py").exists()
            or (p / ".git").exists()
        ):
            return p.resolve()

    # d) Ascend from current directory looking for repo markers
    curr = pathlib.Path.cwd().resolve()
    for parent in [curr] + list(curr.parents):
        if (
            (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
            or (parent / ".git").exists()
            or (parent / "tasks.jsonl").exists()
        ):
            return parent

    return curr


def resolve_target(target_arg: str, ws: pathlib.Path) -> Tuple[Optional[pathlib.Path], str]:
    """Resolve target path safely against workspace."""
    clean = target_arg.strip()
    if not clean or clean in (".", "/", "/workspace"):
        return ws, clean or "."

    # Check direct relative to workspace
    cand = ws / clean.lstrip("/")
    if cand.exists():
        return cand, clean

    # Check absolute
    try:
        p_abs = pathlib.Path(clean).resolve()
        if p_abs.exists() and (p_abs == ws or ws in p_abs.parents):
            return p_abs, clean
    except Exception:
        pass

    # Check with .py appended if not already present
    if not clean.endswith(".py"):
        cand_py = ws / f"{clean.lstrip('/')}.py"
        if cand_py.is_file():
            return cand_py, f"{clean}.py"

    # Check for glob match inside workspace
    try:
        pattern = f"**/{clean}" if clean.endswith(".py") else f"**/{clean}.py"
        matches = [m for m in ws.glob(pattern) if not should_skip_path(m, ws)]
        if matches:
            return matches[0], clean
        if not clean.endswith(".py"):
            dir_matches = [m for m in ws.glob(f"**/{clean}") if m.is_dir() and not should_skip_path(m, ws)]
            if dir_matches:
                return dir_matches[0], clean
    except Exception:
        pass

    return None, clean


def find_closest_paths(clean_target: str, ws: pathlib.Path) -> List[str]:
    """Find closest existing files and directories to the missing target using fuzzy matching."""
    all_dirs: List[str] = []
    all_files: List[str] = []

    try:
        for root, dirs, files in safe_walk(ws, ws, max_depth=8, max_dirs=600):
            dirs[:] = sorted([d for d in dirs if not should_skip_dir(d)])
            rel_dir = os.path.relpath(root, ws)
            if rel_dir != ".":
                all_dirs.append(rel_dir)
            for f in files:
                if f.endswith(".py") and not f.startswith("."):
                    rel_file = os.path.normpath(os.path.join(rel_dir, f)) if rel_dir != "." else f
                    all_files.append(rel_file)
    except Exception:
        pass

    all_paths = all_files + all_dirs
    if not all_paths:
        return []

    target_base = os.path.basename(clean_target)
    exact_bases = [p for p in all_paths if os.path.basename(p) == target_base]
    close_full = difflib.get_close_matches(clean_target, all_paths, n=6, cutoff=0.35)
    close_bases = [
        p
        for p in all_paths
        if os.path.basename(p)
        in difflib.get_close_matches(target_base, [os.path.basename(x) for x in all_paths], n=6, cutoff=0.45)
    ]
    substrings = [p for p in all_paths if target_base.lower() in os.path.basename(p).lower()]

    combined: List[str] = []
    for p in exact_bases + close_full + close_bases + substrings:
        if p not in combined:
            combined.append(p)

    results: List[str] = []
    for p in combined[:8]:
        if p in all_dirs:
            results.append(f"📁 {p}/")
        else:
            results.append(f"📄 {p}")

    return results


def get_top_level_layout(ws: pathlib.Path) -> List[RepoLayoutItem]:
    """Inspect top-level entries in the workspace and return structured layout items."""
    items: List[RepoLayoutItem] = []
    try:
        entries = sorted(ws.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except Exception:
        return items

    for entry in entries:
        if entry.name.startswith(".") or entry.name.startswith("__") or ".adk_exec" in entry.name:
            continue
        if entry.name in ("venv", "wheels", ".git", "__pycache__"):
            continue

        rel = entry.name
        if entry.is_dir():
            py_count = 0
            subdirs = 0
            try:
                for _, d_list, f_list in safe_walk(entry, ws, max_depth=5, max_dirs=300):
                    d_list[:] = [d for d in d_list if not should_skip_dir(d)]
                    subdirs += len(d_list)
                    for f in f_list:
                        if f.endswith(".py") and not f.startswith("."):
                            py_count += 1
            except Exception:
                pass

            desc_parts: List[str] = []
            if py_count > 0:
                desc_parts.append(f"{py_count} .py file{'s' if py_count != 1 else ''}")
            if subdirs > 0:
                desc_parts.append(f"{subdirs} subdir{'s' if subdirs != 1 else ''}")
            desc_suffix = f" ({', '.join(desc_parts)})" if desc_parts else ""
            summary = f"📁 {entry.name}/{desc_suffix}"
            items.append(RepoLayoutItem(name=entry.name, rel_path=rel, is_dir=True, summary=summary))
        else:
            items.append(RepoLayoutItem(name=entry.name, rel_path=rel, is_dir=False, summary=f"📄 {entry.name}"))
    return items


def collect_py_files(target_path: pathlib.Path, ws: pathlib.Path, max_files: int = 150) -> List[pathlib.Path]:
    """Collect Python files from target path in deterministic order."""
    if target_path.is_file():
        if target_path.name.endswith(".py") or target_path.suffix == ".py":
            return [target_path]
        return []

    py_files: List[pathlib.Path] = []
    for root, dirs, files in safe_walk(target_path, ws, max_depth=10, max_dirs=600):
        dirs[:] = sorted([d for d in dirs if not should_skip_dir(d)])
        for f in sorted(files):
            if f.endswith(".py") and not f.startswith("."):
                py_files.append(pathlib.Path(root) / f)
                if len(py_files) >= max_files:
                    return py_files
    return py_files


def get_top_repo_symbols(ws: pathlib.Path, max_symbols: int = 12) -> List[str]:
    """Extract top-level public classes and functions across key workspace modules."""
    symbols: List[str] = []
    seen: Set[str] = set()

    # Prioritize non-test core modules
    py_files = collect_py_files(ws, ws, max_files=40)
    core_files = [p for p in py_files if "test" not in p.name.lower() and "test" not in str(p).lower()]
    target_files = core_files if core_files else py_files

    for fpath in target_files[:20]:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(fpath))
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    if node.name not in seen:
                        seen.add(node.name)
                        symbols.append(f"class {node.name}")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                    if node.name not in seen:
                        seen.add(node.name)
                        symbols.append(f"def {node.name}()")
                if len(symbols) >= max_symbols:
                    return symbols
        except Exception:
            continue

    return symbols


# ==============================================================================
# Graph Discovery & Indexing
# ==============================================================================


def discover_graph_file(
    ws_root: pathlib.Path, explicit_path: Optional[str] = None, query_symbol: Optional[str] = None
) -> Optional[pathlib.Path]:
    """Locate precomputed codebase graph JSON file for the repository."""
    if explicit_path:
        p = pathlib.Path(explicit_path).resolve()
        if p.is_file():
            return p

    for env_var in ("SWEGEMMA_GRAPH_PATH", "GRAPH_PATH", "SWEGEMMA_GRAPH_FILE"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val).resolve()
            if p.is_file():
                return p

    search_dirs: List[pathlib.Path] = []
    for env_dir in ("SWEGEMMA_GRAPH_DIR", "GRAPH_DIR", "DATA_DIR"):
        val = os.environ.get(env_dir)
        if val:
            search_dirs.append(pathlib.Path(val).resolve())

    search_dirs.extend([
        ws_root / "graphs",
        ws_root / "data" / "graphs",
        ws_root.parent / "graphs",
        ws_root.parent.parent / "graphs",
        pathlib.Path.cwd().resolve() / "graphs",
        pathlib.Path.cwd().resolve() / "data" / "graphs",
        pathlib.Path("/data/graphs"),
        pathlib.Path("/workspace/graphs"),
        pathlib.Path("/workspace/data/graphs"),
    ])

    repo_cands: List[str] = []
    for name in ("fastapi", "rich", "requests", "httpx", "starlette", "pydantic", "flask"):
        if (ws_root / name).is_dir() or (ws_root / "src" / name).is_dir():
            repo_cands.append(name)
        elif name in ws_root.name.lower():
            repo_cands.append(name)

    commit: Optional[str] = None
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ws_root,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0 and res.stdout.strip():
            commit = res.stdout.strip()
    except Exception:
        pass

    for d in search_dirs:
        try:
            if not d.is_dir():
                continue
            json_files = sorted(list(d.glob("*.json")))
            if not json_files:
                continue

            if len(json_files) == 1:
                return json_files[0]

            # 1. Match repository name candidate
            for repo in repo_cands:
                matches = [
                    f for f in json_files
                    if f.name.startswith(f"{repo}_") or f.name.startswith(f"{repo}.")
                ]
                if commit:
                    for m in matches:
                        if commit in m.name:
                            return m
                if matches:
                    return matches[0]

            # 2. Match commit directly if available
            if commit:
                for f in json_files:
                    if commit in f.name:
                        return f

            # 3. Query symbol affinity: check 4 core repo families if in dev/harness environment
            if query_symbol:
                families: Dict[str, pathlib.Path] = {}
                for f in json_files:
                    prefix = f.name.split("_")[0].split(".")[0]
                    if prefix not in families:
                        families[prefix] = f

                for _, rep_path in families.items():
                    try:
                        with open(rep_path, "r", encoding="utf-8", errors="replace") as jf:
                            data = json.load(jf)
                        ids = {str(n.get("id") or "") for n in data.get("nodes", [])}
                        if any(query_symbol in nid for nid in ids):
                            return rep_path
                    except Exception:
                        continue

            if json_files:
                return json_files[0]

        except Exception:
            continue

    return None


def load_and_index_graph(graph_path: pathlib.Path) -> Tuple[Dict[str, Any], int, int]:
    """Load precomputed NetworkX node-link JSON and build fast lookup indexes."""
    try:
        with open(graph_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
    except Exception:
        return {}, 0, 0

    node_ids: List[str] = []
    node_map: Dict[str, Dict[str, Any]] = {}
    leaf_map: Dict[str, List[str]] = {}
    in_edges: Dict[str, List[str]] = {}
    out_edges: Dict[str, List[str]] = {}

    for n in nodes:
        nid = str(n.get("id") or n.get("name") or "").strip()
        if not nid:
            continue
        node_ids.append(nid)
        node_map[nid] = n
        leaf = nid.split(".")[-1]
        leaf_map.setdefault(leaf, []).append(nid)

    for e in edges:
        src = str(e.get("source") or "").strip()
        tgt = str(e.get("target") or "").strip()
        if src and tgt:
            out_edges.setdefault(src, []).append(tgt)
            in_edges.setdefault(tgt, []).append(src)

    indexes = {
        "node_ids": node_ids,
        "node_map": node_map,
        "leaf_map": leaf_map,
        "in_edges": in_edges,
        "out_edges": out_edges,
    }
    return indexes, len(nodes), len(edges)


def resolve_graph_node(query: str, indexes: Dict[str, Any]) -> Optional[str]:
    """Resolve query symbol against graph nodes using 3-tier boundary matching."""
    if not indexes:
        return None

    node_ids: List[str] = indexes.get("node_ids", [])
    node_map: Dict[str, Any] = indexes.get("node_map", {})
    leaf_map: Dict[str, List[str]] = indexes.get("leaf_map", {})

    # Tier 1: Exact match
    if query in node_map:
        return query

    # Tier 2: Leaf / boundary match
    if query in leaf_map:
        return leaf_map[query][0]

    suffix_dot = f".{query}"
    suffix_semi = f";{query}"
    for nid in node_ids:
        if nid.endswith(suffix_dot) or nid.endswith(suffix_semi):
            return nid

    # Tier 3: Case-insensitive boundary match
    q_low = query.lower()
    suffix_dot_low = f".{q_low}"
    for nid in node_ids:
        nid_low = nid.lower()
        if nid_low == q_low or nid_low.endswith(suffix_dot_low):
            return nid

    return None


# ==============================================================================
# Fuzzy Matching & Candidate Suggestions
# ==============================================================================


def compute_fuzzy_suggestions(
    query: str,
    candidates: List[Tuple[str, Optional[str], Optional[str]]],
    top_n: int = 6,
    cutoff: float = 0.30,
) -> List[SymbolSuggestion]:
    """Rank candidate symbols by fuzzy similarity (difflib SequenceMatcher), generating exact copy-pasteable commands."""
    q_low = query.lower()
    scored: List[Tuple[float, str, Optional[str], Optional[str]]] = []

    # Deduplicate candidate names, keeping richest kind/location
    best_candidate_map: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for cand_name, kind, loc in candidates:
        cand_clean = cand_name.strip()
        if not cand_clean or cand_clean == query:
            continue
        if cand_clean not in best_candidate_map:
            best_candidate_map[cand_clean] = (kind, loc)
        else:
            old_kind, old_loc = best_candidate_map[cand_clean]
            if not old_loc and loc:
                best_candidate_map[cand_clean] = (kind or old_kind, loc)
            elif old_kind in ("import", "module", "graph_node") and kind in ("class", "function", "method"):
                best_candidate_map[cand_clean] = (kind, loc or old_loc)

    for cand_clean, (kind, loc) in best_candidate_map.items():
        c_low = cand_clean.lower()
        leaf = cand_clean.split(".")[-1]
        l_low = leaf.lower()

        sim_leaf = difflib.SequenceMatcher(None, q_low, l_low).ratio()
        sim_full = difflib.SequenceMatcher(None, q_low, c_low).ratio()

        sub_boost = 0.0
        if q_low == l_low:
            sub_boost = 1.0
        elif q_low in l_low:
            sub_boost = 0.85
        elif q_low in c_low:
            sub_boost = 0.70

        score = max(sim_leaf, sim_full, sub_boost)
        if score >= cutoff:
            scored.append((score, cand_clean, kind, loc))

    scored.sort(key=lambda x: (x[0], -len(x[1])), reverse=True)

    suggestions: List[SymbolSuggestion] = []
    for score, sym, kind, loc in scored[:top_n]:
        inspect_cmd = f"python3 map.py --symbol {sym}"
        file_cmd = None
        if loc and ":" in loc:
            f_path = loc.split(":")[0]
            file_cmd = f"python3 map.py --file {f_path}"

        suggestions.append(
            SymbolSuggestion(
                symbol=sym,
                similarity=round(score, 3),
                kind=kind or ("function" if "(" in sym else "symbol"),
                location=loc,
                reason=f"Fuzzy match (similarity: {score:.2f}) to '{query}'",
                inspect_command=inspect_cmd,
                file_command=file_cmd,
            )
        )
    return suggestions


# ==============================================================================
# AST Reference, Reachability & Hierarchy Collector (--symbol mode)
# ==============================================================================


class AstReferenceCollector(ast.NodeVisitor):
    """Parses Python AST to extract definitions, base classes, subclasses, imports, calls, callers, callees."""

    def __init__(self, rel_path: str, clean_symbol: str, max_ast_depth: int = 80):
        self.rel_path = rel_path
        self.clean_symbol = clean_symbol
        self.scope_stack: List[str] = []
        self.current_depth: int = 0
        self.max_ast_depth: int = max_ast_depth

        self.defs: List[ReferenceDetail] = []
        self.imports: List[ReferenceDetail] = []
        self.calls: List[ReferenceDetail] = []
        self.subclasses: List[ReferenceDetail] = []
        self.ast_callers: Set[str] = set()
        self.ast_callees: Set[str] = set()
        self.catalog_symbols: List[Tuple[str, Optional[str], str]] = []

    def generic_visit(self, node: ast.AST):
        if self.current_depth >= self.max_ast_depth:
            return
        self.current_depth += 1
        try:
            super().generic_visit(node)
        finally:
            self.current_depth -= 1

    def visit_ClassDef(self, node: ast.ClassDef):
        loc = f"{self.rel_path}:{node.lineno}"
        self.catalog_symbols.append((node.name, "class", loc))

        base_names: List[str] = []
        for b in node.bases:
            try:
                base_names.append(ast.unparse(b))
            except Exception:
                if isinstance(b, ast.Name):
                    base_names.append(b.id)

        bases_str = f"({', '.join(base_names)})" if base_names else ""

        if node.name == self.clean_symbol:
            self.defs.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="class",
                    context=f"class {node.name}{bases_str}:",
                    bases=base_names if base_names else None,
                )
            )

        # Check if this class inherits from clean_symbol (class hierarchy)
        if any(self.clean_symbol == b or b.endswith(f".{self.clean_symbol}") for b in base_names):
            self.subclasses.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="subclass",
                    context=f"class {node.name}{bases_str} inherits from {self.clean_symbol}",
                    bases=base_names,
                )
            )

        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_function(node)

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        kind = "method" if self.scope_stack else "function"
        loc = f"{self.rel_path}:{node.lineno}"
        full_scope = ".".join(self.scope_stack + [node.name]) if self.scope_stack else node.name
        self.catalog_symbols.append((node.name, kind, loc))
        self.catalog_symbols.append((full_scope, kind, loc))

        if node.name == self.clean_symbol or full_scope == self.clean_symbol:
            ret_str = ""
            if getattr(node, "returns", None):
                try:
                    ret_str = f" -> {ast.unparse(node.returns)}"
                except Exception:
                    pass
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            self.defs.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind=kind,
                    context=f"{prefix} {node.name}(...){ret_str}",
                )
            )

        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ImportFrom(self, node: ast.ImportFrom):
        dots = "." * node.level if node.level else ""
        mod = f"{dots}{node.module or ''}"
        mod_prefix = f"from {mod} " if mod else ""
        loc = f"{self.rel_path}:{node.lineno}"
        for a in node.names:
            alias_str = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
            desc = f"{mod_prefix}{alias_str}".strip()
            self.catalog_symbols.append((a.name, "import", loc))
            if a.asname:
                self.catalog_symbols.append((a.asname, "import", loc))

            if a.name == self.clean_symbol or a.asname == self.clean_symbol:
                self.imports.append(
                    ReferenceDetail(
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        kind="import",
                        context=desc,
                    )
                )

    def visit_Import(self, node: ast.Import):
        loc = f"{self.rel_path}:{node.lineno}"
        for a in node.names:
            mod_parts = a.name.split(".")
            desc = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
            self.catalog_symbols.append((a.name, "module", loc))
            if a.asname:
                self.catalog_symbols.append((a.asname, "module", loc))

            if (
                a.name == self.clean_symbol
                or self.clean_symbol in mod_parts
                or a.asname == self.clean_symbol
            ):
                self.imports.append(
                    ReferenceDetail(
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        kind="import",
                        context=desc,
                    )
                )

    def visit_Call(self, node: ast.Call):
        func_name = ""
        is_attr = False
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            is_attr = True

        enclosing = ".".join(self.scope_stack) if self.scope_stack else "<module>"

        if func_name == self.clean_symbol:
            kind_str = f".{self.clean_symbol}()" if is_attr else f"{self.clean_symbol}()"
            self.calls.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="call",
                    context=kind_str,
                    caller=enclosing if enclosing != "<module>" else None,
                    callee=self.clean_symbol,
                )
            )
            if enclosing != "<module>":
                self.ast_callers.add(f"{enclosing} ({self.rel_path}:{node.lineno})")

        if (
            self.scope_stack
            and (self.scope_stack[-1] == self.clean_symbol or self.clean_symbol in self.scope_stack)
            and func_name
            and func_name != self.clean_symbol
        ):
            self.ast_callees.add(f"{func_name} ({self.rel_path}:{node.lineno})")

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr == self.clean_symbol:
            enclosing = ".".join(self.scope_stack) if self.scope_stack else "<module>"
            self.calls.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="attribute",
                    context=f".{self.clean_symbol}",
                    caller=enclosing if enclosing != "<module>" else None,
                )
            )
        self.generic_visit(node)


def analyze_symbol(
    symbol_name: str,
    target_path: pathlib.Path,
    ws_root: pathlib.Path,
    explicit_graph_path: Optional[str] = None,
    focus: Optional[str] = None,
) -> CodeGraphResult:
    """Analyze symbol references, graph reachability, definitions, and class hierarchy."""
    clean_symbol = symbol_name.strip()
    is_valid_ident = clean_symbol.isidentifier()

    # 1. Discover and load precomputed codebase graph if available
    graph_file = discover_graph_file(ws_root, explicit_graph_path, query_symbol=clean_symbol)
    graph_indexes: Dict[str, Any] = {}
    node_count = 0
    edge_count = 0
    graph_loaded = False

    if graph_file:
        graph_indexes, node_count, edge_count = load_and_index_graph(graph_file)
        if node_count > 0:
            graph_loaded = True

    if graph_loaded:
        graph_status = GraphStatus(
            graph_loaded=True,
            graph_path=str(graph_file),
            node_count=node_count,
            edge_count=edge_count,
            fallback_mode="hybrid",
            diagnostic_message=(
                f"Loaded precomputed codebase graph ({node_count} nodes, {edge_count} edges) "
                f"from {graph_file}."
            ),
        )
    else:
        graph_status = GraphStatus(
            graph_loaded=False,
            graph_path=None,
            node_count=0,
            edge_count=0,
            fallback_mode="live_ast",
            diagnostic_message=(
                "Precomputed codebase graph JSON is missing or inaccessible. "
                "Where graphs live: Precomputed codebase graphs are stored as 'graphs/<repo>.json' "
                "or 'data/graphs/<repo>.json' (NetworkX node-link JSON format). "
                "Fallback instructions: Automatically falling back to live repository AST analysis "
                "across all Python files in the workspace."
            ),
        )

    # 2. Collect files to scan (capped at 400 files to guarantee zero hangs)
    file_list = collect_py_files(target_path, ws_root, max_files=400)

    # 3. Perform live AST scanning & text search
    defs: List[ReferenceDetail] = []
    imports: List[ReferenceDetail] = []
    calls: List[ReferenceDetail] = []
    subclasses: List[ReferenceDetail] = []
    text_matches: List[ReferenceDetail] = []
    ast_callers: Set[str] = set()
    ast_callees: Set[str] = set()
    ast_symbol_catalog: List[Tuple[str, Optional[str], str]] = []

    seen_defs: Set[Tuple[str, int]] = set()
    seen_imports: Set[Tuple[str, int]] = set()
    seen_calls: Set[Tuple[str, int, str]] = set()
    seen_subclasses: Set[Tuple[str, int]] = set()
    seen_text: Set[Tuple[str, int]] = set()

    for full_path in file_list:
        try:
            rel_path = full_path.relative_to(ws_root)
        except ValueError:
            rel_path = full_path

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                source = f.read()
        except UnicodeDecodeError:
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    source = f.read()
            except Exception:
                continue
        except (PermissionError, OSError):
            continue

        if is_valid_ident:
            try:
                tree = ast.parse(source, filename=str(rel_path))
                collector = AstReferenceCollector(str(rel_path), clean_symbol)
                collector.visit(tree)

                for d in collector.defs:
                    key = (d.file_path, d.line_number)
                    if key not in seen_defs:
                        seen_defs.add(key)
                        defs.append(d)

                for imp in collector.imports:
                    key = (imp.file_path, imp.line_number)
                    if key not in seen_imports:
                        seen_imports.add(key)
                        imports.append(imp)

                for c in collector.calls:
                    key = (c.file_path, c.line_number, c.context)
                    if key not in seen_calls:
                        seen_calls.add(key)
                        calls.append(c)

                for sub in collector.subclasses:
                    key = (sub.file_path, sub.line_number)
                    if key not in seen_subclasses:
                        seen_subclasses.add(key)
                        subclasses.append(sub)

                ast_callers.update(collector.ast_callers)
                ast_callees.update(collector.ast_callees)
                ast_symbol_catalog.extend(collector.catalog_symbols)
            except (SyntaxError, ValueError, MemoryError, RecursionError):
                pass

        if clean_symbol.lower() in source.lower():
            for lineno, line in enumerate(source.splitlines(), 1):
                if clean_symbol.lower() in line.lower():
                    clean_line = line.strip()
                    if len(clean_line) > 140:
                        clean_line = clean_line[:137] + "..."
                    key = (str(rel_path), lineno)
                    if key not in seen_text:
                        seen_text.add(key)
                        text_matches.append(
                            ReferenceDetail(
                                file_path=str(rel_path),
                                line_number=lineno,
                                kind="text",
                                context=clean_line,
                            )
                        )
                    if len(text_matches) >= 30:
                        break
            if len(text_matches) >= 30:
                pass

    # 4. Resolve node in graph if loaded
    resolved_symbol: Optional[str] = None
    graph_callers: List[str] = []
    graph_callees: List[str] = []

    if graph_loaded:
        resolved_symbol = resolve_graph_node(clean_symbol, graph_indexes)
        if resolved_symbol:
            in_edges = graph_indexes.get("in_edges", {})
            out_edges = graph_indexes.get("out_edges", {})
            graph_callers = in_edges.get(resolved_symbol, [])
            graph_callees = out_edges.get(resolved_symbol, [])

            class_prefix = f"{resolved_symbol}."
            for nid, callers_list in in_edges.items():
                if nid.startswith(class_prefix):
                    graph_callers.extend(callers_list)
            for nid, callees_list in out_edges.items():
                if nid.startswith(class_prefix):
                    graph_callees.extend(callees_list)

            # If AST definitions were not found, synthesize from graph node content
            if not defs:
                node = graph_indexes.get("node_map", {}).get(resolved_symbol, {})
                node_text = node.get("text", "") or ""
                first_line = node_text.splitlines()[0].strip() if node_text else ""
                mod_parts = resolved_symbol.split(".")
                inferred_file = "/".join(mod_parts[:-1]) + ".py" if len(mod_parts) > 1 else f"{resolved_symbol}.py"
                inferred_kind = "class" if first_line.startswith("class ") else "function"

                defs.append(
                    ReferenceDetail(
                        file_path=inferred_file,
                        line_number=1,
                        kind=inferred_kind,
                        context=first_line if first_line else f"{inferred_kind} {clean_symbol}",
                    )
                )

                for child_nid, child_node in graph_indexes.get("node_map", {}).items():
                    if child_nid.startswith(class_prefix) and "." not in child_nid[len(class_prefix):]:
                        child_name = child_nid[len(class_prefix):]
                        child_text = child_node.get("text", "") or ""
                        c_line = child_text.splitlines()[0].strip() if child_text else f"def {child_name}(...)"
                        defs.append(
                            ReferenceDetail(
                                file_path=inferred_file,
                                line_number=1,
                                kind="method",
                                context=c_line[:120],
                            )
                        )
                        if len(defs) >= 20:
                            break

    # 5. Merge callers and callees
    all_callers: List[str] = []
    for c in list(ast_callers) + graph_callers:
        if c not in all_callers:
            all_callers.append(c)

    all_callees: List[str] = []
    for c in list(ast_callees) + graph_callees:
        if c not in all_callees:
            all_callees.append(c)

    found = bool(resolved_symbol or defs or imports or calls or subclasses)
    if not found and not is_valid_ident and text_matches:
        found = True

    # 6. Explanations, Suggestions, and Top-Level Symbols
    inspection_hint: Optional[str] = None
    suggestions: List[SymbolSuggestion] = []
    did_you_mean: List[str] = []
    top_repo_symbols: List[str] = []
    next_steps: List[str] = []

    if clean_symbol.startswith("_"):
        inspection_hint = (
            f"Symbol '{clean_symbol}' starts with an underscore ('_'), indicating a private or "
            "internal function or attribute. Private symbols are often scoped locally within "
            "their defining module or class body and may not be registered as top-level public nodes "
            "in precomputed code graphs.\n"
            "Recommended inspection actions:\n"
            f"  1. Search definitions with fast-grep: grep.py 'def {clean_symbol}'\n"
            f"  2. Search attribute accesses: grep.py '.{clean_symbol}'\n"
            "  3. Inspect the containing module file directly using map.py --file <path>."
        )
    elif "." in clean_symbol:
        leaf = clean_symbol.split(".")[-1]
        parent = clean_symbol.rsplit(".", 1)[0]
        inspection_hint = (
            f"Symbol '{clean_symbol}' is a qualified or dotted path. Qualified paths depend on "
            "import bindings and module hierarchies. If the qualified path fails to resolve:\n"
            f"  1. Search for the unqualified leaf symbol: '{leaf}'\n"
            f"  2. Search for the enclosing module or class: '{parent}'\n"
            f"  3. Trace references with fast-grep: grep.py '{leaf}'\n"
            "  4. Inspect the parent module file directly using map.py --file <path>."
        )
    elif not is_valid_ident:
        inspection_hint = (
            f"Query '{clean_symbol}' is not a valid Python identifier. code-map --symbol specializes "
            "in Python AST symbols (classes, functions, methods, variables). For arbitrary text patterns, "
            f"use fast-grep: grep.py '{clean_symbol}'"
        )

    if found:
        active_name = resolved_symbol or clean_symbol
        explanation = f"Symbol '{clean_symbol}' was successfully traced across the repository."
        caller_callee_summary = (
            f"Symbol '{active_name}' has {len(all_callers)} inbound caller(s) "
            f"and {len(all_callees)} outbound callee(s)."
        )
        if defs:
            first_def = defs[0]
            next_steps.append(f"Inspect defining module: python3 map.py --file {first_def.file_path}")
        if focus == "callers" and all_callers:
            next_steps.append(f"Inspect top caller: python3 map.py --symbol {all_callers[0].split()[0]}")
        elif focus == "callees" and all_callees:
            next_steps.append(f"Inspect top callee: python3 map.py --symbol {all_callees[0].split()[0]}")
        next_steps.append(f"Search direct calls across repo: grep.py '{clean_symbol}'")
    else:
        if graph_loaded:
            explanation = (
                f"Symbol '{clean_symbol}' was not found in the precomputed codebase graph "
                f"({node_count} nodes searched) or workspace AST."
            )
        else:
            explanation = (
                f"Symbol '{clean_symbol}' was not found in the precomputed codebase graph "
                f"(graph JSON was missing or inaccessible) or workspace AST ({len(file_list)} files scanned)."
            )

        candidates: List[Tuple[str, Optional[str], Optional[str]]] = []
        if graph_loaded:
            for nid in graph_indexes.get("node_ids", []):
                mod_parts = nid.split(".")
                inferred_loc = "/".join(mod_parts[:-1]) + ".py" if len(mod_parts) > 1 else None
                candidates.append((nid, "graph_node", inferred_loc))
                leaf = nid.split(".")[-1]
                if leaf:
                    candidates.append((leaf, "graph_node", inferred_loc))

        for sym, kind, loc in ast_symbol_catalog:
            candidates.append((sym, kind, loc))

        suggestions = compute_fuzzy_suggestions(clean_symbol, candidates, top_n=6, cutoff=0.30)
        did_you_mean = [s.symbol for s in suggestions]
        caller_callee_summary = f"Symbol '{clean_symbol}' was not found in the codebase graph."

        # Collect available top-level public symbols from the workspace to guide the LLM
        top_repo_symbols = get_top_repo_symbols(ws_root, max_symbols=12)

        if suggestions:
            top_s = suggestions[0]
            if top_s.inspect_command:
                next_steps.append(f"Try closest suggested symbol: {top_s.inspect_command}")
            if top_s.file_command:
                next_steps.append(f"Inspect candidate file: {top_s.file_command}")
        next_steps.append(f"Search codebase text with fast-grep: grep.py '{clean_symbol}'")
        next_steps.append("View repository structure and modules: python3 map.py")

    return CodeGraphResult(
        mode="symbol",
        query=symbol_name,
        found=found,
        resolved_symbol=resolved_symbol,
        focus=focus,
        explanation=explanation,
        inspection_hint=inspection_hint,
        graph_status=graph_status,
        definitions=defs,
        imports=imports,
        calls=calls,
        subclasses=subclasses,
        text_occurrences=text_matches,
        callers=all_callers,
        callees=all_callees,
        caller_callee_summary=caller_callee_summary,
        suggestions=suggestions,
        did_you_mean=did_you_mean,
        available_top_symbols=top_repo_symbols,
        next_steps=next_steps,
    )


def format_symbol_report(result: CodeGraphResult) -> str:
    """Format CodeGraphResult into concise, informative text report with actionable LLM guidance."""
    lines: List[str] = [
        "=" * 80,
        "CODE-MAP: SYMBOL REFERENCE & REACHABILITY REPORT",
        "=" * 80,
        f"QUERY: {result.query}",
        f"STATUS: {'FOUND' if result.found else 'NOT FOUND'}",
    ]

    if result.focus:
        lines.append(f"FOCUS: {result.focus.upper()}")

    if result.resolved_symbol:
        lines.append(f"RESOLVED SYMBOL: {result.resolved_symbol}")

    lines.append(f"EXPLANATION: {result.explanation}")
    lines.append("")

    # If focus == 'callers' or 'callees', highlight them prominently at the top
    if result.focus == "callers":
        lines.append("=" * 40)
        lines.append(f"TARGET INBOUND CALLERS FOR '{result.query}':")
        lines.append("=" * 40)
        if result.callers:
            lines.append(f"  Total Inbound Callers: {len(result.callers)}")
            for clr in result.callers[:30]:
                lines.append(f"  👉 {clr}")
        else:
            lines.append("  (0 direct static callers recorded)")
        lines.append("")
    elif result.focus == "callees":
        lines.append("=" * 40)
        lines.append(f"TARGET OUTBOUND CALLEES FOR '{result.query}':")
        lines.append("=" * 40)
        if result.callees:
            lines.append(f"  Total Outbound Callees: {len(result.callees)}")
            for cle in result.callees[:30]:
                lines.append(f"  👉 {cle}")
        else:
            lines.append("  (0 direct static callees recorded)")
        lines.append("")

    lines.append("GRAPH TOPOLOGY:")
    if result.graph_status.graph_loaded:
        lines.append(f"  {result.graph_status.diagnostic_message}")
    else:
        lines.append("  Precomputed codebase graph JSON is missing or inaccessible.")
        lines.append("  Where graphs live: Precomputed codebase graphs are stored as 'graphs/<repo>.json'")
        lines.append("  or 'data/graphs/<repo>.json' (NetworkX node-link JSON).")
        lines.append("  Fallback instructions: Utilizing live repository AST scan for symbol tracing.")
    lines.append("")

    if result.found:
        lines.append(f"DEFINITIONS ({len(result.definitions)}):")
        if result.definitions:
            for d in result.definitions[:20]:
                bases_info = f" [bases: {', '.join(d.bases)}]" if d.bases else ""
                lines.append(f"  - {d.file_path}:{d.line_number} ({d.kind}): {d.context}{bases_info}")
        else:
            lines.append("  (none found in AST)")
        lines.append("")

        if result.subclasses:
            lines.append(f"CLASS HIERARCHY / SUBCLASSES ({len(result.subclasses)}):")
            for sub in result.subclasses[:15]:
                lines.append(f"  - {sub.file_path}:{sub.line_number}: {sub.context}")
            lines.append("")

        lines.append(f"IMPORTS ({len(result.imports)}):")
        if result.imports:
            for imp in result.imports[:20]:
                lines.append(f"  - {imp.file_path}:{imp.line_number}: {imp.context}")
        else:
            lines.append("  (none)")
        lines.append("")

        lines.append(f"CALLS & ATTRIBUTES ({len(result.calls)}, first 20):")
        if result.calls:
            for c in result.calls[:20]:
                caller_info = f" [caller: {c.caller}]" if c.caller else ""
                lines.append(f"  - {c.file_path}:{c.line_number} ({c.kind}): {c.context}{caller_info}")
        else:
            lines.append("  (none)")
        lines.append("")

        if not result.focus:
            lines.append("CALL GRAPH REACHABILITY:")
            lines.append(f"  {result.caller_callee_summary}")
            if result.callers:
                lines.append(f"  Inbound Callers ({len(result.callers)}, first 10):")
                for clr in result.callers[:10]:
                    lines.append(f"    - {clr}")
            else:
                lines.append("  Inbound Callers: (0 direct static callers recorded)")

            if result.callees:
                lines.append(f"  Outbound Callees ({len(result.callees)}, first 10):")
                for cle in result.callees[:10]:
                    lines.append(f"    - {cle}")
            else:
                lines.append("  Outbound Callees: (0 direct static callees recorded)")
            lines.append("")

        if result.text_occurrences:
            lines.append("TEXT OCCURRENCES (first 15):")
            for t in result.text_occurrences[:15]:
                lines.append(f"  - {t.file_path}:{t.line_number}: {t.context}")
            lines.append("")

    else:
        lines.append("WHY THIS QUERY FAILED:")
        lines.append(f"  Symbol '{result.query}' was not identified in the codebase graph or repository AST.")
        if result.query.startswith("_"):
            lines.append(f"  • Note: Symbol starts with '_', indicating a private/internal function or attribute.")
            lines.append("    Private symbols are often not registered as public graph nodes.")
        elif "." in result.query:
            lines.append(f"  • Note: Symbol contains dots. Dotted path queries depend on exact module import hierarchy.")
        elif not result.query.isidentifier():
            lines.append(f"  • Note: Query '{result.query}' is not a valid Python identifier.")
        else:
            lines.append("  • The symbol name may contain a typo, or the symbol is defined dynamically at runtime.")
        lines.append("")

        lines.append("SUGGESTIONS:")
        if result.suggestions:
            lines.append("  Did you mean one of these symbols?")
            for idx, s in enumerate(result.suggestions, 1):
                loc_str = f" [location: {s.location}]" if s.location else ""
                kind_str = f" ({s.kind})" if s.kind else ""
                lines.append(f"    {idx}. {s.symbol}{kind_str} (similarity: {s.similarity:.2f}){loc_str}")
                if s.inspect_command:
                    lines.append(f"       👉 {s.inspect_command}")
                if s.file_command:
                    lines.append(f"       👉 {s.file_command}")
        else:
            lines.append("  No close fuzzy matches found in codebase graph or repository AST.")
        lines.append("")

        if result.available_top_symbols:
            lines.append("TOP-LEVEL PUBLIC SYMBOLS IN REPOSITORY:")
            for sym in result.available_top_symbols:
                clean_sym = sym.replace("class ", "").replace("def ", "").replace("()", "")
                lines.append(f"  • {sym}  ->  python3 map.py --symbol {clean_sym}")
            lines.append("")

    if result.inspection_hint:
        lines.append("INSPECTION HINT:")
        for hint_line in result.inspection_hint.splitlines():
            lines.append(f"  {hint_line}")
        lines.append("")

    if result.next_steps:
        lines.append("ACTIONABLE NEXT STEPS:")
        for step in result.next_steps:
            lines.append(f"  👉 {step}")
        lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


# ==============================================================================
# AST Formatting & Symbol Extraction (--file mode)
# ==============================================================================


def format_args(args_node: ast.arguments) -> str:
    """Format argument list string from AST node, keeping it concise."""
    try:
        raw = ast.unparse(args_node)
        s = " ".join(raw.split())
        if len(s) > 60:
            s = s[:57] + "..."
        return s
    except Exception:
        pass

    names: List[str] = []
    for a in args_node.posonlyargs + args_node.args:
        names.append(a.arg)
    if args_node.vararg:
        names.append("*" + args_node.vararg.arg)
    for a in args_node.kwonlyargs:
        names.append(a.arg)
    if args_node.kwarg:
        names.append("**" + args_node.kwarg.arg)
    s = ", ".join(names)
    if len(s) > 60:
        s = s[:57] + "..."
    return s


def format_return(ret_node: Optional[ast.AST]) -> str:
    """Format return type annotation string from AST node."""
    if ret_node is None:
        return ""
    try:
        s = ast.unparse(ret_node)
        s = " ".join(s.split())
        return f" -> {s}"
    except Exception:
        return ""


def format_docstring(node: ast.AST, indent: str = "    ") -> Optional[str]:
    """Extract and format a one-line docstring summary."""
    try:
        doc = ast.get_docstring(node)
        if not doc:
            return None
        first_line = doc.strip().split("\n")[0].strip()
        if not first_line:
            return None
        if len(first_line) > 70:
            first_line = first_line[:67] + "..."
        return f'{indent}"""{first_line}"""'
    except Exception:
        return None


def get_symbols(
    body: List[ast.stmt],
    is_class: bool = False,
    current_depth: int = 0,
    max_depth: int = 8,
) -> List[Tuple[str, str, str, int, int, Optional[str]]]:
    """Extract symbol items from AST statements with recursion bounds.

    Returns list of tuples: (kind, name, signature, start_line, end_line, docstring).
    """
    if current_depth >= max_depth:
        return []

    items: List[Tuple[str, str, str, int, int, Optional[str]]] = []
    for node in body:
        try:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                args_str = format_args(node.args)
                ret_str = format_return(getattr(node, "returns", None))
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                indent = "    " if is_class else "  "
                sig = f"{indent}{prefix} {node.name}({args_str}){ret_str} [{start}-{end}]"
                doc = format_docstring(node, indent=indent + "  ")
                items.append((prefix, node.name, sig, start, end, doc))
            elif isinstance(node, ast.ClassDef):
                bases_str = ""
                if node.bases:
                    base_names: List[str] = []
                    for b in node.bases:
                        try:
                            base_names.append(ast.unparse(b))
                        except Exception:
                            if isinstance(b, ast.Name):
                                base_names.append(b.id)
                    if base_names:
                        bases_str = f"({', '.join(base_names)})"
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                sig = f"  class {node.name}{bases_str} [{start}-{end}]"
                doc = format_docstring(node, indent="    ")
                items.append(("class", node.name, sig, start, end, doc))
                methods = get_symbols(node.body, is_class=True, current_depth=current_depth + 1, max_depth=max_depth)
                items.extend(methods)
        except (RecursionError, MemoryError):
            continue
    return items


def parse_and_map_file(
    py_file: pathlib.Path,
    ws: pathlib.Path,
) -> Tuple[ModuleSummary, Optional[MapDiagnostic]]:
    """Parse a single Python file, extract AST symbols, and diagnose syntax/permission/encoding errors."""
    try:
        rel_display = py_file.relative_to(ws)
    except ValueError:
        rel_display = py_file

    try:
        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        diag = MapDiagnostic(
            level="warning",
            category="encoding_error",
            message=f"File '{rel_display}' contains unparseable binary or invalid UTF-8 encoding: {e}",
            target_path=str(rel_display),
            guidance="Verify file encoding (UTF-8 required) or verify that this is a Python source file.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except PermissionError as e:
        diag = MapDiagnostic(
            level="error",
            category="permission_denied",
            message=f"Permission denied reading file '{rel_display}': {e}",
            target_path=str(rel_display),
            guidance="Check file permissions or run with appropriate access privileges.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except OSError as e:
        diag = MapDiagnostic(
            level="error",
            category="unparseable_file",
            message=f"Failed to read file '{rel_display}': {e}",
            target_path=str(rel_display),
            guidance="Verify file exists and filesystem is accessible.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag

    try:
        tree = ast.parse(content, filename=str(py_file))
    except SyntaxError as e:
        err_line = e.lineno or 1
        err_col = e.offset or 1
        err_msg = e.msg or "invalid syntax"

        content_lines = content.splitlines()
        if e.text:
            source_line = e.text.rstrip("\r\n").expandtabs(4)
        elif 1 <= err_line <= len(content_lines):
            source_line = content_lines[err_line - 1].expandtabs(4)
        else:
            source_line = ""

        gutter = f"    {err_line} | "
        safe_col = max(1, min(err_col, len(source_line) + 1))
        caret_line = " " * (len(gutter) + safe_col - 1) + "^"
        snippet = f"{gutter}{source_line}\n{caret_line}"

        guidance = (
            f"File '{rel_display}' contains invalid Python syntax at line {err_line}, column {err_col}. "
            "This error prevents AST parsing and was likely introduced by a recent edit_file call "
            "(e.g., unclosed parenthesis/bracket/quote, mismatched indentation, or incomplete statement). "
            f"Inspect line {err_line} or run diff-inspect / git diff to repair syntax."
        )

        diag = MapDiagnostic(
            level="error",
            category="syntax_error",
            message=f"SyntaxError: {err_msg} (line {err_line}, column {err_col})",
            target_path=str(rel_display),
            line=err_line,
            column=err_col,
            snippet=snippet,
            guidance=guidance,
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except RecursionError:
        diag = MapDiagnostic(
            level="warning",
            category="recursion_limit_exceeded",
            message=f"AST nesting depth exceeds limit in '{rel_display}'.",
            target_path=str(rel_display),
            guidance="File contains deeply nested structures; outline skipped to prevent stack overflow.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except Exception as e:
        diag = MapDiagnostic(
            level="warning",
            category="unparseable_file",
            message=f"AST parse failure in '{rel_display}': {e}",
            target_path=str(rel_display),
            guidance="Inspect file for non-standard Python syntax.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag

    raw_symbols = get_symbols(tree.body)
    symbol_items: List[SymbolItem] = []
    for kind, name, sig, start, end, doc in raw_symbols:
        symbol_items.append(
            SymbolItem(
                kind=kind,
                name=name,
                signature=sig,
                start_line=start,
                end_line=end,
                docstring=doc,
            )
        )

    return (
        ModuleSummary(
            path=str(rel_display),
            symbols=symbol_items,
            symbol_count=len(symbol_items),
        ),
        None,
    )


def generate_file_skeleton(target_str: str, max_lines: int = 120) -> FileSkeletonResult:
    """Generate compact AST skeleton for a target file or directory up to max_lines budget."""
    ws = get_workspace_dir()
    target_path, clean_target = resolve_target(target_str, ws)

    # 1. Target does not exist: Provide actionable diagnostics & suggestions
    if target_path is None or not target_path.exists():
        diag_msg = f"Path '{target_str}' does not exist in /workspace."
        suggestions = find_closest_paths(clean_target, ws)
        layout_items = get_top_level_layout(ws)
        guidance = (
            f"Target '{target_str}' was not found in /workspace. "
            "Review the suggested closest matches or top-level repository layout below to select an existing file."
        )
        diag = MapDiagnostic(
            level="error",
            category="missing_path",
            message=diag_msg,
            target_path=target_str,
            suggestions=suggestions,
            guidance=guidance,
        )
        lines: List[str] = [
            f"[code-map] {diag_msg}",
            "",
            "WHY THIS FAILED:",
            f"  Target path '{target_str}' does not exist in the active workspace.",
            "  Common causes:",
            "  1. Typo in directory or file name.",
            "  2. Missing folder prefix (e.g. 'src/' or package directory).",
            "  3. Missing or wrong file extension (.py).",
            "",
        ]
        if str(ws) != "/workspace":
            lines.append(f"  (Active workspace root: {ws})")
            lines.append("")
        if suggestions:
            lines.append("💡 Suggested closest existing paths:")
            for s in suggestions:
                lines.append(f"  • {s}")
                clean_s = s.replace("📁 ", "").replace("📄 ", "").rstrip("/")
                lines.append(f"     👉 python3 map.py --file {clean_s}")
            lines.append("")
        if layout_items:
            lines.append("📂 Top-level repository layout (/workspace):")
            for item in layout_items:
                lines.append(f"  {item.summary}")
            lines.append("")

        next_steps: List[str] = []
        if suggestions:
            for s in suggestions[:3]:
                best = s.replace("📁 ", "").replace("📄 ", "").rstrip("/")
                next_steps.append(f"Inspect closest match: python3 map.py --file {best}")
        next_steps.append("View repository overview and packages: python3 map.py")

        if next_steps:
            lines.append("👉 Actionable next steps:")
            for step in next_steps:
                lines.append(f"  • {step}")
            lines.append("")

        rendered = "\n".join(lines)
        return FileSkeletonResult(
            mode="file",
            target=target_str,
            workspace_root=str(ws),
            success=False,
            modules=[],
            total_files=0,
            total_symbols=0,
            diagnostics=[diag],
            top_level_layout=layout_items,
            is_truncated=False,
            rendered_text=rendered,
            next_steps=next_steps,
        )

    # 2. Target exists: Collect .py files (single file or directory)
    py_files = collect_py_files(target_path, ws, max_files=100)

    # Directory has no .py files: Forgivingly list directory contents and point to python code
    if not py_files:
        items_in_dir: List[str] = []
        try:
            if target_path.is_dir():
                for item in sorted(target_path.iterdir()):
                    if not item.name.startswith("."):
                        icon = "📁" if item.is_dir() else "📄"
                        items_in_dir.append(f"{icon} {item.name}")
        except Exception:
            pass

        diag_msg = f"No Python source files (.py) found in target '{target_str}'."
        diag = MapDiagnostic(
            level="warning",
            category="empty_target",
            message=diag_msg,
            target_path=target_str,
            suggestions=items_in_dir[:6],
            guidance="Specify a directory or file that contains Python source code.",
        )
        lines = [
            f"[code-map] {diag_msg}",
            "",
            "WHY THIS FAILED:",
            f"  Target '{target_str}' exists but contains no Python source files (.py).",
            "",
        ]
        if items_in_dir:
            lines.append("Contents of target directory:")
            for itm in items_in_dir[:10]:
                lines.append(f"  {itm}")
            lines.append("")

        layout_items = get_top_level_layout(ws)
        if layout_items:
            lines.append("📂 Directories with Python code (/workspace):")
            for item in layout_items:
                if item.is_dir and ".py" in item.summary:
                    lines.append(f"  {item.summary}")
            lines.append("")

        rendered = "\n".join(lines)
        return FileSkeletonResult(
            mode="file",
            target=target_str,
            workspace_root=str(ws),
            success=False,
            modules=[],
            total_files=0,
            total_symbols=0,
            diagnostics=[diag],
            top_level_layout=layout_items,
            is_truncated=False,
            rendered_text=rendered,
            next_steps=["Run 'python3 map.py' to see packages with Python code"],
        )

    # 3. Target is a single file with syntax error: Special detailed diagnostic
    if len(py_files) == 1:
        mod_summary, diag = parse_and_map_file(py_files[0], ws)
        if diag and diag.category == "syntax_error":
            single_file_lines = [
                f"[code-map: SyntaxError in {mod_summary.path}]",
                f"  Location: Line {diag.line}, Column {diag.column}",
                f"  Error: {diag.message}",
                "",
                "  Code Snippet:",
            ]
            if diag.snippet:
                single_file_lines.extend(diag.snippet.splitlines())
            if diag.guidance:
                single_file_lines.append("")
                single_file_lines.append(f"  Guidance: {diag.guidance}")

            rendered = "\n".join(single_file_lines)
            return FileSkeletonResult(
                mode="file",
                target=target_str,
                workspace_root=str(ws),
                success=True,
                modules=[mod_summary],
                total_files=1,
                total_symbols=0,
                diagnostics=[diag],
                top_level_layout=[],
                is_truncated=False,
                rendered_text=rendered,
                next_steps=[f"Fix syntax error at line {diag.line} using edit_file"],
            )

    # 4. Multi-file or single file AST outline generation with strict max_lines budget
    output_lines: List[str] = []
    modules: List[ModuleSummary] = []
    all_diagnostics: List[MapDiagnostic] = []
    total_symbols = 0
    total_files_parsed = 0
    is_truncated = False

    for py_file in py_files:
        mod_summary, diag = parse_and_map_file(py_file, ws)
        modules.append(mod_summary)
        if diag:
            all_diagnostics.append(diag)

        file_lines: List[str] = [f"{mod_summary.path}:"]
        if mod_summary.syntax_error:
            err = mod_summary.syntax_error
            file_lines.append(f"  ⚠️  [SyntaxError at line {err.line}, col {err.column}: {err.message}]")
            if err.snippet:
                file_lines.extend(err.snippet.splitlines())
        else:
            if not mod_summary.symbols:
                continue
            for sym in mod_summary.symbols:
                file_lines.append(sym.signature)
                if sym.docstring:
                    file_lines.append(sym.docstring)

        if len(output_lines) + len(file_lines) > max_lines:
            remaining = len(py_files) - total_files_parsed
            output_lines.append(f"... [Truncated at {max_lines} lines; {remaining} more file(s)]")
            is_truncated = True
            break

        output_lines.extend(file_lines)
        total_symbols += mod_summary.symbol_count
        total_files_parsed += 1

    syntax_err_count = sum(1 for m in modules if m.syntax_error)
    summary_parts = [f"[code-map: {total_symbols} symbols across {total_files_parsed} file(s)"]
    if syntax_err_count > 0:
        summary_parts.append(f" ({syntax_err_count} file(s) had syntax errors)")
    summary_parts.append("]")
    output_lines.append("".join(summary_parts))

    rendered = "\n".join(output_lines)

    next_steps: List[str] = []
    if modules and modules[0].symbols:
        first_sym = modules[0].symbols[0].name
        next_steps.append(f"Trace symbol call-graph: python3 map.py --symbol {first_sym}")
    if len(py_files) > 1 and is_truncated:
        first_mod = modules[0].path
        next_steps.append(f"Inspect single module outline: python3 map.py --file {first_mod}")

    return FileSkeletonResult(
        mode="file",
        target=target_str,
        workspace_root=str(ws),
        success=True,
        modules=modules,
        total_files=total_files_parsed,
        total_symbols=total_symbols,
        diagnostics=all_diagnostics,
        top_level_layout=[],
        is_truncated=is_truncated,
        rendered_text=rendered,
        next_steps=next_steps,
    )


# ==============================================================================
# Workspace Repository Overview & Usage Guide (Empty Calls & '.' / '/workspace')
# ==============================================================================


def generate_workspace_overview(ws: pathlib.Path) -> WorkspaceOverviewResult:
    """Generate forgiving repository overview and copy-pasteable usage guide tailored to current workspace."""
    layout_items = get_top_level_layout(ws)

    # Discovered packages: top-level dirs with .py files
    discovered_packages: List[str] = []
    for item in layout_items:
        if item.is_dir and ".py" in item.summary:
            discovered_packages.append(item.name)

    # Discovered sample files
    sample_files = collect_py_files(ws, ws, max_files=15)
    core_files = [p for p in sample_files if "test" not in p.name.lower() and "test" not in str(p).lower()]
    chosen_files = core_files if core_files else sample_files
    key_modules: List[str] = []
    for p in chosen_files[:3]:
        try:
            rel = str(p.relative_to(ws))
            key_modules.append(rel)
        except Exception:
            pass

    # Sample symbols
    sample_symbols = get_top_repo_symbols(ws, max_symbols=6)
    clean_sample_symbols = [
        s.replace("class ", "").replace("def ", "").replace("()", "")
        for s in sample_symbols
    ]

    # Generate tailored copy-pasteable commands
    example_mod = key_modules[0] if key_modules else "example.py"
    example_pkg = discovered_packages[0] if discovered_packages else "."
    example_sym = clean_sample_symbols[0] if clean_sample_symbols else "main"

    commands = [
        f"python3 map.py --file {example_mod}           # Compact AST outline of a key module",
        f"python3 map.py --file {example_pkg}                 # Map package directory structure",
        f"python3 map.py --symbol {example_sym}             # Trace call-graph, callers, callees, definitions",
        f"python3 map.py --symbol {example_sym} --callers   # Focus specifically on inbound callers",
        f"python3 map.py {example_mod}                  # Positional shorthand (auto-detects file)",
        f"python3 map.py {example_sym}                  # Positional shorthand (auto-detects symbol)",
    ]

    lines: List[str] = [
        "=" * 80,
        "CODE-MAP: WORKSPACE OVERVIEW & ACTIONABLE USAGE GUIDE",
        "=" * 80,
        f"Workspace Root: {ws}",
        "",
        "📂 TOP-LEVEL REPOSITORY LAYOUT:",
    ]
    if layout_items:
        for item in layout_items:
            lines.append(f"  {item.summary}")
    else:
        lines.append("  (empty or inaccessible workspace)")
    lines.append("")

    if discovered_packages:
        lines.append(f"📦 DISCOVERED PACKAGES: {', '.join(discovered_packages)}")
        lines.append("")

    if key_modules:
        lines.append("📄 KEY MODULES:")
        for m in key_modules:
            lines.append(f"  • {m}")
        lines.append("")

    if clean_sample_symbols:
        lines.append("🔍 SAMPLE PUBLIC SYMBOLS:")
        for sym in clean_sample_symbols:
            lines.append(f"  • {sym}")
        lines.append("")

    lines.append("💡 TAILORED COPY-PASTEABLE COMMANDS:")
    for cmd in commands:
        lines.append(f"  {cmd}")
    lines.append("")
    lines.append("=" * 80)

    rendered = "\n".join(lines)

    return WorkspaceOverviewResult(
        mode="overview",
        workspace_root=str(ws),
        success=True,
        top_level_layout=layout_items,
        discovered_packages=discovered_packages,
        key_modules=key_modules,
        sample_symbols=clean_sample_symbols,
        copy_pasteable_commands=commands,
        rendered_text=rendered,
    )


# ==============================================================================
# Forgiving CLI Argument Parsing
# ==============================================================================


def parse_cli_args(argv: List[str]) -> Tuple[ParsedArgs, List[str]]:
    """Forgivingly and omnivorously parse CLI arguments without ever crashing.

    Handles:
    - Aliases: -s, --symbol, -f, --file, -d, --dir, -o, --overview, -t, --tree, --callers, --callees
    - Typo tolerance: maps flags like --symbl to --symbol via fuzzy matching
    - Unrecognized flags: warns and routes to closest intent or overview
    - Missing flag values: uses defaults gracefully without ArgumentError
    - Seamless positional fallbacks: symbol vs file/dir auto-detection
    """
    notices: List[str] = []
    args = ParsedArgs()

    i = 0
    positional: List[str] = []

    KNOWN_FLAGS = {
        "-s": "symbol",
        "--symbol": "symbol",
        "--sym": "symbol",
        "--symbols": "symbol",
        "--function": "symbol",
        "--fn": "symbol",
        "--class": "symbol",
        "-f": "file",
        "--file": "file",
        "--path": "file",
        "--filepath": "file",
        "-d": "dir",
        "--dir": "dir",
        "--directory": "dir",
        "--folder": "dir",
        "-o": "overview",
        "--overview": "overview",
        "--summary": "overview",
        "--workspace": "overview",
        "-t": "tree",
        "--tree": "tree",
        "--callers": "callers",
        "--caller": "callers",
        "--inbound": "callers",
        "--callees": "callees",
        "--callee": "callees",
        "--outbound": "callees",
        "-j": "json",
        "--json": "json",
        "-g": "graph",
        "--graph": "graph",
        "-n": "max_lines",
        "--max-lines": "max_lines",
        "--limit": "max_lines",
        "--lines": "max_lines",
        "-h": "help",
        "--help": "help",
    }

    while i < len(argv):
        arg = argv[i]
        val = None

        if arg in ("-h", "--help"):
            return ParsedArgs(overview=True), ["help"]

        # Handle --flag=value syntax
        if "=" in arg and arg.startswith("-"):
            flag_part, val = arg.split("=", 1)
        else:
            flag_part = arg

        canon = KNOWN_FLAGS.get(flag_part)

        # Fuzzy match flag typo if starts with - or --
        if not canon and flag_part.startswith("-"):
            clean_flag = flag_part.lstrip("-")
            all_clean = {k.lstrip("-"): v for k, v in KNOWN_FLAGS.items()}
            close = difflib.get_close_matches(clean_flag, list(all_clean.keys()), n=1, cutoff=0.6)
            if close:
                canon = all_clean[close[0]]
                notices.append(f"Interpreted flag '{flag_part}' as '--{close[0]}'.")
            else:
                notices.append(f"Unrecognized option '{flag_part}' ignored.")
                i += 1
                continue

        if canon == "symbol":
            if val is not None:
                args.symbol = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.symbol = argv[i]
            else:
                notices.append("Option '--symbol' passed without a value.")
        elif canon == "file":
            if val is not None:
                args.file = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.file = argv[i]
            else:
                notices.append("Option '--file' passed without a value.")
        elif canon == "dir":
            if val is not None:
                args.dir = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.dir = argv[i]
            else:
                notices.append("Option '--dir' passed without a value.")
        elif canon == "overview":
            args.overview = True
        elif canon == "tree":
            args.tree = True
        elif canon == "callers":
            args.focus = "callers"
            if val is not None:
                args.callers = val
                args.symbol = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.callers = argv[i]
                args.symbol = argv[i]
            else:
                args.callers = True
        elif canon == "callees":
            args.focus = "callees"
            if val is not None:
                args.callees = val
                args.symbol = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.callees = argv[i]
                args.symbol = argv[i]
            else:
                args.callees = True
        elif canon == "json":
            args.json = True
        elif canon == "graph":
            if val is not None:
                args.graph = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.graph = argv[i]
        elif canon == "max_lines":
            lines_val = val
            if lines_val is None and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                lines_val = argv[i]
            if lines_val:
                try:
                    args.max_lines = int(lines_val)
                except ValueError:
                    notices.append(f"Invalid integer '{lines_val}' for line budget; using default.")
        elif not arg.startswith("-"):
            positional.append(arg)

        i += 1

    if positional:
        args.target = positional[0]

    args.notices = notices
    return args, []


def determine_mode_and_target(
    args: ParsedArgs,
    ws: pathlib.Path,
) -> Tuple[str, str, Optional[str]]:
    """Deterministically and forgivingly resolve analysis mode ('overview', 'file', 'symbol'), target, and focus."""
    # 1. Explicit overview flag
    if args.overview:
        return "overview", ".", None

    # 2. Tree flag: directory tree / file outline
    if args.tree:
        tree_target = args.dir or args.file or args.target or "."
        return "file", tree_target, None

    # 3. Callers / Callees flag with explicit value or focus
    if args.callers:
        sym = args.callers if isinstance(args.callers, str) else (args.symbol or args.target or "")
        if sym:
            return "symbol", sym, "callers"

    if args.callees:
        sym = args.callees if isinstance(args.callees, str) else (args.symbol or args.target or "")
        if sym:
            return "symbol", sym, "callees"

    # 4. Explicit --symbol
    if args.symbol:
        return "symbol", args.symbol, args.focus

    # 5. Explicit --dir
    if args.dir:
        return "file", args.dir, None

    # 6. Explicit --file
    if args.file:
        if args.file in (".", "/", "/workspace"):
            return "overview", ".", None
        return "file", args.file, None

    # 7. Positional argument
    if args.target:
        clean = args.target.strip()
        if not clean or clean in (".", "/", "/workspace"):
            return "overview", ".", None

        # Clearly a file extension or path with separators
        if clean.endswith(".py") or clean.endswith(".pyi") or "/" in clean or "\\" in clean:
            return "file", clean, None

        # Check direct existence as file or directory in workspace
        cand_p = ws / clean
        if cand_p.is_file() or cand_p.is_dir():
            return "file", clean, None

        cand_py = ws / f"{clean}.py"
        if cand_py.is_file():
            return "file", f"{clean}.py", None

        # Check with resolve_target for glob/search matches
        resolved, _ = resolve_target(clean, ws)
        if resolved is not None and resolved.exists():
            return "file", clean, None

        # Otherwise, treat as symbol
        return "symbol", clean, args.focus

    # 8. No arguments passed at all -> overview mode
    return "overview", ".", None


def print_help():
    """Print user/LLM help text."""
    print("""code-map: AST code structure and symbol call-graph tracer.

Usage:
  python3 map.py [TARGET] [OPTIONS]

Modes:
  --symbol, -s <name>     Trace callers, callees, definitions, and class hierarchy across repository.
  --file, -f <path>       Generate compact AST skeleton for a Python file or directory.
  --dir, -d <path>        Generate AST skeleton for all modules in a directory.
  --tree, -t [path]       Map directory tree structure and module skeletons.
  --overview, -o          Display workspace overview, discovered packages, and key modules.
  --callers [symbol]      Focus on inbound callers for the target symbol.
  --callees [symbol]      Focus on outbound callees for the target symbol.
  <target>                Positional shorthand (auto-detects file, directory, or symbol).
  (empty)                 Displays workspace overview, discovered packages, and tailored commands.

Options:
  --json, -j              Output structured JSON schema (Pydantic v2).
  --max-lines, -n <int>   Maximum lines of symbol output for directory outlines (default: 120).
  --graph, -g <path>      Explicit path to precomputed codebase graph JSON.
  --help, -h              Show this help message and exit.

Examples:
  python3 map.py                                # Repository overview & tailored usage guide
  python3 map.py --symbol APIRouter             # Trace symbol callers/callees/definitions
  python3 map.py -s APIRouter --callers         # Focus on inbound callers of APIRouter
  python3 map.py -s APIRouter --callees         # Focus on outbound callees of APIRouter
  python3 map.py --file fastapi/routing.py      # Compact AST outline of a single file
  python3 map.py -f fastapi                     # Map directory modules up to max_lines budget
  python3 map.py -d fastapi                     # Directory mapping shorthand
  python3 map.py APIRouter                      # Auto-detected symbol mode
  python3 map.py fastapi/routing.py             # Auto-detected file mode
  python3 map.py fastapi                        # Auto-detected directory mode
  python3 map.py --symbol APIRouter --json      # Output structured JSON schema
""")


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def run_cli(argv: List[str]) -> int:
    """Execute code-map CLI forgivingly."""
    ws_root = get_workspace_dir()
    parsed_args, extra = parse_cli_args(argv)

    if extra and extra[0] == "help":
        print_help()
        return 0

    mode, target_name, focus = determine_mode_and_target(parsed_args, ws_root)

    # Print notices if any (only in non-json mode)
    if parsed_args.notices and not parsed_args.json:
        for note in parsed_args.notices:
            print(f"[code-map note] {note}")
        print("")

    # 1. Overview Mode
    if mode == "overview":
        res_overview = generate_workspace_overview(ws_root)
        if parsed_args.json:
            print(res_overview.model_dump_json(indent=2))
        else:
            print(res_overview.rendered_text)
        return 0

    # 2. File / Directory Skeleton Mode
    if mode == "file":
        res_file = generate_file_skeleton(target_name, max_lines=parsed_args.max_lines)
        if parsed_args.json:
            print(res_file.model_dump_json(indent=2))
        else:
            print(res_file.rendered_text)
        return 0

    # 3. Symbol Mode
    target_path, _ = resolve_target(".", ws_root)
    res_symbol = analyze_symbol(
        symbol_name=target_name,
        target_path=target_path or ws_root,
        ws_root=ws_root,
        explicit_graph_path=parsed_args.graph,
        focus=focus,
    )

    if parsed_args.json:
        print(res_symbol.model_dump_json(indent=2))
    else:
        print(format_symbol_report(res_symbol))

    return 0


def main() -> int:
    try:
        return run_cli(sys.argv[1:])
    except Exception as e:
        # Ultimate fallback: never crash with unhandled exception or leave LLM stranded
        ws = get_workspace_dir()
        overview = generate_workspace_overview(ws)
        print(f"[code-map note] Command completed with fallback due to: {e}")
        print(overview.rendered_text)
        return 0


if __name__ == "__main__":
    sys.exit(main())
`````

## File: submission/skills/code-map/map.py
`````python
#!/usr/bin/env python3
"""code-map: AST code structure and symbol call-graph tracer.

Unified skill combining:
1. Symbol call-graph and reference reachability tracer (--symbol <name>, -s, --callers, --callees):
   - Traces definitions, imports, calls, attribute accesses, callers, and callees across repo.
   - Detects class hierarchies: base classes and subclasses inheriting from the queried symbol.
   - Omnivorous: queries precomputed codebase graphs (NetworkX node-link JSON) when available,
     and falls back to / combines with live AST analysis.
   - Provides fuzzy matching suggestions and diagnostics when symbols are missing or private.
   - When a symbol is not found, displays available top-level symbols in the repo and copy-pasteable next steps.
2. Compact AST file and directory skeleton generator (--file <path>, -f, -d, --dir, -t, --tree):
   - Extracts classes, base classes, functions, arguments, return type annotations, docstrings,
     and line ranges [start-end] for a target Python file or directory.
   - For directories, extracts skeletons across modules up to max_lines budget.
   - Diagnoses syntax errors with exact line, column, snippet, and caret pointer.
   - Output-capped to prevent context flooding in 32K token windows.
3. Forgiving positional fallback:
   - If argument is an existing directory or ends in .py, treated as file mode.
   - If argument matches an existing file with .py appended, treated as file mode.
   - If argument contains path separators (/ or \\), treated as file mode.
   - Otherwise, treated as symbol mode.
4. Omnivorous workspace overview on empty args, '.', '/workspace', or -o/--overview:
   - Explains the workspace structure, discovered packages, and key modules.
   - Provides tailored, copy-pasteable example invocations for the current repository.
   - Never crashes or exits 1 on empty calls or unrecognized flags.

100% Pydantic v2 schemas for all structured outputs.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True

# Protect against deeply nested ASTs or deep recursions without stack overflow
try:
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4000))
except Exception:
    pass

from pydantic import BaseModel, ConfigDict, Field

# Directories to skip when scanning repositories
SKIP_DIRS: Set[str] = {
    "__pycache__",
    "build",
    "dist",
    ".git",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    ".eggs",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "wheels",
    "site-packages",
    ".adk_exec",
}


# ==============================================================================
# Pydantic v2 Models: Symbol Tracing (--symbol)
# ==============================================================================


class ReferenceDetail(BaseModel):
    """Detailed location and context for a symbol reference, definition, or import."""

    model_config = ConfigDict(extra="ignore")

    file_path: str = Field(description="Relative file path where the reference occurs")
    line_number: int = Field(description="1-based line number of the reference")
    kind: str = Field(
        description="Reference kind: 'class', 'function', 'method', 'import', 'call', 'attribute', 'subclass', or 'text'"
    )
    context: str = Field(default="", description="Source preview, import statement, or call context")
    caller: Optional[str] = Field(default=None, description="Enclosing caller function/method if applicable")
    callee: Optional[str] = Field(default=None, description="Target callee symbol if applicable")
    bases: Optional[List[str]] = Field(default=None, description="Base classes if symbol is a class definition")
    subclasses: Optional[List[str]] = Field(default=None, description="Subclasses inheriting from this symbol")


class SymbolSuggestion(BaseModel):
    """Candidate symbol suggestion for a missing or misspelled query."""

    model_config = ConfigDict(extra="ignore")

    symbol: str = Field(description="Candidate symbol name or fully qualified path")
    similarity: float = Field(description="Fuzzy match similarity score (0.0 to 1.0)")
    kind: Optional[str] = Field(default=None, description="Inferred or known kind (function, class, method, node)")
    location: Optional[str] = Field(default=None, description="File path or defining location if known")
    reason: Optional[str] = Field(default=None, description="Why this candidate was suggested")
    inspect_command: Optional[str] = Field(
        default=None, description="Exact copy-pasteable command to inspect this candidate symbol"
    )
    file_command: Optional[str] = Field(
        default=None, description="Exact copy-pasteable command to inspect containing file"
    )


class GraphStatus(BaseModel):
    """Diagnostic status of precomputed codebase graph loading."""

    model_config = ConfigDict(extra="ignore")

    graph_loaded: bool = Field(description="Whether a precomputed codebase graph JSON was found and loaded")
    graph_path: Optional[str] = Field(default=None, description="Filesystem path of the loaded graph JSON")
    node_count: int = Field(default=0, description="Total node count in loaded graph")
    edge_count: int = Field(default=0, description="Total edge count in loaded graph")
    fallback_mode: str = Field(default="live_ast", description="Analysis mode ('precomputed_graph', 'live_ast', or 'hybrid')")
    diagnostic_message: Optional[str] = Field(default=None, description="Explanation of graph availability or fallback instructions")


class CodeGraphResult(BaseModel):
    """Complete structured output for code graph symbol tracing and reachability analysis."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="symbol", description="Analysis mode: 'symbol'")
    query: str = Field(description="Queried symbol or text pattern")
    found: bool = Field(description="Whether the symbol was identified in graph or AST")
    resolved_symbol: Optional[str] = Field(default=None, description="Resolved canonical or node identifier")
    focus: Optional[str] = Field(default=None, description="Optional focus filter: 'callers' or 'callees'")
    explanation: str = Field(description="Deterministic explanation of search outcome")
    inspection_hint: Optional[str] = Field(default=None, description="Guidance for private/internal or imported symbols")
    graph_status: GraphStatus = Field(description="Graph loading diagnostics and fallback details")
    definitions: List[ReferenceDetail] = Field(default_factory=list, description="Symbol definitions")
    imports: List[ReferenceDetail] = Field(default_factory=list, description="Symbol imports")
    calls: List[ReferenceDetail] = Field(default_factory=list, description="Direct call sites and attribute accesses")
    subclasses: List[ReferenceDetail] = Field(default_factory=list, description="Classes inheriting from this symbol")
    text_occurrences: List[ReferenceDetail] = Field(default_factory=list, description="Textual matches across files")
    callers: List[str] = Field(default_factory=list, description="Inbound callers invoking this symbol")
    callees: List[str] = Field(default_factory=list, description="Outbound callees invoked by this symbol")
    caller_callee_summary: Optional[str] = Field(default=None, description="Summary of call graph reachability")
    suggestions: List[SymbolSuggestion] = Field(default_factory=list, description="Closest matching candidates")
    did_you_mean: List[str] = Field(default_factory=list, description="List of top suggested symbol names")
    available_top_symbols: List[str] = Field(
        default_factory=list, description="Available top-level public symbols in the repository"
    )
    next_steps: List[str] = Field(default_factory=list, description="Actionable next commands for the LLM")


# ==============================================================================
# Pydantic v2 Models: File Skeleton (--file) & Repository Overview
# ==============================================================================


class MapDiagnostic(BaseModel):
    """Diagnostic explanation for missing paths, syntax errors, or parsing anomalies."""

    model_config = ConfigDict(extra="ignore")

    level: str = Field(default="error", description="Severity level: 'error', 'warning', or 'info'")
    category: str = Field(
        ...,
        description="Category: 'missing_path', 'syntax_error', 'unparseable_file', 'empty_target', 'encoding_error', 'permission_denied', 'recursion_limit_exceeded'",
    )
    message: str = Field(..., description="Primary explanatory message for the agent")
    target_path: Optional[str] = Field(default=None, description="Target file or directory path where issue occurred")
    line: Optional[int] = Field(default=None, description="1-based line number for AST syntax errors")
    column: Optional[int] = Field(default=None, description="1-based column offset for AST syntax errors")
    snippet: Optional[str] = Field(default=None, description="Source code snippet showing the syntax error location and caret pointer")
    suggestions: List[str] = Field(default_factory=list, description="Closest valid paths or recommended actions")
    guidance: Optional[str] = Field(default=None, description="Deterministic guidance instructions for the agent")


class SymbolItem(BaseModel):
    """Extracted Python symbol (class, function, method, async function)."""

    model_config = ConfigDict(extra="ignore")

    kind: str = Field(..., description="Symbol kind: 'class', 'def', 'async def'")
    name: str = Field(..., description="Identifier name of the symbol")
    signature: str = Field(..., description="Formatted symbol signature including arguments, return type, and line range")
    start_line: int = Field(..., description="Starting line number in source file (1-based)")
    end_line: int = Field(..., description="Ending line number in source file (1-based)")
    docstring: Optional[str] = Field(default=None, description="Formatted one-line docstring summary if present")


class ModuleSummary(BaseModel):
    """AST structure summary for a single Python module file."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Workspace-relative path to the Python source file")
    symbols: List[SymbolItem] = Field(default_factory=list, description="List of extracted symbols in document order")
    symbol_count: int = Field(default=0, description="Total number of extracted symbols in this module")
    syntax_error: Optional[MapDiagnostic] = Field(default=None, description="AST syntax error diagnostic if module could not be parsed")


class RepoLayoutItem(BaseModel):
    """Top-level repository layout item for orienting the agent."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Entry name (directory or file name)")
    rel_path: str = Field(..., description="Workspace-relative path")
    is_dir: bool = Field(..., description="True if directory, False if file")
    summary: str = Field(..., description="Formatted human-readable layout summary entry")


class FileSkeletonResult(BaseModel):
    """Complete structured output for file skeleton mapping session."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="file", description="Analysis mode: 'file'")
    target: str = Field(..., description="Target file or directory path requested by the agent")
    workspace_root: str = Field(..., description="Absolute workspace root path")
    success: bool = Field(default=True, description="Whether mapping completed successfully without path resolution failures")
    modules: List[ModuleSummary] = Field(default_factory=list, description="List of mapped module summaries")
    total_files: int = Field(default=0, description="Number of successfully mapped Python files")
    total_symbols: int = Field(default=0, description="Total number of symbols across all modules")
    diagnostics: List[MapDiagnostic] = Field(default_factory=list, description="List of diagnostics, syntax errors, or warnings")
    top_level_layout: List[RepoLayoutItem] = Field(default_factory=list, description="Top-level repository structure")
    is_truncated: bool = Field(default=False, description="True if output was truncated to honor max_lines cap")
    rendered_text: str = Field(default="", description="Human/LLM-readable text output")
    next_steps: List[str] = Field(default_factory=list, description="Actionable next commands for the LLM")


class WorkspaceOverviewResult(BaseModel):
    """Complete structured output for workspace repository overview and usage guide."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="overview", description="Analysis mode: 'overview'")
    workspace_root: str = Field(..., description="Absolute workspace root path")
    success: bool = Field(default=True, description="Whether overview was generated successfully")
    top_level_layout: List[RepoLayoutItem] = Field(default_factory=list, description="Top-level repository structure")
    discovered_packages: List[str] = Field(default_factory=list, description="Discovered Python packages/subdirectories")
    key_modules: List[str] = Field(default_factory=list, description="Key Python module files in workspace")
    sample_symbols: List[str] = Field(default_factory=list, description="Sample discovered public classes and functions")
    copy_pasteable_commands: List[str] = Field(default_factory=list, description="Copy-pasteable invocations tailored to this repo")
    rendered_text: str = Field(default="", description="Human/LLM-readable text output")


# ==============================================================================
# Internal CLI Arguments Schema
# ==============================================================================


class ParsedArgs(BaseModel):
    """Structured internal representation of forgiving CLI arguments."""

    model_config = ConfigDict(extra="ignore")

    symbol: Optional[str] = None
    file: Optional[str] = None
    dir: Optional[str] = None
    target: Optional[str] = None
    overview: bool = False
    tree: bool = False
    callers: Optional[Any] = None
    callees: Optional[Any] = None
    focus: Optional[str] = None
    json: bool = False
    graph: Optional[str] = None
    max_lines: int = 120
    notices: List[str] = Field(default_factory=list)


# ==============================================================================
# Workspace & Target Resolution (Loop-Safe & Symlink-Safe)
# ==============================================================================


def should_skip_dir(name: str) -> bool:
    """Return True if directory should be skipped during walk."""
    if name.startswith(".") or name.startswith("__") or ".adk_exec" in name or name.startswith(".adk_exec"):
        return True
    lower = name.lower()
    if lower in SKIP_DIRS:
        return True
    if "egg-info" in lower:
        return True
    return False


def should_skip_path(p: pathlib.Path, ws: pathlib.Path) -> bool:
    """Return True if path contains any skipped directory components."""
    if ".adk_exec" in p.name or p.name.startswith(".adk_exec"):
        return True
    try:
        rel = p.relative_to(ws)
    except ValueError:
        rel = p
    for part in rel.parts:
        if should_skip_dir(part) or ".adk_exec" in part or part.startswith(".adk_exec"):
            return True
    return False


def safe_walk(
    root_path: pathlib.Path,
    ws_root: pathlib.Path,
    max_depth: int = 15,
    max_dirs: int = 1000,
) -> Any:
    """Cycle-safe, symlink-safe, and depth-bounded generator over directory tree.

    Prevents infinite loops from circular symlinks, directory junctions, runaway depth,
    and massive directory trees.
    """
    visited_inodes: Set[Tuple[int, int]] = set()
    visited_realpaths: Set[str] = set()
    dirs_count = 0

    try:
        real_root = os.path.realpath(str(root_path))
        visited_realpaths.add(real_root)
    except Exception:
        pass

    for dirpath, dirnames, filenames in os.walk(str(root_path), followlinks=False):
        dirs_count += 1
        if dirs_count > max_dirs:
            dirnames.clear()
            return

        curr_p = pathlib.Path(dirpath)
        try:
            real_dir = os.path.realpath(dirpath)
            if real_dir in visited_realpaths and dirpath != str(root_path):
                dirnames.clear()
                continue
            visited_realpaths.add(real_dir)

            stat_res = curr_p.stat()
            inode_key = (stat_res.st_dev, stat_res.st_ino)
            if inode_key in visited_inodes:
                dirnames.clear()
                continue
            visited_inodes.add(inode_key)
        except (OSError, PermissionError):
            dirnames.clear()
            continue

        try:
            rel = curr_p.relative_to(ws_root)
            if len(rel.parts) > max_depth:
                dirnames.clear()
                continue
        except ValueError:
            pass

        # In-place directory filtering: skip ignored dirs and symlink directories
        filtered_dirs: List[str] = []
        for d in dirnames:
            if should_skip_dir(d):
                continue
            full_sub = os.path.join(dirpath, d)
            try:
                if os.path.islink(full_sub):
                    continue
            except (OSError, PermissionError):
                continue
            filtered_dirs.append(d)
        dirnames[:] = filtered_dirs

        yield dirpath, dirnames, filenames


def get_workspace_dir() -> pathlib.Path:
    """Robustly and deterministically locate the active target repository workspace directory."""
    # a) Check caller stack frame for _orig_cwd (set by ADK in _materialize_and_run)
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals and f.f_locals["_orig_cwd"]:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                    or (p / ".git").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    # b) Check environment variable overrides
    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    # c) Standard competition container workspace (/workspace)
    for p_str in ("/workspace", "/workspace/repo", "/repo", "/app"):
        p = pathlib.Path(p_str)
        if p.is_dir() and (
            (p / "pyproject.toml").exists()
            or (p / "setup.py").exists()
            or (p / ".git").exists()
        ):
            return p.resolve()

    # d) Ascend from current directory looking for repo markers
    curr = pathlib.Path.cwd().resolve()
    for parent in [curr] + list(curr.parents):
        if (
            (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
            or (parent / ".git").exists()
            or (parent / "tasks.jsonl").exists()
        ):
            return parent

    return curr


def resolve_target(target_arg: str, ws: pathlib.Path) -> Tuple[Optional[pathlib.Path], str]:
    """Resolve target path safely against workspace."""
    clean = target_arg.strip()
    if not clean or clean in (".", "/", "/workspace"):
        return ws, clean or "."

    # Check direct relative to workspace
    cand = ws / clean.lstrip("/")
    if cand.exists():
        return cand, clean

    # Check absolute
    try:
        p_abs = pathlib.Path(clean).resolve()
        if p_abs.exists() and (p_abs == ws or ws in p_abs.parents):
            return p_abs, clean
    except Exception:
        pass

    # Check with .py appended if not already present
    if not clean.endswith(".py"):
        cand_py = ws / f"{clean.lstrip('/')}.py"
        if cand_py.is_file():
            return cand_py, f"{clean}.py"

    # Check for glob match inside workspace
    try:
        pattern = f"**/{clean}" if clean.endswith(".py") else f"**/{clean}.py"
        matches = [m for m in ws.glob(pattern) if not should_skip_path(m, ws)]
        if matches:
            return matches[0], clean
        if not clean.endswith(".py"):
            dir_matches = [m for m in ws.glob(f"**/{clean}") if m.is_dir() and not should_skip_path(m, ws)]
            if dir_matches:
                return dir_matches[0], clean
    except Exception:
        pass

    return None, clean


def find_closest_paths(clean_target: str, ws: pathlib.Path) -> List[str]:
    """Find closest existing files and directories to the missing target using fuzzy matching."""
    all_dirs: List[str] = []
    all_files: List[str] = []

    try:
        for root, dirs, files in safe_walk(ws, ws, max_depth=8, max_dirs=600):
            dirs[:] = sorted([d for d in dirs if not should_skip_dir(d)])
            rel_dir = os.path.relpath(root, ws)
            if rel_dir != ".":
                all_dirs.append(rel_dir)
            for f in files:
                if f.endswith(".py") and not f.startswith("."):
                    rel_file = os.path.normpath(os.path.join(rel_dir, f)) if rel_dir != "." else f
                    all_files.append(rel_file)
    except Exception:
        pass

    all_paths = all_files + all_dirs
    if not all_paths:
        return []

    target_base = os.path.basename(clean_target)
    exact_bases = [p for p in all_paths if os.path.basename(p) == target_base]
    close_full = difflib.get_close_matches(clean_target, all_paths, n=6, cutoff=0.35)
    close_bases = [
        p
        for p in all_paths
        if os.path.basename(p)
        in difflib.get_close_matches(target_base, [os.path.basename(x) for x in all_paths], n=6, cutoff=0.45)
    ]
    substrings = [p for p in all_paths if target_base.lower() in os.path.basename(p).lower()]

    combined: List[str] = []
    for p in exact_bases + close_full + close_bases + substrings:
        if p not in combined:
            combined.append(p)

    results: List[str] = []
    for p in combined[:8]:
        if p in all_dirs:
            results.append(f"📁 {p}/")
        else:
            results.append(f"📄 {p}")

    return results


def get_top_level_layout(ws: pathlib.Path) -> List[RepoLayoutItem]:
    """Inspect top-level entries in the workspace and return structured layout items."""
    items: List[RepoLayoutItem] = []
    try:
        entries = sorted(ws.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except Exception:
        return items

    for entry in entries:
        if entry.name.startswith(".") or entry.name.startswith("__") or ".adk_exec" in entry.name:
            continue
        if entry.name in ("venv", "wheels", ".git", "__pycache__"):
            continue

        rel = entry.name
        if entry.is_dir():
            py_count = 0
            subdirs = 0
            try:
                for _, d_list, f_list in safe_walk(entry, ws, max_depth=5, max_dirs=300):
                    d_list[:] = [d for d in d_list if not should_skip_dir(d)]
                    subdirs += len(d_list)
                    for f in f_list:
                        if f.endswith(".py") and not f.startswith("."):
                            py_count += 1
            except Exception:
                pass

            desc_parts: List[str] = []
            if py_count > 0:
                desc_parts.append(f"{py_count} .py file{'s' if py_count != 1 else ''}")
            if subdirs > 0:
                desc_parts.append(f"{subdirs} subdir{'s' if subdirs != 1 else ''}")
            desc_suffix = f" ({', '.join(desc_parts)})" if desc_parts else ""
            summary = f"📁 {entry.name}/{desc_suffix}"
            items.append(RepoLayoutItem(name=entry.name, rel_path=rel, is_dir=True, summary=summary))
        else:
            items.append(RepoLayoutItem(name=entry.name, rel_path=rel, is_dir=False, summary=f"📄 {entry.name}"))
    return items


def collect_py_files(target_path: pathlib.Path, ws: pathlib.Path, max_files: int = 150) -> List[pathlib.Path]:
    """Collect Python files from target path in deterministic order."""
    if target_path.is_file():
        if target_path.name.endswith(".py") or target_path.suffix == ".py":
            return [target_path]
        return []

    py_files: List[pathlib.Path] = []
    for root, dirs, files in safe_walk(target_path, ws, max_depth=10, max_dirs=600):
        dirs[:] = sorted([d for d in dirs if not should_skip_dir(d)])
        for f in sorted(files):
            if f.endswith(".py") and not f.startswith("."):
                py_files.append(pathlib.Path(root) / f)
                if len(py_files) >= max_files:
                    return py_files
    return py_files


def get_top_repo_symbols(ws: pathlib.Path, max_symbols: int = 12) -> List[str]:
    """Extract top-level public classes and functions across key workspace modules."""
    symbols: List[str] = []
    seen: Set[str] = set()

    # Prioritize non-test core modules
    py_files = collect_py_files(ws, ws, max_files=40)
    core_files = [p for p in py_files if "test" not in p.name.lower() and "test" not in str(p).lower()]
    target_files = core_files if core_files else py_files

    for fpath in target_files[:20]:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(fpath))
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    if node.name not in seen:
                        seen.add(node.name)
                        symbols.append(f"class {node.name}")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                    if node.name not in seen:
                        seen.add(node.name)
                        symbols.append(f"def {node.name}()")
                if len(symbols) >= max_symbols:
                    return symbols
        except Exception:
            continue

    return symbols


# ==============================================================================
# Graph Discovery & Indexing
# ==============================================================================


def discover_graph_file(
    ws_root: pathlib.Path, explicit_path: Optional[str] = None, query_symbol: Optional[str] = None
) -> Optional[pathlib.Path]:
    """Locate precomputed codebase graph JSON file for the repository."""
    if explicit_path:
        p = pathlib.Path(explicit_path).resolve()
        if p.is_file():
            return p

    for env_var in ("SWEGEMMA_GRAPH_PATH", "GRAPH_PATH", "SWEGEMMA_GRAPH_FILE"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val).resolve()
            if p.is_file():
                return p

    search_dirs: List[pathlib.Path] = []
    for env_dir in ("SWEGEMMA_GRAPH_DIR", "GRAPH_DIR", "DATA_DIR"):
        val = os.environ.get(env_dir)
        if val:
            search_dirs.append(pathlib.Path(val).resolve())

    search_dirs.extend([
        ws_root / "graphs",
        ws_root / "data" / "graphs",
        ws_root.parent / "graphs",
        ws_root.parent.parent / "graphs",
        pathlib.Path.cwd().resolve() / "graphs",
        pathlib.Path.cwd().resolve() / "data" / "graphs",
        pathlib.Path("/data/graphs"),
        pathlib.Path("/workspace/graphs"),
        pathlib.Path("/workspace/data/graphs"),
    ])

    repo_cands: List[str] = []
    for name in ("fastapi", "rich", "requests", "httpx", "starlette", "pydantic", "flask"):
        if (ws_root / name).is_dir() or (ws_root / "src" / name).is_dir():
            repo_cands.append(name)
        elif name in ws_root.name.lower():
            repo_cands.append(name)

    commit: Optional[str] = None
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ws_root,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0 and res.stdout.strip():
            commit = res.stdout.strip()
    except Exception:
        pass

    for d in search_dirs:
        try:
            if not d.is_dir():
                continue
            json_files = sorted(list(d.glob("*.json")))
            if not json_files:
                continue

            if len(json_files) == 1:
                return json_files[0]

            # 1. Match repository name candidate
            for repo in repo_cands:
                matches = [
                    f for f in json_files
                    if f.name.startswith(f"{repo}_") or f.name.startswith(f"{repo}.")
                ]
                if commit:
                    for m in matches:
                        if commit in m.name:
                            return m
                if matches:
                    return matches[0]

            # 2. Match commit directly if available
            if commit:
                for f in json_files:
                    if commit in f.name:
                        return f

            # 3. Query symbol affinity: check 4 core repo families if in dev/harness environment
            if query_symbol:
                families: Dict[str, pathlib.Path] = {}
                for f in json_files:
                    prefix = f.name.split("_")[0].split(".")[0]
                    if prefix not in families:
                        families[prefix] = f

                for _, rep_path in families.items():
                    try:
                        with open(rep_path, "r", encoding="utf-8", errors="replace") as jf:
                            data = json.load(jf)
                        ids = {str(n.get("id") or "") for n in data.get("nodes", [])}
                        if any(query_symbol in nid for nid in ids):
                            return rep_path
                    except Exception:
                        continue

            if json_files:
                return json_files[0]

        except Exception:
            continue

    return None


def load_and_index_graph(graph_path: pathlib.Path) -> Tuple[Dict[str, Any], int, int]:
    """Load precomputed NetworkX node-link JSON and build fast lookup indexes."""
    try:
        with open(graph_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
    except Exception:
        return {}, 0, 0

    node_ids: List[str] = []
    node_map: Dict[str, Dict[str, Any]] = {}
    leaf_map: Dict[str, List[str]] = {}
    in_edges: Dict[str, List[str]] = {}
    out_edges: Dict[str, List[str]] = {}

    for n in nodes:
        nid = str(n.get("id") or n.get("name") or "").strip()
        if not nid:
            continue
        node_ids.append(nid)
        node_map[nid] = n
        leaf = nid.split(".")[-1]
        leaf_map.setdefault(leaf, []).append(nid)

    for e in edges:
        src = str(e.get("source") or "").strip()
        tgt = str(e.get("target") or "").strip()
        if src and tgt:
            out_edges.setdefault(src, []).append(tgt)
            in_edges.setdefault(tgt, []).append(src)

    indexes = {
        "node_ids": node_ids,
        "node_map": node_map,
        "leaf_map": leaf_map,
        "in_edges": in_edges,
        "out_edges": out_edges,
    }
    return indexes, len(nodes), len(edges)


def resolve_graph_node(query: str, indexes: Dict[str, Any]) -> Optional[str]:
    """Resolve query symbol against graph nodes using 3-tier boundary matching."""
    if not indexes:
        return None

    node_ids: List[str] = indexes.get("node_ids", [])
    node_map: Dict[str, Any] = indexes.get("node_map", {})
    leaf_map: Dict[str, List[str]] = indexes.get("leaf_map", {})

    # Tier 1: Exact match
    if query in node_map:
        return query

    # Tier 2: Leaf / boundary match
    if query in leaf_map:
        return leaf_map[query][0]

    suffix_dot = f".{query}"
    suffix_semi = f";{query}"
    for nid in node_ids:
        if nid.endswith(suffix_dot) or nid.endswith(suffix_semi):
            return nid

    # Tier 3: Case-insensitive boundary match
    q_low = query.lower()
    suffix_dot_low = f".{q_low}"
    for nid in node_ids:
        nid_low = nid.lower()
        if nid_low == q_low or nid_low.endswith(suffix_dot_low):
            return nid

    return None


# ==============================================================================
# Fuzzy Matching & Candidate Suggestions
# ==============================================================================


def compute_fuzzy_suggestions(
    query: str,
    candidates: List[Tuple[str, Optional[str], Optional[str]]],
    top_n: int = 6,
    cutoff: float = 0.30,
) -> List[SymbolSuggestion]:
    """Rank candidate symbols by fuzzy similarity (difflib SequenceMatcher), generating exact copy-pasteable commands."""
    q_low = query.lower()
    scored: List[Tuple[float, str, Optional[str], Optional[str]]] = []

    # Deduplicate candidate names, keeping richest kind/location
    best_candidate_map: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for cand_name, kind, loc in candidates:
        cand_clean = cand_name.strip()
        if not cand_clean or cand_clean == query:
            continue
        if cand_clean not in best_candidate_map:
            best_candidate_map[cand_clean] = (kind, loc)
        else:
            old_kind, old_loc = best_candidate_map[cand_clean]
            if not old_loc and loc:
                best_candidate_map[cand_clean] = (kind or old_kind, loc)
            elif old_kind in ("import", "module", "graph_node") and kind in ("class", "function", "method"):
                best_candidate_map[cand_clean] = (kind, loc or old_loc)

    for cand_clean, (kind, loc) in best_candidate_map.items():
        c_low = cand_clean.lower()
        leaf = cand_clean.split(".")[-1]
        l_low = leaf.lower()

        sim_leaf = difflib.SequenceMatcher(None, q_low, l_low).ratio()
        sim_full = difflib.SequenceMatcher(None, q_low, c_low).ratio()

        sub_boost = 0.0
        if q_low == l_low:
            sub_boost = 1.0
        elif q_low in l_low:
            sub_boost = 0.85
        elif q_low in c_low:
            sub_boost = 0.70

        score = max(sim_leaf, sim_full, sub_boost)
        if score >= cutoff:
            scored.append((score, cand_clean, kind, loc))

    scored.sort(key=lambda x: (x[0], -len(x[1])), reverse=True)

    suggestions: List[SymbolSuggestion] = []
    for score, sym, kind, loc in scored[:top_n]:
        inspect_cmd = f"python3 map.py --symbol {sym}"
        file_cmd = None
        if loc and ":" in loc:
            f_path = loc.split(":")[0]
            file_cmd = f"python3 map.py --file {f_path}"

        suggestions.append(
            SymbolSuggestion(
                symbol=sym,
                similarity=round(score, 3),
                kind=kind or ("function" if "(" in sym else "symbol"),
                location=loc,
                reason=f"Fuzzy match (similarity: {score:.2f}) to '{query}'",
                inspect_command=inspect_cmd,
                file_command=file_cmd,
            )
        )
    return suggestions


# ==============================================================================
# AST Reference, Reachability & Hierarchy Collector (--symbol mode)
# ==============================================================================


class AstReferenceCollector(ast.NodeVisitor):
    """Parses Python AST to extract definitions, base classes, subclasses, imports, calls, callers, callees."""

    def __init__(self, rel_path: str, clean_symbol: str, max_ast_depth: int = 80):
        self.rel_path = rel_path
        self.clean_symbol = clean_symbol
        self.scope_stack: List[str] = []
        self.current_depth: int = 0
        self.max_ast_depth: int = max_ast_depth

        self.defs: List[ReferenceDetail] = []
        self.imports: List[ReferenceDetail] = []
        self.calls: List[ReferenceDetail] = []
        self.subclasses: List[ReferenceDetail] = []
        self.ast_callers: Set[str] = set()
        self.ast_callees: Set[str] = set()
        self.catalog_symbols: List[Tuple[str, Optional[str], str]] = []

    def generic_visit(self, node: ast.AST):
        if self.current_depth >= self.max_ast_depth:
            return
        self.current_depth += 1
        try:
            super().generic_visit(node)
        finally:
            self.current_depth -= 1

    def visit_ClassDef(self, node: ast.ClassDef):
        loc = f"{self.rel_path}:{node.lineno}"
        self.catalog_symbols.append((node.name, "class", loc))

        base_names: List[str] = []
        for b in node.bases:
            try:
                base_names.append(ast.unparse(b))
            except Exception:
                if isinstance(b, ast.Name):
                    base_names.append(b.id)

        bases_str = f"({', '.join(base_names)})" if base_names else ""

        if node.name == self.clean_symbol:
            self.defs.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="class",
                    context=f"class {node.name}{bases_str}:",
                    bases=base_names if base_names else None,
                )
            )

        # Check if this class inherits from clean_symbol (class hierarchy)
        if any(self.clean_symbol == b or b.endswith(f".{self.clean_symbol}") for b in base_names):
            self.subclasses.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="subclass",
                    context=f"class {node.name}{bases_str} inherits from {self.clean_symbol}",
                    bases=base_names,
                )
            )

        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_function(node)

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        kind = "method" if self.scope_stack else "function"
        loc = f"{self.rel_path}:{node.lineno}"
        full_scope = ".".join(self.scope_stack + [node.name]) if self.scope_stack else node.name
        self.catalog_symbols.append((node.name, kind, loc))
        self.catalog_symbols.append((full_scope, kind, loc))

        if node.name == self.clean_symbol or full_scope == self.clean_symbol:
            ret_str = ""
            if getattr(node, "returns", None):
                try:
                    ret_str = f" -> {ast.unparse(node.returns)}"
                except Exception:
                    pass
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            self.defs.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind=kind,
                    context=f"{prefix} {node.name}(...){ret_str}",
                )
            )

        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ImportFrom(self, node: ast.ImportFrom):
        dots = "." * node.level if node.level else ""
        mod = f"{dots}{node.module or ''}"
        mod_prefix = f"from {mod} " if mod else ""
        loc = f"{self.rel_path}:{node.lineno}"
        for a in node.names:
            alias_str = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
            desc = f"{mod_prefix}{alias_str}".strip()
            self.catalog_symbols.append((a.name, "import", loc))
            if a.asname:
                self.catalog_symbols.append((a.asname, "import", loc))

            if a.name == self.clean_symbol or a.asname == self.clean_symbol:
                self.imports.append(
                    ReferenceDetail(
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        kind="import",
                        context=desc,
                    )
                )

    def visit_Import(self, node: ast.Import):
        loc = f"{self.rel_path}:{node.lineno}"
        for a in node.names:
            mod_parts = a.name.split(".")
            desc = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
            self.catalog_symbols.append((a.name, "module", loc))
            if a.asname:
                self.catalog_symbols.append((a.asname, "module", loc))

            if (
                a.name == self.clean_symbol
                or self.clean_symbol in mod_parts
                or a.asname == self.clean_symbol
            ):
                self.imports.append(
                    ReferenceDetail(
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        kind="import",
                        context=desc,
                    )
                )

    def visit_Call(self, node: ast.Call):
        func_name = ""
        is_attr = False
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            is_attr = True

        enclosing = ".".join(self.scope_stack) if self.scope_stack else "<module>"

        if func_name == self.clean_symbol:
            kind_str = f".{self.clean_symbol}()" if is_attr else f"{self.clean_symbol}()"
            self.calls.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="call",
                    context=kind_str,
                    caller=enclosing if enclosing != "<module>" else None,
                    callee=self.clean_symbol,
                )
            )
            if enclosing != "<module>":
                self.ast_callers.add(f"{enclosing} ({self.rel_path}:{node.lineno})")

        if (
            self.scope_stack
            and (self.scope_stack[-1] == self.clean_symbol or self.clean_symbol in self.scope_stack)
            and func_name
            and func_name != self.clean_symbol
        ):
            self.ast_callees.add(f"{func_name} ({self.rel_path}:{node.lineno})")

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr == self.clean_symbol:
            enclosing = ".".join(self.scope_stack) if self.scope_stack else "<module>"
            self.calls.append(
                ReferenceDetail(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    kind="attribute",
                    context=f".{self.clean_symbol}",
                    caller=enclosing if enclosing != "<module>" else None,
                )
            )
        self.generic_visit(node)


def analyze_symbol(
    symbol_name: str,
    target_path: pathlib.Path,
    ws_root: pathlib.Path,
    explicit_graph_path: Optional[str] = None,
    focus: Optional[str] = None,
) -> CodeGraphResult:
    """Analyze symbol references, graph reachability, definitions, and class hierarchy."""
    clean_symbol = symbol_name.strip()
    is_valid_ident = clean_symbol.isidentifier()

    # 1. Discover and load precomputed codebase graph if available
    graph_file = discover_graph_file(ws_root, explicit_graph_path, query_symbol=clean_symbol)
    graph_indexes: Dict[str, Any] = {}
    node_count = 0
    edge_count = 0
    graph_loaded = False

    if graph_file:
        graph_indexes, node_count, edge_count = load_and_index_graph(graph_file)
        if node_count > 0:
            graph_loaded = True

    if graph_loaded:
        graph_status = GraphStatus(
            graph_loaded=True,
            graph_path=str(graph_file),
            node_count=node_count,
            edge_count=edge_count,
            fallback_mode="hybrid",
            diagnostic_message=(
                f"Loaded precomputed codebase graph ({node_count} nodes, {edge_count} edges) "
                f"from {graph_file}."
            ),
        )
    else:
        graph_status = GraphStatus(
            graph_loaded=False,
            graph_path=None,
            node_count=0,
            edge_count=0,
            fallback_mode="live_ast",
            diagnostic_message=(
                "Precomputed codebase graph JSON is missing or inaccessible. "
                "Where graphs live: Precomputed codebase graphs are stored as 'graphs/<repo>.json' "
                "or 'data/graphs/<repo>.json' (NetworkX node-link JSON format). "
                "Fallback instructions: Automatically falling back to live repository AST analysis "
                "across all Python files in the workspace."
            ),
        )

    # 2. Collect files to scan (capped at 400 files to guarantee zero hangs)
    file_list = collect_py_files(target_path, ws_root, max_files=400)

    # 3. Perform live AST scanning & text search
    defs: List[ReferenceDetail] = []
    imports: List[ReferenceDetail] = []
    calls: List[ReferenceDetail] = []
    subclasses: List[ReferenceDetail] = []
    text_matches: List[ReferenceDetail] = []
    ast_callers: Set[str] = set()
    ast_callees: Set[str] = set()
    ast_symbol_catalog: List[Tuple[str, Optional[str], str]] = []

    seen_defs: Set[Tuple[str, int]] = set()
    seen_imports: Set[Tuple[str, int]] = set()
    seen_calls: Set[Tuple[str, int, str]] = set()
    seen_subclasses: Set[Tuple[str, int]] = set()
    seen_text: Set[Tuple[str, int]] = set()

    for full_path in file_list:
        try:
            rel_path = full_path.relative_to(ws_root)
        except ValueError:
            rel_path = full_path

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                source = f.read()
        except UnicodeDecodeError:
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    source = f.read()
            except Exception:
                continue
        except (PermissionError, OSError):
            continue

        if is_valid_ident:
            try:
                tree = ast.parse(source, filename=str(rel_path))
                collector = AstReferenceCollector(str(rel_path), clean_symbol)
                collector.visit(tree)

                for d in collector.defs:
                    key = (d.file_path, d.line_number)
                    if key not in seen_defs:
                        seen_defs.add(key)
                        defs.append(d)

                for imp in collector.imports:
                    key = (imp.file_path, imp.line_number)
                    if key not in seen_imports:
                        seen_imports.add(key)
                        imports.append(imp)

                for c in collector.calls:
                    key = (c.file_path, c.line_number, c.context)
                    if key not in seen_calls:
                        seen_calls.add(key)
                        calls.append(c)

                for sub in collector.subclasses:
                    key = (sub.file_path, sub.line_number)
                    if key not in seen_subclasses:
                        seen_subclasses.add(key)
                        subclasses.append(sub)

                ast_callers.update(collector.ast_callers)
                ast_callees.update(collector.ast_callees)
                ast_symbol_catalog.extend(collector.catalog_symbols)
            except (SyntaxError, ValueError, MemoryError, RecursionError):
                pass

        if clean_symbol.lower() in source.lower():
            for lineno, line in enumerate(source.splitlines(), 1):
                if clean_symbol.lower() in line.lower():
                    clean_line = line.strip()
                    if len(clean_line) > 140:
                        clean_line = clean_line[:137] + "..."
                    key = (str(rel_path), lineno)
                    if key not in seen_text:
                        seen_text.add(key)
                        text_matches.append(
                            ReferenceDetail(
                                file_path=str(rel_path),
                                line_number=lineno,
                                kind="text",
                                context=clean_line,
                            )
                        )
                    if len(text_matches) >= 30:
                        break
            if len(text_matches) >= 30:
                pass

    # 4. Resolve node in graph if loaded
    resolved_symbol: Optional[str] = None
    graph_callers: List[str] = []
    graph_callees: List[str] = []

    if graph_loaded:
        resolved_symbol = resolve_graph_node(clean_symbol, graph_indexes)
        if resolved_symbol:
            in_edges = graph_indexes.get("in_edges", {})
            out_edges = graph_indexes.get("out_edges", {})
            graph_callers = in_edges.get(resolved_symbol, [])
            graph_callees = out_edges.get(resolved_symbol, [])

            class_prefix = f"{resolved_symbol}."
            for nid, callers_list in in_edges.items():
                if nid.startswith(class_prefix):
                    graph_callers.extend(callers_list)
            for nid, callees_list in out_edges.items():
                if nid.startswith(class_prefix):
                    graph_callees.extend(callees_list)

            # If AST definitions were not found, synthesize from graph node content
            if not defs:
                node = graph_indexes.get("node_map", {}).get(resolved_symbol, {})
                node_text = node.get("text", "") or ""
                first_line = node_text.splitlines()[0].strip() if node_text else ""
                mod_parts = resolved_symbol.split(".")
                inferred_file = "/".join(mod_parts[:-1]) + ".py" if len(mod_parts) > 1 else f"{resolved_symbol}.py"
                inferred_kind = "class" if first_line.startswith("class ") else "function"

                defs.append(
                    ReferenceDetail(
                        file_path=inferred_file,
                        line_number=1,
                        kind=inferred_kind,
                        context=first_line if first_line else f"{inferred_kind} {clean_symbol}",
                    )
                )

                for child_nid, child_node in graph_indexes.get("node_map", {}).items():
                    if child_nid.startswith(class_prefix) and "." not in child_nid[len(class_prefix):]:
                        child_name = child_nid[len(class_prefix):]
                        child_text = child_node.get("text", "") or ""
                        c_line = child_text.splitlines()[0].strip() if child_text else f"def {child_name}(...)"
                        defs.append(
                            ReferenceDetail(
                                file_path=inferred_file,
                                line_number=1,
                                kind="method",
                                context=c_line[:120],
                            )
                        )
                        if len(defs) >= 20:
                            break

    # 5. Merge callers and callees
    all_callers: List[str] = []
    for c in list(ast_callers) + graph_callers:
        if c not in all_callers:
            all_callers.append(c)

    all_callees: List[str] = []
    for c in list(ast_callees) + graph_callees:
        if c not in all_callees:
            all_callees.append(c)

    found = bool(resolved_symbol or defs or imports or calls or subclasses)
    if not found and not is_valid_ident and text_matches:
        found = True

    # 6. Explanations, Suggestions, and Top-Level Symbols
    inspection_hint: Optional[str] = None
    suggestions: List[SymbolSuggestion] = []
    did_you_mean: List[str] = []
    top_repo_symbols: List[str] = []
    next_steps: List[str] = []

    if clean_symbol.startswith("_"):
        inspection_hint = (
            f"Symbol '{clean_symbol}' starts with an underscore ('_'), indicating a private or "
            "internal function or attribute. Private symbols are often scoped locally within "
            "their defining module or class body and may not be registered as top-level public nodes "
            "in precomputed code graphs.\n"
            "Recommended inspection actions:\n"
            f"  1. Search definitions with fast-grep: grep.py 'def {clean_symbol}'\n"
            f"  2. Search attribute accesses: grep.py '.{clean_symbol}'\n"
            "  3. Inspect the containing module file directly using map.py --file <path>."
        )
    elif "." in clean_symbol:
        leaf = clean_symbol.split(".")[-1]
        parent = clean_symbol.rsplit(".", 1)[0]
        inspection_hint = (
            f"Symbol '{clean_symbol}' is a qualified or dotted path. Qualified paths depend on "
            "import bindings and module hierarchies. If the qualified path fails to resolve:\n"
            f"  1. Search for the unqualified leaf symbol: '{leaf}'\n"
            f"  2. Search for the enclosing module or class: '{parent}'\n"
            f"  3. Trace references with fast-grep: grep.py '{leaf}'\n"
            "  4. Inspect the parent module file directly using map.py --file <path>."
        )
    elif not is_valid_ident:
        inspection_hint = (
            f"Query '{clean_symbol}' is not a valid Python identifier. code-map --symbol specializes "
            "in Python AST symbols (classes, functions, methods, variables). For arbitrary text patterns, "
            f"use fast-grep: grep.py '{clean_symbol}'"
        )

    if found:
        active_name = resolved_symbol or clean_symbol
        explanation = f"Symbol '{clean_symbol}' was successfully traced across the repository."
        caller_callee_summary = (
            f"Symbol '{active_name}' has {len(all_callers)} inbound caller(s) "
            f"and {len(all_callees)} outbound callee(s)."
        )
        if defs:
            first_def = defs[0]
            next_steps.append(f"Inspect defining module: python3 map.py --file {first_def.file_path}")
        if focus == "callers" and all_callers:
            next_steps.append(f"Inspect top caller: python3 map.py --symbol {all_callers[0].split()[0]}")
        elif focus == "callees" and all_callees:
            next_steps.append(f"Inspect top callee: python3 map.py --symbol {all_callees[0].split()[0]}")
        next_steps.append(f"Search direct calls across repo: grep.py '{clean_symbol}'")
    else:
        if graph_loaded:
            explanation = (
                f"Symbol '{clean_symbol}' was not found in the precomputed codebase graph "
                f"({node_count} nodes searched) or workspace AST."
            )
        else:
            explanation = (
                f"Symbol '{clean_symbol}' was not found in the precomputed codebase graph "
                f"(graph JSON was missing or inaccessible) or workspace AST ({len(file_list)} files scanned)."
            )

        candidates: List[Tuple[str, Optional[str], Optional[str]]] = []
        if graph_loaded:
            for nid in graph_indexes.get("node_ids", []):
                mod_parts = nid.split(".")
                inferred_loc = "/".join(mod_parts[:-1]) + ".py" if len(mod_parts) > 1 else None
                candidates.append((nid, "graph_node", inferred_loc))
                leaf = nid.split(".")[-1]
                if leaf:
                    candidates.append((leaf, "graph_node", inferred_loc))

        for sym, kind, loc in ast_symbol_catalog:
            candidates.append((sym, kind, loc))

        suggestions = compute_fuzzy_suggestions(clean_symbol, candidates, top_n=6, cutoff=0.30)
        did_you_mean = [s.symbol for s in suggestions]
        caller_callee_summary = f"Symbol '{clean_symbol}' was not found in the codebase graph."

        # Collect available top-level public symbols from the workspace to guide the LLM
        top_repo_symbols = get_top_repo_symbols(ws_root, max_symbols=12)

        if suggestions:
            top_s = suggestions[0]
            if top_s.inspect_command:
                next_steps.append(f"Try closest suggested symbol: {top_s.inspect_command}")
            if top_s.file_command:
                next_steps.append(f"Inspect candidate file: {top_s.file_command}")
        next_steps.append(f"Search codebase text with fast-grep: grep.py '{clean_symbol}'")
        next_steps.append("View repository structure and modules: python3 map.py")

    return CodeGraphResult(
        mode="symbol",
        query=symbol_name,
        found=found,
        resolved_symbol=resolved_symbol,
        focus=focus,
        explanation=explanation,
        inspection_hint=inspection_hint,
        graph_status=graph_status,
        definitions=defs,
        imports=imports,
        calls=calls,
        subclasses=subclasses,
        text_occurrences=text_matches,
        callers=all_callers,
        callees=all_callees,
        caller_callee_summary=caller_callee_summary,
        suggestions=suggestions,
        did_you_mean=did_you_mean,
        available_top_symbols=top_repo_symbols,
        next_steps=next_steps,
    )


def format_symbol_report(result: CodeGraphResult) -> str:
    """Format CodeGraphResult into concise, informative text report with actionable LLM guidance."""
    lines: List[str] = [
        "=" * 80,
        "CODE-MAP: SYMBOL REFERENCE & REACHABILITY REPORT",
        "=" * 80,
        f"QUERY: {result.query}",
        f"STATUS: {'FOUND' if result.found else 'NOT FOUND'}",
    ]

    if result.focus:
        lines.append(f"FOCUS: {result.focus.upper()}")

    if result.resolved_symbol:
        lines.append(f"RESOLVED SYMBOL: {result.resolved_symbol}")

    lines.append(f"EXPLANATION: {result.explanation}")
    lines.append("")

    # If focus == 'callers' or 'callees', highlight them prominently at the top
    if result.focus == "callers":
        lines.append("=" * 40)
        lines.append(f"TARGET INBOUND CALLERS FOR '{result.query}':")
        lines.append("=" * 40)
        if result.callers:
            lines.append(f"  Total Inbound Callers: {len(result.callers)}")
            for clr in result.callers[:30]:
                lines.append(f"  👉 {clr}")
        else:
            lines.append("  (0 direct static callers recorded)")
        lines.append("")
    elif result.focus == "callees":
        lines.append("=" * 40)
        lines.append(f"TARGET OUTBOUND CALLEES FOR '{result.query}':")
        lines.append("=" * 40)
        if result.callees:
            lines.append(f"  Total Outbound Callees: {len(result.callees)}")
            for cle in result.callees[:30]:
                lines.append(f"  👉 {cle}")
        else:
            lines.append("  (0 direct static callees recorded)")
        lines.append("")

    lines.append("GRAPH TOPOLOGY:")
    if result.graph_status.graph_loaded:
        lines.append(f"  {result.graph_status.diagnostic_message}")
    else:
        lines.append("  Precomputed codebase graph JSON is missing or inaccessible.")
        lines.append("  Where graphs live: Precomputed codebase graphs are stored as 'graphs/<repo>.json'")
        lines.append("  or 'data/graphs/<repo>.json' (NetworkX node-link JSON).")
        lines.append("  Fallback instructions: Utilizing live repository AST scan for symbol tracing.")
    lines.append("")

    if result.found:
        lines.append(f"DEFINITIONS ({len(result.definitions)}):")
        if result.definitions:
            for d in result.definitions[:20]:
                bases_info = f" [bases: {', '.join(d.bases)}]" if d.bases else ""
                lines.append(f"  - {d.file_path}:{d.line_number} ({d.kind}): {d.context}{bases_info}")
        else:
            lines.append("  (none found in AST)")
        lines.append("")

        if result.subclasses:
            lines.append(f"CLASS HIERARCHY / SUBCLASSES ({len(result.subclasses)}):")
            for sub in result.subclasses[:15]:
                lines.append(f"  - {sub.file_path}:{sub.line_number}: {sub.context}")
            lines.append("")

        lines.append(f"IMPORTS ({len(result.imports)}):")
        if result.imports:
            for imp in result.imports[:20]:
                lines.append(f"  - {imp.file_path}:{imp.line_number}: {imp.context}")
        else:
            lines.append("  (none)")
        lines.append("")

        lines.append(f"CALLS & ATTRIBUTES ({len(result.calls)}, first 20):")
        if result.calls:
            for c in result.calls[:20]:
                caller_info = f" [caller: {c.caller}]" if c.caller else ""
                lines.append(f"  - {c.file_path}:{c.line_number} ({c.kind}): {c.context}{caller_info}")
        else:
            lines.append("  (none)")
        lines.append("")

        if not result.focus:
            lines.append("CALL GRAPH REACHABILITY:")
            lines.append(f"  {result.caller_callee_summary}")
            if result.callers:
                lines.append(f"  Inbound Callers ({len(result.callers)}, first 10):")
                for clr in result.callers[:10]:
                    lines.append(f"    - {clr}")
            else:
                lines.append("  Inbound Callers: (0 direct static callers recorded)")

            if result.callees:
                lines.append(f"  Outbound Callees ({len(result.callees)}, first 10):")
                for cle in result.callees[:10]:
                    lines.append(f"    - {cle}")
            else:
                lines.append("  Outbound Callees: (0 direct static callees recorded)")
            lines.append("")

        if result.text_occurrences:
            lines.append("TEXT OCCURRENCES (first 15):")
            for t in result.text_occurrences[:15]:
                lines.append(f"  - {t.file_path}:{t.line_number}: {t.context}")
            lines.append("")

    else:
        lines.append("WHY THIS QUERY FAILED:")
        lines.append(f"  Symbol '{result.query}' was not identified in the codebase graph or repository AST.")
        if result.query.startswith("_"):
            lines.append(f"  • Note: Symbol starts with '_', indicating a private/internal function or attribute.")
            lines.append("    Private symbols are often not registered as public graph nodes.")
        elif "." in result.query:
            lines.append(f"  • Note: Symbol contains dots. Dotted path queries depend on exact module import hierarchy.")
        elif not result.query.isidentifier():
            lines.append(f"  • Note: Query '{result.query}' is not a valid Python identifier.")
        else:
            lines.append("  • The symbol name may contain a typo, or the symbol is defined dynamically at runtime.")
        lines.append("")

        lines.append("SUGGESTIONS:")
        if result.suggestions:
            lines.append("  Did you mean one of these symbols?")
            for idx, s in enumerate(result.suggestions, 1):
                loc_str = f" [location: {s.location}]" if s.location else ""
                kind_str = f" ({s.kind})" if s.kind else ""
                lines.append(f"    {idx}. {s.symbol}{kind_str} (similarity: {s.similarity:.2f}){loc_str}")
                if s.inspect_command:
                    lines.append(f"       👉 {s.inspect_command}")
                if s.file_command:
                    lines.append(f"       👉 {s.file_command}")
        else:
            lines.append("  No close fuzzy matches found in codebase graph or repository AST.")
        lines.append("")

        if result.available_top_symbols:
            lines.append("TOP-LEVEL PUBLIC SYMBOLS IN REPOSITORY:")
            for sym in result.available_top_symbols:
                clean_sym = sym.replace("class ", "").replace("def ", "").replace("()", "")
                lines.append(f"  • {sym}  ->  python3 map.py --symbol {clean_sym}")
            lines.append("")

    if result.inspection_hint:
        lines.append("INSPECTION HINT:")
        for hint_line in result.inspection_hint.splitlines():
            lines.append(f"  {hint_line}")
        lines.append("")

    if result.next_steps:
        lines.append("ACTIONABLE NEXT STEPS:")
        for step in result.next_steps:
            lines.append(f"  👉 {step}")
        lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


# ==============================================================================
# AST Formatting & Symbol Extraction (--file mode)
# ==============================================================================


def format_args(args_node: ast.arguments) -> str:
    """Format argument list string from AST node, keeping it concise."""
    try:
        raw = ast.unparse(args_node)
        s = " ".join(raw.split())
        if len(s) > 60:
            s = s[:57] + "..."
        return s
    except Exception:
        pass

    names: List[str] = []
    for a in args_node.posonlyargs + args_node.args:
        names.append(a.arg)
    if args_node.vararg:
        names.append("*" + args_node.vararg.arg)
    for a in args_node.kwonlyargs:
        names.append(a.arg)
    if args_node.kwarg:
        names.append("**" + args_node.kwarg.arg)
    s = ", ".join(names)
    if len(s) > 60:
        s = s[:57] + "..."
    return s


def format_return(ret_node: Optional[ast.AST]) -> str:
    """Format return type annotation string from AST node."""
    if ret_node is None:
        return ""
    try:
        s = ast.unparse(ret_node)
        s = " ".join(s.split())
        return f" -> {s}"
    except Exception:
        return ""


def format_docstring(node: ast.AST, indent: str = "    ") -> Optional[str]:
    """Extract and format a one-line docstring summary."""
    try:
        doc = ast.get_docstring(node)
        if not doc:
            return None
        first_line = doc.strip().split("\n")[0].strip()
        if not first_line:
            return None
        if len(first_line) > 70:
            first_line = first_line[:67] + "..."
        return f'{indent}"""{first_line}"""'
    except Exception:
        return None


def get_symbols(
    body: List[ast.stmt],
    is_class: bool = False,
    current_depth: int = 0,
    max_depth: int = 8,
) -> List[Tuple[str, str, str, int, int, Optional[str]]]:
    """Extract symbol items from AST statements with recursion bounds.

    Returns list of tuples: (kind, name, signature, start_line, end_line, docstring).
    """
    if current_depth >= max_depth:
        return []

    items: List[Tuple[str, str, str, int, int, Optional[str]]] = []
    for node in body:
        try:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                args_str = format_args(node.args)
                ret_str = format_return(getattr(node, "returns", None))
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                indent = "    " if is_class else "  "
                sig = f"{indent}{prefix} {node.name}({args_str}){ret_str} [{start}-{end}]"
                doc = format_docstring(node, indent=indent + "  ")
                items.append((prefix, node.name, sig, start, end, doc))
            elif isinstance(node, ast.ClassDef):
                bases_str = ""
                if node.bases:
                    base_names: List[str] = []
                    for b in node.bases:
                        try:
                            base_names.append(ast.unparse(b))
                        except Exception:
                            if isinstance(b, ast.Name):
                                base_names.append(b.id)
                    if base_names:
                        bases_str = f"({', '.join(base_names)})"
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                sig = f"  class {node.name}{bases_str} [{start}-{end}]"
                doc = format_docstring(node, indent="    ")
                items.append(("class", node.name, sig, start, end, doc))
                methods = get_symbols(node.body, is_class=True, current_depth=current_depth + 1, max_depth=max_depth)
                items.extend(methods)
        except (RecursionError, MemoryError):
            continue
    return items


def parse_and_map_file(
    py_file: pathlib.Path,
    ws: pathlib.Path,
) -> Tuple[ModuleSummary, Optional[MapDiagnostic]]:
    """Parse a single Python file, extract AST symbols, and diagnose syntax/permission/encoding errors."""
    try:
        rel_display = py_file.relative_to(ws)
    except ValueError:
        rel_display = py_file

    try:
        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        diag = MapDiagnostic(
            level="warning",
            category="encoding_error",
            message=f"File '{rel_display}' contains unparseable binary or invalid UTF-8 encoding: {e}",
            target_path=str(rel_display),
            guidance="Verify file encoding (UTF-8 required) or verify that this is a Python source file.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except PermissionError as e:
        diag = MapDiagnostic(
            level="error",
            category="permission_denied",
            message=f"Permission denied reading file '{rel_display}': {e}",
            target_path=str(rel_display),
            guidance="Check file permissions or run with appropriate access privileges.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except OSError as e:
        diag = MapDiagnostic(
            level="error",
            category="unparseable_file",
            message=f"Failed to read file '{rel_display}': {e}",
            target_path=str(rel_display),
            guidance="Verify file exists and filesystem is accessible.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag

    try:
        tree = ast.parse(content, filename=str(py_file))
    except SyntaxError as e:
        err_line = e.lineno or 1
        err_col = e.offset or 1
        err_msg = e.msg or "invalid syntax"

        content_lines = content.splitlines()
        if e.text:
            source_line = e.text.rstrip("\r\n").expandtabs(4)
        elif 1 <= err_line <= len(content_lines):
            source_line = content_lines[err_line - 1].expandtabs(4)
        else:
            source_line = ""

        gutter = f"    {err_line} | "
        safe_col = max(1, min(err_col, len(source_line) + 1))
        caret_line = " " * (len(gutter) + safe_col - 1) + "^"
        snippet = f"{gutter}{source_line}\n{caret_line}"

        guidance = (
            f"File '{rel_display}' contains invalid Python syntax at line {err_line}, column {err_col}. "
            "This error prevents AST parsing and was likely introduced by a recent edit_file call "
            "(e.g., unclosed parenthesis/bracket/quote, mismatched indentation, or incomplete statement). "
            f"Inspect line {err_line} or run diff-inspect / git diff to repair syntax."
        )

        diag = MapDiagnostic(
            level="error",
            category="syntax_error",
            message=f"SyntaxError: {err_msg} (line {err_line}, column {err_col})",
            target_path=str(rel_display),
            line=err_line,
            column=err_col,
            snippet=snippet,
            guidance=guidance,
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except RecursionError:
        diag = MapDiagnostic(
            level="warning",
            category="recursion_limit_exceeded",
            message=f"AST nesting depth exceeds limit in '{rel_display}'.",
            target_path=str(rel_display),
            guidance="File contains deeply nested structures; outline skipped to prevent stack overflow.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag
    except Exception as e:
        diag = MapDiagnostic(
            level="warning",
            category="unparseable_file",
            message=f"AST parse failure in '{rel_display}': {e}",
            target_path=str(rel_display),
            guidance="Inspect file for non-standard Python syntax.",
        )
        return ModuleSummary(path=str(rel_display), syntax_error=diag), diag

    raw_symbols = get_symbols(tree.body)
    symbol_items: List[SymbolItem] = []
    for kind, name, sig, start, end, doc in raw_symbols:
        symbol_items.append(
            SymbolItem(
                kind=kind,
                name=name,
                signature=sig,
                start_line=start,
                end_line=end,
                docstring=doc,
            )
        )

    return (
        ModuleSummary(
            path=str(rel_display),
            symbols=symbol_items,
            symbol_count=len(symbol_items),
        ),
        None,
    )


def generate_file_skeleton(target_str: str, max_lines: int = 120) -> FileSkeletonResult:
    """Generate compact AST skeleton for a target file or directory up to max_lines budget."""
    ws = get_workspace_dir()
    target_path, clean_target = resolve_target(target_str, ws)

    # 1. Target does not exist: Provide actionable diagnostics & suggestions
    if target_path is None or not target_path.exists():
        diag_msg = f"Path '{target_str}' does not exist in /workspace."
        suggestions = find_closest_paths(clean_target, ws)
        layout_items = get_top_level_layout(ws)
        guidance = (
            f"Target '{target_str}' was not found in /workspace. "
            "Review the suggested closest matches or top-level repository layout below to select an existing file."
        )
        diag = MapDiagnostic(
            level="error",
            category="missing_path",
            message=diag_msg,
            target_path=target_str,
            suggestions=suggestions,
            guidance=guidance,
        )
        lines: List[str] = [
            f"[code-map] {diag_msg}",
            "",
            "WHY THIS FAILED:",
            f"  Target path '{target_str}' does not exist in the active workspace.",
            "  Common causes:",
            "  1. Typo in directory or file name.",
            "  2. Missing folder prefix (e.g. 'src/' or package directory).",
            "  3. Missing or wrong file extension (.py).",
            "",
        ]
        if str(ws) != "/workspace":
            lines.append(f"  (Active workspace root: {ws})")
            lines.append("")
        if suggestions:
            lines.append("💡 Suggested closest existing paths:")
            for s in suggestions:
                lines.append(f"  • {s}")
                clean_s = s.replace("📁 ", "").replace("📄 ", "").rstrip("/")
                lines.append(f"     👉 python3 map.py --file {clean_s}")
            lines.append("")
        if layout_items:
            lines.append("📂 Top-level repository layout (/workspace):")
            for item in layout_items:
                lines.append(f"  {item.summary}")
            lines.append("")

        next_steps: List[str] = []
        if suggestions:
            for s in suggestions[:3]:
                best = s.replace("📁 ", "").replace("📄 ", "").rstrip("/")
                next_steps.append(f"Inspect closest match: python3 map.py --file {best}")
        next_steps.append("View repository overview and packages: python3 map.py")

        if next_steps:
            lines.append("👉 Actionable next steps:")
            for step in next_steps:
                lines.append(f"  • {step}")
            lines.append("")

        rendered = "\n".join(lines)
        return FileSkeletonResult(
            mode="file",
            target=target_str,
            workspace_root=str(ws),
            success=False,
            modules=[],
            total_files=0,
            total_symbols=0,
            diagnostics=[diag],
            top_level_layout=layout_items,
            is_truncated=False,
            rendered_text=rendered,
            next_steps=next_steps,
        )

    # 2. Target exists: Collect .py files (single file or directory)
    py_files = collect_py_files(target_path, ws, max_files=100)

    # Directory has no .py files: Forgivingly list directory contents and point to python code
    if not py_files:
        items_in_dir: List[str] = []
        try:
            if target_path.is_dir():
                for item in sorted(target_path.iterdir()):
                    if not item.name.startswith("."):
                        icon = "📁" if item.is_dir() else "📄"
                        items_in_dir.append(f"{icon} {item.name}")
        except Exception:
            pass

        diag_msg = f"No Python source files (.py) found in target '{target_str}'."
        diag = MapDiagnostic(
            level="warning",
            category="empty_target",
            message=diag_msg,
            target_path=target_str,
            suggestions=items_in_dir[:6],
            guidance="Specify a directory or file that contains Python source code.",
        )
        lines = [
            f"[code-map] {diag_msg}",
            "",
            "WHY THIS FAILED:",
            f"  Target '{target_str}' exists but contains no Python source files (.py).",
            "",
        ]
        if items_in_dir:
            lines.append("Contents of target directory:")
            for itm in items_in_dir[:10]:
                lines.append(f"  {itm}")
            lines.append("")

        layout_items = get_top_level_layout(ws)
        if layout_items:
            lines.append("📂 Directories with Python code (/workspace):")
            for item in layout_items:
                if item.is_dir and ".py" in item.summary:
                    lines.append(f"  {item.summary}")
            lines.append("")

        rendered = "\n".join(lines)
        return FileSkeletonResult(
            mode="file",
            target=target_str,
            workspace_root=str(ws),
            success=False,
            modules=[],
            total_files=0,
            total_symbols=0,
            diagnostics=[diag],
            top_level_layout=layout_items,
            is_truncated=False,
            rendered_text=rendered,
            next_steps=["Run 'python3 map.py' to see packages with Python code"],
        )

    # 3. Target is a single file with syntax error: Special detailed diagnostic
    if len(py_files) == 1:
        mod_summary, diag = parse_and_map_file(py_files[0], ws)
        if diag and diag.category == "syntax_error":
            single_file_lines = [
                f"[code-map: SyntaxError in {mod_summary.path}]",
                f"  Location: Line {diag.line}, Column {diag.column}",
                f"  Error: {diag.message}",
                "",
                "  Code Snippet:",
            ]
            if diag.snippet:
                single_file_lines.extend(diag.snippet.splitlines())
            if diag.guidance:
                single_file_lines.append("")
                single_file_lines.append(f"  Guidance: {diag.guidance}")

            rendered = "\n".join(single_file_lines)
            return FileSkeletonResult(
                mode="file",
                target=target_str,
                workspace_root=str(ws),
                success=True,
                modules=[mod_summary],
                total_files=1,
                total_symbols=0,
                diagnostics=[diag],
                top_level_layout=[],
                is_truncated=False,
                rendered_text=rendered,
                next_steps=[f"Fix syntax error at line {diag.line} using edit_file"],
            )

    # 4. Multi-file or single file AST outline generation with strict max_lines budget
    output_lines: List[str] = []
    modules: List[ModuleSummary] = []
    all_diagnostics: List[MapDiagnostic] = []
    total_symbols = 0
    total_files_parsed = 0
    is_truncated = False

    for py_file in py_files:
        mod_summary, diag = parse_and_map_file(py_file, ws)
        modules.append(mod_summary)
        if diag:
            all_diagnostics.append(diag)

        file_lines: List[str] = [f"{mod_summary.path}:"]
        if mod_summary.syntax_error:
            err = mod_summary.syntax_error
            file_lines.append(f"  ⚠️  [SyntaxError at line {err.line}, col {err.column}: {err.message}]")
            if err.snippet:
                file_lines.extend(err.snippet.splitlines())
        else:
            if not mod_summary.symbols:
                continue
            for sym in mod_summary.symbols:
                file_lines.append(sym.signature)
                if sym.docstring:
                    file_lines.append(sym.docstring)

        if len(output_lines) + len(file_lines) > max_lines:
            remaining = len(py_files) - total_files_parsed
            output_lines.append(f"... [Truncated at {max_lines} lines; {remaining} more file(s)]")
            is_truncated = True
            break

        output_lines.extend(file_lines)
        total_symbols += mod_summary.symbol_count
        total_files_parsed += 1

    syntax_err_count = sum(1 for m in modules if m.syntax_error)
    summary_parts = [f"[code-map: {total_symbols} symbols across {total_files_parsed} file(s)"]
    if syntax_err_count > 0:
        summary_parts.append(f" ({syntax_err_count} file(s) had syntax errors)")
    summary_parts.append("]")
    output_lines.append("".join(summary_parts))

    rendered = "\n".join(output_lines)

    next_steps: List[str] = []
    if modules and modules[0].symbols:
        first_sym = modules[0].symbols[0].name
        next_steps.append(f"Trace symbol call-graph: python3 map.py --symbol {first_sym}")
    if len(py_files) > 1 and is_truncated:
        first_mod = modules[0].path
        next_steps.append(f"Inspect single module outline: python3 map.py --file {first_mod}")

    return FileSkeletonResult(
        mode="file",
        target=target_str,
        workspace_root=str(ws),
        success=True,
        modules=modules,
        total_files=total_files_parsed,
        total_symbols=total_symbols,
        diagnostics=all_diagnostics,
        top_level_layout=[],
        is_truncated=is_truncated,
        rendered_text=rendered,
        next_steps=next_steps,
    )


# ==============================================================================
# Workspace Repository Overview & Usage Guide (Empty Calls & '.' / '/workspace')
# ==============================================================================


def generate_workspace_overview(ws: pathlib.Path) -> WorkspaceOverviewResult:
    """Generate forgiving repository overview and copy-pasteable usage guide tailored to current workspace."""
    layout_items = get_top_level_layout(ws)

    # Discovered packages: top-level dirs with .py files
    discovered_packages: List[str] = []
    for item in layout_items:
        if item.is_dir and ".py" in item.summary:
            discovered_packages.append(item.name)

    # Discovered sample files
    sample_files = collect_py_files(ws, ws, max_files=15)
    core_files = [p for p in sample_files if "test" not in p.name.lower() and "test" not in str(p).lower()]
    chosen_files = core_files if core_files else sample_files
    key_modules: List[str] = []
    for p in chosen_files[:3]:
        try:
            rel = str(p.relative_to(ws))
            key_modules.append(rel)
        except Exception:
            pass

    # Sample symbols
    sample_symbols = get_top_repo_symbols(ws, max_symbols=6)
    clean_sample_symbols = [
        s.replace("class ", "").replace("def ", "").replace("()", "")
        for s in sample_symbols
    ]

    # Generate tailored copy-pasteable commands
    example_mod = key_modules[0] if key_modules else "example.py"
    example_pkg = discovered_packages[0] if discovered_packages else "."
    example_sym = clean_sample_symbols[0] if clean_sample_symbols else "main"

    commands = [
        f"python3 map.py --file {example_mod}           # Compact AST outline of a key module",
        f"python3 map.py --file {example_pkg}                 # Map package directory structure",
        f"python3 map.py --symbol {example_sym}             # Trace call-graph, callers, callees, definitions",
        f"python3 map.py --symbol {example_sym} --callers   # Focus specifically on inbound callers",
        f"python3 map.py {example_mod}                  # Positional shorthand (auto-detects file)",
        f"python3 map.py {example_sym}                  # Positional shorthand (auto-detects symbol)",
    ]

    lines: List[str] = [
        "=" * 80,
        "CODE-MAP: WORKSPACE OVERVIEW & ACTIONABLE USAGE GUIDE",
        "=" * 80,
        f"Workspace Root: {ws}",
        "",
        "📂 TOP-LEVEL REPOSITORY LAYOUT:",
    ]
    if layout_items:
        for item in layout_items:
            lines.append(f"  {item.summary}")
    else:
        lines.append("  (empty or inaccessible workspace)")
    lines.append("")

    if discovered_packages:
        lines.append(f"📦 DISCOVERED PACKAGES: {', '.join(discovered_packages)}")
        lines.append("")

    if key_modules:
        lines.append("📄 KEY MODULES:")
        for m in key_modules:
            lines.append(f"  • {m}")
        lines.append("")

    if clean_sample_symbols:
        lines.append("🔍 SAMPLE PUBLIC SYMBOLS:")
        for sym in clean_sample_symbols:
            lines.append(f"  • {sym}")
        lines.append("")

    lines.append("💡 TAILORED COPY-PASTEABLE COMMANDS:")
    for cmd in commands:
        lines.append(f"  {cmd}")
    lines.append("")
    lines.append("=" * 80)

    rendered = "\n".join(lines)

    return WorkspaceOverviewResult(
        mode="overview",
        workspace_root=str(ws),
        success=True,
        top_level_layout=layout_items,
        discovered_packages=discovered_packages,
        key_modules=key_modules,
        sample_symbols=clean_sample_symbols,
        copy_pasteable_commands=commands,
        rendered_text=rendered,
    )


# ==============================================================================
# Forgiving CLI Argument Parsing
# ==============================================================================


def parse_cli_args(argv: List[str]) -> Tuple[ParsedArgs, List[str]]:
    """Forgivingly and omnivorously parse CLI arguments without ever crashing.

    Handles:
    - Aliases: -s, --symbol, -f, --file, -d, --dir, -o, --overview, -t, --tree, --callers, --callees
    - Typo tolerance: maps flags like --symbl to --symbol via fuzzy matching
    - Unrecognized flags: warns and routes to closest intent or overview
    - Missing flag values: uses defaults gracefully without ArgumentError
    - Seamless positional fallbacks: symbol vs file/dir auto-detection
    """
    notices: List[str] = []
    args = ParsedArgs()

    i = 0
    positional: List[str] = []

    KNOWN_FLAGS = {
        "-s": "symbol",
        "--symbol": "symbol",
        "--sym": "symbol",
        "--symbols": "symbol",
        "--function": "symbol",
        "--fn": "symbol",
        "--class": "symbol",
        "-f": "file",
        "--file": "file",
        "--path": "file",
        "--filepath": "file",
        "-d": "dir",
        "--dir": "dir",
        "--directory": "dir",
        "--folder": "dir",
        "-o": "overview",
        "--overview": "overview",
        "--summary": "overview",
        "--workspace": "overview",
        "-t": "tree",
        "--tree": "tree",
        "--callers": "callers",
        "--caller": "callers",
        "--inbound": "callers",
        "--callees": "callees",
        "--callee": "callees",
        "--outbound": "callees",
        "-j": "json",
        "--json": "json",
        "-g": "graph",
        "--graph": "graph",
        "-n": "max_lines",
        "--max-lines": "max_lines",
        "--limit": "max_lines",
        "--lines": "max_lines",
        "-h": "help",
        "--help": "help",
    }

    while i < len(argv):
        arg = argv[i]
        val = None

        if arg in ("-h", "--help"):
            return ParsedArgs(overview=True), ["help"]

        # Handle --flag=value syntax
        if "=" in arg and arg.startswith("-"):
            flag_part, val = arg.split("=", 1)
        else:
            flag_part = arg

        canon = KNOWN_FLAGS.get(flag_part)

        # Fuzzy match flag typo if starts with - or --
        if not canon and flag_part.startswith("-"):
            clean_flag = flag_part.lstrip("-")
            all_clean = {k.lstrip("-"): v for k, v in KNOWN_FLAGS.items()}
            close = difflib.get_close_matches(clean_flag, list(all_clean.keys()), n=1, cutoff=0.6)
            if close:
                canon = all_clean[close[0]]
                notices.append(f"Interpreted flag '{flag_part}' as '--{close[0]}'.")
            else:
                notices.append(f"Unrecognized option '{flag_part}' ignored.")
                i += 1
                continue

        if canon == "symbol":
            if val is not None:
                args.symbol = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.symbol = argv[i]
            else:
                notices.append("Option '--symbol' passed without a value.")
        elif canon == "file":
            if val is not None:
                args.file = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.file = argv[i]
            else:
                notices.append("Option '--file' passed without a value.")
        elif canon == "dir":
            if val is not None:
                args.dir = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.dir = argv[i]
            else:
                notices.append("Option '--dir' passed without a value.")
        elif canon == "overview":
            args.overview = True
        elif canon == "tree":
            args.tree = True
        elif canon == "callers":
            args.focus = "callers"
            if val is not None:
                args.callers = val
                args.symbol = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.callers = argv[i]
                args.symbol = argv[i]
            else:
                args.callers = True
        elif canon == "callees":
            args.focus = "callees"
            if val is not None:
                args.callees = val
                args.symbol = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.callees = argv[i]
                args.symbol = argv[i]
            else:
                args.callees = True
        elif canon == "json":
            args.json = True
        elif canon == "graph":
            if val is not None:
                args.graph = val
            elif i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                args.graph = argv[i]
        elif canon == "max_lines":
            lines_val = val
            if lines_val is None and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                lines_val = argv[i]
            if lines_val:
                try:
                    args.max_lines = int(lines_val)
                except ValueError:
                    notices.append(f"Invalid integer '{lines_val}' for line budget; using default.")
        elif not arg.startswith("-"):
            positional.append(arg)

        i += 1

    if positional:
        args.target = positional[0]

    args.notices = notices
    return args, []


def determine_mode_and_target(
    args: ParsedArgs,
    ws: pathlib.Path,
) -> Tuple[str, str, Optional[str]]:
    """Deterministically and forgivingly resolve analysis mode ('overview', 'file', 'symbol'), target, and focus."""
    # 1. Explicit overview flag
    if args.overview:
        return "overview", ".", None

    # 2. Tree flag: directory tree / file outline
    if args.tree:
        tree_target = args.dir or args.file or args.target or "."
        return "file", tree_target, None

    # 3. Callers / Callees flag with explicit value or focus
    if args.callers:
        sym = args.callers if isinstance(args.callers, str) else (args.symbol or args.target or "")
        if sym:
            return "symbol", sym, "callers"

    if args.callees:
        sym = args.callees if isinstance(args.callees, str) else (args.symbol or args.target or "")
        if sym:
            return "symbol", sym, "callees"

    # 4. Explicit --symbol
    if args.symbol:
        return "symbol", args.symbol, args.focus

    # 5. Explicit --dir
    if args.dir:
        return "file", args.dir, None

    # 6. Explicit --file
    if args.file:
        if args.file in (".", "/", "/workspace"):
            return "overview", ".", None
        return "file", args.file, None

    # 7. Positional argument
    if args.target:
        clean = args.target.strip()
        if not clean or clean in (".", "/", "/workspace"):
            return "overview", ".", None

        # Clearly a file extension or path with separators
        if clean.endswith(".py") or clean.endswith(".pyi") or "/" in clean or "\\" in clean:
            return "file", clean, None

        # Check direct existence as file or directory in workspace
        cand_p = ws / clean
        if cand_p.is_file() or cand_p.is_dir():
            return "file", clean, None

        cand_py = ws / f"{clean}.py"
        if cand_py.is_file():
            return "file", f"{clean}.py", None

        # Check with resolve_target for glob/search matches
        resolved, _ = resolve_target(clean, ws)
        if resolved is not None and resolved.exists():
            return "file", clean, None

        # Otherwise, treat as symbol
        return "symbol", clean, args.focus

    # 8. No arguments passed at all -> overview mode
    return "overview", ".", None


def print_help():
    """Print user/LLM help text."""
    print("""code-map: AST code structure and symbol call-graph tracer.

Usage:
  python3 map.py [TARGET] [OPTIONS]

Modes:
  --symbol, -s <name>     Trace callers, callees, definitions, and class hierarchy across repository.
  --file, -f <path>       Generate compact AST skeleton for a Python file or directory.
  --dir, -d <path>        Generate AST skeleton for all modules in a directory.
  --tree, -t [path]       Map directory tree structure and module skeletons.
  --overview, -o          Display workspace overview, discovered packages, and key modules.
  --callers [symbol]      Focus on inbound callers for the target symbol.
  --callees [symbol]      Focus on outbound callees for the target symbol.
  <target>                Positional shorthand (auto-detects file, directory, or symbol).
  (empty)                 Displays workspace overview, discovered packages, and tailored commands.

Options:
  --json, -j              Output structured JSON schema (Pydantic v2).
  --max-lines, -n <int>   Maximum lines of symbol output for directory outlines (default: 120).
  --graph, -g <path>      Explicit path to precomputed codebase graph JSON.
  --help, -h              Show this help message and exit.

Examples:
  python3 map.py                                # Repository overview & tailored usage guide
  python3 map.py --symbol APIRouter             # Trace symbol callers/callees/definitions
  python3 map.py -s APIRouter --callers         # Focus on inbound callers of APIRouter
  python3 map.py -s APIRouter --callees         # Focus on outbound callees of APIRouter
  python3 map.py --file fastapi/routing.py      # Compact AST outline of a single file
  python3 map.py -f fastapi                     # Map directory modules up to max_lines budget
  python3 map.py -d fastapi                     # Directory mapping shorthand
  python3 map.py APIRouter                      # Auto-detected symbol mode
  python3 map.py fastapi/routing.py             # Auto-detected file mode
  python3 map.py fastapi                        # Auto-detected directory mode
  python3 map.py --symbol APIRouter --json      # Output structured JSON schema
""")


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def run_cli(argv: List[str]) -> int:
    """Execute code-map CLI forgivingly."""
    ws_root = get_workspace_dir()
    parsed_args, extra = parse_cli_args(argv)

    if extra and extra[0] == "help":
        print_help()
        return 0

    mode, target_name, focus = determine_mode_and_target(parsed_args, ws_root)

    # Print notices if any (only in non-json mode)
    if parsed_args.notices and not parsed_args.json:
        for note in parsed_args.notices:
            print(f"[code-map note] {note}")
        print("")

    # 1. Overview Mode
    if mode == "overview":
        res_overview = generate_workspace_overview(ws_root)
        if parsed_args.json:
            print(res_overview.model_dump_json(indent=2))
        else:
            print(res_overview.rendered_text)
        return 0

    # 2. File / Directory Skeleton Mode
    if mode == "file":
        res_file = generate_file_skeleton(target_name, max_lines=parsed_args.max_lines)
        if parsed_args.json:
            print(res_file.model_dump_json(indent=2))
        else:
            print(res_file.rendered_text)
        return 0

    # 3. Symbol Mode
    target_path, _ = resolve_target(".", ws_root)
    res_symbol = analyze_symbol(
        symbol_name=target_name,
        target_path=target_path or ws_root,
        ws_root=ws_root,
        explicit_graph_path=parsed_args.graph,
        focus=focus,
    )

    if parsed_args.json:
        print(res_symbol.model_dump_json(indent=2))
    else:
        print(format_symbol_report(res_symbol))

    return 0


def main() -> int:
    try:
        return run_cli(sys.argv[1:])
    except Exception as e:
        # Ultimate fallback: never crash with unhandled exception or leave LLM stranded
        ws = get_workspace_dir()
        overview = generate_workspace_overview(ws)
        print(f"[code-map note] Command completed with fallback due to: {e}")
        print(overview.rendered_text)
        return 0


if __name__ == "__main__":
    sys.exit(main())
`````

## File: submission/skills/code-map/SKILL.md
`````markdown
---
name: code-map
description: AST code structure and symbol call-graph tracer. Query with --symbol <name> (or -s/--callers/--callees), --file <path> (or -f/-d/--tree), or positional shorthand.
---

# code-map Skill

Unified AST code structure, class hierarchy, and symbol call-graph tracer.
Omnivorous & forgiving: auto-detects positional arguments, supports flexible flag aliases (`-s`, `-f`, `-d`, `--dir`, `--tree`, `--overview`, `--callers`, `--callees`), and provides actionable diagnostics with exact copy-pasteable next steps.

## How to Run

### Via ADK `run_skill_script`

#### 1. Workspace Overview & Repository Guide (Empty, `.`, or `-o`)
```python
run_skill_script(skill_name="code-map", file_path="map.py", args=[])
```

#### 2. Symbol Tracing & Reachability (`--symbol`, `-s`, `--callers`, `--callees`)
Trace definitions (with base classes), subclasses, imports, callers, and callees across the repository:
```python
run_skill_script(skill_name="code-map", file_path="map.py", args=["--symbol", "APIRouter"])
run_skill_script(skill_name="code-map", file_path="map.py", args=["--callers", "APIRouter"])
```

#### 3. Compact File & Directory Skeletons (`--file`, `-f`, `-d`, `--dir`, `--tree`)
Inspect class signatures, methods, return annotations, docstrings, and line ranges `[start-end]`:
```python
run_skill_script(skill_name="code-map", file_path="map.py", args=["--file", "fastapi/routing.py"])
run_skill_script(skill_name="code-map", file_path="map.py", args=["-d", "fastapi"])
```

#### 4. Omnivorous Positional Auto-Detection
- Existing file, `.py` extension, or path with `/`: treated as file outline:
  ```python
  run_skill_script(skill_name="code-map", file_path="map.py", args=["fastapi/routing.py"])
  run_skill_script(skill_name="code-map", file_path="map.py", args=["fastapi"])
  ```
- Symbol identifier: treated as symbol search:
  ```python
  run_skill_script(skill_name="code-map", file_path="map.py", args=["APIRouter"])
  ```

## Core Guarantees

1. **Omnivorous & Forgiving CLI**:
   - Accepts aliases (`-s`, `-f`, `-d`, `--dir`, `--overview`, `-t`, `--tree`, `--callers`, `--callees`).
   - Tolerate flag typos and unrecognized options without crashing (`argparse.ArgumentError` is eliminated).
2. **Actionable Diagnostics ("Tell the LLM what is wrong & how to fix it")**:
   - Missing symbol: fuzzy matching with `difflib`, closest candidate symbols with file/line locations, and exact copy-pasteable commands to inspect them.
   - Missing file: closest path suggestions and workspace layout with copy-pasteable commands.
   - Explains *why* the query failed and *what concrete action* to take next.
3. **Crash & Loop Immunity**:
   - Inode & realpath tracking, symlink immunity (`followlinks=False`), and bounded directory limits prevent filesystem hangs.
   - Catches `SyntaxError`, `UnicodeDecodeError`, and `PermissionError` cleanly without tracebacks.
   - AST recursion depth bounds protect against deeply nested code.

## Exit Codes
- **0 (Success / Actionable Diagnostics)**: Always exits 0 with structured results or recovery steps.
`````

## File: submission/skills/code-oracle/scripts/oracle.py
`````python
#!/usr/bin/env python3
"""code-oracle: Multi-domain coding assistance oracle for SWE agents.

Provides deterministic diagnostics and inspection tools for domain nuances that
commonly cause subtle bugs or failed assertions in SWE benchmarks:
1. --eval <expr>: Safely evaluates a Python expression in the current environment
   with infinite loop timeout protection, full exception trapping, and actionable
   diagnostics for SyntaxError and NameError.
2. --hex <text>: Hex dump and escape sequence inspector. Decodes raw bytes and
   characters, highlights ANSI escapes, SGR parameters, OSC hyperlinks, and
   invisible control/zero-width characters (\r, \n, \t, \u200d, \ufe0f).
3. --width <text>: Calculates exact terminal cell display width for monospaced
   terminals (handling CJK East Asian Width W/F as 2 cells, ZWJ sequences,
   combining characters, ASCII as 1 cell) and explains which characters cause width mismatches.
4. --html-esc <snippet>: Inspects HTML/template strings. Verifies entity escaping
   (&lt;, &gt;, &amp;, quotes), tag matching (open/close tag balance), and warns if
   unescaped < or > exists inside script tags or attribute values.
5. --schema <file_or_json>: Inspects JSON Schema / OpenAPI schema structure.
   Checks $defs vs definitions, validates $ref pointer resolution (flags dangling
   references with exact corrected paths), checks anyOf with None/null, handles
   non-dict schemas, and protects against recursive $ref cycles.
6. --syntax <file>: Validates AST syntax (ast.parse) and checks that top-level
   module imports can be resolved without executing module side-effects.

Zero external dependencies (pure Python standard library).
"""

from __future__ import annotations

import argparse
import ast
import difflib
import html
from html.parser import HTMLParser
import importlib.util
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

sys.dont_write_bytecode = True

# ANSI Escape Regex covering CSI, OSC, and standard 2-byte escape sequences
ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\].*?(?:\x07|\x1b\\))")

# HTML void elements that do not have closing tags
VOID_HTML_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# Standard JSON Schema data types
VALID_JSON_SCHEMA_TYPES = {
    "string", "number", "integer", "boolean", "array", "object", "null",
}


# ==============================================================================
# Helper Utilities
# ==============================================================================

def read_input_text(input_val: str) -> str:
    """If input_val is an existing file path, read its text, otherwise return input_val.
    
    Also decodes escaped literal backslashes if input appears to be shell-escaped
    (e.g., r'\\x1b[31m' -> actual ESC).
    """
    if not input_val:
        return ""
    try:
        p = pathlib.Path(input_val)
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Unescape raw string sequences if user passed literal backslash sequences like \x1b or \u
    if "\\" in input_val:
        try:
            if any(esc in input_val for esc in (r"\x", r"\u", r"\n", r"\r", r"\t")):
                return input_val.encode("utf-8").decode("unicode_escape")
        except Exception:
            pass

    return input_val


def get_workspace_dir(explicit_ws: Optional[str] = None) -> pathlib.Path:
    """Discover workspace directory deterministically."""
    if explicit_ws:
        p = pathlib.Path(explicit_ws)
        if p.is_dir():
            return p.resolve()

    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    ws_fixed = pathlib.Path("/workspace")
    if ws_fixed.is_dir():
        return ws_fixed.resolve()

    cur = pathlib.Path.cwd().resolve()
    for parent in [cur] + list(cur.parents):
        if (
            (parent / "tasks.jsonl").exists()
            or (parent / "my_submission").exists()
            or (parent / ".git").exists()
            or (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
        ):
            return parent

    return cur


def generate_snippet(
    source_lines: Sequence[str],
    lineno: int,
    column: int,
    context_lines: int = 2,
) -> str:
    """Generate a clean code snippet with line numbers and a visual caret pointer."""
    if not source_lines:
        return ""

    target_idx = max(0, min(len(source_lines) - 1, lineno - 1))
    start_idx = max(0, target_idx - context_lines)
    end_idx = min(len(source_lines), target_idx + context_lines + 1)

    gutter_width = max(len(str(end_idx)), 2)
    blank_gutter = " " * gutter_width

    output_lines: List[str] = []
    for idx in range(start_idx, end_idx):
        cur_line_num = idx + 1
        num_str = str(cur_line_num).rjust(gutter_width)
        line_content = source_lines[idx].rstrip("\r\n")

        if idx == target_idx:
            line_display = line_content.expandtabs(4)
            output_lines.append(f"> {num_str} | {line_display}")
            col = max(1, column)
            prefix = line_content[: col - 1].expandtabs(4)
            caret_indent = " " * len(prefix)
            output_lines.append(f"  {blank_gutter} | {caret_indent}^")
        else:
            line_display = line_content.expandtabs(4)
            output_lines.append(f"  {num_str} | {line_display}")

    return "\n".join(output_lines)


# ==============================================================================
# Mode 1: --eval <expr>
# ==============================================================================

class EvalTimeoutError(TimeoutError):
    """Raised when expression evaluation exceeds execution timeout limit."""
    pass


def _eval_alarm_handler(signum: int, frame: Any) -> None:
    raise EvalTimeoutError("Execution timed out (infinite loop or execution exceeded 5.0s limit).")


def run_eval(expr: str, as_json: bool = False) -> int:
    """Safely evaluates a Python expression or statement in the current environment."""
    if not expr or not expr.strip():
        diag = "No expression provided to --eval. Example: python3 oracle.py --eval 'len([1, 2, 3])'"
        if as_json:
            print(json.dumps({"status": "error", "mode": "eval", "error": diag}, indent=2))
        else:
            print(f"✗ [eval-error] {diag}")
        return 1

    expr_clean = expr.strip()

    # Attempt to compile: try eval first (expression), fallback to exec (statements like loops/assignments)
    is_statement = False
    compiled: Any = None
    try:
        compiled = compile(expr_clean, "<eval>", "eval")
    except SyntaxError as syn_err:
        try:
            compiled = compile(expr_clean, "<eval>", "exec")
            is_statement = True
        except SyntaxError:
            # Genuine syntax error for both eval and exec modes
            snippet = ""
            if syn_err.text:
                snippet = generate_snippet(syn_err.text.splitlines(), syn_err.lineno or 1, syn_err.offset or 1)

            diag = (
                f"SyntaxError in expression: {syn_err.msg} (line {syn_err.lineno}, col {syn_err.offset}).\n"
                f"What is wrong: Python parser encountered invalid syntax near {repr(syn_err.text.strip()) if syn_err.text else 'token'}.\n"
                "Fix: Check for unbalanced parentheses, brackets, or unclosed string quotes. Ensure you passed a valid "
                "expression or statement."
            )
            if as_json:
                print(json.dumps({
                    "status": "error",
                    "mode": "eval",
                    "error_type": "SyntaxError",
                    "message": syn_err.msg,
                    "line": syn_err.lineno,
                    "column": syn_err.offset,
                    "diagnostic": diag,
                    "snippet": snippet,
                }, indent=2))
            else:
                print("=" * 80)
                print("✗ [code-oracle: eval] SyntaxError:")
                print(f"  Message: {syn_err.msg} (col {syn_err.offset})")
                if snippet:
                    print("  Snippet:")
                    for line in snippet.splitlines():
                        print(f"    {line}")
                print(f"\n  Fix: {diag}")
                print("=" * 80)
            return 1
        except (ValueError, RecursionError, MemoryError) as comp_err:
            err_type = type(comp_err).__name__
            diag = (
                f"{err_type} during compilation: {comp_err}.\n"
                "What is wrong: Python compiler encountered an internal limit or invalid character (e.g. null bytes, extreme nesting depth).\n"
                "Fix: Verify expression does not contain null bytes or excessive nesting depth."
            )
            if as_json:
                print(json.dumps({
                    "status": "error",
                    "mode": "eval",
                    "error_type": err_type,
                    "message": str(comp_err),
                    "diagnostic": diag,
                }, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: eval] Compilation {err_type}: {comp_err}")
                print(f"  Fix: {diag}")
                print("=" * 80)
            return 1
    except (ValueError, RecursionError, MemoryError) as comp_err:
        err_type = type(comp_err).__name__
        diag = (
            f"{err_type} during compilation: {comp_err}.\n"
            "What is wrong: Python compiler encountered an internal limit or invalid character (e.g. null bytes, extreme nesting depth).\n"
            "Fix: Verify expression does not contain null bytes or excessive nesting depth."
        )
        if as_json:
            print(json.dumps({
                "status": "error",
                "mode": "eval",
                "error_type": err_type,
                "message": str(comp_err),
                "diagnostic": diag,
            }, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: eval] Compilation {err_type}: {comp_err}")
            print(f"  Fix: {diag}")
            print("=" * 80)
        return 1

    # Prepare standard modules and safe evaluation environment
    eval_globals: Dict[str, Any] = {
        "__builtins__": sys.modules["builtins"].__dict__,
        "json": json,
        "re": re,
        "math": __import__("math"),
        "datetime": __import__("datetime"),
        "collections": __import__("collections"),
        "itertools": __import__("itertools"),
        "pathlib": pathlib,
        "unicodedata": unicodedata,
        "html": html,
        "sys": sys,
        "ast": ast,
    }
    eval_locals: Dict[str, Any] = {}

    # Set timer for timeout / infinite loop protection (5.0 seconds for heavy imports)
    timer_armed = False
    try:
        if hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer"):
            signal.signal(signal.SIGALRM, _eval_alarm_handler)
            signal.setitimer(signal.ITIMER_REAL, 5.0)
            timer_armed = True
    except Exception:
        pass

    try:
        if is_statement:
            exec(compiled, eval_globals, eval_locals)
            new_vars = {k: v for k, v in eval_locals.items() if not k.startswith("__")}
            val = new_vars if new_vars else "Statements executed successfully (no return value)."
        else:
            val = eval(compiled, eval_globals, eval_locals)
    except BaseException as exc:
        exc_type = type(exc).__name__
        exc_msg = str(exc)

        # Construct highly actionable diagnostic for LLM
        if isinstance(exc, (EvalTimeoutError, TimeoutError)):
            exc_type = "TimeoutError"
            action_fix = (
                "Execution timed out. "
                "What is wrong: An infinite loop or long-running computation was detected "
                "(e.g. while True, unbounded loop, or recursive generator). "
                "Fix: Verify loop termination conditions and generator bounds."
            )
        elif isinstance(exc, NameError):
            missing_name = getattr(exc, "name", None)
            if not missing_name:
                m = re.search(r"'([^']+)'", exc_msg)
                if m:
                    missing_name = m.group(1)

            candidates = list(eval_globals.keys()) + dir(__builtins__)
            suggestion = ""
            if missing_name:
                close = difflib.get_close_matches(missing_name, candidates, n=1, cutoff=0.6)
                if close:
                    suggestion = f" Did you mean '{close[0]}'?"

            if missing_name:
                action_fix = (
                    f"NameError: Identifier '{missing_name}' is not defined.{suggestion} "
                    f"What is wrong: The variable or function '{missing_name}' does not exist in the evaluation scope. "
                    f"Fix: Define '{missing_name}' before referencing it, check for typos, or verify if it requires "
                    f"importing a module (e.g. math, sys, os, json)."
                )
            else:
                action_fix = (
                    f"NameError: {exc_msg}. "
                    "What is wrong: An identifier was referenced before being defined. "
                    "Fix: Check for misspelled variable or function names, or import the required module."
                )
        elif isinstance(exc, MemoryError):
            action_fix = (
                "MemoryError: Out of memory during expression evaluation. "
                "What is wrong: The expression attempted to allocate more memory than available. "
                "Fix: Reduce data structure size or use iterators/generators instead of large lists."
            )
        elif isinstance(exc, RecursionError):
            action_fix = (
                "RecursionError: Maximum recursion depth exceeded. "
                "What is wrong: Unbounded or excessively deep recursion was detected. "
                "Fix: Add or check recursive base cases to ensure recursion terminates."
            )
        elif isinstance(exc, ZeroDivisionError):
            action_fix = (
                "ZeroDivisionError: Division or modulo by zero. "
                "What is wrong: An arithmetic operation divided by zero. "
                "Fix: Add a check for zero before dividing or handle denominator == 0."
            )
        elif isinstance(exc, TypeError):
            action_fix = (
                f"TypeError: {exc_msg}. "
                "What is wrong: An invalid type or argument count was passed to an operation or function. "
                "Fix: Verify argument types and function signatures."
            )
        elif isinstance(exc, ValueError):
            action_fix = (
                f"ValueError: {exc_msg}. "
                "What is wrong: An invalid value was passed to a function or operation. "
                "Fix: Check argument formats, ranges, or numeric conversions."
            )
        elif isinstance(exc, KeyError):
            action_fix = (
                f"KeyError: {exc_msg}. "
                "What is wrong: The dictionary key does not exist. "
                "Fix: Check dictionary keys with .keys() or use .get() with a default value."
            )
        elif isinstance(exc, IndexError):
            action_fix = (
                f"IndexError: {exc_msg}. "
                "What is wrong: Sequence index out of range. "
                "Fix: Check sequence length with len() before indexing."
            )
        elif isinstance(exc, AttributeError):
            action_fix = (
                f"AttributeError: {exc_msg}. "
                "What is wrong: The requested attribute or method does not exist on this object. "
                "Fix: Check attribute names with dir() or check for typos."
            )
        elif isinstance(exc, SystemExit):
            action_fix = (
                "SystemExit: Expression attempted to exit the Python process. "
                "What is wrong: sys.exit() was called during evaluation. "
                "Fix: Do not call sys.exit() inside an evaluated expression."
            )
        else:
            action_fix = f"Runtime error during eval(): {exc_type}: {exc_msg}."

        if as_json:
            print(json.dumps({
                "status": "error",
                "mode": "eval",
                "error_type": exc_type,
                "message": exc_msg,
                "diagnostic": action_fix,
            }, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: eval] Runtime {exc_type}:")
            print(f"  Message: {exc_msg}")
            print(f"  Fix:     {action_fix}")
            print("=" * 80)
        return 1
    finally:
        if timer_armed:
            try:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, signal.SIG_DFL)
            except Exception:
                pass

    val_type = type(val).__name__
    val_repr = repr(val)
    val_str = str(val)

    val_len: Optional[int] = None
    try:
        val_len = len(val)  # type: ignore
    except TypeError:
        val_len = None

    if as_json:
        res = {
            "status": "ok",
            "mode": "eval",
            "expression": expr,
            "type": val_type,
            "repr": val_repr,
            "formatted": val_str,
            "len": val_len,
        }
        print(json.dumps(res, indent=2))
    else:
        print("=" * 80)
        print("✓ [code-oracle: eval] Evaluation Successful:")
        print(f"  Expression : {expr}")
        print(f"  Type       : {val_type}")
        print(f"  Repr       : {val_repr}")
        print(f"  Length     : {val_len if val_len is not None else 'N/A (not sized)'}")
        print(f"  Formatted  : {val_str}")
        print("=" * 80)

    return 0


# ==============================================================================
# Mode 2: --hex <text>
# ==============================================================================

SGR_CODES: Dict[str, str] = {
    "0": "Reset / Normal",
    "1": "Bold / Increased Intensity",
    "2": "Faint / Decreased Intensity",
    "3": "Italic",
    "4": "Underline",
    "7": "Reverse Video",
    "9": "Strikethrough",
    "22": "Normal Intensity (Not Bold/Faint)",
    "23": "Not Italic",
    "24": "Not Underlined",
    "27": "Not Reversed",
    "29": "Not Strikethrough",
    "30": "FG Black", "31": "FG Red", "32": "FG Green", "33": "FG Yellow",
    "34": "FG Blue", "35": "FG Magenta", "36": "FG Cyan", "37": "FG White",
    "39": "FG Default",
    "40": "BG Black", "41": "BG Red", "42": "BG Green", "43": "BG Yellow",
    "44": "BG Blue", "45": "BG Magenta", "46": "BG Cyan", "47": "BG White",
    "49": "BG Default",
    "90": "FG Bright Black (Gray)", "91": "FG Bright Red", "92": "FG Bright Green",
    "93": "FG Bright Yellow", "94": "FG Bright Blue", "95": "FG Bright Magenta",
    "96": "FG Bright Cyan", "97": "FG Bright White",
    "100": "BG Bright Black", "101": "BG Bright Red", "102": "BG Bright Green",
    "103": "BG Bright Yellow", "104": "BG Bright Blue", "105": "BG Bright Magenta",
    "106": "BG Bright Cyan", "107": "BG Bright White",
}


def parse_sgr_params(params_str: str) -> List[str]:
    """Parse SGR parameter string into human-readable descriptions."""
    if not params_str:
        return ["Reset / Normal (default 0)"]
    tokens = params_str.split(";")
    res: List[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ("38", "48") and i + 1 < len(tokens):
            target = "FG" if t == "38" else "BG"
            mode = tokens[i + 1]
            if mode == "5" and i + 2 < len(tokens):
                color_idx = tokens[i + 2]
                res.append(f"{target} 256-color (#{color_idx})")
                i += 3
                continue
            elif mode == "2" and i + 4 < len(tokens):
                r, g, b = tokens[i + 2], tokens[i + 3], tokens[i + 4]
                res.append(f"{target} TrueColor RGB({r}, {g}, {b})")
                i += 5
                continue
        desc = SGR_CODES.get(t, f"Code {t}")
        res.append(desc)
        i += 1
    return res


def run_hex(input_val: str, as_json: bool = False) -> int:
    """Hex dump and escape sequence inspector."""
    stripped_val = input_val.strip()
    if stripped_val and "\n" not in stripped_val and len(stripped_val) < 256:
        p = pathlib.Path(stripped_val)
        if (p.suffix in (".txt", ".log", ".dat", ".bin", ".out", ".diff", ".patch", ".raw") or "/" in stripped_val) and not p.exists():
            err_msg = f"File '{stripped_val}' not found."
            diag = (
                f"File '{stripped_val}' does not exist on disk.\n"
                "What is wrong: Specified file path could not be located.\n"
                "Fix: Check file path relative to workspace or pass text directly: python3 oracle.py --hex $'\\x1b[31mText\\x1b[0m'"
            )
            if as_json:
                print(json.dumps({"status": "error", "mode": "hex", "error_type": "FileNotFoundError", "error": err_msg, "diagnostic": diag}, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: hex] {err_msg}")
                print(f"  {diag}")
                print("=" * 80)
            return 1

    text = read_input_text(input_val)
    raw_bytes = text.encode("utf-8")

    # 1. Generate Hex Dump
    hex_dump_lines: List[str] = []
    for offset in range(0, len(raw_bytes), 16):
        chunk = raw_bytes[offset : offset + 16]
        hex_parts: List[str] = [f"{b:02x}" for b in chunk]
        first_half = " ".join(hex_parts[:8])
        second_half = " ".join(hex_parts[8:])
        hex_col = f"{first_half:<23}  {second_half:<23}".rstrip()

        ascii_col = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        hex_dump_lines.append(f"{offset:08x}  {hex_col:<48}  |{ascii_col}|")

    # 2. Inspect Escape Sequences, Invisible Characters, and Controls
    ansi_sequences: List[Dict[str, Any]] = []
    for match in ANSI_RE.finditer(text):
        seq = match.group(0)
        start, end = match.span()
        kind = "Unknown"
        details: List[str] = []
        if seq.startswith("\x1b["):
            kind = "CSI (Control Sequence Introducer)"
            terminator = seq[-1]
            params = seq[2:-1]
            if terminator == "m":
                kind = "CSI SGR (Select Graphic Rendition)"
                details = parse_sgr_params(params)
            elif terminator == "H":
                kind = "CSI Cursor Position"
            elif terminator == "J":
                kind = "CSI Erase Display"
            elif terminator == "K":
                kind = "CSI Erase in Line"
        elif seq.startswith("\x1b]"):
            kind = "OSC (Operating System Command)"
            if seq.startswith("\x1b]8;;"):
                kind = "OSC 8 Hyperlink"
                url = seq[5:].rstrip("\x07\x1b\\")
                details = [f"Hyperlink Target: {url}"]

        ansi_sequences.append({
            "raw": repr(seq),
            "start": start,
            "end": end,
            "kind": kind,
            "details": details,
        })

    # Inspect invisible and special control characters
    special_chars: List[Dict[str, Any]] = []
    for idx, ch in enumerate(text):
        cp = ord(ch)
        cat = unicodedata.category(ch)
        name = unicodedata.name(ch, "<unnamed>")

        is_special = False
        note = ""

        if ch == "\r":
            is_special = True
            is_followed_by_n = (idx + 1 < len(text) and text[idx + 1] == "\n")
            note = "Carriage Return (CR)" + (" [CRLF pair]" if is_followed_by_n else " [Lone CR - can overwrite line!]")
        elif ch == "\n":
            is_special = True
            note = "Line Feed (LF)"
        elif ch == "\t":
            is_special = True
            note = "Horizontal Tab"
        elif ch == "\u200b":
            is_special = True
            note = "Zero-Width Space (invisible)"
        elif ch == "\u200c":
            is_special = True
            note = "Zero-Width Non-Joiner (ZWNJ)"
        elif ch == "\u200d":
            is_special = True
            note = "Zero-Width Joiner (ZWJ - joins emojis/glyphs)"
        elif ch == "\ufe0e":
            is_special = True
            note = "Variation Selector-15 (text presentation)"
        elif ch == "\ufe0f":
            is_special = True
            note = "Variation Selector-16 (emoji presentation)"
        elif ch == "\ufeff":
            is_special = True
            note = "Zero-Width No-Break Space / Byte Order Mark (BOM)"
        elif ch in ("\u200e", "\u200f"):
            is_special = True
            note = "BiDi Directional Mark (LRM/RLM)"
        elif cat.startswith("C") and cp not in (9, 10, 13):
            is_special = True
            note = f"Control / Format character ({cat})"

        if is_special:
            special_chars.append({
                "index": idx,
                "char": repr(ch),
                "codepoint": f"U+{cp:04X}",
                "name": name,
                "category": cat,
                "note": note,
            })

    # Diagnostics
    diagnostics: List[str] = []
    has_sgr = any("SGR" in s["kind"] for s in ansi_sequences)
    has_reset = any("0" in s["raw"] or "Reset" in " ".join(s["details"]) for s in ansi_sequences)
    if has_sgr and not has_reset:
        diagnostics.append(
            "Unclosed ANSI sequence detected: Formatting enabled without a reset code (\\x1b[0m). "
            "Colors or styles will bleed into subsequent terminal output or test runners."
        )

    lone_cr = [sc for sc in special_chars if "Lone CR" in sc["note"]]
    if lone_cr:
        diagnostics.append(
            f"Detected {len(lone_cr)} lone Carriage Return (\\r) character(s) without \\n. "
            "In terminals, lone \\r moves the cursor to column 0 and overwrites previous text."
        )

    zw_chars = [sc for sc in special_chars if "Zero-Width" in sc["note"]]
    if zw_chars:
        diagnostics.append(
            f"Detected {len(zw_chars)} invisible zero-width character(s) (e.g. {zw_chars[0]['codepoint']}). "
            "These characters are invisible to human inspection but will cause str == expected or len() checks to fail."
        )

    if as_json:
        out = {
            "status": "ok",
            "mode": "hex",
            "total_bytes": len(raw_bytes),
            "total_chars": len(text),
            "hex_dump": hex_dump_lines,
            "ansi_sequences": ansi_sequences,
            "special_characters": special_chars,
            "diagnostics": diagnostics,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        print("✓ [code-oracle: hex] Hex Dump & Escape Sequence Inspection:")
        print(f"  Total Bytes : {len(raw_bytes)} | Total Characters: {len(text)}")
        print("\n--- HEX DUMP ---")
        for line in hex_dump_lines[:64]:
            print(line)
        if len(hex_dump_lines) > 64:
            print(f"  ... and {len(hex_dump_lines) - 64} more line(s) ({len(raw_bytes) - 1024} bytes; pass --json to view full dump)")

        if ansi_sequences:
            print(f"\n--- ANSI ESCAPE SEQUENCES ({len(ansi_sequences)} found) ---")
            for seq in ansi_sequences:
                det = f" -> {', '.join(seq['details'])}" if seq["details"] else ""
                print(f"  [{seq['start']}:{seq['end']}] {seq['kind']}: {seq['raw']}{det}")

        if special_chars:
            print(f"\n--- INVISIBLE & CONTROL CHARACTERS ({len(special_chars)} found) ---")
            for sc in special_chars:
                print(f"  Index {sc['index']:<4} | {sc['codepoint']} | {sc['name']:<25} | {sc['note']}")

        if diagnostics:
            print("\n--- ACTIONABLE DIAGNOSTICS ---")
            for diag in diagnostics:
                print(f"  ⚠ {diag}")

        print("=" * 80)

    return 0


# ==============================================================================
# Mode 3: --width <text>
# ==============================================================================

def get_char_display_width(ch: str) -> int:
    """Calculate monospaced cell display width of a single character."""
    o = ord(ch)
    cat = unicodedata.category(ch)

    # Combining characters and format marks occupy 0 terminal cells
    if cat in ("Mn", "Me", "Mc", "Cf", "Cc"):
        return 0

    # Skin tone modifiers (U+1F3FB - U+1F3FF) combine with previous emoji
    if 0x1F3FB <= o <= 0x1F3FF:
        return 0

    # East Asian Width Fullwidth (F) and Wide (W) occupy 2 cells
    ea = unicodedata.east_asian_width(ch)
    if ea in ("W", "F"):
        return 2

    # Common emoji ranges occupy 2 cells in monospaced terminal emulators
    if (0x1F300 <= o <= 0x1FAFF) or (0x2600 <= o <= 0x27BF):
        return 2

    return 1


def calculate_terminal_cells(text: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Calculate exact monospaced terminal columns and character-by-character breakdown."""
    clean_text = ANSI_RE.sub("", text)

    breakdown: List[Dict[str, Any]] = []
    total_width = 0
    i = 0
    n = len(clean_text)

    while i < n:
        ch = clean_text[i]
        o = ord(ch)
        cat = unicodedata.category(ch)
        ea = unicodedata.east_asian_width(ch)
        name = unicodedata.name(ch, "<unnamed>")

        # Handle ZWJ sequence: if current char is ZWJ, it and following emoji contribute 0 extra width
        if ch == "\u200d":
            breakdown.append({
                "char": repr(ch),
                "codepoint": f"U+{o:04X}",
                "name": name,
                "category": cat,
                "ea_width": ea,
                "cell_width": 0,
                "note": "Zero-Width Joiner (joins with adjacent glyph)",
            })
            i += 1
            if i < n:
                next_ch = clean_text[i]
                next_o = ord(next_ch)
                breakdown.append({
                    "char": repr(next_ch),
                    "codepoint": f"U+{next_o:04X}",
                    "name": unicodedata.name(next_ch, "<unnamed>"),
                    "category": unicodedata.category(next_ch),
                    "ea_width": unicodedata.east_asian_width(next_ch),
                    "cell_width": 0,
                    "note": "Joined emoji sequence component",
                })
                i += 1
            continue

        base_width = get_char_display_width(ch)

        # Check if immediately followed by emoji presentation selector \ufe0f
        if i + 1 < n and clean_text[i + 1] == "\ufe0f":
            effective_width = max(base_width, 2)
            total_width += effective_width
            breakdown.append({
                "char": repr(ch),
                "codepoint": f"U+{o:04X}",
                "name": name,
                "category": cat,
                "ea_width": ea,
                "cell_width": effective_width,
                "note": "Base symbol (presented as emoji width 2 via \\ufe0f)",
            })
            i += 1
            vs_o = ord(clean_text[i])
            breakdown.append({
                "char": repr(clean_text[i]),
                "codepoint": f"U+{vs_o:04X}",
                "name": unicodedata.name(clean_text[i], "<unnamed>"),
                "category": unicodedata.category(clean_text[i]),
                "ea_width": unicodedata.east_asian_width(clean_text[i]),
                "cell_width": 0,
                "note": "Variation Selector-16 (emoji presentation)",
            })
            i += 1
            continue

        total_width += base_width
        breakdown.append({
            "char": repr(ch),
            "codepoint": f"U+{o:04X}",
            "name": name,
            "category": cat,
            "ea_width": ea,
            "cell_width": base_width,
            "note": "Wide cell" if base_width == 2 else ("Zero width" if base_width == 0 else "Normal cell"),
        })
        i += 1

    return total_width, breakdown


def run_width(input_val: str, as_json: bool = False) -> int:
    """Calculates exact terminal cell display width for monospaced terminals."""
    text = read_input_text(input_val)

    code_points = len(text)
    utf8_bytes = len(text.encode("utf-8"))
    utf16_units = len(text.encode("utf-16-le")) // 2
    columns, breakdown = calculate_terminal_cells(text)

    # Actionable character-level diagnostics if columns != code_points
    diagnostics: List[str] = []
    char_explanations: List[str] = []
    if columns != code_points:
        reasons: List[str] = []
        wide_items = [b for b in breakdown if b["cell_width"] == 2]
        zero_items = [b for b in breakdown if b["cell_width"] == 0]
        ansi_matches = list(ANSI_RE.finditer(text))

        if wide_items:
            reasons.append(f"{len(wide_items)} wide character(s) (CJK/emoji = 2 cells)")
            for item in wide_items[:10]:
                char_explanations.append(
                    f"Character {item['char']} ({item['codepoint']}) occupies 2 terminal cells, whereas len() is 1."
                )
            if len(wide_items) > 10:
                char_explanations.append(f"... and {len(wide_items) - 10} more wide character(s)")

        if zero_items:
            reasons.append(f"{len(zero_items)} zero-width / combining / ZWJ character(s) (0 cells)")
            for item in zero_items[:10]:
                char_explanations.append(
                    f"Character {item['char']} ({item['codepoint']}) occupies 0 terminal cells, whereas len() is 1."
                )
            if len(zero_items) > 10:
                char_explanations.append(f"... and {len(zero_items) - 10} more zero-width character(s)")

        if ansi_matches:
            reasons.append(f"{len(ansi_matches)} ANSI escape sequence(s) (stripped in display = 0 cells)")
            for m in ansi_matches[:5]:
                esc_str = m.group(0)
                char_explanations.append(
                    f"ANSI escape sequence {repr(esc_str)} occupies 0 terminal cells, whereas len() is {len(esc_str)}."
                )

        diagnostics.append(
            f"Terminal display columns ({columns}) differs from Python len() ({code_points}) due to: "
            + "; ".join(reasons) + "."
        )
        diagnostics.extend(char_explanations)
        diagnostics.append(
            "Actionable Fix: In CLI/TUI tools (Rich, prompt_toolkit, table formatters), DO NOT use "
            "len(), str.ljust(), or str.rjust() to align columns. Use cell width (e.g. rich.cells.cell_len() "
            "or wcwidth) to prevent ragged borders and table misalignment."
        )

    if as_json:
        out = {
            "status": "ok",
            "mode": "width",
            "terminal_columns": columns,
            "len_code_points": code_points,
            "utf8_bytes": utf8_bytes,
            "utf16_units": utf16_units,
            "breakdown": breakdown,
            "diagnostics": diagnostics,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        print("✓ [code-oracle: width] Terminal Cell Display Width:")
        print(f"  Terminal Columns : {columns}")
        print(f"  len(text)        : {code_points} (Unicode code points)")
        print(f"  UTF-8 Bytes      : {utf8_bytes}")
        print(f"  UTF-16 Units     : {utf16_units}")

        if breakdown:
            print("\n--- CHARACTER / GLYPH BREAKDOWN ---")
            print(f"  {'Char':<8} {'CodePoint':<10} {'Width':<7} {'EA':<4} {'Cat':<5} {'Name / Note'}")
            print("  " + "-" * 74)
            for item in breakdown[:50]:
                print(f"  {item['char']:<8} {item['codepoint']:<10} {item['cell_width']:<7} {item['ea_width']:<4} {item['category']:<5} {item['name']} ({item['note']})")
            if len(breakdown) > 50:
                print(f"  ... and {len(breakdown) - 50} more character(s)")

        if char_explanations:
            print("\n--- CHARACTER-LEVEL CELL WIDTH EXPLANATIONS ---")
            for exp in char_explanations:
                print(f"  • {exp}")

        if diagnostics:
            print("\n--- ACTIONABLE DIAGNOSTICS ---")
            for diag in diagnostics:
                print(f"  ℹ {diag}")

        print("=" * 80)

    return 0


# ==============================================================================
# Mode 4: --html-esc <snippet>
# ==============================================================================

class HTMLStructureParser(HTMLParser):
    """HTML Parser that checks tag nesting balance and attribute escaping."""

    def __init__(self):
        super().__init__()
        self.tag_stack: List[Tuple[str, int, int]] = []
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.inside_script: bool = False
        self.inside_style: bool = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        t = tag.lower()
        lineno, offset = self.getpos()

        # Check attribute values for unescaped characters
        for attr_name, attr_val in attrs:
            if attr_val is not None:
                if "<" in attr_val:
                    self.warnings.append({
                        "line": lineno,
                        "column": offset,
                        "kind": "UnescapedAngleBracketInAttribute",
                        "message": f"Attribute '{attr_name}' contains raw '<': {attr_val!r}. "
                                   "Fix: Replace '<' with '&lt;' in attribute values.",
                    })
                if ">" in attr_val:
                    self.warnings.append({
                        "line": lineno,
                        "column": offset,
                        "kind": "UnescapedAngleBracketInAttribute",
                        "message": f"Attribute '{attr_name}' contains raw '>': {attr_val!r}. "
                                   "Fix: Replace '>' with '&gt;' in attribute values.",
                    })
                # Check for raw ampersands not part of a valid HTML entity in attributes
                raw_amp = re.findall(r"&(?!([a-zA-Z][a-zA-Z0-9]*|#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6});)", attr_val)
                if raw_amp:
                    self.warnings.append({
                        "line": lineno,
                        "column": offset,
                        "kind": "UnescapedAmpersandInAttribute",
                        "message": f"Attribute '{attr_name}' contains unescaped '&': {attr_val!r}. "
                                   "Fix: Replace raw '&' with '&amp;'.",
                    })

        if t == "script":
            self.inside_script = True
        elif t == "style":
            self.inside_style = True

        if t not in VOID_HTML_TAGS:
            self.tag_stack.append((t, lineno, offset))

    def handle_endtag(self, tag: str):
        t = tag.lower()
        lineno, offset = self.getpos()

        if t == "script":
            self.inside_script = False
        elif t == "style":
            self.inside_style = False

        if t in VOID_HTML_TAGS:
            self.warnings.append({
                "line": lineno,
                "column": offset,
                "kind": "VoidTagClosed",
                "message": f"Void element <{t}> should not have a closing </{t}> tag.",
            })
            return

        if not self.tag_stack:
            self.errors.append({
                "line": lineno,
                "column": offset,
                "kind": "UnmatchedClosingTag",
                "message": f"Found closing tag </{t}> with no corresponding opening tag. Fix: Remove extra </{t}> or add opening <{t}>.",
            })
            return

        top_tag, top_line, top_col = self.tag_stack[-1]
        if top_tag == t:
            self.tag_stack.pop()
        else:
            stack_tags = [item[0] for item in self.tag_stack]
            if t in stack_tags:
                idx = len(stack_tags) - 1 - stack_tags[::-1].index(t)
                unclosed = self.tag_stack[idx + 1 :]
                unclosed_names = ", ".join(f"<{item[0]} line {item[1]}>" for item in unclosed)
                self.errors.append({
                    "line": lineno,
                    "column": offset,
                    "kind": "MisnestedTag",
                    "message": f"Closing tag </{t}> closes element out of order. Unclosed inner elements: {unclosed_names}. Fix: Close inner elements first.",
                })
                self.tag_stack = self.tag_stack[:idx]
            else:
                self.errors.append({
                    "line": lineno,
                    "column": offset,
                    "kind": "UnmatchedClosingTag",
                    "message": f"Closing tag </{t}> does not match current open element <{top_tag} line {top_line}>. Fix: Ensure tags are properly closed.",
                })

    def handle_data(self, data: str):
        lineno, offset = self.getpos()
        if self.inside_script:
            if "<" in data or ">" in data:
                ch = "<" if "<" in data else ">"
                esc_ch = r"\u003c" if ch == "<" else r"\u003e"
                self.warnings.append({
                    "line": lineno,
                    "column": offset,
                    "kind": "RawScriptAngleBrackets",
                    "message": f"Raw '{ch}' detected inside <script> block. "
                               f"Fix: Escape as '{esc_ch}' in templates (Swagger UI/Redoc) "
                               "to prevent premature script termination or XSS.",
                })


def run_html_esc(input_val: str, as_json: bool = False) -> int:
    """Inspects HTML/template strings for entity escaping and tag balance."""
    raw_html = read_input_text(input_val)
    lines = raw_html.splitlines()

    parser = HTMLStructureParser()
    try:
        parser.feed(raw_html)
        parser.close()
    except BaseException as exc:
        parser.errors.append({
            "line": 1,
            "column": 1,
            "kind": "ParserFailure",
            "message": f"HTML parser encountered exception: {exc}. Fix: Check for unbalanced quotes or malformed markup.",
        })

    # Check for remaining unclosed tags at EOF
    if parser.tag_stack:
        for tag, line, col in parser.tag_stack:
            parser.errors.append({
                "line": line,
                "column": col,
                "kind": "UnclosedTag",
                "message": f"Tag <{tag}> opened at line {line} col {col} was never closed before end of document. "
                           f"Fix: Add closing tag </{tag}>.",
            })

    # Scan for raw unescaped ampersands in text (outside valid HTML entities)
    raw_amp_pattern = re.compile(r"&(?!([a-zA-Z][a-zA-Z0-9]*|#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6});)")
    for line_idx, line_str in enumerate(lines, 1):
        for m in raw_amp_pattern.finditer(line_str):
            col = m.start() + 1
            snippet = generate_snippet(lines, line_idx, col, context_lines=1)
            parser.errors.append({
                "line": line_idx,
                "column": col,
                "kind": "UnescapedAmpersand",
                "message": f"Unescaped '&' found at line {line_idx} col {col}. "
                           "Fix: Replace '&' with '&amp;' or use html.escape().",
                "snippet": snippet,
            })

    status_passed = len(parser.errors) == 0

    if as_json:
        out = {
            "status": "passed" if status_passed else "failed",
            "mode": "html-esc",
            "errors": parser.errors,
            "warnings": parser.warnings,
            "total_errors": len(parser.errors),
            "total_warnings": len(parser.warnings),
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        if status_passed and not parser.warnings:
            print("✓ [code-oracle: html-esc] HTML validation clean: all tags balanced & entities escaped.")
        else:
            header = "✗ [code-oracle: html-esc] HTML issues detected:" if not status_passed else "⚠ [code-oracle: html-esc] HTML warnings:"
            print(header)
            # Cap displayed errors at 25 items to prevent flooding on giant files
            for err in parser.errors[:25]:
                print(f"\n  [ERROR] {err['kind']} (line {err['line']}, col {err['column']}):")
                print(f"    {err['message']}")
                if "snippet" in err and err["snippet"]:
                    for s_line in err["snippet"].splitlines():
                        print(f"      {s_line}")
            if len(parser.errors) > 25:
                print(f"\n  ... and {len(parser.errors) - 25} more error(s)")

            for warn in parser.warnings[:25]:
                print(f"\n  [WARN] {warn['kind']} (line {warn['line']}, col {warn['column']}):")
                print(f"    {warn['message']}")
            if len(parser.warnings) > 25:
                print(f"\n  ... and {len(parser.warnings) - 25} more warning(s)")

            print("\nActionable Fixes for SWE Agent:")
            print("  1. Ensure every non-void opening tag has a matching closing tag.")
            print("  2. Replace unescaped '&' with '&amp;' and '<' with '&lt;'.")
            print("  3. Inside script/JSON templates (Swagger UI / Redoc), escape '<' as '\\u003c'.")
        print("=" * 80)

    return 0 if status_passed else 1


# ==============================================================================
# Mode 5: --schema <file_or_json>
# ==============================================================================

def resolve_json_pointer(root: Any, pointer: str) -> Tuple[bool, Any, str]:
    """Resolve a local JSON Pointer against the root document."""
    if not pointer.startswith("#"):
        return False, None, f"Non-local pointer '{pointer}' (external references not resolvable offline)"

    if pointer in ("#", "#/"):
        return True, root, ""

    if not pointer.startswith("#/"):
        return False, None, f"Malformed pointer '{pointer}' (must start with '#/')"

    tokens = pointer[2:].split("/")
    curr = root
    traversed: List[str] = ["#"]

    for token in tokens:
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(curr, dict):
            if key in curr:
                curr = curr[key]
                traversed.append(key)
            else:
                curr_path = "/".join(traversed)
                available = ", ".join(repr(k) for k in list(curr.keys())[:10])
                return False, None, f"Key '{key}' not found at '{curr_path}'. Available keys: [{available}]"
        elif isinstance(curr, list):
            if key.isdigit() and int(key) < len(curr):
                curr = curr[int(key)]
                traversed.append(key)
            else:
                curr_path = "/".join(traversed)
                return False, None, f"Index '{key}' out of range at '{curr_path}' (length {len(curr)})"
        else:
            curr_path = "/".join(traversed)
            return False, None, f"Cannot traverse into primitive {type(curr).__name__} at '{curr_path}'"

    return True, curr, ""


def find_all_definition_targets(root: Any) -> Dict[str, str]:
    """Find all declared definition target names and their canonical pointer paths."""
    targets: Dict[str, str] = {}
    if not isinstance(root, dict):
        return targets

    if "$defs" in root and isinstance(root["$defs"], dict):
        for name in root["$defs"].keys():
            targets[name] = f"#/$defs/{name}"

    if "definitions" in root and isinstance(root["definitions"], dict):
        for name in root["definitions"].keys():
            targets[name] = f"#/definitions/{name}"

    if "components" in root and isinstance(root["components"], dict):
        schemas = root["components"].get("schemas")
        if isinstance(schemas, dict):
            for name in schemas.keys():
                targets[name] = f"#/components/schemas/{name}"

    return targets


def inspect_schema_tree(root: Any) -> Dict[str, Any]:
    """Recursively inspect JSON Schema / OpenAPI structure with recursion cycle protection."""
    all_refs: List[Dict[str, Any]] = []
    dangling_refs: List[Dict[str, Any]] = []
    dialect_warnings: List[str] = []
    anyof_issues: List[Dict[str, Any]] = []
    type_health_issues: List[Dict[str, Any]] = []

    has_defs = "$defs" in root if isinstance(root, dict) else False
    has_definitions = "definitions" in root if isinstance(root, dict) else False
    openapi_version = root.get("openapi", "") if isinstance(root, dict) else ""
    json_schema_draft = root.get("$schema", "") if isinstance(root, dict) else ""

    if has_defs and has_definitions:
        dialect_warnings.append(
            "Schema root defines BOTH '$defs' and 'definitions'. Standardize on '$defs' (OpenAPI 3.1 / JSON Schema 2020-12) "
            "or 'definitions' (OpenAPI 3.0 / Draft 7) to prevent reference resolution ambiguity."
        )

    if openapi_version.startswith("3.0") and has_defs:
        dialect_warnings.append(
            f"OpenAPI version is {openapi_version} but uses '$defs'. OpenAPI 3.0 uses 'components/schemas' or 'definitions'. "
            "Pydantic v2 schemas use '$defs' by default; ensure FastAPI / OpenAPI generator adapts dialect."
        )
    elif openapi_version.startswith("3.1") and has_definitions and not has_defs:
        dialect_warnings.append(
            f"OpenAPI version is {openapi_version} (OpenAPI 3.1) but uses legacy 'definitions' instead of '$defs'."
        )

    # Collect all available definition targets to provide exact corrected reference paths
    known_targets = find_all_definition_targets(root)

    # Cycle protection tracking object IDs; iterative stack avoids RecursionError
    seen_ids: Set[int] = set()
    stack: List[Tuple[Any, str]] = [(root, "#")]

    while stack:
        obj, path = stack.pop()
        if id(obj) in seen_ids:
            continue
        seen_ids.add(id(obj))

        if isinstance(obj, dict):
            # Check $ref
            if "$ref" in obj and isinstance(obj["$ref"], str):
                ref_val = obj["$ref"]
                all_refs.append({"location": path, "target": ref_val})
                ok, _, err_msg = resolve_json_pointer(root, ref_val)
                if not ok:
                    # Provide exact corrected reference path
                    target_name = ref_val.rsplit("/", 1)[-1] if "/" in ref_val else ref_val.lstrip("#")
                    hint = ""
                    if target_name in known_targets:
                        correct_path = known_targets[target_name]
                        hint = f" Did you mean '{correct_path}'? Target is defined at '{correct_path}'."
                    else:
                        # Case-insensitive or closest match
                        lower_targets = {k.lower(): v for k, v in known_targets.items()}
                        if target_name.lower() in lower_targets:
                            correct_path = lower_targets[target_name.lower()]
                            hint = f" Did you mean '{correct_path}' (case mismatch)?"
                        elif known_targets:
                            close = difflib.get_close_matches(target_name, list(known_targets.keys()), n=1, cutoff=0.5)
                            if close:
                                correct_path = known_targets[close[0]]
                                hint = f" Did you mean '{correct_path}' (closest match)?"

                    dangling_refs.append({
                        "location": path,
                        "target": ref_val,
                        "error": err_msg + hint,
                    })

            # Check anyOf
            if "anyOf" in obj and isinstance(obj["anyOf"], list):
                has_null_type = False
                has_string_none = False
                for item in obj["anyOf"]:
                    if isinstance(item, dict):
                        item_type = item.get("type")
                        if item_type == "null":
                            has_null_type = True
                        elif item_type == "None" or (item_type is None and "None" in str(item)):
                            has_string_none = True

                if has_string_none:
                    anyof_issues.append({
                        "location": path,
                        "message": "anyOf contains 'None' as type or literal. In JSON Schema, nullability MUST be {'type': 'null'}.",
                    })

                if obj.get("nullable") is True and has_null_type:
                    anyof_issues.append({
                        "location": path,
                        "message": "Schema defines both 'nullable: true' and anyOf: [{'type': 'null'}]. "
                                   "OpenAPI 3.0 uses 'nullable: true'; OpenAPI 3.1 uses 'type: null'. Combining both is redundant/conflicting.",
                    })

            # Check type validity
            if "type" in obj:
                t_val = obj["type"]
                if isinstance(t_val, str):
                    if t_val not in VALID_JSON_SCHEMA_TYPES:
                        type_health_issues.append({
                            "location": path,
                            "invalid_type": t_val,
                            "message": f"Invalid type '{t_val}'. Must be one of {sorted(VALID_JSON_SCHEMA_TYPES)}. "
                                       "Check for Python type leaks (e.g. 'str' -> 'string', 'int' -> 'integer', 'dict' -> 'object').",
                        })
                elif isinstance(t_val, list):
                    for sub_t in t_val:
                        if sub_t not in VALID_JSON_SCHEMA_TYPES:
                            type_health_issues.append({
                                "location": path,
                                "invalid_type": sub_t,
                                "message": f"Invalid type '{sub_t}' in type union array. Must be one of {sorted(VALID_JSON_SCHEMA_TYPES)}.",
                            })

            # Check required list vs properties
            if "required" in obj and isinstance(obj["required"], list) and "properties" in obj and isinstance(obj["properties"], dict):
                props = set(obj["properties"].keys())
                for req in obj["required"]:
                    if isinstance(req, str) and req not in props:
                        type_health_issues.append({
                            "location": path,
                            "message": f"Property '{req}' listed in 'required' is not defined in 'properties'.",
                        })

            # Push children to stack (reversed to preserve document order)
            for k, v in reversed(list(obj.items())):
                stack.append((v, f"{path}/{k}"))

        elif isinstance(obj, list):
            for idx in reversed(range(len(obj))):
                stack.append((obj[idx], f"{path}/{idx}"))

    return {
        "openapi_version": openapi_version,
        "json_schema_draft": json_schema_draft,
        "definitions_container": "$defs" if has_defs else ("definitions" if has_definitions else "none"),
        "total_refs": len(all_refs),
        "dangling_refs": dangling_refs,
        "dialect_warnings": dialect_warnings,
        "anyof_issues": anyof_issues,
        "type_health_issues": type_health_issues,
    }


def run_schema(input_val: str, as_json: bool = False) -> int:
    """Inspects JSON Schema / OpenAPI schema structure."""
    stripped = input_val.strip()
    if stripped and not stripped.startswith(("{", "[")) and (stripped.endswith((".json", ".yaml", ".yml")) or "/" in stripped):
        p = pathlib.Path(stripped)
        if not p.is_file():
            diag = (
                f"File '{stripped}' not found.\n"
                "What is wrong: The specified schema file does not exist on disk.\n"
                "Fix: Check file path relative to workspace or pass inline JSON: python3 oracle.py --schema '{\"type\": \"object\"}'"
            )
            if as_json:
                print(json.dumps({"status": "error", "mode": "schema", "error_type": "FileNotFoundError", "error": f"File '{stripped}' not found.", "diagnostic": diag}, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: schema] File '{stripped}' not found.")
                print(f"  {diag}")
                print("=" * 80)
            return 1

    text = read_input_text(input_val)
    if not text.strip():
        diag = "No schema content provided to --schema."
        if as_json:
            print(json.dumps({"status": "error", "mode": "schema", "error": diag}, indent=2))
        else:
            print(f"✗ [schema-error] {diag}")
        return 1

    try:
        data = json.loads(text)
    except json.JSONDecodeError as jde:
        snippet = generate_snippet(text.splitlines(), jde.lineno, jde.colno, context_lines=2)
        diag = f"Invalid JSON syntax: {jde.msg} (line {jde.lineno}, col {jde.colno})."
        if as_json:
            print(json.dumps({
                "status": "error",
                "mode": "schema",
                "error_type": "JSONDecodeError",
                "message": jde.msg,
                "line": jde.lineno,
                "column": jde.colno,
                "snippet": snippet,
            }, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: schema] {diag}")
            if snippet:
                print("  Snippet:")
                for line in snippet.splitlines():
                    print(f"    {line}")
            print("=" * 80)
        return 1

    # Handle boolean schema (Draft 7+ valid schema)
    if isinstance(data, bool):
        status_str = "passed" if data else "failed"
        msg = f"Boolean schema '{data}': all instances are {'valid' if data else 'invalid'}."
        if as_json:
            print(json.dumps({"status": status_str, "mode": "schema", "boolean_schema": data, "message": msg}, indent=2))
        else:
            print("=" * 80)
            print(f"✓ [code-oracle: schema] {msg}")
            print("=" * 80)
        return 0 if data else 1

    # Handle non-dict schemas cleanly without crashing
    if not isinstance(data, dict):
        diag = (
            f"Invalid schema root type: {type(data).__name__}. "
            "Standard JSON Schemas must be an object/dict (or boolean in Draft 7+).\n"
            "Fix: Wrap definitions and properties in a top-level JSON object: { ... }."
        )
        if as_json:
            print(json.dumps({"status": "error", "mode": "schema", "error": diag}, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: schema] {diag}")
            print("=" * 80)
        return 1

    report = inspect_schema_tree(data)
    dangling_count = len(report["dangling_refs"])
    type_issue_count = len(report["type_health_issues"])
    anyof_issue_count = len(report["anyof_issues"])

    has_errors = dangling_count > 0 or type_issue_count > 0 or anyof_issue_count > 0
    status_str = "failed" if has_errors else "passed"

    if as_json:
        out = {
            "status": status_str,
            "mode": "schema",
            **report,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        if not has_errors and not report["dialect_warnings"]:
            print("✓ [code-oracle: schema] Schema structure clean: all references resolved & types valid.")
            print(f"  OpenAPI Version : {report['openapi_version'] or 'N/A'}")
            print(f"  Definitions     : {report['definitions_container']}")
            print(f"  References      : {report['total_refs']} checked (0 dangling)")
        else:
            prefix = "✗ [code-oracle: schema] Issues detected in schema:" if has_errors else "⚠ [code-oracle: schema] Schema warnings:"
            print(prefix)
            print(f"  OpenAPI Version : {report['openapi_version'] or 'N/A'}")
            print(f"  Definitions     : {report['definitions_container']}")
            print(f"  Total $ref      : {report['total_refs']}")

            if report["dialect_warnings"]:
                print("\n--- DIALECT WARNINGS ---")
                for dw in report["dialect_warnings"]:
                    print(f"  ⚠ {dw}")

            if report["dangling_refs"]:
                print(f"\n--- DANGLING REFERENCES ({len(report['dangling_refs'])} found) ---")
                for dr in report["dangling_refs"]:
                    print(f"  ✗ Location : {dr['location']}")
                    print(f"    Target   : {dr['target']}")
                    print(f"    Error    : {dr['error']}")

            if report["anyof_issues"]:
                print(f"\n--- ANYOF / NULLABILITY ISSUES ({len(report['anyof_issues'])} found) ---")
                for ai in report["anyof_issues"]:
                    print(f"  ✗ Location : {ai['location']}")
                    print(f"    Message  : {ai['message']}")

            if report["type_health_issues"]:
                print(f"\n--- TYPE HEALTH ISSUES ({len(report['type_health_issues'])} found) ---")
                for ti in report["type_health_issues"]:
                    print(f"  ✗ Location : {ti['location']}")
                    print(f"    Message  : {ti['message']}")

            print("\nActionable Fixes for SWE Agent:")
            print("  1. If $ref targets are missing, check if Pydantic v1 vs v2 changed 'definitions' to '$defs'.")
            print("  2. Ensure nullable fields in OpenAPI 3.1 use anyOf: [{'type': '...'}, {'type': 'null'}].")
            print("  3. Replace Python type names ('str', 'int', 'dict') with JSON Schema primitives ('string', 'integer', 'object').")
        print("=" * 80)

    return 1 if has_errors else 0


# ==============================================================================
# Mode 6: --syntax <file>
# ==============================================================================

class RegexSyntaxChecker(ast.NodeVisitor):
    """AST visitor that checks regex patterns for invalid lookbehinds and syntax."""

    def __init__(self, file_path: str, source_lines: Sequence[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.issues: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        re_func = None
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id in ("re", "regex"):
                re_func = node.func.attr
        elif isinstance(node.func, ast.Name):
            if node.func.id in ("compile", "search", "match", "sub", "split", "findall"):
                re_func = node.func.id

        if re_func:
            pattern_node = None
            if node.args:
                pattern_node = node.args[0]
            else:
                for kw in node.keywords:
                    if kw.arg == "pattern":
                        pattern_node = kw.value
                        break

            if pattern_node and isinstance(pattern_node, ast.Constant) and isinstance(pattern_node.value, str):
                self._verify_regex(pattern_node.value, pattern_node.lineno, pattern_node.col_offset, f"re.{re_func}()")

        self.generic_visit(node)

    def _verify_regex(self, pattern: str, lineno: int, col: int, context: str):
        try:
            re.compile(pattern)
        except re.error as err:
            self.issues.append({
                "file": self.file_path,
                "line": lineno,
                "column": col + 1,
                "error_type": "RegexSyntaxError",
                "message": f"Invalid regex pattern in {context}: {err.msg}",
                "snippet": generate_snippet(self.source_lines, lineno, col + 1),
            })


def check_top_level_imports(
    tree: ast.AST,
    file_path: pathlib.Path,
    workspace: pathlib.Path,
    source_lines: Sequence[str],
) -> List[Dict[str, Any]]:
    """Verify that top-level module imports can be resolved without side-effects."""
    unresolved: List[Dict[str, Any]] = []

    orig_path = list(sys.path)
    file_parent = str(file_path.parent.resolve())
    ws_str = str(workspace.resolve())

    paths_to_add = [file_parent, ws_str]
    for p in paths_to_add:
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_mod = alias.name.split(".")[0]
                    try:
                        spec = importlib.util.find_spec(top_mod)
                        if spec is None:
                            unresolved.append({
                                "file": str(file_path),
                                "line": node.lineno,
                                "column": node.col_offset + 1,
                                "module": alias.name,
                                "error_type": "UnresolvedImport",
                                "message": f"Module '{alias.name}' cannot be resolved in current environment without side-effects.",
                                "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                            })
                    except Exception as exc:
                        unresolved.append({
                            "file": str(file_path),
                            "line": node.lineno,
                            "column": node.col_offset + 1,
                            "module": alias.name,
                            "error_type": "ImportResolutionError",
                            "message": f"Failed checking module '{alias.name}': {exc}",
                            "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                        })

            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    rel_dir = file_path.parent
                    for _ in range(node.level - 1):
                        rel_dir = rel_dir.parent

                    mod_name = node.module or ""
                    mod_path = rel_dir / (mod_name.replace(".", "/") + ".py")
                    pkg_path = rel_dir / mod_name.replace(".", "/") / "__init__.py"

                    if mod_name and not (mod_path.exists() or pkg_path.exists() or (rel_dir / mod_name).is_dir()):
                        unresolved.append({
                            "file": str(file_path),
                            "line": node.lineno,
                            "column": node.col_offset + 1,
                            "module": f".{mod_name}",
                            "error_type": "UnresolvedRelativeImport",
                            "message": f"Relative import target '{mod_name}' not found at {mod_path} or {pkg_path}.",
                            "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                        })
                elif node.module:
                    top_mod = node.module.split(".")[0]
                    try:
                        spec = importlib.util.find_spec(top_mod)
                        if spec is None:
                            unresolved.append({
                                "file": str(file_path),
                                "line": node.lineno,
                                "column": node.col_offset + 1,
                                "module": node.module,
                                "error_type": "UnresolvedImport",
                                "message": f"Module '{node.module}' cannot be resolved in current environment.",
                                "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                            })
                    except Exception as exc:
                        unresolved.append({
                            "file": str(file_path),
                            "line": node.lineno,
                            "column": node.col_offset + 1,
                            "module": node.module,
                            "error_type": "ImportResolutionError",
                            "message": f"Failed checking module '{node.module}': {exc}",
                            "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                        })
    finally:
        sys.path = orig_path

    return unresolved


def find_git_modified_files(ws: pathlib.Path) -> List[pathlib.Path]:
    """Inspect git status to find modified or untracked .py files."""
    git_bin = shutil.which("git") or "git"
    try:
        res = subprocess.run(
            [git_bin, "status", "--porcelain", "-uall"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            return []
    except Exception:
        return []

    found: List[pathlib.Path] = []
    for line in res.stdout.splitlines():
        line = line.rstrip()
        if not line or len(line) < 3:
            continue
        rel = line[3:].strip().strip('"')
        if " -> " in rel:
            rel = rel.split(" -> ")[-1].strip().strip('"')
        if rel.endswith(".py"):
            p = (ws / rel).resolve()
            if p.is_file():
                found.append(p)
    return sorted(list(set(found)))


def run_syntax(target: Optional[str] = None, as_json: bool = False) -> int:
    """Validates AST syntax and checks top-level module import resolution."""
    ws = get_workspace_dir()
    files_to_check: List[pathlib.Path] = []

    if target:
        p = pathlib.Path(target)
        if not p.is_absolute():
            p = (ws / p).resolve()
        if not p.is_file():
            # Search workspace for closest .py file candidates
            py_candidates: List[str] = []
            try:
                for root_dir, dirs, files in os.walk(str(ws)):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", ".git", "__pycache__")]
                    for f in files:
                        if f.endswith(".py"):
                            full = pathlib.Path(root_dir) / f
                            try:
                                rel = str(full.relative_to(ws))
                                py_candidates.append(rel)
                            except ValueError:
                                pass
            except Exception:
                pass

            target_name = pathlib.Path(target).name
            close_matches = difflib.get_close_matches(target, py_candidates, n=3, cutoff=0.5)
            if not close_matches:
                matched_names = difflib.get_close_matches(target_name, [pathlib.Path(c).name for c in py_candidates], n=3, cutoff=0.5)
                close_matches = [c for c in py_candidates if pathlib.Path(c).name in matched_names]

            suggestion_msg = ""
            if close_matches:
                suggestion_msg = f"\n  Did you mean: {close_matches[0]}?\n  Fix: python3 oracle.py --syntax {close_matches[0]}"

            err_msg = f"Target file '{target}' does not exist."
            if as_json:
                print(json.dumps({
                    "status": "error",
                    "mode": "syntax",
                    "error_type": "FileNotFoundError",
                    "error": err_msg,
                    "suggestions": close_matches,
                    "fix": f"python3 oracle.py --syntax {close_matches[0]}" if close_matches else None,
                }, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: syntax] {err_msg}{suggestion_msg}")
                print("=" * 80)
            return 1
        files_to_check = [p]
    else:
        files_to_check = find_git_modified_files(ws)
        if not files_to_check:
            msg = "No target file specified and no modified .py files found in git status."
            if as_json:
                print(json.dumps({"status": "passed", "mode": "syntax", "message": msg, "files_checked": 0}, indent=2))
            else:
                print(f"✓ [code-oracle: syntax] {msg}")
            return 0

    all_errors: List[Dict[str, Any]] = []

    for fpath in files_to_check:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            all_errors.append({
                "file": str(fpath),
                "line": 1,
                "column": 1,
                "error_type": "FileReadError",
                "message": f"Could not read file: {exc}",
                "snippet": "",
            })
            continue

        lines = content.splitlines()

        # AST Parse check
        try:
            tree = ast.parse(content, filename=str(fpath))
        except (SyntaxError, IndentationError, TabError) as syn_err:
            snip = generate_snippet(lines, syn_err.lineno or 1, syn_err.offset or 1)
            all_errors.append({
                "file": str(fpath),
                "line": syn_err.lineno or 1,
                "column": syn_err.offset or 1,
                "error_type": type(syn_err).__name__,
                "message": syn_err.msg,
                "snippet": snip,
            })
            continue
        except (RecursionError, MemoryError, ValueError) as ast_err:
            all_errors.append({
                "file": str(fpath),
                "line": 1,
                "column": 1,
                "error_type": type(ast_err).__name__,
                "message": f"AST parsing failure: {ast_err}",
                "snippet": "",
            })
            continue

        # Regex syntax check
        try:
            regex_checker = RegexSyntaxChecker(str(fpath), lines)
            regex_checker.visit(tree)
            all_errors.extend(regex_checker.issues)
        except RecursionError:
            all_errors.append({
                "file": str(fpath),
                "line": 1,
                "column": 1,
                "error_type": "RecursionError",
                "message": "Maximum AST recursion depth exceeded during regex inspection.",
                "snippet": "",
            })

        # Import resolution check
        import_issues = check_top_level_imports(tree, fpath, ws, lines)
        all_errors.extend(import_issues)

    status_str = "failed" if all_errors else "passed"

    if as_json:
        out = {
            "status": status_str,
            "mode": "syntax",
            "files_checked": [str(f) for f in files_to_check],
            "total_errors": len(all_errors),
            "errors": all_errors,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        if not all_errors:
            print(f"✓ [code-oracle: syntax] All {len(files_to_check)} Python file(s) passed AST & import verification.")
        else:
            print(f"✗ [code-oracle: syntax] Detected {len(all_errors)} issue(s) across {len(files_to_check)} file(s):")
            for err in all_errors:
                print(f"\n  [{err['error_type']}] {err['file']}:{err['line']}:{err['column']}")
                print(f"  Message: {err['message']}")
                if err["snippet"]:
                    print("  Snippet:")
                    for s_line in err["snippet"].splitlines():
                        print(f"    {s_line}")

            print("\nActionable Fixes for SWE Agent:")
            print("  1. Correct the syntax, indentation, or regex error on the flagged line.")
            print("  2. Verify that top-level imports are available or use guarded/deferred imports inside functions.")
        print("=" * 80)

    return 1 if all_errors else 0


# ==============================================================================
# Overview & CLI Entrypoint
# ==============================================================================

def print_overview():
    """Print clean, compact overview of all 6 modes with copy-pasteable commands."""
    overview_text = """================================================================================
CODE-ORACLE: Multi-Domain Coding Assistance Oracle for SWE Agents
================================================================================

Solves domain nuances (ANSI escapes, Unicode terminal cell widths, HTML escaping,
OpenAPI/JSON Schema validation, AST syntax & import resolution) with actionable
diagnostics for LLMs. Pure Python standard library (zero external dependencies).

SUPPORTED MODES:
  1. -e, --eval <expr>    Safely evaluate Python expressions/statements with loop
                          timeout protection; outputs type, repr, len, and formatted string.
  2. -x, --hex <text>     Hex dump and escape sequence inspector. Decodes raw bytes,
                          ANSI CSI/SGR codes, OSC links, and invisible chars (\\r, \\u200d).
  3. -w, --width <text>   Calculates exact monospaced terminal display width (CJK = 2,
                          emojis = 2, ZWJ = 2, combining = 0) vs len(text).
  4. -H, --html-esc <htm> Verifies HTML entity escaping (&lt;, &gt;, &amp;, quotes), tag
                          matching/balance, and script tag escaping.
  5. -s, --schema <json>  Inspects JSON Schema / OpenAPI structure: checks $defs vs
                          definitions, resolves $ref pointers, checks anyOf nullability.
  6. -S, --syntax <file>  Validates AST syntax (ast.parse), regexes, and checks top-level
                          module import resolution without executing side-effects.

COPY-PASTEABLE EXAMPLE COMMANDS:
  # 1. Safely evaluate an expression:
  python3 oracle.py --eval 'len("hello world")'
  python3 oracle.py '1 + 2 * 3'  # auto-detected

  # 2. Inspect ANSI escapes, hex dump, or invisible characters:
  python3 oracle.py --hex $'\\x1b[31;1mError\\x1b[0m\\r\\n'
  python3 oracle.py file_with_hidden_characters.txt

  # 3. Calculate terminal display cell width for monospaced layouts:
  python3 oracle.py --width '👨‍👩‍👧‍👦 Family'
  python3 oracle.py -w $'\\x1b[32mClean Output\\x1b[0m'

  # 4. Inspect HTML template escaping and tag balance:
  python3 oracle.py --html-esc '<div><p>Hello & welcome</p></div>'
  python3 oracle.py templates/swagger_ui.html

  # 5. Validate OpenAPI / JSON Schema references and dialect:
  python3 oracle.py --schema openapi.json
  python3 oracle.py '{"$defs": {"A": {"type": "string"}}, "$ref": "#/$defs/A"}'

  # 6. Validate AST syntax, regex lookbehinds, and top-level imports:
  python3 oracle.py --syntax rich/text.py
  python3 oracle.py -S  # auto-checks modified files from git status

ADDITIONAL OPTIONS:
  --json, -j              Output results in machine-readable JSON format
  -h, --help              Show this help message and exit
================================================================================
"""
    print(overview_text)


def normalize_cli_args(raw_argv: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """Normalize CLI arguments, handling forgiving flags, extra dashes, aliases, and loose options."""
    parsed: Dict[str, Any] = {
        "help": False,
        "json": False,
        "mode": None,
        "mode_arg": None,
    }
    positional: List[str] = []

    MODE_FLAGS = {
        # Mode 1: eval
        "e": "eval", "eval": "eval", "evaluate": "eval", "expr": "eval",
        "expression": "eval", "exec": "eval", "execute": "eval", "calc": "eval", "py": "eval",
        # Mode 2: hex
        "x": "hex", "hex": "hex", "hexdump": "hex", "dump": "hex", "bytes": "hex",
        "ansi": "hex", "escape": "hex", "escapes": "hex", "raw": "hex",
        # Mode 3: width
        "w": "width", "width": "width", "cell": "width", "cells": "width",
        "cellwidth": "width", "cell-width": "width", "column": "width",
        "columns": "width", "col": "width", "cols": "width", "display-width": "width", "displaywidth": "width",
        # Mode 4: html-esc
        "H": "html-esc", "htmlesc": "html-esc", "html-esc": "html-esc", "html": "html-esc",
        "htm": "html-esc", "html_esc": "html-esc", "htmlescape": "html-esc",
        "html-escape": "html-esc", "tags": "html-esc", "tag": "html-esc",
        # Mode 5: schema
        "s": "schema", "schema": "schema", "openapi": "schema", "jsonschema": "schema",
        "json-schema": "schema", "defs": "schema", "definitions": "schema", "swagger": "schema", "spec": "schema",
        # Mode 6: syntax
        "S": "syntax", "syntax": "syntax", "ast": "syntax", "check": "syntax",
        "checksyntax": "syntax", "check-syntax": "syntax", "lint": "syntax",
        "imports": "syntax", "import": "syntax", "pycompile": "syntax", "compile": "syntax",
    }

    i = 0
    n = len(raw_argv)
    while i < n:
        token = raw_argv[i]

        # Check if token is a flag
        is_flag = token.startswith("-") and not (len(token) > 1 and token[1].isdigit()) and token != "-"
        if is_flag:
            flag_body = token.lstrip("-")
            flag_val: Optional[str] = None
            if "=" in flag_body:
                flag_body, flag_val = flag_body.split("=", 1)

            # Help check
            if flag_body in ("h", "help", "?"):
                parsed["help"] = True
                i += 1
                continue

            # JSON check
            if flag_body in ("j", "json"):
                parsed["json"] = True
                i += 1
                continue

            # Mode flags check (exact or case-normalized / fuzzy)
            matched_mode: Optional[str] = None
            if flag_body in MODE_FLAGS:
                matched_mode = MODE_FLAGS[flag_body]
            elif len(flag_body) > 1:
                clean_body = flag_body.lower().replace("_", "-")
                if clean_body in MODE_FLAGS:
                    matched_mode = MODE_FLAGS[clean_body]
                else:
                    close = difflib.get_close_matches(clean_body, list(MODE_FLAGS.keys()), n=1, cutoff=0.7)
                    if close:
                        matched_mode = MODE_FLAGS[close[0]]

            if matched_mode:
                parsed["mode"] = matched_mode
                if flag_val is not None:
                    parsed["mode_arg"] = flag_val
                elif i + 1 < n:
                    next_token = raw_argv[i + 1]
                    next_is_flag = next_token.startswith("-") and not (len(next_token) > 1 and next_token[1].isdigit()) and next_token != "-"
                    if parsed["mode"] == "syntax" and next_is_flag:
                        parsed["mode_arg"] = None
                    elif not next_is_flag:
                        parsed["mode_arg"] = next_token
                        i += 1
                i += 1
                continue

            # Loose / unrecognized flag: ignore gracefully rather than crashing
            i += 1
            continue

        positional.append(token)
        i += 1

    return parsed, positional


def main(argv: Optional[List[str]] = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parsed, positional = normalize_cli_args(raw_argv)

    if parsed["help"]:
        print_overview()
        return 0

    as_json = parsed["json"]
    mode = parsed["mode"]
    mode_arg = parsed["mode_arg"]

    # If explicit mode was provided with extra positional tokens, join them gracefully
    if mode == "eval":
        expr = mode_arg or ""
        if positional:
            expr = (expr + " " + " ".join(positional)).strip()
        return run_eval(expr, as_json=as_json)

    if mode == "hex":
        text = mode_arg or ""
        if positional:
            text = (text + " " + " ".join(positional)).strip()
        return run_hex(text, as_json=as_json)

    if mode == "width":
        text = mode_arg or ""
        if positional:
            text = (text + " " + " ".join(positional)).strip()
        return run_width(text, as_json=as_json)

    if mode == "html-esc":
        snippet = mode_arg or ""
        if positional:
            snippet = (snippet + " " + " ".join(positional)).strip()
        return run_html_esc(snippet, as_json=as_json)

    if mode == "schema":
        schema_in = mode_arg or ""
        if positional:
            schema_in = (schema_in + " " + " ".join(positional)).strip()
        return run_schema(schema_in, as_json=as_json)

    if mode == "syntax":
        target = mode_arg
        if not target and positional:
            target = positional[0]
        return run_syntax(target, as_json=as_json)

    # Positional auto-detection when no explicit mode flag was specified
    if positional:
        pos_arg = " ".join(positional).strip()
        p = pathlib.Path(pos_arg)

        # 1. Existing file auto-detection
        if len(positional) == 1 and p.is_file():
            suffix = p.suffix.lower()
            if suffix == ".py":
                return run_syntax(pos_arg, as_json=as_json)
            elif suffix in (".json", ".yaml", ".yml"):
                return run_schema(pos_arg, as_json=as_json)
            elif suffix in (".html", ".htm", ".xml", ".svg"):
                return run_html_esc(pos_arg, as_json=as_json)
            else:
                return run_hex(pos_arg, as_json=as_json)

        # 2. File extension path detection (even if missing)
        if pos_arg.endswith(".py"):
            return run_syntax(pos_arg, as_json=as_json)
        elif pos_arg.endswith((".json", ".yaml", ".yml")):
            return run_schema(pos_arg, as_json=as_json)
        elif pos_arg.endswith((".html", ".htm", ".xml", ".svg")):
            return run_html_esc(pos_arg, as_json=as_json)
        elif pos_arg.endswith((".txt", ".log", ".out", ".diff", ".patch", ".dat", ".bin", ".raw")):
            return run_hex(pos_arg, as_json=as_json)

        # 3. ANSI escape sequence detection -> --hex
        if "\x1b" in pos_arg or "\033" in pos_arg or r"\x1b" in pos_arg or r"\033" in pos_arg or ANSI_RE.search(pos_arg):
            return run_hex(pos_arg, as_json=as_json)

        # 4. HTML tag / snippet detection -> --html-esc
        if pos_arg.startswith("<") or re.search(r"</?[a-zA-Z][^>]*>", pos_arg):
            return run_html_esc(pos_arg, as_json=as_json)

        # 5. JSON Schema string detection -> --schema
        if pos_arg.startswith("{") and any(k in pos_arg for k in ('"$defs"', '"definitions"', '"openapi"', '"$schema"', '"properties"', '"type"')):
            return run_schema(pos_arg, as_json=as_json)

        # 6. Default: Python expression / statements -> --eval
        return run_eval(pos_arg, as_json=as_json)

    # Empty invocation: print clean overview and exit 0
    print_overview()
    return 0


if __name__ == "__main__":
    sys.exit(main())
`````

## File: submission/skills/code-oracle/oracle.py
`````python
#!/usr/bin/env python3
"""code-oracle: Multi-domain coding assistance oracle for SWE agents.

Provides deterministic diagnostics and inspection tools for domain nuances that
commonly cause subtle bugs or failed assertions in SWE benchmarks:
1. --eval <expr>: Safely evaluates a Python expression in the current environment
   with infinite loop timeout protection, full exception trapping, and actionable
   diagnostics for SyntaxError and NameError.
2. --hex <text>: Hex dump and escape sequence inspector. Decodes raw bytes and
   characters, highlights ANSI escapes, SGR parameters, OSC hyperlinks, and
   invisible control/zero-width characters (\r, \n, \t, \u200d, \ufe0f).
3. --width <text>: Calculates exact terminal cell display width for monospaced
   terminals (handling CJK East Asian Width W/F as 2 cells, ZWJ sequences,
   combining characters, ASCII as 1 cell) and explains which characters cause width mismatches.
4. --html-esc <snippet>: Inspects HTML/template strings. Verifies entity escaping
   (&lt;, &gt;, &amp;, quotes), tag matching (open/close tag balance), and warns if
   unescaped < or > exists inside script tags or attribute values.
5. --schema <file_or_json>: Inspects JSON Schema / OpenAPI schema structure.
   Checks $defs vs definitions, validates $ref pointer resolution (flags dangling
   references with exact corrected paths), checks anyOf with None/null, handles
   non-dict schemas, and protects against recursive $ref cycles.
6. --syntax <file>: Validates AST syntax (ast.parse) and checks that top-level
   module imports can be resolved without executing module side-effects.

Zero external dependencies (pure Python standard library).
"""

from __future__ import annotations

import argparse
import ast
import difflib
import html
from html.parser import HTMLParser
import importlib.util
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

sys.dont_write_bytecode = True

# ANSI Escape Regex covering CSI, OSC, and standard 2-byte escape sequences
ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\].*?(?:\x07|\x1b\\))")

# HTML void elements that do not have closing tags
VOID_HTML_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# Standard JSON Schema data types
VALID_JSON_SCHEMA_TYPES = {
    "string", "number", "integer", "boolean", "array", "object", "null",
}


# ==============================================================================
# Helper Utilities
# ==============================================================================

def read_input_text(input_val: str) -> str:
    """If input_val is an existing file path, read its text, otherwise return input_val.
    
    Also decodes escaped literal backslashes if input appears to be shell-escaped
    (e.g., r'\\x1b[31m' -> actual ESC).
    """
    if not input_val:
        return ""
    try:
        p = pathlib.Path(input_val)
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Unescape raw string sequences if user passed literal backslash sequences like \x1b or \u
    if "\\" in input_val:
        try:
            if any(esc in input_val for esc in (r"\x", r"\u", r"\n", r"\r", r"\t")):
                return input_val.encode("utf-8").decode("unicode_escape")
        except Exception:
            pass

    return input_val


def get_workspace_dir(explicit_ws: Optional[str] = None) -> pathlib.Path:
    """Discover workspace directory deterministically."""
    if explicit_ws:
        p = pathlib.Path(explicit_ws)
        if p.is_dir():
            return p.resolve()

    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    ws_fixed = pathlib.Path("/workspace")
    if ws_fixed.is_dir():
        return ws_fixed.resolve()

    cur = pathlib.Path.cwd().resolve()
    for parent in [cur] + list(cur.parents):
        if (
            (parent / "tasks.jsonl").exists()
            or (parent / "my_submission").exists()
            or (parent / ".git").exists()
            or (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
        ):
            return parent

    return cur


def generate_snippet(
    source_lines: Sequence[str],
    lineno: int,
    column: int,
    context_lines: int = 2,
) -> str:
    """Generate a clean code snippet with line numbers and a visual caret pointer."""
    if not source_lines:
        return ""

    target_idx = max(0, min(len(source_lines) - 1, lineno - 1))
    start_idx = max(0, target_idx - context_lines)
    end_idx = min(len(source_lines), target_idx + context_lines + 1)

    gutter_width = max(len(str(end_idx)), 2)
    blank_gutter = " " * gutter_width

    output_lines: List[str] = []
    for idx in range(start_idx, end_idx):
        cur_line_num = idx + 1
        num_str = str(cur_line_num).rjust(gutter_width)
        line_content = source_lines[idx].rstrip("\r\n")

        if idx == target_idx:
            line_display = line_content.expandtabs(4)
            output_lines.append(f"> {num_str} | {line_display}")
            col = max(1, column)
            prefix = line_content[: col - 1].expandtabs(4)
            caret_indent = " " * len(prefix)
            output_lines.append(f"  {blank_gutter} | {caret_indent}^")
        else:
            line_display = line_content.expandtabs(4)
            output_lines.append(f"  {num_str} | {line_display}")

    return "\n".join(output_lines)


# ==============================================================================
# Mode 1: --eval <expr>
# ==============================================================================

class EvalTimeoutError(TimeoutError):
    """Raised when expression evaluation exceeds execution timeout limit."""
    pass


def _eval_alarm_handler(signum: int, frame: Any) -> None:
    raise EvalTimeoutError("Execution timed out (infinite loop or execution exceeded 5.0s limit).")


def run_eval(expr: str, as_json: bool = False) -> int:
    """Safely evaluates a Python expression or statement in the current environment."""
    if not expr or not expr.strip():
        diag = "No expression provided to --eval. Example: python3 oracle.py --eval 'len([1, 2, 3])'"
        if as_json:
            print(json.dumps({"status": "error", "mode": "eval", "error": diag}, indent=2))
        else:
            print(f"✗ [eval-error] {diag}")
        return 1

    expr_clean = expr.strip()

    # Attempt to compile: try eval first (expression), fallback to exec (statements like loops/assignments)
    is_statement = False
    compiled: Any = None
    try:
        compiled = compile(expr_clean, "<eval>", "eval")
    except SyntaxError as syn_err:
        try:
            compiled = compile(expr_clean, "<eval>", "exec")
            is_statement = True
        except SyntaxError:
            # Genuine syntax error for both eval and exec modes
            snippet = ""
            if syn_err.text:
                snippet = generate_snippet(syn_err.text.splitlines(), syn_err.lineno or 1, syn_err.offset or 1)

            diag = (
                f"SyntaxError in expression: {syn_err.msg} (line {syn_err.lineno}, col {syn_err.offset}).\n"
                f"What is wrong: Python parser encountered invalid syntax near {repr(syn_err.text.strip()) if syn_err.text else 'token'}.\n"
                "Fix: Check for unbalanced parentheses, brackets, or unclosed string quotes. Ensure you passed a valid "
                "expression or statement."
            )
            if as_json:
                print(json.dumps({
                    "status": "error",
                    "mode": "eval",
                    "error_type": "SyntaxError",
                    "message": syn_err.msg,
                    "line": syn_err.lineno,
                    "column": syn_err.offset,
                    "diagnostic": diag,
                    "snippet": snippet,
                }, indent=2))
            else:
                print("=" * 80)
                print("✗ [code-oracle: eval] SyntaxError:")
                print(f"  Message: {syn_err.msg} (col {syn_err.offset})")
                if snippet:
                    print("  Snippet:")
                    for line in snippet.splitlines():
                        print(f"    {line}")
                print(f"\n  Fix: {diag}")
                print("=" * 80)
            return 1
        except (ValueError, RecursionError, MemoryError) as comp_err:
            err_type = type(comp_err).__name__
            diag = (
                f"{err_type} during compilation: {comp_err}.\n"
                "What is wrong: Python compiler encountered an internal limit or invalid character (e.g. null bytes, extreme nesting depth).\n"
                "Fix: Verify expression does not contain null bytes or excessive nesting depth."
            )
            if as_json:
                print(json.dumps({
                    "status": "error",
                    "mode": "eval",
                    "error_type": err_type,
                    "message": str(comp_err),
                    "diagnostic": diag,
                }, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: eval] Compilation {err_type}: {comp_err}")
                print(f"  Fix: {diag}")
                print("=" * 80)
            return 1
    except (ValueError, RecursionError, MemoryError) as comp_err:
        err_type = type(comp_err).__name__
        diag = (
            f"{err_type} during compilation: {comp_err}.\n"
            "What is wrong: Python compiler encountered an internal limit or invalid character (e.g. null bytes, extreme nesting depth).\n"
            "Fix: Verify expression does not contain null bytes or excessive nesting depth."
        )
        if as_json:
            print(json.dumps({
                "status": "error",
                "mode": "eval",
                "error_type": err_type,
                "message": str(comp_err),
                "diagnostic": diag,
            }, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: eval] Compilation {err_type}: {comp_err}")
            print(f"  Fix: {diag}")
            print("=" * 80)
        return 1

    # Prepare standard modules and safe evaluation environment
    eval_globals: Dict[str, Any] = {
        "__builtins__": sys.modules["builtins"].__dict__,
        "json": json,
        "re": re,
        "math": __import__("math"),
        "datetime": __import__("datetime"),
        "collections": __import__("collections"),
        "itertools": __import__("itertools"),
        "pathlib": pathlib,
        "unicodedata": unicodedata,
        "html": html,
        "sys": sys,
        "ast": ast,
    }
    eval_locals: Dict[str, Any] = {}

    # Set timer for timeout / infinite loop protection (5.0 seconds for heavy imports)
    timer_armed = False
    try:
        if hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer"):
            signal.signal(signal.SIGALRM, _eval_alarm_handler)
            signal.setitimer(signal.ITIMER_REAL, 5.0)
            timer_armed = True
    except Exception:
        pass

    try:
        if is_statement:
            exec(compiled, eval_globals, eval_locals)
            new_vars = {k: v for k, v in eval_locals.items() if not k.startswith("__")}
            val = new_vars if new_vars else "Statements executed successfully (no return value)."
        else:
            val = eval(compiled, eval_globals, eval_locals)
    except BaseException as exc:
        exc_type = type(exc).__name__
        exc_msg = str(exc)

        # Construct highly actionable diagnostic for LLM
        if isinstance(exc, (EvalTimeoutError, TimeoutError)):
            exc_type = "TimeoutError"
            action_fix = (
                "Execution timed out. "
                "What is wrong: An infinite loop or long-running computation was detected "
                "(e.g. while True, unbounded loop, or recursive generator). "
                "Fix: Verify loop termination conditions and generator bounds."
            )
        elif isinstance(exc, NameError):
            missing_name = getattr(exc, "name", None)
            if not missing_name:
                m = re.search(r"'([^']+)'", exc_msg)
                if m:
                    missing_name = m.group(1)

            candidates = list(eval_globals.keys()) + dir(__builtins__)
            suggestion = ""
            if missing_name:
                close = difflib.get_close_matches(missing_name, candidates, n=1, cutoff=0.6)
                if close:
                    suggestion = f" Did you mean '{close[0]}'?"

            if missing_name:
                action_fix = (
                    f"NameError: Identifier '{missing_name}' is not defined.{suggestion} "
                    f"What is wrong: The variable or function '{missing_name}' does not exist in the evaluation scope. "
                    f"Fix: Define '{missing_name}' before referencing it, check for typos, or verify if it requires "
                    f"importing a module (e.g. math, sys, os, json)."
                )
            else:
                action_fix = (
                    f"NameError: {exc_msg}. "
                    "What is wrong: An identifier was referenced before being defined. "
                    "Fix: Check for misspelled variable or function names, or import the required module."
                )
        elif isinstance(exc, MemoryError):
            action_fix = (
                "MemoryError: Out of memory during expression evaluation. "
                "What is wrong: The expression attempted to allocate more memory than available. "
                "Fix: Reduce data structure size or use iterators/generators instead of large lists."
            )
        elif isinstance(exc, RecursionError):
            action_fix = (
                "RecursionError: Maximum recursion depth exceeded. "
                "What is wrong: Unbounded or excessively deep recursion was detected. "
                "Fix: Add or check recursive base cases to ensure recursion terminates."
            )
        elif isinstance(exc, ZeroDivisionError):
            action_fix = (
                "ZeroDivisionError: Division or modulo by zero. "
                "What is wrong: An arithmetic operation divided by zero. "
                "Fix: Add a check for zero before dividing or handle denominator == 0."
            )
        elif isinstance(exc, TypeError):
            action_fix = (
                f"TypeError: {exc_msg}. "
                "What is wrong: An invalid type or argument count was passed to an operation or function. "
                "Fix: Verify argument types and function signatures."
            )
        elif isinstance(exc, ValueError):
            action_fix = (
                f"ValueError: {exc_msg}. "
                "What is wrong: An invalid value was passed to a function or operation. "
                "Fix: Check argument formats, ranges, or numeric conversions."
            )
        elif isinstance(exc, KeyError):
            action_fix = (
                f"KeyError: {exc_msg}. "
                "What is wrong: The dictionary key does not exist. "
                "Fix: Check dictionary keys with .keys() or use .get() with a default value."
            )
        elif isinstance(exc, IndexError):
            action_fix = (
                f"IndexError: {exc_msg}. "
                "What is wrong: Sequence index out of range. "
                "Fix: Check sequence length with len() before indexing."
            )
        elif isinstance(exc, AttributeError):
            action_fix = (
                f"AttributeError: {exc_msg}. "
                "What is wrong: The requested attribute or method does not exist on this object. "
                "Fix: Check attribute names with dir() or check for typos."
            )
        elif isinstance(exc, SystemExit):
            action_fix = (
                "SystemExit: Expression attempted to exit the Python process. "
                "What is wrong: sys.exit() was called during evaluation. "
                "Fix: Do not call sys.exit() inside an evaluated expression."
            )
        else:
            action_fix = f"Runtime error during eval(): {exc_type}: {exc_msg}."

        if as_json:
            print(json.dumps({
                "status": "error",
                "mode": "eval",
                "error_type": exc_type,
                "message": exc_msg,
                "diagnostic": action_fix,
            }, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: eval] Runtime {exc_type}:")
            print(f"  Message: {exc_msg}")
            print(f"  Fix:     {action_fix}")
            print("=" * 80)
        return 1
    finally:
        if timer_armed:
            try:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, signal.SIG_DFL)
            except Exception:
                pass

    val_type = type(val).__name__
    val_repr = repr(val)
    val_str = str(val)

    val_len: Optional[int] = None
    try:
        val_len = len(val)  # type: ignore
    except TypeError:
        val_len = None

    if as_json:
        res = {
            "status": "ok",
            "mode": "eval",
            "expression": expr,
            "type": val_type,
            "repr": val_repr,
            "formatted": val_str,
            "len": val_len,
        }
        print(json.dumps(res, indent=2))
    else:
        print("=" * 80)
        print("✓ [code-oracle: eval] Evaluation Successful:")
        print(f"  Expression : {expr}")
        print(f"  Type       : {val_type}")
        print(f"  Repr       : {val_repr}")
        print(f"  Length     : {val_len if val_len is not None else 'N/A (not sized)'}")
        print(f"  Formatted  : {val_str}")
        print("=" * 80)

    return 0


# ==============================================================================
# Mode 2: --hex <text>
# ==============================================================================

SGR_CODES: Dict[str, str] = {
    "0": "Reset / Normal",
    "1": "Bold / Increased Intensity",
    "2": "Faint / Decreased Intensity",
    "3": "Italic",
    "4": "Underline",
    "7": "Reverse Video",
    "9": "Strikethrough",
    "22": "Normal Intensity (Not Bold/Faint)",
    "23": "Not Italic",
    "24": "Not Underlined",
    "27": "Not Reversed",
    "29": "Not Strikethrough",
    "30": "FG Black", "31": "FG Red", "32": "FG Green", "33": "FG Yellow",
    "34": "FG Blue", "35": "FG Magenta", "36": "FG Cyan", "37": "FG White",
    "39": "FG Default",
    "40": "BG Black", "41": "BG Red", "42": "BG Green", "43": "BG Yellow",
    "44": "BG Blue", "45": "BG Magenta", "46": "BG Cyan", "47": "BG White",
    "49": "BG Default",
    "90": "FG Bright Black (Gray)", "91": "FG Bright Red", "92": "FG Bright Green",
    "93": "FG Bright Yellow", "94": "FG Bright Blue", "95": "FG Bright Magenta",
    "96": "FG Bright Cyan", "97": "FG Bright White",
    "100": "BG Bright Black", "101": "BG Bright Red", "102": "BG Bright Green",
    "103": "BG Bright Yellow", "104": "BG Bright Blue", "105": "BG Bright Magenta",
    "106": "BG Bright Cyan", "107": "BG Bright White",
}


def parse_sgr_params(params_str: str) -> List[str]:
    """Parse SGR parameter string into human-readable descriptions."""
    if not params_str:
        return ["Reset / Normal (default 0)"]
    tokens = params_str.split(";")
    res: List[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ("38", "48") and i + 1 < len(tokens):
            target = "FG" if t == "38" else "BG"
            mode = tokens[i + 1]
            if mode == "5" and i + 2 < len(tokens):
                color_idx = tokens[i + 2]
                res.append(f"{target} 256-color (#{color_idx})")
                i += 3
                continue
            elif mode == "2" and i + 4 < len(tokens):
                r, g, b = tokens[i + 2], tokens[i + 3], tokens[i + 4]
                res.append(f"{target} TrueColor RGB({r}, {g}, {b})")
                i += 5
                continue
        desc = SGR_CODES.get(t, f"Code {t}")
        res.append(desc)
        i += 1
    return res


def run_hex(input_val: str, as_json: bool = False) -> int:
    """Hex dump and escape sequence inspector."""
    stripped_val = input_val.strip()
    if stripped_val and "\n" not in stripped_val and len(stripped_val) < 256:
        p = pathlib.Path(stripped_val)
        if (p.suffix in (".txt", ".log", ".dat", ".bin", ".out", ".diff", ".patch", ".raw") or "/" in stripped_val) and not p.exists():
            err_msg = f"File '{stripped_val}' not found."
            diag = (
                f"File '{stripped_val}' does not exist on disk.\n"
                "What is wrong: Specified file path could not be located.\n"
                "Fix: Check file path relative to workspace or pass text directly: python3 oracle.py --hex $'\\x1b[31mText\\x1b[0m'"
            )
            if as_json:
                print(json.dumps({"status": "error", "mode": "hex", "error_type": "FileNotFoundError", "error": err_msg, "diagnostic": diag}, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: hex] {err_msg}")
                print(f"  {diag}")
                print("=" * 80)
            return 1

    text = read_input_text(input_val)
    raw_bytes = text.encode("utf-8")

    # 1. Generate Hex Dump
    hex_dump_lines: List[str] = []
    for offset in range(0, len(raw_bytes), 16):
        chunk = raw_bytes[offset : offset + 16]
        hex_parts: List[str] = [f"{b:02x}" for b in chunk]
        first_half = " ".join(hex_parts[:8])
        second_half = " ".join(hex_parts[8:])
        hex_col = f"{first_half:<23}  {second_half:<23}".rstrip()

        ascii_col = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        hex_dump_lines.append(f"{offset:08x}  {hex_col:<48}  |{ascii_col}|")

    # 2. Inspect Escape Sequences, Invisible Characters, and Controls
    ansi_sequences: List[Dict[str, Any]] = []
    for match in ANSI_RE.finditer(text):
        seq = match.group(0)
        start, end = match.span()
        kind = "Unknown"
        details: List[str] = []
        if seq.startswith("\x1b["):
            kind = "CSI (Control Sequence Introducer)"
            terminator = seq[-1]
            params = seq[2:-1]
            if terminator == "m":
                kind = "CSI SGR (Select Graphic Rendition)"
                details = parse_sgr_params(params)
            elif terminator == "H":
                kind = "CSI Cursor Position"
            elif terminator == "J":
                kind = "CSI Erase Display"
            elif terminator == "K":
                kind = "CSI Erase in Line"
        elif seq.startswith("\x1b]"):
            kind = "OSC (Operating System Command)"
            if seq.startswith("\x1b]8;;"):
                kind = "OSC 8 Hyperlink"
                url = seq[5:].rstrip("\x07\x1b\\")
                details = [f"Hyperlink Target: {url}"]

        ansi_sequences.append({
            "raw": repr(seq),
            "start": start,
            "end": end,
            "kind": kind,
            "details": details,
        })

    # Inspect invisible and special control characters
    special_chars: List[Dict[str, Any]] = []
    for idx, ch in enumerate(text):
        cp = ord(ch)
        cat = unicodedata.category(ch)
        name = unicodedata.name(ch, "<unnamed>")

        is_special = False
        note = ""

        if ch == "\r":
            is_special = True
            is_followed_by_n = (idx + 1 < len(text) and text[idx + 1] == "\n")
            note = "Carriage Return (CR)" + (" [CRLF pair]" if is_followed_by_n else " [Lone CR - can overwrite line!]")
        elif ch == "\n":
            is_special = True
            note = "Line Feed (LF)"
        elif ch == "\t":
            is_special = True
            note = "Horizontal Tab"
        elif ch == "\u200b":
            is_special = True
            note = "Zero-Width Space (invisible)"
        elif ch == "\u200c":
            is_special = True
            note = "Zero-Width Non-Joiner (ZWNJ)"
        elif ch == "\u200d":
            is_special = True
            note = "Zero-Width Joiner (ZWJ - joins emojis/glyphs)"
        elif ch == "\ufe0e":
            is_special = True
            note = "Variation Selector-15 (text presentation)"
        elif ch == "\ufe0f":
            is_special = True
            note = "Variation Selector-16 (emoji presentation)"
        elif ch == "\ufeff":
            is_special = True
            note = "Zero-Width No-Break Space / Byte Order Mark (BOM)"
        elif ch in ("\u200e", "\u200f"):
            is_special = True
            note = "BiDi Directional Mark (LRM/RLM)"
        elif cat.startswith("C") and cp not in (9, 10, 13):
            is_special = True
            note = f"Control / Format character ({cat})"

        if is_special:
            special_chars.append({
                "index": idx,
                "char": repr(ch),
                "codepoint": f"U+{cp:04X}",
                "name": name,
                "category": cat,
                "note": note,
            })

    # Diagnostics
    diagnostics: List[str] = []
    has_sgr = any("SGR" in s["kind"] for s in ansi_sequences)
    has_reset = any("0" in s["raw"] or "Reset" in " ".join(s["details"]) for s in ansi_sequences)
    if has_sgr and not has_reset:
        diagnostics.append(
            "Unclosed ANSI sequence detected: Formatting enabled without a reset code (\\x1b[0m). "
            "Colors or styles will bleed into subsequent terminal output or test runners."
        )

    lone_cr = [sc for sc in special_chars if "Lone CR" in sc["note"]]
    if lone_cr:
        diagnostics.append(
            f"Detected {len(lone_cr)} lone Carriage Return (\\r) character(s) without \\n. "
            "In terminals, lone \\r moves the cursor to column 0 and overwrites previous text."
        )

    zw_chars = [sc for sc in special_chars if "Zero-Width" in sc["note"]]
    if zw_chars:
        diagnostics.append(
            f"Detected {len(zw_chars)} invisible zero-width character(s) (e.g. {zw_chars[0]['codepoint']}). "
            "These characters are invisible to human inspection but will cause str == expected or len() checks to fail."
        )

    if as_json:
        out = {
            "status": "ok",
            "mode": "hex",
            "total_bytes": len(raw_bytes),
            "total_chars": len(text),
            "hex_dump": hex_dump_lines,
            "ansi_sequences": ansi_sequences,
            "special_characters": special_chars,
            "diagnostics": diagnostics,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        print("✓ [code-oracle: hex] Hex Dump & Escape Sequence Inspection:")
        print(f"  Total Bytes : {len(raw_bytes)} | Total Characters: {len(text)}")
        print("\n--- HEX DUMP ---")
        for line in hex_dump_lines[:64]:
            print(line)
        if len(hex_dump_lines) > 64:
            print(f"  ... and {len(hex_dump_lines) - 64} more line(s) ({len(raw_bytes) - 1024} bytes; pass --json to view full dump)")

        if ansi_sequences:
            print(f"\n--- ANSI ESCAPE SEQUENCES ({len(ansi_sequences)} found) ---")
            for seq in ansi_sequences:
                det = f" -> {', '.join(seq['details'])}" if seq["details"] else ""
                print(f"  [{seq['start']}:{seq['end']}] {seq['kind']}: {seq['raw']}{det}")

        if special_chars:
            print(f"\n--- INVISIBLE & CONTROL CHARACTERS ({len(special_chars)} found) ---")
            for sc in special_chars:
                print(f"  Index {sc['index']:<4} | {sc['codepoint']} | {sc['name']:<25} | {sc['note']}")

        if diagnostics:
            print("\n--- ACTIONABLE DIAGNOSTICS ---")
            for diag in diagnostics:
                print(f"  ⚠ {diag}")

        print("=" * 80)

    return 0


# ==============================================================================
# Mode 3: --width <text>
# ==============================================================================

def get_char_display_width(ch: str) -> int:
    """Calculate monospaced cell display width of a single character."""
    o = ord(ch)
    cat = unicodedata.category(ch)

    # Combining characters and format marks occupy 0 terminal cells
    if cat in ("Mn", "Me", "Mc", "Cf", "Cc"):
        return 0

    # Skin tone modifiers (U+1F3FB - U+1F3FF) combine with previous emoji
    if 0x1F3FB <= o <= 0x1F3FF:
        return 0

    # East Asian Width Fullwidth (F) and Wide (W) occupy 2 cells
    ea = unicodedata.east_asian_width(ch)
    if ea in ("W", "F"):
        return 2

    # Common emoji ranges occupy 2 cells in monospaced terminal emulators
    if (0x1F300 <= o <= 0x1FAFF) or (0x2600 <= o <= 0x27BF):
        return 2

    return 1


def calculate_terminal_cells(text: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Calculate exact monospaced terminal columns and character-by-character breakdown."""
    clean_text = ANSI_RE.sub("", text)

    breakdown: List[Dict[str, Any]] = []
    total_width = 0
    i = 0
    n = len(clean_text)

    while i < n:
        ch = clean_text[i]
        o = ord(ch)
        cat = unicodedata.category(ch)
        ea = unicodedata.east_asian_width(ch)
        name = unicodedata.name(ch, "<unnamed>")

        # Handle ZWJ sequence: if current char is ZWJ, it and following emoji contribute 0 extra width
        if ch == "\u200d":
            breakdown.append({
                "char": repr(ch),
                "codepoint": f"U+{o:04X}",
                "name": name,
                "category": cat,
                "ea_width": ea,
                "cell_width": 0,
                "note": "Zero-Width Joiner (joins with adjacent glyph)",
            })
            i += 1
            if i < n:
                next_ch = clean_text[i]
                next_o = ord(next_ch)
                breakdown.append({
                    "char": repr(next_ch),
                    "codepoint": f"U+{next_o:04X}",
                    "name": unicodedata.name(next_ch, "<unnamed>"),
                    "category": unicodedata.category(next_ch),
                    "ea_width": unicodedata.east_asian_width(next_ch),
                    "cell_width": 0,
                    "note": "Joined emoji sequence component",
                })
                i += 1
            continue

        base_width = get_char_display_width(ch)

        # Check if immediately followed by emoji presentation selector \ufe0f
        if i + 1 < n and clean_text[i + 1] == "\ufe0f":
            effective_width = max(base_width, 2)
            total_width += effective_width
            breakdown.append({
                "char": repr(ch),
                "codepoint": f"U+{o:04X}",
                "name": name,
                "category": cat,
                "ea_width": ea,
                "cell_width": effective_width,
                "note": "Base symbol (presented as emoji width 2 via \\ufe0f)",
            })
            i += 1
            vs_o = ord(clean_text[i])
            breakdown.append({
                "char": repr(clean_text[i]),
                "codepoint": f"U+{vs_o:04X}",
                "name": unicodedata.name(clean_text[i], "<unnamed>"),
                "category": unicodedata.category(clean_text[i]),
                "ea_width": unicodedata.east_asian_width(clean_text[i]),
                "cell_width": 0,
                "note": "Variation Selector-16 (emoji presentation)",
            })
            i += 1
            continue

        total_width += base_width
        breakdown.append({
            "char": repr(ch),
            "codepoint": f"U+{o:04X}",
            "name": name,
            "category": cat,
            "ea_width": ea,
            "cell_width": base_width,
            "note": "Wide cell" if base_width == 2 else ("Zero width" if base_width == 0 else "Normal cell"),
        })
        i += 1

    return total_width, breakdown


def run_width(input_val: str, as_json: bool = False) -> int:
    """Calculates exact terminal cell display width for monospaced terminals."""
    text = read_input_text(input_val)

    code_points = len(text)
    utf8_bytes = len(text.encode("utf-8"))
    utf16_units = len(text.encode("utf-16-le")) // 2
    columns, breakdown = calculate_terminal_cells(text)

    # Actionable character-level diagnostics if columns != code_points
    diagnostics: List[str] = []
    char_explanations: List[str] = []
    if columns != code_points:
        reasons: List[str] = []
        wide_items = [b for b in breakdown if b["cell_width"] == 2]
        zero_items = [b for b in breakdown if b["cell_width"] == 0]
        ansi_matches = list(ANSI_RE.finditer(text))

        if wide_items:
            reasons.append(f"{len(wide_items)} wide character(s) (CJK/emoji = 2 cells)")
            for item in wide_items[:10]:
                char_explanations.append(
                    f"Character {item['char']} ({item['codepoint']}) occupies 2 terminal cells, whereas len() is 1."
                )
            if len(wide_items) > 10:
                char_explanations.append(f"... and {len(wide_items) - 10} more wide character(s)")

        if zero_items:
            reasons.append(f"{len(zero_items)} zero-width / combining / ZWJ character(s) (0 cells)")
            for item in zero_items[:10]:
                char_explanations.append(
                    f"Character {item['char']} ({item['codepoint']}) occupies 0 terminal cells, whereas len() is 1."
                )
            if len(zero_items) > 10:
                char_explanations.append(f"... and {len(zero_items) - 10} more zero-width character(s)")

        if ansi_matches:
            reasons.append(f"{len(ansi_matches)} ANSI escape sequence(s) (stripped in display = 0 cells)")
            for m in ansi_matches[:5]:
                esc_str = m.group(0)
                char_explanations.append(
                    f"ANSI escape sequence {repr(esc_str)} occupies 0 terminal cells, whereas len() is {len(esc_str)}."
                )

        diagnostics.append(
            f"Terminal display columns ({columns}) differs from Python len() ({code_points}) due to: "
            + "; ".join(reasons) + "."
        )
        diagnostics.extend(char_explanations)
        diagnostics.append(
            "Actionable Fix: In CLI/TUI tools (Rich, prompt_toolkit, table formatters), DO NOT use "
            "len(), str.ljust(), or str.rjust() to align columns. Use cell width (e.g. rich.cells.cell_len() "
            "or wcwidth) to prevent ragged borders and table misalignment."
        )

    if as_json:
        out = {
            "status": "ok",
            "mode": "width",
            "terminal_columns": columns,
            "len_code_points": code_points,
            "utf8_bytes": utf8_bytes,
            "utf16_units": utf16_units,
            "breakdown": breakdown,
            "diagnostics": diagnostics,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        print("✓ [code-oracle: width] Terminal Cell Display Width:")
        print(f"  Terminal Columns : {columns}")
        print(f"  len(text)        : {code_points} (Unicode code points)")
        print(f"  UTF-8 Bytes      : {utf8_bytes}")
        print(f"  UTF-16 Units     : {utf16_units}")

        if breakdown:
            print("\n--- CHARACTER / GLYPH BREAKDOWN ---")
            print(f"  {'Char':<8} {'CodePoint':<10} {'Width':<7} {'EA':<4} {'Cat':<5} {'Name / Note'}")
            print("  " + "-" * 74)
            for item in breakdown[:50]:
                print(f"  {item['char']:<8} {item['codepoint']:<10} {item['cell_width']:<7} {item['ea_width']:<4} {item['category']:<5} {item['name']} ({item['note']})")
            if len(breakdown) > 50:
                print(f"  ... and {len(breakdown) - 50} more character(s)")

        if char_explanations:
            print("\n--- CHARACTER-LEVEL CELL WIDTH EXPLANATIONS ---")
            for exp in char_explanations:
                print(f"  • {exp}")

        if diagnostics:
            print("\n--- ACTIONABLE DIAGNOSTICS ---")
            for diag in diagnostics:
                print(f"  ℹ {diag}")

        print("=" * 80)

    return 0


# ==============================================================================
# Mode 4: --html-esc <snippet>
# ==============================================================================

class HTMLStructureParser(HTMLParser):
    """HTML Parser that checks tag nesting balance and attribute escaping."""

    def __init__(self):
        super().__init__()
        self.tag_stack: List[Tuple[str, int, int]] = []
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.inside_script: bool = False
        self.inside_style: bool = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        t = tag.lower()
        lineno, offset = self.getpos()

        # Check attribute values for unescaped characters
        for attr_name, attr_val in attrs:
            if attr_val is not None:
                if "<" in attr_val:
                    self.warnings.append({
                        "line": lineno,
                        "column": offset,
                        "kind": "UnescapedAngleBracketInAttribute",
                        "message": f"Attribute '{attr_name}' contains raw '<': {attr_val!r}. "
                                   "Fix: Replace '<' with '&lt;' in attribute values.",
                    })
                if ">" in attr_val:
                    self.warnings.append({
                        "line": lineno,
                        "column": offset,
                        "kind": "UnescapedAngleBracketInAttribute",
                        "message": f"Attribute '{attr_name}' contains raw '>': {attr_val!r}. "
                                   "Fix: Replace '>' with '&gt;' in attribute values.",
                    })
                # Check for raw ampersands not part of a valid HTML entity in attributes
                raw_amp = re.findall(r"&(?!([a-zA-Z][a-zA-Z0-9]*|#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6});)", attr_val)
                if raw_amp:
                    self.warnings.append({
                        "line": lineno,
                        "column": offset,
                        "kind": "UnescapedAmpersandInAttribute",
                        "message": f"Attribute '{attr_name}' contains unescaped '&': {attr_val!r}. "
                                   "Fix: Replace raw '&' with '&amp;'.",
                    })

        if t == "script":
            self.inside_script = True
        elif t == "style":
            self.inside_style = True

        if t not in VOID_HTML_TAGS:
            self.tag_stack.append((t, lineno, offset))

    def handle_endtag(self, tag: str):
        t = tag.lower()
        lineno, offset = self.getpos()

        if t == "script":
            self.inside_script = False
        elif t == "style":
            self.inside_style = False

        if t in VOID_HTML_TAGS:
            self.warnings.append({
                "line": lineno,
                "column": offset,
                "kind": "VoidTagClosed",
                "message": f"Void element <{t}> should not have a closing </{t}> tag.",
            })
            return

        if not self.tag_stack:
            self.errors.append({
                "line": lineno,
                "column": offset,
                "kind": "UnmatchedClosingTag",
                "message": f"Found closing tag </{t}> with no corresponding opening tag. Fix: Remove extra </{t}> or add opening <{t}>.",
            })
            return

        top_tag, top_line, top_col = self.tag_stack[-1]
        if top_tag == t:
            self.tag_stack.pop()
        else:
            stack_tags = [item[0] for item in self.tag_stack]
            if t in stack_tags:
                idx = len(stack_tags) - 1 - stack_tags[::-1].index(t)
                unclosed = self.tag_stack[idx + 1 :]
                unclosed_names = ", ".join(f"<{item[0]} line {item[1]}>" for item in unclosed)
                self.errors.append({
                    "line": lineno,
                    "column": offset,
                    "kind": "MisnestedTag",
                    "message": f"Closing tag </{t}> closes element out of order. Unclosed inner elements: {unclosed_names}. Fix: Close inner elements first.",
                })
                self.tag_stack = self.tag_stack[:idx]
            else:
                self.errors.append({
                    "line": lineno,
                    "column": offset,
                    "kind": "UnmatchedClosingTag",
                    "message": f"Closing tag </{t}> does not match current open element <{top_tag} line {top_line}>. Fix: Ensure tags are properly closed.",
                })

    def handle_data(self, data: str):
        lineno, offset = self.getpos()
        if self.inside_script:
            if "<" in data or ">" in data:
                ch = "<" if "<" in data else ">"
                esc_ch = r"\u003c" if ch == "<" else r"\u003e"
                self.warnings.append({
                    "line": lineno,
                    "column": offset,
                    "kind": "RawScriptAngleBrackets",
                    "message": f"Raw '{ch}' detected inside <script> block. "
                               f"Fix: Escape as '{esc_ch}' in templates (Swagger UI/Redoc) "
                               "to prevent premature script termination or XSS.",
                })


def run_html_esc(input_val: str, as_json: bool = False) -> int:
    """Inspects HTML/template strings for entity escaping and tag balance."""
    raw_html = read_input_text(input_val)
    lines = raw_html.splitlines()

    parser = HTMLStructureParser()
    try:
        parser.feed(raw_html)
        parser.close()
    except BaseException as exc:
        parser.errors.append({
            "line": 1,
            "column": 1,
            "kind": "ParserFailure",
            "message": f"HTML parser encountered exception: {exc}. Fix: Check for unbalanced quotes or malformed markup.",
        })

    # Check for remaining unclosed tags at EOF
    if parser.tag_stack:
        for tag, line, col in parser.tag_stack:
            parser.errors.append({
                "line": line,
                "column": col,
                "kind": "UnclosedTag",
                "message": f"Tag <{tag}> opened at line {line} col {col} was never closed before end of document. "
                           f"Fix: Add closing tag </{tag}>.",
            })

    # Scan for raw unescaped ampersands in text (outside valid HTML entities)
    raw_amp_pattern = re.compile(r"&(?!([a-zA-Z][a-zA-Z0-9]*|#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6});)")
    for line_idx, line_str in enumerate(lines, 1):
        for m in raw_amp_pattern.finditer(line_str):
            col = m.start() + 1
            snippet = generate_snippet(lines, line_idx, col, context_lines=1)
            parser.errors.append({
                "line": line_idx,
                "column": col,
                "kind": "UnescapedAmpersand",
                "message": f"Unescaped '&' found at line {line_idx} col {col}. "
                           "Fix: Replace '&' with '&amp;' or use html.escape().",
                "snippet": snippet,
            })

    status_passed = len(parser.errors) == 0

    if as_json:
        out = {
            "status": "passed" if status_passed else "failed",
            "mode": "html-esc",
            "errors": parser.errors,
            "warnings": parser.warnings,
            "total_errors": len(parser.errors),
            "total_warnings": len(parser.warnings),
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        if status_passed and not parser.warnings:
            print("✓ [code-oracle: html-esc] HTML validation clean: all tags balanced & entities escaped.")
        else:
            header = "✗ [code-oracle: html-esc] HTML issues detected:" if not status_passed else "⚠ [code-oracle: html-esc] HTML warnings:"
            print(header)
            # Cap displayed errors at 25 items to prevent flooding on giant files
            for err in parser.errors[:25]:
                print(f"\n  [ERROR] {err['kind']} (line {err['line']}, col {err['column']}):")
                print(f"    {err['message']}")
                if "snippet" in err and err["snippet"]:
                    for s_line in err["snippet"].splitlines():
                        print(f"      {s_line}")
            if len(parser.errors) > 25:
                print(f"\n  ... and {len(parser.errors) - 25} more error(s)")

            for warn in parser.warnings[:25]:
                print(f"\n  [WARN] {warn['kind']} (line {warn['line']}, col {warn['column']}):")
                print(f"    {warn['message']}")
            if len(parser.warnings) > 25:
                print(f"\n  ... and {len(parser.warnings) - 25} more warning(s)")

            print("\nActionable Fixes for SWE Agent:")
            print("  1. Ensure every non-void opening tag has a matching closing tag.")
            print("  2. Replace unescaped '&' with '&amp;' and '<' with '&lt;'.")
            print("  3. Inside script/JSON templates (Swagger UI / Redoc), escape '<' as '\\u003c'.")
        print("=" * 80)

    return 0 if status_passed else 1


# ==============================================================================
# Mode 5: --schema <file_or_json>
# ==============================================================================

def resolve_json_pointer(root: Any, pointer: str) -> Tuple[bool, Any, str]:
    """Resolve a local JSON Pointer against the root document."""
    if not pointer.startswith("#"):
        return False, None, f"Non-local pointer '{pointer}' (external references not resolvable offline)"

    if pointer in ("#", "#/"):
        return True, root, ""

    if not pointer.startswith("#/"):
        return False, None, f"Malformed pointer '{pointer}' (must start with '#/')"

    tokens = pointer[2:].split("/")
    curr = root
    traversed: List[str] = ["#"]

    for token in tokens:
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(curr, dict):
            if key in curr:
                curr = curr[key]
                traversed.append(key)
            else:
                curr_path = "/".join(traversed)
                available = ", ".join(repr(k) for k in list(curr.keys())[:10])
                return False, None, f"Key '{key}' not found at '{curr_path}'. Available keys: [{available}]"
        elif isinstance(curr, list):
            if key.isdigit() and int(key) < len(curr):
                curr = curr[int(key)]
                traversed.append(key)
            else:
                curr_path = "/".join(traversed)
                return False, None, f"Index '{key}' out of range at '{curr_path}' (length {len(curr)})"
        else:
            curr_path = "/".join(traversed)
            return False, None, f"Cannot traverse into primitive {type(curr).__name__} at '{curr_path}'"

    return True, curr, ""


def find_all_definition_targets(root: Any) -> Dict[str, str]:
    """Find all declared definition target names and their canonical pointer paths."""
    targets: Dict[str, str] = {}
    if not isinstance(root, dict):
        return targets

    if "$defs" in root and isinstance(root["$defs"], dict):
        for name in root["$defs"].keys():
            targets[name] = f"#/$defs/{name}"

    if "definitions" in root and isinstance(root["definitions"], dict):
        for name in root["definitions"].keys():
            targets[name] = f"#/definitions/{name}"

    if "components" in root and isinstance(root["components"], dict):
        schemas = root["components"].get("schemas")
        if isinstance(schemas, dict):
            for name in schemas.keys():
                targets[name] = f"#/components/schemas/{name}"

    return targets


def inspect_schema_tree(root: Any) -> Dict[str, Any]:
    """Recursively inspect JSON Schema / OpenAPI structure with recursion cycle protection."""
    all_refs: List[Dict[str, Any]] = []
    dangling_refs: List[Dict[str, Any]] = []
    dialect_warnings: List[str] = []
    anyof_issues: List[Dict[str, Any]] = []
    type_health_issues: List[Dict[str, Any]] = []

    has_defs = "$defs" in root if isinstance(root, dict) else False
    has_definitions = "definitions" in root if isinstance(root, dict) else False
    openapi_version = root.get("openapi", "") if isinstance(root, dict) else ""
    json_schema_draft = root.get("$schema", "") if isinstance(root, dict) else ""

    if has_defs and has_definitions:
        dialect_warnings.append(
            "Schema root defines BOTH '$defs' and 'definitions'. Standardize on '$defs' (OpenAPI 3.1 / JSON Schema 2020-12) "
            "or 'definitions' (OpenAPI 3.0 / Draft 7) to prevent reference resolution ambiguity."
        )

    if openapi_version.startswith("3.0") and has_defs:
        dialect_warnings.append(
            f"OpenAPI version is {openapi_version} but uses '$defs'. OpenAPI 3.0 uses 'components/schemas' or 'definitions'. "
            "Pydantic v2 schemas use '$defs' by default; ensure FastAPI / OpenAPI generator adapts dialect."
        )
    elif openapi_version.startswith("3.1") and has_definitions and not has_defs:
        dialect_warnings.append(
            f"OpenAPI version is {openapi_version} (OpenAPI 3.1) but uses legacy 'definitions' instead of '$defs'."
        )

    # Collect all available definition targets to provide exact corrected reference paths
    known_targets = find_all_definition_targets(root)

    # Cycle protection tracking object IDs; iterative stack avoids RecursionError
    seen_ids: Set[int] = set()
    stack: List[Tuple[Any, str]] = [(root, "#")]

    while stack:
        obj, path = stack.pop()
        if id(obj) in seen_ids:
            continue
        seen_ids.add(id(obj))

        if isinstance(obj, dict):
            # Check $ref
            if "$ref" in obj and isinstance(obj["$ref"], str):
                ref_val = obj["$ref"]
                all_refs.append({"location": path, "target": ref_val})
                ok, _, err_msg = resolve_json_pointer(root, ref_val)
                if not ok:
                    # Provide exact corrected reference path
                    target_name = ref_val.rsplit("/", 1)[-1] if "/" in ref_val else ref_val.lstrip("#")
                    hint = ""
                    if target_name in known_targets:
                        correct_path = known_targets[target_name]
                        hint = f" Did you mean '{correct_path}'? Target is defined at '{correct_path}'."
                    else:
                        # Case-insensitive or closest match
                        lower_targets = {k.lower(): v for k, v in known_targets.items()}
                        if target_name.lower() in lower_targets:
                            correct_path = lower_targets[target_name.lower()]
                            hint = f" Did you mean '{correct_path}' (case mismatch)?"
                        elif known_targets:
                            close = difflib.get_close_matches(target_name, list(known_targets.keys()), n=1, cutoff=0.5)
                            if close:
                                correct_path = known_targets[close[0]]
                                hint = f" Did you mean '{correct_path}' (closest match)?"

                    dangling_refs.append({
                        "location": path,
                        "target": ref_val,
                        "error": err_msg + hint,
                    })

            # Check anyOf
            if "anyOf" in obj and isinstance(obj["anyOf"], list):
                has_null_type = False
                has_string_none = False
                for item in obj["anyOf"]:
                    if isinstance(item, dict):
                        item_type = item.get("type")
                        if item_type == "null":
                            has_null_type = True
                        elif item_type == "None" or (item_type is None and "None" in str(item)):
                            has_string_none = True

                if has_string_none:
                    anyof_issues.append({
                        "location": path,
                        "message": "anyOf contains 'None' as type or literal. In JSON Schema, nullability MUST be {'type': 'null'}.",
                    })

                if obj.get("nullable") is True and has_null_type:
                    anyof_issues.append({
                        "location": path,
                        "message": "Schema defines both 'nullable: true' and anyOf: [{'type': 'null'}]. "
                                   "OpenAPI 3.0 uses 'nullable: true'; OpenAPI 3.1 uses 'type: null'. Combining both is redundant/conflicting.",
                    })

            # Check type validity
            if "type" in obj:
                t_val = obj["type"]
                if isinstance(t_val, str):
                    if t_val not in VALID_JSON_SCHEMA_TYPES:
                        type_health_issues.append({
                            "location": path,
                            "invalid_type": t_val,
                            "message": f"Invalid type '{t_val}'. Must be one of {sorted(VALID_JSON_SCHEMA_TYPES)}. "
                                       "Check for Python type leaks (e.g. 'str' -> 'string', 'int' -> 'integer', 'dict' -> 'object').",
                        })
                elif isinstance(t_val, list):
                    for sub_t in t_val:
                        if sub_t not in VALID_JSON_SCHEMA_TYPES:
                            type_health_issues.append({
                                "location": path,
                                "invalid_type": sub_t,
                                "message": f"Invalid type '{sub_t}' in type union array. Must be one of {sorted(VALID_JSON_SCHEMA_TYPES)}.",
                            })

            # Check required list vs properties
            if "required" in obj and isinstance(obj["required"], list) and "properties" in obj and isinstance(obj["properties"], dict):
                props = set(obj["properties"].keys())
                for req in obj["required"]:
                    if isinstance(req, str) and req not in props:
                        type_health_issues.append({
                            "location": path,
                            "message": f"Property '{req}' listed in 'required' is not defined in 'properties'.",
                        })

            # Push children to stack (reversed to preserve document order)
            for k, v in reversed(list(obj.items())):
                stack.append((v, f"{path}/{k}"))

        elif isinstance(obj, list):
            for idx in reversed(range(len(obj))):
                stack.append((obj[idx], f"{path}/{idx}"))

    return {
        "openapi_version": openapi_version,
        "json_schema_draft": json_schema_draft,
        "definitions_container": "$defs" if has_defs else ("definitions" if has_definitions else "none"),
        "total_refs": len(all_refs),
        "dangling_refs": dangling_refs,
        "dialect_warnings": dialect_warnings,
        "anyof_issues": anyof_issues,
        "type_health_issues": type_health_issues,
    }


def run_schema(input_val: str, as_json: bool = False) -> int:
    """Inspects JSON Schema / OpenAPI schema structure."""
    stripped = input_val.strip()
    if stripped and not stripped.startswith(("{", "[")) and (stripped.endswith((".json", ".yaml", ".yml")) or "/" in stripped):
        p = pathlib.Path(stripped)
        if not p.is_file():
            diag = (
                f"File '{stripped}' not found.\n"
                "What is wrong: The specified schema file does not exist on disk.\n"
                "Fix: Check file path relative to workspace or pass inline JSON: python3 oracle.py --schema '{\"type\": \"object\"}'"
            )
            if as_json:
                print(json.dumps({"status": "error", "mode": "schema", "error_type": "FileNotFoundError", "error": f"File '{stripped}' not found.", "diagnostic": diag}, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: schema] File '{stripped}' not found.")
                print(f"  {diag}")
                print("=" * 80)
            return 1

    text = read_input_text(input_val)
    if not text.strip():
        diag = "No schema content provided to --schema."
        if as_json:
            print(json.dumps({"status": "error", "mode": "schema", "error": diag}, indent=2))
        else:
            print(f"✗ [schema-error] {diag}")
        return 1

    try:
        data = json.loads(text)
    except json.JSONDecodeError as jde:
        snippet = generate_snippet(text.splitlines(), jde.lineno, jde.colno, context_lines=2)
        diag = f"Invalid JSON syntax: {jde.msg} (line {jde.lineno}, col {jde.colno})."
        if as_json:
            print(json.dumps({
                "status": "error",
                "mode": "schema",
                "error_type": "JSONDecodeError",
                "message": jde.msg,
                "line": jde.lineno,
                "column": jde.colno,
                "snippet": snippet,
            }, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: schema] {diag}")
            if snippet:
                print("  Snippet:")
                for line in snippet.splitlines():
                    print(f"    {line}")
            print("=" * 80)
        return 1

    # Handle boolean schema (Draft 7+ valid schema)
    if isinstance(data, bool):
        status_str = "passed" if data else "failed"
        msg = f"Boolean schema '{data}': all instances are {'valid' if data else 'invalid'}."
        if as_json:
            print(json.dumps({"status": status_str, "mode": "schema", "boolean_schema": data, "message": msg}, indent=2))
        else:
            print("=" * 80)
            print(f"✓ [code-oracle: schema] {msg}")
            print("=" * 80)
        return 0 if data else 1

    # Handle non-dict schemas cleanly without crashing
    if not isinstance(data, dict):
        diag = (
            f"Invalid schema root type: {type(data).__name__}. "
            "Standard JSON Schemas must be an object/dict (or boolean in Draft 7+).\n"
            "Fix: Wrap definitions and properties in a top-level JSON object: { ... }."
        )
        if as_json:
            print(json.dumps({"status": "error", "mode": "schema", "error": diag}, indent=2))
        else:
            print("=" * 80)
            print(f"✗ [code-oracle: schema] {diag}")
            print("=" * 80)
        return 1

    report = inspect_schema_tree(data)
    dangling_count = len(report["dangling_refs"])
    type_issue_count = len(report["type_health_issues"])
    anyof_issue_count = len(report["anyof_issues"])

    has_errors = dangling_count > 0 or type_issue_count > 0 or anyof_issue_count > 0
    status_str = "failed" if has_errors else "passed"

    if as_json:
        out = {
            "status": status_str,
            "mode": "schema",
            **report,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        if not has_errors and not report["dialect_warnings"]:
            print("✓ [code-oracle: schema] Schema structure clean: all references resolved & types valid.")
            print(f"  OpenAPI Version : {report['openapi_version'] or 'N/A'}")
            print(f"  Definitions     : {report['definitions_container']}")
            print(f"  References      : {report['total_refs']} checked (0 dangling)")
        else:
            prefix = "✗ [code-oracle: schema] Issues detected in schema:" if has_errors else "⚠ [code-oracle: schema] Schema warnings:"
            print(prefix)
            print(f"  OpenAPI Version : {report['openapi_version'] or 'N/A'}")
            print(f"  Definitions     : {report['definitions_container']}")
            print(f"  Total $ref      : {report['total_refs']}")

            if report["dialect_warnings"]:
                print("\n--- DIALECT WARNINGS ---")
                for dw in report["dialect_warnings"]:
                    print(f"  ⚠ {dw}")

            if report["dangling_refs"]:
                print(f"\n--- DANGLING REFERENCES ({len(report['dangling_refs'])} found) ---")
                for dr in report["dangling_refs"]:
                    print(f"  ✗ Location : {dr['location']}")
                    print(f"    Target   : {dr['target']}")
                    print(f"    Error    : {dr['error']}")

            if report["anyof_issues"]:
                print(f"\n--- ANYOF / NULLABILITY ISSUES ({len(report['anyof_issues'])} found) ---")
                for ai in report["anyof_issues"]:
                    print(f"  ✗ Location : {ai['location']}")
                    print(f"    Message  : {ai['message']}")

            if report["type_health_issues"]:
                print(f"\n--- TYPE HEALTH ISSUES ({len(report['type_health_issues'])} found) ---")
                for ti in report["type_health_issues"]:
                    print(f"  ✗ Location : {ti['location']}")
                    print(f"    Message  : {ti['message']}")

            print("\nActionable Fixes for SWE Agent:")
            print("  1. If $ref targets are missing, check if Pydantic v1 vs v2 changed 'definitions' to '$defs'.")
            print("  2. Ensure nullable fields in OpenAPI 3.1 use anyOf: [{'type': '...'}, {'type': 'null'}].")
            print("  3. Replace Python type names ('str', 'int', 'dict') with JSON Schema primitives ('string', 'integer', 'object').")
        print("=" * 80)

    return 1 if has_errors else 0


# ==============================================================================
# Mode 6: --syntax <file>
# ==============================================================================

class RegexSyntaxChecker(ast.NodeVisitor):
    """AST visitor that checks regex patterns for invalid lookbehinds and syntax."""

    def __init__(self, file_path: str, source_lines: Sequence[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.issues: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        re_func = None
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id in ("re", "regex"):
                re_func = node.func.attr
        elif isinstance(node.func, ast.Name):
            if node.func.id in ("compile", "search", "match", "sub", "split", "findall"):
                re_func = node.func.id

        if re_func:
            pattern_node = None
            if node.args:
                pattern_node = node.args[0]
            else:
                for kw in node.keywords:
                    if kw.arg == "pattern":
                        pattern_node = kw.value
                        break

            if pattern_node and isinstance(pattern_node, ast.Constant) and isinstance(pattern_node.value, str):
                self._verify_regex(pattern_node.value, pattern_node.lineno, pattern_node.col_offset, f"re.{re_func}()")

        self.generic_visit(node)

    def _verify_regex(self, pattern: str, lineno: int, col: int, context: str):
        try:
            re.compile(pattern)
        except re.error as err:
            self.issues.append({
                "file": self.file_path,
                "line": lineno,
                "column": col + 1,
                "error_type": "RegexSyntaxError",
                "message": f"Invalid regex pattern in {context}: {err.msg}",
                "snippet": generate_snippet(self.source_lines, lineno, col + 1),
            })


def check_top_level_imports(
    tree: ast.AST,
    file_path: pathlib.Path,
    workspace: pathlib.Path,
    source_lines: Sequence[str],
) -> List[Dict[str, Any]]:
    """Verify that top-level module imports can be resolved without side-effects."""
    unresolved: List[Dict[str, Any]] = []

    orig_path = list(sys.path)
    file_parent = str(file_path.parent.resolve())
    ws_str = str(workspace.resolve())

    paths_to_add = [file_parent, ws_str]
    for p in paths_to_add:
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_mod = alias.name.split(".")[0]
                    try:
                        spec = importlib.util.find_spec(top_mod)
                        if spec is None:
                            unresolved.append({
                                "file": str(file_path),
                                "line": node.lineno,
                                "column": node.col_offset + 1,
                                "module": alias.name,
                                "error_type": "UnresolvedImport",
                                "message": f"Module '{alias.name}' cannot be resolved in current environment without side-effects.",
                                "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                            })
                    except Exception as exc:
                        unresolved.append({
                            "file": str(file_path),
                            "line": node.lineno,
                            "column": node.col_offset + 1,
                            "module": alias.name,
                            "error_type": "ImportResolutionError",
                            "message": f"Failed checking module '{alias.name}': {exc}",
                            "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                        })

            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    rel_dir = file_path.parent
                    for _ in range(node.level - 1):
                        rel_dir = rel_dir.parent

                    mod_name = node.module or ""
                    mod_path = rel_dir / (mod_name.replace(".", "/") + ".py")
                    pkg_path = rel_dir / mod_name.replace(".", "/") / "__init__.py"

                    if mod_name and not (mod_path.exists() or pkg_path.exists() or (rel_dir / mod_name).is_dir()):
                        unresolved.append({
                            "file": str(file_path),
                            "line": node.lineno,
                            "column": node.col_offset + 1,
                            "module": f".{mod_name}",
                            "error_type": "UnresolvedRelativeImport",
                            "message": f"Relative import target '{mod_name}' not found at {mod_path} or {pkg_path}.",
                            "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                        })
                elif node.module:
                    top_mod = node.module.split(".")[0]
                    try:
                        spec = importlib.util.find_spec(top_mod)
                        if spec is None:
                            unresolved.append({
                                "file": str(file_path),
                                "line": node.lineno,
                                "column": node.col_offset + 1,
                                "module": node.module,
                                "error_type": "UnresolvedImport",
                                "message": f"Module '{node.module}' cannot be resolved in current environment.",
                                "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                            })
                    except Exception as exc:
                        unresolved.append({
                            "file": str(file_path),
                            "line": node.lineno,
                            "column": node.col_offset + 1,
                            "module": node.module,
                            "error_type": "ImportResolutionError",
                            "message": f"Failed checking module '{node.module}': {exc}",
                            "snippet": generate_snippet(source_lines, node.lineno, node.col_offset + 1),
                        })
    finally:
        sys.path = orig_path

    return unresolved


def find_git_modified_files(ws: pathlib.Path) -> List[pathlib.Path]:
    """Inspect git status to find modified or untracked .py files."""
    git_bin = shutil.which("git") or "git"
    try:
        res = subprocess.run(
            [git_bin, "status", "--porcelain", "-uall"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            return []
    except Exception:
        return []

    found: List[pathlib.Path] = []
    for line in res.stdout.splitlines():
        line = line.rstrip()
        if not line or len(line) < 3:
            continue
        rel = line[3:].strip().strip('"')
        if " -> " in rel:
            rel = rel.split(" -> ")[-1].strip().strip('"')
        if rel.endswith(".py"):
            p = (ws / rel).resolve()
            if p.is_file():
                found.append(p)
    return sorted(list(set(found)))


def run_syntax(target: Optional[str] = None, as_json: bool = False) -> int:
    """Validates AST syntax and checks top-level module import resolution."""
    ws = get_workspace_dir()
    files_to_check: List[pathlib.Path] = []

    if target:
        p = pathlib.Path(target)
        if not p.is_absolute():
            p = (ws / p).resolve()
        if not p.is_file():
            # Search workspace for closest .py file candidates
            py_candidates: List[str] = []
            try:
                for root_dir, dirs, files in os.walk(str(ws)):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", ".git", "__pycache__")]
                    for f in files:
                        if f.endswith(".py"):
                            full = pathlib.Path(root_dir) / f
                            try:
                                rel = str(full.relative_to(ws))
                                py_candidates.append(rel)
                            except ValueError:
                                pass
            except Exception:
                pass

            target_name = pathlib.Path(target).name
            close_matches = difflib.get_close_matches(target, py_candidates, n=3, cutoff=0.5)
            if not close_matches:
                matched_names = difflib.get_close_matches(target_name, [pathlib.Path(c).name for c in py_candidates], n=3, cutoff=0.5)
                close_matches = [c for c in py_candidates if pathlib.Path(c).name in matched_names]

            suggestion_msg = ""
            if close_matches:
                suggestion_msg = f"\n  Did you mean: {close_matches[0]}?\n  Fix: python3 oracle.py --syntax {close_matches[0]}"

            err_msg = f"Target file '{target}' does not exist."
            if as_json:
                print(json.dumps({
                    "status": "error",
                    "mode": "syntax",
                    "error_type": "FileNotFoundError",
                    "error": err_msg,
                    "suggestions": close_matches,
                    "fix": f"python3 oracle.py --syntax {close_matches[0]}" if close_matches else None,
                }, indent=2))
            else:
                print("=" * 80)
                print(f"✗ [code-oracle: syntax] {err_msg}{suggestion_msg}")
                print("=" * 80)
            return 1
        files_to_check = [p]
    else:
        files_to_check = find_git_modified_files(ws)
        if not files_to_check:
            msg = "No target file specified and no modified .py files found in git status."
            if as_json:
                print(json.dumps({"status": "passed", "mode": "syntax", "message": msg, "files_checked": 0}, indent=2))
            else:
                print(f"✓ [code-oracle: syntax] {msg}")
            return 0

    all_errors: List[Dict[str, Any]] = []

    for fpath in files_to_check:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            all_errors.append({
                "file": str(fpath),
                "line": 1,
                "column": 1,
                "error_type": "FileReadError",
                "message": f"Could not read file: {exc}",
                "snippet": "",
            })
            continue

        lines = content.splitlines()

        # AST Parse check
        try:
            tree = ast.parse(content, filename=str(fpath))
        except (SyntaxError, IndentationError, TabError) as syn_err:
            snip = generate_snippet(lines, syn_err.lineno or 1, syn_err.offset or 1)
            all_errors.append({
                "file": str(fpath),
                "line": syn_err.lineno or 1,
                "column": syn_err.offset or 1,
                "error_type": type(syn_err).__name__,
                "message": syn_err.msg,
                "snippet": snip,
            })
            continue
        except (RecursionError, MemoryError, ValueError) as ast_err:
            all_errors.append({
                "file": str(fpath),
                "line": 1,
                "column": 1,
                "error_type": type(ast_err).__name__,
                "message": f"AST parsing failure: {ast_err}",
                "snippet": "",
            })
            continue

        # Regex syntax check
        try:
            regex_checker = RegexSyntaxChecker(str(fpath), lines)
            regex_checker.visit(tree)
            all_errors.extend(regex_checker.issues)
        except RecursionError:
            all_errors.append({
                "file": str(fpath),
                "line": 1,
                "column": 1,
                "error_type": "RecursionError",
                "message": "Maximum AST recursion depth exceeded during regex inspection.",
                "snippet": "",
            })

        # Import resolution check
        import_issues = check_top_level_imports(tree, fpath, ws, lines)
        all_errors.extend(import_issues)

    status_str = "failed" if all_errors else "passed"

    if as_json:
        out = {
            "status": status_str,
            "mode": "syntax",
            "files_checked": [str(f) for f in files_to_check],
            "total_errors": len(all_errors),
            "errors": all_errors,
        }
        print(json.dumps(out, indent=2))
    else:
        print("=" * 80)
        if not all_errors:
            print(f"✓ [code-oracle: syntax] All {len(files_to_check)} Python file(s) passed AST & import verification.")
        else:
            print(f"✗ [code-oracle: syntax] Detected {len(all_errors)} issue(s) across {len(files_to_check)} file(s):")
            for err in all_errors:
                print(f"\n  [{err['error_type']}] {err['file']}:{err['line']}:{err['column']}")
                print(f"  Message: {err['message']}")
                if err["snippet"]:
                    print("  Snippet:")
                    for s_line in err["snippet"].splitlines():
                        print(f"    {s_line}")

            print("\nActionable Fixes for SWE Agent:")
            print("  1. Correct the syntax, indentation, or regex error on the flagged line.")
            print("  2. Verify that top-level imports are available or use guarded/deferred imports inside functions.")
        print("=" * 80)

    return 1 if all_errors else 0


# ==============================================================================
# Overview & CLI Entrypoint
# ==============================================================================

def print_overview():
    """Print clean, compact overview of all 6 modes with copy-pasteable commands."""
    overview_text = """================================================================================
CODE-ORACLE: Multi-Domain Coding Assistance Oracle for SWE Agents
================================================================================

Solves domain nuances (ANSI escapes, Unicode terminal cell widths, HTML escaping,
OpenAPI/JSON Schema validation, AST syntax & import resolution) with actionable
diagnostics for LLMs. Pure Python standard library (zero external dependencies).

SUPPORTED MODES:
  1. -e, --eval <expr>    Safely evaluate Python expressions/statements with loop
                          timeout protection; outputs type, repr, len, and formatted string.
  2. -x, --hex <text>     Hex dump and escape sequence inspector. Decodes raw bytes,
                          ANSI CSI/SGR codes, OSC links, and invisible chars (\\r, \\u200d).
  3. -w, --width <text>   Calculates exact monospaced terminal display width (CJK = 2,
                          emojis = 2, ZWJ = 2, combining = 0) vs len(text).
  4. -H, --html-esc <htm> Verifies HTML entity escaping (&lt;, &gt;, &amp;, quotes), tag
                          matching/balance, and script tag escaping.
  5. -s, --schema <json>  Inspects JSON Schema / OpenAPI structure: checks $defs vs
                          definitions, resolves $ref pointers, checks anyOf nullability.
  6. -S, --syntax <file>  Validates AST syntax (ast.parse), regexes, and checks top-level
                          module import resolution without executing side-effects.

COPY-PASTEABLE EXAMPLE COMMANDS:
  # 1. Safely evaluate an expression:
  python3 oracle.py --eval 'len("hello world")'
  python3 oracle.py '1 + 2 * 3'  # auto-detected

  # 2. Inspect ANSI escapes, hex dump, or invisible characters:
  python3 oracle.py --hex $'\\x1b[31;1mError\\x1b[0m\\r\\n'
  python3 oracle.py file_with_hidden_characters.txt

  # 3. Calculate terminal display cell width for monospaced layouts:
  python3 oracle.py --width '👨‍👩‍👧‍👦 Family'
  python3 oracle.py -w $'\\x1b[32mClean Output\\x1b[0m'

  # 4. Inspect HTML template escaping and tag balance:
  python3 oracle.py --html-esc '<div><p>Hello & welcome</p></div>'
  python3 oracle.py templates/swagger_ui.html

  # 5. Validate OpenAPI / JSON Schema references and dialect:
  python3 oracle.py --schema openapi.json
  python3 oracle.py '{"$defs": {"A": {"type": "string"}}, "$ref": "#/$defs/A"}'

  # 6. Validate AST syntax, regex lookbehinds, and top-level imports:
  python3 oracle.py --syntax rich/text.py
  python3 oracle.py -S  # auto-checks modified files from git status

ADDITIONAL OPTIONS:
  --json, -j              Output results in machine-readable JSON format
  -h, --help              Show this help message and exit
================================================================================
"""
    print(overview_text)


def normalize_cli_args(raw_argv: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """Normalize CLI arguments, handling forgiving flags, extra dashes, aliases, and loose options."""
    parsed: Dict[str, Any] = {
        "help": False,
        "json": False,
        "mode": None,
        "mode_arg": None,
    }
    positional: List[str] = []

    MODE_FLAGS = {
        # Mode 1: eval
        "e": "eval", "eval": "eval", "evaluate": "eval", "expr": "eval",
        "expression": "eval", "exec": "eval", "execute": "eval", "calc": "eval", "py": "eval",
        # Mode 2: hex
        "x": "hex", "hex": "hex", "hexdump": "hex", "dump": "hex", "bytes": "hex",
        "ansi": "hex", "escape": "hex", "escapes": "hex", "raw": "hex",
        # Mode 3: width
        "w": "width", "width": "width", "cell": "width", "cells": "width",
        "cellwidth": "width", "cell-width": "width", "column": "width",
        "columns": "width", "col": "width", "cols": "width", "display-width": "width", "displaywidth": "width",
        # Mode 4: html-esc
        "H": "html-esc", "htmlesc": "html-esc", "html-esc": "html-esc", "html": "html-esc",
        "htm": "html-esc", "html_esc": "html-esc", "htmlescape": "html-esc",
        "html-escape": "html-esc", "tags": "html-esc", "tag": "html-esc",
        # Mode 5: schema
        "s": "schema", "schema": "schema", "openapi": "schema", "jsonschema": "schema",
        "json-schema": "schema", "defs": "schema", "definitions": "schema", "swagger": "schema", "spec": "schema",
        # Mode 6: syntax
        "S": "syntax", "syntax": "syntax", "ast": "syntax", "check": "syntax",
        "checksyntax": "syntax", "check-syntax": "syntax", "lint": "syntax",
        "imports": "syntax", "import": "syntax", "pycompile": "syntax", "compile": "syntax",
    }

    i = 0
    n = len(raw_argv)
    while i < n:
        token = raw_argv[i]

        # Check if token is a flag
        is_flag = token.startswith("-") and not (len(token) > 1 and token[1].isdigit()) and token != "-"
        if is_flag:
            flag_body = token.lstrip("-")
            flag_val: Optional[str] = None
            if "=" in flag_body:
                flag_body, flag_val = flag_body.split("=", 1)

            # Help check
            if flag_body in ("h", "help", "?"):
                parsed["help"] = True
                i += 1
                continue

            # JSON check
            if flag_body in ("j", "json"):
                parsed["json"] = True
                i += 1
                continue

            # Mode flags check (exact or case-normalized / fuzzy)
            matched_mode: Optional[str] = None
            if flag_body in MODE_FLAGS:
                matched_mode = MODE_FLAGS[flag_body]
            elif len(flag_body) > 1:
                clean_body = flag_body.lower().replace("_", "-")
                if clean_body in MODE_FLAGS:
                    matched_mode = MODE_FLAGS[clean_body]
                else:
                    close = difflib.get_close_matches(clean_body, list(MODE_FLAGS.keys()), n=1, cutoff=0.7)
                    if close:
                        matched_mode = MODE_FLAGS[close[0]]

            if matched_mode:
                parsed["mode"] = matched_mode
                if flag_val is not None:
                    parsed["mode_arg"] = flag_val
                elif i + 1 < n:
                    next_token = raw_argv[i + 1]
                    next_is_flag = next_token.startswith("-") and not (len(next_token) > 1 and next_token[1].isdigit()) and next_token != "-"
                    if parsed["mode"] == "syntax" and next_is_flag:
                        parsed["mode_arg"] = None
                    elif not next_is_flag:
                        parsed["mode_arg"] = next_token
                        i += 1
                i += 1
                continue

            # Loose / unrecognized flag: ignore gracefully rather than crashing
            i += 1
            continue

        positional.append(token)
        i += 1

    return parsed, positional


def main(argv: Optional[List[str]] = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parsed, positional = normalize_cli_args(raw_argv)

    if parsed["help"]:
        print_overview()
        return 0

    as_json = parsed["json"]
    mode = parsed["mode"]
    mode_arg = parsed["mode_arg"]

    # If explicit mode was provided with extra positional tokens, join them gracefully
    if mode == "eval":
        expr = mode_arg or ""
        if positional:
            expr = (expr + " " + " ".join(positional)).strip()
        return run_eval(expr, as_json=as_json)

    if mode == "hex":
        text = mode_arg or ""
        if positional:
            text = (text + " " + " ".join(positional)).strip()
        return run_hex(text, as_json=as_json)

    if mode == "width":
        text = mode_arg or ""
        if positional:
            text = (text + " " + " ".join(positional)).strip()
        return run_width(text, as_json=as_json)

    if mode == "html-esc":
        snippet = mode_arg or ""
        if positional:
            snippet = (snippet + " " + " ".join(positional)).strip()
        return run_html_esc(snippet, as_json=as_json)

    if mode == "schema":
        schema_in = mode_arg or ""
        if positional:
            schema_in = (schema_in + " " + " ".join(positional)).strip()
        return run_schema(schema_in, as_json=as_json)

    if mode == "syntax":
        target = mode_arg
        if not target and positional:
            target = positional[0]
        return run_syntax(target, as_json=as_json)

    # Positional auto-detection when no explicit mode flag was specified
    if positional:
        pos_arg = " ".join(positional).strip()
        p = pathlib.Path(pos_arg)

        # 1. Existing file auto-detection
        if len(positional) == 1 and p.is_file():
            suffix = p.suffix.lower()
            if suffix == ".py":
                return run_syntax(pos_arg, as_json=as_json)
            elif suffix in (".json", ".yaml", ".yml"):
                return run_schema(pos_arg, as_json=as_json)
            elif suffix in (".html", ".htm", ".xml", ".svg"):
                return run_html_esc(pos_arg, as_json=as_json)
            else:
                return run_hex(pos_arg, as_json=as_json)

        # 2. File extension path detection (even if missing)
        if pos_arg.endswith(".py"):
            return run_syntax(pos_arg, as_json=as_json)
        elif pos_arg.endswith((".json", ".yaml", ".yml")):
            return run_schema(pos_arg, as_json=as_json)
        elif pos_arg.endswith((".html", ".htm", ".xml", ".svg")):
            return run_html_esc(pos_arg, as_json=as_json)
        elif pos_arg.endswith((".txt", ".log", ".out", ".diff", ".patch", ".dat", ".bin", ".raw")):
            return run_hex(pos_arg, as_json=as_json)

        # 3. ANSI escape sequence detection -> --hex
        if "\x1b" in pos_arg or "\033" in pos_arg or r"\x1b" in pos_arg or r"\033" in pos_arg or ANSI_RE.search(pos_arg):
            return run_hex(pos_arg, as_json=as_json)

        # 4. HTML tag / snippet detection -> --html-esc
        if pos_arg.startswith("<") or re.search(r"</?[a-zA-Z][^>]*>", pos_arg):
            return run_html_esc(pos_arg, as_json=as_json)

        # 5. JSON Schema string detection -> --schema
        if pos_arg.startswith("{") and any(k in pos_arg for k in ('"$defs"', '"definitions"', '"openapi"', '"$schema"', '"properties"', '"type"')):
            return run_schema(pos_arg, as_json=as_json)

        # 6. Default: Python expression / statements -> --eval
        return run_eval(pos_arg, as_json=as_json)

    # Empty invocation: print clean overview and exit 0
    print_overview()
    return 0


if __name__ == "__main__":
    sys.exit(main())
`````

## File: submission/skills/code-oracle/SKILL.md
`````markdown
---
name: code-oracle
description: Multi-domain coding oracle for Python expression evaluation, ANSI/hex inspection, Unicode terminal cell width, HTML escaping & tag balance, JSON Schema/OpenAPI validation, and AST syntax/import checking.
---

# code-oracle Skill

Multi-domain coding oracle designed for SWE agents to verify domain nuances that trigger subtle test failures without repo-specific hardcoding. Zero external dependencies.

## Supported Modes & Forgiving CLI

### 1. Safely Evaluate Python Expressions (`-e`, `--eval`)
Evaluates expressions/statements in a sandbox with infinite-loop timeout protection (2.0s limit) and actionable error diagnostics:
```bash
python3 oracle.py --eval 'len([x for x in range(10) if x % 2 == 0])'
python3 oracle.py 1 + 2 * 3  # unquoted auto-evaluation
```
*Outputs: Type, `repr()`, `len()`, formatted string, and actionable runtime diagnostics.*

### 2. Hex Dump & ANSI / Escape Inspector (`-x`, `--hex`)
Inspects raw bytes, ANSI CSI/SGR styling (`\x1b[31;1m`), OSC 8 hyperlinks, and invisible characters (`\r`, `\n`, `\t`, `\u200d`, `\ufe0f`):
```bash
python3 oracle.py --hex $'\x1b[31;1mError\x1b[0m\r\n'
python3 oracle.py path/to/file_with_hidden_characters.txt
```
*Flags unclosed ANSI styles, lone `\r` line overwrites, and invisible zero-width spaces.*

### 3. Terminal Cell Display Width (`-w`, `--width`)
Calculates exact monospaced terminal columns (handling CJK Wide `W`/`F` as 2 cells, emojis as 2 cells, ZWJ sequences as 2 cells, combining marks as 0 cells, ANSI escapes as 0 cells) vs `len(text)`:
```bash
python3 oracle.py --width '👨‍👩‍👧‍👦 Family'
python3 oracle.py -w $'\\x1b[32mClean Output\\x1b[0m'
```
*Explains character-level width causes (e.g. `Character '🚀' occupies 2 terminal cells, whereas len() is 1`).*

### 4. HTML Entity & Tag Balance (`-H`, `--html-esc`)
Verifies HTML entity escaping (`&lt;`, `&gt;`, `&amp;`), tag balance/nesting, and script tags:
```bash
python3 oracle.py --html-esc '<div><p>Hello & welcome</p></div>'
python3 oracle.py '<div class="btn">Click</div>'  # auto-detected
```
*Flags unclosed tags, misnested elements, raw ampersands, and raw `<`/`>` inside scripts.*

### 5. OpenAPI & JSON Schema Validator (`-s`, `--schema`)
Inspects JSON Schema / OpenAPI structure, checks `$defs` vs `definitions`, resolves local `$ref` pointers with exact corrected path suggestions, checks `anyOf` with `null`, handles boolean/non-dict schemas, and prevents recursive `$ref` cycles:
```bash
python3 oracle.py --schema openapi.json
python3 oracle.py schema.json
```
*Catches Pydantic v1 vs v2 `$defs`/`definitions` migration bugs and invalid type leaks.*

### 6. AST Syntax & Import Checker (`-S`, `--syntax`)
Validates AST syntax (`ast.parse`), catches regex lookbehind issues, and checks top-level module import resolution without executing module side-effects:
```bash
python3 oracle.py --syntax rich/text.py
python3 oracle.py -S  # auto-checks modified files from git status
```

### 7. Overview & Diagnostics (Empty Invocation)
Invoking `python3 oracle.py` without arguments prints a clean, compact overview of all 6 modes with copy-pasteable example commands and exits code 0.

## Options & Auto-Detection
- `--json`, `-j`: Outputs structured JSON for automated pipelines and agent evaluation.
- Forgiving flags: `-e`, `-x`, `-w`, `-H`, `-s`, `-S`, `-j`, `-eval`, `---eval`.
- Positional auto-detection: `.py` -> syntax, `.json` / schema string -> schema, `.html` / tags -> html-esc, ANSI -> hex, unquoted tokens / expressions -> eval.
`````

## File: submission/skills/fast-grep/scripts/grep.py
`````python
#!/usr/bin/env python3
"""fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents.

Eats ANY input format:
- Single terms, compound phrases, multiple terms (searched as OR/union)
- Unescaped regex or literal code snippets (auto-fallback to literal substring on re.error)
- Dotted symbols, function calls, or raw keywords
- Forgiving CLI: positional args, -p/--pattern, -d/--dir, -i/--ignore-case, -w/--window, -m/--max-matches, --json
- Automatically skips benchmarks, lockfiles, docs, binary files, and noise directories
- Crash & loop immunity: bounded file reads (500KB, 5000 lines), symlink cycle protection, capped match output
- Deterministically explains zero matches with file count, narrow-path detection, and case-insensitive check
- Suggests candidate symbols from AST and repository identifiers via fuzzy matching
- Tokenizes compound phrases on failure and checks for sub-term presence
- Explains regex syntax errors in plain English and suggests escaped patterns
- 100% Pydantic v2 structured schemas (FastGrepResult, MatchExplanation, FuzzySuggestion, etc.)
- Flashes top 2 enclosing functions with complete decorators via AST
- Prioritizes function, method, and class definitions at the top of search rankings over call sites
- Boosts common string/buffer transformation methods & verbs
- Highlights call-sites and enclosing scopes where strings/buffers are transformed
- Automatically expands terse issue keywords to candidate string operations
- Detects non-existent paths, warns the LLM, suggests similar files, and falls back to workspace search
- Context-safe: Sliding context window centered on target line, clean code block for edit_file
- Always exits 0 and never crashes or hangs in runaway loops.
"""

from __future__ import annotations

import ast
import difflib
import os
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True

from pydantic import BaseModel, ConfigDict, Field

# ==============================================================================
# Pydantic v2 Output & Diagnostic Schemas
# ==============================================================================


class MatchExplanation(BaseModel):
    """Deterministic explanation for search outcome."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(
        ...,
        description="Outcome status: MATCHES_FOUND, ZERO_MATCHES, REGEX_ERROR, PATH_NOT_FOUND, or OVERVIEW",
    )
    summary: str = Field(
        ..., description="Human-readable summary of search result"
    )
    case_sensitive: bool = Field(
        default=True, description="Whether search was case-sensitive"
    )
    case_insensitive_count: int = Field(
        default=0, description="Count of matches found ignoring case"
    )
    other_locations_count: int = Field(
        default=0, description="Count of matches found outside target path"
    )
    details: Optional[str] = Field(
        default=None, description="Additional context or diagnostics"
    )
    skipped_extensions: List[str] = Field(
        default_factory=list, description="Extensions excluded from search"
    )
    skipped_dirs: List[str] = Field(
        default_factory=list, description="Directories excluded from search"
    )


class FuzzySuggestion(BaseModel):
    """AST / repository identifier fuzzy candidate suggestion."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., description="Original query term")
    symbol: str = Field(..., description="Candidate symbol identifier")
    similarity: float = Field(
        ..., description="Fuzzy match similarity score (0.0 to 1.0)"
    )
    kind: Optional[str] = Field(
        default="identifier",
        description="Symbol kind: function, class, variable, identifier",
    )
    source_file: Optional[str] = Field(
        default=None,
        description="Workspace-relative file path containing symbol",
    )


class SubtermMatchSummary(BaseModel):
    """Match summary for individual sub-terms of a failed compound query."""

    model_config = ConfigDict(extra="ignore")

    subterm: str = Field(..., description="Subterm token extracted from query")
    match_count: int = Field(..., description="Count of matches found for subterm")
    sample_file: Optional[str] = Field(
        default=None, description="Sample file containing subterm"
    )
    sample_lineno: Optional[int] = Field(
        default=None, description="Sample line number containing subterm"
    )


class RegexErrorDiagnostic(BaseModel):
    """Diagnostic detail for invalid regular expression pattern."""

    model_config = ConfigDict(extra="ignore")

    raw_pattern: str = Field(..., description="Raw invalid pattern string")
    error_message: str = Field(..., description="Underlying re.error message")
    position: Optional[int] = Field(
        default=None, description="Error position character offset"
    )
    plain_english_explanation: str = Field(
        ..., description="Plain-English explanation of syntax issue"
    )
    suggested_escaped_regex: str = Field(
        ..., description="Safe, properly escaped regex pattern"
    )


class CaseInsensitiveMatch(BaseModel):
    """Match line discovered when ignoring character casing."""

    model_config = ConfigDict(extra="ignore")

    file: str = Field(..., description="Workspace-relative file path")
    lineno: int = Field(..., description="1-based line number")
    content: str = Field(..., description="Matching line content preview")


class OtherLocationMatch(BaseModel):
    """Match line discovered in other repository files outside target path."""

    model_config = ConfigDict(extra="ignore")

    file: str = Field(..., description="Workspace-relative file path")
    lineno: int = Field(..., description="1-based line number")
    content: str = Field(..., description="Matching line content preview")


class GrepMatch(BaseModel):
    """Individual ranked match line."""

    model_config = ConfigDict(extra="ignore")

    file: str = Field(..., description="Workspace-relative file path")
    lineno: int = Field(..., description="1-based line number")
    content: str = Field(..., description="Matching line content")
    score: int = Field(default=0, description="Relevance ranking score")
    is_call_site: bool = Field(
        default=False, description="Whether line is an active transform call-site"
    )
    is_definition: bool = Field(
        default=False,
        description="Whether line is a function, method, or class definition signature",
    )
    scope_name: Optional[str] = Field(
        default=None, description="Enclosing function or class name"
    )


class ASTNodePreview(BaseModel):
    """Top-ranked enclosing AST function or class preview."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(
        ..., description="Scope display name (e.g. def foo, class Bar)"
    )
    kind: str = Field(..., description="Scope type: def or class")
    file: str = Field(..., description="Workspace-relative file path")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    score: int = Field(
        default=0, description="Match score associated with scope"
    )
    code_snippet: str = Field(
        ..., description="Complete or folded source code snippet"
    )


class FastGrepResult(BaseModel):
    """Top-level structured result returned by fast-grep."""

    model_config = ConfigDict(extra="ignore")

    query_terms: List[str] = Field(
        default_factory=list, description="Original query search terms"
    )
    target_path: str = Field(
        ..., description="Target search directory or file path"
    )
    total_files_scanned: int = Field(
        default=0, description="Count of files scanned in target"
    )
    total_matches: int = Field(
        default=0, description="Total matching lines found"
    )
    explanation: MatchExplanation = Field(
        ..., description="Match explanation and diagnostic summary"
    )
    regex_diagnostics: List[RegexErrorDiagnostic] = Field(
        default_factory=list, description="Regex syntax diagnostics"
    )
    case_insensitive_matches: List[CaseInsensitiveMatch] = Field(
        default_factory=list, description="Matches found ignoring case"
    )
    other_locations_matches: List[OtherLocationMatch] = Field(
        default_factory=list, description="Matches found in other workspace files"
    )
    fuzzy_suggestions: List[FuzzySuggestion] = Field(
        default_factory=list, description="Candidate symbol suggestions"
    )
    subterm_matches: List[SubtermMatchSummary] = Field(
        default_factory=list,
        description="Matches found for tokenized sub-terms of compound query",
    )
    similar_files: List[str] = Field(
        default_factory=list, description="Relevant workspace files"
    )
    suggestions: List[str] = Field(
        default_factory=list, description="Actionable query reformulation suggestions"
    )
    copy_pasteable_commands: List[str] = Field(
        default_factory=list, description="Copy-pasteable CLI commands for LLM next turn"
    )
    path_warning: Optional[str] = Field(
        default=None, description="Warning if target path was missing or corrected"
    )
    ranked_matches: List[GrepMatch] = Field(
        default_factory=list, description="Ranked match items"
    )
    top_ast_nodes: List[ASTNodePreview] = Field(
        default_factory=list, description="Top AST scope previews"
    )


# ==============================================================================
# Constants & Safety Limits
# ==============================================================================

MAX_FILE_SIZE_BYTES: int = 500_000   # 500 KB limit to prevent OOM on giant dumps
MAX_LINES_PER_FILE: int = 5_000      # Max lines to scan per file
MAX_LINE_LENGTH: int = 1_000         # Max chars per line inspected (prevents ReDoS/OOM)
MAX_RAW_MATCHES: int = 200           # Circuit breaker on raw git/python grep matches
MAX_RANKED_MATCHES: int = 50         # Max ranked matches kept in result
MAX_DISPLAY_PREVIEWS: int = 15       # Max previews shown in console summary
MAX_SCOPES_FLASHED: int = 2          # Top enclosing AST scopes flashed

SKIP_DIRS: Set[str] = {
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
    "wheels",
    "snapshots",
    "benchmarks",
    "benchmark",
    "results",
    "docs",
    "doc",
    "htmlcov",
    "site-packages",
    "embeddings",
    ".adk_exec",
    ".eggs",
    ".beads",
    ".idea",
    ".vscode",
}

SKIP_EXTENSIONS: Set[str] = {
    ".lock",
    ".bin",
    ".tar",
    ".gz",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".ico",
    ".pyc",
    ".safetensors",
    ".whl",
    ".json",
    ".jsonl",
    ".npz",
    ".npy",
    ".csv",
    ".log",
    ".xml",
    ".txt",
    ".yaml",
    ".yml",
    ".md",
    ".rst",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".wasm",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".parquet",
    ".pkl",
    ".pickle",
    ".pdf",
    ".ttf",
    ".woff",
    ".woff2",
    ".eot",
}

STRING_TRANSFORM_VERBS: Set[str] = {
    "splitlines",
    "split",
    "rstrip",
    "strip",
    "lstrip",
    "replace",
    "join",
    "partition",
    "rpartition",
    "decode",
    "encode",
    "from_ansi",
}

PYTHON_KEYWORDS: Set[str] = {
    "False",
    "None",
    "True",
    "and",
    "as",
    "assert",
    "async",
    "await",
    "break",
    "class",
    "continue",
    "def",
    "del",
    "elif",
    "else",
    "except",
    "finally",
    "for",
    "from",
    "global",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "nonlocal",
    "not",
    "or",
    "pass",
    "raise",
    "return",
    "try",
    "while",
    "with",
    "yield",
}

COMMON_STOPWORDS: Set[str] = {
    "the",
    "a",
    "an",
    "in",
    "on",
    "of",
    "to",
    "for",
    "with",
    "at",
    "by",
    "from",
    "into",
    "is",
    "are",
    "was",
    "were",
    "it",
    "this",
    "that",
    "these",
    "those",
    "be",
    "been",
    "has",
    "have",
    "had",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "not",
    "no",
    "but",
    "and",
    "or",
    "as",
    "if",
}

_AST_CACHE: Dict[str, Tuple[Optional[ast.AST], List[str]]] = {}


# ==============================================================================
# Binary & Symlink Safety Checks
# ==============================================================================


def is_binary_file(path: pathlib.Path) -> bool:
    """Detect if file is binary by extension or null byte inspection."""
    if any(path.name.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            if b"\0" in chunk:
                return True
    except Exception:
        return True
    return False


# ==============================================================================
# AST & Scope Inspection Helpers
# ==============================================================================


def get_ast_and_lines(
    full_path: pathlib.Path,
) -> Tuple[Optional[ast.AST], List[str]]:
    """Parse and cache AST and source lines for a python file, skipping gigantic or binary files."""
    try:
        real_p = full_path.resolve()
        key = str(real_p)
    except Exception:
        key = str(full_path)

    if key in _AST_CACHE:
        return _AST_CACHE[key]

    try:
        st = full_path.stat()
        if st.st_size > MAX_FILE_SIZE_BYTES or st.st_size == 0:
            _AST_CACHE[key] = (None, [])
            return (None, [])
        if is_binary_file(full_path):
            _AST_CACHE[key] = (None, [])
            return (None, [])
        text = full_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()[:MAX_LINES_PER_FILE]
        tree = ast.parse("\n".join(lines), filename=key)
        _AST_CACHE[key] = (tree, lines)
        return (tree, lines)
    except Exception:
        _AST_CACHE[key] = (None, [])
        return (None, [])


def find_enclosing_node(
    tree: Optional[ast.AST], target_line: int
) -> Optional[Any]:
    """Find innermost function or class enclosing target_line."""
    if not tree:
        return None
    best_node = None
    best_span = float("inf")
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            s = getattr(node, "lineno", None)
            e = getattr(node, "end_lineno", None)
            if s is not None and e is not None and s <= target_line <= e:
                span = e - s
                if span < best_span:
                    best_span = span
                    best_node = node
    return best_node


def is_string_transform_line(content: str) -> bool:
    """Detect if content is an active call-site or statement transforming strings/buffers."""
    c = content
    if re.search(
        r"\.\s*(splitlines|split|rstrip|strip|lstrip|replace|join|partition|rpartition|decode|encode|from_ansi)\s*\(",
        c,
        re.IGNORECASE,
    ):
        return True
    if re.search(
        r"\b(text|line|lines|terminal_text|buffer|output|input|data|content|string|val|raw|payload|chunk|stream|body|msg)\w*\s*\.\s*(splitlines|split|rstrip|strip|lstrip|replace|join|partition|rpartition|decode|encode|from_ansi)\b",
        c,
        re.IGNORECASE,
    ):
        return True
    if re.search(r"\bre\.(split|sub|finditer|findall)\s*\(", c):
        return True
    return False


def is_string_transform_scope(scope_name: str, lines: List[str]) -> bool:
    """Detect if enclosing function or class is dedicated to string/buffer manipulation."""
    s_lower = scope_name.lower()
    if any(v in s_lower for v in STRING_TRANSFORM_VERBS):
        return True
    if any(
        w in s_lower
        for w in ("ansi", "text", "buffer", "decode", "encode", "line", "codec")
    ):
        return True
    for line in lines[:200]:
        if is_string_transform_line(line):
            return True
    return False


def get_workspace_dir() -> pathlib.Path:
    """Deterministically locate the active repository workspace."""
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / ".git").exists()
                    or (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR", "WORKSPACE"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    ws = pathlib.Path("/workspace")
    if ws.is_dir():
        return ws.resolve()

    return pathlib.Path.cwd().resolve()


def clean_search_term(raw: str) -> str:
    """Normalize terms without destroying useful symbols."""
    cleaned = raw.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()
    if cleaned.startswith("`") and cleaned.endswith("`"):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def extract_subterms(phrase: str) -> List[str]:
    """Extract significant non-stopword identifier tokens from a compound query."""
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", phrase)
    subterms: List[str] = []
    for w in words:
        w_clean = w.strip()
        w_lower = w_clean.lower()
        if (
            len(w_clean) >= 3
            and w_lower not in PYTHON_KEYWORDS
            and w_lower not in COMMON_STOPWORDS
            and w_clean not in subterms
        ):
            subterms.append(w_clean)
    return subterms


def find_similar_workspace_files(
    query_str: str, ws: pathlib.Path, max_results: int = 5
) -> List[str]:
    """Find repository files matching or closely resembling query identifiers."""
    all_files: List[str] = []
    try:
        if (ws / ".git").exists():
            res = subprocess.run(
                ["git", "ls-files", ":(exclude)*.adk_exec*"],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res.returncode == 0:
                all_files = [
                    f
                    for f in res.stdout.splitlines()
                    if f.endswith(".py")
                    and not any(d in f for d in SKIP_DIRS)
                ]
    except Exception:
        pass

    if not all_files:
        try:
            for root, dirs, files in os.walk(ws, followlinks=False):
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in SKIP_DIRS
                    and not d.startswith(".")
                    and not (".adk_exec" in d or d.startswith(".adk_exec"))
                ]
                for f in files:
                    if f.endswith(".py"):
                        full_p = pathlib.Path(root) / f
                        try:
                            all_files.append(str(full_p.relative_to(ws)))
                        except ValueError:
                            all_files.append(str(full_p))
                if len(all_files) > 1000:
                    break
        except Exception:
            pass

    if not all_files:
        return []

    matches: List[str] = []
    tokens = [t.lower() for t in extract_subterms(query_str)]
    if not tokens:
        tokens = [query_str.lower()]

    for f in all_files:
        f_lower = f.lower()
        stem = pathlib.Path(f).stem.lower()
        if any(t == stem for t in tokens):
            if f not in matches:
                matches.append(f)
        elif any(t in f_lower for t in tokens if len(t) >= 4):
            if f not in matches:
                matches.append(f)
        if len(matches) >= max_results:
            return matches

    filenames = [pathlib.Path(f).name for f in all_files]
    for tok in tokens:
        close = difflib.get_close_matches(tok, filenames, n=3, cutoff=0.5)
        for c in close:
            for f in all_files:
                if pathlib.Path(f).name == c and f not in matches:
                    matches.append(f)
                    if len(matches) >= max_results:
                        return matches

    return matches[:max_results]


# ==============================================================================
# Argument Parsing (Omnivorous, Forgiving CLI)
# ==============================================================================


def looks_like_path(val: str) -> bool:
    """Heuristic to check if an argument was meant as a path."""
    if val in (".", "./", "/workspace", "/workspace/", "..", "../"):
        return True
    if val.startswith(("/", "./", "../", "~/")):
        return True
    if "/" in val or "\\" in val:
        return True
    if any(
        val.endswith(ext)
        for ext in (
            ".py",
            ".pyi",
            ".toml",
            ".json",
            ".md",
            ".txt",
            ".yaml",
            ".yml",
            ".rst",
            ".html",
            ".sh",
            ".c",
            ".h",
            ".cpp",
        )
    ):
        return True
    return False


def resolve_target_path(val: str, ws: pathlib.Path) -> Optional[pathlib.Path]:
    """Resolve a path string relative to ws or absolute if exists, or None if non-existent."""
    if val in (".", "./", "/workspace", "/workspace/"):
        return ws
    cand = ws / val.lstrip("/")
    if cand.exists():
        return cand
    cand_direct = pathlib.Path(val).resolve()
    if cand_direct.exists():
        return cand_direct
    return None


def parse_args(
    args: List[str], ws: pathlib.Path
) -> Tuple[
    List[str],          # terms
    pathlib.Path,       # target_path
    bool,               # is_json
    bool,               # is_help
    bool,               # is_case_insensitive
    int,                # context_window
    int,                # max_matches
    Optional[str],      # invalid_target
    Optional[str],      # raw_phrase
    bool,               # is_overview
]:
    """Extract search terms, target directory/file, and flags with forgiving tolerance."""
    terms: List[str] = []
    target_path = ws
    is_json = False
    is_help = False
    is_case_insensitive = False
    context_window = 40  # default 40 lines (15 before, 25 after)
    max_matches = 50
    invalid_target: Optional[str] = None
    raw_phrase: Optional[str] = None
    explicit_target = False
    explicit_terms = False
    positional_args: List[str] = []

    i = 0
    while i < len(args):
        a = args[i].strip()
        if not a:
            i += 1
            continue

        if a in ("--help", "-h"):
            is_help = True
            i += 1
            continue

        if a == "--json":
            is_json = True
            i += 1
            continue

        if a in ("-i", "--ignore-case", "-case-insensitive", "--case-insensitive"):
            is_case_insensitive = True
            i += 1
            continue

        # -p or --pattern or -q or --query
        if a in ("--pattern", "-p", "--query", "-q"):
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                val = clean_search_term(args[i])
                if val:
                    terms.append(val)
                    explicit_terms = True
                    if not raw_phrase:
                        raw_phrase = val
            i += 1
            continue

        if any(
            a.startswith(prefix)
            for prefix in ("--pattern=", "-p=", "--query=", "-q=")
        ):
            val = clean_search_term(a.split("=", 1)[1])
            if val:
                terms.append(val)
                explicit_terms = True
                if not raw_phrase:
                    raw_phrase = val
            i += 1
            continue

        # -d or --dir or --path
        if a in ("--dir", "-d", "--path"):
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                dir_val = clean_search_term(args[i])
                if dir_val:
                    target_cand = resolve_target_path(dir_val, ws)
                    if target_cand is not None:
                        target_path = target_cand
                    else:
                        invalid_target = dir_val
                    explicit_target = True
            i += 1
            continue

        if any(a.startswith(prefix) for prefix in ("--dir=", "-d=", "--path=")):
            dir_val = clean_search_term(a.split("=", 1)[1])
            if dir_val:
                target_cand = resolve_target_path(dir_val, ws)
                if target_cand is not None:
                    target_path = target_cand
                else:
                    invalid_target = dir_val
                explicit_target = True
            i += 1
            continue

        # -w, --window, -c, --context
        if a in ("--window", "-w", "--context", "-c"):
            if i + 1 < len(args) and (
                args[i + 1].isdigit()
                or (args[i + 1].startswith("-") and args[i + 1][1:].isdigit())
            ):
                i += 1
                try:
                    context_window = max(5, min(200, int(args[i])))
                except ValueError:
                    pass
            i += 1
            continue

        if any(
            a.startswith(prefix)
            for prefix in ("--window=", "-w=", "--context=", "-c=")
        ):
            try:
                context_window = max(5, min(200, int(a.split("=", 1)[1])))
            except ValueError:
                pass
            i += 1
            continue

        # -m, --max-matches
        if a in ("--max-matches", "-m"):
            if i + 1 < len(args) and args[i + 1].isdigit():
                i += 1
                try:
                    max_matches = max(1, min(500, int(args[i])))
                except ValueError:
                    pass
            i += 1
            continue

        if any(a.startswith(prefix) for prefix in ("--max-matches=", "-m=")):
            try:
                max_matches = max(1, min(500, int(a.split("=", 1)[1])))
            except ValueError:
                pass
            i += 1
            continue

        # Otherwise it's a positional argument
        cleaned = clean_search_term(a)
        if cleaned:
            positional_args.append(cleaned)
        i += 1

    # Resolve positional arguments
    is_overview = False

    if explicit_terms:
        # User explicitly passed terms via -p/-q; any positional arg is candidate target path
        if not explicit_target and positional_args:
            pos_target = positional_args[0]
            cand = resolve_target_path(pos_target, ws)
            if cand is not None:
                target_path = cand
            else:
                invalid_target = pos_target
    else:
        # Terms were not passed via flags
        if len(positional_args) == 0:
            is_overview = True
        elif len(positional_args) == 1:
            arg = positional_args[0]
            if arg in (".", "./", "/workspace", "/workspace/"):
                is_overview = True
                target_path = ws
            else:
                # Single term search across target
                terms.append(arg)
                raw_phrase = arg
        elif len(positional_args) == 2:
            arg0, arg1 = positional_args[0], positional_args[1]
            if not explicit_target:
                target_cand = resolve_target_path(arg1, ws)
                if target_cand is not None:
                    terms.append(arg0)
                    raw_phrase = arg0
                    target_path = target_cand
                elif looks_like_path(arg1):
                    terms.append(arg0)
                    raw_phrase = arg0
                    invalid_target = arg1
                else:
                    # Multi-term union search across workspace
                    terms.extend([arg0, arg1])
                    raw_phrase = f"{arg0} {arg1}"
            else:
                terms.extend([arg0, arg1])
                raw_phrase = f"{arg0} {arg1}"
        else:
            # >= 3 positional arguments
            if not explicit_target:
                last_arg = positional_args[-1]
                target_cand = resolve_target_path(last_arg, ws)
                if target_cand is not None:
                    target_path = target_cand
                    terms.extend(positional_args[:-1])
                    raw_phrase = " ".join(positional_args[:-1])
                elif looks_like_path(last_arg):
                    invalid_target = last_arg
                    terms.extend(positional_args[:-1])
                    raw_phrase = " ".join(positional_args[:-1])
                else:
                    terms.extend(positional_args)
                    raw_phrase = " ".join(positional_args)
            else:
                terms.extend(positional_args)
                raw_phrase = " ".join(positional_args)

    return (
        terms,
        target_path,
        is_json,
        is_help,
        is_case_insensitive,
        context_window,
        max_matches,
        invalid_target,
        raw_phrase,
        is_overview,
    )


# ==============================================================================
# Regex Diagnostics & Symbol Extraction
# ==============================================================================


def escape_regex_metachars(pattern: str) -> str:
    """Escape regex special characters while preserving readable spaces and alphanumeric words."""
    escaped = re.escape(pattern)
    try:
        re.compile(escaped)
        return escaped
    except re.error:
        return re.sub(r"([()\[\]{}*+?|^$\\.])", r"\\\1", pattern)


def check_regex_syntax(pattern: str) -> Optional[RegexErrorDiagnostic]:
    """Validate regex pattern and produce plain-English diagnostic if invalid."""
    try:
        re.compile(pattern)
        return None
    except re.error as e:
        msg = str(e)
        pos = getattr(e, "pos", None)
        msg_lower = msg.lower()

        if (
            "missing ), unterminated subpattern" in msg_lower
            or "unbalanced parenthesis" in msg_lower
        ):
            plain_english = (
                f"Unclosed opening parenthesis '(' at position {pos if pos is not None else 'unknown'}. "
                "In regex, '(' starts a group. To match literal '(', escape it as '\\('."
            )
        elif "missing (" in msg_lower or "unmatched )" in msg_lower:
            plain_english = (
                f"Unmatched closing parenthesis ')' at position {pos if pos is not None else 'unknown'}. "
                "To match literal ')', escape it as '\\)'."
            )
        elif (
            "unterminated character set" in msg_lower
            or "missing ]" in msg_lower
        ):
            plain_english = (
                f"Unclosed character set bracket '[' at position {pos if pos is not None else 'unknown'}. "
                "To match literal '[', escape it as '\\['."
            )
        elif "missing [" in msg_lower or "unmatched ]" in msg_lower:
            plain_english = (
                f"Unmatched closing bracket ']' at position {pos if pos is not None else 'unknown'}. "
                "To match literal ']', escape it as '\\]'."
            )
        elif "nothing to repeat" in msg_lower:
            plain_english = (
                f"Dangling quantifier (*, +, ?, or {{}}) at position {pos if pos is not None else 'unknown'} "
                "without preceding character or token. To match literal quantifier, escape with '\\'."
            )
        elif "multiple repeat" in msg_lower:
            plain_english = (
                f"Consecutive repeat operators at position {pos if pos is not None else 'unknown'}. "
                "To match literal symbols, escape with '\\'."
            )
        elif "bad escape" in msg_lower or "incomplete escape" in msg_lower:
            plain_english = (
                f"Invalid or incomplete escape sequence at position {pos if pos is not None else 'unknown'}. "
                "Ensure backslashes are properly paired or escape literal backslashes as '\\\\'."
            )
        elif "bad character range" in msg_lower:
            plain_english = (
                f"Invalid character range in brackets at position {pos if pos is not None else 'unknown'} (e.g. [z-a]). "
                "Start character must be <= end character."
            )
        else:
            plain_english = (
                f"Regular expression syntax error ({msg}) at position {pos if pos is not None else 'unknown'}. "
                "Check pattern syntax or escape special characters with '\\'."
            )

        suggested = escape_regex_metachars(pattern)
        return RegexErrorDiagnostic(
            raw_pattern=pattern,
            error_message=msg,
            position=pos,
            plain_english_explanation=plain_english,
            suggested_escaped_regex=suggested,
        )


def count_files_in_target(target: pathlib.Path, ws: pathlib.Path) -> int:
    """Accurately count searchable files in target directory with loop safeguards."""
    if (ws / ".git").exists():
        try:
            rel = "."
            if target != ws:
                try:
                    rel = str(target.relative_to(ws))
                except ValueError:
                    rel = str(target)
            res = subprocess.run(
                [
                    "git",
                    "ls-files",
                    rel,
                    ":(exclude)*.adk_exec*",
                    ":(exclude)**/.adk_exec*",
                ],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                files = [
                    f
                    for f in res.stdout.splitlines()
                    if f.strip()
                    and not (
                        ".adk_exec" in f or f.startswith(".adk_exec")
                    )
                ]
                if files:
                    return len(files)
        except Exception:
            pass

    count = 0
    try:
        for root, dirs, files in os.walk(target, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if d not in SKIP_DIRS
                and not d.startswith(".")
                and not (".adk_exec" in d or d.startswith(".adk_exec"))
            ]
            count += len(
                [
                    f
                    for f in files
                    if not any(f.endswith(ext) for ext in SKIP_EXTENSIONS)
                    and not (".adk_exec" in f or f.startswith(".adk_exec"))
                ]
            )
            if count >= 50000:
                break
    except Exception:
        pass
    return max(count, 1)


def extract_candidate_symbols(
    target: pathlib.Path, ws: pathlib.Path, max_files: int = 150
) -> Dict[str, Tuple[str, str]]:
    """Extract symbol names and kinds from AST and source code in the repository."""
    symbols: Dict[str, Tuple[str, str]] = {}
    search_root = target if target.is_dir() else ws
    scanned_files = 0

    try:
        for root, dirs, files in os.walk(search_root, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if d not in SKIP_DIRS
                and not d.startswith(".")
                and not (".adk_exec" in d or d.startswith(".adk_exec"))
                and "test" not in d.lower()
                and ("doc" not in d.lower() or "docs_src" in d.lower())
            ]
            for f in files:
                if ".adk_exec" in f or f.startswith(".adk_exec"):
                    continue
                if not f.endswith(".py"):
                    continue
                scanned_files += 1
                if scanned_files > max_files:
                    break
                full_p = pathlib.Path(root) / f
                try:
                    rel_p = str(full_p.relative_to(ws))
                except ValueError:
                    rel_p = str(full_p)

                try:
                    if full_p.stat().st_size > MAX_FILE_SIZE_BYTES:
                        continue
                except OSError:
                    continue

                tree, lines = get_ast_and_lines(full_p)
                if tree:
                    for node in ast.walk(tree):
                        if isinstance(
                            node, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ):
                            if node.name not in symbols:
                                symbols[node.name] = ("function", rel_p)
                        elif isinstance(node, ast.ClassDef):
                            if node.name not in symbols:
                                symbols[node.name] = ("class", rel_p)
                        elif isinstance(node, ast.Name) and isinstance(
                            node.ctx, ast.Store
                        ):
                            if (
                                node.id not in symbols
                                and node.id not in PYTHON_KEYWORDS
                                and len(node.id) > 2
                            ):
                                symbols[node.id] = ("variable", rel_p)

                for line in lines[:300]:
                    tokens = re.findall(
                        r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", line[:200]
                    )
                    for tok in tokens:
                        if tok not in symbols and tok not in PYTHON_KEYWORDS:
                            symbols[tok] = ("identifier", rel_p)

                if len(symbols) >= 1000:
                    break

            if scanned_files > max_files or len(symbols) >= 1000:
                break
    except Exception:
        pass

    return symbols


def get_fuzzy_suggestions(
    query_terms: List[str],
    candidate_symbols: Dict[str, Tuple[str, str]],
    top_n: int = 5,
    cutoff: float = 0.35,
) -> List[FuzzySuggestion]:
    """Find closest matching candidate symbols via fuzzy ratio matching."""
    scored: List[Tuple[float, str, str, str, str]] = []
    seen: Set[str] = set()

    for term in query_terms:
        words = [
            w
            for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", term)
            if len(w) > 2 and w.lower() not in PYTHON_KEYWORDS
        ]
        if not words:
            words = [term]

        for cand, (kind, fpath) in candidate_symbols.items():
            s1 = difflib.SequenceMatcher(None, term, cand).ratio()
            s2 = difflib.SequenceMatcher(
                None, term.lower(), cand.lower()
            ).ratio()
            best = max(s1, s2 * 0.95)

            for w in words:
                w1 = difflib.SequenceMatcher(None, w, cand).ratio()
                w2 = difflib.SequenceMatcher(
                    None, w.lower(), cand.lower()
                ).ratio()
                best = max(best, w1, w2 * 0.95)

            if best >= cutoff:
                scored.append((best, cand, kind, fpath, term))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: List[FuzzySuggestion] = []
    for best, cand, kind, fpath, term in scored:
        if cand not in seen:
            seen.add(cand)
            results.append(
                FuzzySuggestion(
                    query=term,
                    symbol=cand,
                    similarity=round(best, 3),
                    kind=kind,
                    source_file=fpath,
                )
            )
            if len(results) >= top_n:
                break

    return results


# ==============================================================================
# Search Execution & Scoring
# ==============================================================================


def run_git_grep(
    terms: List[str],
    target: pathlib.Path,
    ws: pathlib.Path,
    case_insensitive: bool = False,
    max_matches: int = MAX_RAW_MATCHES,
) -> List[str]:
    """Execute git grep with extended regex and literal fallback, with path exclusions."""
    if not (ws / ".git").exists():
        return python_walk_fallback(
            terms,
            target,
            ws,
            case_insensitive=case_insensitive,
            max_matches=max_matches,
        )

    safe_regex_terms: List[str] = []
    for t in terms:
        diag = check_regex_syntax(t)
        if diag:
            safe_regex_terms.append(diag.suggested_escaped_regex)
        else:
            safe_regex_terms.append(t)

    combined_pattern = (
        "|".join(safe_regex_terms)
        if len(safe_regex_terms) > 1
        else safe_regex_terms[0]
    )

    rel_target = "."
    if target != ws:
        try:
            rel_target = str(target.relative_to(ws))
        except ValueError:
            rel_target = str(target)

    path_args = [rel_target]
    for d in SKIP_DIRS:
        path_args.append(f":(exclude){d}/**")
        path_args.append(f":(exclude)**/{d}/**")
    for ext in SKIP_EXTENSIONS:
        path_args.append(f":(exclude)*{ext}")
        path_args.append(f":(exclude)**/*{ext}")
    path_args.append(":(exclude)*.adk_exec*")
    path_args.append(":(exclude)**/.adk_exec*")

    # 1. Try extended regex (-E)
    cmd = ["git", "grep", "-n", "-I"]
    if case_insensitive:
        cmd.append("-i")
    cmd.extend(["-E", "-e", combined_pattern, "--"] + path_args)

    try:
        res = subprocess.run(
            cmd,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            clean_lines = []
            for line in res.stdout.splitlines():
                if not line.strip():
                    continue
                matched_file = line.split(":", 1)[0]
                if (
                    ".adk_exec" in matched_file
                    or matched_file.startswith(".adk_exec")
                ):
                    continue
                clean_lines.append(line)
                if len(clean_lines) >= max_matches:
                    break
            if clean_lines:
                return clean_lines
    except Exception:
        pass

    # 2. Fallback to fixed-strings (-F) for each raw term
    all_lines: List[str] = []
    for t in terms:
        cmd_fixed = ["git", "grep", "-n", "-I"]
        if case_insensitive:
            cmd_fixed.append("-i")
        cmd_fixed.extend(["-F", "-e", t, "--"] + path_args)
        try:
            res = subprocess.run(
                cmd_fixed,
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.splitlines():
                    if not line.strip():
                        continue
                    matched_file = line.split(":", 1)[0]
                    if (
                        ".adk_exec" in matched_file
                        or matched_file.startswith(".adk_exec")
                    ):
                        continue
                    if line not in all_lines:
                        all_lines.append(line)
                    if len(all_lines) >= max_matches:
                        break
        except Exception:
            pass
        if len(all_lines) >= max_matches:
            break

    if all_lines:
        return all_lines

    # 3. Fallback to python walk if git grep failed or was empty
    return python_walk_fallback(
        terms,
        target,
        ws,
        case_insensitive=case_insensitive,
        max_matches=max_matches,
    )


def python_walk_fallback(
    terms: List[str],
    target: pathlib.Path,
    ws: pathlib.Path,
    case_insensitive: bool = False,
    max_matches: int = MAX_RAW_MATCHES,
) -> List[str]:
    """Pure-python fallback scanner with loop, symlink, giant-file, and ReDoS safeguards."""
    matches: List[str] = []
    flags = re.IGNORECASE if case_insensitive else 0
    compiled: List[re.Pattern] = []
    raw_substrings: List[str] = []

    for t in terms:
        try:
            compiled.append(re.compile(t, flags))
        except re.error:
            try:
                compiled.append(re.compile(escape_regex_metachars(t), flags))
            except re.error:
                pass
        raw_substrings.append(t.lower() if case_insensitive else t)

    search_root = (
        target
        if target.is_dir()
        else (target.parent if target.is_file() else ws)
    )
    visited_inodes: Set[Tuple[int, int]] = set()

    file_list: List[pathlib.Path] = []
    if target.is_file():
        file_list = [target]
    else:
        try:
            for root, dirs, files in os.walk(search_root, followlinks=False):
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in SKIP_DIRS
                    and not d.startswith(".")
                    and not (".adk_exec" in d or d.startswith(".adk_exec"))
                ]
                for f in sorted(files):
                    if ".adk_exec" in f or f.startswith(".adk_exec"):
                        continue
                    if any(f.endswith(ext) for ext in SKIP_EXTENSIONS):
                        continue
                    file_list.append(pathlib.Path(root) / f)
                    if len(file_list) >= 50_000:
                        break
                if len(file_list) >= 50_000:
                    break
        except Exception:
            pass

    for full_p in file_list:
        try:
            st = full_p.stat()
            inode_key = (st.st_dev, st.st_ino)
            if inode_key in visited_inodes:
                continue
            visited_inodes.add(inode_key)

            if st.st_size > MAX_FILE_SIZE_BYTES or st.st_size == 0:
                continue
            if is_binary_file(full_p):
                continue
        except OSError:
            continue

        try:
            rel_p = str(full_p.relative_to(ws))
        except ValueError:
            rel_p = str(full_p)

        try:
            with open(full_p, "r", encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if lineno > MAX_LINES_PER_FILE:
                        break
                    line_trunc = line[:MAX_LINE_LENGTH]
                    matched = False

                    for pattern in compiled:
                        try:
                            if pattern.search(line_trunc):
                                matched = True
                                break
                        except Exception:
                            pass

                    if not matched:
                        line_check = (
                            line_trunc.lower()
                            if case_insensitive
                            else line_trunc
                        )
                        for sub in raw_substrings:
                            if sub in line_check:
                                matched = True
                                break

                    if matched:
                        matches.append(
                            f"{rel_p}:{lineno}:{line.rstrip()[:400]}"
                        )
                        if len(matches) >= max_matches:
                            return matches
        except Exception:
            continue

    return matches


def score_match(
    file_path: str,
    lineno: int,
    content: str,
    terms: List[str],
    scope_name: str = "",
) -> int:
    """Calculate relevance score prioritizing core definitions and source code."""
    score = 0
    p_lower = file_path.lower()
    c = content.strip()

    # Prefer python source files
    if file_path.endswith(".py"):
        score += 30
    elif file_path.endswith((".pyi", ".toml")):
        score += 10

    # Demote tests and docs (exempt executable tutorial code in docs_src/*.py)
    if "test" in p_lower:
        score -= 40
    is_docs_src_py = "docs_src" in p_lower and file_path.endswith(".py")
    if not is_docs_src_py and (
        "doc" in p_lower or file_path.endswith((".md", ".rst"))
    ):
        score -= 40
    if "bench" in p_lower or "example" in p_lower:
        score -= 50

    # Priority Tier 1: Function, method, and class definitions
    is_code = not c.startswith(("#", "//", "/*", "*", '"""', "'''"))
    if is_code:
        if re.search(r"\b(async\s+def|def|class)\s+", content):
            score += 60
        elif "@" in content:
            score += 30

        sig_match = re.search(
            r"^\s*(async\s+def|def|class)\s+([A-Za-z0-9_]+)", content
        )
        if sig_match:
            score += 60
            sym_name = sig_match.group(2).lower()
            for t in terms:
                cleaned_t = t.strip().lower()
                if not cleaned_t:
                    continue
                if cleaned_t == sym_name:
                    score += 75
                    break
                elif cleaned_t in sym_name:
                    score += 50
                    break
        elif re.search(r"^\s*@", content):
            score += 30

    if "=" in content and not content.strip().startswith("#"):
        score += 10

    # String & Buffer transform verb boosting
    if is_string_transform_line(content):
        score += 40

    # High-relevance call-site patterns
    if re.search(
        r"\b\w+\.(splitlines|split|rstrip|strip|replace|join|partition|decode|encode)\(",
        content,
    ):
        score += 30

    # Streaming/iteration or line generator patterns
    if (
        re.search(r"for\s+\w+\s+in\s+.*(splitlines|split|partition)", c)
        or "yield" in c
    ):
        score += 20

    # Demote assertion-only and length inspection lines
    if re.search(r"\b(len|assert)\s*\(", c):
        score -= 25

    # Boost string/text-processing modules
    if re.search(
        r"(\b|_)(ansi|text|codec|decode|encode|string|parser|format|stream)(\b|\.py)",
        file_path,
        re.IGNORECASE,
    ):
        score += 25

    # Scope boost if enclosing function/class transforms strings/buffers
    if scope_name:
        scope_lower = scope_name.lower()
        if any(v in scope_lower for v in STRING_TRANSFORM_VERBS):
            score += 25
        if any(
            w in scope_lower
            for w in ("ansi", "text", "buffer", "decode", "encode")
        ):
            score += 20

    for t in terms:
        cleaned_t = t.strip()
        if not cleaned_t:
            continue
        if re.match(r"^[A-Za-z0-9_]+$", cleaned_t):
            if re.search(rf"\b{re.escape(cleaned_t)}\b", content, re.IGNORECASE):
                score += 15
        else:
            if cleaned_t.lower() in content.lower():
                score += 15

    return score


def extract_function_scope(
    full_path: pathlib.Path, target_line: int
) -> Optional[Dict[str, Any]]:
    """Extract enclosing function or class definition lines."""
    tree, lines = get_ast_and_lines(full_path)
    target_node = find_enclosing_node(tree, target_line)
    if not target_node:
        return None

    start = getattr(target_node, "lineno", target_line)
    end = getattr(target_node, "end_lineno", target_line)

    if hasattr(target_node, "decorator_list") and target_node.decorator_list:
        dec_starts = [
            d.lineno for d in target_node.decorator_list if hasattr(d, "lineno")
        ]
        if dec_starts:
            start = min(start, min(dec_starts))

    scope_lines = lines[start - 1 : end]

    kind = (
        "def"
        if isinstance(target_node, (ast.FunctionDef, ast.AsyncFunctionDef))
        else "class"
    )
    raw_name = target_node.name
    scope_name = f"{kind} {raw_name}"
    is_transform = is_string_transform_scope(scope_name, scope_lines)

    return {
        "name": scope_name,
        "raw_name": raw_name,
        "kind": kind,
        "start_line": start,
        "end_line": end,
        "line_count": len(scope_lines),
        "lines": scope_lines,
        "is_transform": is_transform,
    }


def print_help() -> None:
    """Print clean usage information."""
    print(
        """Usage: python grep.py [options] <pattern...> [path]

fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents.

Positional arguments:
  pattern...             Search term(s), phrase, or regex. Multiple terms are searched as OR/union.
  path                   Optional target directory or file (defaults to /workspace).

Options:
  --help, -h             Show this help message and exit.
  -p, --pattern <term>   Search pattern or regex (supports raw code snippets).
  -q, --query <term>     Search query or phrase (auto-tokenized for subterm checking).
  -d, --dir <path>       Target search directory or file path.
  -i, --ignore-case      Perform case-insensitive search.
  -w, --window <lines>   Context window size centered on target line (default: 40).
  -m, --max-matches <n>  Maximum matches to collect (default: 50).
  --json                 Output results as structured JSON conforming to Pydantic v2 FastGrepResult.

Diagnostics:
  - Zero matches: Explains file count, runs case-insensitive check, tests sub-terms, checks other files, and suggests symbols.
  - Regex errors: Fall back cleanly to literal substring search, warn gently, and return matches.
  - Missing path: Detects missing files/directories, suggests close matches, and falls back to workspace.
"""
    )


def print_overview(target_display: str = "/workspace") -> None:
    """Print helpful, copy-pasteable usage overview when called without pattern."""
    print("=" * 80)
    print("fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents")
    print("=" * 80)
    print("\nUsage:")
    print("  python3 grep.py [options] <pattern...> [path]")
    print("\nTailored copy-pasteable commands for next step:")
    print("  1. Search symbol or phrase:")
    print('     python3 grep.py "def score_match"')
    print("  2. Case-insensitive search:")
    print('     python3 grep.py -i "apirouter"')
    print("  3. Search in specific directory:")
    print('     python3 grep.py "splitlines" src/')
    print("  4. Multi-term union search:")
    print("     python3 grep.py splitlines rstrip strip")
    print("  5. Structured JSON output:")
    print('     python3 grep.py --json "APIRouter"')
    print("\nOptions:")
    print("  -p, --pattern <term>   Search pattern or regex")
    print("  -d, --dir <path>       Target directory or file (defaults to /workspace)")
    print("  -i, --ignore-case      Case-insensitive search")
    print("  -w, --window <lines>   Context window size around target line (default: 40)")
    print("  -m, --max-matches <n>  Maximum matches to collect (default: 50)")
    print("  --json                 Output structured Pydantic v2 JSON")
    print("  -h, --help             Show help message and exit")


# ==============================================================================
# Main Entry Point
# ==============================================================================


def main() -> int:
    try:
        raw_args = sys.argv[1:]
        ws = get_workspace_dir()

        (
            terms,
            target,
            is_json,
            is_help,
            is_case_insensitive,
            context_window,
            max_matches,
            invalid_target,
            raw_phrase,
            is_overview,
        ) = parse_args(raw_args, ws)

        if is_help:
            print_help()
            return 0

        # Align workspace if target has .git
        if (
            target.is_dir()
            and (target / ".git").exists()
            and not (ws / ".git").exists()
        ):
            ws = target

        # Target display name
        if target == ws or str(target).startswith("/workspace"):
            target_display = "/workspace"
        else:
            try:
                rel = target.relative_to(ws)
                target_display = f"/workspace/{rel}"
            except ValueError:
                target_display = str(target)

        total_files = count_files_in_target(target, ws)

        # Overview mode (no terms provided or empty arguments)
        if is_overview or (not terms and not invalid_target):
            overview_cmds = [
                'python3 grep.py "def score_match"',
                'python3 grep.py -i "apirouter"',
                'python3 grep.py "splitlines" src/',
                'python3 grep.py splitlines rstrip strip',
                'python3 grep.py --json "APIRouter"',
            ]
            if is_json:
                explanation = MatchExplanation(
                    status="OVERVIEW",
                    summary=f"No search pattern specified. Showing workspace overview for {target_display}.",
                    case_sensitive=not is_case_insensitive,
                    case_insensitive_count=0,
                    details="fast-grep usage overview",
                    skipped_extensions=sorted(list(SKIP_EXTENSIONS)),
                    skipped_dirs=sorted(list(SKIP_DIRS)),
                )
                result = FastGrepResult(
                    query_terms=[],
                    target_path=target_display,
                    total_files_scanned=total_files,
                    total_matches=0,
                    explanation=explanation,
                    suggestions=[
                        "Provide a search pattern: python3 grep.py '<pattern>'"
                    ],
                    copy_pasteable_commands=overview_cmds,
                )
                print(result.model_dump_json(indent=2))
                return 0
            else:
                print_overview(target_display)
                return 0

        # Handle missing/invalid target path
        path_warning_msg = None
        if invalid_target:
            similar_paths = find_similar_workspace_files(
                invalid_target, ws, max_results=3
            )
            path_warning_msg = (
                f"Target path '{invalid_target}' does not exist in workspace ({ws}). "
                f"Falling back to searching entire workspace."
            )
            if not is_json:
                print(
                    f"[fast-grep] ⚠️ TARGET PATH NOT FOUND: '{invalid_target}' does not exist!"
                )
                if similar_paths:
                    print("  Did you mean one of these files?")
                    for sp in similar_paths:
                        print(f"    - {sp}")
                print(
                    f"  [fast-grep] 🔄 Falling back to searching entire workspace (/workspace)...\n"
                )

        if not terms:
            print(
                "[fast-grep] ⚠️ No valid search terms provided after parsing arguments.\n"
                "Usage: python grep.py [options] <pattern...> [path]\n"
                "Example: python grep.py 'def score_match' ."
            )
            return 0

        # 1. Regex validation and diagnostic checks (with forgiving literal fallback)
        regex_diagnostics: List[RegexErrorDiagnostic] = []
        safe_terms: List[str] = []
        for t in terms:
            diag = check_regex_syntax(t)
            if diag:
                regex_diagnostics.append(diag)
                safe_terms.append(diag.suggested_escaped_regex)
                if not is_json:
                    print(
                        f"[fast-grep] ⚠️ Invalid regex pattern '{diag.raw_pattern}': {diag.error_message}"
                    )
                    print(
                        f"  💡 Automatically falling back to literal substring search."
                    )
            else:
                safe_terms.append(t)

        # 2. Run primary search
        expanded_terms = list(safe_terms)
        results = run_git_grep(
            expanded_terms,
            target,
            ws,
            case_insensitive=is_case_insensitive,
            max_matches=max_matches * 2,
        )

        pattern_display = (
            terms[0] if len(terms) == 1 else ", ".join(repr(t) for t in terms)
        )
        first_term = terms[0]

        # 3. Handle ZERO MATCHES
        if not results:
            other_locations_matches: List[OtherLocationMatch] = []
            copy_pasteable_commands: List[str] = []
            suggestions_list: List[str] = []

            # a) Narrow path filter check: check if pattern exists elsewhere in workspace
            if target != ws:
                ws_results = run_git_grep(
                    expanded_terms,
                    ws,
                    ws,
                    case_insensitive=is_case_insensitive,
                    max_matches=10,
                )
                if ws_results:
                    for r in ws_results[:5]:
                        parts = r.split(":", 2)
                        if len(parts) >= 2 and parts[1].isdigit():
                            other_locations_matches.append(
                                OtherLocationMatch(
                                    file=parts[0],
                                    lineno=int(parts[1]),
                                    content=parts[2] if len(parts) > 2 else "",
                                )
                            )
                    cmd = f'python3 grep.py "{first_term}"'
                    if cmd not in copy_pasteable_commands:
                        copy_pasteable_commands.append(cmd)
                    suggestions_list.append(
                        f"Search entire repository: pattern exists in other files outside '{target_display}'"
                    )

            # b) Run case-insensitive search if search was case-sensitive
            ci_matches: List[CaseInsensitiveMatch] = []
            if not is_case_insensitive:
                ci_results = run_git_grep(
                    expanded_terms,
                    target,
                    ws,
                    case_insensitive=True,
                    max_matches=15,
                )
                if not ci_results and target != ws:
                    ci_results = run_git_grep(
                        expanded_terms,
                        ws,
                        ws,
                        case_insensitive=True,
                        max_matches=15,
                    )
                for r in ci_results:
                    parts = r.split(":", 2)
                    if len(parts) >= 2 and parts[1].isdigit():
                        ci_matches.append(
                            CaseInsensitiveMatch(
                                file=parts[0],
                                lineno=int(parts[1]),
                                content=parts[2] if len(parts) > 2 else "",
                            )
                        )
                if ci_matches:
                    target_arg = (
                        f" {target_display.replace('/workspace/', '').replace('/workspace', '.')}"
                        if target != ws
                        else ""
                    )
                    cmd = f'python3 grep.py -i "{first_term}"{target_arg}'.strip()
                    if cmd not in copy_pasteable_commands:
                        copy_pasteable_commands.append(cmd)
                    suggestions_list.append(
                        f"Ignore case: {len(ci_matches)} matches found with -i / --ignore-case"
                    )

            # c) Test tokenized sub-terms if compound query failed
            subterm_summaries: List[SubtermMatchSummary] = []
            candidate_subterms = []
            if raw_phrase:
                candidate_subterms = extract_subterms(raw_phrase)
            for t in terms:
                for sub in extract_subterms(t):
                    if sub not in candidate_subterms:
                        candidate_subterms.append(sub)

            for sub in candidate_subterms[:6]:
                sub_res = run_git_grep(
                    [sub],
                    target,
                    ws,
                    case_insensitive=True,
                    max_matches=5,
                )
                if not sub_res and target != ws:
                    sub_res = run_git_grep(
                        [sub], ws, ws, case_insensitive=True, max_matches=5
                    )
                if sub_res:
                    first_p = sub_res[0].split(":", 2)
                    sf = first_p[0]
                    sl = (
                        int(first_p[1])
                        if len(first_p) > 1 and first_p[1].isdigit()
                        else None
                    )
                    subterm_summaries.append(
                        SubtermMatchSummary(
                            subterm=sub,
                            match_count=len(sub_res),
                            sample_file=sf,
                            sample_lineno=sl,
                        )
                    )
                    sub_cmd = f'python3 grep.py "{sub}"'
                    if sub_cmd not in copy_pasteable_commands:
                        copy_pasteable_commands.append(sub_cmd)

            # d) Extract candidate symbols from AST & repository identifiers
            symbols = extract_candidate_symbols(target, ws)
            fuzzy_suggestions = get_fuzzy_suggestions(
                terms, symbols, top_n=5, cutoff=0.35
            )
            for fs in fuzzy_suggestions[:2]:
                f_cmd = f'python3 grep.py "{fs.symbol}"'
                if f_cmd not in copy_pasteable_commands:
                    copy_pasteable_commands.append(f_cmd)

            # e) Find similar repository files
            similar_files = find_similar_workspace_files(
                raw_phrase or " ".join(terms), ws, max_results=4
            )
            for sf in similar_files[:2]:
                sf_cmd = f'python3 grep.py "{first_term}" {sf}'
                if sf_cmd not in copy_pasteable_commands:
                    copy_pasteable_commands.append(sf_cmd)

            if not copy_pasteable_commands:
                copy_pasteable_commands.append(
                    f'python3 grep.py -i "{first_term}"'
                )
                copy_pasteable_commands.append(f'python3 grep.py "{first_term}"')

            # Formulate structured explanation & result
            status = (
                "REGEX_ERROR"
                if regex_diagnostics and not safe_terms
                else "ZERO_MATCHES"
            )
            summary_msg = f"Zero matches found for pattern '{pattern_display}' across {total_files} files in {target_display}."
            explanation = MatchExplanation(
                status=status,
                summary=summary_msg,
                case_sensitive=not is_case_insensitive,
                case_insensitive_count=len(ci_matches),
                other_locations_count=len(other_locations_matches),
                details=(
                    f"Found {len(ci_matches)} case-insensitive matches. "
                    f"Found {len(other_locations_matches)} matches in other workspace files. "
                    f"Generated {len(fuzzy_suggestions)} fuzzy symbol suggestions. "
                    f"Tested {len(subterm_summaries)} subterm matches."
                ),
                skipped_extensions=sorted(list(SKIP_EXTENSIONS)),
                skipped_dirs=sorted(list(SKIP_DIRS)),
            )

            result = FastGrepResult(
                query_terms=terms,
                target_path=target_display,
                total_files_scanned=total_files,
                total_matches=0,
                explanation=explanation,
                regex_diagnostics=regex_diagnostics,
                case_insensitive_matches=ci_matches,
                other_locations_matches=other_locations_matches,
                fuzzy_suggestions=fuzzy_suggestions,
                subterm_matches=subterm_summaries,
                similar_files=similar_files,
                suggestions=suggestions_list,
                copy_pasteable_commands=copy_pasteable_commands,
                path_warning=path_warning_msg,
                ranked_matches=[],
                top_ast_nodes=[],
            )

            if is_json:
                print(result.model_dump_json(indent=2))
                return 0

            # Deterministic zero matches explanation
            print(f"[fast-grep] {summary_msg}\n")
            print(
                f"ℹ️ SEARCH CONSTRAINTS & DIAGNOSTICS:\n"
                f"  - Scanned: {total_files} files in {target_display}\n"
                f"  - Skipped non-code extensions: {', '.join(sorted(list(SKIP_EXTENSIONS))[:12])} ...\n"
                f"  - Skipped noise directories: {', '.join(sorted(list(SKIP_DIRS))[:10])} ...\n"
            )

            # 1. Path filter too narrow report
            if other_locations_matches:
                print(
                    f"💡 PATH FILTER TOO NARROW: 0 matches in '{target_display}', but {len(other_locations_matches)} match(es) exist elsewhere in the workspace:"
                )
                for om in other_locations_matches[:5]:
                    print(
                        f"  - {om.file}:{om.lineno}: {om.content.strip()[:80]}"
                    )
                print(
                    f'  Try searching without path filter: python3 grep.py "{first_term}"\n'
                )

            # 2. Case-insensitive report
            if ci_matches:
                print(
                    f'💡 0 exact matches, but {len(ci_matches)} matches exist with -i / --ignore-case! Try: python3 grep.py -i "{pattern_display}"'
                )
                for m in ci_matches[:6]:
                    print(f"  - {m.file}:{m.lineno}: {m.content.strip()[:80]}")
                if len(ci_matches) > 6:
                    print(
                        f"  ... (+{len(ci_matches) - 6} additional case-insensitive matches)"
                    )
                print()

            # 3. Tokenized sub-terms report
            if subterm_summaries:
                print("💡 COMPOUND QUERY FAILED — TOKENIZED SUB-TERM MATCHES:")
                print(
                    f"  The full query '{pattern_display}' had 0 exact matches, but sub-terms exist:"
                )
                for st in subterm_summaries:
                    loc = (
                        f" in {st.sample_file}:{st.sample_lineno}"
                        if st.sample_file
                        else ""
                    )
                    print(
                        f"  - '{st.subterm}': {st.match_count} match(es){loc}"
                    )
                print()

            # 4. Fuzzy symbol suggestions
            if fuzzy_suggestions:
                print("🔍 SIMILAR SYMBOLS IN WORKSPACE (from AST):")
                for s in fuzzy_suggestions[:5]:
                    loc = f" in {s.source_file}" if s.source_file else ""
                    print(
                        f"  - {s.symbol} ({s.kind}{loc}) [similarity: {s.similarity:.2f}]"
                    )
                print()

            # 5. Similar repository files
            if similar_files:
                print("📁 RELEVANT REPOSITORY FILES:")
                for rf in similar_files:
                    print(f"  - {rf}")
                print()

            # 6. Actionable next steps for LLM
            print("🚀 ACTIONABLE NEXT STEPS FOR LLM:")
            for idx, cmd in enumerate(copy_pasteable_commands, start=1):
                print(f"  {idx}. {cmd}")
            print()

            return 0

        # 4. Parse and rank MATCHES FOUND
        parsed: List[GrepMatch] = []
        for r in results:
            parts = r.split(":", 2)
            if len(parts) >= 2 and parts[1].isdigit():
                fp = parts[0]
                lineno = int(parts[1])
                content = parts[2] if len(parts) > 2 else ""

                scope_name = ""
                full_p = ws / fp
                if full_p.suffix == ".py" and full_p.exists():
                    tree, _ = get_ast_and_lines(full_p)
                    node = find_enclosing_node(tree, lineno)
                    if node:
                        scope_name = node.name

                sc = score_match(
                    fp, lineno, content, expanded_terms, scope_name=scope_name
                )
                is_def = bool(
                    not content.strip().startswith(
                        ("#", "//", "/*", "*", '"""', "'''")
                    )
                    and (
                        re.search(r"^\s*(async\s+def|def|class)\s+", content)
                        or re.search(r"^\s*@", content)
                    )
                )
                is_call_site = is_string_transform_line(content) and not is_def
                parsed.append(
                    GrepMatch(
                        file=fp,
                        lineno=lineno,
                        content=content,
                        score=sc,
                        scope_name=scope_name or None,
                        is_call_site=is_call_site,
                        is_definition=is_def,
                    )
                )

        parsed.sort(key=lambda m: m.score, reverse=True)
        ranked_matches = parsed[:max_matches]

        # Extract top 2 unique function scopes
        flashed: List[Tuple[GrepMatch, Dict[str, Any]]] = []
        seen = set()
        top_ast_nodes: List[ASTNodePreview] = []

        for m in ranked_matches:
            p = ws / m.file
            if not p.suffix == ".py" or not p.exists():
                continue
            scope = extract_function_scope(p, m.lineno)
            if scope:
                key = (m.file, scope["name"])
                if key not in seen:
                    seen.add(key)
                    flashed.append((m, scope))
                    top_ast_nodes.append(
                        ASTNodePreview(
                            name=scope["name"],
                            kind=scope["kind"],
                            file=m.file,
                            start_line=scope["start_line"],
                            end_line=scope["end_line"],
                            score=m.score,
                            code_snippet="\n".join(scope["lines"]),
                        )
                    )
                    if len(flashed) >= MAX_SCOPES_FLASHED:
                        break

        explanation = MatchExplanation(
            status="MATCHES_FOUND",
            summary=f"Found {len(parsed)} matches across {total_files} files in {target_display}.",
            case_sensitive=not is_case_insensitive,
            case_insensitive_count=0,
            other_locations_count=0,
            details=f"Top {len(flashed)} enclosing AST scopes flashed.",
            skipped_extensions=sorted(list(SKIP_EXTENSIONS)),
            skipped_dirs=sorted(list(SKIP_DIRS)),
        )

        result = FastGrepResult(
            query_terms=terms,
            target_path=target_display,
            total_files_scanned=total_files,
            total_matches=len(parsed),
            explanation=explanation,
            regex_diagnostics=regex_diagnostics,
            case_insensitive_matches=[],
            other_locations_matches=[],
            fuzzy_suggestions=[],
            subterm_matches=[],
            similar_files=[],
            suggestions=[],
            copy_pasteable_commands=[],
            path_warning=path_warning_msg,
            ranked_matches=ranked_matches,
            top_ast_nodes=top_ast_nodes,
        )

        if is_json:
            print(result.model_dump_json(indent=2))
            return 0

        # Output results concisely (capped under ADK context limit)
        terms_display = " | ".join(terms)
        print(
            f"[fast-grep] Search: '{terms_display}' ({len(parsed)} matches, top {len(flashed)} scopes flashed):\n"
        )

        for idx, (m, sc) in enumerate(flashed, start=1):
            fp = m.file
            s_name = sc["name"]
            s_line = sc["start_line"]
            e_line = sc["end_line"]
            lines = sc["lines"]
            target_lineno = m.lineno
            is_call_site = m.is_call_site
            is_def = m.is_definition
            is_transform_scope = sc.get("is_transform", False)

            scope_tag = ""
            if is_def and is_transform_scope:
                scope_tag = " [🎯 DEFINITION TARGET & TRANSFORM SCOPE]"
            elif is_def:
                scope_tag = " [🎯 DEFINITION TARGET]"
            elif is_transform_scope and is_call_site:
                scope_tag = " [⚡ STRING/BUFFER CALL-SITE & TRANSFORM SCOPE]"
            elif is_call_site:
                scope_tag = " [⚡ STRING/BUFFER CALL-SITE]"
            elif is_transform_scope:
                scope_tag = " [STRING/BUFFER TRANSFORM SCOPE]"

            print("=" * 80)
            print(
                f"[{idx}/{len(flashed)}] SCOPE: {s_name} ({sc['kind']}) in {fp}:{s_line}-{e_line}{scope_tag} [score: {m.score:+d}]"
            )
            print("=" * 80)

            def format_line(lineno: int, text: str) -> str:
                truncated_text = text[:300]
                if lineno == target_lineno:
                    if is_def:
                        callout = "  <-- [DEFINITION TARGET]"
                    elif is_call_site:
                        callout = (
                            "  <-- [CALL-SITE: string/buffer transform]"
                        )
                    else:
                        callout = "  <-- [MATCH]"
                    return f"{lineno:4d}: >>> {truncated_text}{callout}"
                return f"{lineno:4d}:     {truncated_text}"

            rel_idx = max(0, min(len(lines) - 1, target_lineno - s_line))
            half_before = max(5, int(context_window * 0.375))
            half_after = max(5, context_window - half_before)

            if len(lines) > (context_window + 5):
                w_start = max(0, rel_idx - half_before)
                w_end = min(len(lines), rel_idx + half_after)
                display_lines = lines[w_start:w_end]
                disp_start_lineno = s_line + w_start
                if w_start > 0:
                    print(
                        f"  ... [{w_start} lines before in {s_name} omitted] ..."
                    )
                for i, l in enumerate(display_lines, start=disp_start_lineno):
                    print(format_line(i, l))
                if w_end < len(lines):
                    print(
                        f"  ... [{len(lines) - w_end} lines after in {s_name} omitted] ..."
                    )
            else:
                display_lines = lines
                w_start = 0
                w_end = len(lines)
                for i, l in enumerate(lines, start=s_line):
                    print(format_line(i, l))

            # Primary top match clean unadorned code block
            if idx == 1:
                clean_snippet = "\n".join(lines[w_start:w_end])
                print("\n[CLEAN CODE FOR edit_file (EXACT INDENTATION)]:")
                print("```python")
                print(clean_snippet)
                print("```")
            print()

        # Summary of other ranked matches
        print("-" * 80)
        print("📋 TOP MATCH PREVIEWS:")
        for m in ranked_matches[:MAX_DISPLAY_PREVIEWS]:
            snippet = m.content.strip()[:75]
            if m.is_definition:
                site_tag = " [DEF]"
            elif m.is_call_site:
                site_tag = " [CALL-SITE]"
            else:
                site_tag = ""
            print(f"  [{m.score:+3d}] {m.file}:{m.lineno}{site_tag}: {snippet}")

        if len(parsed) > MAX_DISPLAY_PREVIEWS:
            print(
                f"  ... ({len(parsed) - MAX_DISPLAY_PREVIEWS} additional matches truncated)"
            )

        return 0
    except Exception as e:
        print(f"[fast-grep] Search completed with fallback: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
`````

## File: submission/skills/fast-grep/grep.py
`````python
#!/usr/bin/env python3
"""fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents.

Eats ANY input format:
- Single terms, compound phrases, multiple terms (searched as OR/union)
- Unescaped regex or literal code snippets (auto-fallback to literal substring on re.error)
- Dotted symbols, function calls, or raw keywords
- Forgiving CLI: positional args, -p/--pattern, -d/--dir, -i/--ignore-case, -w/--window, -m/--max-matches, --json
- Automatically skips benchmarks, lockfiles, docs, binary files, and noise directories
- Crash & loop immunity: bounded file reads (500KB, 5000 lines), symlink cycle protection, capped match output
- Deterministically explains zero matches with file count, narrow-path detection, and case-insensitive check
- Suggests candidate symbols from AST and repository identifiers via fuzzy matching
- Tokenizes compound phrases on failure and checks for sub-term presence
- Explains regex syntax errors in plain English and suggests escaped patterns
- 100% Pydantic v2 structured schemas (FastGrepResult, MatchExplanation, FuzzySuggestion, etc.)
- Flashes top 2 enclosing functions with complete decorators via AST
- Prioritizes function, method, and class definitions at the top of search rankings over call sites
- Boosts common string/buffer transformation methods & verbs
- Highlights call-sites and enclosing scopes where strings/buffers are transformed
- Automatically expands terse issue keywords to candidate string operations
- Detects non-existent paths, warns the LLM, suggests similar files, and falls back to workspace search
- Context-safe: Sliding context window centered on target line, clean code block for edit_file
- Always exits 0 and never crashes or hangs in runaway loops.
"""

from __future__ import annotations

import ast
import difflib
import os
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True

from pydantic import BaseModel, ConfigDict, Field

# ==============================================================================
# Pydantic v2 Output & Diagnostic Schemas
# ==============================================================================


class MatchExplanation(BaseModel):
    """Deterministic explanation for search outcome."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(
        ...,
        description="Outcome status: MATCHES_FOUND, ZERO_MATCHES, REGEX_ERROR, PATH_NOT_FOUND, or OVERVIEW",
    )
    summary: str = Field(
        ..., description="Human-readable summary of search result"
    )
    case_sensitive: bool = Field(
        default=True, description="Whether search was case-sensitive"
    )
    case_insensitive_count: int = Field(
        default=0, description="Count of matches found ignoring case"
    )
    other_locations_count: int = Field(
        default=0, description="Count of matches found outside target path"
    )
    details: Optional[str] = Field(
        default=None, description="Additional context or diagnostics"
    )
    skipped_extensions: List[str] = Field(
        default_factory=list, description="Extensions excluded from search"
    )
    skipped_dirs: List[str] = Field(
        default_factory=list, description="Directories excluded from search"
    )


class FuzzySuggestion(BaseModel):
    """AST / repository identifier fuzzy candidate suggestion."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., description="Original query term")
    symbol: str = Field(..., description="Candidate symbol identifier")
    similarity: float = Field(
        ..., description="Fuzzy match similarity score (0.0 to 1.0)"
    )
    kind: Optional[str] = Field(
        default="identifier",
        description="Symbol kind: function, class, variable, identifier",
    )
    source_file: Optional[str] = Field(
        default=None,
        description="Workspace-relative file path containing symbol",
    )


class SubtermMatchSummary(BaseModel):
    """Match summary for individual sub-terms of a failed compound query."""

    model_config = ConfigDict(extra="ignore")

    subterm: str = Field(..., description="Subterm token extracted from query")
    match_count: int = Field(..., description="Count of matches found for subterm")
    sample_file: Optional[str] = Field(
        default=None, description="Sample file containing subterm"
    )
    sample_lineno: Optional[int] = Field(
        default=None, description="Sample line number containing subterm"
    )


class RegexErrorDiagnostic(BaseModel):
    """Diagnostic detail for invalid regular expression pattern."""

    model_config = ConfigDict(extra="ignore")

    raw_pattern: str = Field(..., description="Raw invalid pattern string")
    error_message: str = Field(..., description="Underlying re.error message")
    position: Optional[int] = Field(
        default=None, description="Error position character offset"
    )
    plain_english_explanation: str = Field(
        ..., description="Plain-English explanation of syntax issue"
    )
    suggested_escaped_regex: str = Field(
        ..., description="Safe, properly escaped regex pattern"
    )


class CaseInsensitiveMatch(BaseModel):
    """Match line discovered when ignoring character casing."""

    model_config = ConfigDict(extra="ignore")

    file: str = Field(..., description="Workspace-relative file path")
    lineno: int = Field(..., description="1-based line number")
    content: str = Field(..., description="Matching line content preview")


class OtherLocationMatch(BaseModel):
    """Match line discovered in other repository files outside target path."""

    model_config = ConfigDict(extra="ignore")

    file: str = Field(..., description="Workspace-relative file path")
    lineno: int = Field(..., description="1-based line number")
    content: str = Field(..., description="Matching line content preview")


class GrepMatch(BaseModel):
    """Individual ranked match line."""

    model_config = ConfigDict(extra="ignore")

    file: str = Field(..., description="Workspace-relative file path")
    lineno: int = Field(..., description="1-based line number")
    content: str = Field(..., description="Matching line content")
    score: int = Field(default=0, description="Relevance ranking score")
    is_call_site: bool = Field(
        default=False, description="Whether line is an active transform call-site"
    )
    is_definition: bool = Field(
        default=False,
        description="Whether line is a function, method, or class definition signature",
    )
    scope_name: Optional[str] = Field(
        default=None, description="Enclosing function or class name"
    )


class ASTNodePreview(BaseModel):
    """Top-ranked enclosing AST function or class preview."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(
        ..., description="Scope display name (e.g. def foo, class Bar)"
    )
    kind: str = Field(..., description="Scope type: def or class")
    file: str = Field(..., description="Workspace-relative file path")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    score: int = Field(
        default=0, description="Match score associated with scope"
    )
    code_snippet: str = Field(
        ..., description="Complete or folded source code snippet"
    )


class FastGrepResult(BaseModel):
    """Top-level structured result returned by fast-grep."""

    model_config = ConfigDict(extra="ignore")

    query_terms: List[str] = Field(
        default_factory=list, description="Original query search terms"
    )
    target_path: str = Field(
        ..., description="Target search directory or file path"
    )
    total_files_scanned: int = Field(
        default=0, description="Count of files scanned in target"
    )
    total_matches: int = Field(
        default=0, description="Total matching lines found"
    )
    explanation: MatchExplanation = Field(
        ..., description="Match explanation and diagnostic summary"
    )
    regex_diagnostics: List[RegexErrorDiagnostic] = Field(
        default_factory=list, description="Regex syntax diagnostics"
    )
    case_insensitive_matches: List[CaseInsensitiveMatch] = Field(
        default_factory=list, description="Matches found ignoring case"
    )
    other_locations_matches: List[OtherLocationMatch] = Field(
        default_factory=list, description="Matches found in other workspace files"
    )
    fuzzy_suggestions: List[FuzzySuggestion] = Field(
        default_factory=list, description="Candidate symbol suggestions"
    )
    subterm_matches: List[SubtermMatchSummary] = Field(
        default_factory=list,
        description="Matches found for tokenized sub-terms of compound query",
    )
    similar_files: List[str] = Field(
        default_factory=list, description="Relevant workspace files"
    )
    suggestions: List[str] = Field(
        default_factory=list, description="Actionable query reformulation suggestions"
    )
    copy_pasteable_commands: List[str] = Field(
        default_factory=list, description="Copy-pasteable CLI commands for LLM next turn"
    )
    path_warning: Optional[str] = Field(
        default=None, description="Warning if target path was missing or corrected"
    )
    ranked_matches: List[GrepMatch] = Field(
        default_factory=list, description="Ranked match items"
    )
    top_ast_nodes: List[ASTNodePreview] = Field(
        default_factory=list, description="Top AST scope previews"
    )


# ==============================================================================
# Constants & Safety Limits
# ==============================================================================

MAX_FILE_SIZE_BYTES: int = 500_000   # 500 KB limit to prevent OOM on giant dumps
MAX_LINES_PER_FILE: int = 5_000      # Max lines to scan per file
MAX_LINE_LENGTH: int = 1_000         # Max chars per line inspected (prevents ReDoS/OOM)
MAX_RAW_MATCHES: int = 200           # Circuit breaker on raw git/python grep matches
MAX_RANKED_MATCHES: int = 50         # Max ranked matches kept in result
MAX_DISPLAY_PREVIEWS: int = 15       # Max previews shown in console summary
MAX_SCOPES_FLASHED: int = 2          # Top enclosing AST scopes flashed

SKIP_DIRS: Set[str] = {
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
    "wheels",
    "snapshots",
    "benchmarks",
    "benchmark",
    "results",
    "docs",
    "doc",
    "htmlcov",
    "site-packages",
    "embeddings",
    ".adk_exec",
    ".eggs",
    ".beads",
    ".idea",
    ".vscode",
}

SKIP_EXTENSIONS: Set[str] = {
    ".lock",
    ".bin",
    ".tar",
    ".gz",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".ico",
    ".pyc",
    ".safetensors",
    ".whl",
    ".json",
    ".jsonl",
    ".npz",
    ".npy",
    ".csv",
    ".log",
    ".xml",
    ".txt",
    ".yaml",
    ".yml",
    ".md",
    ".rst",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".wasm",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".parquet",
    ".pkl",
    ".pickle",
    ".pdf",
    ".ttf",
    ".woff",
    ".woff2",
    ".eot",
}

STRING_TRANSFORM_VERBS: Set[str] = {
    "splitlines",
    "split",
    "rstrip",
    "strip",
    "lstrip",
    "replace",
    "join",
    "partition",
    "rpartition",
    "decode",
    "encode",
    "from_ansi",
}

PYTHON_KEYWORDS: Set[str] = {
    "False",
    "None",
    "True",
    "and",
    "as",
    "assert",
    "async",
    "await",
    "break",
    "class",
    "continue",
    "def",
    "del",
    "elif",
    "else",
    "except",
    "finally",
    "for",
    "from",
    "global",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "nonlocal",
    "not",
    "or",
    "pass",
    "raise",
    "return",
    "try",
    "while",
    "with",
    "yield",
}

COMMON_STOPWORDS: Set[str] = {
    "the",
    "a",
    "an",
    "in",
    "on",
    "of",
    "to",
    "for",
    "with",
    "at",
    "by",
    "from",
    "into",
    "is",
    "are",
    "was",
    "were",
    "it",
    "this",
    "that",
    "these",
    "those",
    "be",
    "been",
    "has",
    "have",
    "had",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "not",
    "no",
    "but",
    "and",
    "or",
    "as",
    "if",
}

_AST_CACHE: Dict[str, Tuple[Optional[ast.AST], List[str]]] = {}


# ==============================================================================
# Binary & Symlink Safety Checks
# ==============================================================================


def is_binary_file(path: pathlib.Path) -> bool:
    """Detect if file is binary by extension or null byte inspection."""
    if any(path.name.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            if b"\0" in chunk:
                return True
    except Exception:
        return True
    return False


# ==============================================================================
# AST & Scope Inspection Helpers
# ==============================================================================


def get_ast_and_lines(
    full_path: pathlib.Path,
) -> Tuple[Optional[ast.AST], List[str]]:
    """Parse and cache AST and source lines for a python file, skipping gigantic or binary files."""
    try:
        real_p = full_path.resolve()
        key = str(real_p)
    except Exception:
        key = str(full_path)

    if key in _AST_CACHE:
        return _AST_CACHE[key]

    try:
        st = full_path.stat()
        if st.st_size > MAX_FILE_SIZE_BYTES or st.st_size == 0:
            _AST_CACHE[key] = (None, [])
            return (None, [])
        if is_binary_file(full_path):
            _AST_CACHE[key] = (None, [])
            return (None, [])
        text = full_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()[:MAX_LINES_PER_FILE]
        tree = ast.parse("\n".join(lines), filename=key)
        _AST_CACHE[key] = (tree, lines)
        return (tree, lines)
    except Exception:
        _AST_CACHE[key] = (None, [])
        return (None, [])


def find_enclosing_node(
    tree: Optional[ast.AST], target_line: int
) -> Optional[Any]:
    """Find innermost function or class enclosing target_line."""
    if not tree:
        return None
    best_node = None
    best_span = float("inf")
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            s = getattr(node, "lineno", None)
            e = getattr(node, "end_lineno", None)
            if s is not None and e is not None and s <= target_line <= e:
                span = e - s
                if span < best_span:
                    best_span = span
                    best_node = node
    return best_node


def is_string_transform_line(content: str) -> bool:
    """Detect if content is an active call-site or statement transforming strings/buffers."""
    c = content
    if re.search(
        r"\.\s*(splitlines|split|rstrip|strip|lstrip|replace|join|partition|rpartition|decode|encode|from_ansi)\s*\(",
        c,
        re.IGNORECASE,
    ):
        return True
    if re.search(
        r"\b(text|line|lines|terminal_text|buffer|output|input|data|content|string|val|raw|payload|chunk|stream|body|msg)\w*\s*\.\s*(splitlines|split|rstrip|strip|lstrip|replace|join|partition|rpartition|decode|encode|from_ansi)\b",
        c,
        re.IGNORECASE,
    ):
        return True
    if re.search(r"\bre\.(split|sub|finditer|findall)\s*\(", c):
        return True
    return False


def is_string_transform_scope(scope_name: str, lines: List[str]) -> bool:
    """Detect if enclosing function or class is dedicated to string/buffer manipulation."""
    s_lower = scope_name.lower()
    if any(v in s_lower for v in STRING_TRANSFORM_VERBS):
        return True
    if any(
        w in s_lower
        for w in ("ansi", "text", "buffer", "decode", "encode", "line", "codec")
    ):
        return True
    for line in lines[:200]:
        if is_string_transform_line(line):
            return True
    return False


def get_workspace_dir() -> pathlib.Path:
    """Deterministically locate the active repository workspace."""
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / ".git").exists()
                    or (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR", "WORKSPACE"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    ws = pathlib.Path("/workspace")
    if ws.is_dir():
        return ws.resolve()

    return pathlib.Path.cwd().resolve()


def clean_search_term(raw: str) -> str:
    """Normalize terms without destroying useful symbols."""
    cleaned = raw.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()
    if cleaned.startswith("`") and cleaned.endswith("`"):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def extract_subterms(phrase: str) -> List[str]:
    """Extract significant non-stopword identifier tokens from a compound query."""
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", phrase)
    subterms: List[str] = []
    for w in words:
        w_clean = w.strip()
        w_lower = w_clean.lower()
        if (
            len(w_clean) >= 3
            and w_lower not in PYTHON_KEYWORDS
            and w_lower not in COMMON_STOPWORDS
            and w_clean not in subterms
        ):
            subterms.append(w_clean)
    return subterms


def find_similar_workspace_files(
    query_str: str, ws: pathlib.Path, max_results: int = 5
) -> List[str]:
    """Find repository files matching or closely resembling query identifiers."""
    all_files: List[str] = []
    try:
        if (ws / ".git").exists():
            res = subprocess.run(
                ["git", "ls-files", ":(exclude)*.adk_exec*"],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res.returncode == 0:
                all_files = [
                    f
                    for f in res.stdout.splitlines()
                    if f.endswith(".py")
                    and not any(d in f for d in SKIP_DIRS)
                ]
    except Exception:
        pass

    if not all_files:
        try:
            for root, dirs, files in os.walk(ws, followlinks=False):
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in SKIP_DIRS
                    and not d.startswith(".")
                    and not (".adk_exec" in d or d.startswith(".adk_exec"))
                ]
                for f in files:
                    if f.endswith(".py"):
                        full_p = pathlib.Path(root) / f
                        try:
                            all_files.append(str(full_p.relative_to(ws)))
                        except ValueError:
                            all_files.append(str(full_p))
                if len(all_files) > 1000:
                    break
        except Exception:
            pass

    if not all_files:
        return []

    matches: List[str] = []
    tokens = [t.lower() for t in extract_subterms(query_str)]
    if not tokens:
        tokens = [query_str.lower()]

    for f in all_files:
        f_lower = f.lower()
        stem = pathlib.Path(f).stem.lower()
        if any(t == stem for t in tokens):
            if f not in matches:
                matches.append(f)
        elif any(t in f_lower for t in tokens if len(t) >= 4):
            if f not in matches:
                matches.append(f)
        if len(matches) >= max_results:
            return matches

    filenames = [pathlib.Path(f).name for f in all_files]
    for tok in tokens:
        close = difflib.get_close_matches(tok, filenames, n=3, cutoff=0.5)
        for c in close:
            for f in all_files:
                if pathlib.Path(f).name == c and f not in matches:
                    matches.append(f)
                    if len(matches) >= max_results:
                        return matches

    return matches[:max_results]


# ==============================================================================
# Argument Parsing (Omnivorous, Forgiving CLI)
# ==============================================================================


def looks_like_path(val: str) -> bool:
    """Heuristic to check if an argument was meant as a path."""
    if val in (".", "./", "/workspace", "/workspace/", "..", "../"):
        return True
    if val.startswith(("/", "./", "../", "~/")):
        return True
    if "/" in val or "\\" in val:
        return True
    if any(
        val.endswith(ext)
        for ext in (
            ".py",
            ".pyi",
            ".toml",
            ".json",
            ".md",
            ".txt",
            ".yaml",
            ".yml",
            ".rst",
            ".html",
            ".sh",
            ".c",
            ".h",
            ".cpp",
        )
    ):
        return True
    return False


def resolve_target_path(val: str, ws: pathlib.Path) -> Optional[pathlib.Path]:
    """Resolve a path string relative to ws or absolute if exists, or None if non-existent."""
    if val in (".", "./", "/workspace", "/workspace/"):
        return ws
    cand = ws / val.lstrip("/")
    if cand.exists():
        return cand
    cand_direct = pathlib.Path(val).resolve()
    if cand_direct.exists():
        return cand_direct
    return None


def parse_args(
    args: List[str], ws: pathlib.Path
) -> Tuple[
    List[str],          # terms
    pathlib.Path,       # target_path
    bool,               # is_json
    bool,               # is_help
    bool,               # is_case_insensitive
    int,                # context_window
    int,                # max_matches
    Optional[str],      # invalid_target
    Optional[str],      # raw_phrase
    bool,               # is_overview
]:
    """Extract search terms, target directory/file, and flags with forgiving tolerance."""
    terms: List[str] = []
    target_path = ws
    is_json = False
    is_help = False
    is_case_insensitive = False
    context_window = 40  # default 40 lines (15 before, 25 after)
    max_matches = 50
    invalid_target: Optional[str] = None
    raw_phrase: Optional[str] = None
    explicit_target = False
    explicit_terms = False
    positional_args: List[str] = []

    i = 0
    while i < len(args):
        a = args[i].strip()
        if not a:
            i += 1
            continue

        if a in ("--help", "-h"):
            is_help = True
            i += 1
            continue

        if a == "--json":
            is_json = True
            i += 1
            continue

        if a in ("-i", "--ignore-case", "-case-insensitive", "--case-insensitive"):
            is_case_insensitive = True
            i += 1
            continue

        # -p or --pattern or -q or --query
        if a in ("--pattern", "-p", "--query", "-q"):
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                val = clean_search_term(args[i])
                if val:
                    terms.append(val)
                    explicit_terms = True
                    if not raw_phrase:
                        raw_phrase = val
            i += 1
            continue

        if any(
            a.startswith(prefix)
            for prefix in ("--pattern=", "-p=", "--query=", "-q=")
        ):
            val = clean_search_term(a.split("=", 1)[1])
            if val:
                terms.append(val)
                explicit_terms = True
                if not raw_phrase:
                    raw_phrase = val
            i += 1
            continue

        # -d or --dir or --path
        if a in ("--dir", "-d", "--path"):
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                dir_val = clean_search_term(args[i])
                if dir_val:
                    target_cand = resolve_target_path(dir_val, ws)
                    if target_cand is not None:
                        target_path = target_cand
                    else:
                        invalid_target = dir_val
                    explicit_target = True
            i += 1
            continue

        if any(a.startswith(prefix) for prefix in ("--dir=", "-d=", "--path=")):
            dir_val = clean_search_term(a.split("=", 1)[1])
            if dir_val:
                target_cand = resolve_target_path(dir_val, ws)
                if target_cand is not None:
                    target_path = target_cand
                else:
                    invalid_target = dir_val
                explicit_target = True
            i += 1
            continue

        # -w, --window, -c, --context
        if a in ("--window", "-w", "--context", "-c"):
            if i + 1 < len(args) and (
                args[i + 1].isdigit()
                or (args[i + 1].startswith("-") and args[i + 1][1:].isdigit())
            ):
                i += 1
                try:
                    context_window = max(5, min(200, int(args[i])))
                except ValueError:
                    pass
            i += 1
            continue

        if any(
            a.startswith(prefix)
            for prefix in ("--window=", "-w=", "--context=", "-c=")
        ):
            try:
                context_window = max(5, min(200, int(a.split("=", 1)[1])))
            except ValueError:
                pass
            i += 1
            continue

        # -m, --max-matches
        if a in ("--max-matches", "-m"):
            if i + 1 < len(args) and args[i + 1].isdigit():
                i += 1
                try:
                    max_matches = max(1, min(500, int(args[i])))
                except ValueError:
                    pass
            i += 1
            continue

        if any(a.startswith(prefix) for prefix in ("--max-matches=", "-m=")):
            try:
                max_matches = max(1, min(500, int(a.split("=", 1)[1])))
            except ValueError:
                pass
            i += 1
            continue

        # Otherwise it's a positional argument
        cleaned = clean_search_term(a)
        if cleaned:
            positional_args.append(cleaned)
        i += 1

    # Resolve positional arguments
    is_overview = False

    if explicit_terms:
        # User explicitly passed terms via -p/-q; any positional arg is candidate target path
        if not explicit_target and positional_args:
            pos_target = positional_args[0]
            cand = resolve_target_path(pos_target, ws)
            if cand is not None:
                target_path = cand
            else:
                invalid_target = pos_target
    else:
        # Terms were not passed via flags
        if len(positional_args) == 0:
            is_overview = True
        elif len(positional_args) == 1:
            arg = positional_args[0]
            if arg in (".", "./", "/workspace", "/workspace/"):
                is_overview = True
                target_path = ws
            else:
                # Single term search across target
                terms.append(arg)
                raw_phrase = arg
        elif len(positional_args) == 2:
            arg0, arg1 = positional_args[0], positional_args[1]
            if not explicit_target:
                target_cand = resolve_target_path(arg1, ws)
                if target_cand is not None:
                    terms.append(arg0)
                    raw_phrase = arg0
                    target_path = target_cand
                elif looks_like_path(arg1):
                    terms.append(arg0)
                    raw_phrase = arg0
                    invalid_target = arg1
                else:
                    # Multi-term union search across workspace
                    terms.extend([arg0, arg1])
                    raw_phrase = f"{arg0} {arg1}"
            else:
                terms.extend([arg0, arg1])
                raw_phrase = f"{arg0} {arg1}"
        else:
            # >= 3 positional arguments
            if not explicit_target:
                last_arg = positional_args[-1]
                target_cand = resolve_target_path(last_arg, ws)
                if target_cand is not None:
                    target_path = target_cand
                    terms.extend(positional_args[:-1])
                    raw_phrase = " ".join(positional_args[:-1])
                elif looks_like_path(last_arg):
                    invalid_target = last_arg
                    terms.extend(positional_args[:-1])
                    raw_phrase = " ".join(positional_args[:-1])
                else:
                    terms.extend(positional_args)
                    raw_phrase = " ".join(positional_args)
            else:
                terms.extend(positional_args)
                raw_phrase = " ".join(positional_args)

    return (
        terms,
        target_path,
        is_json,
        is_help,
        is_case_insensitive,
        context_window,
        max_matches,
        invalid_target,
        raw_phrase,
        is_overview,
    )


# ==============================================================================
# Regex Diagnostics & Symbol Extraction
# ==============================================================================


def escape_regex_metachars(pattern: str) -> str:
    """Escape regex special characters while preserving readable spaces and alphanumeric words."""
    escaped = re.escape(pattern)
    try:
        re.compile(escaped)
        return escaped
    except re.error:
        return re.sub(r"([()\[\]{}*+?|^$\\.])", r"\\\1", pattern)


def check_regex_syntax(pattern: str) -> Optional[RegexErrorDiagnostic]:
    """Validate regex pattern and produce plain-English diagnostic if invalid."""
    try:
        re.compile(pattern)
        return None
    except re.error as e:
        msg = str(e)
        pos = getattr(e, "pos", None)
        msg_lower = msg.lower()

        if (
            "missing ), unterminated subpattern" in msg_lower
            or "unbalanced parenthesis" in msg_lower
        ):
            plain_english = (
                f"Unclosed opening parenthesis '(' at position {pos if pos is not None else 'unknown'}. "
                "In regex, '(' starts a group. To match literal '(', escape it as '\\('."
            )
        elif "missing (" in msg_lower or "unmatched )" in msg_lower:
            plain_english = (
                f"Unmatched closing parenthesis ')' at position {pos if pos is not None else 'unknown'}. "
                "To match literal ')', escape it as '\\)'."
            )
        elif (
            "unterminated character set" in msg_lower
            or "missing ]" in msg_lower
        ):
            plain_english = (
                f"Unclosed character set bracket '[' at position {pos if pos is not None else 'unknown'}. "
                "To match literal '[', escape it as '\\['."
            )
        elif "missing [" in msg_lower or "unmatched ]" in msg_lower:
            plain_english = (
                f"Unmatched closing bracket ']' at position {pos if pos is not None else 'unknown'}. "
                "To match literal ']', escape it as '\\]'."
            )
        elif "nothing to repeat" in msg_lower:
            plain_english = (
                f"Dangling quantifier (*, +, ?, or {{}}) at position {pos if pos is not None else 'unknown'} "
                "without preceding character or token. To match literal quantifier, escape with '\\'."
            )
        elif "multiple repeat" in msg_lower:
            plain_english = (
                f"Consecutive repeat operators at position {pos if pos is not None else 'unknown'}. "
                "To match literal symbols, escape with '\\'."
            )
        elif "bad escape" in msg_lower or "incomplete escape" in msg_lower:
            plain_english = (
                f"Invalid or incomplete escape sequence at position {pos if pos is not None else 'unknown'}. "
                "Ensure backslashes are properly paired or escape literal backslashes as '\\\\'."
            )
        elif "bad character range" in msg_lower:
            plain_english = (
                f"Invalid character range in brackets at position {pos if pos is not None else 'unknown'} (e.g. [z-a]). "
                "Start character must be <= end character."
            )
        else:
            plain_english = (
                f"Regular expression syntax error ({msg}) at position {pos if pos is not None else 'unknown'}. "
                "Check pattern syntax or escape special characters with '\\'."
            )

        suggested = escape_regex_metachars(pattern)
        return RegexErrorDiagnostic(
            raw_pattern=pattern,
            error_message=msg,
            position=pos,
            plain_english_explanation=plain_english,
            suggested_escaped_regex=suggested,
        )


def count_files_in_target(target: pathlib.Path, ws: pathlib.Path) -> int:
    """Accurately count searchable files in target directory with loop safeguards."""
    if (ws / ".git").exists():
        try:
            rel = "."
            if target != ws:
                try:
                    rel = str(target.relative_to(ws))
                except ValueError:
                    rel = str(target)
            res = subprocess.run(
                [
                    "git",
                    "ls-files",
                    rel,
                    ":(exclude)*.adk_exec*",
                    ":(exclude)**/.adk_exec*",
                ],
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                files = [
                    f
                    for f in res.stdout.splitlines()
                    if f.strip()
                    and not (
                        ".adk_exec" in f or f.startswith(".adk_exec")
                    )
                ]
                if files:
                    return len(files)
        except Exception:
            pass

    count = 0
    try:
        for root, dirs, files in os.walk(target, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if d not in SKIP_DIRS
                and not d.startswith(".")
                and not (".adk_exec" in d or d.startswith(".adk_exec"))
            ]
            count += len(
                [
                    f
                    for f in files
                    if not any(f.endswith(ext) for ext in SKIP_EXTENSIONS)
                    and not (".adk_exec" in f or f.startswith(".adk_exec"))
                ]
            )
            if count >= 50000:
                break
    except Exception:
        pass
    return max(count, 1)


def extract_candidate_symbols(
    target: pathlib.Path, ws: pathlib.Path, max_files: int = 150
) -> Dict[str, Tuple[str, str]]:
    """Extract symbol names and kinds from AST and source code in the repository."""
    symbols: Dict[str, Tuple[str, str]] = {}
    search_root = target if target.is_dir() else ws
    scanned_files = 0

    try:
        for root, dirs, files in os.walk(search_root, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if d not in SKIP_DIRS
                and not d.startswith(".")
                and not (".adk_exec" in d or d.startswith(".adk_exec"))
                and "test" not in d.lower()
                and ("doc" not in d.lower() or "docs_src" in d.lower())
            ]
            for f in files:
                if ".adk_exec" in f or f.startswith(".adk_exec"):
                    continue
                if not f.endswith(".py"):
                    continue
                scanned_files += 1
                if scanned_files > max_files:
                    break
                full_p = pathlib.Path(root) / f
                try:
                    rel_p = str(full_p.relative_to(ws))
                except ValueError:
                    rel_p = str(full_p)

                try:
                    if full_p.stat().st_size > MAX_FILE_SIZE_BYTES:
                        continue
                except OSError:
                    continue

                tree, lines = get_ast_and_lines(full_p)
                if tree:
                    for node in ast.walk(tree):
                        if isinstance(
                            node, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ):
                            if node.name not in symbols:
                                symbols[node.name] = ("function", rel_p)
                        elif isinstance(node, ast.ClassDef):
                            if node.name not in symbols:
                                symbols[node.name] = ("class", rel_p)
                        elif isinstance(node, ast.Name) and isinstance(
                            node.ctx, ast.Store
                        ):
                            if (
                                node.id not in symbols
                                and node.id not in PYTHON_KEYWORDS
                                and len(node.id) > 2
                            ):
                                symbols[node.id] = ("variable", rel_p)

                for line in lines[:300]:
                    tokens = re.findall(
                        r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", line[:200]
                    )
                    for tok in tokens:
                        if tok not in symbols and tok not in PYTHON_KEYWORDS:
                            symbols[tok] = ("identifier", rel_p)

                if len(symbols) >= 1000:
                    break

            if scanned_files > max_files or len(symbols) >= 1000:
                break
    except Exception:
        pass

    return symbols


def get_fuzzy_suggestions(
    query_terms: List[str],
    candidate_symbols: Dict[str, Tuple[str, str]],
    top_n: int = 5,
    cutoff: float = 0.35,
) -> List[FuzzySuggestion]:
    """Find closest matching candidate symbols via fuzzy ratio matching."""
    scored: List[Tuple[float, str, str, str, str]] = []
    seen: Set[str] = set()

    for term in query_terms:
        words = [
            w
            for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", term)
            if len(w) > 2 and w.lower() not in PYTHON_KEYWORDS
        ]
        if not words:
            words = [term]

        for cand, (kind, fpath) in candidate_symbols.items():
            s1 = difflib.SequenceMatcher(None, term, cand).ratio()
            s2 = difflib.SequenceMatcher(
                None, term.lower(), cand.lower()
            ).ratio()
            best = max(s1, s2 * 0.95)

            for w in words:
                w1 = difflib.SequenceMatcher(None, w, cand).ratio()
                w2 = difflib.SequenceMatcher(
                    None, w.lower(), cand.lower()
                ).ratio()
                best = max(best, w1, w2 * 0.95)

            if best >= cutoff:
                scored.append((best, cand, kind, fpath, term))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: List[FuzzySuggestion] = []
    for best, cand, kind, fpath, term in scored:
        if cand not in seen:
            seen.add(cand)
            results.append(
                FuzzySuggestion(
                    query=term,
                    symbol=cand,
                    similarity=round(best, 3),
                    kind=kind,
                    source_file=fpath,
                )
            )
            if len(results) >= top_n:
                break

    return results


# ==============================================================================
# Search Execution & Scoring
# ==============================================================================


def run_git_grep(
    terms: List[str],
    target: pathlib.Path,
    ws: pathlib.Path,
    case_insensitive: bool = False,
    max_matches: int = MAX_RAW_MATCHES,
) -> List[str]:
    """Execute git grep with extended regex and literal fallback, with path exclusions."""
    if not (ws / ".git").exists():
        return python_walk_fallback(
            terms,
            target,
            ws,
            case_insensitive=case_insensitive,
            max_matches=max_matches,
        )

    safe_regex_terms: List[str] = []
    for t in terms:
        diag = check_regex_syntax(t)
        if diag:
            safe_regex_terms.append(diag.suggested_escaped_regex)
        else:
            safe_regex_terms.append(t)

    combined_pattern = (
        "|".join(safe_regex_terms)
        if len(safe_regex_terms) > 1
        else safe_regex_terms[0]
    )

    rel_target = "."
    if target != ws:
        try:
            rel_target = str(target.relative_to(ws))
        except ValueError:
            rel_target = str(target)

    path_args = [rel_target]
    for d in SKIP_DIRS:
        path_args.append(f":(exclude){d}/**")
        path_args.append(f":(exclude)**/{d}/**")
    for ext in SKIP_EXTENSIONS:
        path_args.append(f":(exclude)*{ext}")
        path_args.append(f":(exclude)**/*{ext}")
    path_args.append(":(exclude)*.adk_exec*")
    path_args.append(":(exclude)**/.adk_exec*")

    # 1. Try extended regex (-E)
    cmd = ["git", "grep", "-n", "-I"]
    if case_insensitive:
        cmd.append("-i")
    cmd.extend(["-E", "-e", combined_pattern, "--"] + path_args)

    try:
        res = subprocess.run(
            cmd,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            clean_lines = []
            for line in res.stdout.splitlines():
                if not line.strip():
                    continue
                matched_file = line.split(":", 1)[0]
                if (
                    ".adk_exec" in matched_file
                    or matched_file.startswith(".adk_exec")
                ):
                    continue
                clean_lines.append(line)
                if len(clean_lines) >= max_matches:
                    break
            if clean_lines:
                return clean_lines
    except Exception:
        pass

    # 2. Fallback to fixed-strings (-F) for each raw term
    all_lines: List[str] = []
    for t in terms:
        cmd_fixed = ["git", "grep", "-n", "-I"]
        if case_insensitive:
            cmd_fixed.append("-i")
        cmd_fixed.extend(["-F", "-e", t, "--"] + path_args)
        try:
            res = subprocess.run(
                cmd_fixed,
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.splitlines():
                    if not line.strip():
                        continue
                    matched_file = line.split(":", 1)[0]
                    if (
                        ".adk_exec" in matched_file
                        or matched_file.startswith(".adk_exec")
                    ):
                        continue
                    if line not in all_lines:
                        all_lines.append(line)
                    if len(all_lines) >= max_matches:
                        break
        except Exception:
            pass
        if len(all_lines) >= max_matches:
            break

    if all_lines:
        return all_lines

    # 3. Fallback to python walk if git grep failed or was empty
    return python_walk_fallback(
        terms,
        target,
        ws,
        case_insensitive=case_insensitive,
        max_matches=max_matches,
    )


def python_walk_fallback(
    terms: List[str],
    target: pathlib.Path,
    ws: pathlib.Path,
    case_insensitive: bool = False,
    max_matches: int = MAX_RAW_MATCHES,
) -> List[str]:
    """Pure-python fallback scanner with loop, symlink, giant-file, and ReDoS safeguards."""
    matches: List[str] = []
    flags = re.IGNORECASE if case_insensitive else 0
    compiled: List[re.Pattern] = []
    raw_substrings: List[str] = []

    for t in terms:
        try:
            compiled.append(re.compile(t, flags))
        except re.error:
            try:
                compiled.append(re.compile(escape_regex_metachars(t), flags))
            except re.error:
                pass
        raw_substrings.append(t.lower() if case_insensitive else t)

    search_root = (
        target
        if target.is_dir()
        else (target.parent if target.is_file() else ws)
    )
    visited_inodes: Set[Tuple[int, int]] = set()

    file_list: List[pathlib.Path] = []
    if target.is_file():
        file_list = [target]
    else:
        try:
            for root, dirs, files in os.walk(search_root, followlinks=False):
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in SKIP_DIRS
                    and not d.startswith(".")
                    and not (".adk_exec" in d or d.startswith(".adk_exec"))
                ]
                for f in sorted(files):
                    if ".adk_exec" in f or f.startswith(".adk_exec"):
                        continue
                    if any(f.endswith(ext) for ext in SKIP_EXTENSIONS):
                        continue
                    file_list.append(pathlib.Path(root) / f)
                    if len(file_list) >= 50_000:
                        break
                if len(file_list) >= 50_000:
                    break
        except Exception:
            pass

    for full_p in file_list:
        try:
            st = full_p.stat()
            inode_key = (st.st_dev, st.st_ino)
            if inode_key in visited_inodes:
                continue
            visited_inodes.add(inode_key)

            if st.st_size > MAX_FILE_SIZE_BYTES or st.st_size == 0:
                continue
            if is_binary_file(full_p):
                continue
        except OSError:
            continue

        try:
            rel_p = str(full_p.relative_to(ws))
        except ValueError:
            rel_p = str(full_p)

        try:
            with open(full_p, "r", encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if lineno > MAX_LINES_PER_FILE:
                        break
                    line_trunc = line[:MAX_LINE_LENGTH]
                    matched = False

                    for pattern in compiled:
                        try:
                            if pattern.search(line_trunc):
                                matched = True
                                break
                        except Exception:
                            pass

                    if not matched:
                        line_check = (
                            line_trunc.lower()
                            if case_insensitive
                            else line_trunc
                        )
                        for sub in raw_substrings:
                            if sub in line_check:
                                matched = True
                                break

                    if matched:
                        matches.append(
                            f"{rel_p}:{lineno}:{line.rstrip()[:400]}"
                        )
                        if len(matches) >= max_matches:
                            return matches
        except Exception:
            continue

    return matches


def score_match(
    file_path: str,
    lineno: int,
    content: str,
    terms: List[str],
    scope_name: str = "",
) -> int:
    """Calculate relevance score prioritizing core definitions and source code."""
    score = 0
    p_lower = file_path.lower()
    c = content.strip()

    # Prefer python source files
    if file_path.endswith(".py"):
        score += 30
    elif file_path.endswith((".pyi", ".toml")):
        score += 10

    # Demote tests and docs (exempt executable tutorial code in docs_src/*.py)
    if "test" in p_lower:
        score -= 40
    is_docs_src_py = "docs_src" in p_lower and file_path.endswith(".py")
    if not is_docs_src_py and (
        "doc" in p_lower or file_path.endswith((".md", ".rst"))
    ):
        score -= 40
    if "bench" in p_lower or "example" in p_lower:
        score -= 50

    # Priority Tier 1: Function, method, and class definitions
    is_code = not c.startswith(("#", "//", "/*", "*", '"""', "'''"))
    if is_code:
        if re.search(r"\b(async\s+def|def|class)\s+", content):
            score += 60
        elif "@" in content:
            score += 30

        sig_match = re.search(
            r"^\s*(async\s+def|def|class)\s+([A-Za-z0-9_]+)", content
        )
        if sig_match:
            score += 60
            sym_name = sig_match.group(2).lower()
            for t in terms:
                cleaned_t = t.strip().lower()
                if not cleaned_t:
                    continue
                if cleaned_t == sym_name:
                    score += 75
                    break
                elif cleaned_t in sym_name:
                    score += 50
                    break
        elif re.search(r"^\s*@", content):
            score += 30

    if "=" in content and not content.strip().startswith("#"):
        score += 10

    # String & Buffer transform verb boosting
    if is_string_transform_line(content):
        score += 40

    # High-relevance call-site patterns
    if re.search(
        r"\b\w+\.(splitlines|split|rstrip|strip|replace|join|partition|decode|encode)\(",
        content,
    ):
        score += 30

    # Streaming/iteration or line generator patterns
    if (
        re.search(r"for\s+\w+\s+in\s+.*(splitlines|split|partition)", c)
        or "yield" in c
    ):
        score += 20

    # Demote assertion-only and length inspection lines
    if re.search(r"\b(len|assert)\s*\(", c):
        score -= 25

    # Boost string/text-processing modules
    if re.search(
        r"(\b|_)(ansi|text|codec|decode|encode|string|parser|format|stream)(\b|\.py)",
        file_path,
        re.IGNORECASE,
    ):
        score += 25

    # Scope boost if enclosing function/class transforms strings/buffers
    if scope_name:
        scope_lower = scope_name.lower()
        if any(v in scope_lower for v in STRING_TRANSFORM_VERBS):
            score += 25
        if any(
            w in scope_lower
            for w in ("ansi", "text", "buffer", "decode", "encode")
        ):
            score += 20

    for t in terms:
        cleaned_t = t.strip()
        if not cleaned_t:
            continue
        if re.match(r"^[A-Za-z0-9_]+$", cleaned_t):
            if re.search(rf"\b{re.escape(cleaned_t)}\b", content, re.IGNORECASE):
                score += 15
        else:
            if cleaned_t.lower() in content.lower():
                score += 15

    return score


def extract_function_scope(
    full_path: pathlib.Path, target_line: int
) -> Optional[Dict[str, Any]]:
    """Extract enclosing function or class definition lines."""
    tree, lines = get_ast_and_lines(full_path)
    target_node = find_enclosing_node(tree, target_line)
    if not target_node:
        return None

    start = getattr(target_node, "lineno", target_line)
    end = getattr(target_node, "end_lineno", target_line)

    if hasattr(target_node, "decorator_list") and target_node.decorator_list:
        dec_starts = [
            d.lineno for d in target_node.decorator_list if hasattr(d, "lineno")
        ]
        if dec_starts:
            start = min(start, min(dec_starts))

    scope_lines = lines[start - 1 : end]

    kind = (
        "def"
        if isinstance(target_node, (ast.FunctionDef, ast.AsyncFunctionDef))
        else "class"
    )
    raw_name = target_node.name
    scope_name = f"{kind} {raw_name}"
    is_transform = is_string_transform_scope(scope_name, scope_lines)

    return {
        "name": scope_name,
        "raw_name": raw_name,
        "kind": kind,
        "start_line": start,
        "end_line": end,
        "line_count": len(scope_lines),
        "lines": scope_lines,
        "is_transform": is_transform,
    }


def print_help() -> None:
    """Print clean usage information."""
    print(
        """Usage: python grep.py [options] <pattern...> [path]

fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents.

Positional arguments:
  pattern...             Search term(s), phrase, or regex. Multiple terms are searched as OR/union.
  path                   Optional target directory or file (defaults to /workspace).

Options:
  --help, -h             Show this help message and exit.
  -p, --pattern <term>   Search pattern or regex (supports raw code snippets).
  -q, --query <term>     Search query or phrase (auto-tokenized for subterm checking).
  -d, --dir <path>       Target search directory or file path.
  -i, --ignore-case      Perform case-insensitive search.
  -w, --window <lines>   Context window size centered on target line (default: 40).
  -m, --max-matches <n>  Maximum matches to collect (default: 50).
  --json                 Output results as structured JSON conforming to Pydantic v2 FastGrepResult.

Diagnostics:
  - Zero matches: Explains file count, runs case-insensitive check, tests sub-terms, checks other files, and suggests symbols.
  - Regex errors: Fall back cleanly to literal substring search, warn gently, and return matches.
  - Missing path: Detects missing files/directories, suggests close matches, and falls back to workspace.
"""
    )


def print_overview(target_display: str = "/workspace") -> None:
    """Print helpful, copy-pasteable usage overview when called without pattern."""
    print("=" * 80)
    print("fast-grep: Omnivorous, AST-Aware Search Engine for Autonomous Agents")
    print("=" * 80)
    print("\nUsage:")
    print("  python3 grep.py [options] <pattern...> [path]")
    print("\nTailored copy-pasteable commands for next step:")
    print("  1. Search symbol or phrase:")
    print('     python3 grep.py "def score_match"')
    print("  2. Case-insensitive search:")
    print('     python3 grep.py -i "apirouter"')
    print("  3. Search in specific directory:")
    print('     python3 grep.py "splitlines" src/')
    print("  4. Multi-term union search:")
    print("     python3 grep.py splitlines rstrip strip")
    print("  5. Structured JSON output:")
    print('     python3 grep.py --json "APIRouter"')
    print("\nOptions:")
    print("  -p, --pattern <term>   Search pattern or regex")
    print("  -d, --dir <path>       Target directory or file (defaults to /workspace)")
    print("  -i, --ignore-case      Case-insensitive search")
    print("  -w, --window <lines>   Context window size around target line (default: 40)")
    print("  -m, --max-matches <n>  Maximum matches to collect (default: 50)")
    print("  --json                 Output structured Pydantic v2 JSON")
    print("  -h, --help             Show help message and exit")


# ==============================================================================
# Main Entry Point
# ==============================================================================


def main() -> int:
    try:
        raw_args = sys.argv[1:]
        ws = get_workspace_dir()

        (
            terms,
            target,
            is_json,
            is_help,
            is_case_insensitive,
            context_window,
            max_matches,
            invalid_target,
            raw_phrase,
            is_overview,
        ) = parse_args(raw_args, ws)

        if is_help:
            print_help()
            return 0

        # Align workspace if target has .git
        if (
            target.is_dir()
            and (target / ".git").exists()
            and not (ws / ".git").exists()
        ):
            ws = target

        # Target display name
        if target == ws or str(target).startswith("/workspace"):
            target_display = "/workspace"
        else:
            try:
                rel = target.relative_to(ws)
                target_display = f"/workspace/{rel}"
            except ValueError:
                target_display = str(target)

        total_files = count_files_in_target(target, ws)

        # Overview mode (no terms provided or empty arguments)
        if is_overview or (not terms and not invalid_target):
            overview_cmds = [
                'python3 grep.py "def score_match"',
                'python3 grep.py -i "apirouter"',
                'python3 grep.py "splitlines" src/',
                'python3 grep.py splitlines rstrip strip',
                'python3 grep.py --json "APIRouter"',
            ]
            if is_json:
                explanation = MatchExplanation(
                    status="OVERVIEW",
                    summary=f"No search pattern specified. Showing workspace overview for {target_display}.",
                    case_sensitive=not is_case_insensitive,
                    case_insensitive_count=0,
                    details="fast-grep usage overview",
                    skipped_extensions=sorted(list(SKIP_EXTENSIONS)),
                    skipped_dirs=sorted(list(SKIP_DIRS)),
                )
                result = FastGrepResult(
                    query_terms=[],
                    target_path=target_display,
                    total_files_scanned=total_files,
                    total_matches=0,
                    explanation=explanation,
                    suggestions=[
                        "Provide a search pattern: python3 grep.py '<pattern>'"
                    ],
                    copy_pasteable_commands=overview_cmds,
                )
                print(result.model_dump_json(indent=2))
                return 0
            else:
                print_overview(target_display)
                return 0

        # Handle missing/invalid target path
        path_warning_msg = None
        if invalid_target:
            similar_paths = find_similar_workspace_files(
                invalid_target, ws, max_results=3
            )
            path_warning_msg = (
                f"Target path '{invalid_target}' does not exist in workspace ({ws}). "
                f"Falling back to searching entire workspace."
            )
            if not is_json:
                print(
                    f"[fast-grep] ⚠️ TARGET PATH NOT FOUND: '{invalid_target}' does not exist!"
                )
                if similar_paths:
                    print("  Did you mean one of these files?")
                    for sp in similar_paths:
                        print(f"    - {sp}")
                print(
                    f"  [fast-grep] 🔄 Falling back to searching entire workspace (/workspace)...\n"
                )

        if not terms:
            print(
                "[fast-grep] ⚠️ No valid search terms provided after parsing arguments.\n"
                "Usage: python grep.py [options] <pattern...> [path]\n"
                "Example: python grep.py 'def score_match' ."
            )
            return 0

        # 1. Regex validation and diagnostic checks (with forgiving literal fallback)
        regex_diagnostics: List[RegexErrorDiagnostic] = []
        safe_terms: List[str] = []
        for t in terms:
            diag = check_regex_syntax(t)
            if diag:
                regex_diagnostics.append(diag)
                safe_terms.append(diag.suggested_escaped_regex)
                if not is_json:
                    print(
                        f"[fast-grep] ⚠️ Invalid regex pattern '{diag.raw_pattern}': {diag.error_message}"
                    )
                    print(
                        f"  💡 Automatically falling back to literal substring search."
                    )
            else:
                safe_terms.append(t)

        # 2. Run primary search
        expanded_terms = list(safe_terms)
        results = run_git_grep(
            expanded_terms,
            target,
            ws,
            case_insensitive=is_case_insensitive,
            max_matches=max_matches * 2,
        )

        pattern_display = (
            terms[0] if len(terms) == 1 else ", ".join(repr(t) for t in terms)
        )
        first_term = terms[0]

        # 3. Handle ZERO MATCHES
        if not results:
            other_locations_matches: List[OtherLocationMatch] = []
            copy_pasteable_commands: List[str] = []
            suggestions_list: List[str] = []

            # a) Narrow path filter check: check if pattern exists elsewhere in workspace
            if target != ws:
                ws_results = run_git_grep(
                    expanded_terms,
                    ws,
                    ws,
                    case_insensitive=is_case_insensitive,
                    max_matches=10,
                )
                if ws_results:
                    for r in ws_results[:5]:
                        parts = r.split(":", 2)
                        if len(parts) >= 2 and parts[1].isdigit():
                            other_locations_matches.append(
                                OtherLocationMatch(
                                    file=parts[0],
                                    lineno=int(parts[1]),
                                    content=parts[2] if len(parts) > 2 else "",
                                )
                            )
                    cmd = f'python3 grep.py "{first_term}"'
                    if cmd not in copy_pasteable_commands:
                        copy_pasteable_commands.append(cmd)
                    suggestions_list.append(
                        f"Search entire repository: pattern exists in other files outside '{target_display}'"
                    )

            # b) Run case-insensitive search if search was case-sensitive
            ci_matches: List[CaseInsensitiveMatch] = []
            if not is_case_insensitive:
                ci_results = run_git_grep(
                    expanded_terms,
                    target,
                    ws,
                    case_insensitive=True,
                    max_matches=15,
                )
                if not ci_results and target != ws:
                    ci_results = run_git_grep(
                        expanded_terms,
                        ws,
                        ws,
                        case_insensitive=True,
                        max_matches=15,
                    )
                for r in ci_results:
                    parts = r.split(":", 2)
                    if len(parts) >= 2 and parts[1].isdigit():
                        ci_matches.append(
                            CaseInsensitiveMatch(
                                file=parts[0],
                                lineno=int(parts[1]),
                                content=parts[2] if len(parts) > 2 else "",
                            )
                        )
                if ci_matches:
                    target_arg = (
                        f" {target_display.replace('/workspace/', '').replace('/workspace', '.')}"
                        if target != ws
                        else ""
                    )
                    cmd = f'python3 grep.py -i "{first_term}"{target_arg}'.strip()
                    if cmd not in copy_pasteable_commands:
                        copy_pasteable_commands.append(cmd)
                    suggestions_list.append(
                        f"Ignore case: {len(ci_matches)} matches found with -i / --ignore-case"
                    )

            # c) Test tokenized sub-terms if compound query failed
            subterm_summaries: List[SubtermMatchSummary] = []
            candidate_subterms = []
            if raw_phrase:
                candidate_subterms = extract_subterms(raw_phrase)
            for t in terms:
                for sub in extract_subterms(t):
                    if sub not in candidate_subterms:
                        candidate_subterms.append(sub)

            for sub in candidate_subterms[:6]:
                sub_res = run_git_grep(
                    [sub],
                    target,
                    ws,
                    case_insensitive=True,
                    max_matches=5,
                )
                if not sub_res and target != ws:
                    sub_res = run_git_grep(
                        [sub], ws, ws, case_insensitive=True, max_matches=5
                    )
                if sub_res:
                    first_p = sub_res[0].split(":", 2)
                    sf = first_p[0]
                    sl = (
                        int(first_p[1])
                        if len(first_p) > 1 and first_p[1].isdigit()
                        else None
                    )
                    subterm_summaries.append(
                        SubtermMatchSummary(
                            subterm=sub,
                            match_count=len(sub_res),
                            sample_file=sf,
                            sample_lineno=sl,
                        )
                    )
                    sub_cmd = f'python3 grep.py "{sub}"'
                    if sub_cmd not in copy_pasteable_commands:
                        copy_pasteable_commands.append(sub_cmd)

            # d) Extract candidate symbols from AST & repository identifiers
            symbols = extract_candidate_symbols(target, ws)
            fuzzy_suggestions = get_fuzzy_suggestions(
                terms, symbols, top_n=5, cutoff=0.35
            )
            for fs in fuzzy_suggestions[:2]:
                f_cmd = f'python3 grep.py "{fs.symbol}"'
                if f_cmd not in copy_pasteable_commands:
                    copy_pasteable_commands.append(f_cmd)

            # e) Find similar repository files
            similar_files = find_similar_workspace_files(
                raw_phrase or " ".join(terms), ws, max_results=4
            )
            for sf in similar_files[:2]:
                sf_cmd = f'python3 grep.py "{first_term}" {sf}'
                if sf_cmd not in copy_pasteable_commands:
                    copy_pasteable_commands.append(sf_cmd)

            if not copy_pasteable_commands:
                copy_pasteable_commands.append(
                    f'python3 grep.py -i "{first_term}"'
                )
                copy_pasteable_commands.append(f'python3 grep.py "{first_term}"')

            # Formulate structured explanation & result
            status = (
                "REGEX_ERROR"
                if regex_diagnostics and not safe_terms
                else "ZERO_MATCHES"
            )
            summary_msg = f"Zero matches found for pattern '{pattern_display}' across {total_files} files in {target_display}."
            explanation = MatchExplanation(
                status=status,
                summary=summary_msg,
                case_sensitive=not is_case_insensitive,
                case_insensitive_count=len(ci_matches),
                other_locations_count=len(other_locations_matches),
                details=(
                    f"Found {len(ci_matches)} case-insensitive matches. "
                    f"Found {len(other_locations_matches)} matches in other workspace files. "
                    f"Generated {len(fuzzy_suggestions)} fuzzy symbol suggestions. "
                    f"Tested {len(subterm_summaries)} subterm matches."
                ),
                skipped_extensions=sorted(list(SKIP_EXTENSIONS)),
                skipped_dirs=sorted(list(SKIP_DIRS)),
            )

            result = FastGrepResult(
                query_terms=terms,
                target_path=target_display,
                total_files_scanned=total_files,
                total_matches=0,
                explanation=explanation,
                regex_diagnostics=regex_diagnostics,
                case_insensitive_matches=ci_matches,
                other_locations_matches=other_locations_matches,
                fuzzy_suggestions=fuzzy_suggestions,
                subterm_matches=subterm_summaries,
                similar_files=similar_files,
                suggestions=suggestions_list,
                copy_pasteable_commands=copy_pasteable_commands,
                path_warning=path_warning_msg,
                ranked_matches=[],
                top_ast_nodes=[],
            )

            if is_json:
                print(result.model_dump_json(indent=2))
                return 0

            # Deterministic zero matches explanation
            print(f"[fast-grep] {summary_msg}\n")
            print(
                f"ℹ️ SEARCH CONSTRAINTS & DIAGNOSTICS:\n"
                f"  - Scanned: {total_files} files in {target_display}\n"
                f"  - Skipped non-code extensions: {', '.join(sorted(list(SKIP_EXTENSIONS))[:12])} ...\n"
                f"  - Skipped noise directories: {', '.join(sorted(list(SKIP_DIRS))[:10])} ...\n"
            )

            # 1. Path filter too narrow report
            if other_locations_matches:
                print(
                    f"💡 PATH FILTER TOO NARROW: 0 matches in '{target_display}', but {len(other_locations_matches)} match(es) exist elsewhere in the workspace:"
                )
                for om in other_locations_matches[:5]:
                    print(
                        f"  - {om.file}:{om.lineno}: {om.content.strip()[:80]}"
                    )
                print(
                    f'  Try searching without path filter: python3 grep.py "{first_term}"\n'
                )

            # 2. Case-insensitive report
            if ci_matches:
                print(
                    f'💡 0 exact matches, but {len(ci_matches)} matches exist with -i / --ignore-case! Try: python3 grep.py -i "{pattern_display}"'
                )
                for m in ci_matches[:6]:
                    print(f"  - {m.file}:{m.lineno}: {m.content.strip()[:80]}")
                if len(ci_matches) > 6:
                    print(
                        f"  ... (+{len(ci_matches) - 6} additional case-insensitive matches)"
                    )
                print()

            # 3. Tokenized sub-terms report
            if subterm_summaries:
                print("💡 COMPOUND QUERY FAILED — TOKENIZED SUB-TERM MATCHES:")
                print(
                    f"  The full query '{pattern_display}' had 0 exact matches, but sub-terms exist:"
                )
                for st in subterm_summaries:
                    loc = (
                        f" in {st.sample_file}:{st.sample_lineno}"
                        if st.sample_file
                        else ""
                    )
                    print(
                        f"  - '{st.subterm}': {st.match_count} match(es){loc}"
                    )
                print()

            # 4. Fuzzy symbol suggestions
            if fuzzy_suggestions:
                print("🔍 SIMILAR SYMBOLS IN WORKSPACE (from AST):")
                for s in fuzzy_suggestions[:5]:
                    loc = f" in {s.source_file}" if s.source_file else ""
                    print(
                        f"  - {s.symbol} ({s.kind}{loc}) [similarity: {s.similarity:.2f}]"
                    )
                print()

            # 5. Similar repository files
            if similar_files:
                print("📁 RELEVANT REPOSITORY FILES:")
                for rf in similar_files:
                    print(f"  - {rf}")
                print()

            # 6. Actionable next steps for LLM
            print("🚀 ACTIONABLE NEXT STEPS FOR LLM:")
            for idx, cmd in enumerate(copy_pasteable_commands, start=1):
                print(f"  {idx}. {cmd}")
            print()

            return 0

        # 4. Parse and rank MATCHES FOUND
        parsed: List[GrepMatch] = []
        for r in results:
            parts = r.split(":", 2)
            if len(parts) >= 2 and parts[1].isdigit():
                fp = parts[0]
                lineno = int(parts[1])
                content = parts[2] if len(parts) > 2 else ""

                scope_name = ""
                full_p = ws / fp
                if full_p.suffix == ".py" and full_p.exists():
                    tree, _ = get_ast_and_lines(full_p)
                    node = find_enclosing_node(tree, lineno)
                    if node:
                        scope_name = node.name

                sc = score_match(
                    fp, lineno, content, expanded_terms, scope_name=scope_name
                )
                is_def = bool(
                    not content.strip().startswith(
                        ("#", "//", "/*", "*", '"""', "'''")
                    )
                    and (
                        re.search(r"^\s*(async\s+def|def|class)\s+", content)
                        or re.search(r"^\s*@", content)
                    )
                )
                is_call_site = is_string_transform_line(content) and not is_def
                parsed.append(
                    GrepMatch(
                        file=fp,
                        lineno=lineno,
                        content=content,
                        score=sc,
                        scope_name=scope_name or None,
                        is_call_site=is_call_site,
                        is_definition=is_def,
                    )
                )

        parsed.sort(key=lambda m: m.score, reverse=True)
        ranked_matches = parsed[:max_matches]

        # Extract top 2 unique function scopes
        flashed: List[Tuple[GrepMatch, Dict[str, Any]]] = []
        seen = set()
        top_ast_nodes: List[ASTNodePreview] = []

        for m in ranked_matches:
            p = ws / m.file
            if not p.suffix == ".py" or not p.exists():
                continue
            scope = extract_function_scope(p, m.lineno)
            if scope:
                key = (m.file, scope["name"])
                if key not in seen:
                    seen.add(key)
                    flashed.append((m, scope))
                    top_ast_nodes.append(
                        ASTNodePreview(
                            name=scope["name"],
                            kind=scope["kind"],
                            file=m.file,
                            start_line=scope["start_line"],
                            end_line=scope["end_line"],
                            score=m.score,
                            code_snippet="\n".join(scope["lines"]),
                        )
                    )
                    if len(flashed) >= MAX_SCOPES_FLASHED:
                        break

        explanation = MatchExplanation(
            status="MATCHES_FOUND",
            summary=f"Found {len(parsed)} matches across {total_files} files in {target_display}.",
            case_sensitive=not is_case_insensitive,
            case_insensitive_count=0,
            other_locations_count=0,
            details=f"Top {len(flashed)} enclosing AST scopes flashed.",
            skipped_extensions=sorted(list(SKIP_EXTENSIONS)),
            skipped_dirs=sorted(list(SKIP_DIRS)),
        )

        result = FastGrepResult(
            query_terms=terms,
            target_path=target_display,
            total_files_scanned=total_files,
            total_matches=len(parsed),
            explanation=explanation,
            regex_diagnostics=regex_diagnostics,
            case_insensitive_matches=[],
            other_locations_matches=[],
            fuzzy_suggestions=[],
            subterm_matches=[],
            similar_files=[],
            suggestions=[],
            copy_pasteable_commands=[],
            path_warning=path_warning_msg,
            ranked_matches=ranked_matches,
            top_ast_nodes=top_ast_nodes,
        )

        if is_json:
            print(result.model_dump_json(indent=2))
            return 0

        # Output results concisely (capped under ADK context limit)
        terms_display = " | ".join(terms)
        print(
            f"[fast-grep] Search: '{terms_display}' ({len(parsed)} matches, top {len(flashed)} scopes flashed):\n"
        )

        for idx, (m, sc) in enumerate(flashed, start=1):
            fp = m.file
            s_name = sc["name"]
            s_line = sc["start_line"]
            e_line = sc["end_line"]
            lines = sc["lines"]
            target_lineno = m.lineno
            is_call_site = m.is_call_site
            is_def = m.is_definition
            is_transform_scope = sc.get("is_transform", False)

            scope_tag = ""
            if is_def and is_transform_scope:
                scope_tag = " [🎯 DEFINITION TARGET & TRANSFORM SCOPE]"
            elif is_def:
                scope_tag = " [🎯 DEFINITION TARGET]"
            elif is_transform_scope and is_call_site:
                scope_tag = " [⚡ STRING/BUFFER CALL-SITE & TRANSFORM SCOPE]"
            elif is_call_site:
                scope_tag = " [⚡ STRING/BUFFER CALL-SITE]"
            elif is_transform_scope:
                scope_tag = " [STRING/BUFFER TRANSFORM SCOPE]"

            print("=" * 80)
            print(
                f"[{idx}/{len(flashed)}] SCOPE: {s_name} ({sc['kind']}) in {fp}:{s_line}-{e_line}{scope_tag} [score: {m.score:+d}]"
            )
            print("=" * 80)

            def format_line(lineno: int, text: str) -> str:
                truncated_text = text[:300]
                if lineno == target_lineno:
                    if is_def:
                        callout = "  <-- [DEFINITION TARGET]"
                    elif is_call_site:
                        callout = (
                            "  <-- [CALL-SITE: string/buffer transform]"
                        )
                    else:
                        callout = "  <-- [MATCH]"
                    return f"{lineno:4d}: >>> {truncated_text}{callout}"
                return f"{lineno:4d}:     {truncated_text}"

            rel_idx = max(0, min(len(lines) - 1, target_lineno - s_line))
            half_before = max(5, int(context_window * 0.375))
            half_after = max(5, context_window - half_before)

            if len(lines) > (context_window + 5):
                w_start = max(0, rel_idx - half_before)
                w_end = min(len(lines), rel_idx + half_after)
                display_lines = lines[w_start:w_end]
                disp_start_lineno = s_line + w_start
                if w_start > 0:
                    print(
                        f"  ... [{w_start} lines before in {s_name} omitted] ..."
                    )
                for i, l in enumerate(display_lines, start=disp_start_lineno):
                    print(format_line(i, l))
                if w_end < len(lines):
                    print(
                        f"  ... [{len(lines) - w_end} lines after in {s_name} omitted] ..."
                    )
            else:
                display_lines = lines
                w_start = 0
                w_end = len(lines)
                for i, l in enumerate(lines, start=s_line):
                    print(format_line(i, l))

            # Primary top match clean unadorned code block
            if idx == 1:
                clean_snippet = "\n".join(lines[w_start:w_end])
                print("\n[CLEAN CODE FOR edit_file (EXACT INDENTATION)]:")
                print("```python")
                print(clean_snippet)
                print("```")
            print()

        # Summary of other ranked matches
        print("-" * 80)
        print("📋 TOP MATCH PREVIEWS:")
        for m in ranked_matches[:MAX_DISPLAY_PREVIEWS]:
            snippet = m.content.strip()[:75]
            if m.is_definition:
                site_tag = " [DEF]"
            elif m.is_call_site:
                site_tag = " [CALL-SITE]"
            else:
                site_tag = ""
            print(f"  [{m.score:+3d}] {m.file}:{m.lineno}{site_tag}: {snippet}")

        if len(parsed) > MAX_DISPLAY_PREVIEWS:
            print(
                f"  ... ({len(parsed) - MAX_DISPLAY_PREVIEWS} additional matches truncated)"
            )

        return 0
    except Exception as e:
        print(f"[fast-grep] Search completed with fallback: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
`````

## File: submission/skills/fast-grep/SKILL.md
`````markdown
---
name: fast-grep
description: Fast codebase regex and keyword search across /workspace with probability ranking, definition prioritization, AST function flashing, sliding context window, and clean code blocks for edit_file.
---

# fast-grep Skill

Fast, omnivorous codebase search engine for locating symbols, regex patterns, function calls, and error messages across `/workspace`.

## Features
- **Relevance & Definition-First Ranking**: Scores matches so function and class definitions (`def`, `async def`, `class`, `@decorator`) appear at the top (+120 to +195 score bump) rather than being drowned out by call sites or comments.
- **Symbol Bonuses**: Exact symbol name matches receive +75 bonus and substring matches receive +50 bonus.
- **Forgiving & Omnivorous CLI**: Accepts positional arguments `python3 grep.py pattern [path]`, flags `-p`/`--pattern`, `-d`/`--dir`, `-i`/`--ignore-case`, `-w`/`--window`, `-m`/`--max-matches`, and `--json`.
- **Regex-to-Literal Fallback**: When an invalid regex is provided (e.g. unescaped parentheses `def foo(`, unbalanced brackets, or bad escapes), falls back to literal substring search without crashing.
- **Crash & Infinite Loop Immunity**: Limits file scanning to 500KB and 5000 lines per file, detects and skips binary files via null-byte inspection, guards against symlink cycles, and caps total matches to prevent context flooding.
- **Actionable Zero-Match Diagnostics**: When 0 matches are found:
  - Detects if case mismatch occurred and suggests case-insensitive search (`-i`).
  - Detects if path filter was too narrow and reveals occurrences in other repository files.
  - Generates fuzzy symbol candidate suggestions from AST identifiers.
  - Breaks compound queries into tokenized sub-terms.
  - Outputs concrete copy-pasteable commands for the next turn.
- **Top 2 AST Scope Flashing**: Extracts and displays top 2 enclosing functions or classes with complete decorators and line numbers.
- **Target-Centered Sliding Window**: Centers context window around target line (default 15 lines before to 25 lines after, configurable via `-w`).
- **Clean Code Block for `edit_file`**: Provides unadorned code block with exact Python indentation for the top match.
- **Never crashes**: Always exits cleanly with code 0.

## How to Run

### Via ADK `run_skill_script`
```python
# Search symbol across repository:
run_skill_script(
    skill_name="fast-grep",
    file_path="grep.py",
    args=["APIRouter"]
)

# Search within specific directory:
run_skill_script(
    skill_name="fast-grep",
    file_path="grep.py",
    args=["splitlines", "rich/"]
)

# Case-insensitive search:
run_skill_script(
    skill_name="fast-grep",
    file_path="grep.py",
    args=["-i", "apirouter"]
)
```

### Via CLI
```bash
# Positional query:
python3 grep.py "APIRouter" .

# Positional pattern with target path:
python3 grep.py "splitlines" rich/

# Case-insensitive search:
python3 grep.py -i "apirouter"

# Raw snippet search (auto literal fallback):
python3 grep.py "def format("

# Structured JSON output:
python3 grep.py --json "APIRouter"
```
`````

## File: submission/skills/repro-check/scripts/check.py
`````python
#!/usr/bin/env python3
"""repro-check: Omnivorous Defect Reproduction & Verification Engine.

V2 Upgrades:
- Native `--expect-exception <ExceptionType>` support:
  Deterministically catches missing-validation defects (defect_confirmed=True when not raised,
  status=PASSED when fix causes the exception to be raised).
- Base64 decode support via `--b64` / `--base64` to cleanly bypass shell/JSON quote escaping.
- Input quote and fence sanitization (strips redundant outer quotes, markdown blocks, and JSON escaped quotes).
- AST pre-parse syntax validation: verifies syntax prior to scratch file generation or execution.
- Raw multiline script execution via `--file`, `--stdin`, or pipes into isolated `/tmp` cwd,
  avoiding CLI quote escaping and emoji truncation.
- Path Containment Guard: Strictly isolates scratch files in `/tmp` and prevents/cleans any
  accidental `/workspace/tmp/...` files that could pollute git status.
- Prioritizes /workspace and /workspace/src in PYTHONPATH.

Omnivorous core features:
- Auto-asserts bare comparison expressions: `a == b` -> `assert a == b`
- Auto-invokes uncalled test functions: `def test_...():`
- Auto-heals unterminated string literals with raw unescaped newlines in `'...'` and `"..."`
- Omnivorous assert acceptance: executions without explicit `assert` that exit 0 are accepted as valid passes
- Bypasses 2-probe circuit breaker when workspace contains modified files (post-edit verification)
- Strips markdown fences (```py, ```python, etc.) and auto-dedents
- Deterministic failure explanations: introspects failing frame, local variables, actual/expected values, char diffs
- Structured 100% Pydantic v2 models for all diagnostic outputs
- Exits 0 on pass, exits 1 on fail/syntax error.
"""

from __future__ import annotations

import ast
import base64
import contextlib
import difflib
import inspect
import io
import json
import linecache
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
import textwrap
import types
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

PROBE_COUNT_FILE = pathlib.Path("/tmp/.swegemma_repro_probe_count")

OP_MAP = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}


# =============================================================================
# 100% Pydantic v2 Structured Diagnostic Models
# =============================================================================

class VariableInfo(BaseModel):
    """Inspected variable details from stack frame."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Variable name")
    type_name: str = Field(..., description="Variable type name")
    value_repr: str = Field(..., description="String representation with visible escape codes")
    length: Optional[int] = Field(default=None, description="Length of sequence or collection if applicable")


class StackFrameInfo(BaseModel):
    """Inspected call stack frame details."""

    model_config = ConfigDict(extra="ignore")

    filename: str = Field(..., description="File path of execution frame")
    lineno: int = Field(..., description="Line number")
    function_name: str = Field(..., description="Function or module name")
    code_context: Optional[str] = Field(default=None, description="Source code line")
    arguments: Dict[str, VariableInfo] = Field(default_factory=dict, description="Function arguments")
    local_variables: Dict[str, VariableInfo] = Field(default_factory=dict, description="Local variables in frame")


class AssertionDiagnostic(BaseModel):
    """Deterministic failure diagnostic for an assertion failure."""

    model_config = ConfigDict(extra="ignore")

    assertion_code: str = Field(..., description="Source code of the failing assertion")
    op: str = Field(default="==", description="Comparison operator (==, !=, in, etc.)")
    actual_type: str = Field(..., description="Type name of actual value")
    actual_repr: str = Field(..., description="Actual value with visible escape codes")
    actual_length: Optional[int] = Field(default=None, description="Length of actual value if applicable")
    expected_type: str = Field(..., description="Type name of expected value")
    expected_repr: str = Field(..., description="Expected value with visible escape codes")
    expected_length: Optional[int] = Field(default=None, description="Length of expected value if applicable")
    char_diff: Optional[str] = Field(default=None, description="Character-by-character or unified diff")
    first_diff_index: Optional[int] = Field(default=None, description="First index where values differ")
    divergence_detail: Optional[str] = Field(default=None, description="Exact divergence detail with hex characters")
    escape_breakdown: Optional[str] = Field(default=None, description="Decoded ANSI escape sequences and control characters")
    dict_diff_summary: Optional[str] = Field(default=None, description="Detailed dictionary diff summary")
    sequence_diff_summary: Optional[str] = Field(default=None, description="Detailed sequence diff summary")
    root_cause_hint: Optional[str] = Field(default=None, description="Actionable root cause hint for LLM")
    message: Optional[str] = Field(default=None, description="Assertion failure message")
    explanation: str = Field(..., description="Plain-English explanation of why assertion failed")
    remediation_hint: Optional[str] = Field(default=None, description="Actionable remediation hint for common defects")


class ExceptionDiagnostic(BaseModel):
    """Deterministic failure diagnostic for an unhandled runtime exception."""

    model_config = ConfigDict(extra="ignore")

    exception_type: str = Field(..., description="Exception class name")
    exception_message: str = Field(..., description="Exception error message")
    failing_file: str = Field(..., description="File where exception occurred")
    failing_line: int = Field(..., description="Line number where exception occurred")
    failing_code: Optional[str] = Field(default=None, description="Failing source line code")
    operation_description: str = Field(..., description="Plain-English explanation of operation that failed")
    call_stack: List[StackFrameInfo] = Field(default_factory=list, description="Call stack frames")


class DiagnosticReport(BaseModel):
    """Full structured reproduction report."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="Status: passed, PASSED, missing_exception, assertion_error, runtime_exception, syntax_error, probe_budget_reached, probe_run, timeout, error")
    exit_code: int = Field(default=0, description="Process exit code")
    summary: str = Field(..., description="High-level diagnostic summary")
    assertion_diagnostic: Optional[AssertionDiagnostic] = Field(default=None, description="Details if assertion failed")
    exception_diagnostic: Optional[ExceptionDiagnostic] = Field(default=None, description="Details if exception occurred")
    local_variables: Dict[str, VariableInfo] = Field(default_factory=dict, description="Local variables in failing frame")
    raw_stdout: str = Field(default="", description="Captured stdout")
    raw_stderr: str = Field(default="", description="Captured stderr")


class ReproCheckInput(BaseModel):
    """Structured input parameters for reproduction check."""

    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Reproduction script code")
    args: List[str] = Field(default_factory=list, description="Original CLI arguments")
    timeout_secs: int = Field(default=15, description="Timeout in seconds")
    workspace_dir: Optional[str] = Field(default=None, description="Path to active workspace")


class ReproCheckOutput(BaseModel):
    """Top-level structured output of repro-check."""

    model_config = ConfigDict(extra="ignore")

    success: bool = Field(..., description="True if verification passed cleanly")
    defect_confirmed: bool = Field(..., description="True if defect was reproduced via assertion or exception")
    category: str = Field(..., description="Category: passed, assertion_failure, workspace_exception, runtime_exception, syntax_error, probe_budget_reached, probe_run, general_failure, missing_exception")
    report: DiagnosticReport = Field(..., description="Structured diagnostic report")
    rendered_output: str = Field(..., description="Rendered human/agent readable text")


VariableInfo.model_rebuild()
StackFrameInfo.model_rebuild()
AssertionDiagnostic.model_rebuild()
ExceptionDiagnostic.model_rebuild()
DiagnosticReport.model_rebuild()
ReproCheckInput.model_rebuild()
ReproCheckOutput.model_rebuild()


# =============================================================================
# Custom Assertion Exception for Zero-Loss Evaluation
# =============================================================================

class ReproAssertionError(AssertionError):
    """Carries exact evaluated operands and failing frame for deterministic explanation."""

    def __init__(
        self,
        actual: Any,
        expected: Any,
        op: str,
        code_str: str,
        lineno: int,
        msg: str = "",
        frame: Optional[types.FrameType] = None,
    ):
        super().__init__(msg or f"Assertion failed: {code_str}")
        self.actual = actual
        self.expected = expected
        self.op = op
        self.code_str = code_str
        self.lineno = lineno
        self.msg = msg
        self.frame = frame


# =============================================================================
# Value Formatting and Diff Helpers
# =============================================================================

def format_value_repr(val: Any, max_len: int = 300) -> str:
    """Format value representation with visible escape codes and safe length cap."""
    try:
        r = repr(val)
        if len(r) > max_len:
            return r[:max_len] + f"... [truncated, total {len(r)} chars]"
        return r
    except Exception:
        return f"<{type(val).__name__} (unprintable)>"


def get_length(val: Any) -> Optional[int]:
    """Safely obtain length of sequence or collection."""
    try:
        return len(val)
    except Exception:
        return None


def introspect_variable(name: str, val: Any) -> VariableInfo:
    """Convert an arbitrary Python runtime variable into a VariableInfo model."""
    return VariableInfo(
        name=name,
        type_name=type(val).__name__,
        value_repr=format_value_repr(val),
        length=get_length(val),
    )


def extract_frame_info(frame: types.FrameType, lineno: int) -> StackFrameInfo:
    """Extract argument and local variable details from a call stack frame."""
    co = frame.f_code
    filename = co.co_filename
    func_name = co.co_name

    # Try reading source line from linecache
    code_context = linecache.getline(filename, lineno).strip() or None

    # Inspect function arguments if applicable
    args_dict: Dict[str, VariableInfo] = {}
    try:
        argvalues = inspect.getargvalues(frame)
        for arg in argvalues.args:
            if arg in frame.f_locals:
                args_dict[arg] = introspect_variable(arg, frame.f_locals[arg])
        if argvalues.varargs and argvalues.varargs in frame.f_locals:
            args_dict[f"*{argvalues.varargs}"] = introspect_variable(argvalues.varargs, frame.f_locals[argvalues.varargs])
        if argvalues.keywords and argvalues.keywords in frame.f_locals:
            args_dict[f"**{argvalues.keywords}"] = introspect_variable(argvalues.keywords, frame.f_locals[argvalues.keywords])
    except Exception:
        pass

    # Extract clean local variables
    locals_dict: Dict[str, VariableInfo] = {}
    for k, v in frame.f_locals.items():
        if not k.startswith("__") and k not in ("__repro_assert__", "__repro_assert_truthy__"):
            locals_dict[k] = introspect_variable(k, v)

    return StackFrameInfo(
        filename=filename,
        lineno=lineno,
        function_name=func_name,
        code_context=code_context,
        arguments=args_dict,
        local_variables=locals_dict,
    )


def extract_call_stack(exc: BaseException) -> List[StackFrameInfo]:
    """Walk an exception's traceback and introspect all stack frames."""
    frames: List[StackFrameInfo] = []
    tb = exc.__traceback__
    this_file = str(pathlib.Path(__file__).resolve())
    while tb is not None:
        frame = tb.tb_frame
        lineno = tb.tb_lineno
        # Filter out internal runner harness frames
        if frame.f_code.co_name == "run_harness" or frame.f_code.co_filename == this_file:
            tb = tb.tb_next
            continue
        frames.append(extract_frame_info(frame, lineno))
        tb = tb.tb_next

    # Fallback to all frames if all were filtered out
    if not frames and exc.__traceback__ is not None:
        tb = exc.__traceback__
        while tb is not None:
            frames.append(extract_frame_info(tb.tb_frame, tb.tb_lineno))
            tb = tb.tb_next

    return frames


# =============================================================================
# ANSI & Control Sequence Decoding
# =============================================================================

ANSI_CSI_RE = re.compile(r"\x1b\[([0-9;]*)([a-zA-Z])")
ANSI_OSC_RE = re.compile(r"\x1b\]([^\x07\x1b]*)(?:\x07|\x1b\\)")
ANSI_ESCAPE_RE = re.compile(
    r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]"
)

SGR_CODES: Dict[str, str] = {
    "0": "Reset / Normal",
    "1": "Bold",
    "2": "Dim / Faint",
    "3": "Italic",
    "4": "Underline",
    "5": "Slow Blink",
    "6": "Rapid Blink",
    "7": "Invert / Reverse video",
    "8": "Concealed / Hidden",
    "9": "Strikethrough / Crossed-out",
    "22": "Normal intensity",
    "23": "Not italic",
    "24": "Not underlined",
    "27": "Not inverted",
    "28": "Reveal (not concealed)",
    "29": "Not crossed out",
    "30": "Black text",
    "31": "Red text",
    "32": "Green text",
    "33": "Yellow text",
    "34": "Blue text",
    "35": "Magenta text",
    "36": "Cyan text",
    "37": "White text",
    "39": "Default text color",
    "40": "Black background",
    "41": "Red background",
    "42": "Green background",
    "43": "Yellow background",
    "44": "Blue background",
    "45": "Magenta background",
    "46": "Cyan background",
    "47": "White background",
    "49": "Default background color",
    "90": "Bright Black / Dark Gray text",
    "91": "Bright Red text",
    "92": "Bright Green text",
    "93": "Bright Yellow text",
    "94": "Bright Blue text",
    "95": "Bright Magenta text",
    "96": "Bright Cyan text",
    "97": "Bright White text",
    "100": "Bright Black background",
    "101": "Bright Red background",
    "102": "Bright Green background",
    "103": "Bright Yellow background",
    "104": "Bright Blue background",
    "105": "Bright Magenta background",
    "106": "Bright Cyan background",
    "107": "Bright White background",
}

CONTROL_CHAR_NAMES: Dict[int, str] = {
    0x00: "NUL (null byte)",
    0x01: "SOH (start of heading)",
    0x02: "STX (start of text)",
    0x03: "ETX (end of text)",
    0x04: "EOT (end of transmission)",
    0x05: "ENQ (enquiry)",
    0x06: "ACK (acknowledge)",
    0x07: "BEL (bell / alert)",
    0x08: "BS (backspace)",
    0x09: "HT (horizontal tab)",
    0x0A: "LF (line feed / newline)",
    0x0B: "VT (vertical tab)",
    0x0C: "FF (form feed)",
    0x0D: "CR (carriage return)",
    0x0E: "SO (shift out)",
    0x0F: "SI (shift in)",
    0x10: "DLE (data link escape)",
    0x11: "DC1 (device control 1)",
    0x12: "DC2 (device control 2)",
    0x13: "DC3 (device control 3)",
    0x14: "DC4 (device control 4)",
    0x15: "NAK (negative acknowledge)",
    0x16: "SYN (synchronous idle)",
    0x17: "ETB (end of trans block)",
    0x18: "CAN (cancel)",
    0x19: "EM (end of medium)",
    0x1A: "SUB (substitute)",
    0x1B: "ESC (escape)",
    0x1C: "FS (file separator)",
    0x1D: "GS (group separator)",
    0x1E: "RS (record separator)",
    0x1F: "US (unit separator)",
    0x7F: "DEL (delete)",
    0x200B: "Zero-Width Space",
    0x200C: "Zero-Width Non-Joiner",
    0x200D: "Zero-Width Joiner",
    0x200E: "Left-to-Right Mark",
    0x200F: "Right-to-Left Mark",
    0xFEFF: "Zero-Width No-Break Space / BOM",
    0x00A0: "Non-Breaking Space",
    0x2028: "Line Separator",
    0x2029: "Paragraph Separator",
}


def decode_ansi_sequence(seq: str) -> str:
    """Decode an ANSI escape sequence into a human-readable description."""
    m_csi = ANSI_CSI_RE.fullmatch(seq)
    if m_csi:
        params, cmd = m_csi.group(1), m_csi.group(2)
        if cmd == "m":
            if not params or params == "0":
                return f"ANSI CSI SGR {seq[2:]}: Reset / Normal"
            param_list = params.split(";")
            meanings = []
            skip_next = 0
            for i, p in enumerate(param_list):
                if skip_next > 0:
                    skip_next -= 1
                    continue
                if p in ("38", "48") and i + 1 < len(param_list):
                    mode = param_list[i + 1]
                    target = "text" if p == "38" else "background"
                    if mode == "5" and i + 2 < len(param_list):
                        color_idx = param_list[i + 2]
                        meanings.append(f"256-color {target} #{color_idx}")
                        skip_next = 2
                        continue
                    elif mode == "2" and i + 4 < len(param_list):
                        r, g, b = param_list[i + 2 : i + 5]
                        meanings.append(f"RGB {target} ({r},{g},{b})")
                        skip_next = 4
                        continue
                desc = SGR_CODES.get(p, f"code {p}")
                meanings.append(desc)
            return f"ANSI CSI SGR {seq[2:]}: {', '.join(meanings)}"
        elif cmd == "K":
            mode = params or "0"
            k_map = {
                "0": "Clear line from cursor to end",
                "1": "Clear line from cursor to start",
                "2": "Clear entire line",
            }
            return f"ANSI CSI {seq[2:]}: {k_map.get(mode, 'Clear line')}"
        elif cmd == "J":
            mode = params or "0"
            j_map = {
                "0": "Clear screen from cursor to end",
                "1": "Clear screen from cursor to start",
                "2": "Clear entire screen",
            }
            return f"ANSI CSI {seq[2:]}: {j_map.get(mode, 'Clear display')}"
        elif cmd in ("H", "f"):
            pos = params or "1;1"
            return f"ANSI CSI {seq[2:]}: Move cursor to row;col {pos}"
        elif cmd == "A":
            return f"ANSI CSI {seq[2:]}: Move cursor up {params or 1} lines"
        elif cmd == "B":
            return f"ANSI CSI {seq[2:]}: Move cursor down {params or 1} lines"
        elif cmd == "C":
            return f"ANSI CSI {seq[2:]}: Move cursor right {params or 1} cols"
        elif cmd == "D":
            return f"ANSI CSI {seq[2:]}: Move cursor left {params or 1} cols"
        else:
            return f"ANSI CSI command '{cmd}' (params: {params or 'none'})"

    m_osc = ANSI_OSC_RE.fullmatch(seq)
    if m_osc:
        content = m_osc.group(1)
        if content.startswith("0;"):
            return f"ANSI OSC 0: Set window title '{content[2:]}'"
        elif content.startswith("8;;"):
            return f"ANSI OSC 8: Hyperlink '{content[3:]}'"
        return f"ANSI OSC: '{content}'"

    return f"ANSI escape sequence: {repr(seq)}"


def scan_escape_and_control_codes(s: str) -> List[Tuple[int, str, str]]:
    """Scan string for ANSI escape sequences and control characters.

    Returns list of (char_index, raw_repr, description).
    """
    results: List[Tuple[int, str, str]] = []
    covered_spans: List[Tuple[int, int]] = []

    # 1. Match ANSI sequences
    for m in ANSI_ESCAPE_RE.finditer(s):
        start, end = m.span()
        seq = m.group(0)
        desc = decode_ansi_sequence(seq)
        results.append((start, repr(seq), desc))
        covered_spans.append((start, end))

    # 2. Match control characters outside covered spans
    for i, c in enumerate(s):
        in_span = any(start <= i < end for start, end in covered_spans)
        if in_span:
            continue
        cp = ord(c)
        if cp in CONTROL_CHAR_NAMES:
            name = CONTROL_CHAR_NAMES[cp]
            results.append((i, repr(c), f"Control char 0x{cp:02x}: {name}"))
        elif cp < 32 and c not in ("\n", "\t"):
            results.append((i, repr(c), f"Control char 0x{cp:02x}: non-printable"))
        elif 127 <= cp <= 159:
            results.append((i, repr(c), f"Control char 0x{cp:02x}: C1 control code"))

    results.sort(key=lambda x: x[0])
    return results


def format_escape_breakdown(actual: str, expected: str) -> Optional[str]:
    """Generate human-readable escape and control sequence breakdown."""
    act_codes = scan_escape_and_control_codes(actual)
    exp_codes = scan_escape_and_control_codes(expected)

    if not act_codes and not exp_codes:
        return None

    lines = ["📟 ANSI & CONTROL ESCAPE BREAKDOWN:"]

    lines.append(f"  Actual ({len(act_codes)} code(s) detected):")
    if act_codes:
        for idx, raw_rep, desc in act_codes:
            lines.append(f"    - Index {idx:3d}: {raw_rep} -> {desc}")
    else:
        lines.append("    (None - plain text, no escape or control sequences)")

    lines.append(f"  Expected ({len(exp_codes)} code(s) detected):")
    if exp_codes:
        for idx, raw_rep, desc in exp_codes:
            lines.append(f"    - Index {idx:3d}: {raw_rep} -> {desc}")
    else:
        lines.append("    (None - plain text, no escape or control sequences)")

    return "\n".join(lines)


def compute_string_divergence(actual: str, expected: str) -> Tuple[Optional[int], str]:
    """Find character index of first divergence and format exact diagnostic."""
    min_len = min(len(actual), len(expected))
    for i in range(min_len):
        if actual[i] != expected[i]:
            c_a = actual[i]
            c_e = expected[i]
            diff_msg = (
                f"Diff at index {i}: actual={c_a!r} (hex: {hex(ord(c_a))}) vs expected={c_e!r} (hex: {hex(ord(c_e))})"
            )
            return i, diff_msg

    if len(actual) < len(expected):
        first_diff = len(actual)
        c_e = expected[first_diff]
        diff_msg = (
            f"Diff at index {first_diff}: actual string ended (length {len(actual)}) vs expected={c_e!r} (hex: {hex(ord(c_e))})"
        )
        return first_diff, diff_msg
    elif len(actual) > len(expected):
        first_diff = len(expected)
        c_a = actual[first_diff]
        diff_msg = (
            f"Diff at index {first_diff}: actual={c_a!r} (hex: {hex(ord(c_a))}) vs expected string ended (length {len(expected)})"
        )
        return first_diff, diff_msg

    return None, "Strings are identical"


def get_string_remediation_hint(actual: Any, expected: Any) -> Optional[str]:
    """Generate targeted remediation hint for common string and boundary defects."""
    if not isinstance(actual, str) or not isinstance(expected, str):
        return None

    if actual == expected:
        return None

    # Degenerate boundary mismatch (empty string vs newline)
    if (actual == "" and expected in ("\n", "\r\n")) or (actual in ("\n", "\r\n") and expected == ""):
        return (
            "💡 HINT: Boundary value mismatch detected. Verify edge-case handling for empty or boundary inputs."
        )

    # Suffix / trailing mismatch (difference is at or near the end, e.g. missing trailing \n, \r\n, or extra trailing whitespace)
    if actual.rstrip() == expected.rstrip():
        return (
            "💡 HINT: Trailing character or newline mismatch. Actual string differs in suffix from expected."
        )

    # Line count mismatch (empty line suppression or newline preservation issue)
    if ("\n" in actual or "\n" in expected) and actual.count("\n") != expected.count("\n"):
        return f"💡 HINT: Line count mismatch detected. Expected {expected.count('\n')} newlines, got {actual.count('\n')}. Check for dropped empty lines or delimiter parsing differences."

    return None


compute_assertion_remediation_hint = get_string_remediation_hint


def generate_root_cause_hint(
    actual: Any,
    op: str,
    expected: Any,
    first_diff_idx: Optional[int] = None,
) -> str:
    """Generate clear, actionable root cause hint for the LLM."""
    if isinstance(actual, str) and isinstance(expected, str):
        act_has_ansi = bool(ANSI_ESCAPE_RE.search(actual))
        exp_has_ansi = bool(ANSI_ESCAPE_RE.search(expected))

        if act_has_ansi and not exp_has_ansi:
            return (
                "Actual string contains ANSI styling/escape codes that are absent from expected. "
                "If plain text was expected, strip ANSI escapes (e.g. using strip_ansi(), Text.plain, "
                "or re.sub(r'\\x1b\\[[0-9;]*[a-zA-Z]', '', text)). "
                "If styled output was expected, update the assertion or expected string with matching ANSI codes."
            )
        elif exp_has_ansi and not act_has_ansi:
            return (
                "Expected string contains ANSI styling/escape codes that are missing from actual output. "
                "Ensure terminal styling, color formatting, or highlighter is enabled and invoked."
            )
        elif act_has_ansi and exp_has_ansi:
            idx_str = f" at index {first_diff_idx}" if first_diff_idx is not None else ""
            return (
                f"ANSI escape sequences differ{idx_str}. "
                "Check the exact style tags, color parameter numbers, or reset codes in the formatting pipeline."
            )

        # Check line ending / CRLF vs LF differences
        if ("\r" in actual and "\r" not in expected) or ("\r" in expected and "\r" not in actual):
            return (
                "Line ending mismatch detected (CRLF '\\r\\n' vs LF '\\n' or carriage return '\\r'). "
                "Normalize line endings using .replace('\\r\\n', '\\n') or str.splitlines()."
            )

        # Check tab vs space indentation
        if ("\t" in actual or "\t" in expected) and actual.expandtabs() == expected.expandtabs():
            return (
                "Tab vs space indentation mismatch detected. "
                "Verify tab expansion or replace tabs with spaces using .expandtabs() or 4 spaces."
            )

        # Check trailing whitespace or newline differences
        if actual.rstrip() == expected.rstrip():
            return (
                "String mismatch is caused by trailing newline or whitespace differences. "
                "Verify rstrip(), strip(), or newline emission logic."
            )

        # Line count mismatch
        if actual.count("\n") != expected.count("\n"):
            return (
                f"Line count mismatch (actual has {actual.count('\n')} newlines, "
                f"expected has {expected.count('\n')}). "
                "Check for dropped empty lines, delimiter parsing, or splitlines() handling."
            )

        # Boundary empty string
        if (actual == "" and expected != "") or (actual != "" and expected == ""):
            return (
                "Boundary value mismatch (empty string vs non-empty string). "
                "Verify edge-case handling for empty or boundary inputs."
            )

        # General string difference
        idx_str = f" at index {first_diff_idx}" if first_diff_idx is not None else ""
        c_a = actual[first_diff_idx] if first_diff_idx is not None and first_diff_idx < len(actual) else "ended"
        c_e = expected[first_diff_idx] if first_diff_idx is not None and first_diff_idx < len(expected) else "ended"
        return (
            f"Strings diverge{idx_str} (actual={c_a!r} vs expected={c_e!r}). "
            "Verify character formatting, escaping, or string manipulation around this position."
        )

    if isinstance(actual, dict) and isinstance(expected, dict):
        missing_keys = [k for k in expected if k not in actual]
        extra_keys = [k for k in actual if k not in expected]
        common_keys = [k for k in actual if k in expected]
        val_diff_keys = [k for k in common_keys if actual[k] != expected[k]]

        hints = []
        if missing_keys:
            hints.append(f"missing expected key(s): {missing_keys}")
        if extra_keys:
            hints.append(f"unexpected extra key(s): {extra_keys}")
        if val_diff_keys:
            hints.append(f"differing values for key(s): {val_diff_keys}")

        hint_desc = "; ".join(hints) if hints else "dictionary contents differ"
        return (
            f"Dictionary mismatch ({hint_desc}). "
            "Check dictionary construction, field serialization, or schema mapping logic."
        )

    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            return (
                f"Sequence length mismatch: actual has {len(actual)} items, expected has {len(expected)}. "
                "Check loop iteration, filtering conditions, or item appending logic."
            )
        idx_str = f" at index {first_diff_idx}" if first_diff_idx is not None else ""
        return (
            f"Sequence elements differ{idx_str}. "
            "Verify item construction, sorting order, or transformation logic at this position."
        )

    if type(actual) is not type(expected):
        return (
            f"Type mismatch: actual is of type '{type(actual).__name__}' but expected '{type(expected).__name__}'. "
            "Check function return type or explicit type casting."
        )

    if isinstance(actual, (int, float, complex)) and isinstance(expected, (int, float, complex)):
        try:
            diff = actual - expected
            return (
                f"Numeric value mismatch: actual is {actual}, expected is {expected} (difference: {diff:+}). "
                "Verify calculation, rounding, or offset logic."
            )
        except Exception:
            pass

    return (
        f"Assertion condition '{op}' failed between actual and expected values. "
        "Inspect the logic computing the actual value to ensure it matches expected criteria."
    )


def explain_string_diff(actual: str, expected: str) -> Tuple[str, Optional[int]]:
    """Generate exact plain-English mismatch explanation and first differing index for strings."""
    min_len = min(len(actual), len(expected))
    first_diff = None
    for i in range(min_len):
        if actual[i] != expected[i]:
            first_diff = i
            break

    act_short = repr(actual)
    exp_short = repr(expected)

    if first_diff is None:
        if len(actual) < len(expected):
            first_diff = len(actual)
            missing = expected[len(actual):]
            missing_repr = repr(missing)
            summary = (
                f"MISMATCH: Actual string ({act_short}, {len(actual)} chars) is missing trailing "
                f"{missing_repr} present in Expected string ({exp_short}, {len(expected)} chars). "
                f"Difference at index {first_diff}."
            )
            return summary, first_diff
        elif len(actual) > len(expected):
            first_diff = len(expected)
            extra = actual[len(expected):]
            extra_repr = repr(extra)
            summary = (
                f"MISMATCH: Actual string ({act_short}, {len(actual)} chars) has unexpected trailing "
                f"{extra_repr} not present in Expected string ({exp_short}, {len(expected)} chars). "
                f"Difference at index {first_diff}."
            )
            return summary, first_diff
        else:
            return "Strings are identical.", None
    else:
        c_act = actual[first_diff]
        c_exp = expected[first_diff]
        case_note = ""
        if c_act.lower() == c_exp.lower():
            case_note = f" (Casing difference: Actual has '{c_act}', Expected has '{c_exp}')"
        summary = (
            f"MISMATCH: Actual string ({act_short}, {len(actual)} chars) differs from "
            f"Expected string ({exp_short}, {len(expected)} chars) at index {first_diff}. "
            f"Actual has {repr(c_act)} (hex: {hex(ord(c_act))}), Expected has {repr(c_exp)} (hex: {hex(ord(c_exp))}){case_note}."
        )
        return summary, first_diff


def generate_string_char_diff(actual: str, expected: str, first_diff_idx: Optional[int]) -> str:
    """Generate unified and character-by-character diff showing exact differences."""
    diff_lines: List[str] = []
    act_repr = repr(actual)
    exp_repr = repr(expected)
    diff_lines.append(f"- Expected: {exp_repr} (len={len(expected)})")
    diff_lines.append(f"+ Actual:   {act_repr} (len={len(actual)})")

    # Character-level ndiff
    nd = list(difflib.ndiff([exp_repr], [act_repr]))
    if len(nd) > 2:
        diff_lines.append("  ndiff:")
        for line in nd:
            diff_lines.append(f"    {line}")

    # Multiline unified diff if string has newlines
    if "\n" in actual or "\n" in expected:
        exp_lines = [l + "\n" for l in expected.splitlines()] or ["\n"]
        act_lines = [l + "\n" for l in actual.splitlines()] or ["\n"]
        ud = list(difflib.unified_diff(exp_lines, act_lines, fromfile="expected", tofile="actual"))
        if ud:
            diff_lines.append("  unified diff:")
            for line in ud:
                diff_lines.append(f"    {line.rstrip()}")

    # Exact index breakdown
    if first_diff_idx is not None:
        if first_diff_idx < len(actual) and first_diff_idx < len(expected):
            c_act = actual[first_diff_idx]
            c_exp = expected[first_diff_idx]
            diff_lines.append(
                f"  Diff at index {first_diff_idx}: actual={c_act!r} (hex: {hex(ord(c_act))}) vs expected={c_exp!r} (hex: {hex(ord(c_exp))})"
            )
        elif first_diff_idx == len(actual) and len(actual) < len(expected):
            c_exp = expected[first_diff_idx]
            diff_lines.append(
                f"  Diff at index {first_diff_idx}: actual string ended (length {len(actual)}) vs expected={c_exp!r} (hex: {hex(ord(c_exp))})"
            )
        elif first_diff_idx == len(expected) and len(actual) > len(expected):
            c_act = actual[first_diff_idx]
            diff_lines.append(
                f"  Diff at index {first_diff_idx}: actual={c_act!r} (hex: {hex(ord(c_act))}) vs expected string ended (length {len(expected)})"
            )

    return "\n".join(diff_lines)


def format_sequence_mismatch(actual: Any, expected: Any) -> Tuple[str, str, Optional[int]]:
    """Generate detailed sequence comparison showing length differences and first differing element.

    Returns (explanation_summary, detailed_diff_text, first_diff_index).
    """
    seq_name = type(actual).__name__.capitalize()
    len_a = len(actual)
    len_b = len(expected)
    min_len = min(len_a, len_b)

    first_diff_idx = None
    for i in range(min_len):
        if actual[i] != expected[i]:
            first_diff_idx = i
            break

    if first_diff_idx is None and len_a != len_b:
        first_diff_idx = min_len

    summary_parts = []
    if len_a != len_b:
        summary_parts.append(f"length differs (actual has {len_a}, expected has {len_b})")
    if first_diff_idx is not None and first_diff_idx < min_len:
        summary_parts.append(f"first item differs at index {first_diff_idx}")
    elif first_diff_idx is not None:
        summary_parts.append(f"prefix matches through index {first_diff_idx - 1 if first_diff_idx > 0 else 0}")

    explanation = f"{seq_name.upper()} MISMATCH: {'; '.join(summary_parts) if summary_parts else 'items differ'}."

    lines = ["📋 SEQUENCE / LIST MISMATCH:"]
    lines.append("  Length difference:")
    lines.append(f"    Actual length:   {len_a}")
    lines.append(f"    Expected length: {len_b}")
    lines.append(f"    Difference:      {len_a - len_b:+d} item(s)")

    if first_diff_idx is not None:
        lines.append(f"  First differing element at index {first_diff_idx}:")
        if first_diff_idx < len_a:
            lines.append(f"    Actual:   {format_value_repr(actual[first_diff_idx])} ({type(actual[first_diff_idx]).__name__})")
        else:
            lines.append(f"    Actual:   [End of sequence - length {len_a}]")
        if first_diff_idx < len_b:
            lines.append(f"    Expected: {format_value_repr(expected[first_diff_idx])} ({type(expected[first_diff_idx]).__name__})")
        else:
            lines.append(f"    Expected: [End of sequence - length {len_b}]")
    else:
        lines.append("  All corresponding elements match.")

    return explanation, "\n".join(lines), first_diff_idx


def generate_sequence_diff(actual: Any, expected: Any, first_diff_idx: Optional[int]) -> str:
    """Generate unified diff for lists, tuples, or sequences."""
    _, diff_str, _ = format_sequence_mismatch(actual, expected)
    return diff_str


def format_dict_mismatch(actual: dict, expected: dict) -> Tuple[str, str]:
    """Generate detailed dict comparison showing missing, extra, and differing keys.

    Returns (explanation_summary, detailed_diff_text).
    """
    missing_keys = sorted([k for k in expected if k not in actual], key=lambda x: str(x))
    extra_keys = sorted([k for k in actual if k not in expected], key=lambda x: str(x))
    common_keys = sorted([k for k in actual if k in expected], key=lambda x: str(x))
    val_diffs = {k: (actual[k], expected[k]) for k in common_keys if actual[k] != expected[k]}

    summary_parts = []
    if missing_keys:
        summary_parts.append(f"missing {len(missing_keys)} key(s): {missing_keys}")
    if extra_keys:
        summary_parts.append(f"extra {len(extra_keys)} key(s): {extra_keys}")
    if val_diffs:
        summary_parts.append(f"{len(val_diffs)} value difference(s) in shared keys")

    explanation = f"DICT MISMATCH: {'; '.join(summary_parts) if summary_parts else 'contents differ'}."

    lines = ["📋 DICTIONARY / JSON MISMATCH:"]
    lines.append("  Missing keys (in expected but not actual):")
    if missing_keys:
        for k in missing_keys:
            lines.append(f"    - {k!r}: expected value {expected[k]!r}")
    else:
        lines.append("    (None)")

    lines.append("  Extra keys (in actual but not expected):")
    if extra_keys:
        for k in extra_keys:
            lines.append(f"    + {k!r}: actual value {actual[k]!r}")
    else:
        lines.append("    (None)")

    lines.append("  Value differences for shared keys:")
    if val_diffs:
        for k, (a_v, e_v) in val_diffs.items():
            lines.append(f"    * Key {k!r}:")
            lines.append(f"        Actual:   {format_value_repr(a_v)} ({type(a_v).__name__})")
            lines.append(f"        Expected: {format_value_repr(e_v)} ({type(e_v).__name__})")
    else:
        lines.append("    (None)")

    return explanation, "\n".join(lines)


def generate_dict_diff(actual: dict, expected: dict) -> str:
    """Generate key and value diff for mappings."""
    _, diff_str = format_dict_mismatch(actual, expected)
    return diff_str


def build_assertion_diagnostic(
    actual: Any,
    expected: Any,
    op_str: str,
    code_str: str,
    msg: Optional[str] = None,
) -> AssertionDiagnostic:
    """Build a comprehensive, structured AssertionDiagnostic with deep diffs."""
    actual_type = type(actual).__name__ if actual is not None else "unknown"
    actual_repr = format_value_repr(actual)
    actual_len = get_length(actual)

    expected_type = type(expected).__name__ if expected is not None else "unknown"
    expected_repr = format_value_repr(expected)
    expected_len = get_length(expected)

    explanation, diff_str, first_diff_idx = explain_assertion_failure(
        actual, op_str, expected, msg or ""
    )

    divergence_detail = None
    escape_breakdown = None
    dict_diff_summary = None
    sequence_diff_summary = None

    if isinstance(actual, str) and isinstance(expected, str):
        first_diff_idx, divergence_detail = compute_string_divergence(actual, expected)
        escape_breakdown = format_escape_breakdown(actual, expected)
    elif isinstance(actual, dict) and isinstance(expected, dict):
        _, dict_diff_summary = format_dict_mismatch(actual, expected)
    elif isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        _, sequence_diff_summary, first_diff_idx = format_sequence_mismatch(actual, expected)

    root_hint = generate_root_cause_hint(actual, op_str, expected, first_diff_idx)

    return AssertionDiagnostic(
        assertion_code=code_str,
        op=op_str,
        actual_type=actual_type,
        actual_repr=actual_repr,
        actual_length=actual_len,
        expected_type=expected_type,
        expected_repr=expected_repr,
        expected_length=expected_len,
        char_diff=diff_str,
        first_diff_index=first_diff_idx,
        divergence_detail=divergence_detail,
        escape_breakdown=escape_breakdown,
        dict_diff_summary=dict_diff_summary,
        sequence_diff_summary=sequence_diff_summary,
        root_cause_hint=root_hint,
        message=msg if msg else None,
        explanation=explanation,
        remediation_hint=root_hint,
    )


def explain_assertion_failure(
    actual: Any, op: str, expected: Any, msg: str = ""
) -> Tuple[str, Optional[str], Optional[int]]:
    """Compute plain-English diagnostic summary, detailed diff, and difference index."""
    first_diff_idx = None
    diff_str = None

    # Handle membership operators first (operands naturally have different types)
    if op == "in":
        explanation = f"MEMBERSHIP FAILED: {format_value_repr(actual)} was not found inside {format_value_repr(expected)}."
        diff_str = f"Target {format_value_repr(actual)} not in container {format_value_repr(expected)}"
        return explanation, diff_str, None
    elif op == "not in":
        explanation = f"FORBIDDEN MEMBERSHIP: {format_value_repr(actual)} was unexpectedly found inside {format_value_repr(expected)}."
        diff_str = f"Target {format_value_repr(actual)} unexpectedly present in {format_value_repr(expected)}"
        return explanation, diff_str, None
    elif op in ("<", "<=", ">", ">="):
        explanation = f"COMPARISON FAILED: Condition '{format_value_repr(actual)} {op} {format_value_repr(expected)}' evaluated to False."
        diff_str = f"- Expected condition: actual {op} expected\n  Actual:   {format_value_repr(actual)}\n  Expected: {format_value_repr(expected)}"
        return explanation, diff_str, None
    elif op == "is":
        explanation = f"IDENTITY MISMATCH: Expected {format_value_repr(actual)} is {format_value_repr(expected)} (id(actual)={id(actual)}, id(expected)={id(expected)})."
        return explanation, None, None
    elif op == "is not":
        explanation = f"IDENTITY MATCH: Expected objects not to be identical, but id(actual) == id(expected) == {id(actual)}."
        return explanation, None, None

    # Case 1: Types differ for equality checks
    if type(actual) is not type(expected):
        act_t = type(actual).__name__
        exp_t = type(expected).__name__
        act_r = format_value_repr(actual)
        exp_r = format_value_repr(expected)
        explanation = f"TYPE MISMATCH: Actual is of type '{act_t}' ({act_r}), Expected is of type '{exp_t}' ({exp_r})."
        diff_str = f"- Expected ({exp_t}): {exp_r}\n+ Actual   ({act_t}): {act_r}"
        return explanation, diff_str, None

    # Case 2: Both are strings
    if isinstance(actual, str) and isinstance(expected, str):
        explanation, first_diff_idx = explain_string_diff(actual, expected)
        diff_str = generate_string_char_diff(actual, expected, first_diff_idx)
        return explanation, diff_str, first_diff_idx

    # Case 3: Both are lists or tuples
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        explanation, diff_str, first_diff_idx = format_sequence_mismatch(actual, expected)
        return explanation, diff_str, first_diff_idx

    # Case 4: Both are dicts
    if isinstance(actual, dict) and isinstance(expected, dict):
        explanation, diff_str = format_dict_mismatch(actual, expected)
        return explanation, diff_str, None

    # Case 5: Both are sets
    if isinstance(actual, (set, frozenset)) and isinstance(expected, (set, frozenset)):
        missing = set(expected) - set(actual)
        extra = set(actual) - set(expected)
        parts = []
        if missing:
            parts.append(f"missing elements {list(missing)}")
        if extra:
            parts.append(f"unexpected elements {list(extra)}")
        explanation = f"SET MISMATCH: {'; '.join(parts)}."
        diff_str = f"- Missing from actual: {list(missing)}\n+ Extra in actual: {list(extra)}"
        return explanation, diff_str, None

    # Case 6: Numbers
    if isinstance(actual, (int, float, complex)) and isinstance(expected, (int, float, complex)):
        try:
            diff = actual - expected
            explanation = f"VALUE MISMATCH: Actual value {actual} does not equal Expected value {expected} (difference: {diff:+})."
        except Exception:
            explanation = f"VALUE MISMATCH: Actual value {actual} does not equal Expected value {expected}."
        diff_str = f"- Expected: {expected}\n+ Actual:   {actual}"
        return explanation, diff_str, None

    # Default fallback
    explanation = f"VALUE MISMATCH: Expected {format_value_repr(expected)}, but got {format_value_repr(actual)}."
    diff_str = f"- Expected: {format_value_repr(expected)}\n+ Actual:   {format_value_repr(actual)}"
    return explanation, diff_str, None


def explain_exception_operation(
    exc: BaseException,
    line_code: str,
    failing_frame: Optional[StackFrameInfo],
) -> str:
    """Generate clear, plain-English explanation of what operation triggered the exception."""
    exc_type = type(exc).__name__
    exc_msg = str(exc)

    if exc_type == "AttributeError":
        m = re.search(r"'(.*?)' object has no attribute '(.*?)'", exc_msg)
        if m:
            obj_type, attr = m.group(1), m.group(2)
            return (
                f"Attribute access '.{attr}' failed: Target object is of type '{obj_type}' "
                f"which does not possess this attribute."
            )
        return f"Attribute lookup failed: {exc_msg}"

    elif exc_type == "TypeError":
        if "unsupported operand type" in exc_msg:
            return f"Incompatible types for operator: {exc_msg}."
        elif "missing" in exc_msg and "required positional argument" in exc_msg:
            return f"Function call missing argument(s): {exc_msg}."
        elif "takes" in exc_msg and "positional argument" in exc_msg:
            return f"Function call argument count mismatch: {exc_msg}."
        elif "unexpected keyword argument" in exc_msg:
            return f"Function received unexpected keyword argument: {exc_msg}."
        elif "'NoneType' object is not" in exc_msg:
            return f"Operation on None value: {exc_msg}."
        return f"Type mismatch or invalid operation: {exc_msg}"

    elif exc_type == "KeyError":
        return f"Dictionary key lookup failed: Key {exc_msg} does not exist in mapping."

    elif exc_type == "IndexError":
        return f"Sequence index out of bounds: {exc_msg}."

    elif exc_type == "ZeroDivisionError":
        return "Division or modulo operation failed: Denominator evaluated to zero."

    elif exc_type == "ValueError":
        return f"Invalid value supplied to function or operation: {exc_msg}."

    elif exc_type == "FileNotFoundError":
        return f"Filesystem path does not exist: {exc_msg}."

    elif exc_type in ("ModuleNotFoundError", "ImportError"):
        return f"Module import failed: {exc_msg}."

    elif exc_type == "NameError":
        return f"Name reference failed: {exc_msg}. Variable or symbol is not defined in current scope."

    elif exc_type == "UnboundLocalError":
        return f"Local variable referenced before assignment: {exc_msg}."

    return f"Operation failed with {exc_type}: {exc_msg}"


def matches_expected_exception(exc: BaseException, expect_str: Optional[str]) -> bool:
    """Check if the raised exception matches the expected exception specification.

    Supports:
    - Exception class name: 'ValueError', 'KeyError', 'AssertionError'
    - Fully-qualified name: 'pydantic.ValidationError', 'builtins.ValueError'
    - Comma-separated list: 'ValueError, TypeError'
    - Class inheritance / MRO matching: subclass matches parent type name
    - Case-insensitive fallback
    """
    if not expect_str:
        return False

    targets = [t.strip() for t in expect_str.split(",") if t.strip()]
    exc_type = type(exc)
    exc_type_name = exc_type.__name__
    exc_full_name = f"{exc_type.__module__}.{exc_type_name}"
    mro_names = {cls.__name__ for cls in inspect.getmro(exc_type)}

    for target in targets:
        # Direct class name match
        if target == exc_type_name:
            return True
        # Full module.class match or suffix match
        if target == exc_full_name or exc_full_name.endswith(f".{target}"):
            return True
        # MRO / inheritance match (e.g. target is 'Exception', 'ValueError', etc.)
        if target in mro_names:
            return True
        # Special case: ReproAssertionError is an AssertionError
        if isinstance(exc, ReproAssertionError) and target in ("AssertionError", "ReproAssertionError"):
            return True
        # Case-insensitive comparison
        if target.lower() == exc_type_name.lower() or any(target.lower() == m.lower() for m in mro_names):
            return True

    return False


# =============================================================================
# Runtime Assertion Interceptors
# =============================================================================

def _evaluate_op(left: Any, op_str: str, right: Any) -> bool:
    """Evaluate comparison operator safely."""
    if op_str == "==":
        return bool(left == right)
    elif op_str == "!=":
        return bool(left != right)
    elif op_str == "<":
        return bool(left < right)
    elif op_str == "<=":
        return bool(left <= right)
    elif op_str == ">":
        return bool(left > right)
    elif op_str == ">=":
        return bool(left >= right)
    elif op_str == "is":
        return left is right
    elif op_str == "is not":
        return left is not right
    elif op_str == "in":
        return bool(left in right)
    elif op_str == "not in":
        return bool(left not in right)
    return False


def __repro_assert__(left: Any, op_str: str, right: Any, msg: Any, code_str: str, lineno: int) -> None:
    """Injected runtime helper that intercepts assert statements and captures frames."""
    passed = _evaluate_op(left, op_str, right)
    if not passed:
        frame = inspect.currentframe().f_back if inspect.currentframe() else None
        raise ReproAssertionError(
            actual=left,
            expected=right,
            op=op_str,
            code_str=code_str,
            lineno=lineno,
            msg=str(msg) if msg else "",
            frame=frame,
        )


def __repro_assert_truthy__(val: Any, msg: Any, code_str: str, lineno: int) -> None:
    """Injected runtime helper that intercepts boolean assertions."""
    if not bool(val):
        frame = inspect.currentframe().f_back if inspect.currentframe() else None
        raise ReproAssertionError(
            actual=val,
            expected=True,
            op="truthy",
            code_str=code_str,
            lineno=lineno,
            msg=str(msg) if msg else "",
            frame=frame,
        )


# =============================================================================
# Code Healing and Normalization
# =============================================================================

def auto_heal_unterminated_strings(code: str) -> str:
    """Scan and heal unterminated single-line string literals that contain raw unescaped newlines."""
    out: List[str] = []
    state = "NORMAL"
    i = 0
    n = len(code)

    while i < n:
        c = code[i]

        if state == "NORMAL":
            if c == "#":
                end_comment = code.find("\n", i)
                if end_comment == -1:
                    out.append(code[i:])
                    break
                else:
                    out.append(code[i:end_comment])
                    i = end_comment
                    continue

            if code.startswith("'''", i):
                state = "TRIPLE_SINGLE"
                out.append("'''")
                i += 3
            elif code.startswith('"""', i):
                state = "TRIPLE_DOUBLE"
                out.append('"""')
                i += 3
            elif c == "'":
                state = "SINGLE_SINGLE"
                out.append("'")
                i += 1
            elif c == '"':
                state = "SINGLE_DOUBLE"
                out.append('"')
                i += 1
            else:
                out.append(c)
                i += 1

        elif state == "TRIPLE_SINGLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif code.startswith("'''", i):
                state = "NORMAL"
                out.append("'''")
                i += 3
            else:
                out.append(c)
                i += 1

        elif state == "TRIPLE_DOUBLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif code.startswith('"""', i):
                state = "NORMAL"
                out.append('"""')
                i += 3
            else:
                out.append(c)
                i += 1

        elif state == "SINGLE_SINGLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif c == "'":
                out.append(c)
                state = "NORMAL"
                i += 1
            elif c == "\r":
                if i + 1 < n and code[i + 1] == "\n":
                    out.append("\\r\\n")
                    i += 2
                else:
                    out.append("\\r")
                    i += 1
            elif c == "\n":
                out.append("\\n")
                i += 1
            else:
                out.append(c)
                i += 1

        elif state == "SINGLE_DOUBLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif c == '"':
                out.append(c)
                state = "NORMAL"
                i += 1
            elif c == "\r":
                if i + 1 < n and code[i + 1] == "\n":
                    out.append("\\r\\n")
                    i += 2
                else:
                    out.append("\\r")
                    i += 1
            elif c == "\n":
                out.append("\\n")
                i += 1
            else:
                out.append(c)
                i += 1

    return "".join(out)


def sanitize_assertion_code(raw: str) -> str:
    """Sanitize assertion input string against outer quoting artifacts, markdown fences, and JSON escaped quotes."""
    code = raw.strip()

    # Step 1: Strip markdown code blocks and outer redundant quotes iteratively
    for _ in range(10):
        prev = code
        code = code.strip()

        # Check markdown fences: ```python ... ``` or ```py ... ``` or ``` ... ```
        fence_match = re.match(r"^```[a-zA-Z0-9_\-\+]*\s*\n?(.*?)\n?```$", code, re.DOTALL)
        if fence_match:
            code = fence_match.group(1).strip()
            continue

        # Check escaped outer quotes: \"...\" or \'...\'
        if len(code) >= 4:
            if (code.startswith('\\"') and code.endswith('\\"')) or (code.startswith("\\'") and code.endswith("\\'")):
                code = code[2:-2].strip()
                continue

        # Check triple quotes: """...""" or '''...'''
        if len(code) >= 6:
            if (code.startswith('"""') and code.endswith('"""')) or (code.startswith("'''") and code.endswith("'''")):
                code = code[3:-3].strip()
                continue

        # Check single outer quotes: "..." or '...'
        if len(code) >= 2:
            for q in ('"', "'"):
                if code.startswith(q) and code.endswith(q):
                    candidate = code[1:-1].strip()
                    should_strip = False
                    try:
                        tree = ast.parse(code)
                        # If parsed as a single string literal constant, outer quotes are a redundant wrapper
                        if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
                            if isinstance(tree.body[0].value.value, str):
                                should_strip = True
                    except SyntaxError:
                        should_strip = True

                    if should_strip:
                        code = candidate
                        break

        if code == prev:
            break

    # Step 2: Normalize escaped quotes if passed literally due to double-escaping in JSON
    if '\\"' in code or "\\'" in code:
        needs_norm = False
        try:
            tree = ast.parse(code)
            # If it parsed as a single string constant, it's wrapped in quotes
            if (
                len(tree.body) == 1
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)
            ):
                needs_norm = True
        except SyntaxError:
            needs_norm = True

        if needs_norm:
            code = code.replace('\\"', '"').replace("\\'", "'")

    # Step 3: Check if code is a string literal containing python code (e.g. wrapped in quotes that parsed as string)
    try:
        tree = ast.parse(code)
        if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
            if isinstance(tree.body[0].value.value, str):
                inner_str = tree.body[0].value.value.strip()
                try:
                    inner_tree = ast.parse(inner_str)
                    if inner_tree.body and not (
                        len(inner_tree.body) == 1
                        and isinstance(inner_tree.body[0], ast.Expr)
                        and isinstance(inner_tree.body[0].value, ast.Constant)
                    ):
                        code = inner_str
                except SyntaxError:
                    pass
    except SyntaxError:
        pass

    # Normalize newlines if literal \n was passed improperly
    if "\\n" in code and "\n" not in code:
        code = code.replace("\\n", "\n")

    code = textwrap.dedent(code).strip()
    return code


def clean_and_normalize_code(raw_args: Union[List[str], str]) -> str:
    """Extract code from arbitrary CLI arguments or string, stripping fences, outer quotes, and normalizing indentation."""
    if isinstance(raw_args, str):
        code = raw_args.strip()
    else:
        if any("\n" in t for t in raw_args):
            code = "\n".join(raw_args).strip()
        else:
            code = " ".join(raw_args).strip()

    code = sanitize_assertion_code(code)
    return auto_heal_unterminated_strings(code)


# =============================================================================
# Omnivorous AST Transformer with Assertion Rewriting
# =============================================================================

class OmnivorousCodeTransformer(ast.NodeTransformer):
    """AST Transformer that converts bare comparisons and asserts into introspectable calls."""

    def __init__(self) -> None:
        super().__init__()
        self.transformed_comparisons = 0
        self.explicit_asserts = 0
        self.defined_test_funcs: Set[str] = set()
        self.called_funcs: Set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        name = node.name.lower()
        if name.startswith("test_") or name.endswith("_test") or name == "test":
            self.defined_test_funcs.add(node.name)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        name = node.name.lower()
        if name.startswith("test_") or name.endswith("_test") or name == "test":
            self.defined_test_funcs.add(node.name)
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if isinstance(node.func, ast.Name):
            self.called_funcs.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.called_funcs.add(node.func.attr)
        return self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> ast.AST:
        self.explicit_asserts += 1
        lineno = getattr(node, "lineno", 1)
        code_str = ast.unparse(node) if hasattr(ast, "unparse") else "assert"
        msg_node = node.msg if node.msg is not None else ast.Constant(value="")

        # Rewrite single-comparison asserts to capture operands directly
        if isinstance(node.test, ast.Compare) and len(node.test.ops) == 1:
            op_cls = type(node.test.ops[0])
            op_str = OP_MAP.get(op_cls, "==")
            call = ast.Call(
                func=ast.Name(id="__repro_assert__", ctx=ast.Load()),
                args=[
                    node.test.left,
                    ast.Constant(value=op_str),
                    node.test.comparators[0],
                    msg_node,
                    ast.Constant(value=code_str),
                    ast.Constant(value=lineno),
                ],
                keywords=[],
            )
            return ast.copy_location(ast.Expr(value=call), node)

        # Other asserts (calls, boolean values, multi-comparisons)
        call = ast.Call(
            func=ast.Name(id="__repro_assert_truthy__", ctx=ast.Load()),
            args=[
                node.test,
                msg_node,
                ast.Constant(value=code_str),
                ast.Constant(value=lineno),
            ],
            keywords=[],
        )
        return ast.copy_location(ast.Expr(value=call), node)

    def visit_Expr(self, node: ast.Expr) -> ast.AST:
        # If the statement is a standalone comparison expression: `a == b` or `x in y`
        # Auto-transform it into an introspected assertion
        if isinstance(node.value, ast.Compare) and len(node.value.ops) == 1:
            self.transformed_comparisons += 1
            lineno = getattr(node, "lineno", 1)
            op_cls = type(node.value.ops[0])
            op_str = OP_MAP.get(op_cls, "==")
            code_str = ast.unparse(node.value) if hasattr(ast, "unparse") else "comparison"
            msg = f"Check failed (auto-asserted): {code_str}"
            call = ast.Call(
                func=ast.Name(id="__repro_assert__", ctx=ast.Load()),
                args=[
                    node.value.left,
                    ast.Constant(value=op_str),
                    node.value.comparators[0],
                    ast.Constant(value=msg),
                    ast.Constant(value=f"assert {code_str}"),
                    ast.Constant(value=lineno),
                ],
                keywords=[],
            )
            return ast.copy_location(ast.Expr(value=call), node)

        return self.generic_visit(node)


def prepare_executable_code(code: str) -> Tuple[str, bool, int]:
    """Parse, transform, and auto-wire code for deterministic execution."""
    code = auto_heal_unterminated_strings(code)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, False, 0

    transformer = OmnivorousCodeTransformer()
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)

    has_checks = (transformer.explicit_asserts > 0) or (transformer.transformed_comparisons > 0)
    check_count = transformer.explicit_asserts + transformer.transformed_comparisons

    # Auto-invoke uncalled test functions
    uncalled_tests = transformer.defined_test_funcs - transformer.called_funcs
    if uncalled_tests:
        has_checks = True
        runner_lines = ["\n# --- Auto-generated Test Invocations by repro-check ---"]
        for test_fn in sorted(uncalled_tests):
            runner_lines.append(f"{test_fn}()")
        transformed_code = ast.unparse(tree) + "\n" + "\n".join(runner_lines)
    else:
        transformed_code = ast.unparse(tree)

    return transformed_code, has_checks, check_count


# =============================================================================
# Workspace and Probe Circuit Breaker Management
# =============================================================================

def get_workspace_dir() -> pathlib.Path:
    """Deterministically locate the active repository workspace."""
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / ".git").exists()
                    or (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    ws_standard = pathlib.Path("/workspace")
    if ws_standard.is_dir():
        return ws_standard.resolve()

    return pathlib.Path.cwd().resolve()


def is_workspace_path(path_str: str, ws: pathlib.Path) -> bool:
    """Check if a file path belongs to the active target workspace."""
    if not path_str:
        return False
    try:
        p = pathlib.Path(path_str).resolve()
        ws_res = ws.resolve()
        return ws_res in p.parents or p == ws_res
    except Exception:
        return False


def get_probe_count() -> int:
    """Retrieve the current exploratory probe count."""
    try:
        if PROBE_COUNT_FILE.exists():
            return int(PROBE_COUNT_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return 0


def increment_probe_count() -> int:
    """Increment exploratory probe count atomically."""
    cnt = get_probe_count() + 1
    try:
        PROBE_COUNT_FILE.write_text(str(cnt), encoding="utf-8")
    except Exception:
        pass
    return cnt


def reset_probe_count() -> None:
    """Reset exploratory probe count to 0."""
    try:
        if PROBE_COUNT_FILE.exists():
            PROBE_COUNT_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def workspace_has_modifications(ws: pathlib.Path) -> bool:
    """Check if the workspace currently has uncommitted modified files."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            return True
    except Exception:
        pass
    return False


def is_probe_circuit_breaker_active(ws: pathlib.Path) -> bool:
    """Check if the 2-probe circuit breaker is tripped."""
    if workspace_has_modifications(ws):
        return False
    return get_probe_count() >= 2


# =============================================================================
# Path Containment Guard (Strict /tmp Isolation)
# =============================================================================

class PathContainmentGuard:
    """Active containment guard ensuring all scratch files remain strictly in /tmp.

    Prevents and cleans up any accidental /workspace/tmp/... file creation
    that could pollute git status.
    """

    def __init__(self, ws: pathlib.Path):
        self.ws = ws.resolve()
        self.ws_tmp = self.ws / "tmp"
        self.pre_existing_files: Set[pathlib.Path] = set()
        if self.ws_tmp.exists():
            try:
                self.pre_existing_files = {p.resolve() for p in self.ws_tmp.rglob("*")}
            except Exception:
                pass

    def cleanup_pollution(self) -> List[str]:
        """Purge any scratch files or directories created inside /workspace/tmp."""
        cleaned: List[str] = []
        if not self.ws_tmp.exists():
            return cleaned

        try:
            current_files = {p.resolve() for p in self.ws_tmp.rglob("*")}
            new_files = current_files - self.pre_existing_files
            for p in sorted(new_files, key=lambda x: len(str(x)), reverse=True):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink(missing_ok=True)
                        cleaned.append(str(p))
                    elif p.is_dir() and not any(p.iterdir()):
                        p.rmdir()
                        cleaned.append(str(p))
                except Exception:
                    pass

            if (
                self.ws_tmp.is_dir()
                and not any(self.ws_tmp.iterdir())
                and self.ws_tmp.resolve() not in self.pre_existing_files
            ):
                self.ws_tmp.rmdir()
                cleaned.append(str(self.ws_tmp))
        except Exception:
            pass

        return cleaned


def assert_scratch_path_contained(path: pathlib.Path, ws: pathlib.Path) -> None:
    """Guard that scratch files/directories are strictly outside the workspace."""
    resolved = path.resolve()
    ws_resolved = ws.resolve()
    if resolved == ws_resolved or ws_resolved in resolved.parents:
        raise RuntimeError(
            f"[repro-check] Path containment violation: Scratch path {resolved} is inside workspace {ws_resolved}!"
        )


# =============================================================================
# In-Harness Process Execution
# =============================================================================

def run_harness(
    script_path: pathlib.Path,
    report_path: pathlib.Path,
    expect_exception: Optional[str] = None,
) -> None:
    """Internal runner executed inside isolated subprocess with diagnostic recording."""
    # Defensive Sandboxing: Fast-fail socket timeouts to prevent network hanging
    try:
        import socket
        socket.setdefaulttimeout(3.0)
    except Exception:
        pass

    # Memory runaway guard (prevents infinite while True append loops from crashing container)
    try:
        import resource
        curr_soft, curr_hard = resource.getrlimit(resource.RLIMIT_AS)
        limit_1g = 1024 * 1024 * 1024
        if curr_hard == resource.RLIM_INFINITY or curr_hard >= limit_1g:
            resource.setrlimit(resource.RLIMIT_AS, (min(limit_1g, curr_hard), curr_hard))
    except Exception:
        pass

    source_code = script_path.read_text(encoding="utf-8")

    global_ns: Dict[str, Any] = {
        "__name__": "__main__",
        "__file__": str(script_path),
        "__doc__": None,
        "__builtins__": __builtins__,
        "__repro_assert__": __repro_assert__,
        "__repro_assert_truthy__": __repro_assert_truthy__,
    }

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    report: Optional[DiagnosticReport] = None

    try:
        compiled = compile(source_code, str(script_path), "exec")
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            exec(compiled, global_ns)

        if expect_exception:
            report = DiagnosticReport(
                status="missing_exception",
                exit_code=1,
                summary=f"Expected exception '{expect_exception}' was NOT raised. Execution completed normally.",
                raw_stdout=stdout_capture.getvalue(),
                raw_stderr=stderr_capture.getvalue(),
            )
        else:
            report = DiagnosticReport(
                status="passed",
                exit_code=0,
                summary="All assertions and checks passed with 0 errors.",
                raw_stdout=stdout_capture.getvalue(),
                raw_stderr=stderr_capture.getvalue(),
            )

    except ReproAssertionError as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            locals_dict: Dict[str, VariableInfo] = {}
            if exc.frame:
                for k, v in exc.frame.f_locals.items():
                    if not k.startswith("__") and k not in ("__repro_assert__", "__repro_assert_truthy__"):
                        locals_dict[k] = introspect_variable(k, v)

            assertion_diag = build_assertion_diagnostic(
                actual=exc.actual,
                expected=exc.expected,
                op_str=exc.op,
                code_str=exc.code_str,
                msg=exc.msg,
            )

            report = DiagnosticReport(
                status="assertion_error",
                exit_code=1,
                summary=assertion_diag.explanation,
                assertion_diagnostic=assertion_diag,
                local_variables=locals_dict,
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    except AssertionError as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            tb = exc.__traceback__
            last_tb = tb
            while last_tb and last_tb.tb_next:
                last_tb = last_tb.tb_next

            failing_frame = last_tb.tb_frame if last_tb else None
            failing_lineno = last_tb.tb_lineno if last_tb else 1
            failing_file = failing_frame.f_code.co_filename if failing_frame else str(script_path)

            code_line = linecache.getline(failing_file, failing_lineno).strip()

            locals_dict = {}
            if failing_frame:
                for k, v in failing_frame.f_locals.items():
                    if not k.startswith("__"):
                        locals_dict[k] = introspect_variable(k, v)

            actual_val = None
            expected_val = None
            op_str = "=="

            if code_line:
                try:
                    tree = ast.parse(code_line)
                    if tree.body and isinstance(tree.body[0], ast.Assert):
                        assert_node = tree.body[0]
                        if isinstance(assert_node.test, ast.Compare) and len(assert_node.test.ops) == 1:
                            op_cls = type(assert_node.test.ops[0])
                            op_str = OP_MAP.get(op_cls, "==")
                            if failing_frame:
                                try:
                                    actual_val = eval(compile(ast.Expression(assert_node.test.left), "<eval>", "eval"), failing_frame.f_globals, failing_frame.f_locals)
                                    expected_val = eval(compile(ast.Expression(assert_node.test.comparators[0]), "<eval>", "eval"), failing_frame.f_globals, failing_frame.f_locals)
                                except Exception:
                                    pass
                except Exception:
                    pass

            assertion_diag = build_assertion_diagnostic(
                actual=actual_val,
                expected=expected_val,
                op_str=op_str,
                code_str=code_line or f"assert {str(exc)}",
                msg=str(exc) if str(exc) else None,
            )

            report = DiagnosticReport(
                status="assertion_error",
                exit_code=1,
                summary=assertion_diag.explanation,
                assertion_diagnostic=assertion_diag,
                local_variables=locals_dict,
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    except SystemExit as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()
        exit_code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        if exit_code == 0:
            if expect_exception:
                report = DiagnosticReport(
                    status="missing_exception",
                    exit_code=1,
                    summary=f"Expected exception '{expect_exception}' was NOT raised. Process exited cleanly with code 0.",
                    raw_stdout=stdout_val,
                    raw_stderr=stderr_val,
                )
            else:
                report = DiagnosticReport(
                    status="passed",
                    exit_code=0,
                    summary="Process exited cleanly with code 0.",
                    raw_stdout=stdout_val,
                    raw_stderr=stderr_val,
                )
        else:
            report = DiagnosticReport(
                status="runtime_exception",
                exit_code=exit_code,
                summary=f"Process exited prematurely with code {exit_code}.",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    except SyntaxError as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()
        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            caret_line = f"{' ' * (exc.offset - 1 if exc.offset else 0)}^"
            report = DiagnosticReport(
                status="syntax_error",
                exit_code=1,
                summary=f"SyntaxError: {exc.msg} at line {exc.lineno}",
                raw_stdout=stdout_val,
                raw_stderr=f"  File \"{exc.filename}\", line {exc.lineno}\n    {exc.text.strip() if exc.text else ''}\n    {caret_line}\nSyntaxError: {exc.msg}",
            )

    except BaseException as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            call_stack = extract_call_stack(exc)
            failing_frame_info = call_stack[-1] if call_stack else None

            failing_file = failing_frame_info.filename if failing_frame_info else str(script_path)
            failing_line = failing_frame_info.lineno if failing_frame_info else 1
            failing_code = failing_frame_info.code_context if failing_frame_info else ""
            failing_locals = failing_frame_info.local_variables if failing_frame_info else {}

            operation_desc = explain_exception_operation(exc, failing_code, failing_frame_info)

            exc_diag = ExceptionDiagnostic(
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                failing_file=failing_file,
                failing_line=failing_line,
                failing_code=failing_code,
                operation_description=operation_desc,
                call_stack=call_stack,
            )

            summary_text = (
                f"{type(exc).__name__}: {exc} (Expected: {expect_exception})"
                if expect_exception
                else f"{type(exc).__name__}: {exc}"
            )

            report = DiagnosticReport(
                status="runtime_exception",
                exit_code=1,
                summary=summary_text,
                exception_diagnostic=exc_diag,
                local_variables=failing_locals,
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    if report is not None:
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


# =============================================================================
# Execution and Reporting Engine
# =============================================================================

def execute_script(
    code: str,
    ws: pathlib.Path,
    timeout_secs: int = 15,
    expect_exception: Optional[str] = None,
) -> Tuple[int, str, str, DiagnosticReport]:
    """Execute transformed reproduction code inside an isolated /tmp process."""
    tmp_base = "/tmp" if os.path.isdir("/tmp") else None
    guard = PathContainmentGuard(ws)
    try:
        with tempfile.TemporaryDirectory(dir=tmp_base, prefix="swegemma_repro_") as temp_dir:
            temp_dir_path = pathlib.Path(temp_dir).resolve()
            assert_scratch_path_contained(temp_dir_path, ws)

            script_file = temp_dir_path / "repro_test.py"
            script_file.write_text(code, encoding="utf-8")
            report_file = temp_dir_path / "diagnostic_report.json"

            check_py = pathlib.Path(__file__).resolve()

            cmd = [
                sys.executable,
                str(check_py),
                "--runner",
                str(script_file),
                str(report_file),
            ]
            if expect_exception:
                cmd.extend(["--expect-exception", expect_exception])

            env = os.environ.copy()
            python_paths = []
            if (ws / "src").is_dir():
                python_paths.append(str((ws / "src").resolve()))
            if ws.is_dir():
                python_paths.append(str(ws.resolve()))
            for p in ["/workspace", "/workspace/src"]:
                if p not in python_paths:
                    python_paths.append(p)
            existing_pp = env.get("PYTHONPATH", "")
            if existing_pp:
                for p in existing_pp.split(":"):
                    if p and p not in python_paths:
                        python_paths.append(p)

            env["PYTHONPATH"] = ":".join(python_paths)
            env["SWEGEMMA_WORKSPACE"] = str(ws.resolve())
            env["WORKSPACE_DIR"] = str(ws.resolve())
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            if os.path.isdir("/tmp"):
                env["TMPDIR"] = "/tmp"
                env["TEMP"] = "/tmp"
                env["TMP"] = "/tmp"

            proc = None
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=temp_dir_path,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    start_new_session=True,  # Distinct process group (setsid)
                )
                stdout_out, stderr_out = proc.communicate(timeout=timeout_secs)
                exit_code = proc.returncode
                stdout_out = stdout_out.strip() if stdout_out else ""
                stderr_out = stderr_out.strip() if stderr_out else ""

                if report_file.exists():
                    try:
                        report_data = json.loads(report_file.read_text(encoding="utf-8"))
                        report = DiagnosticReport.model_validate(report_data)
                        return exit_code, stdout_out, stderr_out, report
                    except Exception:
                        pass

                combined_err = f"{stderr_out}\n{stdout_out}".strip()
                status = "error"
                if expect_exception and expect_exception in combined_err:
                    status = "PASSED"
                elif "AssertionError" in combined_err:
                    status = "assertion_error"
                elif "SyntaxError" in combined_err:
                    status = "syntax_error"
                elif exit_code == 0:
                    status = "passed"
                else:
                    status = "runtime_exception"

                fallback_report = DiagnosticReport(
                    status=status,
                    exit_code=exit_code,
                    summary=combined_err.splitlines()[-1] if combined_err else "Execution finished",
                    raw_stdout=stdout_out,
                    raw_stderr=stderr_out,
                )
                return exit_code, stdout_out, stderr_out, fallback_report

            except subprocess.TimeoutExpired:
                # Terminate entire process group cleanly via SIGKILL
                if proc is not None:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    try:
                        proc.communicate(timeout=2)
                    except Exception:
                        pass

                timeout_summary = f"⏱️ Execution timed out after {timeout_secs}s (possible infinite loop in repro script)"
                timeout_report = DiagnosticReport(
                    status="timeout",
                    exit_code=124,
                    summary=timeout_summary,
                    raw_stderr=f"Timeout expired ({timeout_secs}s)",
                )
                return 124, "", timeout_summary, timeout_report
            except Exception as e:
                err_report = DiagnosticReport(
                    status="error",
                    exit_code=1,
                    summary=f"Failed to execute process: {e}",
                    raw_stderr=str(e),
                )
                return 1, "", f"Failed to execute process: {e}", err_report
    finally:
        guard.cleanup_pollution()


def _format_assertion_failure(
    diag_or_actual: Union[AssertionDiagnostic, Any],
    locals_or_expected: Any = None,
) -> Union[List[str], str]:
    """Format assertion failure details, deep diffs, and root cause hints.

    When called with (AssertionDiagnostic, Optional[Dict[str, VariableInfo]]):
        Returns List[str] formatted lines with assertion details and remediation hints.
    When called with (str, str):
        Returns str remediation hint for trailing newlines or boundary mismatches.
    """
    if isinstance(diag_or_actual, str) and isinstance(locals_or_expected, str):
        hint = get_string_remediation_hint(diag_or_actual, locals_or_expected)
        return hint or ""

    if not isinstance(diag_or_actual, AssertionDiagnostic):
        return []

    diag = diag_or_actual
    locals_vars = locals_or_expected if isinstance(locals_or_expected, dict) else None

    lines: List[str] = [
        "[repro-check] 🎯 DEFECT CONFIRMED (Assertion Failed):"
    ]
    if diag.assertion_code:
        lines.append(f"  Failing Statement: {diag.assertion_code}")
    if diag.divergence_detail:
        lines.append(f"  {diag.divergence_detail}")
    elif diag.first_diff_index is not None:
        lines.append(f"  Difference at index: {diag.first_diff_index}")

    lines.append("")
    lines.append("  🔍 DIAGNOSTIC SUMMARY:")
    lines.append(f"    {diag.explanation}")

    # Actionable Diagnostics: Section 💡 ROOT CAUSE HINT FOR LLM:
    root_hint = diag.root_cause_hint or diag.remediation_hint
    if not root_hint and diag.actual_repr and diag.expected_repr:
        try:
            act_val = ast.literal_eval(diag.actual_repr)
            exp_val = ast.literal_eval(diag.expected_repr)
            root_hint = generate_root_cause_hint(act_val, diag.op, exp_val, diag.first_diff_index)
        except Exception:
            pass

    if root_hint:
        lines.append("")
        lines.append("  💡 ROOT CAUSE HINT FOR LLM:")
        for hl in root_hint.splitlines():
            clean_hl = hl.lstrip("💡 HINT: ")
            lines.append(f"    {clean_hl}")

    lines.append("")
    lines.append("  📊 VALUE COMPARISON:")
    if diag.actual_type == "str" and diag.expected_type == "str":
        lines.append(f"    Actual:   {diag.actual_repr} (length {diag.actual_length})")
        lines.append(f"    Expected: {diag.expected_repr} (length {diag.expected_length})")
    else:
        act_len_str = f" (length {diag.actual_length})" if diag.actual_length is not None else ""
        exp_len_str = f" (length {diag.expected_length})" if diag.expected_length is not None else ""
        lines.append(f"    Actual:   {diag.actual_repr}{act_len_str}")
        lines.append(f"    Expected: {diag.expected_repr}{exp_len_str}")

    # Decoded ANSI escape breakdown
    if diag.escape_breakdown:
        lines.append("")
        for el in diag.escape_breakdown.splitlines():
            lines.append(f"  {el}")

    # Dictionary / JSON mismatch
    if diag.dict_diff_summary:
        lines.append("")
        for dl in diag.dict_diff_summary.splitlines():
            lines.append(f"  {dl}")

    # Sequence / List mismatch
    if diag.sequence_diff_summary:
        lines.append("")
        for sl in diag.sequence_diff_summary.splitlines():
            lines.append(f"  {sl}")

    # Character diff (for strings and general comparisons)
    if diag.char_diff and not diag.dict_diff_summary and not diag.sequence_diff_summary:
        lines.append("")
        lines.append("  🔀 CHARACTER DIFF:")
        for dl in diag.char_diff.splitlines():
            lines.append(f"    {dl}")

    if locals_vars:
        lines.append("")
        lines.append("  📦 LOCAL VARIABLES IN FAILING FRAME:")
        for vname, vinfo in locals_vars.items():
            vlen_str = f", len={vinfo.length}" if vinfo.length is not None else ""
            lines.append(f"    {vname} ({vinfo.type_name}{vlen_str}): {vinfo.value_repr}")

    return lines


format_assertion_diagnostic = _format_assertion_failure


def render_report_output(report: DiagnosticReport, has_checks: bool, ws: pathlib.Path) -> str:
    """Render structured report into deterministic human and LLM-friendly diagnostic output."""
    lines: List[str] = []

    if report.status.lower() == "passed":
        if "Expected exception" in report.summary:
            lines.append(f"[repro-check] ✅ PASSED: {report.summary}")
            if report.raw_stdout:
                lines.append(report.raw_stdout)
            return "\n".join(lines)
        if has_checks:
            lines.append("[repro-check] ✅ PASSED: All assertions and checks passed with 0 errors.")
            if report.raw_stdout:
                lines.append(report.raw_stdout)
        else:
            probe_cnt = get_probe_count()
            if is_probe_circuit_breaker_active(ws):
                lines.append(
                    "[repro-check] ⚠️ PROBE BUDGET REACHED (2/2 probes used): "
                    "You have executed 2 exploratory probes without reproducing a defect or failing an assertion. "
                    "Stop probing! Formulate your defect hypothesis, locate candidate source lines, and call edit_file immediately."
                )
            else:
                lines.append(
                    f"[repro-check] ℹ️ PROBE RUN ({probe_cnt}/2 probes used): "
                    f"Code executed cleanly (exit code 0), but contained NO assertions or test functions."
                )
                if report.raw_stdout:
                    lines.append(report.raw_stdout)
        return "\n".join(lines)

    if report.status == "missing_exception":
        lines.append("[repro-check] 🎯 DEFECT CONFIRMED (Expected Exception Not Raised):")
        lines.append(f"  {report.summary}")
        lines.append("")
        lines.append("  🔍 DIAGNOSTIC SUMMARY:")
        lines.append("    The target code executed silently without raising the expected exception.")
        lines.append("    This confirms a missing validation or unhandled condition defect.")
        if report.raw_stdout:
            lines.append("")
            lines.append(f"  Standard Output:\n    {report.raw_stdout.strip()}")
        return "\n".join(lines)

    if report.status == "assertion_error":
        if report.assertion_diagnostic:
            formatted_lines = _format_assertion_failure(report.assertion_diagnostic, report.local_variables)
            return "\n".join(formatted_lines)
        lines.append("[repro-check] 🎯 DEFECT CONFIRMED (Assertion Failed):")
        lines.append(f"  {report.summary}")
        return "\n".join(lines)

    if report.status == "runtime_exception":
        diag = report.exception_diagnostic
        failing_file = diag.failing_file if diag else ""
        is_ws = is_workspace_path(failing_file, ws) or (str(ws) in (report.raw_stderr + report.raw_stdout))

        if is_ws:
            lines.append("[repro-check] 💥 DEFECT REPRODUCED (Workspace Runtime Exception):")
        else:
            lines.append("[repro-check] 💥 DEFECT REPRODUCED (Runtime Exception):")

        if diag:
            lines.append(f"  Exception: {diag.exception_type}: {diag.exception_message}")
            rel_path = diag.failing_file
            try:
                rel_path = str(pathlib.Path(diag.failing_file).relative_to(ws))
            except Exception:
                pass
            lines.append(f"  Location: line {diag.failing_line} in {rel_path}")

            lines.append("")
            lines.append("  🔍 DIAGNOSTIC SUMMARY:")
            lines.append(f"    {diag.operation_description}")

            if diag.failing_code:
                lines.append("")
                lines.append("  📍 FAILING LINE:")
                lines.append(f"    {diag.failing_code}")

            if diag.call_stack:
                lines.append("")
                lines.append("  📚 CALL STACK:")
                for i, frame in enumerate(diag.call_stack, 1):
                    try:
                        frame_rel = str(pathlib.Path(frame.filename).relative_to(ws))
                    except Exception:
                        frame_rel = pathlib.Path(frame.filename).name
                    lines.append(f"    [{i}] {frame_rel}:{frame.lineno} in {frame.function_name}()")
                    if frame.code_context:
                        lines.append(f"        Line: {frame.code_context}")
                    if frame.arguments:
                        arg_strs = [f"{k}={v.value_repr}" for k, v in frame.arguments.items()]
                        lines.append(f"        Arguments: {', '.join(arg_strs)}")

        if report.local_variables:
            lines.append("")
            lines.append("  📦 LOCAL VARIABLES IN FAILING FRAME:")
            for vname, vinfo in report.local_variables.items():
                vlen_str = f", len={vinfo.length}" if vinfo.length is not None else ""
                lines.append(f"    {vname} ({vinfo.type_name}{vlen_str}): {vinfo.value_repr}")

        return "\n".join(lines)

    if report.status == "syntax_error":
        lines.append("[repro-check] ⚠️ TEST SCRIPT SYNTAX ERROR:")
        lines.append(f"  {report.summary}")
        if report.raw_stderr:
            for l in report.raw_stderr.splitlines()[-6:]:
                lines.append(f"    {l}")
        return "\n".join(lines)

    if report.status == "timeout":
        lines.append(f"[repro-check] {report.summary}")
        return "\n".join(lines)

    lines.append(f"[repro-check] ❌ EXECUTION FAILED (Exit code {report.exit_code}):")
    lines.append(f"  {report.summary}")
    if report.raw_stderr:
        for l in report.raw_stderr.splitlines()[-10:]:
            lines.append(f"    {l}")
    return "\n".join(lines)


# =============================================================================
# Main CLI Entrypoint
# =============================================================================

def print_help() -> None:
    """Print comprehensive help and usage guide."""
    help_text = """repro-check: Omnivorous Defect Reproduction & Verification Engine.

Usage:
  python3 check.py [options] [<code>]
  python3 check.py --code "assert 1 == 1" [options]
  python3 check.py --b64 <base64_code> [options]
  python3 check.py --file <script.py> [options]
  cat <script.py> | python3 check.py [options]
  run_skill_script('repro-check', 'check.py', args=['[options]', '<code>'])

Options:
  --code, -c <CODE>             Python code snippet to execute (alternative to positional argument).
  --expect-exception, -e <EXC>  Expect a specific exception type (e.g. ValueError, KeyError, AssertionError).
                                If baseline code fails to raise it, defect_confirmed=True.
                                When the fix causes the exception to be raised, status=PASSED.
  --timeout, -t <SECS>          Execution timeout in seconds (default: 15s). Terminated cleanly via os.killpg.
  --b64, --base64 <B64>         Execute base64-encoded Python assertion code (avoids shell/JSON quote escaping).
  --file, -f <FILE>             Execute raw Python script from the specified file path.
  --stdin, -                    Execute raw Python script read from standard input.
  --help, -h                    Show this help message and exit (exit code 0).

Positional Arguments:
  code                          Python reproduction code snippet to execute.
                                If a single argument is an existing file, it is executed as a script.
                                Multiple positional tokens are joined automatically with spaces.

Guarantees:
  - Omnivorous: auto-asserts comparisons, auto-invokes uncalled test functions, strips fences and redundant outer quotes.
  - Quote sanitization: automatically strips outer quotes and normalizes escaped quotes from JSON.
  - AST pre-parse: validates syntax before writing to /tmp or executing, cleanly reporting SYNTAX_ERROR.
  - Zero git pollution: strictly executes inside isolated /tmp process with Path Containment Guard.
  - Workspace import priority: PYTHONPATH=/workspace:/workspace/src.
  - Deterministic AST diagnostics: plain-English explanations and char diffs.
  - Probe budget limiter: 2-probe cap on exploratory runs; auto-resets on defect or fix.
  - Exit code: exits 0 on pass, exits 1 on fail or syntax error.
"""
    print(help_text.strip())


def main() -> int:
    """Main execution function. Exits 0 on pass, exits 1 on fail/syntax error."""
    try:
        raw_args = sys.argv[1:]

        # Check for help flag
        if any(arg in ("--help", "-h") for arg in raw_args):
            print_help()
            return 0

        # Internal runner mode invoked by execute_script
        if len(raw_args) >= 3 and raw_args[0] == "--runner":
            script_path = pathlib.Path(raw_args[1])
            report_path = pathlib.Path(raw_args[2])
            expect_exc = None
            i = 3
            while i < len(raw_args):
                arg = raw_args[i]
                if arg in ("--expect-exception", "-e") and i + 1 < len(raw_args):
                    expect_exc = raw_args[i + 1]
                    i += 2
                elif arg.startswith(("--expect-exception=", "-e=")):
                    expect_exc = arg.split("=", 1)[1]
                    i += 1
                else:
                    i += 1
            run_harness(script_path, report_path, expect_exception=expect_exc)
            return 0

        # Parse general arguments
        expect_exception: Optional[str] = None
        file_path: Optional[pathlib.Path] = None
        code_arg: Optional[str] = None
        timeout_secs: int = 15
        use_stdin = False
        use_b64 = False
        b64_arg: Optional[str] = None
        code_tokens: List[str] = []

        i = 0
        while i < len(raw_args):
            arg = raw_args[i]
            if arg in ("--expect-exception", "-e") and i + 1 < len(raw_args):
                expect_exception = raw_args[i + 1]
                i += 2
            elif arg.startswith(("--expect-exception=", "-e=")):
                expect_exception = arg.split("=", 1)[1]
                i += 1
            elif arg in ("--timeout", "-t") and i + 1 < len(raw_args):
                try:
                    timeout_secs = int(raw_args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif arg.startswith(("--timeout=", "-t=")):
                try:
                    timeout_secs = int(arg.split("=", 1)[1])
                except ValueError:
                    pass
                i += 1
            elif arg in ("--code", "-c") and i + 1 < len(raw_args):
                code_arg = raw_args[i + 1]
                i += 2
            elif arg.startswith(("--code=", "-c=")):
                code_arg = arg.split("=", 1)[1]
                i += 1
            elif arg in ("--file", "-f") and i + 1 < len(raw_args):
                file_path = pathlib.Path(raw_args[i + 1])
                i += 2
            elif arg.startswith(("--file=", "-f=")):
                file_path = pathlib.Path(arg.split("=", 1)[1])
                i += 1
            elif arg in ("--stdin", "-"):
                use_stdin = True
                i += 1
            elif arg in ("--b64", "--base64"):
                use_b64 = True
                if i + 1 < len(raw_args) and not raw_args[i + 1].startswith("-"):
                    b64_arg = raw_args[i + 1]
                    i += 2
                else:
                    i += 1
            elif arg.startswith(("--b64=", "--base64=")):
                use_b64 = True
                b64_arg = arg.split("=", 1)[1]
                i += 1
            else:
                code_tokens.append(arg)
                i += 1

        # Determine code source
        code = ""
        if code_arg is not None:
            code = code_arg
        elif use_b64:
            if not b64_arg and code_tokens:
                b64_arg = " ".join(code_tokens).strip()
                code_tokens = []
            elif not b64_arg and (use_stdin or not sys.stdin.isatty()):
                b64_arg = sys.stdin.read().strip()

            if not b64_arg:
                print("[repro-check] ⚠️ TEST SCRIPT SYNTAX_ERROR:\n  SYNTAX_ERROR: No base64 payload provided to --b64")
                return 1

            # Sanitize b64_arg of redundant outer quotes
            b64_clean = b64_arg.strip()
            for _ in range(3):
                if (b64_clean.startswith('"') and b64_clean.endswith('"')) or (b64_clean.startswith("'") and b64_clean.endswith("'")):
                    b64_clean = b64_clean[1:-1].strip()
                elif (b64_clean.startswith('\\"') and b64_clean.endswith('\\"')) or (b64_clean.startswith("\\'") and b64_clean.endswith("\\'")):
                    b64_clean = b64_clean[2:-2].strip()

            try:
                pad = len(b64_clean) % 4
                if pad:
                    b64_clean += "=" * (4 - pad)
                code = base64.b64decode(b64_clean).decode("utf-8")
            except Exception as exc:
                print(f"[repro-check] ⚠️ TEST SCRIPT SYNTAX_ERROR:\n  SYNTAX_ERROR: Invalid base64 payload: {exc}")
                return 1
        elif file_path is not None:
            if not file_path.exists():
                print(f"[repro-check] Error: Script file not found: {file_path}")
                return 1
            code = file_path.read_text(encoding="utf-8")
        elif use_stdin:
            code = sys.stdin.read()
        elif code_tokens:
            # Check if single token is a path to an existing .py file
            if len(code_tokens) == 1 and (code_tokens[0].endswith(".py") or "\n" not in code_tokens[0]):
                candidate_path = pathlib.Path(code_tokens[0])
                if candidate_path.is_file():
                    code = candidate_path.read_text(encoding="utf-8")
                else:
                    code = code_tokens[0]
            else:
                if any("\n" in t for t in code_tokens):
                    code = "\n".join(code_tokens)
                else:
                    code = " ".join(code_tokens)
        elif not sys.stdin.isatty():
            piped = sys.stdin.read()
            if piped.strip():
                code = piped

        code = clean_and_normalize_code(code)

        if not code or not code.strip():
            print("[repro-check] No code provided. Usage: check.py [options] [<code>]")
            return 1

        # AST pre-parse syntax validation before writing to /tmp and executing
        try:
            ast.parse(code)
        except SyntaxError as exc:
            if expect_exception and matches_expected_exception(exc, expect_exception):
                report = DiagnosticReport(
                    status="PASSED",
                    exit_code=0,
                    summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                )
                print(f"[repro-check] ✅ PASSED: {report.summary}")
                return 0

            err_line = exc.text.strip() if exc.text else ""
            if not err_line and exc.lineno and 1 <= exc.lineno <= len(code.splitlines()):
                err_line = code.splitlines()[exc.lineno - 1].strip()
            offset = exc.offset or 1
            caret_line = f"{' ' * max(0, offset - 1)}^"
            summary = f"SYNTAX_ERROR: {exc.msg} at line {exc.lineno}"
            raw_err = f"  File \"<assertion>\", line {exc.lineno}\n    {err_line}\n    {caret_line}\nSyntaxError: {exc.msg}"
            report = DiagnosticReport(
                status="syntax_error",
                exit_code=1,
                summary=summary,
                raw_stderr=raw_err,
            )
            print(
                f"[repro-check] ⚠️ TEST SCRIPT SYNTAX_ERROR:\n"
                f"  {summary}\n"
                f"    {err_line}\n"
                f"    {caret_line}\n"
                f"  SyntaxError: {exc.msg}"
            )
            return 1

        ws = get_workspace_dir()

        # If workspace modified, reset probe count immediately
        if workspace_has_modifications(ws):
            reset_probe_count()

        transformed_code, has_checks, check_count = prepare_executable_code(code)

        # If expecting exception, it is an active check
        if expect_exception:
            has_checks = True

        # Check circuit breaker before running pure probes
        if not has_checks and is_probe_circuit_breaker_active(ws):
            rendered = (
                "[repro-check] ⚠️ PROBE BUDGET REACHED (2/2 probes used): "
                "You have executed 2 exploratory probes without reproducing a defect or failing an assertion. "
                "Stop probing! Formulate your defect hypothesis, locate candidate source lines, and call edit_file immediately."
            )
            output = ReproCheckOutput(
                success=False,
                defect_confirmed=False,
                category="probe_budget_reached",
                report=DiagnosticReport(
                    status="probe_budget_reached",
                    exit_code=1,
                    summary="Probe budget reached",
                ),
                rendered_output=rendered,
            )
            print(output.rendered_output)
            return 1

        exit_code, stdout, stderr, report = execute_script(
            transformed_code, ws, timeout_secs=timeout_secs, expect_exception=expect_exception
        )

        # Handle probe count updates
        if report.status.lower() == "passed":
            if has_checks or expect_exception:
                reset_probe_count()
                category = "passed"
                defect_confirmed = False
                success = True
            else:
                increment_probe_count()
                if is_probe_circuit_breaker_active(ws):
                    category = "probe_budget_reached"
                    defect_confirmed = False
                    success = False
                else:
                    category = "probe_run"
                    defect_confirmed = False
                    success = True
        elif report.status == "missing_exception":
            reset_probe_count()
            category = "missing_exception"
            defect_confirmed = True
            success = False
        elif report.status == "assertion_error":
            reset_probe_count()
            category = "assertion_failure"
            defect_confirmed = True
            success = False
        elif report.status == "runtime_exception":
            reset_probe_count()
            failing_file = report.exception_diagnostic.failing_file if report.exception_diagnostic else ""
            category = "workspace_exception" if is_workspace_path(failing_file, ws) else "runtime_exception"
            defect_confirmed = True
            success = False
        elif report.status == "syntax_error":
            category = "syntax_error"
            defect_confirmed = False
            success = False
        elif report.status == "timeout":
            reset_probe_count()
            category = "timeout"
            defect_confirmed = False
            success = False
        else:
            category = "general_failure"
            defect_confirmed = False
            success = False

        rendered = render_report_output(report, has_checks, ws)

        final_output = ReproCheckOutput(
            success=success,
            defect_confirmed=defect_confirmed,
            category=category,
            report=report,
            rendered_output=rendered,
        )

        print(final_output.rendered_output)
        return 0 if success else 1

    except Exception as e:
        print(f"[repro-check] Runner error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
`````

## File: submission/skills/repro-check/check.py
`````python
#!/usr/bin/env python3
"""repro-check: Omnivorous Defect Reproduction & Verification Engine.

V2 Upgrades:
- Native `--expect-exception <ExceptionType>` support:
  Deterministically catches missing-validation defects (defect_confirmed=True when not raised,
  status=PASSED when fix causes the exception to be raised).
- Base64 decode support via `--b64` / `--base64` to cleanly bypass shell/JSON quote escaping.
- Input quote and fence sanitization (strips redundant outer quotes, markdown blocks, and JSON escaped quotes).
- AST pre-parse syntax validation: verifies syntax prior to scratch file generation or execution.
- Raw multiline script execution via `--file`, `--stdin`, or pipes into isolated `/tmp` cwd,
  avoiding CLI quote escaping and emoji truncation.
- Path Containment Guard: Strictly isolates scratch files in `/tmp` and prevents/cleans any
  accidental `/workspace/tmp/...` files that could pollute git status.
- Prioritizes /workspace and /workspace/src in PYTHONPATH.

Omnivorous core features:
- Auto-asserts bare comparison expressions: `a == b` -> `assert a == b`
- Auto-invokes uncalled test functions: `def test_...():`
- Auto-heals unterminated string literals with raw unescaped newlines in `'...'` and `"..."`
- Omnivorous assert acceptance: executions without explicit `assert` that exit 0 are accepted as valid passes
- Bypasses 2-probe circuit breaker when workspace contains modified files (post-edit verification)
- Strips markdown fences (```py, ```python, etc.) and auto-dedents
- Deterministic failure explanations: introspects failing frame, local variables, actual/expected values, char diffs
- Structured 100% Pydantic v2 models for all diagnostic outputs
- Exits 0 on pass, exits 1 on fail/syntax error.
"""

from __future__ import annotations

import ast
import base64
import contextlib
import difflib
import inspect
import io
import json
import linecache
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
import textwrap
import types
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

PROBE_COUNT_FILE = pathlib.Path("/tmp/.swegemma_repro_probe_count")

OP_MAP = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}


# =============================================================================
# 100% Pydantic v2 Structured Diagnostic Models
# =============================================================================

class VariableInfo(BaseModel):
    """Inspected variable details from stack frame."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Variable name")
    type_name: str = Field(..., description="Variable type name")
    value_repr: str = Field(..., description="String representation with visible escape codes")
    length: Optional[int] = Field(default=None, description="Length of sequence or collection if applicable")


class StackFrameInfo(BaseModel):
    """Inspected call stack frame details."""

    model_config = ConfigDict(extra="ignore")

    filename: str = Field(..., description="File path of execution frame")
    lineno: int = Field(..., description="Line number")
    function_name: str = Field(..., description="Function or module name")
    code_context: Optional[str] = Field(default=None, description="Source code line")
    arguments: Dict[str, VariableInfo] = Field(default_factory=dict, description="Function arguments")
    local_variables: Dict[str, VariableInfo] = Field(default_factory=dict, description="Local variables in frame")


class AssertionDiagnostic(BaseModel):
    """Deterministic failure diagnostic for an assertion failure."""

    model_config = ConfigDict(extra="ignore")

    assertion_code: str = Field(..., description="Source code of the failing assertion")
    op: str = Field(default="==", description="Comparison operator (==, !=, in, etc.)")
    actual_type: str = Field(..., description="Type name of actual value")
    actual_repr: str = Field(..., description="Actual value with visible escape codes")
    actual_length: Optional[int] = Field(default=None, description="Length of actual value if applicable")
    expected_type: str = Field(..., description="Type name of expected value")
    expected_repr: str = Field(..., description="Expected value with visible escape codes")
    expected_length: Optional[int] = Field(default=None, description="Length of expected value if applicable")
    char_diff: Optional[str] = Field(default=None, description="Character-by-character or unified diff")
    first_diff_index: Optional[int] = Field(default=None, description="First index where values differ")
    divergence_detail: Optional[str] = Field(default=None, description="Exact divergence detail with hex characters")
    escape_breakdown: Optional[str] = Field(default=None, description="Decoded ANSI escape sequences and control characters")
    dict_diff_summary: Optional[str] = Field(default=None, description="Detailed dictionary diff summary")
    sequence_diff_summary: Optional[str] = Field(default=None, description="Detailed sequence diff summary")
    root_cause_hint: Optional[str] = Field(default=None, description="Actionable root cause hint for LLM")
    message: Optional[str] = Field(default=None, description="Assertion failure message")
    explanation: str = Field(..., description="Plain-English explanation of why assertion failed")
    remediation_hint: Optional[str] = Field(default=None, description="Actionable remediation hint for common defects")


class ExceptionDiagnostic(BaseModel):
    """Deterministic failure diagnostic for an unhandled runtime exception."""

    model_config = ConfigDict(extra="ignore")

    exception_type: str = Field(..., description="Exception class name")
    exception_message: str = Field(..., description="Exception error message")
    failing_file: str = Field(..., description="File where exception occurred")
    failing_line: int = Field(..., description="Line number where exception occurred")
    failing_code: Optional[str] = Field(default=None, description="Failing source line code")
    operation_description: str = Field(..., description="Plain-English explanation of operation that failed")
    call_stack: List[StackFrameInfo] = Field(default_factory=list, description="Call stack frames")


class DiagnosticReport(BaseModel):
    """Full structured reproduction report."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="Status: passed, PASSED, missing_exception, assertion_error, runtime_exception, syntax_error, probe_budget_reached, probe_run, timeout, error")
    exit_code: int = Field(default=0, description="Process exit code")
    summary: str = Field(..., description="High-level diagnostic summary")
    assertion_diagnostic: Optional[AssertionDiagnostic] = Field(default=None, description="Details if assertion failed")
    exception_diagnostic: Optional[ExceptionDiagnostic] = Field(default=None, description="Details if exception occurred")
    local_variables: Dict[str, VariableInfo] = Field(default_factory=dict, description="Local variables in failing frame")
    raw_stdout: str = Field(default="", description="Captured stdout")
    raw_stderr: str = Field(default="", description="Captured stderr")


class ReproCheckInput(BaseModel):
    """Structured input parameters for reproduction check."""

    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Reproduction script code")
    args: List[str] = Field(default_factory=list, description="Original CLI arguments")
    timeout_secs: int = Field(default=15, description="Timeout in seconds")
    workspace_dir: Optional[str] = Field(default=None, description="Path to active workspace")


class ReproCheckOutput(BaseModel):
    """Top-level structured output of repro-check."""

    model_config = ConfigDict(extra="ignore")

    success: bool = Field(..., description="True if verification passed cleanly")
    defect_confirmed: bool = Field(..., description="True if defect was reproduced via assertion or exception")
    category: str = Field(..., description="Category: passed, assertion_failure, workspace_exception, runtime_exception, syntax_error, probe_budget_reached, probe_run, general_failure, missing_exception")
    report: DiagnosticReport = Field(..., description="Structured diagnostic report")
    rendered_output: str = Field(..., description="Rendered human/agent readable text")


VariableInfo.model_rebuild()
StackFrameInfo.model_rebuild()
AssertionDiagnostic.model_rebuild()
ExceptionDiagnostic.model_rebuild()
DiagnosticReport.model_rebuild()
ReproCheckInput.model_rebuild()
ReproCheckOutput.model_rebuild()


# =============================================================================
# Custom Assertion Exception for Zero-Loss Evaluation
# =============================================================================

class ReproAssertionError(AssertionError):
    """Carries exact evaluated operands and failing frame for deterministic explanation."""

    def __init__(
        self,
        actual: Any,
        expected: Any,
        op: str,
        code_str: str,
        lineno: int,
        msg: str = "",
        frame: Optional[types.FrameType] = None,
    ):
        super().__init__(msg or f"Assertion failed: {code_str}")
        self.actual = actual
        self.expected = expected
        self.op = op
        self.code_str = code_str
        self.lineno = lineno
        self.msg = msg
        self.frame = frame


# =============================================================================
# Value Formatting and Diff Helpers
# =============================================================================

def format_value_repr(val: Any, max_len: int = 300) -> str:
    """Format value representation with visible escape codes and safe length cap."""
    try:
        r = repr(val)
        if len(r) > max_len:
            return r[:max_len] + f"... [truncated, total {len(r)} chars]"
        return r
    except Exception:
        return f"<{type(val).__name__} (unprintable)>"


def get_length(val: Any) -> Optional[int]:
    """Safely obtain length of sequence or collection."""
    try:
        return len(val)
    except Exception:
        return None


def introspect_variable(name: str, val: Any) -> VariableInfo:
    """Convert an arbitrary Python runtime variable into a VariableInfo model."""
    return VariableInfo(
        name=name,
        type_name=type(val).__name__,
        value_repr=format_value_repr(val),
        length=get_length(val),
    )


def extract_frame_info(frame: types.FrameType, lineno: int) -> StackFrameInfo:
    """Extract argument and local variable details from a call stack frame."""
    co = frame.f_code
    filename = co.co_filename
    func_name = co.co_name

    # Try reading source line from linecache
    code_context = linecache.getline(filename, lineno).strip() or None

    # Inspect function arguments if applicable
    args_dict: Dict[str, VariableInfo] = {}
    try:
        argvalues = inspect.getargvalues(frame)
        for arg in argvalues.args:
            if arg in frame.f_locals:
                args_dict[arg] = introspect_variable(arg, frame.f_locals[arg])
        if argvalues.varargs and argvalues.varargs in frame.f_locals:
            args_dict[f"*{argvalues.varargs}"] = introspect_variable(argvalues.varargs, frame.f_locals[argvalues.varargs])
        if argvalues.keywords and argvalues.keywords in frame.f_locals:
            args_dict[f"**{argvalues.keywords}"] = introspect_variable(argvalues.keywords, frame.f_locals[argvalues.keywords])
    except Exception:
        pass

    # Extract clean local variables
    locals_dict: Dict[str, VariableInfo] = {}
    for k, v in frame.f_locals.items():
        if not k.startswith("__") and k not in ("__repro_assert__", "__repro_assert_truthy__"):
            locals_dict[k] = introspect_variable(k, v)

    return StackFrameInfo(
        filename=filename,
        lineno=lineno,
        function_name=func_name,
        code_context=code_context,
        arguments=args_dict,
        local_variables=locals_dict,
    )


def extract_call_stack(exc: BaseException) -> List[StackFrameInfo]:
    """Walk an exception's traceback and introspect all stack frames."""
    frames: List[StackFrameInfo] = []
    tb = exc.__traceback__
    this_file = str(pathlib.Path(__file__).resolve())
    while tb is not None:
        frame = tb.tb_frame
        lineno = tb.tb_lineno
        # Filter out internal runner harness frames
        if frame.f_code.co_name == "run_harness" or frame.f_code.co_filename == this_file:
            tb = tb.tb_next
            continue
        frames.append(extract_frame_info(frame, lineno))
        tb = tb.tb_next

    # Fallback to all frames if all were filtered out
    if not frames and exc.__traceback__ is not None:
        tb = exc.__traceback__
        while tb is not None:
            frames.append(extract_frame_info(tb.tb_frame, tb.tb_lineno))
            tb = tb.tb_next

    return frames


# =============================================================================
# ANSI & Control Sequence Decoding
# =============================================================================

ANSI_CSI_RE = re.compile(r"\x1b\[([0-9;]*)([a-zA-Z])")
ANSI_OSC_RE = re.compile(r"\x1b\]([^\x07\x1b]*)(?:\x07|\x1b\\)")
ANSI_ESCAPE_RE = re.compile(
    r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]"
)

SGR_CODES: Dict[str, str] = {
    "0": "Reset / Normal",
    "1": "Bold",
    "2": "Dim / Faint",
    "3": "Italic",
    "4": "Underline",
    "5": "Slow Blink",
    "6": "Rapid Blink",
    "7": "Invert / Reverse video",
    "8": "Concealed / Hidden",
    "9": "Strikethrough / Crossed-out",
    "22": "Normal intensity",
    "23": "Not italic",
    "24": "Not underlined",
    "27": "Not inverted",
    "28": "Reveal (not concealed)",
    "29": "Not crossed out",
    "30": "Black text",
    "31": "Red text",
    "32": "Green text",
    "33": "Yellow text",
    "34": "Blue text",
    "35": "Magenta text",
    "36": "Cyan text",
    "37": "White text",
    "39": "Default text color",
    "40": "Black background",
    "41": "Red background",
    "42": "Green background",
    "43": "Yellow background",
    "44": "Blue background",
    "45": "Magenta background",
    "46": "Cyan background",
    "47": "White background",
    "49": "Default background color",
    "90": "Bright Black / Dark Gray text",
    "91": "Bright Red text",
    "92": "Bright Green text",
    "93": "Bright Yellow text",
    "94": "Bright Blue text",
    "95": "Bright Magenta text",
    "96": "Bright Cyan text",
    "97": "Bright White text",
    "100": "Bright Black background",
    "101": "Bright Red background",
    "102": "Bright Green background",
    "103": "Bright Yellow background",
    "104": "Bright Blue background",
    "105": "Bright Magenta background",
    "106": "Bright Cyan background",
    "107": "Bright White background",
}

CONTROL_CHAR_NAMES: Dict[int, str] = {
    0x00: "NUL (null byte)",
    0x01: "SOH (start of heading)",
    0x02: "STX (start of text)",
    0x03: "ETX (end of text)",
    0x04: "EOT (end of transmission)",
    0x05: "ENQ (enquiry)",
    0x06: "ACK (acknowledge)",
    0x07: "BEL (bell / alert)",
    0x08: "BS (backspace)",
    0x09: "HT (horizontal tab)",
    0x0A: "LF (line feed / newline)",
    0x0B: "VT (vertical tab)",
    0x0C: "FF (form feed)",
    0x0D: "CR (carriage return)",
    0x0E: "SO (shift out)",
    0x0F: "SI (shift in)",
    0x10: "DLE (data link escape)",
    0x11: "DC1 (device control 1)",
    0x12: "DC2 (device control 2)",
    0x13: "DC3 (device control 3)",
    0x14: "DC4 (device control 4)",
    0x15: "NAK (negative acknowledge)",
    0x16: "SYN (synchronous idle)",
    0x17: "ETB (end of trans block)",
    0x18: "CAN (cancel)",
    0x19: "EM (end of medium)",
    0x1A: "SUB (substitute)",
    0x1B: "ESC (escape)",
    0x1C: "FS (file separator)",
    0x1D: "GS (group separator)",
    0x1E: "RS (record separator)",
    0x1F: "US (unit separator)",
    0x7F: "DEL (delete)",
    0x200B: "Zero-Width Space",
    0x200C: "Zero-Width Non-Joiner",
    0x200D: "Zero-Width Joiner",
    0x200E: "Left-to-Right Mark",
    0x200F: "Right-to-Left Mark",
    0xFEFF: "Zero-Width No-Break Space / BOM",
    0x00A0: "Non-Breaking Space",
    0x2028: "Line Separator",
    0x2029: "Paragraph Separator",
}


def decode_ansi_sequence(seq: str) -> str:
    """Decode an ANSI escape sequence into a human-readable description."""
    m_csi = ANSI_CSI_RE.fullmatch(seq)
    if m_csi:
        params, cmd = m_csi.group(1), m_csi.group(2)
        if cmd == "m":
            if not params or params == "0":
                return f"ANSI CSI SGR {seq[2:]}: Reset / Normal"
            param_list = params.split(";")
            meanings = []
            skip_next = 0
            for i, p in enumerate(param_list):
                if skip_next > 0:
                    skip_next -= 1
                    continue
                if p in ("38", "48") and i + 1 < len(param_list):
                    mode = param_list[i + 1]
                    target = "text" if p == "38" else "background"
                    if mode == "5" and i + 2 < len(param_list):
                        color_idx = param_list[i + 2]
                        meanings.append(f"256-color {target} #{color_idx}")
                        skip_next = 2
                        continue
                    elif mode == "2" and i + 4 < len(param_list):
                        r, g, b = param_list[i + 2 : i + 5]
                        meanings.append(f"RGB {target} ({r},{g},{b})")
                        skip_next = 4
                        continue
                desc = SGR_CODES.get(p, f"code {p}")
                meanings.append(desc)
            return f"ANSI CSI SGR {seq[2:]}: {', '.join(meanings)}"
        elif cmd == "K":
            mode = params or "0"
            k_map = {
                "0": "Clear line from cursor to end",
                "1": "Clear line from cursor to start",
                "2": "Clear entire line",
            }
            return f"ANSI CSI {seq[2:]}: {k_map.get(mode, 'Clear line')}"
        elif cmd == "J":
            mode = params or "0"
            j_map = {
                "0": "Clear screen from cursor to end",
                "1": "Clear screen from cursor to start",
                "2": "Clear entire screen",
            }
            return f"ANSI CSI {seq[2:]}: {j_map.get(mode, 'Clear display')}"
        elif cmd in ("H", "f"):
            pos = params or "1;1"
            return f"ANSI CSI {seq[2:]}: Move cursor to row;col {pos}"
        elif cmd == "A":
            return f"ANSI CSI {seq[2:]}: Move cursor up {params or 1} lines"
        elif cmd == "B":
            return f"ANSI CSI {seq[2:]}: Move cursor down {params or 1} lines"
        elif cmd == "C":
            return f"ANSI CSI {seq[2:]}: Move cursor right {params or 1} cols"
        elif cmd == "D":
            return f"ANSI CSI {seq[2:]}: Move cursor left {params or 1} cols"
        else:
            return f"ANSI CSI command '{cmd}' (params: {params or 'none'})"

    m_osc = ANSI_OSC_RE.fullmatch(seq)
    if m_osc:
        content = m_osc.group(1)
        if content.startswith("0;"):
            return f"ANSI OSC 0: Set window title '{content[2:]}'"
        elif content.startswith("8;;"):
            return f"ANSI OSC 8: Hyperlink '{content[3:]}'"
        return f"ANSI OSC: '{content}'"

    return f"ANSI escape sequence: {repr(seq)}"


def scan_escape_and_control_codes(s: str) -> List[Tuple[int, str, str]]:
    """Scan string for ANSI escape sequences and control characters.

    Returns list of (char_index, raw_repr, description).
    """
    results: List[Tuple[int, str, str]] = []
    covered_spans: List[Tuple[int, int]] = []

    # 1. Match ANSI sequences
    for m in ANSI_ESCAPE_RE.finditer(s):
        start, end = m.span()
        seq = m.group(0)
        desc = decode_ansi_sequence(seq)
        results.append((start, repr(seq), desc))
        covered_spans.append((start, end))

    # 2. Match control characters outside covered spans
    for i, c in enumerate(s):
        in_span = any(start <= i < end for start, end in covered_spans)
        if in_span:
            continue
        cp = ord(c)
        if cp in CONTROL_CHAR_NAMES:
            name = CONTROL_CHAR_NAMES[cp]
            results.append((i, repr(c), f"Control char 0x{cp:02x}: {name}"))
        elif cp < 32 and c not in ("\n", "\t"):
            results.append((i, repr(c), f"Control char 0x{cp:02x}: non-printable"))
        elif 127 <= cp <= 159:
            results.append((i, repr(c), f"Control char 0x{cp:02x}: C1 control code"))

    results.sort(key=lambda x: x[0])
    return results


def format_escape_breakdown(actual: str, expected: str) -> Optional[str]:
    """Generate human-readable escape and control sequence breakdown."""
    act_codes = scan_escape_and_control_codes(actual)
    exp_codes = scan_escape_and_control_codes(expected)

    if not act_codes and not exp_codes:
        return None

    lines = ["📟 ANSI & CONTROL ESCAPE BREAKDOWN:"]

    lines.append(f"  Actual ({len(act_codes)} code(s) detected):")
    if act_codes:
        for idx, raw_rep, desc in act_codes:
            lines.append(f"    - Index {idx:3d}: {raw_rep} -> {desc}")
    else:
        lines.append("    (None - plain text, no escape or control sequences)")

    lines.append(f"  Expected ({len(exp_codes)} code(s) detected):")
    if exp_codes:
        for idx, raw_rep, desc in exp_codes:
            lines.append(f"    - Index {idx:3d}: {raw_rep} -> {desc}")
    else:
        lines.append("    (None - plain text, no escape or control sequences)")

    return "\n".join(lines)


def compute_string_divergence(actual: str, expected: str) -> Tuple[Optional[int], str]:
    """Find character index of first divergence and format exact diagnostic."""
    min_len = min(len(actual), len(expected))
    for i in range(min_len):
        if actual[i] != expected[i]:
            c_a = actual[i]
            c_e = expected[i]
            diff_msg = (
                f"Diff at index {i}: actual={c_a!r} (hex: {hex(ord(c_a))}) vs expected={c_e!r} (hex: {hex(ord(c_e))})"
            )
            return i, diff_msg

    if len(actual) < len(expected):
        first_diff = len(actual)
        c_e = expected[first_diff]
        diff_msg = (
            f"Diff at index {first_diff}: actual string ended (length {len(actual)}) vs expected={c_e!r} (hex: {hex(ord(c_e))})"
        )
        return first_diff, diff_msg
    elif len(actual) > len(expected):
        first_diff = len(expected)
        c_a = actual[first_diff]
        diff_msg = (
            f"Diff at index {first_diff}: actual={c_a!r} (hex: {hex(ord(c_a))}) vs expected string ended (length {len(expected)})"
        )
        return first_diff, diff_msg

    return None, "Strings are identical"


def get_string_remediation_hint(actual: Any, expected: Any) -> Optional[str]:
    """Generate targeted remediation hint for common string and boundary defects."""
    if not isinstance(actual, str) or not isinstance(expected, str):
        return None

    if actual == expected:
        return None

    # Degenerate boundary mismatch (empty string vs newline)
    if (actual == "" and expected in ("\n", "\r\n")) or (actual in ("\n", "\r\n") and expected == ""):
        return (
            "💡 HINT: Boundary value mismatch detected. Verify edge-case handling for empty or boundary inputs."
        )

    # Suffix / trailing mismatch (difference is at or near the end, e.g. missing trailing \n, \r\n, or extra trailing whitespace)
    if actual.rstrip() == expected.rstrip():
        return (
            "💡 HINT: Trailing character or newline mismatch. Actual string differs in suffix from expected."
        )

    # Line count mismatch (empty line suppression or newline preservation issue)
    if ("\n" in actual or "\n" in expected) and actual.count("\n") != expected.count("\n"):
        return f"💡 HINT: Line count mismatch detected. Expected {expected.count('\n')} newlines, got {actual.count('\n')}. Check for dropped empty lines or delimiter parsing differences."

    return None


compute_assertion_remediation_hint = get_string_remediation_hint


def generate_root_cause_hint(
    actual: Any,
    op: str,
    expected: Any,
    first_diff_idx: Optional[int] = None,
) -> str:
    """Generate clear, actionable root cause hint for the LLM."""
    if isinstance(actual, str) and isinstance(expected, str):
        act_has_ansi = bool(ANSI_ESCAPE_RE.search(actual))
        exp_has_ansi = bool(ANSI_ESCAPE_RE.search(expected))

        if act_has_ansi and not exp_has_ansi:
            return (
                "Actual string contains ANSI styling/escape codes that are absent from expected. "
                "If plain text was expected, strip ANSI escapes (e.g. using strip_ansi(), Text.plain, "
                "or re.sub(r'\\x1b\\[[0-9;]*[a-zA-Z]', '', text)). "
                "If styled output was expected, update the assertion or expected string with matching ANSI codes."
            )
        elif exp_has_ansi and not act_has_ansi:
            return (
                "Expected string contains ANSI styling/escape codes that are missing from actual output. "
                "Ensure terminal styling, color formatting, or highlighter is enabled and invoked."
            )
        elif act_has_ansi and exp_has_ansi:
            idx_str = f" at index {first_diff_idx}" if first_diff_idx is not None else ""
            return (
                f"ANSI escape sequences differ{idx_str}. "
                "Check the exact style tags, color parameter numbers, or reset codes in the formatting pipeline."
            )

        # Check line ending / CRLF vs LF differences
        if ("\r" in actual and "\r" not in expected) or ("\r" in expected and "\r" not in actual):
            return (
                "Line ending mismatch detected (CRLF '\\r\\n' vs LF '\\n' or carriage return '\\r'). "
                "Normalize line endings using .replace('\\r\\n', '\\n') or str.splitlines()."
            )

        # Check tab vs space indentation
        if ("\t" in actual or "\t" in expected) and actual.expandtabs() == expected.expandtabs():
            return (
                "Tab vs space indentation mismatch detected. "
                "Verify tab expansion or replace tabs with spaces using .expandtabs() or 4 spaces."
            )

        # Check trailing whitespace or newline differences
        if actual.rstrip() == expected.rstrip():
            return (
                "String mismatch is caused by trailing newline or whitespace differences. "
                "Verify rstrip(), strip(), or newline emission logic."
            )

        # Line count mismatch
        if actual.count("\n") != expected.count("\n"):
            return (
                f"Line count mismatch (actual has {actual.count('\n')} newlines, "
                f"expected has {expected.count('\n')}). "
                "Check for dropped empty lines, delimiter parsing, or splitlines() handling."
            )

        # Boundary empty string
        if (actual == "" and expected != "") or (actual != "" and expected == ""):
            return (
                "Boundary value mismatch (empty string vs non-empty string). "
                "Verify edge-case handling for empty or boundary inputs."
            )

        # General string difference
        idx_str = f" at index {first_diff_idx}" if first_diff_idx is not None else ""
        c_a = actual[first_diff_idx] if first_diff_idx is not None and first_diff_idx < len(actual) else "ended"
        c_e = expected[first_diff_idx] if first_diff_idx is not None and first_diff_idx < len(expected) else "ended"
        return (
            f"Strings diverge{idx_str} (actual={c_a!r} vs expected={c_e!r}). "
            "Verify character formatting, escaping, or string manipulation around this position."
        )

    if isinstance(actual, dict) and isinstance(expected, dict):
        missing_keys = [k for k in expected if k not in actual]
        extra_keys = [k for k in actual if k not in expected]
        common_keys = [k for k in actual if k in expected]
        val_diff_keys = [k for k in common_keys if actual[k] != expected[k]]

        hints = []
        if missing_keys:
            hints.append(f"missing expected key(s): {missing_keys}")
        if extra_keys:
            hints.append(f"unexpected extra key(s): {extra_keys}")
        if val_diff_keys:
            hints.append(f"differing values for key(s): {val_diff_keys}")

        hint_desc = "; ".join(hints) if hints else "dictionary contents differ"
        return (
            f"Dictionary mismatch ({hint_desc}). "
            "Check dictionary construction, field serialization, or schema mapping logic."
        )

    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            return (
                f"Sequence length mismatch: actual has {len(actual)} items, expected has {len(expected)}. "
                "Check loop iteration, filtering conditions, or item appending logic."
            )
        idx_str = f" at index {first_diff_idx}" if first_diff_idx is not None else ""
        return (
            f"Sequence elements differ{idx_str}. "
            "Verify item construction, sorting order, or transformation logic at this position."
        )

    if type(actual) is not type(expected):
        return (
            f"Type mismatch: actual is of type '{type(actual).__name__}' but expected '{type(expected).__name__}'. "
            "Check function return type or explicit type casting."
        )

    if isinstance(actual, (int, float, complex)) and isinstance(expected, (int, float, complex)):
        try:
            diff = actual - expected
            return (
                f"Numeric value mismatch: actual is {actual}, expected is {expected} (difference: {diff:+}). "
                "Verify calculation, rounding, or offset logic."
            )
        except Exception:
            pass

    return (
        f"Assertion condition '{op}' failed between actual and expected values. "
        "Inspect the logic computing the actual value to ensure it matches expected criteria."
    )


def explain_string_diff(actual: str, expected: str) -> Tuple[str, Optional[int]]:
    """Generate exact plain-English mismatch explanation and first differing index for strings."""
    min_len = min(len(actual), len(expected))
    first_diff = None
    for i in range(min_len):
        if actual[i] != expected[i]:
            first_diff = i
            break

    act_short = repr(actual)
    exp_short = repr(expected)

    if first_diff is None:
        if len(actual) < len(expected):
            first_diff = len(actual)
            missing = expected[len(actual):]
            missing_repr = repr(missing)
            summary = (
                f"MISMATCH: Actual string ({act_short}, {len(actual)} chars) is missing trailing "
                f"{missing_repr} present in Expected string ({exp_short}, {len(expected)} chars). "
                f"Difference at index {first_diff}."
            )
            return summary, first_diff
        elif len(actual) > len(expected):
            first_diff = len(expected)
            extra = actual[len(expected):]
            extra_repr = repr(extra)
            summary = (
                f"MISMATCH: Actual string ({act_short}, {len(actual)} chars) has unexpected trailing "
                f"{extra_repr} not present in Expected string ({exp_short}, {len(expected)} chars). "
                f"Difference at index {first_diff}."
            )
            return summary, first_diff
        else:
            return "Strings are identical.", None
    else:
        c_act = actual[first_diff]
        c_exp = expected[first_diff]
        case_note = ""
        if c_act.lower() == c_exp.lower():
            case_note = f" (Casing difference: Actual has '{c_act}', Expected has '{c_exp}')"
        summary = (
            f"MISMATCH: Actual string ({act_short}, {len(actual)} chars) differs from "
            f"Expected string ({exp_short}, {len(expected)} chars) at index {first_diff}. "
            f"Actual has {repr(c_act)} (hex: {hex(ord(c_act))}), Expected has {repr(c_exp)} (hex: {hex(ord(c_exp))}){case_note}."
        )
        return summary, first_diff


def generate_string_char_diff(actual: str, expected: str, first_diff_idx: Optional[int]) -> str:
    """Generate unified and character-by-character diff showing exact differences."""
    diff_lines: List[str] = []
    act_repr = repr(actual)
    exp_repr = repr(expected)
    diff_lines.append(f"- Expected: {exp_repr} (len={len(expected)})")
    diff_lines.append(f"+ Actual:   {act_repr} (len={len(actual)})")

    # Character-level ndiff
    nd = list(difflib.ndiff([exp_repr], [act_repr]))
    if len(nd) > 2:
        diff_lines.append("  ndiff:")
        for line in nd:
            diff_lines.append(f"    {line}")

    # Multiline unified diff if string has newlines
    if "\n" in actual or "\n" in expected:
        exp_lines = [l + "\n" for l in expected.splitlines()] or ["\n"]
        act_lines = [l + "\n" for l in actual.splitlines()] or ["\n"]
        ud = list(difflib.unified_diff(exp_lines, act_lines, fromfile="expected", tofile="actual"))
        if ud:
            diff_lines.append("  unified diff:")
            for line in ud:
                diff_lines.append(f"    {line.rstrip()}")

    # Exact index breakdown
    if first_diff_idx is not None:
        if first_diff_idx < len(actual) and first_diff_idx < len(expected):
            c_act = actual[first_diff_idx]
            c_exp = expected[first_diff_idx]
            diff_lines.append(
                f"  Diff at index {first_diff_idx}: actual={c_act!r} (hex: {hex(ord(c_act))}) vs expected={c_exp!r} (hex: {hex(ord(c_exp))})"
            )
        elif first_diff_idx == len(actual) and len(actual) < len(expected):
            c_exp = expected[first_diff_idx]
            diff_lines.append(
                f"  Diff at index {first_diff_idx}: actual string ended (length {len(actual)}) vs expected={c_exp!r} (hex: {hex(ord(c_exp))})"
            )
        elif first_diff_idx == len(expected) and len(actual) > len(expected):
            c_act = actual[first_diff_idx]
            diff_lines.append(
                f"  Diff at index {first_diff_idx}: actual={c_act!r} (hex: {hex(ord(c_act))}) vs expected string ended (length {len(expected)})"
            )

    return "\n".join(diff_lines)


def format_sequence_mismatch(actual: Any, expected: Any) -> Tuple[str, str, Optional[int]]:
    """Generate detailed sequence comparison showing length differences and first differing element.

    Returns (explanation_summary, detailed_diff_text, first_diff_index).
    """
    seq_name = type(actual).__name__.capitalize()
    len_a = len(actual)
    len_b = len(expected)
    min_len = min(len_a, len_b)

    first_diff_idx = None
    for i in range(min_len):
        if actual[i] != expected[i]:
            first_diff_idx = i
            break

    if first_diff_idx is None and len_a != len_b:
        first_diff_idx = min_len

    summary_parts = []
    if len_a != len_b:
        summary_parts.append(f"length differs (actual has {len_a}, expected has {len_b})")
    if first_diff_idx is not None and first_diff_idx < min_len:
        summary_parts.append(f"first item differs at index {first_diff_idx}")
    elif first_diff_idx is not None:
        summary_parts.append(f"prefix matches through index {first_diff_idx - 1 if first_diff_idx > 0 else 0}")

    explanation = f"{seq_name.upper()} MISMATCH: {'; '.join(summary_parts) if summary_parts else 'items differ'}."

    lines = ["📋 SEQUENCE / LIST MISMATCH:"]
    lines.append("  Length difference:")
    lines.append(f"    Actual length:   {len_a}")
    lines.append(f"    Expected length: {len_b}")
    lines.append(f"    Difference:      {len_a - len_b:+d} item(s)")

    if first_diff_idx is not None:
        lines.append(f"  First differing element at index {first_diff_idx}:")
        if first_diff_idx < len_a:
            lines.append(f"    Actual:   {format_value_repr(actual[first_diff_idx])} ({type(actual[first_diff_idx]).__name__})")
        else:
            lines.append(f"    Actual:   [End of sequence - length {len_a}]")
        if first_diff_idx < len_b:
            lines.append(f"    Expected: {format_value_repr(expected[first_diff_idx])} ({type(expected[first_diff_idx]).__name__})")
        else:
            lines.append(f"    Expected: [End of sequence - length {len_b}]")
    else:
        lines.append("  All corresponding elements match.")

    return explanation, "\n".join(lines), first_diff_idx


def generate_sequence_diff(actual: Any, expected: Any, first_diff_idx: Optional[int]) -> str:
    """Generate unified diff for lists, tuples, or sequences."""
    _, diff_str, _ = format_sequence_mismatch(actual, expected)
    return diff_str


def format_dict_mismatch(actual: dict, expected: dict) -> Tuple[str, str]:
    """Generate detailed dict comparison showing missing, extra, and differing keys.

    Returns (explanation_summary, detailed_diff_text).
    """
    missing_keys = sorted([k for k in expected if k not in actual], key=lambda x: str(x))
    extra_keys = sorted([k for k in actual if k not in expected], key=lambda x: str(x))
    common_keys = sorted([k for k in actual if k in expected], key=lambda x: str(x))
    val_diffs = {k: (actual[k], expected[k]) for k in common_keys if actual[k] != expected[k]}

    summary_parts = []
    if missing_keys:
        summary_parts.append(f"missing {len(missing_keys)} key(s): {missing_keys}")
    if extra_keys:
        summary_parts.append(f"extra {len(extra_keys)} key(s): {extra_keys}")
    if val_diffs:
        summary_parts.append(f"{len(val_diffs)} value difference(s) in shared keys")

    explanation = f"DICT MISMATCH: {'; '.join(summary_parts) if summary_parts else 'contents differ'}."

    lines = ["📋 DICTIONARY / JSON MISMATCH:"]
    lines.append("  Missing keys (in expected but not actual):")
    if missing_keys:
        for k in missing_keys:
            lines.append(f"    - {k!r}: expected value {expected[k]!r}")
    else:
        lines.append("    (None)")

    lines.append("  Extra keys (in actual but not expected):")
    if extra_keys:
        for k in extra_keys:
            lines.append(f"    + {k!r}: actual value {actual[k]!r}")
    else:
        lines.append("    (None)")

    lines.append("  Value differences for shared keys:")
    if val_diffs:
        for k, (a_v, e_v) in val_diffs.items():
            lines.append(f"    * Key {k!r}:")
            lines.append(f"        Actual:   {format_value_repr(a_v)} ({type(a_v).__name__})")
            lines.append(f"        Expected: {format_value_repr(e_v)} ({type(e_v).__name__})")
    else:
        lines.append("    (None)")

    return explanation, "\n".join(lines)


def generate_dict_diff(actual: dict, expected: dict) -> str:
    """Generate key and value diff for mappings."""
    _, diff_str = format_dict_mismatch(actual, expected)
    return diff_str


def build_assertion_diagnostic(
    actual: Any,
    expected: Any,
    op_str: str,
    code_str: str,
    msg: Optional[str] = None,
) -> AssertionDiagnostic:
    """Build a comprehensive, structured AssertionDiagnostic with deep diffs."""
    actual_type = type(actual).__name__ if actual is not None else "unknown"
    actual_repr = format_value_repr(actual)
    actual_len = get_length(actual)

    expected_type = type(expected).__name__ if expected is not None else "unknown"
    expected_repr = format_value_repr(expected)
    expected_len = get_length(expected)

    explanation, diff_str, first_diff_idx = explain_assertion_failure(
        actual, op_str, expected, msg or ""
    )

    divergence_detail = None
    escape_breakdown = None
    dict_diff_summary = None
    sequence_diff_summary = None

    if isinstance(actual, str) and isinstance(expected, str):
        first_diff_idx, divergence_detail = compute_string_divergence(actual, expected)
        escape_breakdown = format_escape_breakdown(actual, expected)
    elif isinstance(actual, dict) and isinstance(expected, dict):
        _, dict_diff_summary = format_dict_mismatch(actual, expected)
    elif isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        _, sequence_diff_summary, first_diff_idx = format_sequence_mismatch(actual, expected)

    root_hint = generate_root_cause_hint(actual, op_str, expected, first_diff_idx)

    return AssertionDiagnostic(
        assertion_code=code_str,
        op=op_str,
        actual_type=actual_type,
        actual_repr=actual_repr,
        actual_length=actual_len,
        expected_type=expected_type,
        expected_repr=expected_repr,
        expected_length=expected_len,
        char_diff=diff_str,
        first_diff_index=first_diff_idx,
        divergence_detail=divergence_detail,
        escape_breakdown=escape_breakdown,
        dict_diff_summary=dict_diff_summary,
        sequence_diff_summary=sequence_diff_summary,
        root_cause_hint=root_hint,
        message=msg if msg else None,
        explanation=explanation,
        remediation_hint=root_hint,
    )


def explain_assertion_failure(
    actual: Any, op: str, expected: Any, msg: str = ""
) -> Tuple[str, Optional[str], Optional[int]]:
    """Compute plain-English diagnostic summary, detailed diff, and difference index."""
    first_diff_idx = None
    diff_str = None

    # Handle membership operators first (operands naturally have different types)
    if op == "in":
        explanation = f"MEMBERSHIP FAILED: {format_value_repr(actual)} was not found inside {format_value_repr(expected)}."
        diff_str = f"Target {format_value_repr(actual)} not in container {format_value_repr(expected)}"
        return explanation, diff_str, None
    elif op == "not in":
        explanation = f"FORBIDDEN MEMBERSHIP: {format_value_repr(actual)} was unexpectedly found inside {format_value_repr(expected)}."
        diff_str = f"Target {format_value_repr(actual)} unexpectedly present in {format_value_repr(expected)}"
        return explanation, diff_str, None
    elif op in ("<", "<=", ">", ">="):
        explanation = f"COMPARISON FAILED: Condition '{format_value_repr(actual)} {op} {format_value_repr(expected)}' evaluated to False."
        diff_str = f"- Expected condition: actual {op} expected\n  Actual:   {format_value_repr(actual)}\n  Expected: {format_value_repr(expected)}"
        return explanation, diff_str, None
    elif op == "is":
        explanation = f"IDENTITY MISMATCH: Expected {format_value_repr(actual)} is {format_value_repr(expected)} (id(actual)={id(actual)}, id(expected)={id(expected)})."
        return explanation, None, None
    elif op == "is not":
        explanation = f"IDENTITY MATCH: Expected objects not to be identical, but id(actual) == id(expected) == {id(actual)}."
        return explanation, None, None

    # Case 1: Types differ for equality checks
    if type(actual) is not type(expected):
        act_t = type(actual).__name__
        exp_t = type(expected).__name__
        act_r = format_value_repr(actual)
        exp_r = format_value_repr(expected)
        explanation = f"TYPE MISMATCH: Actual is of type '{act_t}' ({act_r}), Expected is of type '{exp_t}' ({exp_r})."
        diff_str = f"- Expected ({exp_t}): {exp_r}\n+ Actual   ({act_t}): {act_r}"
        return explanation, diff_str, None

    # Case 2: Both are strings
    if isinstance(actual, str) and isinstance(expected, str):
        explanation, first_diff_idx = explain_string_diff(actual, expected)
        diff_str = generate_string_char_diff(actual, expected, first_diff_idx)
        return explanation, diff_str, first_diff_idx

    # Case 3: Both are lists or tuples
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        explanation, diff_str, first_diff_idx = format_sequence_mismatch(actual, expected)
        return explanation, diff_str, first_diff_idx

    # Case 4: Both are dicts
    if isinstance(actual, dict) and isinstance(expected, dict):
        explanation, diff_str = format_dict_mismatch(actual, expected)
        return explanation, diff_str, None

    # Case 5: Both are sets
    if isinstance(actual, (set, frozenset)) and isinstance(expected, (set, frozenset)):
        missing = set(expected) - set(actual)
        extra = set(actual) - set(expected)
        parts = []
        if missing:
            parts.append(f"missing elements {list(missing)}")
        if extra:
            parts.append(f"unexpected elements {list(extra)}")
        explanation = f"SET MISMATCH: {'; '.join(parts)}."
        diff_str = f"- Missing from actual: {list(missing)}\n+ Extra in actual: {list(extra)}"
        return explanation, diff_str, None

    # Case 6: Numbers
    if isinstance(actual, (int, float, complex)) and isinstance(expected, (int, float, complex)):
        try:
            diff = actual - expected
            explanation = f"VALUE MISMATCH: Actual value {actual} does not equal Expected value {expected} (difference: {diff:+})."
        except Exception:
            explanation = f"VALUE MISMATCH: Actual value {actual} does not equal Expected value {expected}."
        diff_str = f"- Expected: {expected}\n+ Actual:   {actual}"
        return explanation, diff_str, None

    # Default fallback
    explanation = f"VALUE MISMATCH: Expected {format_value_repr(expected)}, but got {format_value_repr(actual)}."
    diff_str = f"- Expected: {format_value_repr(expected)}\n+ Actual:   {format_value_repr(actual)}"
    return explanation, diff_str, None


def explain_exception_operation(
    exc: BaseException,
    line_code: str,
    failing_frame: Optional[StackFrameInfo],
) -> str:
    """Generate clear, plain-English explanation of what operation triggered the exception."""
    exc_type = type(exc).__name__
    exc_msg = str(exc)

    if exc_type == "AttributeError":
        m = re.search(r"'(.*?)' object has no attribute '(.*?)'", exc_msg)
        if m:
            obj_type, attr = m.group(1), m.group(2)
            return (
                f"Attribute access '.{attr}' failed: Target object is of type '{obj_type}' "
                f"which does not possess this attribute."
            )
        return f"Attribute lookup failed: {exc_msg}"

    elif exc_type == "TypeError":
        if "unsupported operand type" in exc_msg:
            return f"Incompatible types for operator: {exc_msg}."
        elif "missing" in exc_msg and "required positional argument" in exc_msg:
            return f"Function call missing argument(s): {exc_msg}."
        elif "takes" in exc_msg and "positional argument" in exc_msg:
            return f"Function call argument count mismatch: {exc_msg}."
        elif "unexpected keyword argument" in exc_msg:
            return f"Function received unexpected keyword argument: {exc_msg}."
        elif "'NoneType' object is not" in exc_msg:
            return f"Operation on None value: {exc_msg}."
        return f"Type mismatch or invalid operation: {exc_msg}"

    elif exc_type == "KeyError":
        return f"Dictionary key lookup failed: Key {exc_msg} does not exist in mapping."

    elif exc_type == "IndexError":
        return f"Sequence index out of bounds: {exc_msg}."

    elif exc_type == "ZeroDivisionError":
        return "Division or modulo operation failed: Denominator evaluated to zero."

    elif exc_type == "ValueError":
        return f"Invalid value supplied to function or operation: {exc_msg}."

    elif exc_type == "FileNotFoundError":
        return f"Filesystem path does not exist: {exc_msg}."

    elif exc_type in ("ModuleNotFoundError", "ImportError"):
        return f"Module import failed: {exc_msg}."

    elif exc_type == "NameError":
        return f"Name reference failed: {exc_msg}. Variable or symbol is not defined in current scope."

    elif exc_type == "UnboundLocalError":
        return f"Local variable referenced before assignment: {exc_msg}."

    return f"Operation failed with {exc_type}: {exc_msg}"


def matches_expected_exception(exc: BaseException, expect_str: Optional[str]) -> bool:
    """Check if the raised exception matches the expected exception specification.

    Supports:
    - Exception class name: 'ValueError', 'KeyError', 'AssertionError'
    - Fully-qualified name: 'pydantic.ValidationError', 'builtins.ValueError'
    - Comma-separated list: 'ValueError, TypeError'
    - Class inheritance / MRO matching: subclass matches parent type name
    - Case-insensitive fallback
    """
    if not expect_str:
        return False

    targets = [t.strip() for t in expect_str.split(",") if t.strip()]
    exc_type = type(exc)
    exc_type_name = exc_type.__name__
    exc_full_name = f"{exc_type.__module__}.{exc_type_name}"
    mro_names = {cls.__name__ for cls in inspect.getmro(exc_type)}

    for target in targets:
        # Direct class name match
        if target == exc_type_name:
            return True
        # Full module.class match or suffix match
        if target == exc_full_name or exc_full_name.endswith(f".{target}"):
            return True
        # MRO / inheritance match (e.g. target is 'Exception', 'ValueError', etc.)
        if target in mro_names:
            return True
        # Special case: ReproAssertionError is an AssertionError
        if isinstance(exc, ReproAssertionError) and target in ("AssertionError", "ReproAssertionError"):
            return True
        # Case-insensitive comparison
        if target.lower() == exc_type_name.lower() or any(target.lower() == m.lower() for m in mro_names):
            return True

    return False


# =============================================================================
# Runtime Assertion Interceptors
# =============================================================================

def _evaluate_op(left: Any, op_str: str, right: Any) -> bool:
    """Evaluate comparison operator safely."""
    if op_str == "==":
        return bool(left == right)
    elif op_str == "!=":
        return bool(left != right)
    elif op_str == "<":
        return bool(left < right)
    elif op_str == "<=":
        return bool(left <= right)
    elif op_str == ">":
        return bool(left > right)
    elif op_str == ">=":
        return bool(left >= right)
    elif op_str == "is":
        return left is right
    elif op_str == "is not":
        return left is not right
    elif op_str == "in":
        return bool(left in right)
    elif op_str == "not in":
        return bool(left not in right)
    return False


def __repro_assert__(left: Any, op_str: str, right: Any, msg: Any, code_str: str, lineno: int) -> None:
    """Injected runtime helper that intercepts assert statements and captures frames."""
    passed = _evaluate_op(left, op_str, right)
    if not passed:
        frame = inspect.currentframe().f_back if inspect.currentframe() else None
        raise ReproAssertionError(
            actual=left,
            expected=right,
            op=op_str,
            code_str=code_str,
            lineno=lineno,
            msg=str(msg) if msg else "",
            frame=frame,
        )


def __repro_assert_truthy__(val: Any, msg: Any, code_str: str, lineno: int) -> None:
    """Injected runtime helper that intercepts boolean assertions."""
    if not bool(val):
        frame = inspect.currentframe().f_back if inspect.currentframe() else None
        raise ReproAssertionError(
            actual=val,
            expected=True,
            op="truthy",
            code_str=code_str,
            lineno=lineno,
            msg=str(msg) if msg else "",
            frame=frame,
        )


# =============================================================================
# Code Healing and Normalization
# =============================================================================

def auto_heal_unterminated_strings(code: str) -> str:
    """Scan and heal unterminated single-line string literals that contain raw unescaped newlines."""
    out: List[str] = []
    state = "NORMAL"
    i = 0
    n = len(code)

    while i < n:
        c = code[i]

        if state == "NORMAL":
            if c == "#":
                end_comment = code.find("\n", i)
                if end_comment == -1:
                    out.append(code[i:])
                    break
                else:
                    out.append(code[i:end_comment])
                    i = end_comment
                    continue

            if code.startswith("'''", i):
                state = "TRIPLE_SINGLE"
                out.append("'''")
                i += 3
            elif code.startswith('"""', i):
                state = "TRIPLE_DOUBLE"
                out.append('"""')
                i += 3
            elif c == "'":
                state = "SINGLE_SINGLE"
                out.append("'")
                i += 1
            elif c == '"':
                state = "SINGLE_DOUBLE"
                out.append('"')
                i += 1
            else:
                out.append(c)
                i += 1

        elif state == "TRIPLE_SINGLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif code.startswith("'''", i):
                state = "NORMAL"
                out.append("'''")
                i += 3
            else:
                out.append(c)
                i += 1

        elif state == "TRIPLE_DOUBLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif code.startswith('"""', i):
                state = "NORMAL"
                out.append('"""')
                i += 3
            else:
                out.append(c)
                i += 1

        elif state == "SINGLE_SINGLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif c == "'":
                out.append(c)
                state = "NORMAL"
                i += 1
            elif c == "\r":
                if i + 1 < n and code[i + 1] == "\n":
                    out.append("\\r\\n")
                    i += 2
                else:
                    out.append("\\r")
                    i += 1
            elif c == "\n":
                out.append("\\n")
                i += 1
            else:
                out.append(c)
                i += 1

        elif state == "SINGLE_DOUBLE":
            if c == "\\":
                out.append(c)
                i += 1
                if i < n:
                    out.append(code[i])
                    i += 1
            elif c == '"':
                out.append(c)
                state = "NORMAL"
                i += 1
            elif c == "\r":
                if i + 1 < n and code[i + 1] == "\n":
                    out.append("\\r\\n")
                    i += 2
                else:
                    out.append("\\r")
                    i += 1
            elif c == "\n":
                out.append("\\n")
                i += 1
            else:
                out.append(c)
                i += 1

    return "".join(out)


def sanitize_assertion_code(raw: str) -> str:
    """Sanitize assertion input string against outer quoting artifacts, markdown fences, and JSON escaped quotes."""
    code = raw.strip()

    # Step 1: Strip markdown code blocks and outer redundant quotes iteratively
    for _ in range(10):
        prev = code
        code = code.strip()

        # Check markdown fences: ```python ... ``` or ```py ... ``` or ``` ... ```
        fence_match = re.match(r"^```[a-zA-Z0-9_\-\+]*\s*\n?(.*?)\n?```$", code, re.DOTALL)
        if fence_match:
            code = fence_match.group(1).strip()
            continue

        # Check escaped outer quotes: \"...\" or \'...\'
        if len(code) >= 4:
            if (code.startswith('\\"') and code.endswith('\\"')) or (code.startswith("\\'") and code.endswith("\\'")):
                code = code[2:-2].strip()
                continue

        # Check triple quotes: """...""" or '''...'''
        if len(code) >= 6:
            if (code.startswith('"""') and code.endswith('"""')) or (code.startswith("'''") and code.endswith("'''")):
                code = code[3:-3].strip()
                continue

        # Check single outer quotes: "..." or '...'
        if len(code) >= 2:
            for q in ('"', "'"):
                if code.startswith(q) and code.endswith(q):
                    candidate = code[1:-1].strip()
                    should_strip = False
                    try:
                        tree = ast.parse(code)
                        # If parsed as a single string literal constant, outer quotes are a redundant wrapper
                        if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
                            if isinstance(tree.body[0].value.value, str):
                                should_strip = True
                    except SyntaxError:
                        should_strip = True

                    if should_strip:
                        code = candidate
                        break

        if code == prev:
            break

    # Step 2: Normalize escaped quotes if passed literally due to double-escaping in JSON
    if '\\"' in code or "\\'" in code:
        needs_norm = False
        try:
            tree = ast.parse(code)
            # If it parsed as a single string constant, it's wrapped in quotes
            if (
                len(tree.body) == 1
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)
            ):
                needs_norm = True
        except SyntaxError:
            needs_norm = True

        if needs_norm:
            code = code.replace('\\"', '"').replace("\\'", "'")

    # Step 3: Check if code is a string literal containing python code (e.g. wrapped in quotes that parsed as string)
    try:
        tree = ast.parse(code)
        if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
            if isinstance(tree.body[0].value.value, str):
                inner_str = tree.body[0].value.value.strip()
                try:
                    inner_tree = ast.parse(inner_str)
                    if inner_tree.body and not (
                        len(inner_tree.body) == 1
                        and isinstance(inner_tree.body[0], ast.Expr)
                        and isinstance(inner_tree.body[0].value, ast.Constant)
                    ):
                        code = inner_str
                except SyntaxError:
                    pass
    except SyntaxError:
        pass

    # Normalize newlines if literal \n was passed improperly
    if "\\n" in code and "\n" not in code:
        code = code.replace("\\n", "\n")

    code = textwrap.dedent(code).strip()
    return code


def clean_and_normalize_code(raw_args: Union[List[str], str]) -> str:
    """Extract code from arbitrary CLI arguments or string, stripping fences, outer quotes, and normalizing indentation."""
    if isinstance(raw_args, str):
        code = raw_args.strip()
    else:
        if any("\n" in t for t in raw_args):
            code = "\n".join(raw_args).strip()
        else:
            code = " ".join(raw_args).strip()

    code = sanitize_assertion_code(code)
    return auto_heal_unterminated_strings(code)


# =============================================================================
# Omnivorous AST Transformer with Assertion Rewriting
# =============================================================================

class OmnivorousCodeTransformer(ast.NodeTransformer):
    """AST Transformer that converts bare comparisons and asserts into introspectable calls."""

    def __init__(self) -> None:
        super().__init__()
        self.transformed_comparisons = 0
        self.explicit_asserts = 0
        self.defined_test_funcs: Set[str] = set()
        self.called_funcs: Set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        name = node.name.lower()
        if name.startswith("test_") or name.endswith("_test") or name == "test":
            self.defined_test_funcs.add(node.name)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        name = node.name.lower()
        if name.startswith("test_") or name.endswith("_test") or name == "test":
            self.defined_test_funcs.add(node.name)
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if isinstance(node.func, ast.Name):
            self.called_funcs.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.called_funcs.add(node.func.attr)
        return self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> ast.AST:
        self.explicit_asserts += 1
        lineno = getattr(node, "lineno", 1)
        code_str = ast.unparse(node) if hasattr(ast, "unparse") else "assert"
        msg_node = node.msg if node.msg is not None else ast.Constant(value="")

        # Rewrite single-comparison asserts to capture operands directly
        if isinstance(node.test, ast.Compare) and len(node.test.ops) == 1:
            op_cls = type(node.test.ops[0])
            op_str = OP_MAP.get(op_cls, "==")
            call = ast.Call(
                func=ast.Name(id="__repro_assert__", ctx=ast.Load()),
                args=[
                    node.test.left,
                    ast.Constant(value=op_str),
                    node.test.comparators[0],
                    msg_node,
                    ast.Constant(value=code_str),
                    ast.Constant(value=lineno),
                ],
                keywords=[],
            )
            return ast.copy_location(ast.Expr(value=call), node)

        # Other asserts (calls, boolean values, multi-comparisons)
        call = ast.Call(
            func=ast.Name(id="__repro_assert_truthy__", ctx=ast.Load()),
            args=[
                node.test,
                msg_node,
                ast.Constant(value=code_str),
                ast.Constant(value=lineno),
            ],
            keywords=[],
        )
        return ast.copy_location(ast.Expr(value=call), node)

    def visit_Expr(self, node: ast.Expr) -> ast.AST:
        # If the statement is a standalone comparison expression: `a == b` or `x in y`
        # Auto-transform it into an introspected assertion
        if isinstance(node.value, ast.Compare) and len(node.value.ops) == 1:
            self.transformed_comparisons += 1
            lineno = getattr(node, "lineno", 1)
            op_cls = type(node.value.ops[0])
            op_str = OP_MAP.get(op_cls, "==")
            code_str = ast.unparse(node.value) if hasattr(ast, "unparse") else "comparison"
            msg = f"Check failed (auto-asserted): {code_str}"
            call = ast.Call(
                func=ast.Name(id="__repro_assert__", ctx=ast.Load()),
                args=[
                    node.value.left,
                    ast.Constant(value=op_str),
                    node.value.comparators[0],
                    ast.Constant(value=msg),
                    ast.Constant(value=f"assert {code_str}"),
                    ast.Constant(value=lineno),
                ],
                keywords=[],
            )
            return ast.copy_location(ast.Expr(value=call), node)

        return self.generic_visit(node)


def prepare_executable_code(code: str) -> Tuple[str, bool, int]:
    """Parse, transform, and auto-wire code for deterministic execution."""
    code = auto_heal_unterminated_strings(code)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, False, 0

    transformer = OmnivorousCodeTransformer()
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)

    has_checks = (transformer.explicit_asserts > 0) or (transformer.transformed_comparisons > 0)
    check_count = transformer.explicit_asserts + transformer.transformed_comparisons

    # Auto-invoke uncalled test functions
    uncalled_tests = transformer.defined_test_funcs - transformer.called_funcs
    if uncalled_tests:
        has_checks = True
        runner_lines = ["\n# --- Auto-generated Test Invocations by repro-check ---"]
        for test_fn in sorted(uncalled_tests):
            runner_lines.append(f"{test_fn}()")
        transformed_code = ast.unparse(tree) + "\n" + "\n".join(runner_lines)
    else:
        transformed_code = ast.unparse(tree)

    return transformed_code, has_checks, check_count


# =============================================================================
# Workspace and Probe Circuit Breaker Management
# =============================================================================

def get_workspace_dir() -> pathlib.Path:
    """Deterministically locate the active repository workspace."""
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / ".git").exists()
                    or (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    ws_standard = pathlib.Path("/workspace")
    if ws_standard.is_dir():
        return ws_standard.resolve()

    return pathlib.Path.cwd().resolve()


def is_workspace_path(path_str: str, ws: pathlib.Path) -> bool:
    """Check if a file path belongs to the active target workspace."""
    if not path_str:
        return False
    try:
        p = pathlib.Path(path_str).resolve()
        ws_res = ws.resolve()
        return ws_res in p.parents or p == ws_res
    except Exception:
        return False


def get_probe_count() -> int:
    """Retrieve the current exploratory probe count."""
    try:
        if PROBE_COUNT_FILE.exists():
            return int(PROBE_COUNT_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return 0


def increment_probe_count() -> int:
    """Increment exploratory probe count atomically."""
    cnt = get_probe_count() + 1
    try:
        PROBE_COUNT_FILE.write_text(str(cnt), encoding="utf-8")
    except Exception:
        pass
    return cnt


def reset_probe_count() -> None:
    """Reset exploratory probe count to 0."""
    try:
        if PROBE_COUNT_FILE.exists():
            PROBE_COUNT_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def workspace_has_modifications(ws: pathlib.Path) -> bool:
    """Check if the workspace currently has uncommitted modified files."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            return True
    except Exception:
        pass
    return False


def is_probe_circuit_breaker_active(ws: pathlib.Path) -> bool:
    """Check if the 2-probe circuit breaker is tripped."""
    if workspace_has_modifications(ws):
        return False
    return get_probe_count() >= 2


# =============================================================================
# Path Containment Guard (Strict /tmp Isolation)
# =============================================================================

class PathContainmentGuard:
    """Active containment guard ensuring all scratch files remain strictly in /tmp.

    Prevents and cleans up any accidental /workspace/tmp/... file creation
    that could pollute git status.
    """

    def __init__(self, ws: pathlib.Path):
        self.ws = ws.resolve()
        self.ws_tmp = self.ws / "tmp"
        self.pre_existing_files: Set[pathlib.Path] = set()
        if self.ws_tmp.exists():
            try:
                self.pre_existing_files = {p.resolve() for p in self.ws_tmp.rglob("*")}
            except Exception:
                pass

    def cleanup_pollution(self) -> List[str]:
        """Purge any scratch files or directories created inside /workspace/tmp."""
        cleaned: List[str] = []
        if not self.ws_tmp.exists():
            return cleaned

        try:
            current_files = {p.resolve() for p in self.ws_tmp.rglob("*")}
            new_files = current_files - self.pre_existing_files
            for p in sorted(new_files, key=lambda x: len(str(x)), reverse=True):
                try:
                    if p.is_file() or p.is_symlink():
                        p.unlink(missing_ok=True)
                        cleaned.append(str(p))
                    elif p.is_dir() and not any(p.iterdir()):
                        p.rmdir()
                        cleaned.append(str(p))
                except Exception:
                    pass

            if (
                self.ws_tmp.is_dir()
                and not any(self.ws_tmp.iterdir())
                and self.ws_tmp.resolve() not in self.pre_existing_files
            ):
                self.ws_tmp.rmdir()
                cleaned.append(str(self.ws_tmp))
        except Exception:
            pass

        return cleaned


def assert_scratch_path_contained(path: pathlib.Path, ws: pathlib.Path) -> None:
    """Guard that scratch files/directories are strictly outside the workspace."""
    resolved = path.resolve()
    ws_resolved = ws.resolve()
    if resolved == ws_resolved or ws_resolved in resolved.parents:
        raise RuntimeError(
            f"[repro-check] Path containment violation: Scratch path {resolved} is inside workspace {ws_resolved}!"
        )


# =============================================================================
# In-Harness Process Execution
# =============================================================================

def run_harness(
    script_path: pathlib.Path,
    report_path: pathlib.Path,
    expect_exception: Optional[str] = None,
) -> None:
    """Internal runner executed inside isolated subprocess with diagnostic recording."""
    # Defensive Sandboxing: Fast-fail socket timeouts to prevent network hanging
    try:
        import socket
        socket.setdefaulttimeout(3.0)
    except Exception:
        pass

    # Memory runaway guard (prevents infinite while True append loops from crashing container)
    try:
        import resource
        curr_soft, curr_hard = resource.getrlimit(resource.RLIMIT_AS)
        limit_1g = 1024 * 1024 * 1024
        if curr_hard == resource.RLIM_INFINITY or curr_hard >= limit_1g:
            resource.setrlimit(resource.RLIMIT_AS, (min(limit_1g, curr_hard), curr_hard))
    except Exception:
        pass

    source_code = script_path.read_text(encoding="utf-8")

    global_ns: Dict[str, Any] = {
        "__name__": "__main__",
        "__file__": str(script_path),
        "__doc__": None,
        "__builtins__": __builtins__,
        "__repro_assert__": __repro_assert__,
        "__repro_assert_truthy__": __repro_assert_truthy__,
    }

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    report: Optional[DiagnosticReport] = None

    try:
        compiled = compile(source_code, str(script_path), "exec")
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            exec(compiled, global_ns)

        if expect_exception:
            report = DiagnosticReport(
                status="missing_exception",
                exit_code=1,
                summary=f"Expected exception '{expect_exception}' was NOT raised. Execution completed normally.",
                raw_stdout=stdout_capture.getvalue(),
                raw_stderr=stderr_capture.getvalue(),
            )
        else:
            report = DiagnosticReport(
                status="passed",
                exit_code=0,
                summary="All assertions and checks passed with 0 errors.",
                raw_stdout=stdout_capture.getvalue(),
                raw_stderr=stderr_capture.getvalue(),
            )

    except ReproAssertionError as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            locals_dict: Dict[str, VariableInfo] = {}
            if exc.frame:
                for k, v in exc.frame.f_locals.items():
                    if not k.startswith("__") and k not in ("__repro_assert__", "__repro_assert_truthy__"):
                        locals_dict[k] = introspect_variable(k, v)

            assertion_diag = build_assertion_diagnostic(
                actual=exc.actual,
                expected=exc.expected,
                op_str=exc.op,
                code_str=exc.code_str,
                msg=exc.msg,
            )

            report = DiagnosticReport(
                status="assertion_error",
                exit_code=1,
                summary=assertion_diag.explanation,
                assertion_diagnostic=assertion_diag,
                local_variables=locals_dict,
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    except AssertionError as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            tb = exc.__traceback__
            last_tb = tb
            while last_tb and last_tb.tb_next:
                last_tb = last_tb.tb_next

            failing_frame = last_tb.tb_frame if last_tb else None
            failing_lineno = last_tb.tb_lineno if last_tb else 1
            failing_file = failing_frame.f_code.co_filename if failing_frame else str(script_path)

            code_line = linecache.getline(failing_file, failing_lineno).strip()

            locals_dict = {}
            if failing_frame:
                for k, v in failing_frame.f_locals.items():
                    if not k.startswith("__"):
                        locals_dict[k] = introspect_variable(k, v)

            actual_val = None
            expected_val = None
            op_str = "=="

            if code_line:
                try:
                    tree = ast.parse(code_line)
                    if tree.body and isinstance(tree.body[0], ast.Assert):
                        assert_node = tree.body[0]
                        if isinstance(assert_node.test, ast.Compare) and len(assert_node.test.ops) == 1:
                            op_cls = type(assert_node.test.ops[0])
                            op_str = OP_MAP.get(op_cls, "==")
                            if failing_frame:
                                try:
                                    actual_val = eval(compile(ast.Expression(assert_node.test.left), "<eval>", "eval"), failing_frame.f_globals, failing_frame.f_locals)
                                    expected_val = eval(compile(ast.Expression(assert_node.test.comparators[0]), "<eval>", "eval"), failing_frame.f_globals, failing_frame.f_locals)
                                except Exception:
                                    pass
                except Exception:
                    pass

            assertion_diag = build_assertion_diagnostic(
                actual=actual_val,
                expected=expected_val,
                op_str=op_str,
                code_str=code_line or f"assert {str(exc)}",
                msg=str(exc) if str(exc) else None,
            )

            report = DiagnosticReport(
                status="assertion_error",
                exit_code=1,
                summary=assertion_diag.explanation,
                assertion_diagnostic=assertion_diag,
                local_variables=locals_dict,
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    except SystemExit as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()
        exit_code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        if exit_code == 0:
            if expect_exception:
                report = DiagnosticReport(
                    status="missing_exception",
                    exit_code=1,
                    summary=f"Expected exception '{expect_exception}' was NOT raised. Process exited cleanly with code 0.",
                    raw_stdout=stdout_val,
                    raw_stderr=stderr_val,
                )
            else:
                report = DiagnosticReport(
                    status="passed",
                    exit_code=0,
                    summary="Process exited cleanly with code 0.",
                    raw_stdout=stdout_val,
                    raw_stderr=stderr_val,
                )
        else:
            report = DiagnosticReport(
                status="runtime_exception",
                exit_code=exit_code,
                summary=f"Process exited prematurely with code {exit_code}.",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    except SyntaxError as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()
        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            caret_line = f"{' ' * (exc.offset - 1 if exc.offset else 0)}^"
            report = DiagnosticReport(
                status="syntax_error",
                exit_code=1,
                summary=f"SyntaxError: {exc.msg} at line {exc.lineno}",
                raw_stdout=stdout_val,
                raw_stderr=f"  File \"{exc.filename}\", line {exc.lineno}\n    {exc.text.strip() if exc.text else ''}\n    {caret_line}\nSyntaxError: {exc.msg}",
            )

    except BaseException as exc:
        stdout_val = stdout_capture.getvalue()
        stderr_val = stderr_capture.getvalue()

        if expect_exception and matches_expected_exception(exc, expect_exception):
            report = DiagnosticReport(
                status="PASSED",
                exit_code=0,
                summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )
        else:
            call_stack = extract_call_stack(exc)
            failing_frame_info = call_stack[-1] if call_stack else None

            failing_file = failing_frame_info.filename if failing_frame_info else str(script_path)
            failing_line = failing_frame_info.lineno if failing_frame_info else 1
            failing_code = failing_frame_info.code_context if failing_frame_info else ""
            failing_locals = failing_frame_info.local_variables if failing_frame_info else {}

            operation_desc = explain_exception_operation(exc, failing_code, failing_frame_info)

            exc_diag = ExceptionDiagnostic(
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                failing_file=failing_file,
                failing_line=failing_line,
                failing_code=failing_code,
                operation_description=operation_desc,
                call_stack=call_stack,
            )

            summary_text = (
                f"{type(exc).__name__}: {exc} (Expected: {expect_exception})"
                if expect_exception
                else f"{type(exc).__name__}: {exc}"
            )

            report = DiagnosticReport(
                status="runtime_exception",
                exit_code=1,
                summary=summary_text,
                exception_diagnostic=exc_diag,
                local_variables=failing_locals,
                raw_stdout=stdout_val,
                raw_stderr=stderr_val,
            )

    if report is not None:
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


# =============================================================================
# Execution and Reporting Engine
# =============================================================================

def execute_script(
    code: str,
    ws: pathlib.Path,
    timeout_secs: int = 15,
    expect_exception: Optional[str] = None,
) -> Tuple[int, str, str, DiagnosticReport]:
    """Execute transformed reproduction code inside an isolated /tmp process."""
    tmp_base = "/tmp" if os.path.isdir("/tmp") else None
    guard = PathContainmentGuard(ws)
    try:
        with tempfile.TemporaryDirectory(dir=tmp_base, prefix="swegemma_repro_") as temp_dir:
            temp_dir_path = pathlib.Path(temp_dir).resolve()
            assert_scratch_path_contained(temp_dir_path, ws)

            script_file = temp_dir_path / "repro_test.py"
            script_file.write_text(code, encoding="utf-8")
            report_file = temp_dir_path / "diagnostic_report.json"

            check_py = pathlib.Path(__file__).resolve()

            cmd = [
                sys.executable,
                str(check_py),
                "--runner",
                str(script_file),
                str(report_file),
            ]
            if expect_exception:
                cmd.extend(["--expect-exception", expect_exception])

            env = os.environ.copy()
            python_paths = []
            if (ws / "src").is_dir():
                python_paths.append(str((ws / "src").resolve()))
            if ws.is_dir():
                python_paths.append(str(ws.resolve()))
            for p in ["/workspace", "/workspace/src"]:
                if p not in python_paths:
                    python_paths.append(p)
            existing_pp = env.get("PYTHONPATH", "")
            if existing_pp:
                for p in existing_pp.split(":"):
                    if p and p not in python_paths:
                        python_paths.append(p)

            env["PYTHONPATH"] = ":".join(python_paths)
            env["SWEGEMMA_WORKSPACE"] = str(ws.resolve())
            env["WORKSPACE_DIR"] = str(ws.resolve())
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            if os.path.isdir("/tmp"):
                env["TMPDIR"] = "/tmp"
                env["TEMP"] = "/tmp"
                env["TMP"] = "/tmp"

            proc = None
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=temp_dir_path,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    start_new_session=True,  # Distinct process group (setsid)
                )
                stdout_out, stderr_out = proc.communicate(timeout=timeout_secs)
                exit_code = proc.returncode
                stdout_out = stdout_out.strip() if stdout_out else ""
                stderr_out = stderr_out.strip() if stderr_out else ""

                if report_file.exists():
                    try:
                        report_data = json.loads(report_file.read_text(encoding="utf-8"))
                        report = DiagnosticReport.model_validate(report_data)
                        return exit_code, stdout_out, stderr_out, report
                    except Exception:
                        pass

                combined_err = f"{stderr_out}\n{stdout_out}".strip()
                status = "error"
                if expect_exception and expect_exception in combined_err:
                    status = "PASSED"
                elif "AssertionError" in combined_err:
                    status = "assertion_error"
                elif "SyntaxError" in combined_err:
                    status = "syntax_error"
                elif exit_code == 0:
                    status = "passed"
                else:
                    status = "runtime_exception"

                fallback_report = DiagnosticReport(
                    status=status,
                    exit_code=exit_code,
                    summary=combined_err.splitlines()[-1] if combined_err else "Execution finished",
                    raw_stdout=stdout_out,
                    raw_stderr=stderr_out,
                )
                return exit_code, stdout_out, stderr_out, fallback_report

            except subprocess.TimeoutExpired:
                # Terminate entire process group cleanly via SIGKILL
                if proc is not None:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    try:
                        proc.communicate(timeout=2)
                    except Exception:
                        pass

                timeout_summary = f"⏱️ Execution timed out after {timeout_secs}s (possible infinite loop in repro script)"
                timeout_report = DiagnosticReport(
                    status="timeout",
                    exit_code=124,
                    summary=timeout_summary,
                    raw_stderr=f"Timeout expired ({timeout_secs}s)",
                )
                return 124, "", timeout_summary, timeout_report
            except Exception as e:
                err_report = DiagnosticReport(
                    status="error",
                    exit_code=1,
                    summary=f"Failed to execute process: {e}",
                    raw_stderr=str(e),
                )
                return 1, "", f"Failed to execute process: {e}", err_report
    finally:
        guard.cleanup_pollution()


def _format_assertion_failure(
    diag_or_actual: Union[AssertionDiagnostic, Any],
    locals_or_expected: Any = None,
) -> Union[List[str], str]:
    """Format assertion failure details, deep diffs, and root cause hints.

    When called with (AssertionDiagnostic, Optional[Dict[str, VariableInfo]]):
        Returns List[str] formatted lines with assertion details and remediation hints.
    When called with (str, str):
        Returns str remediation hint for trailing newlines or boundary mismatches.
    """
    if isinstance(diag_or_actual, str) and isinstance(locals_or_expected, str):
        hint = get_string_remediation_hint(diag_or_actual, locals_or_expected)
        return hint or ""

    if not isinstance(diag_or_actual, AssertionDiagnostic):
        return []

    diag = diag_or_actual
    locals_vars = locals_or_expected if isinstance(locals_or_expected, dict) else None

    lines: List[str] = [
        "[repro-check] 🎯 DEFECT CONFIRMED (Assertion Failed):"
    ]
    if diag.assertion_code:
        lines.append(f"  Failing Statement: {diag.assertion_code}")
    if diag.divergence_detail:
        lines.append(f"  {diag.divergence_detail}")
    elif diag.first_diff_index is not None:
        lines.append(f"  Difference at index: {diag.first_diff_index}")

    lines.append("")
    lines.append("  🔍 DIAGNOSTIC SUMMARY:")
    lines.append(f"    {diag.explanation}")

    # Actionable Diagnostics: Section 💡 ROOT CAUSE HINT FOR LLM:
    root_hint = diag.root_cause_hint or diag.remediation_hint
    if not root_hint and diag.actual_repr and diag.expected_repr:
        try:
            act_val = ast.literal_eval(diag.actual_repr)
            exp_val = ast.literal_eval(diag.expected_repr)
            root_hint = generate_root_cause_hint(act_val, diag.op, exp_val, diag.first_diff_index)
        except Exception:
            pass

    if root_hint:
        lines.append("")
        lines.append("  💡 ROOT CAUSE HINT FOR LLM:")
        for hl in root_hint.splitlines():
            clean_hl = hl.lstrip("💡 HINT: ")
            lines.append(f"    {clean_hl}")

    lines.append("")
    lines.append("  📊 VALUE COMPARISON:")
    if diag.actual_type == "str" and diag.expected_type == "str":
        lines.append(f"    Actual:   {diag.actual_repr} (length {diag.actual_length})")
        lines.append(f"    Expected: {diag.expected_repr} (length {diag.expected_length})")
    else:
        act_len_str = f" (length {diag.actual_length})" if diag.actual_length is not None else ""
        exp_len_str = f" (length {diag.expected_length})" if diag.expected_length is not None else ""
        lines.append(f"    Actual:   {diag.actual_repr}{act_len_str}")
        lines.append(f"    Expected: {diag.expected_repr}{exp_len_str}")

    # Decoded ANSI escape breakdown
    if diag.escape_breakdown:
        lines.append("")
        for el in diag.escape_breakdown.splitlines():
            lines.append(f"  {el}")

    # Dictionary / JSON mismatch
    if diag.dict_diff_summary:
        lines.append("")
        for dl in diag.dict_diff_summary.splitlines():
            lines.append(f"  {dl}")

    # Sequence / List mismatch
    if diag.sequence_diff_summary:
        lines.append("")
        for sl in diag.sequence_diff_summary.splitlines():
            lines.append(f"  {sl}")

    # Character diff (for strings and general comparisons)
    if diag.char_diff and not diag.dict_diff_summary and not diag.sequence_diff_summary:
        lines.append("")
        lines.append("  🔀 CHARACTER DIFF:")
        for dl in diag.char_diff.splitlines():
            lines.append(f"    {dl}")

    if locals_vars:
        lines.append("")
        lines.append("  📦 LOCAL VARIABLES IN FAILING FRAME:")
        for vname, vinfo in locals_vars.items():
            vlen_str = f", len={vinfo.length}" if vinfo.length is not None else ""
            lines.append(f"    {vname} ({vinfo.type_name}{vlen_str}): {vinfo.value_repr}")

    return lines


format_assertion_diagnostic = _format_assertion_failure


def render_report_output(report: DiagnosticReport, has_checks: bool, ws: pathlib.Path) -> str:
    """Render structured report into deterministic human and LLM-friendly diagnostic output."""
    lines: List[str] = []

    if report.status.lower() == "passed":
        if "Expected exception" in report.summary:
            lines.append(f"[repro-check] ✅ PASSED: {report.summary}")
            if report.raw_stdout:
                lines.append(report.raw_stdout)
            return "\n".join(lines)
        if has_checks:
            lines.append("[repro-check] ✅ PASSED: All assertions and checks passed with 0 errors.")
            if report.raw_stdout:
                lines.append(report.raw_stdout)
        else:
            probe_cnt = get_probe_count()
            if is_probe_circuit_breaker_active(ws):
                lines.append(
                    "[repro-check] ⚠️ PROBE BUDGET REACHED (2/2 probes used): "
                    "You have executed 2 exploratory probes without reproducing a defect or failing an assertion. "
                    "Stop probing! Formulate your defect hypothesis, locate candidate source lines, and call edit_file immediately."
                )
            else:
                lines.append(
                    f"[repro-check] ℹ️ PROBE RUN ({probe_cnt}/2 probes used): "
                    f"Code executed cleanly (exit code 0), but contained NO assertions or test functions."
                )
                if report.raw_stdout:
                    lines.append(report.raw_stdout)
        return "\n".join(lines)

    if report.status == "missing_exception":
        lines.append("[repro-check] 🎯 DEFECT CONFIRMED (Expected Exception Not Raised):")
        lines.append(f"  {report.summary}")
        lines.append("")
        lines.append("  🔍 DIAGNOSTIC SUMMARY:")
        lines.append("    The target code executed silently without raising the expected exception.")
        lines.append("    This confirms a missing validation or unhandled condition defect.")
        if report.raw_stdout:
            lines.append("")
            lines.append(f"  Standard Output:\n    {report.raw_stdout.strip()}")
        return "\n".join(lines)

    if report.status == "assertion_error":
        if report.assertion_diagnostic:
            formatted_lines = _format_assertion_failure(report.assertion_diagnostic, report.local_variables)
            return "\n".join(formatted_lines)
        lines.append("[repro-check] 🎯 DEFECT CONFIRMED (Assertion Failed):")
        lines.append(f"  {report.summary}")
        return "\n".join(lines)

    if report.status == "runtime_exception":
        diag = report.exception_diagnostic
        failing_file = diag.failing_file if diag else ""
        is_ws = is_workspace_path(failing_file, ws) or (str(ws) in (report.raw_stderr + report.raw_stdout))

        if is_ws:
            lines.append("[repro-check] 💥 DEFECT REPRODUCED (Workspace Runtime Exception):")
        else:
            lines.append("[repro-check] 💥 DEFECT REPRODUCED (Runtime Exception):")

        if diag:
            lines.append(f"  Exception: {diag.exception_type}: {diag.exception_message}")
            rel_path = diag.failing_file
            try:
                rel_path = str(pathlib.Path(diag.failing_file).relative_to(ws))
            except Exception:
                pass
            lines.append(f"  Location: line {diag.failing_line} in {rel_path}")

            lines.append("")
            lines.append("  🔍 DIAGNOSTIC SUMMARY:")
            lines.append(f"    {diag.operation_description}")

            if diag.failing_code:
                lines.append("")
                lines.append("  📍 FAILING LINE:")
                lines.append(f"    {diag.failing_code}")

            if diag.call_stack:
                lines.append("")
                lines.append("  📚 CALL STACK:")
                for i, frame in enumerate(diag.call_stack, 1):
                    try:
                        frame_rel = str(pathlib.Path(frame.filename).relative_to(ws))
                    except Exception:
                        frame_rel = pathlib.Path(frame.filename).name
                    lines.append(f"    [{i}] {frame_rel}:{frame.lineno} in {frame.function_name}()")
                    if frame.code_context:
                        lines.append(f"        Line: {frame.code_context}")
                    if frame.arguments:
                        arg_strs = [f"{k}={v.value_repr}" for k, v in frame.arguments.items()]
                        lines.append(f"        Arguments: {', '.join(arg_strs)}")

        if report.local_variables:
            lines.append("")
            lines.append("  📦 LOCAL VARIABLES IN FAILING FRAME:")
            for vname, vinfo in report.local_variables.items():
                vlen_str = f", len={vinfo.length}" if vinfo.length is not None else ""
                lines.append(f"    {vname} ({vinfo.type_name}{vlen_str}): {vinfo.value_repr}")

        return "\n".join(lines)

    if report.status == "syntax_error":
        lines.append("[repro-check] ⚠️ TEST SCRIPT SYNTAX ERROR:")
        lines.append(f"  {report.summary}")
        if report.raw_stderr:
            for l in report.raw_stderr.splitlines()[-6:]:
                lines.append(f"    {l}")
        return "\n".join(lines)

    if report.status == "timeout":
        lines.append(f"[repro-check] {report.summary}")
        return "\n".join(lines)

    lines.append(f"[repro-check] ❌ EXECUTION FAILED (Exit code {report.exit_code}):")
    lines.append(f"  {report.summary}")
    if report.raw_stderr:
        for l in report.raw_stderr.splitlines()[-10:]:
            lines.append(f"    {l}")
    return "\n".join(lines)


# =============================================================================
# Main CLI Entrypoint
# =============================================================================

def print_help() -> None:
    """Print comprehensive help and usage guide."""
    help_text = """repro-check: Omnivorous Defect Reproduction & Verification Engine.

Usage:
  python3 check.py [options] [<code>]
  python3 check.py --code "assert 1 == 1" [options]
  python3 check.py --b64 <base64_code> [options]
  python3 check.py --file <script.py> [options]
  cat <script.py> | python3 check.py [options]
  run_skill_script('repro-check', 'check.py', args=['[options]', '<code>'])

Options:
  --code, -c <CODE>             Python code snippet to execute (alternative to positional argument).
  --expect-exception, -e <EXC>  Expect a specific exception type (e.g. ValueError, KeyError, AssertionError).
                                If baseline code fails to raise it, defect_confirmed=True.
                                When the fix causes the exception to be raised, status=PASSED.
  --timeout, -t <SECS>          Execution timeout in seconds (default: 15s). Terminated cleanly via os.killpg.
  --b64, --base64 <B64>         Execute base64-encoded Python assertion code (avoids shell/JSON quote escaping).
  --file, -f <FILE>             Execute raw Python script from the specified file path.
  --stdin, -                    Execute raw Python script read from standard input.
  --help, -h                    Show this help message and exit (exit code 0).

Positional Arguments:
  code                          Python reproduction code snippet to execute.
                                If a single argument is an existing file, it is executed as a script.
                                Multiple positional tokens are joined automatically with spaces.

Guarantees:
  - Omnivorous: auto-asserts comparisons, auto-invokes uncalled test functions, strips fences and redundant outer quotes.
  - Quote sanitization: automatically strips outer quotes and normalizes escaped quotes from JSON.
  - AST pre-parse: validates syntax before writing to /tmp or executing, cleanly reporting SYNTAX_ERROR.
  - Zero git pollution: strictly executes inside isolated /tmp process with Path Containment Guard.
  - Workspace import priority: PYTHONPATH=/workspace:/workspace/src.
  - Deterministic AST diagnostics: plain-English explanations and char diffs.
  - Probe budget limiter: 2-probe cap on exploratory runs; auto-resets on defect or fix.
  - Exit code: exits 0 on pass, exits 1 on fail or syntax error.
"""
    print(help_text.strip())


def main() -> int:
    """Main execution function. Exits 0 on pass, exits 1 on fail/syntax error."""
    try:
        raw_args = sys.argv[1:]

        # Check for help flag
        if any(arg in ("--help", "-h") for arg in raw_args):
            print_help()
            return 0

        # Internal runner mode invoked by execute_script
        if len(raw_args) >= 3 and raw_args[0] == "--runner":
            script_path = pathlib.Path(raw_args[1])
            report_path = pathlib.Path(raw_args[2])
            expect_exc = None
            i = 3
            while i < len(raw_args):
                arg = raw_args[i]
                if arg in ("--expect-exception", "-e") and i + 1 < len(raw_args):
                    expect_exc = raw_args[i + 1]
                    i += 2
                elif arg.startswith(("--expect-exception=", "-e=")):
                    expect_exc = arg.split("=", 1)[1]
                    i += 1
                else:
                    i += 1
            run_harness(script_path, report_path, expect_exception=expect_exc)
            return 0

        # Parse general arguments
        expect_exception: Optional[str] = None
        file_path: Optional[pathlib.Path] = None
        code_arg: Optional[str] = None
        timeout_secs: int = 15
        use_stdin = False
        use_b64 = False
        b64_arg: Optional[str] = None
        code_tokens: List[str] = []

        i = 0
        while i < len(raw_args):
            arg = raw_args[i]
            if arg in ("--expect-exception", "-e") and i + 1 < len(raw_args):
                expect_exception = raw_args[i + 1]
                i += 2
            elif arg.startswith(("--expect-exception=", "-e=")):
                expect_exception = arg.split("=", 1)[1]
                i += 1
            elif arg in ("--timeout", "-t") and i + 1 < len(raw_args):
                try:
                    timeout_secs = int(raw_args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif arg.startswith(("--timeout=", "-t=")):
                try:
                    timeout_secs = int(arg.split("=", 1)[1])
                except ValueError:
                    pass
                i += 1
            elif arg in ("--code", "-c") and i + 1 < len(raw_args):
                code_arg = raw_args[i + 1]
                i += 2
            elif arg.startswith(("--code=", "-c=")):
                code_arg = arg.split("=", 1)[1]
                i += 1
            elif arg in ("--file", "-f") and i + 1 < len(raw_args):
                file_path = pathlib.Path(raw_args[i + 1])
                i += 2
            elif arg.startswith(("--file=", "-f=")):
                file_path = pathlib.Path(arg.split("=", 1)[1])
                i += 1
            elif arg in ("--stdin", "-"):
                use_stdin = True
                i += 1
            elif arg in ("--b64", "--base64"):
                use_b64 = True
                if i + 1 < len(raw_args) and not raw_args[i + 1].startswith("-"):
                    b64_arg = raw_args[i + 1]
                    i += 2
                else:
                    i += 1
            elif arg.startswith(("--b64=", "--base64=")):
                use_b64 = True
                b64_arg = arg.split("=", 1)[1]
                i += 1
            else:
                code_tokens.append(arg)
                i += 1

        # Determine code source
        code = ""
        if code_arg is not None:
            code = code_arg
        elif use_b64:
            if not b64_arg and code_tokens:
                b64_arg = " ".join(code_tokens).strip()
                code_tokens = []
            elif not b64_arg and (use_stdin or not sys.stdin.isatty()):
                b64_arg = sys.stdin.read().strip()

            if not b64_arg:
                print("[repro-check] ⚠️ TEST SCRIPT SYNTAX_ERROR:\n  SYNTAX_ERROR: No base64 payload provided to --b64")
                return 1

            # Sanitize b64_arg of redundant outer quotes
            b64_clean = b64_arg.strip()
            for _ in range(3):
                if (b64_clean.startswith('"') and b64_clean.endswith('"')) or (b64_clean.startswith("'") and b64_clean.endswith("'")):
                    b64_clean = b64_clean[1:-1].strip()
                elif (b64_clean.startswith('\\"') and b64_clean.endswith('\\"')) or (b64_clean.startswith("\\'") and b64_clean.endswith("\\'")):
                    b64_clean = b64_clean[2:-2].strip()

            try:
                pad = len(b64_clean) % 4
                if pad:
                    b64_clean += "=" * (4 - pad)
                code = base64.b64decode(b64_clean).decode("utf-8")
            except Exception as exc:
                print(f"[repro-check] ⚠️ TEST SCRIPT SYNTAX_ERROR:\n  SYNTAX_ERROR: Invalid base64 payload: {exc}")
                return 1
        elif file_path is not None:
            if not file_path.exists():
                print(f"[repro-check] Error: Script file not found: {file_path}")
                return 1
            code = file_path.read_text(encoding="utf-8")
        elif use_stdin:
            code = sys.stdin.read()
        elif code_tokens:
            # Check if single token is a path to an existing .py file
            if len(code_tokens) == 1 and (code_tokens[0].endswith(".py") or "\n" not in code_tokens[0]):
                candidate_path = pathlib.Path(code_tokens[0])
                if candidate_path.is_file():
                    code = candidate_path.read_text(encoding="utf-8")
                else:
                    code = code_tokens[0]
            else:
                if any("\n" in t for t in code_tokens):
                    code = "\n".join(code_tokens)
                else:
                    code = " ".join(code_tokens)
        elif not sys.stdin.isatty():
            piped = sys.stdin.read()
            if piped.strip():
                code = piped

        code = clean_and_normalize_code(code)

        if not code or not code.strip():
            print("[repro-check] No code provided. Usage: check.py [options] [<code>]")
            return 1

        # AST pre-parse syntax validation before writing to /tmp and executing
        try:
            ast.parse(code)
        except SyntaxError as exc:
            if expect_exception and matches_expected_exception(exc, expect_exception):
                report = DiagnosticReport(
                    status="PASSED",
                    exit_code=0,
                    summary=f"Expected exception '{type(exc).__name__}' was raised as expected: {exc}",
                )
                print(f"[repro-check] ✅ PASSED: {report.summary}")
                return 0

            err_line = exc.text.strip() if exc.text else ""
            if not err_line and exc.lineno and 1 <= exc.lineno <= len(code.splitlines()):
                err_line = code.splitlines()[exc.lineno - 1].strip()
            offset = exc.offset or 1
            caret_line = f"{' ' * max(0, offset - 1)}^"
            summary = f"SYNTAX_ERROR: {exc.msg} at line {exc.lineno}"
            raw_err = f"  File \"<assertion>\", line {exc.lineno}\n    {err_line}\n    {caret_line}\nSyntaxError: {exc.msg}"
            report = DiagnosticReport(
                status="syntax_error",
                exit_code=1,
                summary=summary,
                raw_stderr=raw_err,
            )
            print(
                f"[repro-check] ⚠️ TEST SCRIPT SYNTAX_ERROR:\n"
                f"  {summary}\n"
                f"    {err_line}\n"
                f"    {caret_line}\n"
                f"  SyntaxError: {exc.msg}"
            )
            return 1

        ws = get_workspace_dir()

        # If workspace modified, reset probe count immediately
        if workspace_has_modifications(ws):
            reset_probe_count()

        transformed_code, has_checks, check_count = prepare_executable_code(code)

        # If expecting exception, it is an active check
        if expect_exception:
            has_checks = True

        # Check circuit breaker before running pure probes
        if not has_checks and is_probe_circuit_breaker_active(ws):
            rendered = (
                "[repro-check] ⚠️ PROBE BUDGET REACHED (2/2 probes used): "
                "You have executed 2 exploratory probes without reproducing a defect or failing an assertion. "
                "Stop probing! Formulate your defect hypothesis, locate candidate source lines, and call edit_file immediately."
            )
            output = ReproCheckOutput(
                success=False,
                defect_confirmed=False,
                category="probe_budget_reached",
                report=DiagnosticReport(
                    status="probe_budget_reached",
                    exit_code=1,
                    summary="Probe budget reached",
                ),
                rendered_output=rendered,
            )
            print(output.rendered_output)
            return 1

        exit_code, stdout, stderr, report = execute_script(
            transformed_code, ws, timeout_secs=timeout_secs, expect_exception=expect_exception
        )

        # Handle probe count updates
        if report.status.lower() == "passed":
            if has_checks or expect_exception:
                reset_probe_count()
                category = "passed"
                defect_confirmed = False
                success = True
            else:
                increment_probe_count()
                if is_probe_circuit_breaker_active(ws):
                    category = "probe_budget_reached"
                    defect_confirmed = False
                    success = False
                else:
                    category = "probe_run"
                    defect_confirmed = False
                    success = True
        elif report.status == "missing_exception":
            reset_probe_count()
            category = "missing_exception"
            defect_confirmed = True
            success = False
        elif report.status == "assertion_error":
            reset_probe_count()
            category = "assertion_failure"
            defect_confirmed = True
            success = False
        elif report.status == "runtime_exception":
            reset_probe_count()
            failing_file = report.exception_diagnostic.failing_file if report.exception_diagnostic else ""
            category = "workspace_exception" if is_workspace_path(failing_file, ws) else "runtime_exception"
            defect_confirmed = True
            success = False
        elif report.status == "syntax_error":
            category = "syntax_error"
            defect_confirmed = False
            success = False
        elif report.status == "timeout":
            reset_probe_count()
            category = "timeout"
            defect_confirmed = False
            success = False
        else:
            category = "general_failure"
            defect_confirmed = False
            success = False

        rendered = render_report_output(report, has_checks, ws)

        final_output = ReproCheckOutput(
            success=success,
            defect_confirmed=defect_confirmed,
            category=category,
            report=report,
            rendered_output=rendered,
        )

        print(final_output.rendered_output)
        return 0 if success else 1

    except Exception as e:
        print(f"[repro-check] Runner error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
`````

## File: submission/skills/repro-check/SKILL.md
`````markdown
---
name: repro-check
description: Executes a Python reproduction snippet or test assertion in an isolated process with workspace PYTHONPATH to verify a defect before editing and confirm the fix after editing.
---

# repro-check Skill

Fast, isolated Python verification tool to **reproduce a reported issue** and **confirm your fix**.

## Why Use This?
In SWE-bench and real-world issues, there is **no unit test in the repo for the reported bug yet**.
`blast-radius` only checks regression of existing tests.
`repro-check` directly tests if the **reported defect is confirmed or resolved**.

## How to Run

### 1. Direct Python Snippet (Positional, `--code`, or Multiple Words)
```bash
python3 check.py "assert 1 == 1"
# Multiple unquoted tokens joined automatically:
python3 check.py assert 1 == 1
# Explicit code flag:
python3 check.py --code "from rich.text import Text; assert Text.from_ansi('\\n').plain == '\\n'"
```

### 2. Base64 Mode (`--b64` / `--base64`)
Eliminates JSON escaping and quote conflicts:
```bash
python3 check.py --b64 "YXNzZXJ0IDQgKyA0ID09IDg="
```

### 3. File or Stdin Pipe (`--file`, `repro.py`, stdin)
```bash
python3 check.py /tmp/repro.py
python3 check.py --file /tmp/repro.py
cat /tmp/repro.py | python3 check.py
```

### 4. Missing-Validation Defect Verification (`--expect-exception`, `-e`)
For bugs where invalid input is silently accepted without validation:
```bash
python3 check.py -e ValueError "from mypkg import validate; validate(-1)"
```
- **Baseline reproduction**: If baseline code silently completes without raising the exception, `defect_confirmed=True` (exit 1).
- **Post-fix verification**: When the fix causes the exception to be raised, `status=PASSED` (exit 0).

### 5. Configurable Timeout (`--timeout`, `-t`)
Default timeout is 15s. Infinite loops (`while True: pass`) are killed cleanly via process group signal (`os.killpg`) without hanging:
```bash
python3 check.py -t 5 "while True: pass"
```

## CLI Options & Flags
- `--code, -c <code>`: Code snippet to execute.
- `--b64, --base64 <b64>`: Base64-encoded Python snippet.
- `--file, -f <file>`: Script file path inside `/tmp`.
- `--expect-exception, -e <exc>`: Expected exception class name (e.g. `ValueError`, `KeyError`).
- `--timeout, -t <secs>`: Subprocess timeout in seconds (default: 15s).
- `--stdin, -`: Read script from standard input.
- `--help, -h`: Show usage help (exit 0).

## High-Signal LLM Diagnostics
On `AssertionError`, `repro-check` provides deterministic, structured inspection:
1. **Strings**: Lengths, exact character index of divergence (`Diff at index <i>: actual='...' (hex: 0x...) vs expected='...' (hex: 0x...)`), and decoded ANSI escape breakdown (`\x1b[31m`, CR `\r`, `\t`).
2. **Dicts / JSON**: Missing expected keys, unexpected extra keys, and shared key value differences.
3. **Sequences / Lists**: Length mismatch and first differing element with its index.
4. **Actionable Root Cause Hints**: Concrete `💡 ROOT CAUSE HINT FOR LLM:` explaining *why* the assertion failed and *how* to fix the code.

## Hardening & Guarantees
- **Forgiving Sanitization**: Strips outer markdown fences (```` ```python ... ``` ````), single `'...'`, double `"..."`, triple `'''...'''` / `"""..."""`, and escaped quotes.
- **AST Pre-Parse**: Validates syntax before creating files or running, printing a clean caret pointer without dumping raw Python tracebacks.
- **Crash & Infinite Loop Immunity**: 15s default timeout with process group signal cleanup (`os.killpg`).
- **Strict `/tmp` Containment**: Scratch files remain strictly in `/tmp`, preventing any git pollution.
- **Probe Circuit Breaker**: 2-probe cap on pure exploratory runs without assertions.
`````

## File: submission/skills/test-gate/scripts/gate.py
`````python
#!/usr/bin/env python3
"""test-gate: Consolidated regression test runner, diff inspector, and patch readiness gatekeeper.

Consolidates blast-radius (distance-1 neighbor regression test runner) and diff-inspect
(safe git diff viewer) into a single authoritative gatekeeper skill.

Modes:
  1. Default or blast / --blast / -b:
     - Identifies modified Python files in git working tree.
     - Locates distance-1 neighbor tests (maps source files to test files).
     - Executes pytest on neighbor tests with timeout (default 60s per test file).
     - Reports clear summary: tests run, tests passed, tests failed, and failing traceback snippet.
  2. diff / --diff / -d:
     - Runs safe read-only git diff against HEAD.
     - Verifies NO test files in /workspace were modified. If modified, emits:
       🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE
       explaining that Container B automatically reverts (discards) test-file modifications during evaluation.
       Instructs exact command: git checkout -- <file>.
     - Summarizes lines added, lines removed, files touched.
     - Diff truncation safety: truncates massive diffs (>500 lines or >50KB) with file-by-file summary.
  3. status / --status / -s:
     - Full patch readiness: modified files, test file safety check, syntax check on touched files,
       and recommendation on whether it is safe to run submit_patch.
     - Emits [✓ READY TO SUBMIT] when patch is 100% clean and ready.
  4. Actionable Diagnostics:
     - If no files modified, tells the LLM cleanly what files exist to test.
     - If tests fail, prints the exact failing test names, line numbers, statements, and guidance.
     - If non-existent flags or arguments passed, explains available options with copy-pasteable examples.
  5. --json / -j:
     - Returns 100% Pydantic v2 structured schemas.

Always exits with code 0.
"""

from __future__ import annotations

import ast
from collections import defaultdict
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True

from pydantic import BaseModel, ConfigDict, Field

ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
SKIP_DIRS = {"build", "dist", ".git", "__pycache__", "venv", ".venv", "node_modules", "wheels", ".pytest_cache"}

FORBIDDEN_HARNESS_FILES = {
    "pytest.ini",
    "conftest.py",
    "setup.cfg",
    "tox.ini",
    ".pre-commit-config.yaml",
}

SCRATCH_FILE_PATTERNS = [
    r"^repro.*\.py$",
    r"^.*_repro\.py$",
    r"^reproduce.*\.py$",
    r"^test.*\.py$",
    r"^.*_test\.py$",
    r"^tmp.*\.py$",
    r"^temp.*\.py$",
    r"^scratch.*\.py$",
    r"^run_.*\.py$",
    r"^debug.*\.py$",
    r"^poc.*\.py$",
    r"^solve.*\.py$",
    r"^check.*\.py$",
    r"^verify.*\.py$",
]

MAX_DIFF_LINES = 500
MAX_DIFF_BYTES = 50 * 1024  # 50 KB


def strip_ansi(text: str) -> str:
    """Strip ANSI terminal escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


# ==============================================================================
# Pydantic v2 Data Models
# ==============================================================================

class FailureDetail(BaseModel):
    """Detailed breakdown of an individual test failure."""

    model_config = ConfigDict(extra="ignore")

    test_id: str = Field(..., description="Test node ID, e.g. tests/test_routing.py::test_route")
    test_file: str = Field(default="", description="Path to test file")
    test_name: str = Field(default="", description="Name of test function or method")
    line_number: Optional[int] = Field(default=None, description="Line number of failure")
    error_type: str = Field(default="AssertionError", description="Exception type")
    error_message: str = Field(default="", description="Raw error message")
    failing_statement: str = Field(default="", description="Failing code statement")
    expected: Optional[str] = Field(default=None, description="Expected value")
    actual: Optional[str] = Field(default=None, description="Actual value")
    traceback_snippet: str = Field(default="", description="Cleaned traceback snippet")
    remediation_hint: str = Field(default="", description="Actionable hint for remediation")


class SyntaxErrorDetail(BaseModel):
    """Details of a Python syntax or compilation error."""

    model_config = ConfigDict(extra="ignore")

    file_path: str = Field(..., description="File with syntax error")
    line_number: int = Field(default=1, description="Line number")
    column: int = Field(default=1, description="Column number")
    error_type: str = Field(default="SyntaxError", description="SyntaxError or IndentationError")
    message: str = Field(..., description="Error message from parser")
    snippet: str = Field(default="", description="Code snippet with caret pointer")


class FileChangeStat(BaseModel):
    """File-level git change statistics and safety classifications."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Relative file path")
    status: str = Field(default="M", description="Git status code (M, A, D, R, ??)")
    additions: int = Field(default=0, ge=0, description="Lines added")
    deletions: int = Field(default=0, ge=0, description="Lines deleted")
    binary: bool = Field(default=False, description="Whether file is binary")
    is_test_file: bool = Field(default=False, description="Whether file is part of the test suite")
    is_forbidden: bool = Field(default=False, description="Whether file is a forbidden test/harness file")
    is_scratch_file: bool = Field(default=False, description="Whether file is an untracked scratch file")


class TestGateResult(BaseModel):
    """Authoritative result schema for test-gate CLI."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(..., description="Execution mode: blast, diff, status")
    workspace: str = Field(..., description="Resolved workspace root directory")
    success: bool = Field(default=True, description="True if check/run passed cleanly")
    status: str = Field(default="PASSED", description="High-level status code")
    modified_files: List[str] = Field(default_factory=list, description="Modified source files detected")
    untracked_files: List[str] = Field(default_factory=list, description="Untracked files detected")
    test_files_checked: List[str] = Field(default_factory=list, description="Test files executed or identified")
    tests_run: int = Field(default=0, ge=0, description="Count of tests executed")
    tests_passed: int = Field(default=0, ge=0, description="Count of tests passed")
    tests_failed: int = Field(default=0, ge=0, description="Count of tests failed")
    tests_errors: int = Field(default=0, ge=0, description="Count of test errors")
    failures: List[FailureDetail] = Field(default_factory=list, description="Detailed test failure breakdowns")
    file_stats: List[FileChangeStat] = Field(default_factory=list, description="File-by-file diff stats")
    total_files_modified: int = Field(default=0, ge=0, description="Total files touched")
    total_additions: int = Field(default=0, ge=0, description="Total lines added")
    total_deletions: int = Field(default=0, ge=0, description="Total lines deleted")
    forbidden_test_files: List[str] = Field(default_factory=list, description="Modified test files (forbidden in SWE-bench)")
    dangerous_scratch_files: List[str] = Field(default_factory=list, description="Untracked scratch files in /workspace")
    syntax_errors: List[SyntaxErrorDetail] = Field(default_factory=list, description="Syntax errors in touched files")
    can_submit_patch: bool = Field(default=False, description="True if patch is ready and safe for submit_patch")
    summary: str = Field(default="", description="Concise human-readable summary")
    recommendation: str = Field(default="", description="Explicit actionable recommendation")
    diff_preview: str = Field(default="", description="Unified diff preview (capped at 500 lines / 50KB)")


FailureDetail.model_rebuild()
SyntaxErrorDetail.model_rebuild()
FileChangeStat.model_rebuild()
TestGateResult.model_rebuild()


# ==============================================================================
# Helper Functions: Workspace & Classifications
# ==============================================================================

def get_workspace_dir(explicit_ws: Optional[str] = None) -> pathlib.Path:
    """Robustly and deterministically locate the target repository workspace directory."""
    if explicit_ws:
        p = pathlib.Path(explicit_ws)
        if p.is_dir():
            return p.resolve()

    # 1. Check caller stack frame for _orig_cwd (set by ADK harness)
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals and f.f_locals["_orig_cwd"]:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / ".git").exists()
                    or (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                    or (p / "setup.cfg").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    # 2. Environment variable overrides
    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    # 3. Search upward from current working directory for repository markers
    cur = pathlib.Path.cwd().resolve()
    for parent in [cur] + list(cur.parents):
        if (
            (parent / ".git").exists()
            or (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
            or (parent / "setup.cfg").exists()
        ):
            return parent

    # 4. Standard container workspace fallback
    ws_fixed = pathlib.Path("/workspace")
    if ws_fixed.is_dir():
        return ws_fixed.resolve()

    return cur


def is_git_repo(ws: pathlib.Path) -> bool:
    """Check if directory is inside a valid git working tree."""
    code, _ = run_git_cmd(["rev-parse", "--is-inside-work-tree"], cwd=ws, timeout_secs=5)
    return code == 0


def is_test_file(path_str: str) -> bool:
    """Check if file is part of the test suite."""
    p = pathlib.Path(path_str)
    name = p.name.lower()
    parts_lower = [part.lower() for part in p.parts]

    if any(part in ("tests", "test", "testing") for part in parts_lower):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if name in ("conftest.py", "pytest.ini"):
        return True
    return False


def is_forbidden_harness_file(path_str: str) -> bool:
    """Check if file is a forbidden harness configuration or test configuration."""
    p = pathlib.Path(path_str)
    name = p.name.lower()
    if name in FORBIDDEN_HARNESS_FILES:
        return True
    if is_test_file(path_str):
        return True
    return False


def is_scratch_file(path_str: str) -> bool:
    """Check if file matches temporary, reproduction, or scratch script patterns."""
    p = pathlib.Path(path_str)
    name = p.name.lower()

    if ".adk_exec" in name or name.startswith(".adk_exec"):
        return False
    if name.endswith((".tmp", ".temp", ".log", ".bak", ".swp", "~")):
        return True

    for pat in SCRATCH_FILE_PATTERNS:
        if re.match(pat, name):
            return True

    if len(p.parts) == 1 and name.endswith(".py"):
        # Root-level python scripts not matching standard project files
        if name not in ("setup.py", "conftest.py", "__init__.py"):
            return True

    parts_lower = [part.lower() for part in p.parts]
    if any(part in ("tmp", "temp", "scratch") for part in parts_lower):
        return True

    return False


def run_git_cmd(args: List[str], cwd: pathlib.Path, timeout_secs: int = 15) -> Tuple[int, str]:
    """Execute a git command safely in cwd without raising unhandled exceptions."""
    git_bin = shutil.which("git") or "git"
    try:
        res = subprocess.run(
            [git_bin] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_secs,
        )
        out = res.stdout if res.stdout else res.stderr
        return res.returncode, out.rstrip()
    except subprocess.TimeoutExpired:
        return 1, f"Git command timed out after {timeout_secs}s: git {' '.join(args)}"
    except Exception as e:
        return 1, f"Git command error: {e}"


def get_git_status_and_files(ws: pathlib.Path) -> Tuple[List[str], List[str], Dict[str, str]]:
    """Query git status to return (modified_files, untracked_files, status_map)."""
    if not is_git_repo(ws):
        return [], [], {}

    code, out = run_git_cmd(
        ["status", "--porcelain", "-uall", "--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"],
        cwd=ws,
        timeout_secs=10,
    )
    if code != 0:
        code, out = run_git_cmd(["status", "--porcelain"], cwd=ws, timeout_secs=10)

    modified_files: List[str] = []
    untracked_files: List[str] = []
    status_map: Dict[str, str] = {}

    if code == 0 and out:
        for raw_line in out.splitlines():
            line = raw_line.rstrip()
            if not line:
                continue
            parts = line.strip().split(maxsplit=1)
            if len(parts) < 2:
                continue
            code_str = parts[0]
            rel_path = parts[1].strip('"')
            if " -> " in rel_path:
                rel_path = rel_path.split(" -> ")[-1].strip().strip('"')

            if ".adk_exec" in rel_path or pathlib.Path(rel_path).name.startswith(".adk_exec"):
                continue

            if code_str == "??":
                untracked_files.append(rel_path)
            else:
                status_map[rel_path] = code_str or "M"
                if "D" not in code_str:
                    modified_files.append(rel_path)

    return modified_files, untracked_files, status_map


# ==============================================================================
# Syntax Verification
# ==============================================================================

def generate_syntax_snippet(source_lines: List[str], lineno: int, column: int) -> str:
    """Generate code snippet with visual caret pointer at line and column."""
    if not source_lines:
        return ""
    target_idx = max(0, min(len(source_lines) - 1, lineno - 1))
    start_idx = max(0, target_idx - 1)
    end_idx = min(len(source_lines), target_idx + 2)

    width = max(len(str(end_idx)), 2)
    out: List[str] = []
    for idx in range(start_idx, end_idx):
        line_num = idx + 1
        num_str = str(line_num).rjust(width)
        line_content = source_lines[idx].rstrip("\r\n")
        if idx == target_idx:
            out.append(f"> {num_str} | {line_content.expandtabs(4)}")
            prefix = line_content[: max(0, column - 1)].expandtabs(4)
            out.append(f"  {' ' * width} | {' ' * len(prefix)}^")
        else:
            out.append(f"  {num_str} | {line_content.expandtabs(4)}")
    return "\n".join(out)


def verify_python_syntax(file_path: pathlib.Path) -> Optional[SyntaxErrorDetail]:
    """Parse a Python file using AST and return a SyntaxErrorDetail if invalid."""
    if not file_path.exists() or not file_path.is_file():
        return None
    try:
        raw_bytes = file_path.read_bytes()
    except Exception as e:
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=1,
            column=1,
            error_type="FileReadError",
            message=f"Could not read file: {e}",
            snippet="> 1 | (unreadable file)",
        )

    # Detect binary files containing null bytes
    if b"\x00" in raw_bytes[:4096]:
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=1,
            column=1,
            error_type="BinaryFileError",
            message="File contains binary or null bytes; cannot parse as Python source.",
            snippet="> 1 | (binary file)",
        )

    try:
        source_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        source_text = raw_bytes.decode("latin-1", errors="replace")

    source_lines = source_text.splitlines()

    try:
        ast.parse(raw_bytes, filename=str(file_path))
    except SyntaxError as e:
        lineno = e.lineno or 1
        col = e.offset or 1
        error_type = type(e).__name__
        msg = e.msg or "syntax error"
        snippet = generate_syntax_snippet(source_lines, lineno, col)
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=lineno,
            column=col,
            error_type=error_type,
            message=msg,
            snippet=snippet,
        )
    except Exception as e:
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=1,
            column=1,
            error_type=type(e).__name__,
            message=str(e),
            snippet="> 1 | (parse error)",
        )

    return None


# ==============================================================================
# Neighbor Test Resolution & Blast Radius Discovery
# ==============================================================================

def resolve_docs_src_test_path(path_str: str) -> Optional[str]:
    """Framework-aware path mapping for FastAPI doc tutorials.

    Maps docs_src/<category>/tutorial<N>[_<variant>].py to
    tests/test_tutorial/test_<category>/test_tutorial<N>.py (stripping _py310, _py39, etc.).
    """
    clean_p = path_str.replace("\\", "/").strip().lstrip("/")
    parts = clean_p.split("/")
    if "docs_src" not in parts:
        return None
    idx = parts.index("docs_src")
    subparts = parts[idx + 1:]
    if len(subparts) < 2:
        return None

    category_parts = subparts[:-1]
    filename = subparts[-1]
    stem = filename[:-3] if filename.endswith(".py") else filename

    m = re.match(r"^(tutorial\d+[a-z]?)(?:_.*)?$", stem)
    base_stem = m.group(1) if m else re.sub(r"(_(?:an|py3\d+|py\d+|pv\d+|non_annotated|annotated))+$", "", stem)

    category = "_".join(category_parts)
    clean_category = category[5:] if category.startswith("test_") else category
    return f"tests/test_tutorial/test_{clean_category}/test_{base_stem}.py"


def extract_ast_symbols(file_path: pathlib.Path) -> Set[str]:
    """Extract top-level class and function names from a Python source file."""
    symbols: Set[str] = set()
    if not file_path.exists() or file_path.suffix != ".py":
        return symbols
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(file_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.add(node.name)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not item.name.startswith("__"):
                            symbols.add(item.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("__"):
                    symbols.add(node.name)
    except Exception:
        pass
    return {s for s in symbols if len(s) > 1}


def find_neighbor_tests_for_target(target_path: pathlib.Path, ws: pathlib.Path) -> List[str]:
    """Locate distance-1 neighbor tests for a source target file."""
    try:
        rel_target = target_path.relative_to(ws)
    except ValueError:
        rel_target = target_path

    rel_posix = rel_target.as_posix()
    stem = target_path.stem

    # If target is already a test file, return it directly
    if is_test_file(rel_posix):
        return [rel_posix]

    direct_tests: List[str] = []

    # 1. Framework-aware mapping (e.g. FastAPI docs tutorials)
    docs_cand = resolve_docs_src_test_path(rel_posix)
    if docs_cand:
        cp = ws / docs_cand
        if cp.exists():
            direct_tests.append(cp.relative_to(ws).as_posix())

    # 2. Canonical neighbor candidates
    target_mod_parts = list(rel_target.parts)
    if target_mod_parts and target_mod_parts[-1].endswith(".py"):
        target_mod_parts[-1] = target_mod_parts[-1][:-3]
    full_mod_name = "_".join(target_mod_parts)

    candidates = [
        f"tests/test_{stem}.py",
        f"test/test_{stem}.py",
        f"tests/{stem}_test.py",
        f"test_{stem}.py",
        f"tests/test_{full_mod_name}.py",
    ]
    if len(rel_target.parts) > 1:
        candidates.append(f"tests/{'/'.join(rel_target.parts[:-1])}/test_{stem}.py")

    for cand in candidates:
        cp = ws / cand
        if cp.exists():
            rel_cand = cp.relative_to(ws).as_posix()
            if rel_cand not in direct_tests:
                direct_tests.append(rel_cand)

    # 3. Search repo for test_<stem>.py if not yet resolved
    if not direct_tests:
        try:
            for match in ws.rglob(f"test_{stem}.py"):
                if not any(part in SKIP_DIRS for part in match.parts):
                    direct_tests.append(match.relative_to(ws).as_posix())
                    break
        except Exception:
            pass

    # 4. Symbol-level test scan
    symbols = extract_ast_symbols(target_path)
    if symbols and len(direct_tests) < 4:
        cand_test_files: List[pathlib.Path] = []
        try:
            for p in ws.rglob("*.py"):
                if any(part in SKIP_DIRS for part in p.parts):
                    continue
                if is_test_file(str(p.relative_to(ws))):
                    cand_test_files.append(p)
        except Exception:
            pass

        for tf in cand_test_files:
            rel_tf = tf.relative_to(ws).as_posix()
            if rel_tf in direct_tests:
                continue
            try:
                txt = tf.read_text(encoding="utf-8", errors="replace")
                if any(sym in txt for sym in symbols):
                    direct_tests.append(rel_tf)
                    if len(direct_tests) >= 5:
                        break
            except Exception:
                continue

    # 5. Distance-1 consumer test resolution
    consumer_tests: List[str] = []
    mod_name_dot = ".".join(target_mod_parts)
    try:
        for p in ws.rglob("*.py"):
            if any(part in SKIP_DIRS for part in p.parts) or p == target_path:
                continue
            rel_p = p.relative_to(ws).as_posix()
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                if stem not in content and mod_name_dot not in content:
                    continue
            except Exception:
                continue

            if is_test_file(rel_p):
                if rel_p not in direct_tests and rel_p not in consumer_tests:
                    consumer_tests.append(rel_p)
            else:
                c_stem = p.stem
                for c_cand in (f"tests/test_{c_stem}.py", f"test/test_{c_stem}.py", f"tests/{c_stem}_test.py"):
                    cp = ws / c_cand
                    if cp.exists():
                        rel_cp = cp.relative_to(ws).as_posix()
                        if rel_cp not in direct_tests and rel_cp not in consumer_tests:
                            consumer_tests.append(rel_cp)
    except Exception:
        pass

    all_tests = direct_tests + consumer_tests
    # Deduplicate and cap to 8 files for fast execution
    seen: Set[str] = set()
    deduped: List[str] = []
    for t in all_tests:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped[:8]


# ==============================================================================
# Pytest Runner & Output Parser
# ==============================================================================

def find_pytest_command(ws: pathlib.Path) -> List[str]:
    """Find the most appropriate pytest runner executable."""
    # 1. Active virtualenv or interpreter directory
    for base in (pathlib.Path(sys.executable).parent, pathlib.Path(sys.prefix) / "bin"):
        cand = base / "pytest"
        if cand.is_file() and os.access(cand, os.X_OK):
            return [str(cand)]

    # 2. VIRTUAL_ENV env var
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        v_cand = pathlib.Path(venv) / "bin" / "pytest"
        if v_cand.is_file() and os.access(v_cand, os.X_OK):
            return [str(v_cand)]

    # 3. Workspace venvs
    for vname in (".venv", "venv"):
        v_cand = ws / vname / "bin" / "pytest"
        if v_cand.is_file() and os.access(v_cand, os.X_OK):
            return [str(v_cand)]

    # 4. Standard container paths
    for vpath in ("/venv", "/opt/venv", "/root/.venv"):
        v_cand = pathlib.Path(vpath) / "bin" / "pytest"
        if v_cand.is_file() and os.access(v_cand, os.X_OK):
            return [str(v_cand)]

    # 5. Check if active interpreter has pytest
    try:
        if importlib.util.find_spec("pytest") is not None:
            return [sys.executable, "-m", "pytest"]
    except Exception:
        pass

    # 6. Fallback PATH
    pytest_bin = shutil.which("pytest")
    if pytest_bin:
        return [pytest_bin]

    return [sys.executable or "python3", "-m", "pytest"]


def run_pytest_suite(test_files: List[str], ws: pathlib.Path, timeout_secs: int = 60) -> Tuple[int, str]:
    """Run pytest on the given test files with workspace in PYTHONPATH and timeout protection."""
    cmd_base = find_pytest_command(ws)
    cmd = cmd_base + ["-vv", "--tb=short", "--disable-warnings"] + test_files

    env = os.environ.copy()
    pp_parts: List[str] = [str(ws)]
    if "/workspace" not in pp_parts:
        pp_parts.append("/workspace")
    existing_pp = env.get("PYTHONPATH", "")
    if existing_pp:
        for p in existing_pp.split(":"):
            if p and p not in pp_parts:
                pp_parts.append(p)
    env["PYTHONPATH"] = ":".join(pp_parts)

    try:
        res = subprocess.run(
            cmd,
            cwd=ws,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_secs,
        )
        return res.returncode, (res.stdout + "\n" + res.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"[test-gate] Pytest timed out after {timeout_secs}s on: {', '.join(test_files)}"
    except Exception as e:
        return 1, f"[test-gate] Pytest error: {e}"


def parse_pytest_results(
    raw_output: str,
    ws: pathlib.Path,
    test_files: Optional[List[str]] = None,
    timeout_secs: Optional[int] = None,
) -> Tuple[int, int, int, List[FailureDetail]]:
    """Parse pytest summary and detailed failures from output."""
    clean_out = strip_ansi(raw_output)
    lines = clean_out.splitlines()

    total_passed = 0
    total_failed = 0
    total_errors = 0

    for line in reversed(lines):
        s = line.strip("= ").strip().lower()
        if "passed" in s or "failed" in s or "error" in s:
            pm = re.search(r"(\d+)\s+passed", s)
            if pm:
                total_passed = int(pm.group(1))
            fm = re.search(r"(\d+)\s+failed", s)
            if fm:
                total_failed = int(fm.group(1))
            em = re.search(r"(\d+)\s+error", s)
            if em:
                total_errors = int(em.group(1))
            break

    # Check for timeout condition
    if "timed out after" in clean_out.lower():
        total_failed = max(1, total_failed)
        return (
            total_passed,
            total_failed,
            total_errors,
            [
                FailureDetail(
                    test_id=f"timeout::{test_files[0] if test_files else 'neighbor_tests'}",
                    test_file=test_files[0] if test_files else "",
                    test_name="pytest_timeout",
                    line_number=None,
                    error_type="TimeoutExpired",
                    error_message=clean_out.strip().splitlines()[-1] if clean_out.strip() else "Pytest timed out",
                    failing_statement=f"Execution timed out after {timeout_secs or 60}s",
                    expected="Tests to complete within timeout limit",
                    actual=f"Timed out after {timeout_secs or 60}s",
                    traceback_snippet=clean_out.strip()[:600],
                    remediation_hint=f"Pytest execution timed out after {timeout_secs or 60}s. Check for infinite loops, deadlocks, or slow fixtures. Increase timeout with -t <secs> or --timeout <secs>.",
                )
            ],
        )

    # Parse failure blocks
    header_re = re.compile(r"^_{3,}\s+(.*?)\s+_{3,}$")
    loc_re = re.compile(r"^(.*?):(\d+):\s+in\s+(\S+)")
    assert_eq_re = re.compile(r"(?:AssertionError:\s+)?assert\s+(.+?)\s+==\s+(.+)$")
    err_re = re.compile(r"^E\s+([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception):\s*(.*)$")

    blocks: List[Tuple[str, List[str]]] = []
    current_header: Optional[str] = None
    current_lines: List[str] = []

    for line in lines:
        clean = line.strip()
        m = header_re.match(clean)
        if m:
            if current_header and current_lines:
                blocks.append((current_header, current_lines))
            current_header = m.group(1).strip()
            current_lines = []
        elif current_header is not None:
            if clean.startswith("=") and ("short test summary info" in clean or "failed" in clean or "passed" in clean):
                blocks.append((current_header, current_lines))
                current_header = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_header and current_lines:
        blocks.append((current_header, current_lines))

    failures: List[FailureDetail] = []
    for header, blines in blocks:
        test_file = ""
        line_no = None
        func_name = header
        error_type = "AssertionError"
        error_msg = ""
        failing_stmt = ""
        expected = None
        actual = None
        snippet_lines: List[str] = []

        for bline in blines:
            sline = bline.strip()
            lm = loc_re.match(sline)
            if lm:
                test_file = lm.group(1)
                line_no = int(lm.group(2))
                func_name = lm.group(3)
                continue

            if sline.startswith("E   ") or sline.startswith("E "):
                e_content = sline[2:].strip()
                snippet_lines.append(sline)
                em = err_re.match(sline)
                if em:
                    error_type = em.group(1)
                    error_msg = em.group(2).strip()
                elif "assert " in sline and not error_msg:
                    error_type = "AssertionError"
                    error_msg = e_content

                am = assert_eq_re.search(e_content)
                if am:
                    actual = am.group(1).strip()
                    expected = am.group(2).strip()
            elif sline.startswith("assert ") and not failing_stmt:
                failing_stmt = sline
                snippet_lines.append(sline)

        # Build clean test id
        test_id = f"{test_file}::{func_name}" if test_file else func_name
        tb_snippet = "\n".join(snippet_lines[:8]) if snippet_lines else "\n".join(blines[:6])

        hint = f"Fix implementation in source code causing `{failing_stmt or error_msg or 'failure'}`."
        if expected and actual:
            hint = f"Expected `{expected}` but produced `{actual}`. Align return values or edge case handling."

        failures.append(
            FailureDetail(
                test_id=test_id,
                test_file=test_file,
                test_name=func_name,
                line_number=line_no,
                error_type=error_type,
                error_message=error_msg,
                failing_statement=failing_stmt,
                expected=expected,
                actual=actual,
                traceback_snippet=tb_snippet,
                remediation_hint=hint,
            )
        )

    # Fallback if pytest failed without standard block headers (e.g. collection error)
    if total_failed == 0 and total_errors > 0 and not failures:
        err_lines = [l for l in lines if l.startswith("E   ") or "error" in l.lower()]
        failures.append(
            FailureDetail(
                test_id=test_files[0] if test_files else "pytest_suite",
                test_file=test_files[0] if test_files else "",
                test_name="pytest_error",
                error_type="PytestError",
                error_message=err_lines[0].strip() if err_lines else "Pytest error occurred during suite execution",
                traceback_snippet="\n".join(err_lines[:8]) if err_lines else clean_out[:400],
                remediation_hint="Inspect pytest error output and fix syntax or import errors.",
            )
        )

    return total_passed, total_failed, total_errors, failures


# ==============================================================================
# Mode Handlers: blast, diff, status
# ==============================================================================

def execute_blast(
    ws: pathlib.Path,
    target_args: List[str],
    timeout_per_file: int = 60,
) -> TestGateResult:
    """Execute Mode 1: Distance-1 Neighbor Regression Test Runner."""
    if not is_git_repo(ws) and not target_args:
        return TestGateResult(
            mode="blast",
            workspace=str(ws),
            success=False,
            status="NOT_A_GIT_REPOSITORY",
            summary=f"Workspace '{ws}' is not a git repository.",
            recommendation="Initialize git or specify a valid repository path with --workspace <dir>.",
        )

    modified_files, untracked, _ = get_git_status_and_files(ws)

    # Check for forbidden test files in /workspace
    forbidden_modified: List[str] = [f for f in modified_files if is_forbidden_harness_file(f)]
    for u in untracked:
        if is_test_file(u):
            forbidden_modified.append(u)

    # Determine targets: explicit target args or git modified files
    targets: List[pathlib.Path] = []
    if target_args:
        for targ in target_args:
            p = ws / targ if not pathlib.Path(targ).is_absolute() else pathlib.Path(targ)
            if p.exists():
                targets.append(p)
            else:
                # Try finding across repo
                cands = list(ws.rglob(pathlib.Path(targ).name))
                if cands:
                    targets.append(cands[0])
                else:
                    targets.append(p)
    else:
        for m in modified_files:
            if m.endswith(".py"):
                p = ws / m
                if p.exists():
                    targets.append(p)

    # Actionable diagnostics if no files modified or targets specified
    if not targets:
        sample_files: List[str] = []
        try:
            for py_f in ws.rglob("*.py"):
                if any(part in SKIP_DIRS for part in py_f.parts):
                    continue
                rel = py_f.relative_to(ws).as_posix()
                if not is_test_file(rel):
                    sample_files.append(rel)
                    if len(sample_files) >= 6:
                        break
        except Exception:
            pass

        msg = (
            "No modified files detected in git working tree and no target specified.\n"
            f"Available source modules to test:\n"
            + "\n".join(f"  • {f}" for f in sample_files)
            + "\nUsage: python3 gate.py --blast <path/to/file.py>"
        )

        return TestGateResult(
            mode="blast",
            workspace=str(ws),
            success=True,
            status="CLEAN_NO_TARGETS",
            modified_files=[],
            untracked_files=untracked,
            test_files_checked=[],
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_errors=0,
            failures=[],
            forbidden_test_files=forbidden_modified,
            summary="No modified files detected in working tree.",
            recommendation=msg,
        )

    # Resolve neighbor test files for all targets
    test_files: List[str] = []
    for targ in targets:
        neighbors = find_neighbor_tests_for_target(targ, ws)
        for n in neighbors:
            if n not in test_files:
                test_files.append(n)

    target_names = [t.relative_to(ws).as_posix() if ws in t.parents else t.name for t in targets]

    if not test_files:
        summary = f"UNVERIFIED_NO_TESTS: 0 matching neighbor test files found for target(s): {', '.join(target_names)}."
        rec = "VERIFICATION REQUIRED: No tests were run. Write or execute a targeted test before calling submit_patch()."
        return TestGateResult(
            mode="blast",
            workspace=str(ws),
            success=False,
            status="UNVERIFIED_NO_TESTS",
            modified_files=target_names,
            untracked_files=untracked,
            test_files_checked=[],
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_errors=0,
            failures=[],
            forbidden_test_files=forbidden_modified,
            summary=summary,
            recommendation=rec,
        )

    timeout = max(timeout_per_file, len(test_files) * timeout_per_file)
    exit_code, raw_output = run_pytest_suite(test_files, ws, timeout_secs=timeout)
    passed_cnt, failed_cnt, err_cnt, failures = parse_pytest_results(
        raw_output,
        ws,
        test_files=test_files,
        timeout_secs=timeout,
    )

    total_run = passed_cnt + failed_cnt + err_cnt
    if total_run == 0 and exit_code != 0:
        failed_cnt = max(1, len(failures) or 1)
        total_run = failed_cnt

    has_forbidden = len(forbidden_modified) > 0
    success = (exit_code == 0 and failed_cnt == 0 and err_cnt == 0 and not has_forbidden)
    status_str = "PASSED" if success else ("BLOCKED_FORBIDDEN_TEST_FILE" if has_forbidden else "FAILED")

    if success:
        summary = f"PASSED: {passed_cnt} test(s) passed across neighbor test suite ({', '.join(test_files)})."
        rec = "Regression gate clean. Changes pass distance-1 neighbor tests."
    else:
        failing_names = [f.test_id for f in failures]
        f_list = ", ".join(failing_names[:5])
        summary = f"FAILED: {failed_cnt} test(s) failed ({f_list}) across {len(test_files)} neighbor test file(s)."
        rec = (
            f"Exact failing tests:\n"
            + "\n".join(f"  ✗ {t}" for t in failing_names)
            + "\nGuidance: Fix the logic causing test failures in your modified files before calling submit_patch(). Inspect the failing statements and expected vs actual values above, then re-run python3 gate.py."
        )

    return TestGateResult(
        mode="blast",
        workspace=str(ws),
        success=success,
        status=status_str,
        modified_files=target_names,
        untracked_files=untracked,
        test_files_checked=test_files,
        tests_run=total_run,
        tests_passed=passed_cnt,
        tests_failed=failed_cnt,
        tests_errors=err_cnt,
        failures=failures,
        forbidden_test_files=forbidden_modified,
        summary=summary,
        recommendation=rec,
    )


def execute_diff(ws: pathlib.Path, extra_args: Optional[List[str]] = None) -> TestGateResult:
    """Execute Mode 2: Safe Git Diff Viewer & Safety Assertion Gate with Diff Truncation."""
    if not is_git_repo(ws):
        return TestGateResult(
            mode="diff",
            workspace=str(ws),
            success=False,
            status="NOT_A_GIT_REPOSITORY",
            summary=f"Workspace '{ws}' is not a git repository.",
            recommendation="Initialize git or specify a valid repository path with --workspace <dir>.",
        )

    modified_files, untracked, status_map = get_git_status_and_files(ws)

    # 1. Parse git diff --numstat HEAD
    numstat_cmd = ["diff", "--numstat", "HEAD", "--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"]
    code, numstat_out = run_git_cmd(numstat_cmd, cwd=ws, timeout_secs=10)
    if code != 0:
        code, numstat_out = run_git_cmd(["diff", "--numstat"], cwd=ws, timeout_secs=10)

    file_stats: List[FileChangeStat] = []
    forbidden_modified: List[str] = []
    dangerous_scratch: List[str] = []
    total_adds = 0
    total_dels = 0

    if code == 0 and numstat_out:
        for line in numstat_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                add_str, del_str, raw_p = parts[0], parts[1], parts[2]
                is_bin = (add_str == "-" and del_str == "-")
                adds = int(add_str) if not is_bin and add_str.isdigit() else 0
                dels = int(del_str) if not is_bin and del_str.isdigit() else 0

                clean_p = raw_p
                if " => " in clean_p:
                    clean_p = clean_p.split(" => ")[-1].strip()

                if ".adk_exec" in clean_p:
                    continue

                total_adds += adds
                total_dels += dels

                is_test = is_test_file(clean_p)
                is_forbid = is_forbidden_harness_file(clean_p)
                is_scratch = is_scratch_file(clean_p)

                if is_forbid or is_test:
                    forbidden_modified.append(clean_p)

                file_stats.append(
                    FileChangeStat(
                        path=clean_p,
                        status=status_map.get(clean_p, "M"),
                        additions=adds,
                        deletions=dels,
                        binary=is_bin,
                        is_test_file=is_test,
                        is_forbidden=is_forbid,
                        is_scratch_file=is_scratch,
                    )
                )

    # Check untracked files for scratch files and test files
    for u in untracked:
        if is_scratch_file(u):
            dangerous_scratch.append(u)
        if is_test_file(u):
            forbidden_modified.append(u)

    # 2. Get unified diff preview capped at MAX_DIFF_LINES / MAX_DIFF_BYTES
    diff_cmd = ["diff", "HEAD", "--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"]
    if extra_args:
        diff_cmd = ["diff", "HEAD"] + extra_args + ["--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"]
    code, diff_out = run_git_cmd(diff_cmd, cwd=ws, timeout_secs=15)
    if code != 0:
        code, diff_out = run_git_cmd(["diff"], cwd=ws, timeout_secs=15)

    diff_lines = diff_out.splitlines() if diff_out else []
    total_diff_lines = len(diff_lines)
    truncated_lines: List[str] = []
    accumulated_bytes = 0
    is_truncated = False

    for idx, line in enumerate(diff_lines):
        line_bytes = len(line.encode("utf-8", errors="replace")) + 1
        if idx >= MAX_DIFF_LINES or (accumulated_bytes + line_bytes > MAX_DIFF_BYTES and idx >= 20):
            is_truncated = True
            break
        truncated_lines.append(line)
        accumulated_bytes += line_bytes

    total_files = len(file_stats)

    if is_truncated:
        omitted_lines = total_diff_lines - len(truncated_lines)
        preview = "\n".join(truncated_lines)
        preview += (
            f"\n\n... [DIFF TRUNCATED: {omitted_lines} lines omitted to prevent LLM context blowout; "
            f"capped at {len(truncated_lines)} lines / {accumulated_bytes // 1024}KB] ...\n\n"
            f"File-by-file summary of changes:\n"
        )
        for stat in file_stats:
            tag = " [FORBIDDEN TEST]" if stat.is_forbidden else ""
            preview += f"  • {stat.path}: +{stat.additions}, -{stat.deletions} [{stat.status}]{tag}\n"
        preview += f"Total changes: {total_files} file(s) touched (+{total_adds} additions, -{total_dels} deletions)"
    else:
        preview = "\n".join(diff_lines)

    is_clean = (total_files == 0 and not diff_out)

    # Safety Assertions
    has_forbidden = len(forbidden_modified) > 0
    has_scratch = len(dangerous_scratch) > 0

    if has_forbidden:
        status_str = "BLOCKED_FORBIDDEN_TEST_FILE"
        success = False
        summary = (
            f"🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE ({', '.join(forbidden_modified)})\n"
            f"Container B automatically reverts (discards) test-file modifications during evaluation.\n"
            f"Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files."
        )
        rec = (
            "To revert forbidden test file modifications, run:\n"
            + "\n".join(f"  git checkout -- {f}" for f in forbidden_modified)
        )
    elif is_clean:
        status_str = "CLEAN"
        success = True
        summary = "Working tree is clean. 0 files modified relative to HEAD."
        rec = "No changes to inspect. Implement fix in source files before calling submit_patch()."
    else:
        status_str = "MODIFIED"
        success = True
        summary = f"{total_files} file(s) touched: +{total_adds} additions, -{total_dels} deletions."
        if has_scratch:
            rec = (
                f"⚠️ DANGER: Untracked scratch files in /workspace ({', '.join(dangerous_scratch)}). "
                f"Remove them or move them to /tmp before submitting!"
            )
        else:
            rec = "Diff inspection clean of forbidden test files."

    return TestGateResult(
        mode="diff",
        workspace=str(ws),
        success=success,
        status=status_str,
        modified_files=[f.path for f in file_stats],
        untracked_files=untracked,
        file_stats=file_stats,
        total_files_modified=total_files,
        total_additions=total_adds,
        total_deletions=total_dels,
        forbidden_test_files=forbidden_modified,
        dangerous_scratch_files=dangerous_scratch,
        can_submit_patch=(not has_forbidden and not has_scratch and not is_clean),
        summary=summary,
        recommendation=rec,
        diff_preview=preview or "(no diff)",
    )


def execute_status(ws: pathlib.Path) -> TestGateResult:
    """Execute Mode 3: Full Patch Readiness & Pre-Submission Gate."""
    if not is_git_repo(ws):
        return TestGateResult(
            mode="status",
            workspace=str(ws),
            success=False,
            status="NOT_A_GIT_REPOSITORY",
            summary=f"Workspace '{ws}' is not a git repository.",
            recommendation="Initialize git or specify a valid repository path with --workspace <dir>.",
        )

    diff_res = execute_diff(ws)

    # Collect Python files touched for syntax verification
    modified_py = [f for f in diff_res.modified_files if f.endswith(".py")]
    syntax_errors: List[SyntaxErrorDetail] = []
    for rel_py in modified_py:
        err = verify_python_syntax(ws / rel_py)
        if err:
            syntax_errors.append(err)

    has_forbidden = len(diff_res.forbidden_test_files) > 0
    has_scratch = len(diff_res.dangerous_scratch_files) > 0
    has_syntax_err = len(syntax_errors) > 0
    is_clean = (diff_res.total_files_modified == 0)

    # Determine readiness and final recommendation
    can_submit = False
    if is_clean:
        status_str = "BLOCKED_EMPTY_DIFF"
        summary = "BLOCKED: Working tree is clean (0 files modified relative to HEAD)."
        rec = "Calling submit_patch() now will result in an empty patch failure. Edit source files first."
    elif has_forbidden:
        status_str = "BLOCKED_FORBIDDEN_TEST_FILE"
        summary = (
            f"🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE: {', '.join(diff_res.forbidden_test_files)}\n"
            f"Container B automatically reverts (discards) test-file modifications during evaluation."
        )
        rec = (
            "Revert forbidden test modifications before submitting:\n"
            + "\n".join(f"  git checkout -- {f}" for f in diff_res.forbidden_test_files)
        )
    elif has_syntax_err:
        status_str = "BLOCKED_SYNTAX_ERROR"
        err_files = [e.file_path for e in syntax_errors]
        summary = f"BLOCKED: Syntax error(s) detected in touched file(s): {', '.join(err_files)}."
        rec = (
            "Fix syntax errors before submitting:\n"
            + "\n".join(f"  • {e.file_path}:{e.line_number} [{e.error_type}]: {e.message}" for e in syntax_errors)
        )
    elif has_scratch:
        status_str = "BLOCKED_DANGEROUS_SCRATCH"
        summary = f"BLOCKED: Dangerous untracked scratch files in /workspace ({', '.join(diff_res.dangerous_scratch_files)})."
        rec = "Delete scratch files or move to /tmp. 'git add -N .' will pollute the official patch."
    else:
        status_str = "READY"
        can_submit = True
        summary = (
            f"READY: Patch is clean and safe to submit! {diff_res.total_files_modified} file(s) touched "
            f"(+{diff_res.total_additions}, -{diff_res.total_deletions})."
        )
        multi_file_note = (
            "\nNote: Over 90% of SWE-bench tasks only require modifying 1 file."
            if diff_res.total_files_modified > 1
            else ""
        )
        rec = f"Patch is verified and [✓ READY TO SUBMIT]. Safe to run submit_patch().{multi_file_note}"

    return TestGateResult(
        mode="status",
        workspace=str(ws),
        success=(can_submit or is_clean),
        status=status_str,
        modified_files=diff_res.modified_files,
        untracked_files=diff_res.untracked_files,
        file_stats=diff_res.file_stats,
        total_files_modified=diff_res.total_files_modified,
        total_additions=diff_res.total_additions,
        total_deletions=diff_res.total_deletions,
        forbidden_test_files=diff_res.forbidden_test_files,
        dangerous_scratch_files=diff_res.dangerous_scratch_files,
        syntax_errors=syntax_errors,
        can_submit_patch=can_submit,
        summary=summary,
        recommendation=rec,
        diff_preview=diff_res.diff_preview,
    )


# ==============================================================================
# Human-Readable Formatting
# ==============================================================================

def format_report(res: TestGateResult) -> str:
    """Format TestGateResult into high-signal human- and agent-readable text."""
    lines: List[str] = []

    if res.mode == "blast":
        lines.append(f"=== [test-gate] Regression Test Gate ({res.status}) ===")
        lines.append(f"Workspace: {res.workspace}")
        if res.modified_files:
            lines.append(f"Target(s): {', '.join(res.modified_files)}")
        if res.test_files_checked:
            lines.append(f"Neighbor test suite ({len(res.test_files_checked)} file(s)): {', '.join(res.test_files_checked)}")
        lines.append(f"Results: {res.tests_run} run | {res.tests_passed} passed | {res.tests_failed} failed | {res.tests_errors} errors")
        lines.append("-" * 75)

        if res.forbidden_test_files:
            lines.append("\n" + "=" * 75)
            lines.append("🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE")
            for f in res.forbidden_test_files:
                lines.append(f"  • {f}")
            lines.append("Container B automatically reverts (discards) test-file modifications during evaluation.")
            lines.append("Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files.")
            lines.append("To revert forbidden test file modifications, run:")
            for f in res.forbidden_test_files:
                lines.append(f"  git checkout -- {f}")
            lines.append("=" * 75 + "\n")

        if res.failures:
            lines.append("💥 TEST FAILURES DETECTED:")
            for f in res.failures[:5]:
                lines.append(f"  • {f.test_id} [{f.error_type}]")
                if f.line_number:
                    lines.append(f"    Line: {f.line_number}")
                if f.failing_statement:
                    lines.append(f"    Statement: {f.failing_statement}")
                if f.error_message:
                    lines.append(f"    Failure: {f.error_message}")
                if f.expected and f.actual:
                    lines.append(f"    Expected:  {f.expected}")
                    lines.append(f"    Actual:    {f.actual}")
                if f.traceback_snippet:
                    lines.append("    Traceback snippet:")
                    for tb_line in f.traceback_snippet.splitlines()[:4]:
                        lines.append(f"      {tb_line}")
                if f.remediation_hint:
                    lines.append(f"    Guidance: {f.remediation_hint}")
                lines.append("")
            if len(res.failures) > 5:
                lines.append(f"  ... (+{len(res.failures) - 5} additional failure(s) omitted)")
            lines.append("-" * 75)

        lines.append(f"Summary: {res.summary}")
        lines.append(f"Recommendation: {res.recommendation}")

    elif res.mode == "diff":
        lines.append(f"=== [test-gate] Git Diff Inspector ({res.status}) ===")
        lines.append(f"Workspace: {res.workspace}")

        if res.forbidden_test_files:
            lines.append("\n" + "=" * 75)
            lines.append("🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE")
            for f in res.forbidden_test_files:
                lines.append(f"  • {f}")
            lines.append("Container B automatically reverts (discards) test-file modifications during evaluation.")
            lines.append("Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files.")
            lines.append("To revert forbidden test file modifications, run:")
            for f in res.forbidden_test_files:
                lines.append(f"  git checkout -- {f}")
            lines.append("=" * 75 + "\n")

        if res.dangerous_scratch_files:
            lines.append("⚠️ DANGER: Untracked scratch files in /workspace:")
            for s in res.dangerous_scratch_files:
                lines.append(f"  • {s}")
            lines.append("Move to /tmp or delete immediately.\n")

        lines.append(f"Touched files ({res.total_files_modified}): +{res.total_additions}, -{res.total_deletions}")
        for stat in res.file_stats:
            tag = " [FORBIDDEN TEST]" if stat.is_forbidden else ""
            lines.append(f"  • {stat.path}: +{stat.additions}, -{stat.deletions} [{stat.status}]{tag}")

        lines.append("\n=== Unified Diff Preview ===")
        lines.append(res.diff_preview)
        lines.append("\n" + "-" * 75)
        lines.append(f"Summary: {res.summary}")
        lines.append(f"Recommendation: {res.recommendation}")

    elif res.mode == "status":
        lines.append(f"=== [test-gate] Patch Readiness Status ({res.status}) ===")
        lines.append(f"Workspace: {res.workspace}")

        if res.forbidden_test_files:
            lines.append("\n" + "=" * 75)
            lines.append("🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE")
            for f in res.forbidden_test_files:
                lines.append(f"  • {f}")
            lines.append("Container B automatically reverts (discards) test-file modifications during evaluation.")
            lines.append("Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files.")
            lines.append("To revert forbidden test file modifications, run:")
            for f in res.forbidden_test_files:
                lines.append(f"  git checkout -- {f}")
            lines.append("=" * 75 + "\n")

        if res.syntax_errors:
            lines.append("\n✗ Syntax Errors Detected:")
            for se in res.syntax_errors:
                lines.append(f"  • {se.file_path}:{se.line_number}:{se.column} [{se.error_type}]: {se.message}")
                if se.snippet:
                    lines.append(se.snippet)

        if res.dangerous_scratch_files:
            lines.append("\n⚠️ Dangerous untracked scratch files:")
            for d in res.dangerous_scratch_files:
                lines.append(f"  • {d}")

        lines.append(f"\nFiles touched ({res.total_files_modified}): +{res.total_additions}, -{res.total_deletions}")
        for stat in res.file_stats:
            tag = " [FORBIDDEN TEST]" if stat.is_forbidden else ""
            lines.append(f"  • {stat.path}: +{stat.additions}, -{stat.deletions} [{stat.status}]{tag}")

        lines.append("\nPatch Submission Readiness:")
        if res.can_submit_patch:
            lines.append("  [✓ READY TO SUBMIT] Safe to run submit_patch().")
        else:
            lines.append("  [✗ BLOCKED] DO NOT run submit_patch(). Address issues above.")

        if res.summary:
            lines.append(f"\nSummary: {res.summary}")
        lines.append(f"\nRecommendation: {res.recommendation}")

    return "\n".join(lines)


def print_usage_guide(invalid_arg: Optional[str] = None):
    """Print available options with copy-pasteable examples."""
    if invalid_arg:
        print(f"[test-gate] ⚠️ Unknown argument or flag: '{invalid_arg}'\n")
    print("test-gate: Authoritative regression runner, diff inspector, and patch readiness gate.\n")
    print("Available Modes & Options:")
    print("  --blast [file], -b, blast    Run distance-1 neighbor tests on modified or target files (default)")
    print("  --diff, -d, diff             Safe read-only git diff with test-file mutation assertion")
    print("  --status, -s, status         Full patch readiness: syntax checks, safety, submit recommendation")
    print("  --json, -j                   Output structured JSON (Pydantic v2)")
    print("  --timeout <sec>, -t <sec>    Pytest execution timeout per test file (default: 60s)")
    print("  --workspace <dir>, -w <dir>  Explicit workspace root directory")
    print("  --help, -h                   Show this help message\n")
    print("Copy-Pasteable Examples:")
    print("  python3 gate.py                      # Smart default: check status or run neighbor tests if files modified")
    print("  python3 gate.py diff                 # Positional diff inspection")
    print("  python3 gate.py blast                # Positional blast regression")
    print("  python3 gate.py status               # Positional patch readiness")
    print("  python3 gate.py fastapi/routing.py   # Run distance-1 neighbor tests for target file")
    print("  python3 gate.py --diff               # Inspect diff and assert no test files were touched")
    print("  python3 gate.py --status             # Verify syntax, safety, and patch submission readiness")
    print("  python3 gate.py --status --json      # Structured patch readiness assessment for agents")
    print("  python3 gate.py -t 30 --blast        # Run blast regression with 30s timeout per test file")


# ==============================================================================
# CLI Argument Parser & Entrypoint
# ==============================================================================

def parse_cli_args(argv: List[str]) -> Tuple[str, List[str], bool, Optional[str], int, Optional[str]]:
    """Parse CLI arguments with high forgiveness and positional routing.

    Returns:
        (mode, target_args, json_mode, ws_override, timeout_per_file, unknown_flag)
    """
    mode: Optional[str] = None
    target_args: List[str] = []
    json_mode: bool = False
    ws_override: Optional[str] = None
    timeout_per_file: int = 60
    unknown_flag: Optional[str] = None

    # Check for help first
    if any(a.lower() in ("-h", "--help", "help", "-help") for a in argv):
        return ("help", [], False, None, 60, None)

    i = 0
    while i < len(argv):
        arg = argv[i]
        arg_lower = arg.lower()

        # JSON mode
        if arg in ("--json", "-j"):
            json_mode = True
            i += 1
            continue

        # Timeout options
        if arg in ("--timeout", "-t"):
            if i + 1 < len(argv):
                try:
                    timeout_per_file = max(1, int(argv[i + 1]))
                except ValueError:
                    pass
                i += 2
                continue
            else:
                i += 1
                continue
        if arg.startswith(("--timeout=", "-t=")):
            val = arg.split("=", 1)[1]
            try:
                timeout_per_file = max(1, int(val))
            except ValueError:
                pass
            i += 1
            continue

        # Workspace options
        if arg in ("--workspace", "-w"):
            if i + 1 < len(argv):
                ws_override = argv[i + 1]
                i += 2
                continue
            else:
                i += 1
                continue
        if arg.startswith(("--workspace=", "-w=")):
            ws_override = arg.split("=", 1)[1]
            i += 1
            continue

        # Mode flags
        if arg in ("--diff", "-d"):
            mode = "diff"
            i += 1
            continue
        if arg in ("--status", "-s"):
            mode = "status"
            i += 1
            continue
        if arg in ("--blast", "-b"):
            mode = "blast"
            i += 1
            continue

        # Check for unknown flags (starting with -)
        if arg.startswith("-"):
            unknown_flag = arg
            i += 1
            continue

        # Positional routing
        if arg_lower in ("diff", "inspect"):
            mode = "diff"
            i += 1
            continue
        if arg_lower in ("status", "ready", "check"):
            mode = "status"
            i += 1
            continue
        if arg_lower in ("blast", "test", "tests"):
            mode = "blast"
            i += 1
            continue

        # Ignored loose / filler words
        if arg_lower in ("run", "show", "on", "for", "against"):
            i += 1
            continue

        # Any other positional argument is treated as a target file or git arg
        target_args.append(arg)
        i += 1

    return (mode or "auto", target_args, json_mode, ws_override, timeout_per_file, unknown_flag)


def main() -> int:
    """CLI entrypoint. Always exits 0."""
    try:
        raw_args = sys.argv[1:]
        mode, target_args, json_mode, ws_override, timeout_per_file, unknown_flag = parse_cli_args(raw_args)

        if mode == "help":
            print_usage_guide()
            return 0

        if unknown_flag:
            print_usage_guide(unknown_flag)
            return 0

        ws = get_workspace_dir(ws_override)

        # Smart default resolution for "auto"
        if mode == "auto":
            if target_args:
                mode = "blast"
            else:
                modified_files, _, _ = get_git_status_and_files(ws)
                if modified_files:
                    mode = "blast"
                else:
                    mode = "status"

        if mode == "blast":
            res = execute_blast(ws, target_args, timeout_per_file=timeout_per_file)
        elif mode == "diff":
            res = execute_diff(ws, target_args)
        elif mode == "status":
            res = execute_status(ws)
        else:
            print_usage_guide()
            return 0

        if json_mode:
            print(res.model_dump_json(indent=2))
        else:
            print(format_report(res))

        return 0

    except Exception as e:
        print(f"[test-gate] Unexpected error: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
`````

## File: submission/skills/test-gate/gate.py
`````python
#!/usr/bin/env python3
"""test-gate: Consolidated regression test runner, diff inspector, and patch readiness gatekeeper.

Consolidates blast-radius (distance-1 neighbor regression test runner) and diff-inspect
(safe git diff viewer) into a single authoritative gatekeeper skill.

Modes:
  1. Default or blast / --blast / -b:
     - Identifies modified Python files in git working tree.
     - Locates distance-1 neighbor tests (maps source files to test files).
     - Executes pytest on neighbor tests with timeout (default 60s per test file).
     - Reports clear summary: tests run, tests passed, tests failed, and failing traceback snippet.
  2. diff / --diff / -d:
     - Runs safe read-only git diff against HEAD.
     - Verifies NO test files in /workspace were modified. If modified, emits:
       🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE
       explaining that Container B automatically reverts (discards) test-file modifications during evaluation.
       Instructs exact command: git checkout -- <file>.
     - Summarizes lines added, lines removed, files touched.
     - Diff truncation safety: truncates massive diffs (>500 lines or >50KB) with file-by-file summary.
  3. status / --status / -s:
     - Full patch readiness: modified files, test file safety check, syntax check on touched files,
       and recommendation on whether it is safe to run submit_patch.
     - Emits [✓ READY TO SUBMIT] when patch is 100% clean and ready.
  4. Actionable Diagnostics:
     - If no files modified, tells the LLM cleanly what files exist to test.
     - If tests fail, prints the exact failing test names, line numbers, statements, and guidance.
     - If non-existent flags or arguments passed, explains available options with copy-pasteable examples.
  5. --json / -j:
     - Returns 100% Pydantic v2 structured schemas.

Always exits with code 0.
"""

from __future__ import annotations

import ast
from collections import defaultdict
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True

from pydantic import BaseModel, ConfigDict, Field

ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
SKIP_DIRS = {"build", "dist", ".git", "__pycache__", "venv", ".venv", "node_modules", "wheels", ".pytest_cache"}

FORBIDDEN_HARNESS_FILES = {
    "pytest.ini",
    "conftest.py",
    "setup.cfg",
    "tox.ini",
    ".pre-commit-config.yaml",
}

SCRATCH_FILE_PATTERNS = [
    r"^repro.*\.py$",
    r"^.*_repro\.py$",
    r"^reproduce.*\.py$",
    r"^test.*\.py$",
    r"^.*_test\.py$",
    r"^tmp.*\.py$",
    r"^temp.*\.py$",
    r"^scratch.*\.py$",
    r"^run_.*\.py$",
    r"^debug.*\.py$",
    r"^poc.*\.py$",
    r"^solve.*\.py$",
    r"^check.*\.py$",
    r"^verify.*\.py$",
]

MAX_DIFF_LINES = 500
MAX_DIFF_BYTES = 50 * 1024  # 50 KB


def strip_ansi(text: str) -> str:
    """Strip ANSI terminal escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


# ==============================================================================
# Pydantic v2 Data Models
# ==============================================================================

class FailureDetail(BaseModel):
    """Detailed breakdown of an individual test failure."""

    model_config = ConfigDict(extra="ignore")

    test_id: str = Field(..., description="Test node ID, e.g. tests/test_routing.py::test_route")
    test_file: str = Field(default="", description="Path to test file")
    test_name: str = Field(default="", description="Name of test function or method")
    line_number: Optional[int] = Field(default=None, description="Line number of failure")
    error_type: str = Field(default="AssertionError", description="Exception type")
    error_message: str = Field(default="", description="Raw error message")
    failing_statement: str = Field(default="", description="Failing code statement")
    expected: Optional[str] = Field(default=None, description="Expected value")
    actual: Optional[str] = Field(default=None, description="Actual value")
    traceback_snippet: str = Field(default="", description="Cleaned traceback snippet")
    remediation_hint: str = Field(default="", description="Actionable hint for remediation")


class SyntaxErrorDetail(BaseModel):
    """Details of a Python syntax or compilation error."""

    model_config = ConfigDict(extra="ignore")

    file_path: str = Field(..., description="File with syntax error")
    line_number: int = Field(default=1, description="Line number")
    column: int = Field(default=1, description="Column number")
    error_type: str = Field(default="SyntaxError", description="SyntaxError or IndentationError")
    message: str = Field(..., description="Error message from parser")
    snippet: str = Field(default="", description="Code snippet with caret pointer")


class FileChangeStat(BaseModel):
    """File-level git change statistics and safety classifications."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Relative file path")
    status: str = Field(default="M", description="Git status code (M, A, D, R, ??)")
    additions: int = Field(default=0, ge=0, description="Lines added")
    deletions: int = Field(default=0, ge=0, description="Lines deleted")
    binary: bool = Field(default=False, description="Whether file is binary")
    is_test_file: bool = Field(default=False, description="Whether file is part of the test suite")
    is_forbidden: bool = Field(default=False, description="Whether file is a forbidden test/harness file")
    is_scratch_file: bool = Field(default=False, description="Whether file is an untracked scratch file")


class TestGateResult(BaseModel):
    """Authoritative result schema for test-gate CLI."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(..., description="Execution mode: blast, diff, status")
    workspace: str = Field(..., description="Resolved workspace root directory")
    success: bool = Field(default=True, description="True if check/run passed cleanly")
    status: str = Field(default="PASSED", description="High-level status code")
    modified_files: List[str] = Field(default_factory=list, description="Modified source files detected")
    untracked_files: List[str] = Field(default_factory=list, description="Untracked files detected")
    test_files_checked: List[str] = Field(default_factory=list, description="Test files executed or identified")
    tests_run: int = Field(default=0, ge=0, description="Count of tests executed")
    tests_passed: int = Field(default=0, ge=0, description="Count of tests passed")
    tests_failed: int = Field(default=0, ge=0, description="Count of tests failed")
    tests_errors: int = Field(default=0, ge=0, description="Count of test errors")
    failures: List[FailureDetail] = Field(default_factory=list, description="Detailed test failure breakdowns")
    file_stats: List[FileChangeStat] = Field(default_factory=list, description="File-by-file diff stats")
    total_files_modified: int = Field(default=0, ge=0, description="Total files touched")
    total_additions: int = Field(default=0, ge=0, description="Total lines added")
    total_deletions: int = Field(default=0, ge=0, description="Total lines deleted")
    forbidden_test_files: List[str] = Field(default_factory=list, description="Modified test files (forbidden in SWE-bench)")
    dangerous_scratch_files: List[str] = Field(default_factory=list, description="Untracked scratch files in /workspace")
    syntax_errors: List[SyntaxErrorDetail] = Field(default_factory=list, description="Syntax errors in touched files")
    can_submit_patch: bool = Field(default=False, description="True if patch is ready and safe for submit_patch")
    summary: str = Field(default="", description="Concise human-readable summary")
    recommendation: str = Field(default="", description="Explicit actionable recommendation")
    diff_preview: str = Field(default="", description="Unified diff preview (capped at 500 lines / 50KB)")


FailureDetail.model_rebuild()
SyntaxErrorDetail.model_rebuild()
FileChangeStat.model_rebuild()
TestGateResult.model_rebuild()


# ==============================================================================
# Helper Functions: Workspace & Classifications
# ==============================================================================

def get_workspace_dir(explicit_ws: Optional[str] = None) -> pathlib.Path:
    """Robustly and deterministically locate the target repository workspace directory."""
    if explicit_ws:
        p = pathlib.Path(explicit_ws)
        if p.is_dir():
            return p.resolve()

    # 1. Check caller stack frame for _orig_cwd (set by ADK harness)
    try:
        f = sys._getframe()
        while f:
            if "_orig_cwd" in f.f_locals and f.f_locals["_orig_cwd"]:
                p = pathlib.Path(f.f_locals["_orig_cwd"])
                if p.is_dir() and (
                    (p / ".git").exists()
                    or (p / "pyproject.toml").exists()
                    or (p / "setup.py").exists()
                    or (p / "setup.cfg").exists()
                ):
                    return p.resolve()
            f = f.f_back
    except Exception:
        pass

    # 2. Environment variable overrides
    for env_var in ("SWEGEMMA_WORKSPACE", "WORKSPACE_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = pathlib.Path(val)
            if p.is_dir():
                return p.resolve()

    # 3. Search upward from current working directory for repository markers
    cur = pathlib.Path.cwd().resolve()
    for parent in [cur] + list(cur.parents):
        if (
            (parent / ".git").exists()
            or (parent / "pyproject.toml").exists()
            or (parent / "setup.py").exists()
            or (parent / "setup.cfg").exists()
        ):
            return parent

    # 4. Standard container workspace fallback
    ws_fixed = pathlib.Path("/workspace")
    if ws_fixed.is_dir():
        return ws_fixed.resolve()

    return cur


def is_git_repo(ws: pathlib.Path) -> bool:
    """Check if directory is inside a valid git working tree."""
    code, _ = run_git_cmd(["rev-parse", "--is-inside-work-tree"], cwd=ws, timeout_secs=5)
    return code == 0


def is_test_file(path_str: str) -> bool:
    """Check if file is part of the test suite."""
    p = pathlib.Path(path_str)
    name = p.name.lower()
    parts_lower = [part.lower() for part in p.parts]

    if any(part in ("tests", "test", "testing") for part in parts_lower):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if name in ("conftest.py", "pytest.ini"):
        return True
    return False


def is_forbidden_harness_file(path_str: str) -> bool:
    """Check if file is a forbidden harness configuration or test configuration."""
    p = pathlib.Path(path_str)
    name = p.name.lower()
    if name in FORBIDDEN_HARNESS_FILES:
        return True
    if is_test_file(path_str):
        return True
    return False


def is_scratch_file(path_str: str) -> bool:
    """Check if file matches temporary, reproduction, or scratch script patterns."""
    p = pathlib.Path(path_str)
    name = p.name.lower()

    if ".adk_exec" in name or name.startswith(".adk_exec"):
        return False
    if name.endswith((".tmp", ".temp", ".log", ".bak", ".swp", "~")):
        return True

    for pat in SCRATCH_FILE_PATTERNS:
        if re.match(pat, name):
            return True

    if len(p.parts) == 1 and name.endswith(".py"):
        # Root-level python scripts not matching standard project files
        if name not in ("setup.py", "conftest.py", "__init__.py"):
            return True

    parts_lower = [part.lower() for part in p.parts]
    if any(part in ("tmp", "temp", "scratch") for part in parts_lower):
        return True

    return False


def run_git_cmd(args: List[str], cwd: pathlib.Path, timeout_secs: int = 15) -> Tuple[int, str]:
    """Execute a git command safely in cwd without raising unhandled exceptions."""
    git_bin = shutil.which("git") or "git"
    try:
        res = subprocess.run(
            [git_bin] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_secs,
        )
        out = res.stdout if res.stdout else res.stderr
        return res.returncode, out.rstrip()
    except subprocess.TimeoutExpired:
        return 1, f"Git command timed out after {timeout_secs}s: git {' '.join(args)}"
    except Exception as e:
        return 1, f"Git command error: {e}"


def get_git_status_and_files(ws: pathlib.Path) -> Tuple[List[str], List[str], Dict[str, str]]:
    """Query git status to return (modified_files, untracked_files, status_map)."""
    if not is_git_repo(ws):
        return [], [], {}

    code, out = run_git_cmd(
        ["status", "--porcelain", "-uall", "--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"],
        cwd=ws,
        timeout_secs=10,
    )
    if code != 0:
        code, out = run_git_cmd(["status", "--porcelain"], cwd=ws, timeout_secs=10)

    modified_files: List[str] = []
    untracked_files: List[str] = []
    status_map: Dict[str, str] = {}

    if code == 0 and out:
        for raw_line in out.splitlines():
            line = raw_line.rstrip()
            if not line:
                continue
            parts = line.strip().split(maxsplit=1)
            if len(parts) < 2:
                continue
            code_str = parts[0]
            rel_path = parts[1].strip('"')
            if " -> " in rel_path:
                rel_path = rel_path.split(" -> ")[-1].strip().strip('"')

            if ".adk_exec" in rel_path or pathlib.Path(rel_path).name.startswith(".adk_exec"):
                continue

            if code_str == "??":
                untracked_files.append(rel_path)
            else:
                status_map[rel_path] = code_str or "M"
                if "D" not in code_str:
                    modified_files.append(rel_path)

    return modified_files, untracked_files, status_map


# ==============================================================================
# Syntax Verification
# ==============================================================================

def generate_syntax_snippet(source_lines: List[str], lineno: int, column: int) -> str:
    """Generate code snippet with visual caret pointer at line and column."""
    if not source_lines:
        return ""
    target_idx = max(0, min(len(source_lines) - 1, lineno - 1))
    start_idx = max(0, target_idx - 1)
    end_idx = min(len(source_lines), target_idx + 2)

    width = max(len(str(end_idx)), 2)
    out: List[str] = []
    for idx in range(start_idx, end_idx):
        line_num = idx + 1
        num_str = str(line_num).rjust(width)
        line_content = source_lines[idx].rstrip("\r\n")
        if idx == target_idx:
            out.append(f"> {num_str} | {line_content.expandtabs(4)}")
            prefix = line_content[: max(0, column - 1)].expandtabs(4)
            out.append(f"  {' ' * width} | {' ' * len(prefix)}^")
        else:
            out.append(f"  {num_str} | {line_content.expandtabs(4)}")
    return "\n".join(out)


def verify_python_syntax(file_path: pathlib.Path) -> Optional[SyntaxErrorDetail]:
    """Parse a Python file using AST and return a SyntaxErrorDetail if invalid."""
    if not file_path.exists() or not file_path.is_file():
        return None
    try:
        raw_bytes = file_path.read_bytes()
    except Exception as e:
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=1,
            column=1,
            error_type="FileReadError",
            message=f"Could not read file: {e}",
            snippet="> 1 | (unreadable file)",
        )

    # Detect binary files containing null bytes
    if b"\x00" in raw_bytes[:4096]:
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=1,
            column=1,
            error_type="BinaryFileError",
            message="File contains binary or null bytes; cannot parse as Python source.",
            snippet="> 1 | (binary file)",
        )

    try:
        source_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        source_text = raw_bytes.decode("latin-1", errors="replace")

    source_lines = source_text.splitlines()

    try:
        ast.parse(raw_bytes, filename=str(file_path))
    except SyntaxError as e:
        lineno = e.lineno or 1
        col = e.offset or 1
        error_type = type(e).__name__
        msg = e.msg or "syntax error"
        snippet = generate_syntax_snippet(source_lines, lineno, col)
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=lineno,
            column=col,
            error_type=error_type,
            message=msg,
            snippet=snippet,
        )
    except Exception as e:
        return SyntaxErrorDetail(
            file_path=str(file_path),
            line_number=1,
            column=1,
            error_type=type(e).__name__,
            message=str(e),
            snippet="> 1 | (parse error)",
        )

    return None


# ==============================================================================
# Neighbor Test Resolution & Blast Radius Discovery
# ==============================================================================

def resolve_docs_src_test_path(path_str: str) -> Optional[str]:
    """Framework-aware path mapping for FastAPI doc tutorials.

    Maps docs_src/<category>/tutorial<N>[_<variant>].py to
    tests/test_tutorial/test_<category>/test_tutorial<N>.py (stripping _py310, _py39, etc.).
    """
    clean_p = path_str.replace("\\", "/").strip().lstrip("/")
    parts = clean_p.split("/")
    if "docs_src" not in parts:
        return None
    idx = parts.index("docs_src")
    subparts = parts[idx + 1:]
    if len(subparts) < 2:
        return None

    category_parts = subparts[:-1]
    filename = subparts[-1]
    stem = filename[:-3] if filename.endswith(".py") else filename

    m = re.match(r"^(tutorial\d+[a-z]?)(?:_.*)?$", stem)
    base_stem = m.group(1) if m else re.sub(r"(_(?:an|py3\d+|py\d+|pv\d+|non_annotated|annotated))+$", "", stem)

    category = "_".join(category_parts)
    clean_category = category[5:] if category.startswith("test_") else category
    return f"tests/test_tutorial/test_{clean_category}/test_{base_stem}.py"


def extract_ast_symbols(file_path: pathlib.Path) -> Set[str]:
    """Extract top-level class and function names from a Python source file."""
    symbols: Set[str] = set()
    if not file_path.exists() or file_path.suffix != ".py":
        return symbols
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(file_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.add(node.name)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not item.name.startswith("__"):
                            symbols.add(item.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("__"):
                    symbols.add(node.name)
    except Exception:
        pass
    return {s for s in symbols if len(s) > 1}


def find_neighbor_tests_for_target(target_path: pathlib.Path, ws: pathlib.Path) -> List[str]:
    """Locate distance-1 neighbor tests for a source target file."""
    try:
        rel_target = target_path.relative_to(ws)
    except ValueError:
        rel_target = target_path

    rel_posix = rel_target.as_posix()
    stem = target_path.stem

    # If target is already a test file, return it directly
    if is_test_file(rel_posix):
        return [rel_posix]

    direct_tests: List[str] = []

    # 1. Framework-aware mapping (e.g. FastAPI docs tutorials)
    docs_cand = resolve_docs_src_test_path(rel_posix)
    if docs_cand:
        cp = ws / docs_cand
        if cp.exists():
            direct_tests.append(cp.relative_to(ws).as_posix())

    # 2. Canonical neighbor candidates
    target_mod_parts = list(rel_target.parts)
    if target_mod_parts and target_mod_parts[-1].endswith(".py"):
        target_mod_parts[-1] = target_mod_parts[-1][:-3]
    full_mod_name = "_".join(target_mod_parts)

    candidates = [
        f"tests/test_{stem}.py",
        f"test/test_{stem}.py",
        f"tests/{stem}_test.py",
        f"test_{stem}.py",
        f"tests/test_{full_mod_name}.py",
    ]
    if len(rel_target.parts) > 1:
        candidates.append(f"tests/{'/'.join(rel_target.parts[:-1])}/test_{stem}.py")

    for cand in candidates:
        cp = ws / cand
        if cp.exists():
            rel_cand = cp.relative_to(ws).as_posix()
            if rel_cand not in direct_tests:
                direct_tests.append(rel_cand)

    # 3. Search repo for test_<stem>.py if not yet resolved
    if not direct_tests:
        try:
            for match in ws.rglob(f"test_{stem}.py"):
                if not any(part in SKIP_DIRS for part in match.parts):
                    direct_tests.append(match.relative_to(ws).as_posix())
                    break
        except Exception:
            pass

    # 4. Symbol-level test scan
    symbols = extract_ast_symbols(target_path)
    if symbols and len(direct_tests) < 4:
        cand_test_files: List[pathlib.Path] = []
        try:
            for p in ws.rglob("*.py"):
                if any(part in SKIP_DIRS for part in p.parts):
                    continue
                if is_test_file(str(p.relative_to(ws))):
                    cand_test_files.append(p)
        except Exception:
            pass

        for tf in cand_test_files:
            rel_tf = tf.relative_to(ws).as_posix()
            if rel_tf in direct_tests:
                continue
            try:
                txt = tf.read_text(encoding="utf-8", errors="replace")
                if any(sym in txt for sym in symbols):
                    direct_tests.append(rel_tf)
                    if len(direct_tests) >= 5:
                        break
            except Exception:
                continue

    # 5. Distance-1 consumer test resolution
    consumer_tests: List[str] = []
    mod_name_dot = ".".join(target_mod_parts)
    try:
        for p in ws.rglob("*.py"):
            if any(part in SKIP_DIRS for part in p.parts) or p == target_path:
                continue
            rel_p = p.relative_to(ws).as_posix()
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                if stem not in content and mod_name_dot not in content:
                    continue
            except Exception:
                continue

            if is_test_file(rel_p):
                if rel_p not in direct_tests and rel_p not in consumer_tests:
                    consumer_tests.append(rel_p)
            else:
                c_stem = p.stem
                for c_cand in (f"tests/test_{c_stem}.py", f"test/test_{c_stem}.py", f"tests/{c_stem}_test.py"):
                    cp = ws / c_cand
                    if cp.exists():
                        rel_cp = cp.relative_to(ws).as_posix()
                        if rel_cp not in direct_tests and rel_cp not in consumer_tests:
                            consumer_tests.append(rel_cp)
    except Exception:
        pass

    all_tests = direct_tests + consumer_tests
    # Deduplicate and cap to 8 files for fast execution
    seen: Set[str] = set()
    deduped: List[str] = []
    for t in all_tests:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped[:8]


# ==============================================================================
# Pytest Runner & Output Parser
# ==============================================================================

def find_pytest_command(ws: pathlib.Path) -> List[str]:
    """Find the most appropriate pytest runner executable."""
    # 1. Active virtualenv or interpreter directory
    for base in (pathlib.Path(sys.executable).parent, pathlib.Path(sys.prefix) / "bin"):
        cand = base / "pytest"
        if cand.is_file() and os.access(cand, os.X_OK):
            return [str(cand)]

    # 2. VIRTUAL_ENV env var
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        v_cand = pathlib.Path(venv) / "bin" / "pytest"
        if v_cand.is_file() and os.access(v_cand, os.X_OK):
            return [str(v_cand)]

    # 3. Workspace venvs
    for vname in (".venv", "venv"):
        v_cand = ws / vname / "bin" / "pytest"
        if v_cand.is_file() and os.access(v_cand, os.X_OK):
            return [str(v_cand)]

    # 4. Standard container paths
    for vpath in ("/venv", "/opt/venv", "/root/.venv"):
        v_cand = pathlib.Path(vpath) / "bin" / "pytest"
        if v_cand.is_file() and os.access(v_cand, os.X_OK):
            return [str(v_cand)]

    # 5. Check if active interpreter has pytest
    try:
        if importlib.util.find_spec("pytest") is not None:
            return [sys.executable, "-m", "pytest"]
    except Exception:
        pass

    # 6. Fallback PATH
    pytest_bin = shutil.which("pytest")
    if pytest_bin:
        return [pytest_bin]

    return [sys.executable or "python3", "-m", "pytest"]


def run_pytest_suite(test_files: List[str], ws: pathlib.Path, timeout_secs: int = 60) -> Tuple[int, str]:
    """Run pytest on the given test files with workspace in PYTHONPATH and timeout protection."""
    cmd_base = find_pytest_command(ws)
    cmd = cmd_base + ["-vv", "--tb=short", "--disable-warnings"] + test_files

    env = os.environ.copy()
    pp_parts: List[str] = [str(ws)]
    if "/workspace" not in pp_parts:
        pp_parts.append("/workspace")
    existing_pp = env.get("PYTHONPATH", "")
    if existing_pp:
        for p in existing_pp.split(":"):
            if p and p not in pp_parts:
                pp_parts.append(p)
    env["PYTHONPATH"] = ":".join(pp_parts)

    try:
        res = subprocess.run(
            cmd,
            cwd=ws,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_secs,
        )
        return res.returncode, (res.stdout + "\n" + res.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"[test-gate] Pytest timed out after {timeout_secs}s on: {', '.join(test_files)}"
    except Exception as e:
        return 1, f"[test-gate] Pytest error: {e}"


def parse_pytest_results(
    raw_output: str,
    ws: pathlib.Path,
    test_files: Optional[List[str]] = None,
    timeout_secs: Optional[int] = None,
) -> Tuple[int, int, int, List[FailureDetail]]:
    """Parse pytest summary and detailed failures from output."""
    clean_out = strip_ansi(raw_output)
    lines = clean_out.splitlines()

    total_passed = 0
    total_failed = 0
    total_errors = 0

    for line in reversed(lines):
        s = line.strip("= ").strip().lower()
        if "passed" in s or "failed" in s or "error" in s:
            pm = re.search(r"(\d+)\s+passed", s)
            if pm:
                total_passed = int(pm.group(1))
            fm = re.search(r"(\d+)\s+failed", s)
            if fm:
                total_failed = int(fm.group(1))
            em = re.search(r"(\d+)\s+error", s)
            if em:
                total_errors = int(em.group(1))
            break

    # Check for timeout condition
    if "timed out after" in clean_out.lower():
        total_failed = max(1, total_failed)
        return (
            total_passed,
            total_failed,
            total_errors,
            [
                FailureDetail(
                    test_id=f"timeout::{test_files[0] if test_files else 'neighbor_tests'}",
                    test_file=test_files[0] if test_files else "",
                    test_name="pytest_timeout",
                    line_number=None,
                    error_type="TimeoutExpired",
                    error_message=clean_out.strip().splitlines()[-1] if clean_out.strip() else "Pytest timed out",
                    failing_statement=f"Execution timed out after {timeout_secs or 60}s",
                    expected="Tests to complete within timeout limit",
                    actual=f"Timed out after {timeout_secs or 60}s",
                    traceback_snippet=clean_out.strip()[:600],
                    remediation_hint=f"Pytest execution timed out after {timeout_secs or 60}s. Check for infinite loops, deadlocks, or slow fixtures. Increase timeout with -t <secs> or --timeout <secs>.",
                )
            ],
        )

    # Parse failure blocks
    header_re = re.compile(r"^_{3,}\s+(.*?)\s+_{3,}$")
    loc_re = re.compile(r"^(.*?):(\d+):\s+in\s+(\S+)")
    assert_eq_re = re.compile(r"(?:AssertionError:\s+)?assert\s+(.+?)\s+==\s+(.+)$")
    err_re = re.compile(r"^E\s+([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception):\s*(.*)$")

    blocks: List[Tuple[str, List[str]]] = []
    current_header: Optional[str] = None
    current_lines: List[str] = []

    for line in lines:
        clean = line.strip()
        m = header_re.match(clean)
        if m:
            if current_header and current_lines:
                blocks.append((current_header, current_lines))
            current_header = m.group(1).strip()
            current_lines = []
        elif current_header is not None:
            if clean.startswith("=") and ("short test summary info" in clean or "failed" in clean or "passed" in clean):
                blocks.append((current_header, current_lines))
                current_header = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_header and current_lines:
        blocks.append((current_header, current_lines))

    failures: List[FailureDetail] = []
    for header, blines in blocks:
        test_file = ""
        line_no = None
        func_name = header
        error_type = "AssertionError"
        error_msg = ""
        failing_stmt = ""
        expected = None
        actual = None
        snippet_lines: List[str] = []

        for bline in blines:
            sline = bline.strip()
            lm = loc_re.match(sline)
            if lm:
                test_file = lm.group(1)
                line_no = int(lm.group(2))
                func_name = lm.group(3)
                continue

            if sline.startswith("E   ") or sline.startswith("E "):
                e_content = sline[2:].strip()
                snippet_lines.append(sline)
                em = err_re.match(sline)
                if em:
                    error_type = em.group(1)
                    error_msg = em.group(2).strip()
                elif "assert " in sline and not error_msg:
                    error_type = "AssertionError"
                    error_msg = e_content

                am = assert_eq_re.search(e_content)
                if am:
                    actual = am.group(1).strip()
                    expected = am.group(2).strip()
            elif sline.startswith("assert ") and not failing_stmt:
                failing_stmt = sline
                snippet_lines.append(sline)

        # Build clean test id
        test_id = f"{test_file}::{func_name}" if test_file else func_name
        tb_snippet = "\n".join(snippet_lines[:8]) if snippet_lines else "\n".join(blines[:6])

        hint = f"Fix implementation in source code causing `{failing_stmt or error_msg or 'failure'}`."
        if expected and actual:
            hint = f"Expected `{expected}` but produced `{actual}`. Align return values or edge case handling."

        failures.append(
            FailureDetail(
                test_id=test_id,
                test_file=test_file,
                test_name=func_name,
                line_number=line_no,
                error_type=error_type,
                error_message=error_msg,
                failing_statement=failing_stmt,
                expected=expected,
                actual=actual,
                traceback_snippet=tb_snippet,
                remediation_hint=hint,
            )
        )

    # Fallback if pytest failed without standard block headers (e.g. collection error)
    if total_failed == 0 and total_errors > 0 and not failures:
        err_lines = [l for l in lines if l.startswith("E   ") or "error" in l.lower()]
        failures.append(
            FailureDetail(
                test_id=test_files[0] if test_files else "pytest_suite",
                test_file=test_files[0] if test_files else "",
                test_name="pytest_error",
                error_type="PytestError",
                error_message=err_lines[0].strip() if err_lines else "Pytest error occurred during suite execution",
                traceback_snippet="\n".join(err_lines[:8]) if err_lines else clean_out[:400],
                remediation_hint="Inspect pytest error output and fix syntax or import errors.",
            )
        )

    return total_passed, total_failed, total_errors, failures


# ==============================================================================
# Mode Handlers: blast, diff, status
# ==============================================================================

def execute_blast(
    ws: pathlib.Path,
    target_args: List[str],
    timeout_per_file: int = 60,
) -> TestGateResult:
    """Execute Mode 1: Distance-1 Neighbor Regression Test Runner."""
    if not is_git_repo(ws) and not target_args:
        return TestGateResult(
            mode="blast",
            workspace=str(ws),
            success=False,
            status="NOT_A_GIT_REPOSITORY",
            summary=f"Workspace '{ws}' is not a git repository.",
            recommendation="Initialize git or specify a valid repository path with --workspace <dir>.",
        )

    modified_files, untracked, _ = get_git_status_and_files(ws)

    # Check for forbidden test files in /workspace
    forbidden_modified: List[str] = [f for f in modified_files if is_forbidden_harness_file(f)]
    for u in untracked:
        if is_test_file(u):
            forbidden_modified.append(u)

    # Determine targets: explicit target args or git modified files
    targets: List[pathlib.Path] = []
    if target_args:
        for targ in target_args:
            p = ws / targ if not pathlib.Path(targ).is_absolute() else pathlib.Path(targ)
            if p.exists():
                targets.append(p)
            else:
                # Try finding across repo
                cands = list(ws.rglob(pathlib.Path(targ).name))
                if cands:
                    targets.append(cands[0])
                else:
                    targets.append(p)
    else:
        for m in modified_files:
            if m.endswith(".py"):
                p = ws / m
                if p.exists():
                    targets.append(p)

    # Actionable diagnostics if no files modified or targets specified
    if not targets:
        sample_files: List[str] = []
        try:
            for py_f in ws.rglob("*.py"):
                if any(part in SKIP_DIRS for part in py_f.parts):
                    continue
                rel = py_f.relative_to(ws).as_posix()
                if not is_test_file(rel):
                    sample_files.append(rel)
                    if len(sample_files) >= 6:
                        break
        except Exception:
            pass

        msg = (
            "No modified files detected in git working tree and no target specified.\n"
            f"Available source modules to test:\n"
            + "\n".join(f"  • {f}" for f in sample_files)
            + "\nUsage: python3 gate.py --blast <path/to/file.py>"
        )

        return TestGateResult(
            mode="blast",
            workspace=str(ws),
            success=True,
            status="CLEAN_NO_TARGETS",
            modified_files=[],
            untracked_files=untracked,
            test_files_checked=[],
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_errors=0,
            failures=[],
            forbidden_test_files=forbidden_modified,
            summary="No modified files detected in working tree.",
            recommendation=msg,
        )

    # Resolve neighbor test files for all targets
    test_files: List[str] = []
    for targ in targets:
        neighbors = find_neighbor_tests_for_target(targ, ws)
        for n in neighbors:
            if n not in test_files:
                test_files.append(n)

    target_names = [t.relative_to(ws).as_posix() if ws in t.parents else t.name for t in targets]

    if not test_files:
        summary = f"UNVERIFIED_NO_TESTS: 0 matching neighbor test files found for target(s): {', '.join(target_names)}."
        rec = "VERIFICATION REQUIRED: No tests were run. Write or execute a targeted test before calling submit_patch()."
        return TestGateResult(
            mode="blast",
            workspace=str(ws),
            success=False,
            status="UNVERIFIED_NO_TESTS",
            modified_files=target_names,
            untracked_files=untracked,
            test_files_checked=[],
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            tests_errors=0,
            failures=[],
            forbidden_test_files=forbidden_modified,
            summary=summary,
            recommendation=rec,
        )

    timeout = max(timeout_per_file, len(test_files) * timeout_per_file)
    exit_code, raw_output = run_pytest_suite(test_files, ws, timeout_secs=timeout)
    passed_cnt, failed_cnt, err_cnt, failures = parse_pytest_results(
        raw_output,
        ws,
        test_files=test_files,
        timeout_secs=timeout,
    )

    total_run = passed_cnt + failed_cnt + err_cnt
    if total_run == 0 and exit_code != 0:
        failed_cnt = max(1, len(failures) or 1)
        total_run = failed_cnt

    has_forbidden = len(forbidden_modified) > 0
    success = (exit_code == 0 and failed_cnt == 0 and err_cnt == 0 and not has_forbidden)
    status_str = "PASSED" if success else ("BLOCKED_FORBIDDEN_TEST_FILE" if has_forbidden else "FAILED")

    if success:
        summary = f"PASSED: {passed_cnt} test(s) passed across neighbor test suite ({', '.join(test_files)})."
        rec = "Regression gate clean. Changes pass distance-1 neighbor tests."
    else:
        failing_names = [f.test_id for f in failures]
        f_list = ", ".join(failing_names[:5])
        summary = f"FAILED: {failed_cnt} test(s) failed ({f_list}) across {len(test_files)} neighbor test file(s)."
        rec = (
            f"Exact failing tests:\n"
            + "\n".join(f"  ✗ {t}" for t in failing_names)
            + "\nGuidance: Fix the logic causing test failures in your modified files before calling submit_patch(). Inspect the failing statements and expected vs actual values above, then re-run python3 gate.py."
        )

    return TestGateResult(
        mode="blast",
        workspace=str(ws),
        success=success,
        status=status_str,
        modified_files=target_names,
        untracked_files=untracked,
        test_files_checked=test_files,
        tests_run=total_run,
        tests_passed=passed_cnt,
        tests_failed=failed_cnt,
        tests_errors=err_cnt,
        failures=failures,
        forbidden_test_files=forbidden_modified,
        summary=summary,
        recommendation=rec,
    )


def execute_diff(ws: pathlib.Path, extra_args: Optional[List[str]] = None) -> TestGateResult:
    """Execute Mode 2: Safe Git Diff Viewer & Safety Assertion Gate with Diff Truncation."""
    if not is_git_repo(ws):
        return TestGateResult(
            mode="diff",
            workspace=str(ws),
            success=False,
            status="NOT_A_GIT_REPOSITORY",
            summary=f"Workspace '{ws}' is not a git repository.",
            recommendation="Initialize git or specify a valid repository path with --workspace <dir>.",
        )

    modified_files, untracked, status_map = get_git_status_and_files(ws)

    # 1. Parse git diff --numstat HEAD
    numstat_cmd = ["diff", "--numstat", "HEAD", "--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"]
    code, numstat_out = run_git_cmd(numstat_cmd, cwd=ws, timeout_secs=10)
    if code != 0:
        code, numstat_out = run_git_cmd(["diff", "--numstat"], cwd=ws, timeout_secs=10)

    file_stats: List[FileChangeStat] = []
    forbidden_modified: List[str] = []
    dangerous_scratch: List[str] = []
    total_adds = 0
    total_dels = 0

    if code == 0 and numstat_out:
        for line in numstat_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                add_str, del_str, raw_p = parts[0], parts[1], parts[2]
                is_bin = (add_str == "-" and del_str == "-")
                adds = int(add_str) if not is_bin and add_str.isdigit() else 0
                dels = int(del_str) if not is_bin and del_str.isdigit() else 0

                clean_p = raw_p
                if " => " in clean_p:
                    clean_p = clean_p.split(" => ")[-1].strip()

                if ".adk_exec" in clean_p:
                    continue

                total_adds += adds
                total_dels += dels

                is_test = is_test_file(clean_p)
                is_forbid = is_forbidden_harness_file(clean_p)
                is_scratch = is_scratch_file(clean_p)

                if is_forbid or is_test:
                    forbidden_modified.append(clean_p)

                file_stats.append(
                    FileChangeStat(
                        path=clean_p,
                        status=status_map.get(clean_p, "M"),
                        additions=adds,
                        deletions=dels,
                        binary=is_bin,
                        is_test_file=is_test,
                        is_forbidden=is_forbid,
                        is_scratch_file=is_scratch,
                    )
                )

    # Check untracked files for scratch files and test files
    for u in untracked:
        if is_scratch_file(u):
            dangerous_scratch.append(u)
        if is_test_file(u):
            forbidden_modified.append(u)

    # 2. Get unified diff preview capped at MAX_DIFF_LINES / MAX_DIFF_BYTES
    diff_cmd = ["diff", "HEAD", "--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"]
    if extra_args:
        diff_cmd = ["diff", "HEAD"] + extra_args + ["--", ".", ":(exclude)*.adk_exec*", ":(exclude)**/.adk_exec*"]
    code, diff_out = run_git_cmd(diff_cmd, cwd=ws, timeout_secs=15)
    if code != 0:
        code, diff_out = run_git_cmd(["diff"], cwd=ws, timeout_secs=15)

    diff_lines = diff_out.splitlines() if diff_out else []
    total_diff_lines = len(diff_lines)
    truncated_lines: List[str] = []
    accumulated_bytes = 0
    is_truncated = False

    for idx, line in enumerate(diff_lines):
        line_bytes = len(line.encode("utf-8", errors="replace")) + 1
        if idx >= MAX_DIFF_LINES or (accumulated_bytes + line_bytes > MAX_DIFF_BYTES and idx >= 20):
            is_truncated = True
            break
        truncated_lines.append(line)
        accumulated_bytes += line_bytes

    total_files = len(file_stats)

    if is_truncated:
        omitted_lines = total_diff_lines - len(truncated_lines)
        preview = "\n".join(truncated_lines)
        preview += (
            f"\n\n... [DIFF TRUNCATED: {omitted_lines} lines omitted to prevent LLM context blowout; "
            f"capped at {len(truncated_lines)} lines / {accumulated_bytes // 1024}KB] ...\n\n"
            f"File-by-file summary of changes:\n"
        )
        for stat in file_stats:
            tag = " [FORBIDDEN TEST]" if stat.is_forbidden else ""
            preview += f"  • {stat.path}: +{stat.additions}, -{stat.deletions} [{stat.status}]{tag}\n"
        preview += f"Total changes: {total_files} file(s) touched (+{total_adds} additions, -{total_dels} deletions)"
    else:
        preview = "\n".join(diff_lines)

    is_clean = (total_files == 0 and not diff_out)

    # Safety Assertions
    has_forbidden = len(forbidden_modified) > 0
    has_scratch = len(dangerous_scratch) > 0

    if has_forbidden:
        status_str = "BLOCKED_FORBIDDEN_TEST_FILE"
        success = False
        summary = (
            f"🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE ({', '.join(forbidden_modified)})\n"
            f"Container B automatically reverts (discards) test-file modifications during evaluation.\n"
            f"Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files."
        )
        rec = (
            "To revert forbidden test file modifications, run:\n"
            + "\n".join(f"  git checkout -- {f}" for f in forbidden_modified)
        )
    elif is_clean:
        status_str = "CLEAN"
        success = True
        summary = "Working tree is clean. 0 files modified relative to HEAD."
        rec = "No changes to inspect. Implement fix in source files before calling submit_patch()."
    else:
        status_str = "MODIFIED"
        success = True
        summary = f"{total_files} file(s) touched: +{total_adds} additions, -{total_dels} deletions."
        if has_scratch:
            rec = (
                f"⚠️ DANGER: Untracked scratch files in /workspace ({', '.join(dangerous_scratch)}). "
                f"Remove them or move them to /tmp before submitting!"
            )
        else:
            rec = "Diff inspection clean of forbidden test files."

    return TestGateResult(
        mode="diff",
        workspace=str(ws),
        success=success,
        status=status_str,
        modified_files=[f.path for f in file_stats],
        untracked_files=untracked,
        file_stats=file_stats,
        total_files_modified=total_files,
        total_additions=total_adds,
        total_deletions=total_dels,
        forbidden_test_files=forbidden_modified,
        dangerous_scratch_files=dangerous_scratch,
        can_submit_patch=(not has_forbidden and not has_scratch and not is_clean),
        summary=summary,
        recommendation=rec,
        diff_preview=preview or "(no diff)",
    )


def execute_status(ws: pathlib.Path) -> TestGateResult:
    """Execute Mode 3: Full Patch Readiness & Pre-Submission Gate."""
    if not is_git_repo(ws):
        return TestGateResult(
            mode="status",
            workspace=str(ws),
            success=False,
            status="NOT_A_GIT_REPOSITORY",
            summary=f"Workspace '{ws}' is not a git repository.",
            recommendation="Initialize git or specify a valid repository path with --workspace <dir>.",
        )

    diff_res = execute_diff(ws)

    # Collect Python files touched for syntax verification
    modified_py = [f for f in diff_res.modified_files if f.endswith(".py")]
    syntax_errors: List[SyntaxErrorDetail] = []
    for rel_py in modified_py:
        err = verify_python_syntax(ws / rel_py)
        if err:
            syntax_errors.append(err)

    has_forbidden = len(diff_res.forbidden_test_files) > 0
    has_scratch = len(diff_res.dangerous_scratch_files) > 0
    has_syntax_err = len(syntax_errors) > 0
    is_clean = (diff_res.total_files_modified == 0)

    # Determine readiness and final recommendation
    can_submit = False
    if is_clean:
        status_str = "BLOCKED_EMPTY_DIFF"
        summary = "BLOCKED: Working tree is clean (0 files modified relative to HEAD)."
        rec = "Calling submit_patch() now will result in an empty patch failure. Edit source files first."
    elif has_forbidden:
        status_str = "BLOCKED_FORBIDDEN_TEST_FILE"
        summary = (
            f"🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE: {', '.join(diff_res.forbidden_test_files)}\n"
            f"Container B automatically reverts (discards) test-file modifications during evaluation."
        )
        rec = (
            "Revert forbidden test modifications before submitting:\n"
            + "\n".join(f"  git checkout -- {f}" for f in diff_res.forbidden_test_files)
        )
    elif has_syntax_err:
        status_str = "BLOCKED_SYNTAX_ERROR"
        err_files = [e.file_path for e in syntax_errors]
        summary = f"BLOCKED: Syntax error(s) detected in touched file(s): {', '.join(err_files)}."
        rec = (
            "Fix syntax errors before submitting:\n"
            + "\n".join(f"  • {e.file_path}:{e.line_number} [{e.error_type}]: {e.message}" for e in syntax_errors)
        )
    elif has_scratch:
        status_str = "BLOCKED_DANGEROUS_SCRATCH"
        summary = f"BLOCKED: Dangerous untracked scratch files in /workspace ({', '.join(diff_res.dangerous_scratch_files)})."
        rec = "Delete scratch files or move to /tmp. 'git add -N .' will pollute the official patch."
    else:
        status_str = "READY"
        can_submit = True
        summary = (
            f"READY: Patch is clean and safe to submit! {diff_res.total_files_modified} file(s) touched "
            f"(+{diff_res.total_additions}, -{diff_res.total_deletions})."
        )
        multi_file_note = (
            "\nNote: Over 90% of SWE-bench tasks only require modifying 1 file."
            if diff_res.total_files_modified > 1
            else ""
        )
        rec = f"Patch is verified and [✓ READY TO SUBMIT]. Safe to run submit_patch().{multi_file_note}"

    return TestGateResult(
        mode="status",
        workspace=str(ws),
        success=(can_submit or is_clean),
        status=status_str,
        modified_files=diff_res.modified_files,
        untracked_files=diff_res.untracked_files,
        file_stats=diff_res.file_stats,
        total_files_modified=diff_res.total_files_modified,
        total_additions=diff_res.total_additions,
        total_deletions=diff_res.total_deletions,
        forbidden_test_files=diff_res.forbidden_test_files,
        dangerous_scratch_files=diff_res.dangerous_scratch_files,
        syntax_errors=syntax_errors,
        can_submit_patch=can_submit,
        summary=summary,
        recommendation=rec,
        diff_preview=diff_res.diff_preview,
    )


# ==============================================================================
# Human-Readable Formatting
# ==============================================================================

def format_report(res: TestGateResult) -> str:
    """Format TestGateResult into high-signal human- and agent-readable text."""
    lines: List[str] = []

    if res.mode == "blast":
        lines.append(f"=== [test-gate] Regression Test Gate ({res.status}) ===")
        lines.append(f"Workspace: {res.workspace}")
        if res.modified_files:
            lines.append(f"Target(s): {', '.join(res.modified_files)}")
        if res.test_files_checked:
            lines.append(f"Neighbor test suite ({len(res.test_files_checked)} file(s)): {', '.join(res.test_files_checked)}")
        lines.append(f"Results: {res.tests_run} run | {res.tests_passed} passed | {res.tests_failed} failed | {res.tests_errors} errors")
        lines.append("-" * 75)

        if res.forbidden_test_files:
            lines.append("\n" + "=" * 75)
            lines.append("🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE")
            for f in res.forbidden_test_files:
                lines.append(f"  • {f}")
            lines.append("Container B automatically reverts (discards) test-file modifications during evaluation.")
            lines.append("Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files.")
            lines.append("To revert forbidden test file modifications, run:")
            for f in res.forbidden_test_files:
                lines.append(f"  git checkout -- {f}")
            lines.append("=" * 75 + "\n")

        if res.failures:
            lines.append("💥 TEST FAILURES DETECTED:")
            for f in res.failures[:5]:
                lines.append(f"  • {f.test_id} [{f.error_type}]")
                if f.line_number:
                    lines.append(f"    Line: {f.line_number}")
                if f.failing_statement:
                    lines.append(f"    Statement: {f.failing_statement}")
                if f.error_message:
                    lines.append(f"    Failure: {f.error_message}")
                if f.expected and f.actual:
                    lines.append(f"    Expected:  {f.expected}")
                    lines.append(f"    Actual:    {f.actual}")
                if f.traceback_snippet:
                    lines.append("    Traceback snippet:")
                    for tb_line in f.traceback_snippet.splitlines()[:4]:
                        lines.append(f"      {tb_line}")
                if f.remediation_hint:
                    lines.append(f"    Guidance: {f.remediation_hint}")
                lines.append("")
            if len(res.failures) > 5:
                lines.append(f"  ... (+{len(res.failures) - 5} additional failure(s) omitted)")
            lines.append("-" * 75)

        lines.append(f"Summary: {res.summary}")
        lines.append(f"Recommendation: {res.recommendation}")

    elif res.mode == "diff":
        lines.append(f"=== [test-gate] Git Diff Inspector ({res.status}) ===")
        lines.append(f"Workspace: {res.workspace}")

        if res.forbidden_test_files:
            lines.append("\n" + "=" * 75)
            lines.append("🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE")
            for f in res.forbidden_test_files:
                lines.append(f"  • {f}")
            lines.append("Container B automatically reverts (discards) test-file modifications during evaluation.")
            lines.append("Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files.")
            lines.append("To revert forbidden test file modifications, run:")
            for f in res.forbidden_test_files:
                lines.append(f"  git checkout -- {f}")
            lines.append("=" * 75 + "\n")

        if res.dangerous_scratch_files:
            lines.append("⚠️ DANGER: Untracked scratch files in /workspace:")
            for s in res.dangerous_scratch_files:
                lines.append(f"  • {s}")
            lines.append("Move to /tmp or delete immediately.\n")

        lines.append(f"Touched files ({res.total_files_modified}): +{res.total_additions}, -{res.total_deletions}")
        for stat in res.file_stats:
            tag = " [FORBIDDEN TEST]" if stat.is_forbidden else ""
            lines.append(f"  • {stat.path}: +{stat.additions}, -{stat.deletions} [{stat.status}]{tag}")

        lines.append("\n=== Unified Diff Preview ===")
        lines.append(res.diff_preview)
        lines.append("\n" + "-" * 75)
        lines.append(f"Summary: {res.summary}")
        lines.append(f"Recommendation: {res.recommendation}")

    elif res.mode == "status":
        lines.append(f"=== [test-gate] Patch Readiness Status ({res.status}) ===")
        lines.append(f"Workspace: {res.workspace}")

        if res.forbidden_test_files:
            lines.append("\n" + "=" * 75)
            lines.append("🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE")
            for f in res.forbidden_test_files:
                lines.append(f"  • {f}")
            lines.append("Container B automatically reverts (discards) test-file modifications during evaluation.")
            lines.append("Your patch must resolve the defect exclusively in the source codebase, never by altering existing test files.")
            lines.append("To revert forbidden test file modifications, run:")
            for f in res.forbidden_test_files:
                lines.append(f"  git checkout -- {f}")
            lines.append("=" * 75 + "\n")

        if res.syntax_errors:
            lines.append("\n✗ Syntax Errors Detected:")
            for se in res.syntax_errors:
                lines.append(f"  • {se.file_path}:{se.line_number}:{se.column} [{se.error_type}]: {se.message}")
                if se.snippet:
                    lines.append(se.snippet)

        if res.dangerous_scratch_files:
            lines.append("\n⚠️ Dangerous untracked scratch files:")
            for d in res.dangerous_scratch_files:
                lines.append(f"  • {d}")

        lines.append(f"\nFiles touched ({res.total_files_modified}): +{res.total_additions}, -{res.total_deletions}")
        for stat in res.file_stats:
            tag = " [FORBIDDEN TEST]" if stat.is_forbidden else ""
            lines.append(f"  • {stat.path}: +{stat.additions}, -{stat.deletions} [{stat.status}]{tag}")

        lines.append("\nPatch Submission Readiness:")
        if res.can_submit_patch:
            lines.append("  [✓ READY TO SUBMIT] Safe to run submit_patch().")
        else:
            lines.append("  [✗ BLOCKED] DO NOT run submit_patch(). Address issues above.")

        if res.summary:
            lines.append(f"\nSummary: {res.summary}")
        lines.append(f"\nRecommendation: {res.recommendation}")

    return "\n".join(lines)


def print_usage_guide(invalid_arg: Optional[str] = None):
    """Print available options with copy-pasteable examples."""
    if invalid_arg:
        print(f"[test-gate] ⚠️ Unknown argument or flag: '{invalid_arg}'\n")
    print("test-gate: Authoritative regression runner, diff inspector, and patch readiness gate.\n")
    print("Available Modes & Options:")
    print("  --blast [file], -b, blast    Run distance-1 neighbor tests on modified or target files (default)")
    print("  --diff, -d, diff             Safe read-only git diff with test-file mutation assertion")
    print("  --status, -s, status         Full patch readiness: syntax checks, safety, submit recommendation")
    print("  --json, -j                   Output structured JSON (Pydantic v2)")
    print("  --timeout <sec>, -t <sec>    Pytest execution timeout per test file (default: 60s)")
    print("  --workspace <dir>, -w <dir>  Explicit workspace root directory")
    print("  --help, -h                   Show this help message\n")
    print("Copy-Pasteable Examples:")
    print("  python3 gate.py                      # Smart default: check status or run neighbor tests if files modified")
    print("  python3 gate.py diff                 # Positional diff inspection")
    print("  python3 gate.py blast                # Positional blast regression")
    print("  python3 gate.py status               # Positional patch readiness")
    print("  python3 gate.py fastapi/routing.py   # Run distance-1 neighbor tests for target file")
    print("  python3 gate.py --diff               # Inspect diff and assert no test files were touched")
    print("  python3 gate.py --status             # Verify syntax, safety, and patch submission readiness")
    print("  python3 gate.py --status --json      # Structured patch readiness assessment for agents")
    print("  python3 gate.py -t 30 --blast        # Run blast regression with 30s timeout per test file")


# ==============================================================================
# CLI Argument Parser & Entrypoint
# ==============================================================================

def parse_cli_args(argv: List[str]) -> Tuple[str, List[str], bool, Optional[str], int, Optional[str]]:
    """Parse CLI arguments with high forgiveness and positional routing.

    Returns:
        (mode, target_args, json_mode, ws_override, timeout_per_file, unknown_flag)
    """
    mode: Optional[str] = None
    target_args: List[str] = []
    json_mode: bool = False
    ws_override: Optional[str] = None
    timeout_per_file: int = 60
    unknown_flag: Optional[str] = None

    # Check for help first
    if any(a.lower() in ("-h", "--help", "help", "-help") for a in argv):
        return ("help", [], False, None, 60, None)

    i = 0
    while i < len(argv):
        arg = argv[i]
        arg_lower = arg.lower()

        # JSON mode
        if arg in ("--json", "-j"):
            json_mode = True
            i += 1
            continue

        # Timeout options
        if arg in ("--timeout", "-t"):
            if i + 1 < len(argv):
                try:
                    timeout_per_file = max(1, int(argv[i + 1]))
                except ValueError:
                    pass
                i += 2
                continue
            else:
                i += 1
                continue
        if arg.startswith(("--timeout=", "-t=")):
            val = arg.split("=", 1)[1]
            try:
                timeout_per_file = max(1, int(val))
            except ValueError:
                pass
            i += 1
            continue

        # Workspace options
        if arg in ("--workspace", "-w"):
            if i + 1 < len(argv):
                ws_override = argv[i + 1]
                i += 2
                continue
            else:
                i += 1
                continue
        if arg.startswith(("--workspace=", "-w=")):
            ws_override = arg.split("=", 1)[1]
            i += 1
            continue

        # Mode flags
        if arg in ("--diff", "-d"):
            mode = "diff"
            i += 1
            continue
        if arg in ("--status", "-s"):
            mode = "status"
            i += 1
            continue
        if arg in ("--blast", "-b"):
            mode = "blast"
            i += 1
            continue

        # Check for unknown flags (starting with -)
        if arg.startswith("-"):
            unknown_flag = arg
            i += 1
            continue

        # Positional routing
        if arg_lower in ("diff", "inspect"):
            mode = "diff"
            i += 1
            continue
        if arg_lower in ("status", "ready", "check"):
            mode = "status"
            i += 1
            continue
        if arg_lower in ("blast", "test", "tests"):
            mode = "blast"
            i += 1
            continue

        # Ignored loose / filler words
        if arg_lower in ("run", "show", "on", "for", "against"):
            i += 1
            continue

        # Any other positional argument is treated as a target file or git arg
        target_args.append(arg)
        i += 1

    return (mode or "auto", target_args, json_mode, ws_override, timeout_per_file, unknown_flag)


def main() -> int:
    """CLI entrypoint. Always exits 0."""
    try:
        raw_args = sys.argv[1:]
        mode, target_args, json_mode, ws_override, timeout_per_file, unknown_flag = parse_cli_args(raw_args)

        if mode == "help":
            print_usage_guide()
            return 0

        if unknown_flag:
            print_usage_guide(unknown_flag)
            return 0

        ws = get_workspace_dir(ws_override)

        # Smart default resolution for "auto"
        if mode == "auto":
            if target_args:
                mode = "blast"
            else:
                modified_files, _, _ = get_git_status_and_files(ws)
                if modified_files:
                    mode = "blast"
                else:
                    mode = "status"

        if mode == "blast":
            res = execute_blast(ws, target_args, timeout_per_file=timeout_per_file)
        elif mode == "diff":
            res = execute_diff(ws, target_args)
        elif mode == "status":
            res = execute_status(ws)
        else:
            print_usage_guide()
            return 0

        if json_mode:
            print(res.model_dump_json(indent=2))
        else:
            print(format_report(res))

        return 0

    except Exception as e:
        print(f"[test-gate] Unexpected error: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
`````

## File: submission/skills/test-gate/SKILL.md
`````markdown
---
name: test-gate
description: Authoritative gatekeeper consolidating blast-radius regression test runner and diff-inspect safe git diff viewer with SWE-bench test file safety assertions.
---

# test-gate Skill

Consolidates regression testing (`blast-radius`) and git diff inspection (`diff-inspect`) into a single authoritative gatekeeper for SWE-bench agent workflows.

## Key Capabilities

1. **Distance-1 Regression Tests (`--blast`, `blast`, or default)**:
   - Auto-detects modified Python files in the git working tree or accepts explicit targets.
   - Maps source files to neighbor test files (e.g. `fastapi/routing.py` -> `tests/test_routing.py`, `rich/ansi.py` -> `tests/test_ansi.py`).
   - Runs pytest with 60s/file timeout (configurable via `-t` or `--timeout`) and formats concise failure summaries with traceback snippets.
   - Guard against 0-test false passes: flags `UNVERIFIED_NO_TESTS` if no tests were found.

2. **Safe Git Diff & Safety Assertion (`--diff`, `diff`, `-d`)**:
   - Runs safe read-only git diff against `HEAD`.
   - **CRITICAL SWE-BENCH SAFETY ASSERTION**: Detects any test file modifications in `/workspace` (`tests/*`, `test_*.py`, `conftest.py`). Emits a loud `🚨 FORBIDDEN TEST FILE MODIFIED IN /WORKSPACE` warning with exact `git checkout -- <file>` revert commands because Container B automatically reverts (discards) test-file modifications during evaluation.
   - Diff truncation safety: truncates diffs exceeding 500 lines or 50KB to protect LLM context windows, providing file-by-file stats and net changes.
   - Detects untracked scratch files (`repro*.py`, `tmp*.py`) that `git add -N .` would pollute the official patch with.

3. **Full Patch Readiness Gate (`--status`, `status`, `-s`)**:
   - Synthesizes diff stats, test file safety, scratch file checks, and AST syntax validation across all touched `.py` files.
   - Outputs definitive `[✓ READY TO SUBMIT]` or `[✗ BLOCKED]` advice for calling `submit_patch()`.

4. **Structured JSON Output (`--json`, `-j`)**:
   - Returns 100% Pydantic v2 structured schemas (`TestGateResult`) for programmatic tool use.

## How to Run

### Smart Default (tests modified files or shows status)
```bash
python3 gate.py
```

### Positional Argument Routing
```bash
python3 gate.py diff                 # View diff & check test file safety
python3 gate.py blast                # Run neighbor tests on touched files
python3 gate.py status               # Check patch readiness before submitting
python3 gate.py fastapi/routing.py   # Run neighbor tests for target file
```

### Forgiving Flags & Timeout Tuning
```bash
python3 gate.py -d                   # Short flag for diff
python3 gate.py -s                   # Short flag for status
python3 gate.py -b -t 30             # Blast with 30s timeout per test file
python3 gate.py status --json        # Machine-readable JSON output
```

## Guarantees
- **Always Safe**: Read-only, never mutates files, and always exits with code 0.
- **Context-Safe**: Tracebacks and diffs are capped (<500 lines / <50KB) to prevent LLM context blowout.
- **Actionable Diagnostics**: Emits exact failing test names, line numbers, statements, and revert commands.
`````

## File: submission/agent.yaml
`````yaml
name: main
model: gemma-4-31b-it-qat-w4a16-ct
adapter: main_lora
instruction: !include prompts/main.md
tools:
  - read_file
  - edit_file
  - write_file
  - get_status
  - submit_patch
skills:
  - skills/code-map
  - skills/fast-grep
  - skills/code-oracle
  - skills/repro-check
  - skills/test-gate
generate_content_config: !include configs/sampling.yaml
`````

## File: submission/eval_config.yaml
`````yaml
# Optional participant evaluation configuration for Stage 1 inference.
evaluation:
  timeout_seconds: 60
  max_tool_calls: 40
  max_time_minutes: 4.5
  max_turns: 100
`````

## File: CANARY_ANALYSIS_REPORT.md
`````markdown
# SWE-Gemma 4 Developer Agent — Canary Evaluation & Performance Analysis Report

**Document ID:** CANARY-EVAL-REPORT-20261003  
**Target Submission:** Track 1 (Rank-8 LoRA Baseline + 5 Hardened Skills)  
**Execution Environment:** Kaggle Cloud Infrastructure (4x NVIDIA L4 24GB GPUs)  
**Kernel Slug:** `francisclyap/gemma4-canary-eval`  
**Report Date:** October 3, 2026  
**Artifact Directory:** `/Users/yapilymm/Downloads/projects/gemma4-dev/cloud_results/canary_test_results`

---

## Executive Summary

This report establishes the forensic performance analysis of the SWE-Gemma 4 Developer Agent following the completion of the cloud canary evaluation (`francisclyap/gemma4-canary-eval`) on Kaggle GPU infrastructure.

The canary evaluation conclusively resolves the central architectural question: **The 0.03 Leaderboard score from October 1 was entirely an infrastructure and sampling configuration crash, not corrupt adapter weights.** In this evaluation, the agent ran smoothly with zero platform crashes, executed 37 multi-turn steps, modified source code, and submitted a patch.

However, forensic traces revealed two mechanical failure loops—a **JSON argument syntax splice** in `fastapi_14479` and **repetitive probe thrashing** in `requests_7205`—that prevented task resolution. Both failure modes are completely remediable via prompt governor hardening without requiring retraining before the Track 1 quota window resets tonight.

---

## 1. Objective of This Submission

The primary objective of this submission pipeline is to **achieve and restore the 43.41% resolution rate (56/129 tasks resolved in benchmark run_B39)** on the official Kaggle competition leaderboard.

### Key Milestones:
* **Target Metric:** Resolution Rate $\ge 43.4\%$ across unseen Python repositories (FastAPI, Requests, Rich, HTTPX).
* **Current Operational Gate:** Transition from local/offline verification into the live Kaggle competition environment under the strict 1-submission-per-day quota.
* **Eliminate Platform Failures:** Eliminate all bridge incompatibilities, token starvation ceilings, and unhandled tool repetition loops that depress cloud performance below the model's true empirical capability.

---

## 2. What Were We Trying to Achieve?

Following the anomalous 0.03 (1/33 tasks) score on the October 1 submission (`submission ref 56744693`), this canary run was designed to achieve three specific validation gates:

1. **Test the "Reasoning Effort" Bridge Fix:**
   * *Problem:* LiteLLM in the Kaggle runner was translating `thinking_level: 2` into `reasoning_effort: medium`, which the Gemma 4 C++ bridge rejected with `RuntimeError: unsupported reasoning_effort in Gemma bridge`.
   * *Objective:* Validate that omitting `thinking_level` completely from `configs/sampling.yaml` allows Gemma 4 to run natively via LiteLLM without triggering bridge crashes.

2. **Validate Input Context Restoration:**
   * *Problem:* The prior configuration set `max_output_tokens: 16384`, which consumed 50% of the entire 32,768-token Gemma 4 context budget for output generation alone, starving prompt history down to 16K tokens.
   * *Objective:* Validate that setting `max_output_tokens: 4096` successfully restores **28,672 tokens of input context**, preventing premature context compaction and truncation.

3. **Verify Pure Cloud Tool-Calling on Remote L4 GPUs:**
   * *Problem:* Local evaluation (`./start.sh`) runs inside local development containers where host system dependencies might mask isolation bugs.
   * *Objective:* Run a clean 2-task cloud canary (`fastapi_14479` and `requests_7205`) directly on Kaggle 4x L4 GPUs to obtain ground-truth execution traces and verify tool dispatch.

---

## 3. What Did We Observe? (Empirical Evidence & Forensic Traces)

The downloaded results (`task_results.jsonl`, `gemma4-canary-eval.log`, and ATIF traces) provide definitive empirical evidence:

| Task ID | Repository | Result | Test Exit Code | Tool Calls | Duration | Patch Length |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `requests_7205` | psf/requests | **Unresolved** | 1 | 30 | 170.96s | 503 chars |
| `fastapi_14479` | fastapi/fastapi | **Unresolved** | -1 | 0 | 84.38s | 0 chars |

### Positive Verification Observations:
1. **Zero Infrastructure Crashes:** vLLM started cleanly on 4x L4 GPUs, model weights (`main_lora`) loaded properly, and no LiteLLM bridge rejections occurred.
2. **Context Window Stability:** Prompt tokens scaled up to 12,228 tokens in `requests_7205` without triggering compaction errors or memory faults.
3. **End-to-End Task Lifecycle:** In `requests_7205`, the agent ran 37 steps, edited `src/requests/utils.py`, and invoked `submit_patch()`, proving that the submission package structure, skills, and patch generation pipeline are functional.

---

### Root Cause Analysis of Task Failures:

#### Failure Mode A: JSON Delimiter Corruption & Unrecovered Loop (`fastapi_14479`)
* **Observation:** In `trace_fastapi_14479.json`, Step 4 shows the agent attempting to invoke `fast-grep` via `run_skill_script`:
  ```json
  "arguments": {
    "args": ["analyze_param"],
    "file_path": "grep.py`,skill_name:"
  }
  ```
* **Mechanism:** In `prompts/main.md`, skills were documented using Python backtick syntax:
  ``Invoke via: run_skill_script(skill_name="fast-grep", file_path="grep.py", args=["<pattern>"])``
  The INT4 quantized Gemma 4 model misconstrued the backticks and spliced the argument keys together.
* **The Lock-In:** The harness returned:
  `{"error": "Argument 'skill_name' is required.", "error_code": "INVALID_ARGUMENTS"}`
  Because `prompts/main.md` lacked an explicit *Argument Syntax Recovery Rule*, the agent repeated this **identical malformed JSON call 40 times consecutively** until it hit the turn budget ceiling with 0 tool calls executed.

#### Failure Mode B: Repetitive Probe Thrashing (`requests_7205`)
* **Observation:** In `trace_requests_7205.json`, the agent wrote a test script in `repro-check` at Step 13:
  ```python
  from requests.utils import get_netrc_auth
  import os
  open('/tmp/netrc', 'w').write('machine example.com login\n')
  os.environ['NETRC'] = '/tmp/netrc'
  print(f'Result: {get_netrc_auth("http://example.com")}')
  ```
  `repro-check` responded:
  `Code executed cleanly (exit code 0), but contained NO assertions or test functions.`
* **Mechanism:** The model did not recognize that it needed an `assert` statement to turn the probe into a test. Instead, it re-sent the **exact same Python probe 21 times consecutively** (Steps 14 through 34).
* **Consequence:** The agent burned 21 out of its 30 allowed tool calls on an unvarying string. When it finally issued `edit_file` on `src/requests/utils.py` at Step 35, the harness reported:
  `Tool call budget exhausted (30 calls). You must submit now.`
  The agent was forced to call `submit_patch()` immediately without running verification.

---

## 4. How Far Are We from Our Goal?

### Gap Assessment:
* **Target Baseline:** 43.41% (56/129 tasks).
* **Current Live Leaderboard:** 0.03 (1/33 tasks, blocked by Oct 1 LiteLLM crash).
* **Canary Run:** 0.00 (0/2 tasks, blocked by prompt syntax splicing and probe repetition).

### Reality Check:
The distance between our current state and the 43.4% goal is **narrow and mechanical, not architectural**:
1. **The weights and agent architecture are sound:** In `requests_7205`, the agent correctly located `src/requests/utils.py`, understood the `netrc` bug context, and modified the correct conditional block (`if _netrc and any(_netrc):`).
2. **The failure is tool protocol adherence:** The agent lost 100% of its budget in both tasks to unconstrained repetition loops (40 turns in FastAPI, 21 turns in Requests).
3. **No Retraining Required for Track 1:** Fixing these two failure modes does not require days of GPU retraining. It requires strict prompt governance:
   - Converting skill examples from Python syntax to clean JSON envelopes.
   - Enforcing an anti-thrashing circuit breaker that forbids repeating identical payloads.

---

## 5. Immediate and Interim Action Plan (Next 7 Days)

### Phase 1: Immediate Actions (Next 16 Hours — Before 00:00:00 UTC Quota Reset)

| Step | Action Item | Description | Target File / Area |
| :---: | :--- | :--- | :--- |
| **1.1** | **Hardened JSON Prompt Schema** | Replace all Python-style backtick documentation in `prompts/main.md` with explicit, unambiguous JSON schemas to eliminate key splicing. | `my_submission/prompts/main.md` |
| **1.2** | **Anti-Thrashing Circuit Breaker** | Implement strict prompt directives: <br>• **Zero-Repetition Rule:** Strictly forbid identical payloads.<br>• **Syntax Error Recovery:** If `INVALID_ARGUMENTS` occurs, reformat or immediately abort to `read_file`.<br>• **2-Probe Hard Cap:** Limit `repro-check` to 2 attempts max, then force transition to code inspection. | `my_submission/prompts/main.md` |
| **1.3** | **Repackage `submission.zip`** | Recompile and verify `submission.zip` (<3 GiB, 0 bytecode, validated sha256 checksum). | `submission.zip` |
| **1.4** | **Track 1 Leaderboard Submission** | Submit the verified archive to the Kaggle Leaderboard immediately when the quota resets at **00:00:00 UTC**. | Kaggle Competition CLI |

---

### Phase 2: Interim Actions (Days 2 to 7 — Track 2 LoRA Fine-Tuning)

Kaggle's weekly **30-hour GPU quota refreshed today, October 3**. This provides dedicated compute to upgrade from Track 1 (prompt-guided baseline) to Track 2 (fine-tuned multi-turn trajectory LoRA).

| Step | Milestone | Execution Protocol | Gate Criteria |
| :---: | :--- | :--- | :--- |
| **2.1** | **Deploy Unsloth LoRA Training** | Launch `kaggle_unsloth/train_gemma4_lora_minimal.ipynb` on Kaggle L4 GPU using Unsloth 4-bit QLoRA. | • Sequence length: 6144<br>• `lora_dropout: 0`<br>• Target modules: `q, k, v, o_proj`<br>• Loss convergence < 1.1 |
| **2.2** | **Weight Extraction & Packaging** | Extract `adapter_model.safetensors` (~69 MB) and place in `my_submission/adapters/main_lora/`. | Size < 100 MB, clean safetensors header |
| **2.3** | **Gauntlet 14-Task Evaluation** | Run canary evaluation against the 14-task Gauntlet suite to verify trajectory compliance. | Zero probe thrashing loops; tool transitions automated in weights |
| **2.4** | **Track 2 Leaderboard Deployment** | Deploy new LoRA adapter to Kaggle Leaderboard once resolution rate meets or exceeds the 43.4% baseline. | Resolution Rate $\ge 43.41\%$ |

---

## Conclusion & Next Step

The canary evaluation accomplished its primary mission: proving that our 4x L4 deployment stack, LiteLLM bridge configuration, and Rank-8 adapter are fully operational on Kaggle cloud compute.

By implementing the prompt governor circuit breakers, we eliminate the two known repetition traps and establish a clean, verified candidate for tonight's 00:00:00 UTC leaderboard submission.
`````
