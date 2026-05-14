#!/usr/bin/env bash
set -euo pipefail
# SessionStart hook — inject compact dashboard summary into context.
# Coexists with other SessionStart hooks (e.g. caveman). Idempotent.
# Input: JSON payload on stdin (may be empty for SessionStart). Output: stdout → injected into Claude context.

# Drain stdin (SessionStart payload mostly informational; we don't need fields)
_=$(cat 2>/dev/null || true)

SETTINGS="plans/_dashboard/settings.json"
[ -f "$SETTINGS" ] || exit 0

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

AUTO_INJECT=$(bash "$PLUGIN_ROOT/scripts/config-get.sh" meta_dev.dashboard.auto_inject_on_session 2>/dev/null || echo "false")
[ "$AUTO_INJECT" = "true" ] || exit 0

echo "---"
echo "meta-dev dashboard snapshot:"

# Active state summary
bash "$PLUGIN_ROOT/scripts/state-read.sh" 2>/dev/null || echo "(state unavailable)"

echo "---"

# Quick counts
ACTIVE_PLANS=$(find plans -name "masterplan.md" -o -name "00-master-plan.md" 2>/dev/null | wc -l | tr -d ' ')
INBOX_OPEN=$(bash "$PLUGIN_ROOT/scripts/inbox-count.sh" --status open 2>/dev/null || echo 0)
echo "Active plans: $ACTIVE_PLANS | Inbox open: $INBOX_OPEN"
echo "Run /meta-dashboard for full view."
