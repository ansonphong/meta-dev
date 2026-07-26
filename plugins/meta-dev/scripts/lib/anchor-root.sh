#!/usr/bin/env bash
# ============================================================================
# anchor-root.sh — cd to the meta-dev project root. SOURCE THIS, don't run it.
#
# Most meta-dev scripts address state with project-root-relative paths
# ("plans/_dashboard/state.events.jsonl", "plans/", "plans/_archive/..."). That
# is only correct when cwd IS the project root. It usually is — until a
# conductor's shell keeps a `cd` into a child repository from an earlier Bash call, at
# which point every one of those paths silently retargets into the child repo:
# a second event log, a second inbox, a second claim registry, plans archived
# from a tree that has no plans. Nothing errors; the state just forks.
#
# That is not hypothetical — it can commit a state log and a stray plan into a
# child repository before this anchor exists.
#
# Sourcing this file cds to the project root (as found by repo-topology.py,
# which is itself cwd-independent), so those relative paths resolve to THE
# project no matter where the caller stood. With no topology config anywhere
# (meta-dev used standalone) cwd is left exactly as it was.
#
# Do NOT source this from:
#   • init-project.sh   — bootstraps a NEW root in cwd; anchoring would scaffold
#                         into an existing parent project instead.
#   • archive-guard.sh  — takes a caller-relative plan path as its argument.
# ============================================================================

_md_anchor_root() {
    local lib_dir plugin_root root
    lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
    # shellcheck source=plugin-root.sh
    source "$lib_dir/plugin-root.sh"
    plugin_root="$(_md_plugin_root)"
    root="$(python3 "$plugin_root/scripts/lib/repo-topology.py" --root 2>/dev/null || true)"
    if [ -n "$root" ] && [ -d "$root" ]; then
        cd "$root" || return 0
    fi
    return 0
}

_md_anchor_root
