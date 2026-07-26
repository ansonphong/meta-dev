#!/usr/bin/env python3
"""Resolve the host project root or a logical repository root.

Plugin root, project root, and repository root are deliberately separate: this
script belongs to the plugin; a topology file names the host project; a
``repos`` entry names a repository. Config schema:
``{"root": "<abs or rel to config dir>", "repos": {"slug": "path"}}``.

Discovery order: explicit ``META_DEV_REPOS_FILE``; neutral
``.meta-dev/repos.json``; legacy ``.claude/meta-dev-repos.json``. A configured
host root (``META_DEV_PROJECT_ROOT``, ``CLAUDE_PROJECT_DIR``, ``META_DEV_ROOT``)
is preferred. Ancestor walking remains only for standalone/legacy invocation.
When neutral and legacy files conflict, the chosen and shadowed files are
reported on stderr and available through ``--diagnose``.
"""
import json
import os
import sys

NEUTRAL_CONFIG_RELPATH = os.path.join(".meta-dev", "repos.json")
LEGACY_CONFIG_RELPATH = os.path.join(".claude", "meta-dev-repos.json")
ROOT_ALIASES = ("meta", "root")
PROJECT_ROOT_ENVS = ("META_DEV_PROJECT_ROOT", "CLAUDE_PROJECT_DIR", "META_DEV_ROOT")


def _existing(path):
    return path if path and os.path.isfile(path) else None


def _walk_for(relpath):
    """Nearest topology file above cwd; preserves legacy standalone behavior."""
    cur = os.path.abspath(os.getcwd())
    while True:
        found = _existing(os.path.join(cur, relpath))
        if found:
            return found
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _project_roots():
    seen = set()
    for name in PROJECT_ROOT_ENVS:
        value = os.environ.get(name)
        if value:
            root = os.path.abspath(value)
            if root not in seen:
                seen.add(root)
                yield root


def find_config():
    """Return ``(chosen_path, shadowed_paths)`` in documented precedence."""
    explicit = _existing(os.environ.get("META_DEV_REPOS_FILE"))
    if explicit:
        return os.path.abspath(explicit), []

    candidates = []
    configured_roots = tuple(_project_roots())
    # Examine all neutral candidates before legacy candidates. This prevents a
    # nearby old config from silently overriding a project's neutral contract.
    for relpath in (NEUTRAL_CONFIG_RELPATH, LEGACY_CONFIG_RELPATH):
        found = None
        for root in configured_roots:
            found = _existing(os.path.join(root, relpath))
            if found:
                break
        if not found and not configured_roots:
            found = _walk_for(relpath)
        if found:
            candidates.append(os.path.abspath(found))
    return (candidates[0], candidates[1:]) if candidates else (None, [])


def _report_conflict(chosen, shadowed):
    if shadowed:
        sys.stderr.write(
            "repo-topology: multiple topology files found; using %s; ignored %s\n"
            % (chosen, ", ".join(shadowed))
        )


def load():
    """Return ``(project_root, repos)`` or ``(None, None)`` if unusable."""
    explicit_config = _existing(os.environ.get("META_DEV_REPOS_FILE"))
    configured_root = os.environ.get("META_DEV_PROJECT_ROOT")
    if configured_root:
        configured_root = os.path.abspath(configured_root)
    cfg_path, shadowed = find_config()
    if not cfg_path:
        return (configured_root, {}) if configured_root else (None, None)
    _report_conflict(cfg_path, shadowed)
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError, TypeError):
        return None, None
    cfg_dir = os.path.dirname(cfg_path)
    root = cfg.get("root", ".")
    if not isinstance(root, str):
        return None, None
    if not os.path.isabs(root):
        root = os.path.normpath(os.path.join(cfg_dir, root))
    repos = cfg.get("repos") or {}
    if not isinstance(repos, dict):
        return None, None
    # META_DEV_PROJECT_ROOT pins the host boundary for discovered topology,
    # while an explicit META_DEV_REPOS_FILE remains an intentional override.
    return (configured_root if configured_root and not explicit_config else root, repos)


def resolve(name, root, repos):
    rel = repos.get(name)
    if rel is None:
        return root if name in ROOT_ALIASES else None
    if not isinstance(rel, str):
        return None
    return rel if os.path.isabs(rel) else os.path.normpath(os.path.join(root, rel))


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if not arg:
        return 1
    if arg == "--diagnose":
        chosen, shadowed = find_config()
        if not chosen:
            return 1
        sys.stdout.write("selected\t%s\n" % chosen)
        for path in shadowed:
            sys.stdout.write("shadowed\t%s\n" % path)
        return 0

    root, repos = load()
    if root is None:
        return 1
    if arg == "--root":
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
