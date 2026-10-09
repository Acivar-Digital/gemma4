#!/usr/bin/env python3
"""Comprehensive deterministic test suite for SFT Trajectory Translation DAG.

Tests:
1. Strict Pydantic V2 schema validation (extra="forbid", skill-to-script pairing, argument rules)
2. Trajectory structural rules (discovery, valid edit, verification, submit_patch, anti-thrashing)
3. Pydantic AI 2.0 ModelRetry self-correction via FunctionModel
4. Gemma 4 Jinja prefix-delta tokenization and invariant verification
"""

from __future__ import annotations

# ==============================================================================
# Mandatory Import Shadowing Guard:
# ==============================================================================
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
sys.path[:] = [
    p for p in sys.path
    if Path(p or ".").resolve() not in (_THIS_DIR, _REPO_ROOT)
]

import asyncio
import json
import pytest
import pydantic
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from transformers import AutoTokenizer

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

# Import translation modules directly from translate_sft_dag
from translate_sft_dag import (
    EditFileAction,
    GetStatusAction,
    ReadFileAction,
    RunSkillScriptAction,
    SubmitPatchAction,
    TranslatedStep,
    TranslatedTrajectory,
    WriteFileAction,
    RawStep,
    RawTask,
    TranslationDeps,
    RenderGemma4JinjaNode,
    ReconcileObservationsNode,
    TaskTranslationState,
    build_translator_agent,
    extract_single_target_py_filepath,
    is_single_file_py_patch,
    TOKENIZER_DIR,
    SYSTEM_PROMPT_PATH,
)
from pydantic_graph import GraphRunContext


# ==============================================================================
# Test 1: Strict Pydantic V2 Schema Validation (extra="forbid", Skill Pairing)
# ==============================================================================

def test_action_models_validation_and_forbid_extra():
    """Validates that actions enforce strict types and forbid extra fields."""
    # Valid read_file
    rf = ReadFileAction(filepath="app/main.py", start_line=10)
    assert rf.filepath == "app/main.py"
    assert rf.start_line == 10

    # Extra field forbidden
    with pytest.raises(ValidationError):
        ReadFileAction.model_validate({"filepath": "app/main.py", "extra_prop": "bad"})

    # Valid edit_file
    ef = EditFileAction(filepath="app/main.py", old_string="foo", new_string="bar")
    assert ef.old_string == "foo"

    # Empty old_string forbidden
    with pytest.raises(ValidationError):
        EditFileAction(filepath="app/main.py", old_string="", new_string="bar")

    # Valid skills
    fg = RunSkillScriptAction(skill_name="fast-grep", file_path="grep.py", args=["my_func"])
    assert fg.skill_name == "fast-grep"

    # Invalid skill-script pairing: fast-grep with map.py
    with pytest.raises(ValidationError):
        RunSkillScriptAction(skill_name="fast-grep", file_path="map.py", args=["my_func"])

    # Invalid skill args: code-map with wrong flag
    with pytest.raises(ValidationError):
        RunSkillScriptAction(skill_name="code-map", file_path="map.py", args=["--invalid", "sym"])

    # Invalid skill args: repro-check without assert
    with pytest.raises(ValidationError):
        RunSkillScriptAction(skill_name="repro-check", file_path="check.py", args=["print('hello')"])

    # Valid repro-check
    rc = RunSkillScriptAction(skill_name="repro-check", file_path="check.py", args=["assert True"])
    assert rc.skill_name == "repro-check"

    # Valid test-gate
    tg = RunSkillScriptAction(skill_name="test-gate", file_path="gate.py", args=["--diff"])
    assert tg.args == ["--diff"]


# ==============================================================================
# Test 2: Trajectory Structural Rules (Discovery, Edit, Verification, End)
# ==============================================================================

