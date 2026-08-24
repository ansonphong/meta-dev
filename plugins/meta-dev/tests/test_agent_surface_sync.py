from __future__ import annotations

from pathlib import Path
import subprocess
import sys


PLUGIN = Path(__file__).resolve().parents[1]
SYNC = PLUGIN / "scripts" / "sync-agent-skill-adapters.py"


def test_sync_rejects_symlinked_generated_adapter_root(tmp_path):
    root = tmp_path / "project"
    source = root / ".agents" / "skills" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
    target = tmp_path / "adapter-target"
    target.mkdir()
    destination = root / ".claude" / "skills"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(target, target_is_directory=True)

    result = subprocess.run(
        [sys.executable, str(SYNC), "--project-root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "generated adapter root symlink forbidden" in result.stderr


def test_sync_rejects_symlinked_claude_ancestor(tmp_path):
    root = tmp_path / "project"
    source = root / ".agents" / "skills" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
    target = root / "real" / ".claude"
    target.mkdir(parents=True)
    (root / ".claude").symlink_to(target, target_is_directory=True)

    result = subprocess.run(
        [sys.executable, str(SYNC), "--project-root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "generated adapter root symlink forbidden" in result.stderr


def test_sync_reports_file_shaped_canonical_skill_root_in_check_and_write_modes(tmp_path):
    root = tmp_path / "project"
    source = root / ".agents" / "skills"
    source.parent.mkdir(parents=True)
    source.write_text("not a directory\n", encoding="utf-8")

    for args in ((), ("--check",)):
        result = subprocess.run(
            [sys.executable, str(SYNC), "--project-root", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1
        assert "skill root must be a directory" in result.stderr
