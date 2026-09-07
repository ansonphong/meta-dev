"""Behavioral checks against actual renderer output, not filename conventions."""

from pathlib import Path
import subprocess

import pytest

from test_plan_artifact_render import base_ir, rich_ir, run_renderer, task


VALIDATOR = Path(__file__).resolve().parents[1] / "scripts/planner-validate.sh"


def render(tmp_path, layout="multi-phase", count=1, target="standard"):
    ir = rich_ir() if layout == "rich" else base_ir(layout)
    ir["target"] = target
    if layout != "rich":
        tasks = [task(f"T1.{index}", f"Outcome {index}", f"src/item{index}.py") for index in range(1, count + 1)]
        for item in tasks:
            item["files"].append(item["files"][0] + ".test.py")
        if layout == "multi-phase":
            ir["phases"] = [{"id": "1", "title": "Contract", "summary": "Verified anchors.", "tasks": tasks}]
        else:
            ir["tasks"] = tasks
    result = run_renderer(tmp_path, ir)
    assert result.returncode == 0, result.stderr
    artifact = tmp_path / ir["artifact_path"]
    detail = artifact / "01-contract.md" if artifact.is_dir() else artifact
    return artifact, detail


def validate(path):
    return subprocess.run(["bash", str(VALIDATOR), str(path)], capture_output=True, text=True)


@pytest.mark.parametrize("layout", ["multi-phase", "single-file", "rich"])
def test_accepts_rendered_layouts_with_declared_verification(tmp_path, layout):
    artifact, _ = render(tmp_path, layout)
    result = validate(artifact)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Scanned 1 task files, 1 tasks" in result.stdout


@pytest.mark.parametrize("target,count,code", [("lean", 6, 0), ("lean", 7, 1), ("standard", 4, 1), ("explicit", 4, 1)])
def test_phase_cap_inherits_master_target(tmp_path, target, count, code):
    artifact, _ = render(tmp_path, count=count, target=target)
    result = validate(artifact)
    assert result.returncode == code, result.stdout + result.stderr


def test_master_file_input_follows_arbitrary_phase_filename(tmp_path):
    artifact, _ = render(tmp_path)
    result = validate(artifact / "00-master-plan.md")
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("mutation,message", [
    (lambda text: text.replace("**Verify-After:**", "**Verify-Elsewhere:**"), "exactly one Verify-After"),
    (lambda text: text + "\n**Verify-After:**\n- `pytest src/item1.py.test.py -q`\n", "exactly one Verify-After"),
    (lambda text: text.replace("- `pytest src/item1.py.test.py -q` (focused)", ""), "empty verify-after"),
    (lambda text: text.replace("pytest src/item1.py.test.py -q", "npm run check"), "broad Verify"),
    (lambda text: text.replace("pytest src/item1.py.test.py -q", "pytest other/test_outside.py -q"), "unscoped Verify"),
    (lambda text: text.replace("pytest src/item1.py.test.py -q", "pytest src/item1.py.test.py other/test_outside.py -q"), "unscoped Verify"),
    (lambda text: text.replace("pytest src/item1.py.test.py -q", "pytest src/item1.py.test.py -k outcome -q"), "pytest -k"),
    (lambda text: text + "\n- [ ] unrelated checklist\n", "sole ledger"),
    (lambda text: text + "\nTODO: decide behavior\n", "placeholder"),
    (lambda text: text + "\n" + text, "duplicate task detail"),
])
def test_mutated_renderer_output_rejected(tmp_path, mutation, message):
    artifact, detail = render(tmp_path)
    detail.write_text(mutation(detail.read_text()))
    result = validate(artifact)
    assert result.returncode == 2, result.stdout + result.stderr
    assert message in result.stdout


def test_balanced_global_hook_counts_cannot_hide_missing_task_hook(tmp_path):
    artifact, detail = render(tmp_path, count=2)
    text = detail.read_text().replace("**Verify-After:**", "**Verify-Elsewhere:**", 1)
    detail.write_text(text + "\n**Verify-After:**\n- `pytest src/item2.py.test.py -q`\n")
    result = validate(artifact)
    assert result.returncode == 2
    assert result.stdout.count("exactly one Verify-After") == 2


def test_missing_phase_and_ledger_mismatch_are_errors(tmp_path):
    artifact, detail = render(tmp_path)
    detail.rename(artifact / "unlinked.md")
    result = validate(artifact)
    assert result.returncode == 2
    assert "missing phase file" in result.stdout
    assert "not linked by the master" in result.stdout


def test_ledger_requires_each_task_exactly_once(tmp_path):
    artifact, _ = render(tmp_path)
    master = artifact / "00-master-plan.md"
    master.write_text(master.read_text().replace("`T1.1`", "`T9.9`"))
    result = validate(artifact)
    assert result.returncode == 2
    assert "ledger must match" in result.stdout


def test_empty_directory_cannot_return_clean(tmp_path):
    result = validate(tmp_path)
    assert result.returncode == 2
    assert "no tasks scanned" in result.stdout


def test_single_file_checklist_cannot_silently_lose_all_task_rows(tmp_path):
    artifact, detail = render(tmp_path, "single-file")
    detail.write_text("\n".join(line for line in detail.read_text().splitlines() if not line.startswith("- [ ]")))
    result = validate(artifact)
    assert result.returncode == 2
    assert "ledger must match" in result.stdout


def test_fenced_examples_are_not_executable_tasks_or_placeholders(tmp_path):
    artifact, detail = render(tmp_path)
    detail.write_text(detail.read_text() + "\n```markdown\n### Task 9.9: TODO\nVerify-After:\n- `npm run check`\n```\n")
    result = validate(artifact)
    assert result.returncode == 0, result.stdout


def test_rich_verify_before_is_scoped_and_from_path_is_not_command(tmp_path):
    artifact, detail = render(tmp_path, "rich")
    text = detail.read_text().replace("python3 -m pytest backend/tests/test_prompt.py::test_interpolation_threshold -q", "npm run build", 1)
    detail.write_text(text)
    result = validate(artifact)
    assert result.returncode == 2
    assert "broad Verify command: npm run build" in result.stdout
    assert "Verify command: /workspace" not in result.stdout


def test_task_cannot_borrow_other_tasks_file_declarations(tmp_path):
    artifact, detail = render(tmp_path, count=2)
    text = detail.read_text().replace("pytest src/item1.py.test.py -q", "pytest src/item2.py.test.py -q")
    detail.write_text(text)
    result = validate(artifact)
    assert result.returncode == 2
    assert "T1.1: unscoped" in result.stdout


@pytest.mark.parametrize("dependency,message", [("T9.9", "missing task dependency"), ("T1.1", "self dependency")])
def test_loaded_markdown_dependency_references_are_validated(tmp_path, dependency, message):
    artifact, detail = render(tmp_path)
    detail.write_text(detail.read_text() + f"\n**Dependencies:**\n- {dependency}\n")
    result = validate(artifact)
    assert result.returncode == 2
    assert message in result.stdout


def test_loaded_markdown_dependency_cycle_is_rejected(tmp_path):
    artifact, detail = render(tmp_path, count=2)
    text = detail.read_text()
    text = text.replace("### Task 1.2", "**Dependencies:**\n- T1.2\n\n### Task 1.2")
    detail.write_text(text + "\n**Dependencies:**\n- T1.1\n")
    result = validate(artifact)
    assert result.returncode == 2
    assert "cycle blocks" in result.stdout
