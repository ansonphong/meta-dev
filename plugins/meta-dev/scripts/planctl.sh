#!/usr/bin/env bash
# planctl.sh — bash shim → exec python3 -m planctl "$@"
#
# Resolves the plugin scripts dir from $0 (symlink-safe via readlink -f — the
# installed cache may live under a version-keyed path that is symlinked),
# prepends it to PYTHONPATH, then execs the planctl package. Works whether or
# not CLAUDE_PLUGIN_ROOT is set.
#
# Usage: planctl.sh <verb> [--json]
#
# Invocation standard (R11): from the meta-dev repo root,
#   bash plugins/meta-dev/scripts/planctl.sh <verb>
# or directly:
#   PYTHONPATH=plugins/meta-dev/scripts python3 -m planctl <verb>
set -euo pipefail

# Resolve this script's real location (follows symlinks). readlink -f is
# available on GNU/Linux (WSL2); fall back to a plain $0 if absent.
if command -v readlink >/dev/null 2>&1; then
  SCRIPT_PATH="$(readlink -f "$0")"
else
  SCRIPT_PATH="$0"
fi
SCRIPTS_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"

# Put the scripts dir (parent of the planctl/ package) on PYTHONPATH so
# `python3 -m planctl` finds the package. Prepend so we win over anything else.
export PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

exec python3 -m planctl "$@"
