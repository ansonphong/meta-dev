#!/usr/bin/env python3
"""Resolve a logical repo name (or the project root) to an absolute path.

Config file (JSON):
    { "root": "<abs or rel to config-file dir>", "repos": { "<name>": "<rel-to-root or abs>" } }

Discovery is deliberately **cwd-independent**. A conductor's shell keeps its cwd
across Bash calls, so a stray `cd child-repo/` re-points every worker dispatched
afterwards. The old discovery (`./.claude/meta-dev-repos.json`, relative to cwd)
made that worse: from inside a child repo NO name resolved, and callers silently
fell back to cwd — so `--repo www` would land a worker in the app repo. The
anchor must not depend on the thing it is anchoring.

Order (first hit wins):
    1. $META_DEV_REPOS_FILE                              explicit override
    2. $CLAUDE_PROJECT_DIR/.claude/meta-dev-repos.json
    3. walk UP from cwd to /, first .claude/meta-dev-repos.json wins

Usage:
    repo-topology.py <name>    -> abs path of that repo
    repo-topology.py --root    -> abs path of the project root
    repo-topology.py --list    -> "<name><TAB><abs path>" per known repo

Exit 0 with the path on stdout when resolved; exit 1 with empty stdout when not.
Callers MUST treat exit 1 as fatal and never fall back to cwd.

Built-in names "meta" and "root" resolve to the project root, so a project can
always name its meta layer without config. An explicit config entry overrides.

Stdlib only.
"""
import json
import os
import sys

CONFIG_RELPATH = os.path.join(".claude", "meta-dev-repos.json")
ROOT_ALIASES = ("meta", "root")


def find_config():
    """Locate the topology config without trusting cwd to be the project root."""
    env = os.environ.get("META_DEV_REPOS_FILE")
    if env and os.path.isfile(env):
        return env

    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        cand = os.path.join(proj, CONFIG_RELPATH)
        if os.path.isfile(cand):
            return cand

    # Walk up from cwd: a worker started inside 360-HEXTILE-APP still finds the
    # meta root's config, which is the whole point.
    cur = os.getcwd()
    while True:
        cand = os.path.join(cur, CONFIG_RELPATH)
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def load():
    """Return (root_abs, repos_dict), or (None, None) if no usable config."""
    cfg_path = find_config()
    if not cfg_path:
        return None, None
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except Exception:
        return None, None
    cfg_dir = os.path.dirname(os.path.abspath(cfg_path))
    root = cfg.get("root", ".")
    if not os.path.isabs(root):
        root = os.path.normpath(os.path.join(cfg_dir, root))
    return root, (cfg.get("repos") or {})


def resolve(name, root, repos):
    rel = repos.get(name)
    if rel is None:
        return root if name in ROOT_ALIASES else None
    return rel if os.path.isabs(rel) else os.path.normpath(os.path.join(root, rel))


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if not arg:
        return 1

    root, repos = load()
    if root is None:
        return 1

    if arg == "--root":
        if not os.path.isdir(root):
            return 1
        sys.stdout.write(root)
        return 0

    if arg == "--list":
        for name in sorted(set(repos) | set(ROOT_ALIASES)):
            path = resolve(name, root, repos)
            if path:
                sys.stdout.write("%s\t%s\n" % (name, path))
        return 0

    path = resolve(arg, root, repos)
    if not path or not os.path.isdir(path):
        return 1
    sys.stdout.write(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
