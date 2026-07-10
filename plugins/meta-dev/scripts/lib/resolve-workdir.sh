#!/usr/bin/env bash
# ============================================================================
# resolve-workdir.sh — decide a headless worker's working directory.
#
# Sourced by claude-headless-exec / codex-headless-exec / grok-headless-exec,
# which previously carried three copies of the same block.
#
# THE LAW: a worker's cwd is set by the DISPATCH, never by the conductor's
# ambient shell. The conductor's shell keeps its cwd between Bash calls, so one
# stray `cd 360-HEXTILE-APP` used to silently re-point every worker launched
# afterwards — they would resolve `git rev-parse --show-toplevel` to the child
# repo and write plans into it. Two rules follow:
#
#   1. --repo <name> that does not resolve is FATAL. Never fall back to cwd.
#      The old fallback meant `--repo www` from an app-repo cwd ran in the app
#      repo, with only a warning on stderr that nobody reads.
#   2. No --repo => the PROJECT ROOT, not $(pwd). Deterministic anchor; it is
#      also where plans/ lives, which is what unqualified workers want.
#
# Only when there is no topology config at all (meta-dev used standalone,
# outside a project) do we fall back to cwd — and we say so.
#
# Contract:
#   in : $REPO (may be empty), $SCRIPT_DIR (dir holding lib/)
#   out: $WORK_DIR (abs), $REPO (label), $WORKDIR_ORIGIN (how it was decided)
# ============================================================================

resolve_workdir() {
    local topo="$SCRIPT_DIR/lib/repo-topology.py"
    local root=""

    if [[ ! -f "$topo" ]]; then
        echo "[headless] FATAL: missing $topo" >&2
        exit 1
    fi

    root="$(python3 "$topo" --root 2>/dev/null || true)"

    if [[ -n "$REPO" ]]; then
        local resolved
        if resolved="$(python3 "$topo" "$REPO" 2>/dev/null)" && [[ -n "$resolved" && -d "$resolved" ]]; then
            WORK_DIR="$resolved"
            WORKDIR_ORIGIN="--repo $REPO"
            return 0
        fi
        # Refuse to guess. Silently running in the wrong repo corrupts the tree.
        {
            echo "[headless] ABORT: --repo '$REPO' does not resolve to a directory."
            if [[ -n "$root" ]]; then
                echo "           Known repos (from ${META_DEV_REPOS_FILE:-<project>/.claude/meta-dev-repos.json}):"
                python3 "$topo" --list 2>/dev/null | sed 's/^/             - /' || true
            else
                echo "           No meta-dev topology config found. Looked for:"
                echo "             \$META_DEV_REPOS_FILE"
                echo "             \$CLAUDE_PROJECT_DIR/.claude/meta-dev-repos.json"
                echo "             .claude/meta-dev-repos.json in cwd and every parent"
            fi
            echo "           Not dispatching — a worker in the wrong repo writes to the wrong tree."
        } >&2
        exit 1
    fi

    if [[ -n "$root" && -d "$root" ]]; then
        WORK_DIR="$root"
        REPO="meta"
        WORKDIR_ORIGIN="project root (no --repo)"
        return 0
    fi

    # Standalone: no config anywhere. cwd is all we have; be explicit about it.
    WORK_DIR="$(pwd)"
    REPO="$(basename "$WORK_DIR")"
    WORKDIR_ORIGIN="cwd fallback — no topology config found"
    echo "[headless] WARN: no .claude/meta-dev-repos.json found; using cwd $WORK_DIR" >&2
    return 0
}
