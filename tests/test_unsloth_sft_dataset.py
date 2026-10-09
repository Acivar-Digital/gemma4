"""Pre-upload deterministic verification suite for Track 2 Gemma 4 SFT dataset and cloud script."""

import json
from pathlib import Path
import sys

from transformers import AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.sft_data_filters import (
    classify_trajectory_steps,
    is_single_file_py_patch,
    load_benchmark_exclusion_set,
    translate_tool_call,
)

TRAIN_JSONL = ROOT_DIR / "data" / "unsloth_sft" / "train.jsonl"
VAL_JSONL = ROOT_DIR / "data" / "unsloth_sft" / "val.jsonl"
ROOT_TRAIN_JSONL = ROOT_DIR / "data" / "unsloth_sft_train.jsonl"
ROOT_VAL_JSONL = ROOT_DIR / "data" / "unsloth_sft_val.jsonl"
METADATA_JSON = ROOT_DIR / "data" / "unsloth_sft" / "metadata.json"
TASKS_JSONL = ROOT_DIR / "tasks.jsonl"
MODEL_DIR = ROOT_DIR / "models" / "gemma-4-31b-it-qat-w4a16-ct"
CLOUD_SCRIPT = ROOT_DIR / "scripts" / "train_gemma4_unsloth_cloud.py"

ALLOWED_TOOLS = {
    "read_file",
    "edit_file",
    "write_file",
    "get_status",
    "submit_patch",
    "run_skill_script",
}


def test_single_file_py_filter() -> None:
    single_py = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"
    )
    multi_py = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "diff --git a/reproduce.py b/reproduce.py\n"
        "--- a/reproduce.py\n"
        "+++ b/reproduce.py\n"
    )
    non_py = (
        "diff --git a/README.md b/README.md\n"
        "--- a/README.md\n"
        "+++ b/README.md\n"
    )
    assert is_single_file_py_patch(single_py) is True
    assert is_single_file_py_patch(multi_py) is False
    assert is_single_file_py_patch(non_py) is False


def test_two_kind_negative_classifier() -> None:
    # Type A (Red-to-Green repro failure -> edit_file -> submit_patch) => KEEP
    type_a_steps = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "run_skill_script",
                        "arguments": {"skill_name": "repro-check", "file_path": "check.py", "args": ["assert 1==2"]},
                    },
                }
            ],
        },
        {"role": "tool", "name": "run_skill_script", "tool_call_id": "c1", "content": "Traceback: AssertionError"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c2",
                    "type": "function",
                    "function": {
                        "name": "edit_file",
                        "arguments": {
                            "filepath": "app.py",
                            "old_string": "return 1",
                            "new_string": "return 2",
                            "allow_multiple": False,
                        },
                    },
                }
            ],
        },
        {"role": "tool", "name": "edit_file", "tool_call_id": "c2", "content": "Successfully edited app.py"},
        {
            "role": "assistant",
            "tool_calls": [{"id": "c3", "type": "function", "function": {"name": "submit_patch", "arguments": {}}}],
        },
        {"role": "tool", "name": "submit_patch", "tool_call_id": "c3", "content": "Patch submitted."},
    ]
    ok_a, stats_a = classify_trajectory_steps(type_a_steps)
    assert ok_a is True
    assert stats_a["type_b_dumb_calls"] == 0
    assert stats_a["type_a_neg_calls"] == 1

    # Type B (failed edit_file old_string mismatch) => REJECT
    type_b_steps = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "edit_file",
                        "arguments": {
                            "filepath": "app.py",
                            "old_string": "missing",
                            "new_string": "fixed",
                            "allow_multiple": False,
                        },
                    },
                }
            ],
        },
        {"role": "tool", "name": "edit_file", "tool_call_id": "c1", "content": "Error: old_string not found in app.py"},
        {
            "role": "assistant",
            "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "submit_patch", "arguments": {}}}],
        },
        {"role": "tool", "name": "submit_patch", "tool_call_id": "c2", "content": "Patch submitted."},
    ]
    ok_b, stats_b = classify_trajectory_steps(type_b_steps)
    assert ok_b is False
    assert stats_b["type_b_dumb_calls"] >= 1


