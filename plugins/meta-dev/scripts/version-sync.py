#!/usr/bin/env python3
"""Detect and fix drift between versioning.json and actual version_files."""
import json
import os
import re
import sys

VERSIONING_FILE = "plans/_dashboard/versioning.json"
DRY_RUN = "--dry-run" in sys.argv


def extract_version(filepath: str) -> str | None:
    if not os.path.exists(filepath):
        return None
    with open(filepath) as f:
        content = f.read()
    # Match "version": "X.Y.Z" in JSON or __version__ = "X.Y.Z" in Python
    m = re.search(r'"version"\s*:\s*"(\d+\.\d+\.\d+)"', content)
    if m:
        return m.group(1)
    m = re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"', content)
    if m:
        return m.group(1)
    # package.json may use "version" key
    return None


def main():
    if not os.path.exists(VERSIONING_FILE):
        print("No versioning.json found.")
        sys.exit(1)

    with open(VERSIONING_FILE) as f:
        data = json.load(f)

    for repo in data.get("repos", []):
        declared = repo["current_version"]
        for vf in repo.get("version_files", []):
            actual = extract_version(vf)
            if actual is None:
                print(f"  {repo['id']}: {vf} — cannot read version")
                continue
            if actual != declared:
                print(f"  DRIFT {repo['id']}: {vf} has {actual}, versioning.json has {declared}")
                if not DRY_RUN:
                    print(f"    Fixing {vf}: {actual} → {declared}")
                    with open(vf) as f:
                        content = f.read()
                    content = content.replace(f'"{actual}"', f'"{declared}"')
                    with open(vf, "w") as f:
                        f.write(content)
            else:
                print(f"  OK {repo['id']}: {vf} = {declared}")


if __name__ == "__main__":
    main()
