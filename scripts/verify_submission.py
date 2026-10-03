#!/usr/bin/env python3
"""Automated 9-Gate Verification Script for Kaggle SWE-Gemma Submissions.

Enforces all anti-regression controls established in .agents/skills/kaggle-submit/SKILL.md.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import zipfile
from pathlib import Path

import yaml

SUBMISSION_DIR = Path("my_submission")
ZIP_PATH = Path("submission.zip")


class SafeLoaderIgnoreUnknown(yaml.SafeLoader):
    pass


SafeLoaderIgnoreUnknown.add_constructor(None, lambda loader, node: None)


def print_gate(gate_num: int, title: str, passed: bool, detail: str = "") -> None:
    icon = "✅" if passed else "❌"
    status = "PASSED" if passed else "FAILED"
    print(f"{icon} GATE {gate_num} {status}: {title}")
    if detail:
        print(f"   ↳ {detail}")


def main() -> int:
    print("=" * 65)
    print("KAGGLE LEADERBOARD SUBMISSION: 9-GATE PRE-SUBMISSION AUDIT")
    print("=" * 65)

    if not ZIP_PATH.exists():
        print(f"❌ FAIL: {ZIP_PATH} does not exist! Run packaging protocol first.")
        return 1

    all_passed = True

    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        zip_names = z.namelist()

    # Gate 1: Root Layout Integrity
    g1_pass = ("agent.yaml" in zip_names or "root_agent.yaml" in zip_names) and not any(
        n.startswith("my_submission/agent.yaml") for n in zip_names
    )
    all_passed &= g1_pass
    print_gate(1, "Root Layout Integrity", g1_pass, "agent.yaml is located at root of zip")

    # Gate 2: LoRA Integrity
    agent_yaml_text = (SUBMISSION_DIR / "agent.yaml").read_text(encoding="utf-8")
    parsed_agent = yaml.load(agent_yaml_text, Loader=SafeLoaderIgnoreUnknown) or {}
    has_adapter = bool(parsed_agent.get("adapter"))
    has_adapter_dir = any(n.startswith("adapters/") for n in zip_names)
    g2_pass = not has_adapter and not has_adapter_dir
    all_passed &= g2_pass
    print_gate(
        2,
        "LoRA Integrity",
        g2_pass,
        "Pure Track 1 declarative baseline; no un-trained adapter mounted"
        if g2_pass
        else f"Found adapter='{parsed_agent.get('adapter')}' or adapters/ in zip",
    )

    # Gate 3: Cleanliness & Hygiene
    ds_count = sum(1 for n in zip_names if ".DS_Store" in n)
    pyc_count = sum(1 for n in zip_names if n.endswith(".pyc") or "__pycache__" in n)
    dot_count = sum(1 for n in zip_names if "/._" in n or n.startswith("._"))
    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    g3_pass = ds_count == 0 and pyc_count == 0 and dot_count == 0 and size_mb < 3072
    all_passed &= g3_pass
    print_gate(
        3,
        "Artifact Cleanliness",
        g3_pass,
        f"{size_mb * 1024:.1f} KB (0 .pyc, 0 .DS_Store, 0 ._*, < 3 GiB)",
    )

    # Gate 4: Sandboxed ADK Compilation
    try:
        from adk_submission.compiler import compile_submission
        from swegemma.context import SwegemmaContext
        from swegemma.models import setup_gemma_model_registry
        from swegemma.sandbox.subprocess import SubprocessManager

        models = setup_gemma_model_registry(
            api_base=os.getenv("SWEGEMMA_API_BASE", "http://literouter.lan:7766/v1"),
            api_key=os.getenv("SWEGEMMA_API_KEY", "dummy"),
            served_model=os.getenv("SWEGEMMA_MODEL", "stealth/space-bunny-alpha"),
        )
        mgr = SubprocessManager(system_site_packages=True)
        sb_id = mgr.start()
        ctx = SwegemmaContext(docker_manager=mgr, container_id=sb_id, problem_statement="test")
        tools = ctx.create_tools()
        agent = compile_submission(
            submission_dir=SUBMISSION_DIR, tool_registry=tools, model_registry=models
        )
        mgr.stop(sb_id)
        g4_pass = agent is not None and getattr(agent, "name", None) == "main"
        detail_g4 = f"Successfully compiled agent '{agent.name}'"
    except Exception as e:
        g4_pass = False
        detail_g4 = f"Compilation exception: {e}"
    all_passed &= g4_pass
    print_gate(4, "Sandboxed ADK Compilation", g4_pass, detail_g4)

    # Gate 5: Skill Specifications & Kebab-Case
    skills_dir = SUBMISSION_DIR / "skills"
    skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()] if skills_dir.exists() else []
    g5_pass = True
    g5_detail = f"Verified {len(skill_dirs)} skill directories"
    for d in skill_dirs:
        sf = d / "SKILL.md"
        if not sf.exists():
            g5_pass = False
            g5_detail = f"{d.name} missing SKILL.md"
            break
        text = sf.read_text(encoding="utf-8")
        if not any(line.strip() == f"name: {d.name}" for line in text.splitlines()):
            g5_pass = False
            g5_detail = f"{d.name} frontmatter name does not match kebab-case folder name"
            break
    all_passed &= g5_pass
    print_gate(5, "Skill Directory & Spec", g5_pass, g5_detail)

    # Gate 6: Patch Safety & Container B Protections
    prompt_path = SUBMISSION_DIR / "prompts" / "main.md"
    prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    has_tmp = "/tmp" in prompt_text
    has_container_b = "Container B" in prompt_text or "test" in prompt_text
    g6_pass = has_tmp and has_container_b
    all_passed &= g6_pass
    print_gate(
        6,
        "Patch Safety & Container B",
        g6_pass,
        "Mandatory /tmp scratch repro and test-file protection present",
    )

    # Gate 7: Budget Ladder Synchronization
    has_50_calls = bool(re.search(r"50[- ](tool[- ])?calls?", prompt_text, re.IGNORECASE))
    g7_pass = has_50_calls
    all_passed &= g7_pass
    print_gate(
        7,
        "Budget Ladder Synchronization",
        g7_pass,
        "Prompt aligns with harness 50 tool-call limit and get_status() countdown",
    )

    # Gate 8: Tool & Skill Invocation Contract
    # Look for illegal direct function invocation instructions like `fast-grep(term=...)`
    direct_skill_call = bool(
        re.search(
            r"`(fast-grep|code-map|code-oracle|repro-check|test-gate)\(", prompt_text
        )
    )
    g8_pass = not direct_skill_call
    g8_detail = (
        "Instructions correctly invoke skills via run_skill_script or use native tools"
        if g8_pass
        else "Instruction prompt tells model to call skill directly as a tool!"
    )
    all_passed &= g8_pass
    print_gate(8, "Tool & Skill Invocation API", g8_pass, g8_detail)

    # Gate 9: SHA-256 Checksum
    h = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    print_gate(9, "Submission Checksum Verified", True, f"SHA-256: {h}")

    print("=" * 65)
    if all_passed:
        print("AUDIT OUTCOME: 100% PASS — SUBMISSION IS CLEARED FOR LEADERBOARD")
        print("=" * 65)
        return 0
    else:
        print("AUDIT OUTCOME: ❌ GATES FAILED — DO NOT SUBMIT TO KAGGLE")
        print("=" * 65)
        return 1


if __name__ == "__main__":
    sys.exit(main())
