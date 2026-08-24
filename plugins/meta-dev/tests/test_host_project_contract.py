"""Focused contract tests for AGENTS-first project discovery and bootstrap."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
FIXTURES = PLUGIN_ROOT / "tests" / "fixtures" / "blank-project"
INIT = PLUGIN_ROOT / "scripts" / "init-project.sh"
DOCTOR = PLUGIN_ROOT / "scripts" / "agent-surface-doctor.py"


def classify_contract(root: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(DOCTOR), "--project-root", str(root), "--classify"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return __import__("json").loads(result.stdout)["projects"][0]["contract"]


def classify(root: Path) -> str:
    return classify_contract(root)["state"]


def _project(tmp_path: Path, name: str) -> Path:
    destination = tmp_path / name
    shutil.copytree(FIXTURES / name, destination)
    return destination


def initialize(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INIT)], cwd=project, env=dict(os.environ, AUTO="true"),
        capture_output=True, text=True, check=False,
    )


def assert_instruction_check_passes(project: Path) -> None:
    result = subprocess.run(
        [str(PLUGIN_ROOT / "scripts" / "agent-surface-check"), "--project-root", str(project),
         "--scope-file", "AGENTS.md", "--check", "instructions"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_production_classifier_distinguishes_every_discovery_state(tmp_path):
    expected = {
        "agents-first": "canonical",
        "legacy-only": "compatibility",
        "conflicting": "conflict",
        "missing": "missing",
        "root-claude": "compatibility",
        "nested-claude-adapter": "adapter",
    }
    for name, state in expected.items():
        assert classify(_project(tmp_path, name)) == state

    casefolded = _project(tmp_path, "case-folded")
    os.link(casefolded / "AGENTS.md", casefolded / "agents.md")
    assert classify(casefolded) == "casefold_alias"


def test_initializer_emits_neutral_contract_and_warns_for_legacy_input(tmp_path):
    for name, legacy in (
        ("root-claude", Path("CLAUDE.md")),
        ("legacy-only", Path(".claude/CLAUDE.md")),
    ):
        project = _project(tmp_path, name)
        doctrine = (project / legacy).read_text(encoding="utf-8")
        result = initialize(project)

        assert result.returncode == 0, result.stderr
        assert (project / "AGENTS.md").read_text(encoding="utf-8") == doctrine
        assert not (project / "CLAUDE.md").exists()
        assert (project / ".claude" / "CLAUDE.md").read_text(encoding="utf-8") == "@../AGENTS.md\n"
        assert (project / "docs" / "agent-context").is_dir()
        assert (project / ".agents" / "skills").is_dir()
        assert "migration warning" in result.stdout.lower()
        assert classify(project) == "adapter"
        assert_instruction_check_passes(project)


def test_initializer_creates_thin_adapter_for_a_fresh_missing_project(tmp_path):
    project = tmp_path / "fresh"
    project.mkdir()

    result = initialize(project)

    assert result.returncode == 0, result.stderr
    assert (project / "AGENTS.md").is_file()
    assert not (project / "CLAUDE.md").exists()
    assert (project / ".claude" / "CLAUDE.md").read_bytes() == b"@../AGENTS.md\n"
    assert_instruction_check_passes(project)


def test_initializer_adds_adapter_to_canonical_project_without_overwriting_host_settings(tmp_path):
    project = tmp_path / "canonical"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Existing doctrine\n", encoding="utf-8")
    (project / ".claude").mkdir()
    settings = project / ".claude" / "settings.json"
    settings.write_text('{"preserve": true}\n', encoding="utf-8")

    result = initialize(project)

    assert result.returncode == 0, result.stderr
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == "# Existing doctrine\n"
    assert settings.read_text(encoding="utf-8") == '{"preserve": true}\n'
    assert not (project / "CLAUDE.md").exists()
    assert (project / ".claude" / "CLAUDE.md").read_bytes() == b"@../AGENTS.md\n"
    assert_instruction_check_passes(project)


def test_initializer_leaves_an_existing_exact_adapter_unchanged(tmp_path):
    project = tmp_path / "adapter"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Existing doctrine\n", encoding="utf-8")
    (project / ".claude").mkdir()
    adapter = project / ".claude" / "CLAUDE.md"
    adapter.write_bytes(b"@../AGENTS.md\n")
    before = adapter.stat().st_mtime_ns

    first = initialize(project)
    second = initialize(project)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert adapter.read_bytes() == b"@../AGENTS.md\n"
    assert adapter.stat().st_mtime_ns == before
    assert_instruction_check_passes(project)


def test_initializer_refuses_conflict_before_writing(tmp_path):
    project = _project(tmp_path, "conflicting")
    result = initialize(project)
    assert result.returncode == 1
    assert "refusing" in result.stderr.lower()
    assert not (project / "plans").exists()


def test_classifier_rejects_symlinked_claude_trees_before_initializer_writes(tmp_path):
    cases = []

    empty_ancestor = tmp_path / "empty-claude-ancestor"
    empty_ancestor.mkdir()
    empty_target = empty_ancestor / "target"
    empty_target.mkdir()
    (empty_ancestor / ".claude").symlink_to(empty_target, target_is_directory=True)
    cases.append((empty_ancestor, "claude_adapter_symlink"))

    adapter_skills = tmp_path / "adapter-skills"
    adapter_skills.mkdir()
    (adapter_skills / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    (adapter_skills / ".claude").mkdir()
    (adapter_skills / ".claude" / "CLAUDE.md").write_text("@../AGENTS.md\n", encoding="utf-8")
    skills_target = adapter_skills / "skills-target"
    skills_target.mkdir()
    (adapter_skills / ".claude" / "skills").symlink_to(skills_target, target_is_directory=True)
    cases.append((adapter_skills, "adapter_root_symlink"))

    for project, reason in cases:
        contract = classify_contract(project)
        assert contract["state"] == "conflict"
        assert contract["reason"] == reason

        result = initialize(project)

        assert result.returncode == 1
        assert "refusing" in result.stderr.lower()
        assert not (project / "plans").exists()
        assert not (project / ".agents").exists()


def test_initializer_refuses_symlinked_neutral_context_before_writing(tmp_path):
    cases = []

    docs_ancestor = tmp_path / "docs-ancestor"
    docs_ancestor.mkdir()
    docs_target = tmp_path / "docs-target"
    docs_target.mkdir()
    (docs_ancestor / "docs").symlink_to(docs_target, target_is_directory=True)
    cases.append((docs_ancestor, docs_target))

    context_leaf = tmp_path / "context-leaf"
    context_leaf.mkdir()
    (context_leaf / "docs").mkdir()
    context_target = tmp_path / "context-target"
    context_target.mkdir()
    (context_leaf / "docs" / "agent-context").symlink_to(context_target, target_is_directory=True)
    cases.append((context_leaf, context_target))

    for project, target in cases:
        contract = classify_contract(project)
        assert contract == {"state": "conflict", "reason": "context_symlink", "compatibility_inputs": []}

        result = initialize(project)

        assert result.returncode == 1
        assert "refusing" in result.stderr.lower()
        assert not (project / "plans").exists()
        assert not (project / "AGENTS.md").exists()
        assert not (project / ".agents").exists()
        assert not (project / ".claude").exists()
        assert not any(target.iterdir())


def test_initializer_preserves_both_regular_legacy_doctrines(tmp_path):
    project = tmp_path / "both-legacy"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# Root doctrine\n", encoding="utf-8")
    (project / ".claude").mkdir()
    (project / ".claude" / "CLAUDE.md").write_text("# Nested doctrine\n", encoding="utf-8")

    result = initialize(project)

    assert result.returncode == 0, result.stderr
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == (
        "# Root doctrine\n\n\n<!-- Migrated from .claude/CLAUDE.md -->\n\n# Nested doctrine\n"
    )
    assert not (project / "CLAUDE.md").exists()
    assert (project / ".claude" / "CLAUDE.md").read_bytes() == b"@../AGENTS.md\n"
    assert classify(project) == "adapter"
    assert_instruction_check_passes(project)


def test_repository_contract_has_one_canonical_doctrine_and_thin_claude_adapter():
    doctrine = REPO_ROOT / "AGENTS.md"
    adapter = REPO_ROOT / ".claude" / "CLAUDE.md"
    contract = PLUGIN_ROOT / "references" / "host-project-contract.md"

    assert doctrine.is_file()
    assert doctrine.stat().st_size <= 24_000
    assert len(doctrine.read_text(encoding="utf-8")) < 40_000
    assert not (REPO_ROOT / "CLAUDE.md").exists()
    assert adapter.read_text(encoding="utf-8") == "@../AGENTS.md\n"
    assert contract.is_file()
    assert not (PLUGIN_ROOT / "references" / "host-claude-contract.md").exists()
