#!/usr/bin/env python3
"""Shared SFT trajectory filter, tool translation, and quality gate module for Track 2 Gemma 4.

Exports:
- Constants: MAX_DIFF_LINES, MAX_CLEAN_CALLS, MAX_NEGATIVE_CALLS, MAX_TOTAL_TOOL_CALLS,
             MAX_OBSERVATION_CHARS, SYSTEM_PROMPT, TOOLS_SCHEMA
- Benchmark isolation: load_benchmark_exclusion_set
- Patch qualification: is_single_file_py_patch
- Workspace normalization: normalize_workspace_path, sanitize_text, compact_observation
- Tool translation: translate_tool_call
- Quality classifier: classify_trajectory_steps
"""

import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

# Core thresholds
MAX_DIFF_LINES: int = 150
MAX_CLEAN_CALLS: int = 20
MAX_NEGATIVE_CALLS: int = 20
MAX_TOTAL_TOOL_CALLS: int = 40
MAX_OBSERVATION_CHARS: int = 800

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
TASKS_BENCHMARK_PATH: Path = ROOT_DIR / "tasks.jsonl"

VALID_SKILLS: Set[str] = {
    "fast-grep",
    "code-map",
    "code-oracle",
    "repro-check",
    "test-gate",
}

SYSTEM_PROMPT: str = (
    "You are the Autonomous Software Developer fixing Python defects in /workspace.\n"
    "STRICT TOOLSET & SKILL INVOCATION CONTRACT:\n"
    "1. Direct tools: read_file, edit_file, write_file, get_status, submit_patch.\n"
    "2. Pre-installed skills (invoke EXCLUSIVELY via run_skill_script with skill_name, file_path, args):\n"
    "   - fast-grep: file_path='grep.py', args=['<pattern>'] or ['<pattern>', '<path>']\n"
    "   - code-map: file_path='map.py', args=['--symbol', '<symbol>'] or ['--file', '<path>']\n"
    "   - code-oracle: file_path='oracle.py', args=['--eval', '<expr>'] or ['--syntax', '<file>']\n"
    "   - repro-check: file_path='check.py', args=['assert <condition>']\n"
    "   - test-gate: file_path='gate.py', args=[] or ['--diff'] or ['--status']\n"
    "3. ABSOLUTELY FORBIDDEN: NEVER call run_command, load_skill, list_skills, or write scratch scripts in /workspace.\n"
    "4. Workflow: localize defect with fast-grep/code-map, inspect with read_file, apply surgical edits via edit_file, "
    "verify with repro-check/code-oracle/test-gate, and finalize with submit_patch."
)

SCRATCH_FILE_RE = re.compile(
    r"(?:^|/)(?:repro[^/]*|reproduce[^/]*|test_[^/]*|[^/]*_test|verify[^/]*|check_[^/]*|debug[^/]*|bug[^/]*|poc[^/]*|tmp[^/]*|temp[^/]*|scratch[^/]*|issue[^/]*)\.py$",
    re.IGNORECASE,
)


def _is_scratch_or_repro_path(path: str) -> bool:
    """Returns True if path is a temporary reproduction, test, or scratch script."""
    norm = normalize_workspace_path(path)
    if not norm:
        return False
    if norm.startswith("tests/") or "/tests/" in f"/{norm}":
        return True
    return bool(SCRATCH_FILE_RE.search(norm))

TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads contents of a file within /workspace with optional line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Relative path to file in /workspace."},
                    "start_line": {"type": "integer", "description": "Optional starting line (1-indexed)."},
                    "end_line": {"type": "integer", "description": "Optional ending line (inclusive)."},
                },
                "required": ["filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Applies surgical text replacement to an existing file in /workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Relative path to file in /workspace."},
                    "old_string": {"type": "string", "description": "Exact text block to replace."},
                    "new_string": {"type": "string", "description": "Replacement text block."},
                    "allow_multiple": {"type": "boolean", "description": "Whether to allow multiple occurrences."},
                },
                "required": ["filepath", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes or overwrites an entire file in /workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Relative path to file in /workspace."},
                    "content": {"type": "string", "description": "Full file content to write."},
                },
                "required": ["filepath", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "Free tool returning current workspace git status and remaining budget.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_patch",
            "description": "Submits final patch and terminates evaluation task immediately.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_skill_script",
            "description": "Executes one of the 5 pre-installed skills (fast-grep, code-map, code-oracle, repro-check, test-gate).",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string", "description": "Name of skill directory."},
                    "file_path": {"type": "string", "description": "Script file inside skill (e.g. grep.py, map.py, oracle.py, check.py, gate.py)."},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Command-line arguments passed to script."},
                },
                "required": ["skill_name", "file_path", "args"],
            },
        },
    },
]


