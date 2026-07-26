#!/usr/bin/env bash
# Resolve the plugin root, not the host project or a named repository.
# Environment precedence is stable across runtime integrations; cwd is never an
# input. Source this file and call _md_plugin_root.

_md_plugin_root() {
    local configured lib_dir
    configured="${META_DEV_PLUGIN_ROOT:-${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}}"
    if [[ -n "$configured" ]]; then
        if [[ -d "$configured" ]]; then
            (cd "$configured" && pwd -P)
        else
            printf '%s\n' "$configured"
        fi
        return 0
    fi
    # lib/ → scripts/ → plugin root. BASH_SOURCE names this library even when
    # the consuming script was invoked from another directory.
    lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
    (cd "$lib_dir/../.." && pwd -P)
}
