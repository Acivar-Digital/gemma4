---
name: kaggle-submit
description: Playbook for validating, packaging, and submitting Google Gemma 4 Developer Agent competition submissions to the Kaggle Leaderboard. Use when preparing, checking, or executing Kaggle submissions, diagnosing submission failures, or preventing low-score regressions (such as the 0.03 score failure).
---

# Kaggle Leaderboard Submission Playbook (`kaggle-submit`)

This skill defines the mandatory protocol for submitting entries to the **Google Gemma 4 Developer Agent** Kaggle competition (`gemma-4-developer-agent`).

---

## 1. Post-Mortem: Why Past Submissions Scored 0.03

On 2026-10-02, submission `56765397` ("Submission v2: Rank-8 LoRA Adapter + 5-Skill Architecture") scored a catastrophic **0.03** (3% resolution rate) on the public leaderboard. 

Investigation revealed the root causes behind this and other low-score traps:

1. **Un-Trained / Placeholder LoRA Adapter**:
   - `agent.yaml` mounted `adapter: main_lora`, which contained un-trained 69 MB placeholder weights.
   - In ADK, declaring an adapter instructs the runtime to route queries through adapter hooks. On Kaggle's evaluation containers, this caused either invalid output generation or inference crashes on Turn 1.
   - **RULE:** Never submit an adapter unless it has been empirically verified to score $\ge 43.4\%$ on the 14-task local validation suite.
2. **Directory Nesting Defect**:
   - Packaging the directory `my_submission/` directly (e.g. `zip -r submission.zip my_submission/`) places `my_submission/agent.yaml` inside the archive instead of `agent.yaml` at the root.
   - The competition evaluator (`adk-submission`) expects `agent.yaml` strictly at the root of `submission.zip`. Root discovery failure causes immediate zero scores across all tasks.
3. **Test-File Pollution & Container B Discard**:
   - Agents that modify files in `tests/`, `test_*.py`, `conftest.py`, or `pyproject.toml` have their edits completely wiped by Container B's checkout before the evaluation test patch is applied.
   - If the agent "fixed" the problem by modifying a test, Container B discards the fix, leaving the unresolved bug and scoring 0.
4. **Budget Ladder Mismatch & Early Circuit-Breaking**:
   - Prompts configured with a 40-call budget while the harness enforces a 50-call limit caused agents to trip emergency fallback routines 10 turns prematurely, failing to complete complex multi-file fixes.
5. **Bytecode & OS Metadata Bloat**:
   - Including `__pycache__`, `.pyc`, and `.DS_Store` files pollutes the archive and risks import path collisions or container extraction errors.
6. **Direct Skill Invocation Hallucination Trap (`ValueError: Tool '<skill_name>' not found`)**:
   - In Google ADK's `SkillToolset`, skills (like `fast-grep` or `code-map`) are NOT exposed as direct top-level tools in `tools_dict`.
   - Instead, ADK provides meta-tools: `run_skill_script`, `list_skills`, `load_skill`, `load_skill_resource`.
   - If system instructions tell the model to call `fast-grep(...)` directly, the model emits `<|tool_call|fast-grep(...)>`, causing ADK to raise `ValueError: Tool 'fast-grep' not found` and aborting the turn.
   - **RULE:** Prompt instructions must strictly instruct the model to use either native tools (`read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`) or invoke skills via `run_skill_script(skill_name="...", script_name="...", ...)`.

---

## 2. The 9 Mandatory Pre-Submission Gates

Before ANY submission is sent to Kaggle, the candidate package MUST pass all 9 gates:

```text
[Gate 1: Root Layout] ─────► agent.yaml must be at the root of submission.zip
[Gate 2: LoRA Integrity] ───► NO un-trained adapters (Track 1 = pure declarative)
[Gate 3: Cleanliness] ─────► 0 .pyc, 0 .DS_Store, 0 ._*, size < 3 GiB
[Gate 4: YAML Schema] ─────► Passes compile_submission without errors
[Gate 5: Skill Spec] ──────► Directory names must match frontmatter 'name' (kebab-case)
[Gate 6: Patch Safety] ────► Instructions enforce /tmp for repro, zero edits to tests
[Gate 7: Budget Sync] ─────► 50-call ladder strictly synchronized with get_status()
[Gate 8: Tool/Skill API] ──► No hallucinated direct tool calls (skills invoked via run_skill_script)
[Gate 9: Preflight 6/6] ───► scripts/preflight_check.py passes 100%
```

### Detailed Gate Specifications

#### Gate 1: Root Layout Integrity
The root config MUST reside at the archive root. Run:
```bash
unzip -l submission.zip | grep -E "(^| )agent\.ya?ml$"
```
Expected output: exactly one matching line for `agent.yaml`.

#### Gate 2: LoRA Integrity Rule
- **Track 1 (Declarative Baseline):** `agent.yaml` MUST NOT contain `adapter:` lines, and no `adapters/` directory should be packaged.
- **Track 2 (Trained LoRA):** Only permitted if `adapter_model.safetensors` was trained and local validation achieved $\ge 43.4\%$ resolution rate.

