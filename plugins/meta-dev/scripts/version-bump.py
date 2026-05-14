#!/usr/bin/env python3
"""Bump version for a repo. Atomic: update all version_files + git tag."""
import json
import os
import re
import sys
import subprocess
import tempfile

VERSIONING_FILE = "plans/_dashboard/versioning.json"
DRY_RUN = "--dry-run" in sys.argv


def bump_semver(current: str, bump_type: str) -> str:
    major, minor, patch = map(int, current.split("."))
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:
        return f"{major}.{minor}.{patch + 1}"


def update_file(filepath: str, old_ver: str, new_ver: str):
    if not os.path.exists(filepath):
        print(f"  skip {filepath} (not found)")
        return
    with open(filepath) as f:
        content = f.read()
    if old_ver not in content:
        print(f"  warn: {old_ver} not found in {filepath}")
        return
    content = content.replace(old_ver, new_ver)
    if not DRY_RUN:
        with open(filepath, "w") as f:
            f.write(content)
    print(f"  {'[DRY]' if DRY_RUN else ''} update {filepath}: {old_ver} → {new_ver}")


def atomic_write_json(filepath: str, data: dict):
    """Write JSON atomically via tempfile + rename."""
    dirname = os.path.dirname(filepath) or "."
    os.makedirs(dirname, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dirname, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, filepath)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def main():
    if not os.path.exists(VERSIONING_FILE):
        print("No versioning.json found.")
        sys.exit(1)

    with open(VERSIONING_FILE) as f:
        data = json.load(f)

    repo_id = None
    bump_type = "patch"
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--repo":
            repo_id = args[i + 1]; i += 2
        elif args[i] == "--type":
            bump_type = args[i + 1]; i += 2
        elif args[i] == "--dry-run":
            i += 1
        else:
            i += 1

    repos = data.get("repos", [])
    if not repos:
        print("No repos configured.")
        return

    target = repos[0]
    if repo_id:
        for r in repos:
            if r["id"] == repo_id:
                target = r
                break

    old_ver = target["current_version"]
    new_ver = bump_semver(old_ver, bump_type)

    print(f"Bump {target['id']} ({target['name']}): {old_ver} → {new_ver} ({bump_type})")

    if not DRY_RUN:
        target["current_version"] = new_ver
        atomic_write_json(VERSIONING_FILE, data)

    for vf in target.get("version_files", []):
        update_file(vf, old_ver, new_ver)

    # Git tag
    prefix = target.get("git_tag_prefix", "v")
    tag = f"{prefix}{new_ver}"
    if not DRY_RUN:
        result = subprocess.run(
            ["git", "add", VERSIONING_FILE] + target.get("version_files", []),
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  warn: git add failed ({result.returncode}): {result.stderr.strip()}")

        result = subprocess.run(
            ["git", "commit", "-m", f"chore: bump {target['id']} to {new_ver}"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  warn: git commit failed ({result.returncode}): {result.stderr.strip()}")
        else:
            result = subprocess.run(["git", "tag", tag], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  warn: git tag failed: {result.stderr.strip()}")
            else:
                print(f"Tagged: {tag}")

    # Cascade to followers
    for r in repos:
        if r.get("follows") == target["id"] and not r.get("independent"):
            fmode = r.get("follows_mode", "patch")
            follower_new = bump_semver(r["current_version"], fmode)
            print(f"  Cascade: {r['id']} {r['current_version']} → {follower_new} ({fmode})")
            if not DRY_RUN:
                r["current_version"] = follower_new
                for vf in r.get("version_files", []):
                    update_file(vf, r.get("current_version", old_ver), follower_new)

    if not DRY_RUN:
        atomic_write_json(VERSIONING_FILE, data)


if __name__ == "__main__":
    main()
