#!/usr/bin/env python3
"""
scripts/baseline_gate.py

Deterministic baseline whitelist and exception gate tool.
Enforces that modifications to the verified baseline (Track 1 live)
are explicitly approved before submission to Kaggle Leaderboard or Compute.

Modes:
  leaderboard: Strictly allows ONLY files matching the baseline whitelist.
               Any unapproved change or un-promoted exception causes exit 1.
  compute:     Allows files matching the baseline whitelist OR registered
               exceptions in configs/baseline_registry.json.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple


IGNORED_NAMES = {".DS_Store", "__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def sha256_file(path: Path) -> str:
    """Compute hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def collect_source_files(source_dir: Path) -> Dict[str, str]:
    """
    Recursively scan source_dir for regular files, ignoring cache/system files.
    Returns mapping of posix relative path -> sha256 hex digest.
    """
    if not source_dir.is_dir():
        return {}

    files: Dict[str, str] = {}
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORED_NAMES for part in path.parts):
            continue
        if path.suffix in IGNORED_SUFFIXES or path.name in IGNORED_NAMES:
            continue
        rel_posix = path.relative_to(source_dir).as_posix()
        files[rel_posix] = sha256_file(path)
    return files


def load_registry(registry_path: Path) -> Dict[str, Any]:
    """Load JSON registry from path."""
    if not registry_path.is_file():
        raise FileNotFoundError(f"Baseline registry not found: {registry_path}")
    with registry_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry_path: Path, data: Dict[str, Any]) -> None:
    """Save JSON registry with formatting."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)
        f.write("\n")


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize or re-hash baseline whitelist registry."""
    source_dir = Path(args.source)
    if not source_dir.is_dir():
        print(f"[FAIL] Source directory does not exist: {source_dir}", file=sys.stderr)
        return 1

    zip_path = Path(args.zip) if args.zip else None
    zip_sha = None
    if zip_path and zip_path.is_file():
        zip_sha = sha256_file(zip_path)
    elif zip_path:
        print(f"[WARN] Zip file not found at {zip_path}; zip_sha256 set to null", file=sys.stderr)

    files = collect_source_files(source_dir)
    if not files:
        print(f"[FAIL] No files found in source directory: {source_dir}", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    existing: Dict[str, Any] = {}
    if out_path.is_file():
        try:
            existing = load_registry(out_path)
        except Exception:
            pass

    registry = {
        "baseline_ref": args.baseline_ref or existing.get("baseline_ref", "56883026"),
        "public_score": float(args.score if args.score is not None else existing.get("public_score", 0.13)),
        "locked_at": args.locked_at or existing.get("locked_at", "2026-10-06T14:21:38Z"),
        "zip_sha256": zip_sha or existing.get("zip_sha256"),
        "whitelist": dict(sorted(files.items())),
        "exceptions": existing.get("exceptions", {})
    }

    save_registry(out_path, registry)
    print(f"[INIT] Baseline registry created at {out_path}")
    print(f"       Baseline Ref : {registry['baseline_ref']}")
    print(f"       Public Score : {registry['public_score']}")
    print(f"       Locked At    : {registry['locked_at']}")
    print(f"       Zip SHA-256  : {registry['zip_sha256']}")
    print(f"       Files Whitelisted: {len(registry['whitelist'])}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify source files against whitelist and exceptions."""
    registry_path = Path(args.registry)
    if not registry_path.is_file():
        print(f"[FAIL] Registry file not found: {registry_path}", file=sys.stderr)
        return 1

    try:
        registry = load_registry(registry_path)
    except Exception as e:
        print(f"[FAIL] Failed to parse registry {registry_path}: {e}", file=sys.stderr)
        return 1

    source_dir = Path(args.source)
    if not source_dir.is_dir():
        print(f"[FAIL] Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    whitelist: Dict[str, str] = registry.get("whitelist", {})
    exceptions: Dict[str, Dict[str, Any]] = registry.get("exceptions", {})
    current_files = collect_source_files(source_dir)

    mode = args.mode
    print(f"=== Baseline Gate Verification [Mode: {mode.upper()}] ===")
    print(f"Registry: {registry_path} (Ref: {registry.get('baseline_ref')}, Score: {registry.get('public_score')})")
    print(f"Source  : {source_dir}\n")

    failures: List[str] = []
    passes: List[str] = []

    all_keys = sorted(set(whitelist.keys()) | set(current_files.keys()) | set(exceptions.keys()))

    for rel_path in all_keys:
        in_current = rel_path in current_files
        in_whitelist = rel_path in whitelist
        in_exceptions = rel_path in exceptions

        current_hash = current_files.get(rel_path)
        whitelist_hash = whitelist.get(rel_path)
        exception_entry = exceptions.get(rel_path)

        if mode == "leaderboard":
            # Strict mode: must be in whitelist, must match hash, no un-promoted exceptions allowed
            if not in_current and in_whitelist:
                msg = f"[FAIL] MISSING: {rel_path} (expected whitelist file is missing)"
                failures.append(msg)
                print(msg)
            elif in_current and not in_whitelist:
                if in_exceptions:
                    msg = f"[FAIL] UN-PROMOTED EXCEPTION: {rel_path} (registered exception not permitted on Leaderboard)"
                else:
                    msg = f"[FAIL] UNAPPROVED FILE: {rel_path} (extraneous file not in whitelist)"
                failures.append(msg)
                print(msg)
            elif in_current and in_whitelist:
                if in_exceptions:
                    msg = f"[FAIL] UN-PROMOTED EXCEPTION: {rel_path} (has pending exception; promote first)"
                    failures.append(msg)
                    print(msg)
                elif current_hash != whitelist_hash:
                    msg = f"[FAIL] MODIFIED: {rel_path} (sha256 mismatch against whitelist: {current_hash} != {whitelist_hash})"
                    failures.append(msg)
                    print(msg)
                else:
                    msg = f"[PASS] {rel_path} (matches whitelist)"
                    passes.append(msg)
                    print(msg)

        elif mode == "compute":
            # Compute mode: matches whitelist OR approved exception
            if in_exceptions:
                exp_hash = exception_entry.get("sha256")
                reason = exception_entry.get("reason", "N/A")
                approved_by = exception_entry.get("approved_by", "Unknown")
                if not in_current:
                    msg = f"[FAIL] MISSING EXCEPTION FILE: {rel_path} (registered exception missing on disk)"
                    failures.append(msg)
                    print(msg)
                elif current_hash != exp_hash:
                    msg = f"[FAIL] EXCEPTION MISMATCH: {rel_path} (sha256 {current_hash} != approved {exp_hash})"
                    failures.append(msg)
                    print(msg)
                else:
                    msg = f"[PASS] {rel_path} (APPROVED EXCEPTION by {approved_by}: {reason})"
                    passes.append(msg)
                    print(msg)
            elif in_whitelist:
                if not in_current:
                    msg = f"[FAIL] MISSING: {rel_path} (whitelist file is missing)"
                    failures.append(msg)
                    print(msg)
                elif current_hash != whitelist_hash:
                    msg = f"[FAIL] UNAPPROVED MODIFICATION: {rel_path} (modified without exception)"
                    failures.append(msg)
                    print(msg)
                else:
                    msg = f"[PASS] {rel_path} (matches whitelist)"
                    passes.append(msg)
                    print(msg)
            else:
                msg = f"[FAIL] UNAPPROVED FILE: {rel_path} (not in whitelist or exceptions)"
                failures.append(msg)
                print(msg)

    # Optional zip check
    if args.check_zip:
        zip_path = Path(args.zip)
        expected_zip_sha = registry.get("zip_sha256")
        if not zip_path.is_file():
            msg = f"[FAIL] ZIP MISSING: {zip_path} not found"
            failures.append(msg)
            print(msg)
        elif not expected_zip_sha:
            msg = f"[FAIL] ZIP REGISTRY MISSING: no zip_sha256 recorded in registry"
            failures.append(msg)
            print(msg)
        else:
            actual_zip_sha = sha256_file(zip_path)
            if actual_zip_sha != expected_zip_sha:
                msg = f"[FAIL] ZIP MISMATCH: {zip_path} sha256 {actual_zip_sha} != expected {expected_zip_sha}"
                failures.append(msg)
                print(msg)
            else:
                msg = f"[PASS] {zip_path} (sha256 matches baseline {actual_zip_sha})"
                passes.append(msg)
                print(msg)

    print("\n--- Summary ---")
    print(f"Passed: {len(passes)}")
    print(f"Failed: {len(failures)}")

    if failures:
        print(f"\n[VERDICT] FAIL ({len(failures)} violations detected)", file=sys.stderr)
        return 1

    print("\n[VERDICT] PASS (Baseline verified cleanly)")
    return 0


def cmd_add_exception(args: argparse.Namespace) -> int:
    """Add or update an approved exception in the registry."""
    registry_path = Path(args.registry)
    if not registry_path.is_file():
        print(f"[FAIL] Registry file not found: {registry_path}", file=sys.stderr)
        return 1

    source_dir = Path(args.source)
    target_arg = Path(args.file)

    # Resolve file path
    if target_arg.is_file():
        file_path = target_arg
        try:
            rel_path = file_path.resolve().relative_to(source_dir.resolve()).as_posix()
        except ValueError:
            rel_path = target_arg.as_posix()
    elif (source_dir / target_arg).is_file():
        file_path = source_dir / target_arg
        rel_path = target_arg.as_posix()
    else:
        print(f"[FAIL] File not found at {target_arg} or {source_dir / target_arg}", file=sys.stderr)
        return 1

    file_hash = sha256_file(file_path)

    registry = load_registry(registry_path)
    if "exceptions" not in registry:
        registry["exceptions"] = {}

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    approved_by = args.approved_by or "Francis"

    registry["exceptions"][rel_path] = {
        "sha256": file_hash,
        "reason": args.reason,
        "approved_by": approved_by,
        "created_at": created_at
    }

    save_registry(registry_path, registry)
    print(f"[EXCEPTION ADDED] {rel_path}")
    print(f"  SHA-256    : {file_hash}")
    print(f"  Reason     : {args.reason}")
    print(f"  Approved By: {approved_by}")
    print(f"  Created At : {created_at}")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    """Promote exception(s) into whitelist."""
    registry_path = Path(args.registry)
    if not registry_path.is_file():
        print(f"[FAIL] Registry file not found: {registry_path}", file=sys.stderr)
        return 1

    registry = load_registry(registry_path)
    whitelist: Dict[str, str] = registry.setdefault("whitelist", {})
    exceptions: Dict[str, Dict[str, Any]] = registry.setdefault("exceptions", {})

    if not args.all and not args.file:
        print("[FAIL] Either --file <rel_path> or --all must be specified", file=sys.stderr)
        return 1

    if args.all:
        if not exceptions:
            print("[INFO] No exceptions to promote.")
            return 0
        promoted = []
        for rel_path, entry in list(exceptions.items()):
            whitelist[rel_path] = entry["sha256"]
            promoted.append(rel_path)
            del exceptions[rel_path]
        registry["whitelist"] = dict(sorted(whitelist.items()))
        save_registry(registry_path, registry)
        print(f"[PROMOTED ALL] Promoted {len(promoted)} exception(s) to whitelist:")
        for p in promoted:
            print(f"  - {p}")
        return 0

    rel_path = Path(args.file).as_posix()
    if rel_path not in exceptions:
        print(f"[FAIL] No active exception found for '{rel_path}'", file=sys.stderr)
        return 1

    entry = exceptions[rel_path]
    whitelist[rel_path] = entry["sha256"]
    del exceptions[rel_path]
    registry["whitelist"] = dict(sorted(whitelist.items()))
    save_registry(registry_path, registry)
    print(f"[PROMOTED] {rel_path} moved to whitelist with sha256 {whitelist[rel_path]}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Print status of baseline registry."""
    registry_path = Path(args.registry)
    if not registry_path.is_file():
        print(f"[FAIL] Registry file not found: {registry_path}", file=sys.stderr)
        return 1

    registry = load_registry(registry_path)
    whitelist = registry.get("whitelist", {})
    exceptions = registry.get("exceptions", {})

    print("=== Baseline Gate Status ===")
    print(f"Baseline Ref   : {registry.get('baseline_ref')}")
    print(f"Public Score   : {registry.get('public_score')}")
    print(f"Locked At      : {registry.get('locked_at')}")
    print(f"Zip SHA-256    : {registry.get('zip_sha256')}")
    print(f"Whitelist Files: {len(whitelist)}")
    print(f"Exceptions     : {len(exceptions)}")

    if exceptions:
        print("\nActive Exceptions:")
        for path, info in sorted(exceptions.items()):
            print(f"  - {path}:")
            print(f"      SHA-256    : {info.get('sha256')}")
            print(f"      Reason     : {info.get('reason')}")
            print(f"      Approved By: {info.get('approved_by')}")
            print(f"      Created At : {info.get('created_at')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic baseline whitelist & exception gate tool"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize or re-hash baseline whitelist registry")
    p_init.add_argument("--source", default="submissions/track1_live", help="Path to source directory")
    p_init.add_argument("--zip", default="submission.zip", help="Path to submission.zip")
    p_init.add_argument("--out", default="configs/baseline_registry.json", help="Output registry JSON path")
    p_init.add_argument("--baseline-ref", default=None, help="Baseline submission ref (default: 56883026)")
    p_init.add_argument("--score", type=float, default=None, help="Public score (default: 0.13)")
    p_init.add_argument("--locked-at", default=None, help="Locked timestamp (default: 2026-10-06T14:21:38Z)")
    p_init.set_defaults(func=cmd_init)

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify source files against baseline whitelist/exceptions")
    p_verify.add_argument("--mode", choices=["leaderboard", "compute"], default="leaderboard",
                          help="Verification mode: leaderboard (strict) or compute (allows exceptions)")
    p_verify.add_argument("--registry", default="configs/baseline_registry.json", help="Path to registry JSON")
    p_verify.add_argument("--source", default="submissions/track1_live", help="Path to source directory")
    p_verify.add_argument("--zip", default="submission.zip", help="Path to submission.zip")
    p_verify.add_argument("--check-zip", action="store_true", help="Also verify submission.zip SHA-256")
    p_verify.set_defaults(func=cmd_verify)

    # add-exception
    p_exc = subparsers.add_parser("add-exception", help="Add or update an approved exception")
    p_exc.add_argument("--file", required=True, help="Relative path of file within source directory")
    p_exc.add_argument("--reason", required=True, help="Justification/hypothesis for deviation")
    p_exc.add_argument("--approved-by", default="Francis", help="Approver name (default: Francis)")
    p_exc.add_argument("--registry", default="configs/baseline_registry.json", help="Path to registry JSON")
    p_exc.add_argument("--source", default="submissions/track1_live", help="Path to source directory")
    p_exc.set_defaults(func=cmd_add_exception)

    # promote
    p_prom = subparsers.add_parser("promote", help="Promote exception(s) into whitelist")
    p_prom.add_argument("--file", default=None, help="Relative path of specific exception file to promote")
    p_prom.add_argument("--all", action="store_true", help="Promote all active exceptions")
    p_prom.add_argument("--registry", default="configs/baseline_registry.json", help="Path to registry JSON")
    p_prom.set_defaults(func=cmd_promote)

    # status
    p_stat = subparsers.add_parser("status", help="Print summary of baseline registry")
    p_stat.add_argument("--registry", default="configs/baseline_registry.json", help="Path to registry JSON")
    p_stat.set_defaults(func=cmd_status)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