#### Gate 3: Artifact Cleanliness & Hygiene
Run the hygiene verification script:
```bash
DS_COUNT=$(unzip -l submission.zip | grep -c "\.DS_Store" || true)
PYC_COUNT=$(unzip -l submission.zip | grep -c "\.pyc" || true)
DOT_COUNT=$(unzip -l submission.zip | grep -c "/\._" || true)
SIZE_MB=$(du -m submission.zip | cut -f1)

if [ "$DS_COUNT" -ne 0 ] || [ "$PYC_COUNT" -ne 0 ] || [ "$DOT_COUNT" -ne 0 ]; then
  echo "FAILED Gate 3: Archive contains metadata or bytecode artifacts!"
  exit 1
fi

if [ "$SIZE_MB" -ge 3072 ]; then
  echo "FAILED Gate 3: Archive exceeds 3 GiB limit ($SIZE_MB MB)"
  exit 1
fi
echo "PASSED Gate 3: Clean archive ($SIZE_MB MB)"
```

#### Gate 4: Sandboxed ADK Compilation
Compile using `adk-submission` inside the venv:
```bash
/private/tmp/brun/venv/bin/python -c "
from adk_submission.compiler import compile_submission
agent = compile_submission('my_submission')
print(f'Successfully compiled root agent: {agent.name}')
"
```

#### Gate 5: Skill Specification & Kebab-Case
Every subfolder in `skills/` must contain a `SKILL.md` with kebab-case YAML frontmatter matching its directory name:
```bash
for d in my_submission/skills/*; do
  [ -d "$d" ] || continue
  dirname=$(basename "$d")
  skill_name=$(grep -E "^name:" "$d/SKILL.md" | head -n1 | awk '{print $2}')
  if [ "$dirname" != "$skill_name" ]; then
    echo "FAILED Gate 5: Skill directory '$dirname' != frontmatter name '$skill_name'"
    exit 1
  fi
done
echo "PASSED Gate 5: All skills match kebab-case directory specifications."
```

#### Gate 6: Patch Safety & Container B Protection
Verify `my_submission/prompts/main.md` contains the mandatory Container B test protection warnings:
- Scratch repro files MUST go to `/tmp` (never `/workspace`).
- Edits to `tests/` or configuration files are strictly forbidden.

#### Gate 7: Budget Ladder Synchronization
Verify that `my_submission/prompts/main.md` paces the agent against the **50-call** ladder (matching `get_status()`), NOT 40 calls.

#### Gate 8: Tool & Skill Invocation Contract
Ensure instructions DO NOT instruct the model to call skill names directly as tools.
- Skills must be invoked via `run_skill_script(skill_name="...", script_name="...", ...)`.
- Native tools declared in `agent.yaml` (`read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`) are the only direct tool calls permitted.
- Verify that `prompts/main.md` contains zero instructions phrasing skills as direct functions like `fast-grep(...)` without `run_skill_script`.

#### Gate 9: Full Preflight Gate Execution
Run the complete environment preflight check:
```bash
/private/tmp/brun/venv/bin/python scripts/preflight_check.py
```
All 6/6 tiers must report `OK`.
All 6/6 tiers must report `OK`.

---

## 3. Packaging Protocol

To create a clean, 100% compliant `submission.zip`:

```bash
# 1. Purge all transient and cache files
find my_submission -name ".DS_Store" -delete 2>/dev/null || true
find my_submission -name "._*" -delete 2>/dev/null || true
find my_submission -name "*.pyc" -delete 2>/dev/null || true
find my_submission -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 2. Package from INSIDE the folder to ensure root-level structure
rm -f submission.zip
(cd my_submission && zip -r ../submission.zip . \
  -x "*.safetensors.bak" \
  -x "__pycache__/*" \
  -x "*.pyc" \
  -x ".DS_Store" \
  -x "*/.DS_Store" \
  -x "._*" \
  -x "*/._*" \
  -x ".git/*")

# 3. Print verification receipt
ls -lh submission.zip
shasum -a 256 submission.zip
```

---

## 4. Kaggle Leaderboard Submission Execution

### Check Quota Availability
Kaggle allows 5 submissions per 24-hour UTC window. Check submission history:
```bash
kaggle competitions submissions -c gemma-4-developer-agent | head -n 10
```

### Submit the Archive
Submit using the official CLI with a clear, descriptive message:
```bash
kaggle competitions submit \
  -c gemma-4-developer-agent \
  -f submission.zip \
  -m "Track 1 Baseline: Declarative Agent + 5-Skill Architecture (verified 50-call budget, clean root layout)"
```

### Monitor Submission Status
Kaggle takes 15–45 minutes to run the container evaluation:
```bash
kaggle competitions submissions -c gemma-4-developer-agent | head -n 5
```
Watch for `SubmissionStatus.COMPLETE` and verify that `publicScore` is updated.