def test_translated_trajectory_structural_rules():
    """Validates structural requirements on full translated trajectories."""
    valid_steps = [
        TranslatedStep(
            step_index=0,
            source_step_index=0,
            action=RunSkillScriptAction(skill_name="fast-grep", file_path="grep.py", args=["def target"]),
        ),
        TranslatedStep(
            step_index=1,
            source_step_index=1,
            action=ReadFileAction(filepath="src/core.py", start_line=1),
        ),
        TranslatedStep(
            step_index=2,
            source_step_index=2,
            action=EditFileAction(filepath="src/core.py", old_string="bug", new_string="fix"),
        ),
        TranslatedStep(
            step_index=3,
            source_step_index=3,
            action=RunSkillScriptAction(skill_name="repro-check", file_path="check.py", args=["assert fix"]),
        ),
        TranslatedStep(
            step_index=4,
            source_step_index=4,
            action=SubmitPatchAction(),
        ),
    ]

    traj = TranslatedTrajectory(task_id="test_task_1", steps=valid_steps)
    assert traj.task_id == "test_task_1"
    assert len(traj.steps) == 5

    # Missing discovery: replace fast-grep with get_status
    bad_discovery = [
        TranslatedStep(
            step_index=0,
            source_step_index=0,
            action=GetStatusAction(),
        ),
        valid_steps[1],
        valid_steps[2],
        valid_steps[3],
        valid_steps[4],
    ]
    with pytest.raises(ValidationError, match="discovery call"):
        TranslatedTrajectory(task_id="test_task_1", steps=bad_discovery)

    # Missing valid edit: edit targeting tests/test_core.py only
    bad_edit = [
        valid_steps[0],
        valid_steps[1],
        TranslatedStep(
            step_index=2,
            source_step_index=2,
            action=EditFileAction(filepath="tests/test_core.py", old_string="a", new_string="b"),
        ),
        valid_steps[3],
        valid_steps[4],
    ]
    with pytest.raises(ValidationError, match="edit_file targeting a non-test .py file"):
        TranslatedTrajectory(task_id="test_task_1", steps=bad_edit)

    # Missing verification
    bad_verify = [
        valid_steps[0],
        valid_steps[1],
        valid_steps[2],
        valid_steps[4],  # Skips repro-check
    ]
    with pytest.raises(ValidationError, match="verification call"):
        TranslatedTrajectory(task_id="test_task_1", steps=bad_verify)

    # Not ending with submit_patch
    bad_end = valid_steps[:4]
    with pytest.raises(ValidationError, match="end with submit_patch"):
        TranslatedTrajectory(task_id="test_task_1", steps=bad_end)

    # Consecutive identical actions (anti-thrashing)
    duplicate_steps = [
        valid_steps[0],
        valid_steps[0],  # Duplicate identical fast-grep
        valid_steps[2],
        valid_steps[3],
        valid_steps[4],
    ]
    with pytest.raises(ValidationError, match="Consecutive identical actions"):
        TranslatedTrajectory(task_id="test_task_1", steps=duplicate_steps)


# ==============================================================================
# Test 3: Pydantic AI 2.0 ModelRetry Self-Correction via FunctionModel
# ==============================================================================