def test_dataset_files_and_invariants() -> None:
    for p in (TRAIN_JSONL, VAL_JSONL, ROOT_TRAIN_JSONL, ROOT_VAL_JSONL, METADATA_JSON):
        assert p.exists() and p.stat().st_size > 0, f"Missing or empty dataset file: {p}"

    exclusions = load_benchmark_exclusion_set(TASKS_JSONL)
    assert len(exclusions) == 129

    train_rows = [json.loads(line) for line in open(TRAIN_JSONL, encoding="utf-8") if line.strip()]
    val_rows = [json.loads(line) for line in open(VAL_JSONL, encoding="utf-8") if line.strip()]
    all_rows = train_rows + val_rows

    assert len(train_rows) >= 400, f"Expected >=400 train rows, got {len(train_rows)}"
    assert len(val_rows) >= 50, f"Expected >=50 val rows, got {len(val_rows)}"

    train_tasks = {r["task_id"] for r in train_rows}
    val_tasks = {r["task_id"] for r in val_rows}
    assert train_tasks.isdisjoint(val_tasks), "Train and val task_ids overlap!"

    for r in all_rows:
        # 1. Source check: swe_smith or swe_zero only (zero swe_rebench)
        assert r["source"] in ("swe_smith", "swe_zero"), f"Forbidden source: {r.get('source')}"
        raw_tid = r["task_id"].split("__", 1)[1] if "__" in r["task_id"] else r["task_id"]
        assert raw_tid not in exclusions, f"Benchmark leakage: {raw_tid}"

        # 2. Prefix-delta & Zero-Thought checks
        prefix_text = r["prefix_text"]
        comp_text = r["completion_text"]
        full_text = r["text"]

        assert full_text.startswith(prefix_text)
        assert full_text[len(prefix_text) :] == comp_text
        assert comp_text.startswith("<|tool_call>call:"), f"Completion does not start with tool call: {comp_text[:60]}"
        assert "<|channel>thought" not in comp_text, "Thought channel found in completion_text!"
        assert "<|think|>" not in comp_text, "<|think|> token found in completion_text!"
        assert "<start_of_turn>" not in full_text, "Legacy Gemma 2/3 token found!"

        # 3. Tool contract check
        for t in r["target_tools"]:
            assert t in ALLOWED_TOOLS, f"Forbidden tool in target_tools: {t}"
            assert t != "run_command"

        # 4. Token budget check
        assert r["total_token_count"] <= 3072
        assert 0 < r["prefix_token_count"] < r["total_token_count"]

        # 5. Role preservation invariant in messages
        for m in r["messages"]:
            assert m["role"] in ("system", "user", "assistant", "tool")
            if m["role"] == "assistant":
                assert "reasoning" not in m and "reasoning_content" not in m


def test_tokenizer_262k_prefix_alignment_sample() -> None:
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    assert len(tokenizer) == 262144

    train_rows = [json.loads(line) for idx, line in enumerate(open(TRAIN_JSONL, encoding="utf-8")) if idx < 25 and line.strip()]
    bos_id = tokenizer.bos_token_id

    for r in train_rows:
        p_ids = tokenizer(r["prefix_text"], add_special_tokens=False)["input_ids"]
        f_ids = tokenizer(r["text"], add_special_tokens=False)["input_ids"]
        assert f_ids[0] == bos_id, "First token must be <bos>"
        assert f_ids[1] != bos_id, "Duplicate <bos><bos> detected!"
        assert f_ids[: len(p_ids)] == p_ids, "Tokenized prefix_ids do not match prefix of full_ids!"
        assert len(f_ids) <= 3072


