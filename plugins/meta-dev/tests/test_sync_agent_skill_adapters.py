from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


PLUGIN = Path(__file__).resolve().parents[1]
SYNC = PLUGIN / "scripts" / "sync-agent-skill-adapters.py"


def test_sync_mirrors_complete_skill_and_detects_edits(tmp_path):
    root = tmp_path / "project"
    source = root / ".agents" / "skills" / "demo"
    (source / "references").mkdir(parents=True)
    (source / "scripts").mkdir()
    (source / "empty-resource").mkdir()
    (source / "SKILL.md").write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
    (source / "references" / "guide.md").write_text("guide\n", encoding="utf-8")
    script = source / "scripts" / "read.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o555)
    sync = subprocess.run([sys.executable, str(SYNC), "--project-root", str(root)], capture_output=True, text=True, check=False)
    assert sync.returncode == 0, sync.stderr
    mirror = root / ".claude" / "skills" / "demo"
    assert (mirror / "references" / "guide.md").read_text() == "guide\n"
    assert (mirror / "empty-resource").is_dir()
    assert not (mirror / "scripts" / "read.sh").is_symlink()
    assert (mirror / "scripts" / "read.sh").stat().st_mode & 0o111
    manifest = json.loads((root / ".claude" / "skills" / ".agent-skill-adapters.json").read_text(encoding="utf-8"))
    assert manifest["directories"] == ["demo", "demo/empty-resource", "demo/references", "demo/scripts"]
    assert subprocess.run([sys.executable, str(SYNC), "--project-root", str(root), "--check"], check=False).returncode == 0
    (mirror / "empty-resource").rmdir()
    assert subprocess.run([sys.executable, str(SYNC), "--project-root", str(root), "--check"], check=False).returncode == 1
    assert subprocess.run([sys.executable, str(SYNC), "--project-root", str(root)], check=False).returncode == 0
    (root / ".claude" / "skills" / "empty").mkdir()
    assert subprocess.run([sys.executable, str(SYNC), "--project-root", str(root), "--check"], check=False).returncode == 1
    (root / ".claude" / "skills" / "empty").rmdir()
    (mirror / "SKILL.md").write_text("edited\n", encoding="utf-8")
    assert subprocess.run([sys.executable, str(SYNC), "--project-root", str(root), "--check"], check=False).returncode == 1


def test_sync_rejects_symlinked_skill_root(tmp_path):
    root = tmp_path / "project"
    target = tmp_path / "target"
    target.mkdir()
    (root / ".agents").mkdir(parents=True)
    (root / ".agents" / "skills").symlink_to(target, target_is_directory=True)
    result = subprocess.run([sys.executable, str(SYNC), "--project-root", str(root)], capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "skill root symlink forbidden" in result.stderr


def test_sync_accepts_explicit_empty_generated_mirror(tmp_path):
    root = tmp_path / "project"
    destination = root / ".claude" / "skills"
    destination.mkdir(parents=True)
    (destination / ".agent-skill-adapters.json").write_text(
        '{"schema_version": 1, "directories": [], "files": {}}\n', encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, str(SYNC), "--project-root", str(root), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_sync_rejects_nested_canonical_directory_symlinks(tmp_path):
    for name in ("references", "scripts"):
        root = tmp_path / name
        source = root / ".agents" / "skills" / "demo"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: demo\n---\nbody\n", encoding="utf-8")
        target = tmp_path / f"{name}-target"
        target.mkdir()
        (target / "resource.txt").write_text("x\n", encoding="utf-8")
        (source / name).symlink_to(target, target_is_directory=True)

        result = subprocess.run(
            [sys.executable, str(SYNC), "--project-root", str(root)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1
        assert "source symlink forbidden" in result.stderr
