#!/usr/bin/env python3
"""
tests/test_baseline_gate.py

Unit tests for scripts/baseline_gate.py:
- Init on dummy tree
- Verification pass in leaderboard mode
- Verification fail in leaderboard mode when a file is modified, added, or deleted
- Verification fail in leaderboard mode when an exception is present but not promoted
- Verification pass in compute mode when an approved exception is present
- Exception addition and promotion lifecycle
"""

import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.baseline_gate import (
    build_parser,
    collect_source_files,
    load_registry,
    save_registry,
    sha256_file,
)


class TestBaselineGate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source_dir = self.root / "source"
        self.source_dir.mkdir(parents=True)
        self.registry_path = self.root / "configs" / "baseline_registry.json"
        self.zip_path = self.root / "submission.zip"

        # Populate a dummy source tree
        (self.source_dir / "agent.yaml").write_text("agent_config: v1\n", encoding="utf-8")
        (self.source_dir / "eval_config.yaml").write_text("max_tool_calls: 40\n", encoding="utf-8")
        sub_dir = self.source_dir / "prompts"
        sub_dir.mkdir()
        (sub_dir / "main.md").write_text("# Main Prompt\n", encoding="utf-8")

        # Create dummy submission.zip
        self.zip_path.write_bytes(b"dummy zip content 12345")

        self.parser = build_parser()

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, args_list):
        args = self.parser.parse_args(args_list)
        return args.func(args)

    def test_init_dummy_tree(self):
        """Init builds registry with correct whitelist and zip sha256."""
        rc = self.run_cli([
            "init",
            "--source", str(self.source_dir),
            "--zip", str(self.zip_path),
            "--out", str(self.registry_path),
            "--baseline-ref", "12345678",
            "--score", "0.15",
            "--locked-at", "2026-10-07T00:00:00Z"
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(self.registry_path.is_file())

        reg = load_registry(self.registry_path)
        self.assertEqual(reg["baseline_ref"], "12345678")
        self.assertEqual(reg["public_score"], 0.15)
        self.assertEqual(reg["locked_at"], "2026-10-07T00:00:00Z")
        self.assertEqual(reg["zip_sha256"], sha256_file(self.zip_path))
        self.assertEqual(len(reg["whitelist"]), 3)
        self.assertIn("agent.yaml", reg["whitelist"])
        self.assertIn("eval_config.yaml", reg["whitelist"])
        self.assertIn("prompts/main.md", reg["whitelist"])
        self.assertEqual(reg["exceptions"], {})

    def test_verify_leaderboard_pass(self):
        """Clean tree matching whitelist passes leaderboard mode."""
        self.run_cli([
            "init",
            "--source", str(self.source_dir),
            "--zip", str(self.zip_path),
            "--out", str(self.registry_path),
        ])

        rc = self.run_cli([
            "verify",
            "--mode", "leaderboard",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
            "--zip", str(self.zip_path),
            "--check-zip"
        ])
        self.assertEqual(rc, 0)

    def test_verify_leaderboard_fail_modified_file(self):
        """Modifying a whitelist file fails leaderboard mode."""
        self.run_cli([
            "init",
            "--source", str(self.source_dir),
            "--out", str(self.registry_path),
        ])

        # Mutate agent.yaml
        (self.source_dir / "agent.yaml").write_text("agent_config: mutated\n", encoding="utf-8")

        rc = self.run_cli([
            "verify",
            "--mode", "leaderboard",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc, 1)

    def test_verify_leaderboard_fail_added_file(self):
        """Adding an extraneous unwhitelisted file fails leaderboard mode."""
        self.run_cli([
            "init",
            "--source", str(self.source_dir),
            "--out", str(self.registry_path),
        ])

        (self.source_dir / "extra.py").write_text("print('rogue')\n", encoding="utf-8")

        rc = self.run_cli([
            "verify",
            "--mode", "leaderboard",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc, 1)

    def test_verify_leaderboard_fail_deleted_file(self):
        """Deleting a whitelisted file fails leaderboard mode."""
        self.run_cli([
            "init",
            "--source", str(self.source_dir),
            "--out", str(self.registry_path),
        ])

        (self.source_dir / "eval_config.yaml").unlink()

        rc = self.run_cli([
            "verify",
            "--mode", "leaderboard",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc, 1)

    def test_verify_leaderboard_fail_unpromoted_exception(self):
        """A registered exception that is not promoted fails leaderboard mode."""
        self.run_cli([
            "init",
            "--source", str(self.source_dir),
            "--out", str(self.registry_path),
        ])

        # Modify agent.yaml and register as exception
        (self.source_dir / "agent.yaml").write_text("agent_config: v2_experimental\n", encoding="utf-8")
        rc_exc = self.run_cli([
            "add-exception",
            "--file", "agent.yaml",
            "--reason", "Test experimental feature",
            "--approved-by", "Francis",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc_exc, 0)

        # In leaderboard mode, this MUST fail
        rc = self.run_cli([
            "verify",
            "--mode", "leaderboard",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc, 1)

    def test_verify_compute_pass_approved_exception(self):
        """A registered exception passes compute mode."""
        self.run_cli([
            "init",
            "--source", str(self.source_dir),
            "--out", str(self.registry_path),
        ])

        # Modify agent.yaml and register exception
        (self.source_dir / "agent.yaml").write_text("agent_config: v2_experimental\n", encoding="utf-8")
        rc_exc = self.run_cli([
            "add-exception",
            "--file", "agent.yaml",
            "--reason", "Compute test run only",
            "--approved-by", "Francis",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc_exc, 0)

        # In compute mode, this MUST pass
        rc = self.run_cli([
            "verify",
            "--mode", "compute",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc, 0)

    def test_verify_compute_fail_unapproved_modification(self):
        """An unapproved modification (not in exceptions) fails compute mode."""
        self.run_cli([
            "init",
            "--source", str(self.source_dir),
            "--out", str(self.registry_path),
        ])

        (self.source_dir / "agent.yaml").write_text("agent_config: rogue_unapproved\n", encoding="utf-8")

        rc = self.run_cli([
            "verify",
            "--mode", "compute",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc, 1)

    def test_exception_lifecycle_add_and_promote(self):
        """Full lifecycle: add-exception -> compute PASS -> leaderboard FAIL -> promote -> leaderboard PASS."""
        self.run_cli([
            "init",
            "--source", str(self.source_dir),
            "--out", str(self.registry_path),
        ])

        # 1. Modify prompt
        (self.source_dir / "prompts" / "main.md").write_text("# Optimized Main Prompt\n", encoding="utf-8")

        # 2. Add exception
        rc_add = self.run_cli([
            "add-exception",
            "--file", "prompts/main.md",
            "--reason", "Prompt engineering optimization",
            "--approved-by", "Francis",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc_add, 0)

        # Check registry has exception
        reg = load_registry(self.registry_path)
        self.assertIn("prompts/main.md", reg["exceptions"])
        self.assertEqual(reg["exceptions"]["prompts/main.md"]["reason"], "Prompt engineering optimization")
        self.assertEqual(reg["exceptions"]["prompts/main.md"]["approved_by"], "Francis")

        # 3. Compute mode passes
        rc_compute = self.run_cli([
            "verify",
            "--mode", "compute",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc_compute, 0)

        # 4. Leaderboard mode fails before promotion
        rc_lb_fail = self.run_cli([
            "verify",
            "--mode", "leaderboard",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc_lb_fail, 1)

        # 5. Status command check
        rc_status = self.run_cli([
            "status",
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc_status, 0)

        # 6. Promote exception
        rc_promote = self.run_cli([
            "promote",
            "--file", "prompts/main.md",
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc_promote, 0)

        # Check registry state after promotion
        reg_after = load_registry(self.registry_path)
        self.assertEqual(reg_after["exceptions"], {})
        new_prompt_sha = sha256_file(self.source_dir / "prompts" / "main.md")
        self.assertEqual(reg_after["whitelist"]["prompts/main.md"], new_prompt_sha)

        # 7. Leaderboard mode now passes
        rc_lb_pass = self.run_cli([
            "verify",
            "--mode", "leaderboard",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc_lb_pass, 0)

    def test_promote_all_exceptions(self):
        """Promote --all promotes multiple exceptions at once."""
        self.run_cli([
            "init",
            "--source", str(self.source_dir),
            "--out", str(self.registry_path),
        ])

        (self.source_dir / "agent.yaml").write_text("agent_config: v2\n", encoding="utf-8")
        (self.source_dir / "eval_config.yaml").write_text("max_tool_calls: 30\n", encoding="utf-8")

        self.run_cli([
            "add-exception",
            "--file", "agent.yaml",
            "--reason", "v2 agent",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])
        self.run_cli([
            "add-exception",
            "--file", "eval_config.yaml",
            "--reason", "30 calls",
            "--source", str(self.source_dir),
            "--registry", str(self.registry_path),
        ])

        reg = load_registry(self.registry_path)
        self.assertEqual(len(reg["exceptions"]), 2)

        rc_promote = self.run_cli([
            "promote",
            "--all",
            "--registry", str(self.registry_path),
        ])
        self.assertEqual(rc_promote, 0)

        reg_after = load_registry(self.registry_path)
        self.assertEqual(len(reg_after["exceptions"]), 0)
        self.assertEqual(reg_after["whitelist"]["agent.yaml"], sha256_file(self.source_dir / "agent.yaml"))
        self.assertEqual(reg_after["whitelist"]["eval_config.yaml"], sha256_file(self.source_dir / "eval_config.yaml"))


if __name__ == "__main__":
    unittest.main()