def test_agent_model_retry_self_correction():
    """Tests that ModelRetry fires on wrong edit filepath and succeeds on Turn 2."""
    async def _run():
        raw_task = RawTask(
            task_id="dummy_task",
            repo="dummy_repo",
            problem_statement="Fix bug in src/module.py",
            gold_patch="diff --git a/src/module.py b/src/module.py\n--- a/src/module.py\n+++ b/src/module.py\n",
            target_filepath="src/module.py",
            raw_steps=[
                RawStep(step_index=0, tool_name="bash", tool_input={"command": "grep"}, observation="found"),
                RawStep(step_index=1, tool_name="str_replace_editor", tool_input={}, observation="edited"),
                RawStep(step_index=2, tool_name="bash", tool_input={"command": "pytest"}, observation="passed"),
                RawStep(step_index=3, tool_name="submit", tool_input={}, observation="done"),
            ],
        )

        attempt_count = 0

        def mock_model_fn(messages, info):
            nonlocal attempt_count
            attempt_count += 1

            # Turn 1: Return EditFileAction with WRONG filepath to trigger ModelRetry
            if attempt_count == 1:
                bad_data = {
                    "task_id": "dummy_task",
                    "steps": [
                        {
                            "step_index": 0,
                            "source_step_index": 0,
                            "action": {
                                "action_type": "run_skill_script",
                                "skill_name": "fast-grep",
                                "file_path": "grep.py",
                                "args": ["target"],
                            },
                        },
                        {
                            "step_index": 1,
                            "source_step_index": 1,
                            "action": {
                                "action_type": "edit_file",
                                "filepath": "wrong_dir/wrong_file.py",  # WRONG FILE!
                                "old_string": "foo",
                                "new_string": "bar",
                                "allow_multiple": False,
                            },
                        },
                        {
                            "step_index": 2,
                            "source_step_index": 2,
                            "action": {
                                "action_type": "run_skill_script",
                                "skill_name": "repro-check",
                                "file_path": "check.py",
                                "args": ["assert True"],
                            },
                        },
                        {
                            "step_index": 3,
                            "source_step_index": 3,
                            "action": {"action_type": "submit_patch"},
                        },
                    ],
                }
                call_id = f"call_{attempt_count}"
                return ModelResponse(parts=[ToolCallPart("final_result", bad_data, tool_call_id=call_id)])

            # Turn 2: Self-corrected with CORRECT target filepath 'src/module.py'
            good_data = {
                "task_id": "dummy_task",
                "steps": [
                    {
                        "step_index": 0,
                        "source_step_index": 0,
                        "action": {
                            "skill_name": "fast-grep",
                            "file_path": "grep.py",
                            "args": ["target"],
                            "action_type": "run_skill_script",
                        },
                    },
                    {
                        "step_index": 1,
                        "source_step_index": 1,
                        "action": {
                            "action_type": "edit_file",
                            "filepath": "src/module.py",  # CORRECTED!
                            "old_string": "foo",
                            "new_string": "bar",
                            "allow_multiple": False,
                        },
                    },
                    {
                        "step_index": 2,
                        "source_step_index": 2,
                        "action": {
                            "skill_name": "repro-check",
                            "file_path": "check.py",
                            "args": ["assert True"],
                            "action_type": "run_skill_script",
                        },
                    },
                    {
                        "step_index": 3,
                        "source_step_index": 3,
                        "action": {"action_type": "submit_patch"},
                    },
                ],
            }
            call_id = f"call_{attempt_count}"
            return ModelResponse(parts=[ToolCallPart("final_result", good_data, tool_call_id=call_id)])

        agent = build_translator_agent()
        with agent.override(model=FunctionModel(mock_model_fn)):
            res = await agent.run("translate", deps=TranslationDeps(raw_task=raw_task))

        assert attempt_count == 2, f"Expected 2 attempts (retry triggered), got {attempt_count}"
        assert res.output.task_id == "dummy_task"
        edit_step = res.output.steps[1].action
        assert isinstance(edit_step, EditFileAction)
        assert edit_step.filepath == "src/module.py"

    asyncio.run(_run())


# ==============================================================================
# Test 4: Gemma 4 Jinja Prefix-Delta Tokenization and Invariant Verification
# ==============================================================================