def load_benchmark_exclusion_set(tasks_path: Optional[Union[str, Path]] = None) -> Set[str]:
    """Loads all 129 benchmark instance IDs from tasks.jsonl to guarantee zero train leakage."""
    target_path = Path(tasks_path) if tasks_path is not None else TASKS_BENCHMARK_PATH
    if not target_path.exists():
        logger.warning("Benchmark tasks file not found at %s", target_path)
        return set()
    exclusion: Set[str] = set()
    with open(target_path, encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                try:
                    exclusion.add(json.loads(line_str)["instance_id"])
                except Exception:
                    pass
    logger.info("Loaded %d benchmark task IDs to strictly exclude from SFT data.", len(exclusion))
    return exclusion


def normalize_workspace_path(path: str) -> str:
    """Strips container sandbox and repo roots to clean relative workspace paths."""
    if not path:
        return ""
    p = str(path).strip()
    p = re.sub(r"^/?testbed/", "", p)
    p = re.sub(r"^/?workspace/[^/]+/", "", p)
    p = re.sub(r"^/?workspace/", "", p)
    p = re.sub(r"^/?[a-zA-Z0-9_\-]+__[^/]+/", "", p)
    return p.lstrip("/")


def sanitize_text(text: Any) -> str:
    """Removes environment artifacts and handles list/dict content blocks."""
    if not text:
        return ""
    if isinstance(text, list):
        parts = []
        for item in text:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        text = "\n".join(parts)
    elif isinstance(text, dict):
        text = str(text.get("text") or text.get("content") or json.dumps(text))
    elif not isinstance(text, str):
        text = str(text)
    text = re.sub(r"/testbed/?", "/workspace/", text)
    text = re.sub(r"/workspace/[^/]+__[^/]+/", "/workspace/", text)
    text = re.sub(r"/(?:private/)?var/folders/[^\s\"'\\]+", "/tmp", text)
    return text.strip()


def compact_observation(raw_obs: Any) -> str:
    """Compacts tool observations to fit context window."""
    if isinstance(raw_obs, dict):
        text = str(raw_obs.get("stdout") or raw_obs.get("content") or json.dumps(raw_obs))
    else:
        text = str(raw_obs or "")
    text = sanitize_text(text)
    if len(text) <= MAX_OBSERVATION_CHARS:
        return text
    half = MAX_OBSERVATION_CHARS // 2 - 20
    return text[:half] + "\n... [truncated] ...\n" + text[-half:]


def is_single_file_py_patch(patch: str) -> bool:
    """Extracts all modified file paths from a patch, discards /dev/null,

    and returns True iff len(files) == 1 and the single file ends with .py
    (100% single-file .py, 0% multi-file, 0% non-.py).
    """
    if not patch or not isinstance(patch, str):
        return False

    files: Set[str] = set()
    for raw_line in patch.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Format 1: diff --git a/<path1> b/<path2>
        if line.startswith("diff --git"):
            m = re.match(r"^diff --git\s+(?:\"?a/)?(.+?)\"?\s+(?:\"?b/)?(.+?)\"?$", line)
            if m:
                p1, p2 = m.group(1).strip().strip('"'), m.group(2).strip().strip('"')
                for p in (p1, p2):
                    if p and p != "/dev/null":
                        norm = normalize_workspace_path(p)
                        if norm:
                            files.add(norm)
            continue

        # Format 2: --- a/<path> or --- /dev/null
        if line.startswith("--- "):
            target = line[4:].strip()
            target = re.split(r"[\t\s]+", target)[0].strip('"')
            if target.startswith("a/"):
                target = target[2:]
            if target and target != "/dev/null":
                norm = normalize_workspace_path(target)
                if norm:
                    files.add(norm)
            continue

        # Format 3: +++ b/<path> or +++ /dev/null
        if line.startswith("+++ "):
            target = line[4:].strip()
            target = re.split(r"[\t\s]+", target)[0].strip('"')
            if target.startswith("b/"):
                target = target[2:]
            if target and target != "/dev/null":
                norm = normalize_workspace_path(target)
                if norm:
                    files.add(norm)
            continue

    files.discard("/dev/null")
    files.discard("")
    if len(files) == 1:
        single_file = next(iter(files))
        return single_file.endswith(".py")
    return False


def translate_tool_call(
    fn_name: str,
    raw_args: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Translates external OpenHands/Claude tool calls into the strict 6-tool contract

    (read_file, edit_file, write_file, get_status, submit_patch, run_skill_script).
    Excludes run_command completely.
    Supports 5 skills: fast-grep, code-map, code-oracle, repro-check, test-gate.
    """
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except Exception:
            raw_args = {}
    if not isinstance(raw_args, dict):
        raw_args = {}

    name = str(fn_name or "").strip()

    # 1. Direct tools
    if name == "read_file":
        fp = normalize_workspace_path(raw_args.get("filepath") or raw_args.get("file_path", ""))
        if not fp:
            return None
        args: Dict[str, Any] = {"filepath": fp}
        if raw_args.get("start_line") is not None:
            try:
                args["start_line"] = int(raw_args["start_line"])
            except (ValueError, TypeError):
                pass
        if raw_args.get("end_line") is not None:
            try:
                args["end_line"] = int(raw_args["end_line"])
            except (ValueError, TypeError):
                pass
        return {"name": "read_file", "arguments": args}

    if name == "edit_file":
        fp = normalize_workspace_path(raw_args.get("filepath") or raw_args.get("file_path", ""))
        old_s = raw_args.get("old_string") if "old_string" in raw_args else raw_args.get("old_text", "")
        new_s = raw_args.get("new_string") if "new_string" in raw_args else raw_args.get("new_text", "")
        if not fp or not old_s:
            return None
        return {
            "name": "edit_file",
            "arguments": {
                "filepath": fp,
                "old_string": old_s,
                "new_string": new_s,
                "allow_multiple": bool(raw_args.get("allow_multiple", False)),
            },
        }

    if name == "write_file":
        fp = normalize_workspace_path(raw_args.get("filepath") or raw_args.get("file_path", ""))
        content = raw_args.get("content") if "content" in raw_args else raw_args.get("file_text", "")
        if not fp:
            return None
        if context is not None and "repro_files" in context:
            context["repro_files"][fp] = str(content)
            context["repro_files"][Path(fp).name] = str(content)
        if _is_scratch_or_repro_path(fp):
            return None
        return {"name": "write_file", "arguments": {"filepath": fp, "content": str(content)}}
    if name in ("submit_patch", "finish", "submit"):
        return {"name": "submit_patch", "arguments": {}}

    if name == "get_status":
        return {"name": "get_status", "arguments": {}}

    if name == "run_skill_script":
        skill = str(raw_args.get("skill_name", "")).strip()
        fp = str(raw_args.get("file_path", "")).strip()
        args_list = raw_args.get("args", [])
        if not skill or not fp or skill not in VALID_SKILLS:
            return None
        if not isinstance(args_list, list):
            args_list = [str(args_list)]
        return {
            "name": "run_skill_script",
            "arguments": {
                "skill_name": skill,
                "file_path": fp,
                "args": [str(a) for a in args_list],
            },
        }

    # 2. OpenHands str_replace_editor mapping
    if name in ("str_replace_editor", "editor"):
        cmd = str(raw_args.get("command", "")).strip()
        path = normalize_workspace_path(raw_args.get("path") or raw_args.get("filepath") or raw_args.get("file_path", ""))
        if cmd == "view":
            if not path:
                return None
            # Check if viewing a directory / package root -> map to code-map --file
            vr = raw_args.get("view_range") or []
            has_extension = bool(Path(path).suffix)
            if not has_extension and not vr:
                return {
                    "name": "run_skill_script",
                    "arguments": {
                        "skill_name": "code-map",
                        "file_path": "map.py",
                        "args": ["--file", path],
                    },
                }
            read_args: Dict[str, Any] = {"filepath": path}
            if isinstance(vr, list):
                if len(vr) > 0 and vr[0] is not None:
                    try:
                        read_args["start_line"] = int(vr[0])
                    except (ValueError, TypeError):
                        pass
                if len(vr) > 1 and vr[1] is not None:
                    try:
                        read_args["end_line"] = int(vr[1])
                    except (ValueError, TypeError):
                        pass
            return {"name": "read_file", "arguments": read_args}
        if cmd == "str_replace":
            old_s = raw_args.get("old_str") if "old_str" in raw_args else raw_args.get("old_string", "")
            new_s = raw_args.get("new_str") if "new_str" in raw_args else raw_args.get("new_string", "")
            if not path or not old_s:
                return None
            return {
                "name": "edit_file",
                "arguments": {
                    "filepath": path,
                    "old_string": old_s,
                    "new_string": new_s,
                    "allow_multiple": False,
                },
            }

        if cmd == "create":
            if not path:
                return None
            content = raw_args.get("file_text") if "file_text" in raw_args else raw_args.get("content", "")
            if context is not None and "repro_files" in context:
                context["repro_files"][path] = str(content)
                context["repro_files"][Path(path).name] = str(content)
            if _is_scratch_or_repro_path(path):
                return None
            return {"name": "write_file", "arguments": {"filepath": path, "content": str(content)}}
    # 3. OpenHands / Claude bash commands mapped to skills (ZERO run_command)
    if name in ("execute_bash", "bash", "execute_command", "cmd"):
        cmd_str = str(raw_args.get("command") or raw_args.get("cmd") or "").strip()
        if not cmd_str:
            return None

        # Drop file cleanup / git reset commands
        if cmd_str.startswith(("rm ", "git checkout", "git clean", "git reset")):
            return None

        # 1. Regression / test execution -> test-gate
        if any(kw in cmd_str for kw in ("pytest", "python -m unittest", "python -m pytest", "tox")):
            return {
                "name": "run_skill_script",
                "arguments": {"skill_name": "test-gate", "file_path": "gate.py", "args": []},
            }

        # 2. Git diff -> test-gate --diff, Git status -> get_status
        if "git diff" in cmd_str:
            return {
                "name": "run_skill_script",
                "arguments": {"skill_name": "test-gate", "file_path": "gate.py", "args": ["--diff"]},
            }
        if "git status" in cmd_str:
            return {"name": "get_status", "arguments": {}}

        # 3. Python syntax check -> code-oracle --syntax
        if "py_compile" in cmd_str:
            parts = cmd_str.split()
            target_f = normalize_workspace_path(parts[-1]) if parts else ""
            return {
                "name": "run_skill_script",
                "arguments": {"skill_name": "code-oracle", "file_path": "oracle.py", "args": ["--syntax", target_f]},
            }

        # 4. Inline Python reproduction vs expression evaluation (before grep/rg!)
        m_py_c = re.search(r"python(?:3)?\s+-c\s+(.+)$", cmd_str, re.DOTALL)
        if m_py_c:
            expr = m_py_c.group(1).strip().strip("'\"")
            if "assert" in expr:
                return {
                    "name": "run_skill_script",
                    "arguments": {"skill_name": "repro-check", "file_path": "check.py", "args": [expr]},
                }
            else:
                return {
                    "name": "run_skill_script",
                    "arguments": {"skill_name": "code-oracle", "file_path": "oracle.py", "args": ["--eval", expr]},
                }

        # 5. Script execution reproduction -> repro-check or code-oracle (before grep/rg!)
        m_repro = re.search(r"python(?:3)?\s+(?:-[a-zA-Z0-9]+\s+)*([a-zA-Z0-9_\-\./]+\.py)\b", cmd_str)
        if m_repro:
            script_path = m_repro.group(1)
            norm_script = normalize_workspace_path(script_path)
            script_name = Path(script_path).name
            repro_content = ""
            if context and "repro_files" in context:
                repro_content = (
                    context["repro_files"].get(norm_script)
                    or context["repro_files"].get(script_path)
                    or context["repro_files"].get(script_name)
                    or ""
                )
            if repro_content:
                if "assert" in repro_content or "AssertionError" in repro_content:
                    if "assert " not in repro_content:
                        repro_content = repro_content.rstrip() + "\nassert True"
                    return {
                        "name": "run_skill_script",
                        "arguments": {"skill_name": "repro-check", "file_path": "check.py", "args": [repro_content]},
                    }
                else:
                    return {
                        "name": "run_skill_script",
                        "arguments": {
                            "skill_name": "code-oracle",
                            "file_path": "oracle.py",
                            "args": ["--eval", repro_content],
                        },
                    }
            return None

        # 6. File / Directory exploration -> code-map --file
        if cmd_str.startswith("find ") and ("-name" in cmd_str or "-type" in cmd_str):
            find_parts = cmd_str.split()
            base_dir = "."
            for p in find_parts[1:]:
                if not p.startswith("-"):
                    base_dir = normalize_workspace_path(p)
                    break
            return {
                "name": "run_skill_script",
                "arguments": {"skill_name": "code-map", "file_path": "map.py", "args": ["--file", base_dir or "."]},
            }
        if cmd_str.startswith("ls ") or cmd_str == "ls":
            parts = cmd_str.split()
            target_dir = parts[-1] if len(parts) > 1 and not parts[-1].startswith("-") else "."
            target_dir = normalize_workspace_path(target_dir) or "."
            return {
                "name": "run_skill_script",
                "arguments": {"skill_name": "code-map", "file_path": "map.py", "args": ["--file", target_dir]},
            }

        # 7. Grep / Ripgrep -> code-map --symbol (for class/def) or fast-grep
        if any(kw in cmd_str for kw in ("grep", "rg ")):
            m_sym = re.search(r"(?:class|def)\s+([a-zA-Z0-9_]+)", cmd_str)
            if m_sym:
                sym = m_sym.group(1)
                return {
                    "name": "run_skill_script",
                    "arguments": {"skill_name": "code-map", "file_path": "map.py", "args": ["--symbol", sym]},
                }

            m_quote = re.search(r'["\']([^"\']+)["\']', cmd_str)
            if m_quote:
                pattern = m_quote.group(1).strip()
                remainder = cmd_str[m_quote.end() :].strip().split()
                target_path = (
                    normalize_workspace_path(remainder[0])
                    if remainder and not remainder[0].startswith("-")
                    else ""
                )
            else:
                tokens = [
                    tok
                    for tok in cmd_str.split()
                    if not tok.startswith("-") and tok not in ("grep", "rg", "xargs")
                ]
                if not tokens:
                    return None
                pattern = tokens[0]
                target_path = normalize_workspace_path(tokens[1]) if len(tokens) > 1 else ""

            if not pattern or len(pattern) < 2:
                return None

            grep_args = [pattern, target_path] if target_path else [pattern]
            return {
                "name": "run_skill_script",
                "arguments": {"skill_name": "fast-grep", "file_path": "grep.py", "args": grep_args},
            }

        return None

def _extract_tc_info(tc: Any) -> Tuple[str, Dict[str, Any]]:
    """Extracts function name and argument dictionary from various tool_call shapes."""
    if not isinstance(tc, dict):
        return "", {}
    if "function" in tc and isinstance(tc["function"], dict):
        fn = tc["function"]
        name = fn.get("name", "")
        args = fn.get("arguments", {})
    else:
        name = tc.get("name", "")
        args = tc.get("arguments", {})

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    return str(name or ""), args if isinstance(args, dict) else {}


def classify_trajectory_steps(steps: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, int]]:
    """Evaluates a list of alternating assistant and tool messages.

    Counts clean_calls, type_a_neg_calls, and type_b_dumb_calls.
    Rejects trajectories immediately if type_b_dumb_calls > 0.
    Enforces dual budget:
      0 < clean_calls < 20
      type_a_neg_calls < 20
      (clean_calls + type_a_neg_calls) < 40
      final step in trajectory has an edit or submit action.

    Returns:
      (is_valid, stats)
    """
    clean_calls: int = 0
    type_a_neg_calls: int = 0
    type_b_dumb_calls: int = 0
    total_tool_calls: int = 0

    if not steps or not isinstance(steps, list):
        return False, {
            "clean_calls": 0,
            "type_a_neg_calls": 0,
            "type_b_dumb_calls": 0,
            "total_tool_calls": 0,
        }

    prev_turn_signatures: Optional[Tuple[Tuple[str, str], ...]] = None
    last_assistant_turn_tool_names: List[str] = []

    for idx, msg in enumerate(steps):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue

        raw_tcs = msg.get("tool_calls") or []
        if not raw_tcs:
            continue

        current_turn_tcs: List[Tuple[str, Dict[str, Any]]] = []

        # Find following tool observations
        obs_parts: List[str] = []
        lookahead = idx + 1
        while lookahead < len(steps) and isinstance(steps[lookahead], dict) and steps[lookahead].get("role") == "tool":
            obs_parts.append(str(steps[lookahead].get("content") or ""))
            lookahead += 1
        obs_content = "\n".join(obs_parts)

        turn_signatures: List[Tuple[str, str]] = []

        for tc in raw_tcs:
            fn_name, raw_args = _extract_tc_info(tc)
            if not fn_name:
                continue

            # Standardize to 6-tool schema
            translated = translate_tool_call(fn_name, raw_args)
            if translated:
                eff_name = translated["name"]
                eff_args = translated["arguments"]
            else:
                eff_name = fn_name
                eff_args = raw_args

            total_tool_calls += 1
            current_turn_tcs.append((eff_name, eff_args))
            sig = (eff_name, json.dumps(eff_args, sort_keys=True))
            turn_signatures.append(sig)

            # Check Type B Dumb Negatives
            is_type_b = False

            # Type B (a): edit_file followed by error/mismatch indicators
            if eff_name == "edit_file":
                edit_errors = [
                    "Error", "not found", "No match", "no match",
                    "did not match", "Failed", "SyntaxError", "old_str"
                ]
                if any(err in obs_content for err in edit_errors):
                    type_b_dumb_calls += 1
                    is_type_b = True

            # Type B (b): read_file followed by file/directory not found indicators
            if not is_type_b and eff_name == "read_file":
                read_errors = [
                    "FileNotFoundError", "No such file", "does not exist", "IsADirectoryError"
                ]
                if any(err in obs_content for err in read_errors):
                    type_b_dumb_calls += 1
                    is_type_b = True

            if is_type_b:
                continue

            # Check Type A Endgame-Pivoting Negatives
            is_type_a = False

            if eff_name == "run_skill_script":
                skill = eff_args.get("skill_name", "")
                # Type A (a): repro-check or test-gate returning Red-to-Green defect repro
                if skill in ("repro-check", "test-gate"):
                    piv_indicators = ["Traceback", "AssertionError", "FAILED", "Error"]
                    if any(piv in obs_content for piv in piv_indicators):
                        type_a_neg_calls += 1
                        is_type_a = True
                # Type A (b): fast-grep or code-map hypothesis-disconfirming probe
                elif skill in ("fast-grep", "code-map"):
                    piv_indicators = ["No matches", "0 matches"]
                    if any(piv in obs_content for piv in piv_indicators):
                        type_a_neg_calls += 1
                        is_type_a = True

            if is_type_a:
                continue

            # Clean call
            clean_calls += 1

        # Check Type B (c): repeated identical tool call on consecutive assistant turns (blind thrashing)
        tuple_turn_sigs = tuple(turn_signatures)
        if prev_turn_signatures is not None and tuple_turn_sigs == prev_turn_signatures and tuple_turn_sigs:
            type_b_dumb_calls += 1
        prev_turn_signatures = tuple_turn_sigs

        if current_turn_tcs:
            last_assistant_turn_tool_names = [t[0] for t in current_turn_tcs]

    final_has_edit_or_submit = any(
        name in ("submit_patch", "edit_file", "write_file", "submit", "finish")
        for name in last_assistant_turn_tool_names
    )

    is_valid = (
        type_b_dumb_calls == 0
        and 0 < clean_calls < MAX_CLEAN_CALLS
        and type_a_neg_calls < MAX_NEGATIVE_CALLS
        and (clean_calls + type_a_neg_calls) < MAX_TOTAL_TOOL_CALLS
        and final_has_edit_or_submit
    )

    stats: Dict[str, int] = {
        "clean_calls": clean_calls,
        "type_a_neg_calls": type_a_neg_calls,
        "type_b_dumb_calls": type_b_dumb_calls,
        "total_tool_calls": total_tool_calls,
    }
    return is_valid, stats


__all__ = [
    "MAX_DIFF_LINES",
    "MAX_CLEAN_CALLS",
    "MAX_NEGATIVE_CALLS",
    "MAX_TOTAL_TOOL_CALLS",
    "MAX_OBSERVATION_CHARS",
    "SYSTEM_PROMPT",
    "TOOLS_SCHEMA",
    "load_benchmark_exclusion_set",
    "is_single_file_py_patch",
    "normalize_workspace_path",
    "sanitize_text",
    "compact_observation",
    "translate_tool_call",
    "classify_trajectory_steps",
]
