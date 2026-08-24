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

def expected(root: Path):
    source = root / ".agents" / "skills"
    output = {}
    if source.is_symlink():
        raise ValueError(f"skill root symlink forbidden: {source}")
    if source.exists():
        for path in regular_files(source, "source"):
            output[str(path.relative_to(source))] = sha(path)
    return output

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    destination = root / ".claude" / "skills"
    manifest = destination / ".agent-skill-adapters.json"
    if destination.is_symlink():
        print(f"generated adapter root symlink forbidden: {destination}", file=sys.stderr)
        return 1
    try:
        wanted = expected(root)
        destination_files = regular_files(destination, "generated adapter") if destination.exists() else []
    except ValueError as exc:
        print(str(exc), file=sys.stderr); return 1
    actual = {str(p.relative_to(destination)): sha(p) for p in destination_files if p != manifest}
    recorded = json.loads(manifest.read_text()).get("files", {}) if manifest.exists() else None
    valid = actual == wanted and recorded == wanted if destination.exists() else not wanted
    if args.check:
        if not valid: print("adapter mirrors differ from canonical source", file=sys.stderr)
        return 0 if valid else 1
    if destination.exists(): shutil.rmtree(destination)
    destination.mkdir(parents=True)
    source = root / ".agents" / "skills"
    for rel in wanted:
        origin, target = source / rel, destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
    manifest.write_text(json.dumps({"schema_version": 1, "files": wanted}, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__": raise SystemExit(main())
