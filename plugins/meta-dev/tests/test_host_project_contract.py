"""Focused contract tests for AGENTS-first project discovery and bootstrap."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
FIXTURES = PLUGIN_ROOT / "tests" / "fixtures" / "blank-project"
INIT = PLUGIN_ROOT / "scripts" / "init-project.sh"


def _identity(path: Path) -> tuple[int, int, str]:
    resolved = path.resolve()
    stat = resolved.stat()
    return stat.st_dev, stat.st_ino, hashlib.sha256(resolved.read_bytes()).hexdigest()


def _classify(root: Path) -> str:
    """Model the documented contract classifier without host-specific imports."""
    candidates = [path for path in root.iterdir() if path.name.casefold() == "agents.md"]
    canonical = root / "AGENTS.md"
    legacy = [root / "CLAUDE.md", root / ".claude" / "CLAUDE.md"]
    present_legacy = [path for path in legacy if path.is_file()]
    if not candidates and not present_legacy:
        return "missing"
    if canonical.is_file():
        others = [path for path in candidates if path != canonical]
        if others:
            canonical_identity = _identity(canonical)
            other_identities = [_identity(path) for path in others]
            if any(identity[:2] == canonical_identity[:2] for identity in other_identities):
                return "casefold_alias"
            if all(identity[2] == canonical_identity[2] for identity in other_identities):
                return "duplicate_copy"
            return "conflict"
        if any(path.read_text(encoding="utf-8") != "@../AGENTS.md\n" for path in present_legacy):
            return "conflict"
        return "canonical"
    return "legacy_only"


def _project(tmp_path: Path, name: str) -> Path:
    destination = tmp_path / name
    shutil.copytree(FIXTURES / name, destination)
    return destination


def test_contract_fixtures_distinguish_every_discovery_state(tmp_path):
    expected = {
        "agents-first": "canonical",
        "legacy-only": "legacy_only",
        "conflicting": "conflict",
        "missing": "missing",
        "root-claude": "legacy_only",
        "nested-claude-adapter": "canonical",
    }
    for name, state in expected.items():
        assert _classify(_project(tmp_path, name)) == state

    casefolded = _project(tmp_path, "case-folded")
    os.link(casefolded / "AGENTS.md", casefolded / "agents.md")
    assert _classify(casefolded) == "casefold_alias"


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
