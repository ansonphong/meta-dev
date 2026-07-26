"""Focused golden coverage for the host-neutral plan artifact renderer."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "plan-artifact-render.py"


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
    result = run_renderer(tmp_path, base_ir("multi-phase"))

    assert result.returncode == 0, result.stderr
    plan_dir = tmp_path / "plans/meta/renderer-contract"
    master = (plan_dir / "00-master-plan.md").read_text(encoding="utf-8")
    phase_one = (plan_dir / "01-contract.md").read_text(encoding="utf-8")
    phase_two = (plan_dir / "02-renderer.md").read_text(encoding="utf-8")

    assert master == """---
stage: 3
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
    result = run_renderer(tmp_path, base_ir("single-file"))

    assert result.returncode == 0, result.stderr
    artifact = (tmp_path / "plans/meta/renderer-contract.md").read_text(encoding="utf-8")
    assert artifact == """---
stage: 3
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


def test_invalid_ir_writes_no_partial_artifact(tmp_path: Path):
    ir = base_ir("multi-phase")
    ir["artifact_path"] = "../outside"

    result = run_renderer(tmp_path, ir)

    assert result.returncode == 2
    assert "without traversal" in result.stderr
    assert not (tmp_path / "plans").exists()
    assert not (tmp_path.parent / "outside").exists()


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
