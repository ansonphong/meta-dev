#!/usr/bin/env python3
"""Render a validated Plan Artifact IR into deterministic Markdown artifacts.

The IR schema lives at ``schemas/plan-artifact.schema.json``. This program uses
only the standard library so Claude and Codex share the same validation and
rendering path. It intentionally does not mutate planctl state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


VERSION = "1.0"
LAYOUTS = {"multi-phase", "single-file"}
PATH_FIELDS = ("context", "docs", "depends", "blocks")
TASK_HANDLE = re.compile(r"^T[A-Za-z0-9]+\.[0-9]+$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PHASE_ID = re.compile(r"^[A-Za-z0-9]+$")
_BROAD_VERIFY = re.compile(
    r"(?:^|\s)(?:npm|pnpm|yarn)\s+(?:run\s+)?(?:check|build|test)(?:\s|$)|"
    r"(?:^|\s)(?:pytest|vitest|jest)(?:\s*$|\s+-k\b)|"
    r"(?:^|\s)(?:svelte-check|tsc)(?:\s|$)",
    re.IGNORECASE,
)
_CHECKBOX_ROW = re.compile(r"^\s*[-*+]\s+\[[ xX]\]")


class ValidationError(ValueError):
    """Collectable contract violations; no render starts when one is raised."""


def fail(errors: list[str], path: str, message: str) -> None:
    errors.append(f"{path}: {message}")


def is_project_relative(value: Any) -> bool:
    """Accept only slash-separated paths below the selected project root."""
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in ("", ".", "..") for part in path.parts) and not re.match(r"^[A-Za-z]:", value)


def text_list(value: Any, path: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        fail(errors, path, "must be an array")
        return []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            fail(errors, f"{path}[{index}]", "must be a non-empty string")
        elif any(_CHECKBOX_ROW.match(line) for line in item.splitlines()):
            fail(errors, f"{path}[{index}]", "must not contain a checkbox-shaped line")
    return value


def rendered_text(value: Any, path: str, errors: list[str]) -> None:
    """Reject input that could create a task ledger row outside the master."""
    if not isinstance(value, str) or not value.strip():
        fail(errors, path, "must be a non-empty string")
    elif any(_CHECKBOX_ROW.match(line) for line in value.splitlines()):
        fail(errors, path, "must not contain a checkbox-shaped line")


def path_list(value: Any, path: str, errors: list[str]) -> list[str]:
    items = text_list(value, path, errors)
    for index, item in enumerate(items):
        if not is_project_relative(item):
            fail(errors, f"{path}[{index}]", "must be a project-relative POSIX path without traversal")
    return items


def validate_task(task: Any, path: str, errors: list[str], handles: set[str]) -> None:
    if not isinstance(task, dict):
        fail(errors, path, "must be an object")
        return
    allowed = {"handle", "title", "description", "test", "dependencies", "files", "acceptance", "verify_after"}
    unknown = set(task) - allowed
    if unknown:
        fail(errors, path, f"contains unsupported fields: {', '.join(sorted(unknown))}")
    for key in allowed:
        if key not in task:
            fail(errors, path, f"missing required field {key!r}")
    handle = task.get("handle")
    if not isinstance(handle, str) or not TASK_HANDLE.fullmatch(handle):
        fail(errors, f"{path}.handle", "must be a stable handle like T1.1")
    elif handle in handles:
        fail(errors, f"{path}.handle", f"duplicate handle {handle}")
    else:
        handles.add(handle)
    for key in ("title", "description"):
        rendered_text(task.get(key), f"{path}.{key}", errors)
    if not isinstance(task.get("test"), bool):
        fail(errors, f"{path}.test", "must be boolean")
    text_list(task.get("dependencies"), f"{path}.dependencies", errors)
    path_list(task.get("files"), f"{path}.files", errors)
    text_list(task.get("acceptance"), f"{path}.acceptance", errors)
    verifies = task.get("verify_after")
    if not isinstance(verifies, list) or not verifies:
        fail(errors, f"{path}.verify_after", "must be a non-empty array")
        return
    for index, verify in enumerate(verifies):
        item_path = f"{path}.verify_after[{index}]"
        if not isinstance(verify, dict) or set(verify) != {"command", "scope"}:
            fail(errors, item_path, "must contain exactly command and scope")
            continue
        command, scope = verify["command"], verify["scope"]
        rendered_text(command, f"{item_path}.command", errors)
        if isinstance(command, str) and command.strip() and _BROAD_VERIFY.search(command):
            fail(errors, f"{item_path}.command", "must be a focused command, not a broad check")
        if scope not in {"focused", "scoped_check"}:
            fail(errors, f"{item_path}.scope", "must be focused or scoped_check")


def validate_ir(ir: Any) -> dict[str, Any]:
    """Validate the versioned IR before creating a staging directory or output."""
    errors: list[str] = []
    if not isinstance(ir, dict):
        raise ValidationError("IR: must be a JSON object")
    required = {"version", "layout", "artifact_path", "title", "slug", "repo", "stage", "context", "docs", "depends", "blocks", "why", "files", "acceptance", "loop_gap_baseline"}
    optional = {"phases", "tasks"}
    unknown = set(ir) - required - optional
    if unknown:
        fail(errors, "IR", f"contains unsupported fields: {', '.join(sorted(unknown))}")
    for key in required:
        if key not in ir:
            fail(errors, "IR", f"missing required field {key!r}")
    if ir.get("version") != VERSION:
        fail(errors, "IR.version", f"must equal {VERSION!r}")
    layout = ir.get("layout")
    if layout not in LAYOUTS:
        fail(errors, "IR.layout", "must be multi-phase or single-file")
    artifact_path = ir.get("artifact_path")
    if not is_project_relative(artifact_path):
        fail(errors, "IR.artifact_path", "must be a project-relative POSIX path without traversal")
    elif layout == "single-file" and not artifact_path.endswith(".md"):
        fail(errors, "IR.artifact_path", "single-file layout must end in .md")
    elif layout == "multi-phase" and artifact_path.endswith(".md"):
        fail(errors, "IR.artifact_path", "multi-phase layout must name a directory, not a .md file")
    for key in ("title", "why"):
        rendered_text(ir.get(key), f"IR.{key}", errors)
    if not isinstance(ir.get("slug"), str) or not SLUG.fullmatch(ir["slug"]):
        fail(errors, "IR.slug", "must be lowercase kebab-case")
    if not isinstance(ir.get("repo"), str) or not SLUG.fullmatch(ir["repo"]):
        fail(errors, "IR.repo", "must be a safe lowercase kebab-case slug")
    elif is_project_relative(artifact_path):
        artifact_parts = PurePosixPath(artifact_path).parts
        if len(artifact_parts) < 3 or artifact_parts[:2] != ("plans", ir["repo"]):
            fail(errors, "IR.artifact_path", "must be under plans/<repo>/ and match IR.repo")
    if not isinstance(ir.get("stage"), int) or not 1 <= ir["stage"] <= 6:
        fail(errors, "IR.stage", "must be an integer from 1 through 6")
    for key in PATH_FIELDS:
        path_list(ir.get(key), f"IR.{key}", errors)
    files = ir.get("files")
    if not isinstance(files, list):
        fail(errors, "IR.files", "must be an array")
    else:
        for index, file in enumerate(files):
            item_path = f"IR.files[{index}]"
            if not isinstance(file, dict) or set(file) != {"path", "action", "purpose"}:
                fail(errors, item_path, "must contain exactly path, action, and purpose")
                continue
            if not is_project_relative(file["path"]):
                fail(errors, f"{item_path}.path", "must be a project-relative POSIX path without traversal")
            if file["action"] not in {"create", "modify", "delete", "move"}:
                fail(errors, f"{item_path}.action", "must be create, modify, delete, or move")
            rendered_text(file["purpose"], f"{item_path}.purpose", errors)
    text_list(ir.get("acceptance"), "IR.acceptance", errors)
    baseline = ir.get("loop_gap_baseline")
    if not isinstance(baseline, dict) or set(baseline) != {"summary", "signatures", "affected_files", "prioritized_gaps"}:
        fail(errors, "IR.loop_gap_baseline", "must contain exactly summary, signatures, affected_files, and prioritized_gaps")
    else:
        rendered_text(baseline["summary"], "IR.loop_gap_baseline.summary", errors)
        text_list(baseline["signatures"], "IR.loop_gap_baseline.signatures", errors)
        path_list(baseline["affected_files"], "IR.loop_gap_baseline.affected_files", errors)
        text_list(baseline["prioritized_gaps"], "IR.loop_gap_baseline.prioritized_gaps", errors)
    handles: set[str] = set()
    if layout == "multi-phase":
        if "tasks" in ir:
            fail(errors, "IR.tasks", "is only allowed for single-file layout")
        phases = ir.get("phases")
        if not isinstance(phases, list) or not phases:
            fail(errors, "IR.phases", "must be a non-empty array")
        else:
            phase_ids: set[str] = set()
            for index, phase in enumerate(phases):
                phase_path = f"IR.phases[{index}]"
                if not isinstance(phase, dict) or set(phase) != {"id", "title", "summary", "tasks"}:
                    fail(errors, phase_path, "must contain exactly id, title, summary, and tasks")
                    continue
                phase_id = phase["id"]
                if not isinstance(phase_id, str) or not PHASE_ID.fullmatch(phase_id):
                    fail(errors, f"{phase_path}.id", "must be alphanumeric")
                elif phase_id in phase_ids:
                    fail(errors, f"{phase_path}.id", f"duplicate phase id {phase_id}")
                else:
                    phase_ids.add(phase_id)
                for key in ("title", "summary"):
                    rendered_text(phase[key], f"{phase_path}.{key}", errors)
                tasks = phase["tasks"]
                if not isinstance(tasks, list) or not tasks:
                    fail(errors, f"{phase_path}.tasks", "must be a non-empty array")
                else:
                    for task_index, task in enumerate(tasks):
                        validate_task(task, f"{phase_path}.tasks[{task_index}]", errors, handles)
    elif layout == "single-file":
        if "phases" in ir:
            fail(errors, "IR.phases", "is only allowed for multi-phase layout")
        tasks = ir.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            fail(errors, "IR.tasks", "must be a non-empty array")
        else:
            for index, task in enumerate(tasks):
                validate_task(task, f"IR.tasks[{index}]", errors, handles)
    if errors:
        raise ValidationError("\n".join(errors))
    return ir


def yaml_value(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_paths(values: list[str]) -> str:
    return "none" if not values else "[" + ", ".join(yaml_value(value) for value in values) + "]"


def frontmatter(ir: dict[str, Any]) -> list[str]:
    # status is deliberately absent: planctl derives it from stage + ledger state.
    return [
        "---",
        f"stage: {ir['stage']}",
        f"repo: {ir['repo']}",
        f"context: {yaml_paths(ir['context'])}",
        f"docs: {yaml_paths(ir['docs'])}",
        f"depends: {yaml_paths(ir['depends'])}",
        f"blocks: {yaml_paths(ir['blocks'])}",
        f"why: {yaml_value(ir['why'])}",
        "---",
        "",
    ]


def bead_for(handle: str, title: str) -> str:
    # Mirrors planctl.parse.compute_hex(): hash normalized checkbox rest without T handle.
    rest = f"`{handle}` **Task {handle}:** {title}"
    normalized = TASK_HANDLE.sub("", rest)
    normalized = " ".join(normalized.split()).casefold()
    return "#" + hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:4]


def lines_list(items: Iterable[str], prefix: str = "- ") -> list[str]:
    return [prefix + item for item in items]


def task_checkbox(task: dict[str, Any]) -> str:
    return f"- [ ] {bead_for(task['handle'], task['title'])} `{task['handle']}` **Task {task['handle']}:** {task['title']}"


def render_task_details(task: dict[str, Any]) -> list[str]:
    lines = [f"### Task {task['handle'][1:]}: {task['title']}", "", task["description"], "", f"**Test:** {'yes' if task['test'] else 'no'}", ""]
    if task["dependencies"]:
        lines += ["**Dependencies:**", *lines_list(task["dependencies"]), ""]
    if task["files"]:
        lines += ["**Files:**", *lines_list((f"`{path}`" for path in task["files"])), ""]
    lines += ["**Acceptance:**", *lines_list(task["acceptance"]), "", "**Verify-After:**"]
    lines += [f"- `{item['command']}` ({item['scope']})" for item in task["verify_after"]]
    return lines + [""]


def render_file_structure(files: list[dict[str, str]]) -> list[str]:
    lines = ["## File Structure", "", "| File | Action | Purpose |", "| --- | --- | --- |"]
    lines.extend(f"| `{item['path']}` | {item['action']} | {item['purpose']} |" for item in files)
    return lines + [""]


def render_master(ir: dict[str, Any], phase_names: list[tuple[dict[str, Any], str]]) -> str:
    lines = frontmatter(ir) + [f"# {ir['title']} — Master Plan", "", "## Task Checklist", ""]
    for phase, filename in phase_names:
        lines += [f"### Phase {phase['id']}: {phase['title']} ([`{filename}`]({filename}))", ""]
        lines.extend(task_checkbox(task) for task in phase["tasks"])
        lines.append("")
    lines += render_file_structure(ir["files"])
    lines += ["## Acceptance", "", *lines_list(ir["acceptance"]), "", "## Execution Rules", "", "- This master file is the sole checkbox ledger.", "- Use planctl to mutate task state; never hand-edit checkbox marks.", "- Phase files contain task detail and Verify-After hooks, but no checkboxes.", ""]
    return "\n".join(lines)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "phase"


def render_phase(phase: dict[str, Any]) -> str:
    lines = [f"# Phase {phase['id']}: {phase['title']}", "", "## Codebase Snapshot", "", phase["summary"], ""]
    for task in phase["tasks"]:
        lines += render_task_details(task)
    return "\n".join(lines)


def render_single(ir: dict[str, Any]) -> str:
    lines = frontmatter(ir) + [f"# {ir['title']}", "", "## Task Checklist", ""]
    lines.extend(task_checkbox(task) for task in ir["tasks"])
    lines += [""]
    for task in ir["tasks"]:
        lines += render_task_details(task)
    lines += render_file_structure(ir["files"])
    lines += ["## Acceptance", "", *lines_list(ir["acceptance"]), "", "## Loop-Gap Baseline", "", ir["loop_gap_baseline"]["summary"], ""]
    return "\n".join(lines)


def render_loop_gap(baseline: dict[str, Any]) -> str:
    lines = ["# Loop-Gap Configuration", "", "## Baseline", "", baseline["summary"], "", "## Signature Snapshots", ""]
    lines += lines_list(baseline["signatures"])
    lines += ["", "## Affected Files", ""]
    lines += lines_list((f"`{path}`" for path in baseline["affected_files"]))
    lines += ["", "## Prioritized Gap Categories", ""]
    lines += lines_list(baseline["prioritized_gaps"])
    return "\n".join(lines) + "\n"


def render_files(ir: dict[str, Any]) -> dict[PurePosixPath, str]:
    if ir["layout"] == "single-file":
        return {PurePosixPath(ir["artifact_path"]): render_single(ir) + "\n"}
    phase_names: list[tuple[dict[str, Any], str]] = []
    for index, phase in enumerate(ir["phases"], 1):
        phase_names.append((phase, f"{index:02d}-{slugify(phase['title'])}.md"))
    base = PurePosixPath(ir["artifact_path"])
    files = {base / "00-master-plan.md": render_master(ir, phase_names) + "\n"}
    for phase, filename in phase_names:
        files[base / filename] = render_phase(phase) + "\n"
    files[base / ".loop-gap-config.md"] = render_loop_gap(ir["loop_gap_baseline"])
    return files


def install(ir: dict[str, Any], project_root: Path, force: bool) -> list[Path]:
    """Stage complete output, then atomically install the plan artifact(s)."""
    rendered = render_files(ir)
    root = project_root.resolve()
    destinations = {relative: root.joinpath(*relative.parts) for relative in rendered}

    def assert_safe_ancestors() -> None:
        for destination in destinations.values():
            try:
                destination.parent.resolve(strict=False).relative_to(root)
            except ValueError as exc:
                raise ValidationError(
                    f"rendered path has a symlinked ancestor escaping project root: {destination}"
                ) from exc

    assert_safe_ancestors()
    artifact = root.joinpath(*PurePosixPath(ir["artifact_path"]).parts)
    artifact_exists = os.path.lexists(artifact)

    def assert_safe_existing_artifact() -> None:
        if not artifact_exists:
            return
        if artifact.is_symlink():
            raise ValidationError(f"refusing to replace symlinked artifact: {artifact}")
        if ir["layout"] == "multi-phase" and not artifact.is_dir():
            raise ValidationError(f"refusing to replace non-directory multi-phase artifact: {artifact}")
        if ir["layout"] == "single-file" and not artifact.is_file():
            raise ValidationError(f"refusing to replace non-file single-file artifact: {artifact}")
        try:
            artifact.resolve(strict=True).relative_to(root)
        except ValueError as exc:
            raise ValidationError(f"refusing to replace artifact outside project root: {artifact}") from exc

    if force:
        assert_safe_existing_artifact()
    if artifact_exists and not force:
        raise FileExistsError(f"refusing to overwrite existing artifact: {artifact}")
    if ir["layout"] == "multi-phase" and any(os.path.lexists(path) for path in destinations.values()) and not force:
        raise FileExistsError(f"refusing to overwrite existing artifact member under: {artifact}")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".plan-artifact-", dir=artifact.parent))
    try:
        if ir["layout"] == "multi-phase":
            staged_artifact = stage / "artifact"
            staged_artifact.mkdir()
            for relative, content in rendered.items():
                child = staged_artifact.joinpath(*relative.relative_to(PurePosixPath(ir["artifact_path"])).parts)
                child.parent.mkdir(parents=True, exist_ok=True)
                child.write_text(content, encoding="utf-8", newline="\n")
            backup = stage / "previous-artifact"
            if artifact_exists:
                os.replace(artifact, backup)
            try:
                assert_safe_ancestors()
                os.replace(staged_artifact, artifact)
            except OSError:
                if os.path.lexists(backup):
                    os.replace(backup, artifact)
                raise
        else:
            relative, content = next(iter(rendered.items()))
            staged_file = stage / relative.name
            staged_file.write_text(content, encoding="utf-8", newline="\n")
            backup = stage / "previous-artifact"
            if artifact_exists:
                os.replace(artifact, backup)
            try:
                assert_safe_ancestors()
                os.replace(staged_file, artifact)
            except OSError:
                if os.path.lexists(backup):
                    os.replace(backup, artifact)
                raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return [destinations[key] for key in sorted(rendered)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and render the Plan Artifact IR")
    parser.add_argument("ir", type=Path, help="path to a Plan Artifact IR JSON file")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="root that project-relative artifact paths resolve under")
    parser.add_argument("--validate", action="store_true", help="validate only; write no artifact")
    parser.add_argument("--force", action="store_true", help="allow replacement of an existing artifact")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        with args.ir.open(encoding="utf-8") as handle:
            ir = validate_ir(json.load(handle))
        if args.validate:
            print("plan artifact IR: valid")
            return 0
        written = install(ir, args.project_root, args.force)
        root = args.project_root.resolve()
        for path in written:
            print(path.relative_to(root).as_posix())
        return 0
    except (OSError, json.JSONDecodeError, ValidationError, FileExistsError) as exc:
        print(f"plan-artifact-render: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
