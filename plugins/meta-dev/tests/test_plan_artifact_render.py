"""Focused golden coverage for the host-neutral plan artifact renderer."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import jsonschema


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "plan-artifact-render.py"
SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "plan-artifact.schema.json"


def task(handle: str, title: str, path: str) -> dict:
    return {
        "handle": handle,
        "title": title,
        "description": f"Implement {title.lower()}.",
        "test": True,
        "dependencies": [],
        "files": [path],
        "acceptance": [f"{title} is complete."],
        "verify_after": [{"command": f"pytest {path}.test.py -q", "scope": "focused"}],
    }


def base_ir(layout: str) -> dict:
    ir = {
        "version": "1.0",
        "layout": layout,
        "artifact_path": "plans/meta/renderer-contract" + (".md" if layout == "single-file" else ""),
        "title": "Renderer Contract",
        "slug": "renderer-contract",
        "repo": "meta",
        "stage": 3,
        "context": [".claude/context/meta.md"],
        "docs": ["docs/contract.md"],
        "depends": ["plans/meta/previous.md"],
        "blocks": [],
        "why": "Keep Claude and Codex plan artifacts byte-stable.",
        "files": [{"path": "plugins/meta-dev/scripts/plan-artifact-render.py", "action": "create", "purpose": "Render the shared IR."}],
        "acceptance": ["Both hosts produce identical Markdown."],
        "loop_gap_baseline": {
            "summary": "Existing planner output has host-specific drift.",
            "signatures": ["render_plan(ir)"],
            "affected_files": ["plugins/meta-dev/commands/meta-planner.md"],
            "prioritized_gaps": ["Cross-host parity"],
        },
    }
    if layout == "multi-phase":
        ir["phases"] = [
            {"id": "1", "title": "Contract", "summary": "Confirm the host-neutral boundary.", "tasks": [task("T1.1", "Define IR", "plugins/meta-dev/schemas/plan-artifact.schema.json")]},
            {"id": "2", "title": "Renderer", "summary": "Render only after validation.", "tasks": [task("T2.1", "Write Renderer", "plugins/meta-dev/scripts/plan-artifact-render.py")]},
        ]
    else:
        ir["tasks"] = [task("T1.1", "Define IR", "plugins/meta-dev/schemas/plan-artifact.schema.json")]
    return ir


def rich_ir() -> dict:
    return {
        "version": "1.1",
        "layout": "single-file",
        "artifact_path": "plans/app/2026-07-25-prompt-controls.md",
        "title": "Prompt Controls",
        "slug": "prompt-controls",
        "repo": "app",
        "stage": 3,
        "context": ["app/.claude/context/prompt-system.md"],
        "docs": [],
        "depends": [],
        "blocks": [],
        "why": "Give a fresh worker enough verified context to implement safely.",
        "goal": "Add one processor-aware prompt cutoff without changing existing automatic outcomes.",
        "architecture": "Keep processor metadata authoritative and resolve the nullable setting at the shared interpolation boundary.",
        "tech_stack": ["Python/Pydantic backend", "Svelte 5 frontend"],
        "global_constraints": ["Preserve existing processor defaults.", "Use focused verification only."],
        "codebase_snapshot": {
            "revision": "app@abc1234; relevant files clean",
            "current_behavior": ["The persisted field uses 0.01 as both a value and a sentinel."],
            "anchors": ["backend/prompt.py::interpolate_prompts reads min_weight_threshold."],
            "data_flow": ["Saved config -> processor schema -> interpolate_prompts -> prompt weights."],
        },
        "decisions": ["Represent Auto as null; explicit 0.01 remains literal."],
        "non_goals": ["Do not add unrelated sampler controls."],
        "files": [
            {
                "path": "app/backend/prompt.py",
                "action": "modify",
                "purpose": "Resolve the automatic threshold at the shared boundary.",
            }
        ],
        "tasks": [
            {
                "handle": "T1.1",
                "title": "Define the nullable cutoff contract",
                "objective": "Make null mean Auto while preserving explicit numeric values.",
                "context": [
                    "InterpolationSettings currently defaults min_weight_threshold to 0.01.",
                    "interpolate_prompts is the only shared resolution boundary.",
                ],
                "test": True,
                "dependencies": [],
                "files": [
                    {
                        "path": "backend/prompt.py",
                        "action": "modify",
                        "purpose": "Resolve null against the processor default.",
                        "anchors": ["interpolate_prompts", "min_weight_threshold: float | None"],
                    },
                    {
                        "path": "backend/tests/test_prompt.py",
                        "action": "modify",
                        "purpose": "Lock Auto and explicit-value behavior.",
                        "anchors": ["test_interpolation_threshold"],
                    },
                ],
                "interfaces": {
                    "consumes": ["min_weight_threshold: float | None"],
                    "produces": ["effective_threshold: float"],
                },
                "steps": [
                    "Extend test_interpolation_threshold with null/0.15 and explicit-0.01/0.15-default cases.",
                    "Change interpolate_prompts so only None selects the processor default; never use truthiness.",
                ],
                "acceptance": ["Null resolves to the processor default and numeric zero remains literal."],
                "verify_before": [
                    {
                        "command": "python3 -m pytest backend/tests/test_prompt.py::test_interpolation_threshold -q",
                        "scope": "focused",
                        "expected": "FAIL because null is not yet resolved.",
                    }
                ],
                "verify_after": [
                    {
                        "command": "python3 -m pytest backend/tests/test_prompt.py::test_interpolation_threshold -q",
                        "scope": "focused",
                        "expected": "PASS with the Auto and explicit-value cases.",
                    }
                ],
                "commit": {
                    "repo_root": "/workspace/app",
                    "message": "feat: add processor-aware prompt cutoff",
                    "files": ["backend/prompt.py", "backend/tests/test_prompt.py"],
                },
            }
        ],
        "acceptance": ["A fresh worker can execute the task without conversation history."],
        "failure_modes": [
            {
                "failure": "Processor metadata is absent",
                "handling": "Use the documented compatibility default and do not crash.",
            }
        ],
        "blast_radius": ["Prompt interpolation only; no persistence schema outside the named field."],
        "rollback": ["Revert the nullable field and shared resolver in one path-scoped commit."],
    }


def run_renderer(tmp_path: Path, ir: dict, *, validate: bool = False, force: bool = False) -> subprocess.CompletedProcess[str]:
    source = tmp_path / "artifact.json"
    source.write_text(json.dumps(ir), encoding="utf-8")
    command = [sys.executable, str(SCRIPT), str(source), "--project-root", str(tmp_path)]
    if validate:
        command.append("--validate")
    if force:
        command.append("--force")
    return subprocess.run(command, text=True, capture_output=True, check=False)


def test_multi_phase_golden_artifact_has_one_checkbox_ledger(tmp_path: Path):
    ir = base_ir("multi-phase")
    jsonschema.validate(ir, json.loads(SCHEMA.read_text(encoding="utf-8")))
    result = run_renderer(tmp_path, ir)

    assert result.returncode == 0, result.stderr
    plan_dir = tmp_path / "plans/meta/renderer-contract"
    master = (plan_dir / "00-master-plan.md").read_text(encoding="utf-8")
    phase_one = (plan_dir / "01-contract.md").read_text(encoding="utf-8")
    phase_two = (plan_dir / "02-renderer.md").read_text(encoding="utf-8")

    assert master == """---
