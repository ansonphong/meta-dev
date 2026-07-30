#!/usr/bin/env bash
# Refresh the installed meta-dev plugin in Codex from the git marketplace.
#
# Codex has no auto-update for plugins: `codex plugin marketplace upgrade` must
# be run by hand, and it REFUSES the refresh if the snapshot's marketplace name
# differs from the configured one. This script does the whole cycle and reports
# the version actually installed, so a stale cache can never hide.
#
# The Claude Code side is separate: `/plugin marketplace update meta-dev` +
# `/plugin install meta-dev@meta-dev` inside a Claude session.
#
# Usage:
#   bash plugins/meta-dev/scripts/plugin-refresh.sh [marketplace] [plugin]
set -euo pipefail

MARKETPLACE="${1:-meta-dev}"
PLUGIN="${2:-meta-dev}"
PLUGIN_ID="${PLUGIN}@${MARKETPLACE}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"

if ! command -v codex >/dev/null 2>&1; then
  echo "plugin-refresh: codex CLI not on PATH" >&2
  exit 1
fi

echo "==> upgrading marketplace snapshot: ${MARKETPLACE}"
if ! codex plugin marketplace upgrade "${MARKETPLACE}"; then
  cat >&2 <<EOF

plugin-refresh: marketplace upgrade FAILED.

The usual cause is a name mismatch: the "name" field in the repo's
.agents/plugins/marketplace.json must equal the marketplace name registered in
${CODEX_HOME_DIR}/config.toml under [marketplaces.<name>]. Codex reads
.agents/plugins/marketplace.json in preference to .claude-plugin/marketplace.json,
so a divergent name there silently freezes every future upgrade.

Both must read: ${MARKETPLACE}
EOF
  exit 1
fi

echo "==> installing ${PLUGIN_ID}"
codex plugin add "${PLUGIN_ID}"

echo "==> installed versions in cache"
CACHE_DIR="${CODEX_HOME_DIR}/plugins/cache/${MARKETPLACE}/${PLUGIN}"
if [[ -d "${CACHE_DIR}" ]]; then
  ls -1 "${CACHE_DIR}"
else
  echo "plugin-refresh: no cache directory at ${CACHE_DIR}" >&2
  exit 1
fi

echo
echo "Restart Codex to load the new version."
