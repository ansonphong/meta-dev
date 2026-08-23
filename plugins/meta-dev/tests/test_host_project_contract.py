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


def classify(root: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(DOCTOR), "--project-root", str(root), "--classify"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return __import__("json").loads(result.stdout)["projects"][0]["contract"]["state"]


def _project(tmp_path: Path, name: str) -> Path:
    destination = tmp_path / name
    shutil.copytree(FIXTURES / name, destination)
    return destination


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
    project = _project(tmp_path, "legacy-only")
    result = subprocess.run(
        ["bash", str(INIT)], cwd=project, env=dict(os.environ, AUTO="true"),
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (project / "AGENTS.md").is_file()
    assert (project / "docs" / "agent-context").is_dir()
    assert (project / ".agents" / "skills").is_dir()
    assert "migration warning" in result.stdout.lower()


def test_initializer_refuses_conflict_before_writing(tmp_path):
    project = _project(tmp_path, "conflicting")
    result = subprocess.run(
        ["bash", str(INIT)], cwd=project, env=dict(os.environ, AUTO="true"),
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "refusing" in result.stderr.lower()
    assert not (project / "plans").exists()


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
