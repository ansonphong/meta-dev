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
def files(root: Path): return sorted(p for p in root.rglob("*") if p.is_file())

def expected(root: Path):
    source = root / ".agents" / "skills"
    output = {}
    if source.is_symlink():
        raise ValueError(f"skill root symlink forbidden: {source}")
    if source.exists():
        for path in files(source):
            if path.is_symlink(): raise ValueError(f"source symlink forbidden: {path}")
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
    except ValueError as exc:
        print(str(exc), file=sys.stderr); return 1
    actual = {str(p.relative_to(destination)): sha(p) for p in files(destination) if p != manifest} if destination.exists() else {}
    recorded = json.loads(manifest.read_text()).get("files", {}) if manifest.exists() else None
    valid = actual == wanted and recorded == wanted and not any(p.is_symlink() for p in destination.rglob("*")) if destination.exists() else not wanted
    if args.check:
        if not valid: print("adapter mirrors differ from canonical source", file=sys.stderr)
        return 0 if valid else 1
    if destination.exists(): shutil.rmtree(destination)
    destination.mkdir(parents=True)
    source = root / ".agents" / "skills"
    if source.exists():
        for directory in sorted(p for p in source.rglob("*") if p.is_dir()):
            (destination / directory.relative_to(source)).mkdir(parents=True, exist_ok=True)
    for rel in wanted:
        origin, target = source / rel, destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
    manifest.write_text(json.dumps({"schema_version": 1, "files": wanted}, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__": raise SystemExit(main())