def test_gemma4_jinja_rendering_and_invariants():
    """Validates Gemma 4 chat_template.jinja prefix-delta alignment and invariants."""
    async def _run():
        assert TOKENIZER_DIR.exists(), f"Tokenizer directory missing at {TOKENIZER_DIR}"
        tokenizer = AutoTokenizer.from_pretrained(str(TOKENIZER_DIR))

        with open(SYSTEM_PROMPT_PATH, encoding="utf-8") as f:
            system_prompt = f.read()

        raw_task = RawTask(
            task_id="jinja_test_task",
            repo="test_repo",
            problem_statement="Fix bug in foo.py",
            gold_patch="diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n",
            target_filepath="foo.py",
            raw_steps=[
                RawStep(step_index=0, tool_name="bash", tool_input={}, observation="def foo(): pass"),
                RawStep(step_index=1, tool_name="str_replace_editor", tool_input={}, observation="edited"),
                RawStep(step_index=2, tool_name="bash", tool_input={}, observation="assertion passed"),
                RawStep(step_index=3, tool_name="submit", tool_input={}, observation="done"),
            ],
        )

        trajectory = TranslatedTrajectory(
            task_id="jinja_test_task",
            steps=[
                TranslatedStep(
                    step_index=0,
                    source_step_index=0,
                    action=RunSkillScriptAction(skill_name="fast-grep", file_path="grep.py", args=["def foo"]),
                ),
                TranslatedStep(
                    step_index=1,
                    source_step_index=1,
                    action=EditFileAction(filepath="foo.py", old_string="foo", new_string="bar"),
                ),
                TranslatedStep(
                    step_index=2,
                    source_step_index=2,
                    action=RunSkillScriptAction(skill_name="repro-check", file_path="check.py", args=["assert True"]),
                ),
                TranslatedStep(
                    step_index=3,
                    source_step_index=3,
                    action=SubmitPatchAction(),
                ),
            ],
        )

        state = TaskTranslationState(
            raw_task=raw_task,
            translated_trajectory=trajectory,
        )

        from pydantic_graph import GraphRunContext

        # Step 1: Reconcile observations
        reconcile_node = ReconcileObservationsNode()
        await reconcile_node.run(GraphRunContext(state=state, deps=None))
        assert state.reconciled_messages is not None
        assert len(state.reconciled_messages) == 8  # 4 assistant actions + 4 tool returns

        # Step 2: Render Gemma 4 Jinja windows
        render_node = RenderGemma4JinjaNode(tokenizer=tokenizer, system_prompt=system_prompt)
        await render_node.run(GraphRunContext(state=state, deps=None))

        assert state.sft_windows is not None
        assert len(state.sft_windows) > 0, "Expected at least 1 valid SFT window"

        for w in state.sft_windows:
            full_text = str(w["text"])
            prefix_text = str(w["prefix_text"])
            completion_text = str(w["completion_text"])

            # Invariant 1: full_text starts with prefix_text
            assert full_text.startswith(prefix_text), "full_text must start with prefix_text"

            # Invariant 2: completion_text starts with tool call
            assert completion_text.startswith("<|tool_call>call:"), (
                f"completion_text must start with '<|tool_call>call:', got {completion_text[:30]}"
            )

            # Invariant 3: no thought tokens in completion
            assert "<|channel>thought" not in completion_text, "No thoughts allowed in completion"

            # Invariant 4: Token ID alignment
            prefix_ids = tokenizer(prefix_text, add_special_tokens=False)["input_ids"]
            full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]
            assert full_ids[:len(prefix_ids)] == prefix_ids, "Prefix token IDs must match exactly"

            # Invariant 5: Max sequence length <= 8192
            assert len(full_ids) <= 8192, f"Sequence length {len(full_ids)} exceeds 8192"

    asyncio.run(_run())


# ==============================================================================
# Test 5: Multi-Turn Diagnostic Pivot Loop with History & Self-Correction
# ==============================================================================