def test_cloud_training_script_alignment() -> None:
    for script_path in (
        CLOUD_SCRIPT,
        ROOT_DIR / "scripts" / "build_unsloth_notebook.py",
        ROOT_DIR / "scripts" / "build_unsloth_training_kernel.py",
    ):
        code = script_path.read_text(encoding="utf-8")
        for mod in ("q_proj", "v_proj", "o_proj"):
            assert f'"{mod}"' in code or f"'{mod}'" in code, f"Missing {mod} in {script_path.name}"
        assert '"k_proj"' not in code and "'k_proj'" not in code, f"Forbidden k_proj in {script_path.name}"
        assert "unsloth-bnb-4bit" not in code, f"Forbidden unsloth-bnb-4bit in {script_path.name}"
        assert "train_on_responses_only" not in code, f"Forbidden train_on_responses_only in {script_path.name}"
        assert "<start_of_turn>" not in code, f"Legacy <start_of_turn> in {script_path.name}"
        assert "add_special_tokens=False" in code, f"Missing add_special_tokens=False in {script_path.name}"
        assert "prefix_text" in code and "-100" in code, f"Missing prefix_text/-100 masking in {script_path.name}"
        assert "thinking_level" not in code, f"Forbidden thinking_level in {script_path.name}"
    assert "--preflight-probe" in CLOUD_SCRIPT.read_text(encoding="utf-8")