stage: 3
target: standard
repo: meta
context: [\".claude/context/meta.md\"]
docs: [\"docs/contract.md\"]
depends: [\"plans/meta/previous.md\"]
blocks: none
why: \"Keep Claude and Codex plan artifacts byte-stable.\"
---

# Renderer Contract — Master Plan

## Task Checklist

### Phase 1: Contract ([`01-contract.md`](01-contract.md))

- [ ] #fda7 `T1.1` **Task T1.1:** Define IR

### Phase 2: Renderer ([`02-renderer.md`](02-renderer.md))

- [ ] #3760 `T2.1` **Task T2.1:** Write Renderer

## File Structure

| File | Action | Purpose |
| --- | --- | --- |
| `plugins/meta-dev/scripts/plan-artifact-render.py` | create | Render the shared IR. |

## Acceptance

- Both hosts produce identical Markdown.

## Execution Rules

- This master file is the sole checkbox ledger.
- Use planctl to mutate task state; never hand-edit checkbox marks.
- Phase files contain task detail and Verify-After hooks, but no checkboxes.

"""
    assert "status:" not in master
    assert "- [ ]" not in phase_one
    assert "- [x]" not in phase_one
    assert "### Task 1.1: Define IR" in phase_one
    assert "### Task 2.1: Write Renderer" in phase_two
    assert (plan_dir / ".loop-gap-config.md").read_text(encoding="utf-8") == """# Loop-Gap Configuration

## Baseline

Existing planner output has host-specific drift.

## Signature Snapshots

- render_plan(ir)

## Affected Files

- `plugins/meta-dev/commands/meta-planner.md`

## Prioritized Gap Categories

- Cross-host parity
"""


def test_single_file_golden_artifact_is_compact_and_has_no_status(tmp_path: Path):
    ir = base_ir("single-file")
    jsonschema.validate(ir, json.loads(SCHEMA.read_text(encoding="utf-8")))
    result = run_renderer(tmp_path, ir)

    assert result.returncode == 0, result.stderr
    artifact = (tmp_path / "plans/meta/renderer-contract.md").read_text(encoding="utf-8")
    assert artifact == """---
stage: 3
target: standard
repo: meta
context: [\".claude/context/meta.md\"]
docs: [\"docs/contract.md\"]
depends: [\"plans/meta/previous.md\"]
blocks: none
why: \"Keep Claude and Codex plan artifacts byte-stable.\"
---

# Renderer Contract

## Task Checklist

- [ ] #fda7 `T1.1` **Task T1.1:** Define IR

### Task 1.1: Define IR

Implement define ir.

**Test:** yes

**Files:**
- `plugins/meta-dev/schemas/plan-artifact.schema.json`

**Acceptance:**
- Define IR is complete.

**Verify-After:**
- `pytest plugins/meta-dev/schemas/plan-artifact.schema.json.test.py -q` (focused)

## File Structure

| File | Action | Purpose |
| --- | --- | --- |
| `plugins/meta-dev/scripts/plan-artifact-render.py` | create | Render the shared IR. |

## Acceptance

- Both hosts produce identical Markdown.

## Loop-Gap Baseline

Existing planner output has host-specific drift.

"""
    assert "status:" not in artifact
    assert not (tmp_path / "plans/meta/renderer-contract").exists()


def test_v11_single_file_is_execution_grade_and_checkbox_free(tmp_path: Path):
    ir = rich_ir()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(ir, schema)

    result = run_renderer(tmp_path, ir)

    assert result.returncode == 0, result.stderr
    artifact = (tmp_path / ir["artifact_path"]).read_text(encoding="utf-8")
    for heading in (
        "## Outcome",
        "## Architecture",
        "## Codebase Ground Truth",
        "## Decisions",
        "## Non-Goals",
        "## Implementation Tasks",
        "## Failure Modes",
        "## Blast Radius",
        "## Rollback",
        "## Execution Handoff",
    ):
        assert heading in artifact
    assert "backend/prompt.py::interpolate_prompts" in artifact
    assert "min_weight_threshold: float \\| None" in artifact
    assert "Expected: FAIL because null is not yet resolved." in artifact
    assert "git -C /workspace/app commit --only -m 'feat: add processor-aware prompt cutoff' -- backend/prompt.py backend/tests/test_prompt.py" in artifact
    assert "status:" not in artifact
    assert "- [ ]" not in artifact
    assert "- [x]" not in artifact


def test_v11_rejects_thin_or_misplaced_plans_without_writing(tmp_path: Path):
    cases = []

    undated = rich_ir()
    undated["artifact_path"] = "plans/app/prompt-controls.md"
    cases.append((undated, "YYYY-MM-DD"))

    mismatched = rich_ir()
    mismatched["artifact_path"] = "plans/app/2026-07-25-other-slug.md"
    cases.append((mismatched, "must match IR.slug"))

    placeholder = rich_ir()
    placeholder["tasks"][0]["steps"][1] = "Add appropriate error handling."
    cases.append((placeholder, "placeholder language"))

    no_red = rich_ir()
    no_red["tasks"][0]["verify_before"] = []
    cases.append((no_red, "at least 1 item"))

    thin = rich_ir()
    thin["tasks"][0]["steps"] = ["Change it."]
    cases.append((thin, "at least 2 item"))

    relative_root = rich_ir()
    relative_root["tasks"][0]["commit"]["repo_root"] = "app"
    cases.append((relative_root, "absolute host path"))

    incomplete_commit = rich_ir()
    incomplete_commit["tasks"][0]["commit"]["files"] = ["backend/prompt.py"]
    cases.append((incomplete_commit, "exactly match"))

    for ir, expected in cases:
        result = run_renderer(tmp_path, ir, validate=True)
        assert result.returncode == 2
        assert expected in result.stderr
    assert not (tmp_path / "plans").exists()


def test_invalid_ir_writes_no_partial_artifact(tmp_path: Path):
    ir = base_ir("multi-phase")
    ir["artifact_path"] = "../outside"

    result = run_renderer(tmp_path, ir)

    assert result.returncode == 2
    assert "without traversal" in result.stderr
    assert not (tmp_path / "plans").exists()
    assert not (tmp_path.parent / "outside").exists()


def test_rejects_off_ledger_and_repo_mismatched_artifact_paths(tmp_path: Path):
    for artifact_path, expected in (
        ("docs/renderer-contract.md", "must be under plans/<repo>/"),
        ("plans/www/renderer-contract", "must be under plans/<repo>/"),
    ):
        ir = base_ir("multi-phase")
        ir["artifact_path"] = artifact_path
        result = run_renderer(tmp_path, ir)
        assert result.returncode == 2
        assert expected in result.stderr
    assert not (tmp_path / "plans").exists()


def test_rejects_symlinked_output_ancestor_escaping_project_root(tmp_path: Path):
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    (tmp_path / "plans").symlink_to(outside, target_is_directory=True)

    result = run_renderer(tmp_path, base_ir("multi-phase"))

    assert result.returncode == 2
    assert "symlinked ledger ancestor" in result.stderr
    assert not (outside / "meta" / "renderer-contract").exists()


def test_rejects_repo_ledger_symlink_into_another_ledger(tmp_path: Path):
    www_ledger = tmp_path / "plans" / "www"
    www_ledger.mkdir(parents=True)
    (tmp_path / "plans" / "meta").symlink_to(www_ledger, target_is_directory=True)

    result = run_renderer(tmp_path, base_ir("multi-phase"))

    assert result.returncode == 2
    assert "symlinked ledger ancestor" in result.stderr
    assert not (www_ledger / "renderer-contract").exists()


def test_accepts_arbitrary_safe_repo_slug_and_rejects_checkbox_in_phase_text(tmp_path: Path):
    ir = base_ir("multi-phase")
    ir["repo"] = "studio-api"
    ir["artifact_path"] = "plans/studio-api/renderer-contract"
    ir["phases"][0]["tasks"][0]["description"] = "Safe detail.\n- [ ] injected row"

    result = run_renderer(tmp_path, ir)

    assert result.returncode == 2
    assert "checkbox-shaped line" in result.stderr
    ir["phases"][0]["tasks"][0]["description"] = "Safe detail."
    result = run_renderer(tmp_path, ir)
    assert result.returncode == 0, result.stderr
    phase_files = (tmp_path / "plans" / "studio-api" / "renderer-contract").glob("0[1-9]-*.md")
    assert all("- [" not in path.read_text(encoding="utf-8") for path in phase_files)


def test_rejects_checkbox_rows_from_every_phase_free_form_field(tmp_path: Path):
    def injected(ir: dict, field: str) -> None:
        if field == "phase_title":
            ir["phases"][0]["title"] = "Contract\n- [ ] injected"
        elif field == "phase_summary":
            ir["phases"][0]["summary"] = "Snapshot\n- [ ] injected"
        elif field == "task_title":
            ir["phases"][0]["tasks"][0]["title"] = "Define IR\n- [ ] injected"
        elif field == "task_description":
            ir["phases"][0]["tasks"][0]["description"] = "Detail\n- [ ] injected"
        elif field == "dependency":
            ir["phases"][0]["tasks"][0]["dependencies"] = ["needs\n- [ ] injected"]
        elif field == "acceptance":
            ir["phases"][0]["tasks"][0]["acceptance"] = ["done\n- [ ] injected"]
        elif field == "verify":
            ir["phases"][0]["tasks"][0]["verify_after"][0]["command"] = "pytest one.py\n- [ ] injected"
        elif field == "baseline":
            ir["loop_gap_baseline"]["summary"] = "Baseline\n- [ ] injected"

    for field in ("phase_title", "phase_summary", "task_title", "task_description", "dependency", "acceptance", "verify", "baseline"):
        ir = base_ir("multi-phase")
        injected(ir, field)
        result = run_renderer(tmp_path, ir, validate=True)
        assert result.returncode == 2, field
        assert "checkbox-shaped line" in result.stderr


def test_repeat_render_is_deterministic(tmp_path: Path):
    ir = base_ir("multi-phase")
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()

    first = run_renderer(first_root, copy.deepcopy(ir))
    second = run_renderer(second_root, copy.deepcopy(ir))

    assert first.returncode == second.returncode == 0
    first_dir = first_root / "plans/meta/renderer-contract"
    second_dir = second_root / "plans/meta/renderer-contract"
    first_files = sorted(path.relative_to(first_dir) for path in first_dir.rglob("*") if path.is_file())
    second_files = sorted(path.relative_to(second_dir) for path in second_dir.rglob("*") if path.is_file())
    assert first_files == second_files
    assert [(path, (first_dir / path).read_bytes()) for path in first_files] == [(path, (second_dir / path).read_bytes()) for path in second_files]

    refused = run_renderer(first_root, copy.deepcopy(ir))
    forced = run_renderer(first_root, copy.deepcopy(ir), force=True)
    assert refused.returncode == 2
    assert "refusing to overwrite" in refused.stderr
    assert forced.returncode == 0, forced.stderr
    assert [(path, (first_dir / path).read_bytes()) for path in first_files] == [(path, (second_dir / path).read_bytes()) for path in second_files]


def test_force_refuses_to_replace_a_symlinked_artifact(tmp_path: Path):
    ir = base_ir("multi-phase")
    artifact = tmp_path / ir["artifact_path"]
    target = tmp_path / "safe-target"
    target.mkdir()
    artifact.parent.mkdir(parents=True)
    artifact.symlink_to(target, target_is_directory=True)

    result = run_renderer(tmp_path, ir, force=True)

    assert result.returncode == 2
    assert "refusing to replace symlinked artifact" in result.stderr
    assert artifact.is_symlink()
    assert not (target / "00-master-plan.md").exists()