def test_agent_multi_turn_pivot_loop():
    """Tests that RunPydanticAgentNode diagnoses invariant failures, sends history & pivot prompt, and succeeds on Turn 2."""
    async def _run():
        raw_task = RawTask(
            task_id="pivot_test_task",
            repo="test_repo",
            problem_statement="Fix bug in core/engine.py",
            gold_patch="diff --git a/core/engine.py b/core/engine.py\n--- a/core/engine.py\n+++ b/core/engine.py\n",
            target_filepath="core/engine.py",
            raw_steps=[
                RawStep(step_index=0, tool_name="bash", tool_input={"command": "grep"}, observation="found"),
                RawStep(step_index=1, tool_name="str_replace_editor", tool_input={}, observation="edited"),
                RawStep(step_index=2, tool_name="bash", tool_input={"command": "pytest"}, observation="passed"),
                RawStep(step_index=3, tool_name="submit", tool_input={}, observation="done"),
            ],
        )

        attempt_count = 0
        received_prompts: list[str] = []

        def mock_model_fn(messages, info):
            nonlocal attempt_count
            attempt_count += 1

            # Inspect the user prompt received
            user_part = [p for m in messages for p in getattr(m, "parts", []) if hasattr(p, "content")]
            if user_part:
                received_prompts.append(str(user_part[-1].content))

            # Turn 1: Valid schema, but edits wrong file 'wrong_core/engine.py'
            if attempt_count == 1:
                bad_trajectory = {
                    "task_id": "pivot_test_task",
                    "steps": [
                        {
                            "step_index": 0,
                            "source_step_index": 0,
                            "action": {
                                "action_type": "run_skill_script",
                                "skill_name": "fast-grep",
                                "file_path": "grep.py",
                                "args": ["engine"],
                            },
                        },
                        {
                            "step_index": 1,
                            "source_step_index": 1,
                            "action": {
                                "action_type": "edit_file",
                                "filepath": "wrong_core/engine.py",
                                "old_string": "a = 1",
                                "new_string": "a = 2",
                                "allow_multiple": False,
                            },
                        },
                        {
                            "step_index": 2,
                            "source_step_index": 2,
                            "action": {
                                "action_type": "run_skill_script",
                                "skill_name": "repro-check",
                                "file_path": "check.py",
                                "args": ["assert True"],
                            },
                        },
                        {
                            "step_index": 3,
                            "source_step_index": 3,
                            "action": {"action_type": "submit_patch"},
                        },
                    ],
                }
                return ModelResponse(parts=[ToolCallPart("final_result", bad_trajectory, tool_call_id=f"c_{attempt_count}")])

            # Turn 2: Self-corrected to target 'core/engine.py'
            good_trajectory = {
                "task_id": "pivot_test_task",
                "steps": [
                    {
                        "step_index": 0,
                        "source_step_index": 0,
                        "action": {
                            "action_type": "run_skill_script",
                            "skill_name": "fast-grep",
                            "file_path": "grep.py",
                            "args": ["engine"],
                        },
                    },
                    {
                        "step_index": 1,
                        "source_step_index": 1,
                        "action": {
                            "action_type": "edit_file",
                            "filepath": "core/engine.py",
                            "old_string": "a = 1",
                            "new_string": "a = 2",
                            "allow_multiple": False,
                        },
                    },
                    {
                        "step_index": 2,
                        "source_step_index": 2,
                        "action": {
                            "action_type": "run_skill_script",
                            "skill_name": "repro-check",
                            "file_path": "check.py",
                            "args": ["assert True"],
                        },
                    },
                    {
                        "step_index": 3,
                        "source_step_index": 3,
                        "action": {"action_type": "submit_patch"},
                    },
                ],
            }
            return ModelResponse(parts=[ToolCallPart("final_result", good_trajectory, tool_call_id=f"c_{attempt_count}")])

        from translate_sft_dag import RunPydanticAgentNode, ReconcileObservationsNode

        agent = build_translator_agent()
        node = RunPydanticAgentNode(agent=agent, max_pivots=3)
        state = TaskTranslationState(raw_task=raw_task)

        with agent.override(model=FunctionModel(mock_model_fn)):
            result_node = await node.run(GraphRunContext(state=state, deps=None))

        # Assertions
        assert attempt_count == 2, f"Expected 2 attempts for pivot, got {attempt_count}"
        assert isinstance(result_node, ReconcileObservationsNode), f"Expected ReconcileObservationsNode, got {type(result_node)}"
        assert state.translated_trajectory is not None
        assert len(state.translated_trajectory.steps) == 4
        assert isinstance(state.translated_trajectory.steps[-1].action, SubmitPatchAction)
        assert state.translated_trajectory.steps[1].action.filepath == "core/engine.py"

        # Verify that Turn 2 received the pivot directive
        assert len(received_prompts) >= 2
        pivot_prompt_received = received_prompts[-1]
        assert "core/engine.py" in pivot_prompt_received

    asyncio.run(_run())