def test_dual_path_loader_and_vllm_normalizer_contract(tmp_path: Path = None) -> None:
    for script_path in (
        CLOUD_SCRIPT,
        ROOT_DIR / "scripts" / "build_unsloth_notebook.py",
        ROOT_DIR / "scripts" / "build_unsloth_training_kernel.py",
    ):
        code = script_path.read_text(encoding="utf-8")
        assert "google/gemma-4-31b-it-qat-w4a16-ct" in code, (
            f"Missing primary model google/gemma-4-31b-it-qat-w4a16-ct in {script_path.name}"
        )
        assert "google/gemma-4-31B-it-qat-q4_0-unquantized" in code, (
            f"Missing fallback model google/gemma-4-31B-it-qat-q4_0-unquantized in {script_path.name}"
        )
        assert "load_in_4bit=False" in code and "load_in_4bit=True" in code, (
            f"Missing dual-path loading (load_in_4bit=False and load_in_4bit=True) in {script_path.name}"
        )
        assert "bnb_4bit_use_double_quant=False" in code, (
            f"Missing bnb_4bit_use_double_quant=False in {script_path.name}"
        )
        assert "base_model.model.language_model.model.layers." in code, (
            f"Missing base_model.model.language_model.model.layers. in {script_path.name}"
        )

    import tempfile
    import torch
    from safetensors.torch import load_file, save_file
    from scripts.normalize_adapter_vllm import normalize_adapter_for_vllm

    if tmp_path is None:
        temp_dir_ctx = tempfile.TemporaryDirectory()
        test_dir = Path(temp_dir_ctx.name)
    else:
        temp_dir_ctx = None
        test_dir = Path(tmp_path)

    try:
        mock_config = {
            "r": 8,
            "lora_alpha": 16,
            "target_modules": ["q_proj", "v_proj", "o_proj"],
        }
        (test_dir / "adapter_config.json").write_text(json.dumps(mock_config, indent=2), encoding="utf-8")
        (test_dir / "tokenizer.model").write_text("dummy tokenizer binary content", encoding="utf-8")

        synthetic_tensors = {}
        for i in range(60):
            modules = ["q_proj", "o_proj"]
            if i % 6 != 5:
                modules.append("v_proj")
            for m in modules:
                for ab in ("lora_A", "lora_B"):
                    key = f"base_model.model.model.layers.{i}.self_attn.{m}.{ab}.weight"
                    synthetic_tensors[key] = torch.zeros((2, 2), dtype=torch.float32)

        assert len(synthetic_tensors) == 340
        save_file(synthetic_tensors, str(test_dir / "adapter_model.safetensors"), metadata={"format": "pt"})

        success, msg = normalize_adapter_for_vllm(test_dir)
        assert success is True, f"normalize_adapter_for_vllm failed: {msg}"

        remaining_files = sorted(p.name for p in test_dir.iterdir() if p.is_file())
        assert remaining_files == ["adapter_config.json", "adapter_model.safetensors"], (
            f"Unexpected files in adapter dir after normalization: {remaining_files}"
        )

        normalized_weights = load_file(str(test_dir / "adapter_model.safetensors"))
        assert len(normalized_weights) == 340
        target_prefix = "base_model.model.language_model.model.layers."
        for key, tensor in normalized_weights.items():
            assert key.startswith(target_prefix), f"Key {key} does not start with {target_prefix}"
            assert tensor.dtype == torch.bfloat16, f"Tensor {key} has dtype {tensor.dtype}, expected torch.bfloat16"

        with open(test_dir / "adapter_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        assert cfg.get("r") == 8
        assert cfg.get("lora_alpha") == 16
        assert sorted(cfg.get("target_modules", [])) == ["o_proj", "q_proj", "v_proj"]
    finally:
        if temp_dir_ctx is not None:
            temp_dir_ctx.cleanup()


def test_five_skill_translation_and_scratch_scrubbing() -> None:
    ctx = {"repro_files": {}}
    # 1. Scratch script creation is stored in context and dropped (returns None)
    res_create = translate_tool_call(
        "str_replace_editor",
        {"command": "create", "path": "/testbed/reproduce.py", "file_text": "assert 1 + 1 == 2\n"},
        context=ctx,
    )
    assert res_create is None
    assert "reproduce.py" in ctx["repro_files"]

    # 2. Executing tracked reproduce.py translates to repro-check with inline code
    res_repro = translate_tool_call("bash", {"command": "python /testbed/reproduce.py"}, context=ctx)
    assert res_repro == {
        "name": "run_skill_script",
        "arguments": {"skill_name": "repro-check", "file_path": "check.py", "args": ["assert 1 + 1 == 2\n"]},
    }

    # 3. Inline python -c with def/print (no assert) translates to code-oracle --eval, NOT code-map
    res_oracle = translate_tool_call("bash", {"command": 'python -c "def f(): return 42; print(f())"'}, context=ctx)
    assert res_oracle == {
        "name": "run_skill_script",
        "arguments": {
            "skill_name": "code-oracle",
            "file_path": "oracle.py",
            "args": ["--eval", "def f(): return 42; print(f())"],
        },
    }

    # 4. Grep for class/def translates to code-map --symbol
    res_map_sym = translate_tool_call("bash", {"command": 'grep -rn "class PromptBase" rich/'}, context=ctx)
    assert res_map_sym == {
        "name": "run_skill_script",
        "arguments": {"skill_name": "code-map", "file_path": "map.py", "args": ["--symbol", "PromptBase"]},
    }

    # 5. Keyword grep translates to fast-grep with pattern and path
    res_grep = translate_tool_call("bash", {"command": 'grep -rn "on_validate_error" rich/'}, context=ctx)
    assert res_grep == {
        "name": "run_skill_script",
        "arguments": {"skill_name": "fast-grep", "file_path": "grep.py", "args": ["on_validate_error", "rich/"]},
    }

    # 6. Git diff translates to test-gate --diff
    res_gate = translate_tool_call("bash", {"command": "git diff"}, context=ctx)
    assert res_gate == {
        "name": "run_skill_script",
        "arguments": {"skill_name": "test-gate", "file_path": "gate.py", "args": ["--diff"]},
    }


def test_five_test_alignment_dataset_and_collator_contract() -> None:
    five_test_train = ROOT_DIR / "data" / "unsloth_sft_5test" / "train.jsonl"
    assert five_test_train.exists() and five_test_train.stat().st_size > 0

    rows = [json.loads(line) for line in open(five_test_train, encoding="utf-8") if line.strip()]
    assert len(rows) >= 50

    skills_seen = set()
    for r in rows:
        assert r["full_text"].startswith(r["prefix_text"])
        comp = r["completion_text"]
        if "<|channel>thought" in comp:
            assert comp.startswith("<|channel>thought\n<channel|>")
        for sk in ("fast-grep", "code-map", "code-oracle", "repro-check", "test-gate"):
            if f'skill_name:<|"|>{sk}<|"|>' in comp:
                skills_seen.add(sk)
    assert skills_seen == {"fast-grep", "code-map", "code-oracle", "repro-check", "test-gate"}

    # Verify PrefixDeltaDataCollator equal-length -100 label padding in train_gemma4_unsloth_cloud.py
    cloud_code = CLOUD_SCRIPT.read_text(encoding="utf-8")
    assert "PrefixDeltaDataCollator" in cloud_code
    assert "batch_labels.append(labels + [-100] * pad_len)" in cloud_code
    assert "assert input_ids_tensor.shape == labels_tensor.shape" in cloud_code
    assert "--train-file" in cloud_code
    assert "--max-seq-length" in cloud_code
