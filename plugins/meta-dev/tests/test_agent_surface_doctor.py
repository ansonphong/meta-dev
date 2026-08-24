from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
DOCTOR = PLUGIN / "scripts" / "agent-surface-doctor.py"
CHECK = PLUGIN / "scripts" / "agent-surface-check"


def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    (root / ".claude").mkdir()
    (root / ".claude" / "CLAUDE.md").write_text("@../AGENTS.md\n", encoding="utf-8")
    (root / "docs" / "agent-context").mkdir(parents=True)
    (root / "docs" / "agent-context" / "note.md").write_text("context\n", encoding="utf-8")
    (root / ".agents" / "skills" / "demo" / "references").mkdir(parents=True)
    (root / ".agents" / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
    (root / ".agents" / "skills" / "demo" / "references" / "note.md").write_text("x\n", encoding="utf-8")
    return root


def run(*args: str):
    return subprocess.run([sys.executable, str(DOCTOR), *args], capture_output=True, text=True, check=False)


def write_generated_adapters(root: Path) -> Path:
    source = root / ".agents" / "skills"
    destination = root / ".claude" / "skills"
    files = {}
    directories = []
    for origin in source.rglob("*"):
        relative = origin.relative_to(source)
        if origin.is_dir():
            (destination / relative).mkdir(parents=True, exist_ok=True)
            directories.append(relative.as_posix())
            continue
        if origin.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(origin.read_bytes())
            files[relative.as_posix()] = hashlib.sha256(origin.read_bytes()).hexdigest()
    (destination / ".agent-skill-adapters.json").write_text(
        json.dumps({"schema_version": 1, "directories": sorted(directories), "files": files}, sort_keys=True), encoding="utf-8"
    )
    return destination


def test_doctor_reports_stable_json_and_boundaries(tmp_path):
    root = project(tmp_path)
    stable = run("--project-root", str(root), "--check", "instructions", "--check", "context")
    assert stable.returncode == 0, stable.stderr
    report = json.loads(stable.stdout)
    assert report["ok"] is True
    assert report["projects"][0]["agents"]["bytes"] == 6
    assert report["projects"][0]["agents"]["characters"] == 6

    (root / "AGENTS.md").write_bytes(b"a" * 23999)
    pass_boundary = run("--project-root", str(root), "--check", "instructions")
    assert pass_boundary.returncode == 0, pass_boundary.stderr
    pass_report = json.loads(pass_boundary.stdout)
    assert pass_report["projects"][0]["agents"]["bytes"] == 23999
    assert pass_report["projects"][0]["agents"]["characters"] == 23999
    assert all(finding["code"] != "agents_bytes" for finding in pass_report["projects"][0]["findings"])

    (root / "AGENTS.md").write_bytes(b"a" * 24000)
    pass_boundary = run("--project-root", str(root), "--check", "instructions")
    assert pass_boundary.returncode == 0, pass_boundary.stderr
    pass_report = json.loads(pass_boundary.stdout)
    assert pass_report["projects"][0]["agents"]["bytes"] == 24000
    assert pass_report["projects"][0]["agents"]["characters"] == 24000
    assert all(finding["code"] != "agents_bytes" for finding in pass_report["projects"][0]["findings"])

    (root / "AGENTS.md").write_bytes(b"a" * 24001)
    fail_boundary = run("--project-root", str(root), "--check", "instructions")
    assert fail_boundary.returncode == 1, fail_boundary.stderr
    fail_report = json.loads(fail_boundary.stdout)
    assert fail_report["projects"][0]["agents"]["bytes"] == 24001
    assert fail_report["projects"][0]["agents"]["characters"] == 24001
    assert any(finding["code"] == "agents_bytes" for finding in fail_report["projects"][0]["findings"])

    (root / "AGENTS.md").write_text("🧩" * 39999, encoding="utf-8")
    near_char_limit = run("--project-root", str(root), "--check", "instructions")
    assert near_char_limit.returncode == 1, near_char_limit.stderr
    near_report = json.loads(near_char_limit.stdout)
    assert near_report["projects"][0]["agents"]["characters"] == 39999
    assert all(finding["code"] != "agents_characters" for finding in near_report["projects"][0]["findings"])

    (root / "AGENTS.md").write_text("🧩" * 40000, encoding="utf-8")
    at_char_limit = run("--project-root", str(root), "--check", "instructions")
    assert at_char_limit.returncode == 1, at_char_limit.stderr
    at_report = json.loads(at_char_limit.stdout)
    assert at_report["projects"][0]["agents"]["characters"] == 40000
    assert any(finding["code"] == "agents_characters" for finding in at_report["projects"][0]["findings"])


def test_case_fold_alias_and_symlink_root(tmp_path):
    root = project(tmp_path)
    accepted = subprocess.run([str(CHECK), "--project-root", str(root), "--scope-file", "AGENTS.md", "--check", "instructions"], capture_output=True, text=True, check=False)
    assert accepted.returncode == 0, accepted.stderr
    (root / "agents.md").write_text("other\n", encoding="utf-8")
    assert run("--project-root", str(root), "--check", "case-fold").returncode == 1
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    rejected = subprocess.run([str(CHECK), "--project-root", str(root), "--scope-file", str(outside)], capture_output=True, text=True, check=False)
    assert rejected.returncode == 2


def test_case_fold_alias_recognizes_case_insensitive_inodes():
    mount = Path("/mnt/d")
    if not mount.is_dir():
        pytest.skip("/mnt/d is not available for case-insensitive alias fixture")
    with tempfile.TemporaryDirectory(dir=mount, prefix="agent-surface-doctor-") as tmp_root:
        root = project(Path(tmp_root))
        agents = root / "AGENTS.md"
        alias = root / "agents.md"
        alias.write_text(agents.read_text(encoding="utf-8"), encoding="utf-8")
        same_inode = (agents.stat().st_dev, agents.stat().st_ino) == (alias.stat().st_dev, alias.stat().st_ino)

        result = run("--project-root", str(root), "--check", "case-fold")
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        findings = report["projects"][0]["findings"]
        codes = {finding["code"] for finding in findings}

        if same_inode:
            assert "casefold_alias" in codes
            assert "conflict" not in codes
        else:
            assert "duplicate_copy" in codes


def test_case_conflict_and_scope_wrapper(tmp_path):
    root = project(tmp_path)
    accepted = subprocess.run([str(CHECK), "--project-root", str(root), "--scope-file", "AGENTS.md", "--check", "instructions"], capture_output=True, text=True, check=False)
    assert accepted.returncode == 0, accepted.stderr
    (root / "agents.md").write_text("other\n", encoding="utf-8")
    assert run("--project-root", str(root), "--check", "case-fold").returncode == 1
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    rejected = subprocess.run([str(CHECK), "--project-root", str(root), "--scope-file", str(outside)], capture_output=True, text=True, check=False)
    assert rejected.returncode == 2


def test_scope_wrapper_rejects_nonexistent_file_and_binds_doctor_scope(tmp_path):
    root = project(tmp_path)
    missing = subprocess.run(
        [str(CHECK), "--project-root", str(root), "--scope-file", "missing.md", "--check", "instructions"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode == 2
    assert "existing regular file" in missing.stderr

    accepted = subprocess.run(
        [str(CHECK), "--project-root", str(root), "--scope-file", "AGENTS.md", "--check", "instructions"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert accepted.returncode == 0, accepted.stderr
    assert json.loads(accepted.stdout)["scope_files"] == [(root / "AGENTS.md").as_posix()]


def test_doctor_rejects_symlinked_adapter_root_and_missing_manifest(tmp_path):
    root = project(tmp_path)
    adapter_root = root / ".claude" / "skills"
    target = tmp_path / "adapter-target"
    target.mkdir()
    adapter_root.symlink_to(target, target_is_directory=True)

    symlinked = run("--project-root", str(root), "--check", "adapters")
    assert symlinked.returncode == 1, symlinked.stderr
    assert "adapter_root_symlink" in symlinked.stdout

    adapter_root.unlink()
    missing = run("--project-root", str(root), "--check", "adapters")
    assert missing.returncode == 1, missing.stderr
    assert "adapter_manifest" in missing.stdout


def test_doctor_allows_missing_generated_adapters_without_canonical_skills(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    (root / ".claude").mkdir()
    (root / ".claude" / "CLAUDE.md").write_text("@../AGENTS.md\n", encoding="utf-8")

    result = run("--project-root", str(root), "--check", "adapters")

    assert result.returncode == 0, result.stderr


def test_doctor_requires_manifest_for_empty_adapter_root_and_accepts_explicit_empty_mirror(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    (root / ".claude" / "skills").mkdir(parents=True)
    (root / ".claude" / "CLAUDE.md").write_text("@../AGENTS.md\n", encoding="utf-8")

    orphan = run("--project-root", str(root), "--check", "adapters")
    assert orphan.returncode == 1, orphan.stderr
    assert "adapter_manifest" in orphan.stdout

    manifest = root / ".claude" / "skills" / ".agent-skill-adapters.json"
    manifest.write_text(json.dumps({"schema_version": 1, "directories": [], "files": {}}), encoding="utf-8")
    explicit_empty = run("--project-root", str(root), "--check", "adapters")
    assert explicit_empty.returncode == 0, explicit_empty.stderr

    manifest.write_text(json.dumps({"schema_version": 1, "files": {}}), encoding="utf-8")
    missing_directories = run("--project-root", str(root), "--check", "adapters")
    assert missing_directories.returncode == 1, missing_directories.stderr
    assert "adapter_manifest" in missing_directories.stdout


def test_doctor_requires_complete_canonical_directory_mirror(tmp_path):
    root = project(tmp_path)
    source = root / ".agents" / "skills" / "demo" / "empty-resource"
    source.mkdir()
    destination = write_generated_adapters(root)

    valid = run("--project-root", str(root), "--check", "adapters")
    assert valid.returncode == 0, valid.stderr

    (destination / "demo" / "empty-resource").rmdir()
    missing = run("--project-root", str(root), "--check", "adapters")
    assert missing.returncode == 1, missing.stderr
    assert "adapter_mismatch" in missing.stdout


def test_doctor_reports_file_shaped_canonical_skill_root_as_json(tmp_path):
    root = project(tmp_path)
    shutil.rmtree(root / ".agents" / "skills")
    (root / ".agents" / "skills").write_text("not a directory\n", encoding="utf-8")

    for check in ("skills", "adapters"):
        result = run("--project-root", str(root), "--check", check)
        assert result.returncode == 1, result.stderr
        report = json.loads(result.stdout)
        assert report["checks"] == [check]
        assert any(finding["code"] == "skill_root" for finding in report["projects"][0]["findings"])


def test_doctor_rejects_nonregular_manifest_and_undeclared_adapter_entries(tmp_path):
    manifest_case = tmp_path / "manifest"
    manifest_case.mkdir()
    manifest_root = project(manifest_case)
    manifest_destination = write_generated_adapters(manifest_root)
    manifest = manifest_destination / ".agent-skill-adapters.json"
    manifest_target = tmp_path / "manifest-target.json"
    manifest_target.write_bytes(manifest.read_bytes())
    manifest.unlink()
    manifest.symlink_to(manifest_target)
    manifest_result = run("--project-root", str(manifest_root), "--check", "adapters")
    assert manifest_result.returncode == 1, manifest_result.stderr
    assert "adapter_manifest" in manifest_result.stdout

    for name, make_entry in (
        ("file", lambda destination: (destination / "hand-authored.md").write_text("x\n", encoding="utf-8")),
        ("directory", lambda destination: (destination / "empty").mkdir()),
        ("symlink-directory", lambda destination: (destination / "linked").symlink_to(tmp_path, target_is_directory=True)),
    ):
        case = tmp_path / name
        case.mkdir()
        root = project(case)
        destination = write_generated_adapters(root)
        make_entry(destination)
        result = run("--project-root", str(root), "--check", "adapters")
        assert result.returncode == 1, result.stderr
        assert "adapter_unexpected" in result.stdout


def test_manifest_escape_and_skill_root_symlink_are_rejected(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    root = project(workspace)
    manifest = workspace / "repos.json"
    manifest.write_text(json.dumps({"repositories": {"bad": "../../outside"}}), encoding="utf-8")
    escaped = run("--manifest", "repos.json", "--workspace-root", str(workspace))
    assert escaped.returncode == 2

    outside_manifest = tmp_path / "outside.json"
    outside_manifest.write_text(json.dumps({"repositories": {}}), encoding="utf-8")
    direct_escape = run("--manifest", "../outside.json", "--workspace-root", str(workspace))
    assert direct_escape.returncode == 2
    wrapped_escape = subprocess.run(
        [str(CHECK), "--manifest", "../outside.json", "--workspace-root", str(workspace), "--scope-file", "AGENTS.md"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert wrapped_escape.returncode == 2

    shutil_target = workspace / "skills-target"
    shutil_target.mkdir()
    shutil.rmtree(root / ".agents" / "skills")
    (root / ".agents" / "skills").symlink_to(shutil_target, target_is_directory=True)
    symlinked = run("--project-root", str(root), "--check", "skills")
    assert symlinked.returncode == 1
    assert "skill_root_symlink" in symlinked.stdout


def test_doctor_rejects_symlinked_repository_ancestors(tmp_path):
    agents_case = tmp_path / "agents-ancestor"
    agents_case.mkdir()
    agents_root = project(agents_case)
    agents_target = agents_root / "real" / ".agents"
    agents_target.mkdir(parents=True)
    shutil.rmtree(agents_root / ".agents")
    (agents_root / ".agents").symlink_to(agents_target, target_is_directory=True)

    skills = run("--project-root", str(agents_root), "--check", "skills")
    assert skills.returncode == 1, skills.stderr
    assert "skill_root_symlink" in skills.stdout

    claude_case = tmp_path / "claude-ancestor"
    claude_case.mkdir()
    claude_root = project(claude_case)
    claude_target = claude_root / "real" / ".claude"
    shutil.copytree(claude_root / ".claude", claude_target)
    shutil.rmtree(claude_root / ".claude")
    (claude_root / ".claude").symlink_to(claude_target, target_is_directory=True)

    instructions = run("--project-root", str(claude_root), "--check", "instructions")
    assert instructions.returncode == 1, instructions.stderr
    assert "claude_adapter_symlink" in instructions.stdout
    adapters = run("--project-root", str(claude_root), "--check", "adapters")
    assert adapters.returncode == 1, adapters.stderr
    assert "adapter_root_symlink" in adapters.stdout


def test_doctor_rejects_symlinked_context_ancestors(tmp_path):
    root = project(tmp_path)
    target = root / "real" / "docs"
    shutil.copytree(root / "docs", target)
    shutil.rmtree(root / "docs")
    (root / "docs").symlink_to(target, target_is_directory=True)

    result = run("--project-root", str(root), "--check", "context")

    assert result.returncode == 1, result.stderr
    assert "context_symlink" in result.stdout


def test_scope_symlink_ancestors_are_rejected_by_doctor_and_wrapper(tmp_path):
    root = project(tmp_path)
    target = root / "real" / "docs"
    shutil.copytree(root / "docs", target)
    shutil.rmtree(root / "docs")
    (root / "docs").symlink_to(target, target_is_directory=True)
    scope = "docs/agent-context/note.md"

    direct = run("--project-root", str(root), "--scope-file", scope, "--check", "context")
    assert direct.returncode == 2
    assert "scope path contains a symlink component" in direct.stderr

    wrapped = subprocess.run(
        [str(CHECK), "--project-root", str(root), "--scope-file", scope, "--check", "context"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert wrapped.returncode == 2
    assert "scope path contains a symlink component" in wrapped.stderr


def test_legacy_symlink_candidates_are_conflicts_without_agents(tmp_path):
    for legacy in (Path("CLAUDE.md"), Path(".claude") / "CLAUDE.md"):
        root = tmp_path / legacy.parts[0]
        root.mkdir()
        target = tmp_path / f"{legacy.parts[0]}-target.md"
        target.write_text("legacy\n", encoding="utf-8")
        path = root / legacy
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)

        result = run("--project-root", str(root), "--classify")
        assert result.returncode == 0, result.stderr
        contract = json.loads(result.stdout)["projects"][0]["contract"]
        assert contract["state"] == "conflict"
        assert contract["reason"] == "legacy_symlink"

        init = subprocess.run(
            ["bash", str(PLUGIN / "scripts" / "init-project.sh")], cwd=root,
            env={**os.environ, "AUTO": "true"}, capture_output=True, text=True, check=False,
        )
        assert init.returncode == 1
        assert not (root / "plans").exists()


def capability_manifest(tmp_path: Path) -> Path:
    root = project(tmp_path)
    manifest = {
        "repositories": {"demo": "project"},
        "host_capability_matrix": {
            "official_discovery_semantics": {
                "codex": {"source": "codex docs", "behavior": "reads AGENTS.md"},
                "claude_code": {"source": "claude docs", "behavior": "reads CLAUDE.md"},
                "grok": {"source": "grok docs", "behavior": "imports compatible skills"},
            },
            "live_grok_inspect": {
                "command": "grok inspect",
                "version": "1.0.5",
                "workspace_relative_cwd": ".",
                "project_instructions": ["AGENTS.md is canonical", "CLAUDE.md remains compatible"],
                "settings_source": ".claude/settings.local.json",
                "skills_summary": "one project skill",
                "observed_on": "2026-08-23",
            },
            "case_folded_aliases": {
                "demo": {"case_fold": "demo", "classification": "unique_ascii_lowercase"},
            },
        },
        "entries": [
            {
                "repository": "demo",
                "path": ".claude/settings.local.json",
                "tracked": True,
                "consumers": ["Claude Code", "Grok"],
                "grok_compatibility": "Grok reads compatible settings",
                "disposition": "host_runtime",
            },
            {
                "repository": "demo",
                "path": ".claude/commands/demo.md",
                "tracked": True,
                "consumers": ["Claude Code", "Grok"],
                "grok_compatibility": "Grok imports compatible commands",
                "disposition": "generated_adapter",
            },
            {
                "repository": "demo",
                "path": ".agents/skills/demo/SKILL.md",
                "tracked": True,
                "consumers": ["Codex", "Grok"],
                "grok_compatibility": "Grok uses the generated compatible adapter",
                "disposition": "canonical",
            },
        ],
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def run_capabilities(tmp_path: Path, manifest: Path):
    return run("--manifest", manifest.name, "--workspace-root", str(tmp_path), "--check", "capabilities")


def test_doctor_validates_a_representative_capability_matrix(tmp_path):
    manifest = capability_manifest(tmp_path)

    result = run_capabilities(tmp_path, manifest)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True


def test_doctor_reports_missing_or_malformed_capability_matrix_fields(tmp_path):
    manifest = capability_manifest(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    del data["host_capability_matrix"]["official_discovery_semantics"]["codex"]["source"]
    data["host_capability_matrix"]["live_grok_inspect"]["project_instructions"] = "AGENTS.md and CLAUDE.md"
    manifest.write_text(json.dumps(data), encoding="utf-8")

    result = run_capabilities(tmp_path, manifest)

    assert result.returncode == 1, result.stderr
    assert "capability_matrix" in result.stdout
    assert "official_discovery_semantics.codex" in result.stdout
    assert "project_instructions" in result.stdout


def test_doctor_reports_case_folded_alias_mismatch(tmp_path):
    manifest = capability_manifest(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["host_capability_matrix"]["case_folded_aliases"]["demo"]["case_fold"] = "wrong"
    manifest.write_text(json.dumps(data), encoding="utf-8")

    result = run_capabilities(tmp_path, manifest)

    assert result.returncode == 1, result.stderr
    assert "case_folded_aliases.demo" in result.stdout


def test_doctor_reports_vendor_capability_metadata_mismatch(tmp_path):
    manifest = capability_manifest(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    command = data["entries"][1]
    command["consumers"] = ["Claude Code"]
    command["grok_compatibility"] = ""
    command["disposition"] = "unknown"
    manifest.write_text(json.dumps(data), encoding="utf-8")

    result = run_capabilities(tmp_path, manifest)

    assert result.returncode == 1, result.stderr
    assert "vendor entry .claude/commands/demo.md requires grok_compatibility" in result.stdout
    assert "tracked Grok-discovered entry .claude/commands/demo.md must include Grok" in result.stdout
