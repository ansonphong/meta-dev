#!/usr/bin/env python3
"""Resolve a logical repo name to an absolute path from project topology config.

Config file (JSON): { "root": "<abs or rel to config-file dir>", "repos": { "<name>": "<rel-to-root or abs>" } }
Discovery: $META_DEV_REPOS_FILE, else ./.claude/meta-dev-repos.json. No config => empty output.
Stdlib only; never raises to the shell — prints "" and exits 0 on any problem.
"""
import json, os, sys

def find_config():
    env = os.environ.get("META_DEV_REPOS_FILE")
    if env and os.path.isfile(env):
        return env
    local = os.path.join(os.getcwd(), ".claude", "meta-dev-repos.json")
    return local if os.path.isfile(local) else None

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    cfg_path = find_config()
    if not cfg_path or not name:
        return
    try:
        cfg = json.load(open(cfg_path, encoding="utf-8"))
    except Exception:
        return
    cfg_dir = os.path.dirname(os.path.abspath(cfg_path))
    root = cfg.get("root", ".")
    root = root if os.path.isabs(root) else os.path.normpath(os.path.join(cfg_dir, root))
    rel = (cfg.get("repos") or {}).get(name)
    if not rel:
        return
    path = rel if os.path.isabs(rel) else os.path.normpath(os.path.join(root, rel))
    sys.stdout.write(path)

if __name__ == "__main__":
    main()
