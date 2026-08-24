#!/usr/bin/env python3
"""Materialize canonical .agents skills for hosts that require .claude skills."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


def sha(path: Path): return hashlib.sha256(path.read_bytes()).hexdigest()


def first_repository_symlink(root: Path, path: Path):
    """Return a symlink component below root without inspecting root ancestry."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    current = root
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            return current
    return None


def regular_files(root: Path, label: str):
    """Collect regular files without traversing or accepting symlinks."""
    result = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_symlink():
            raise ValueError(f"{label} symlink forbidden: {path}")
        if path.is_dir():
            result.extend(regular_files(path, label))
        elif path.is_file():
            result.append(path)
    return result


def regular_directories(root: Path, label: str):
    """Collect regular descendant directories and reject symlink entries."""
    result = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_symlink():
            raise ValueError(f"{label} symlink forbidden: {path}")
        if path.is_dir():
            result.append(path)
            result.extend(regular_directories(path, label))
    return result


def expected(root: Path):
    """Return the complete canonical tree, relative to its skill root."""
    source = root / ".agents" / "skills"
    files = {}
    directories = []
    if symlink := first_repository_symlink(root, source):
        raise ValueError(f"skill root symlink forbidden: {symlink}")
    if source.exists() and not source.is_dir():
        raise ValueError(f"skill root must be a directory: {source}")
    if source.exists():
        directories = [str(path.relative_to(source)) for path in regular_directories(source, "source")]
        for path in regular_files(source, "source"):
            files[str(path.relative_to(source))] = sha(path)
    return files, sorted(directories)


def recorded_tree(manifest: Path):
    """Read a complete adapter manifest or return ``None`` when it is invalid."""
    if not manifest.is_file() or manifest.is_symlink():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    files = data.get("files")
    directories = data.get("directories")
    if not isinstance(files, dict) or not isinstance(directories, list):
        return None
    if not all(isinstance(path, str) for path in directories):
        return None
    return files, directories

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    destination = root / ".claude" / "skills"
    manifest = destination / ".agent-skill-adapters.json"
    if symlink := first_repository_symlink(root, destination):
        print(f"generated adapter root symlink forbidden: {symlink}", file=sys.stderr)
        return 1
    if destination.exists() and not destination.is_dir():
        print(f"generated adapter root must be a directory: {destination}", file=sys.stderr)
        return 1
    try:
        wanted_files, wanted_directories = expected(root)
        destination_files = regular_files(destination, "generated adapter") if destination.exists() else []
        destination_directories = regular_directories(destination, "generated adapter") if destination.exists() else []
    except ValueError as exc:
        print(str(exc), file=sys.stderr); return 1
    actual_files = {str(p.relative_to(destination)): sha(p) for p in destination_files if p != manifest}
    actual_directories = {str(path.relative_to(destination)) for path in destination_directories}
    recorded = recorded_tree(manifest)
    valid = (
        actual_files == wanted_files
        and actual_directories == set(wanted_directories)
        and recorded == (wanted_files, wanted_directories)
        if destination.exists() else not wanted_files and not wanted_directories
    )
    if args.check:
        if not valid: print("adapter mirrors differ from canonical source", file=sys.stderr)
        return 0 if valid else 1
    if destination.exists(): shutil.rmtree(destination)
    destination.mkdir(parents=True)
    source = root / ".agents" / "skills"
    for rel in wanted_directories:
        (destination / rel).mkdir(parents=True, exist_ok=True)
    for rel in wanted_files:
        origin, target = source / rel, destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
    manifest.write_text(
        json.dumps({"schema_version": 1, "directories": wanted_directories, "files": wanted_files}, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0

if __name__ == "__main__": raise SystemExit(main())
