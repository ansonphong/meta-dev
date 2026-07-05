#!/usr/bin/env bash
set -euo pipefail
# SessionStart hook — inject compact dashboard summary into context.
# Coexists with other SessionStart hooks (e.g. caveman). Idempotent.
# Input: JSON payload on stdin (may be empty for SessionStart). Output: stdout → injected into Claude context.

# Drain stdin (SessionStart payload mostly informational; we don't need fields)
_=$(cat 2>/dev/null || true)

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

# ── Concurrent-session safety notice (always on; silent unless contended) ─
# The meta working tree is SHARED across sessions. If another session's
# headless workers are live OR a plan-dir scope is actively claimed, surface
# it so this session partitions work instead of racing (incident 2026-07-05).
# Fully defensive — never let a check failure disrupt session start.
concurrency_notice() {
  local live claims wc_sh ver
  live=$(pgrep -fc 'claude-headless-exec' 2>/dev/null || true); live=${live:-0}
  wc_sh="$PLUGIN_ROOT/scripts/worker-claim.sh"
  claims=""
  [ -f "$wc_sh" ] && claims=$(bash "$wc_sh" list 2>/dev/null | grep -v '(no active claims)' || true)
  if [ "${live:-0}" -gt 0 ] || [ -n "$claims" ]; then
    ver=$(printf '%s' "$PLUGIN_ROOT" | grep -oE 'meta-dev/[0-9]+\.[0-9]+\.[0-9]+' | head -1 | cut -d/ -f2)
    echo "---"
    echo "⚠ meta-dev CONCURRENCY: another session may be active in this SHARED tree."
    [ "${live:-0}" -gt 0 ] && echo "  • ${live} live headless worker process(es) (ps: claude-headless-exec)."
    if [ -n "$claims" ]; then
      echo "  • Active plan-dir claims:"
      printf '%s\n' "$claims" | jq -r '"      - " + (.scope|tostring) + "  (session=" + (.session|tostring) + " pid=" + (.pid|tostring) + ")"' 2>/dev/null | head -10 \
        || printf '%s\n' "$claims" | sed 's/^/      /'
    fi
    echo "  Dispatch plan-editing workers with 'claude-headless-exec --claim <plan-dir>',"
    echo "  partition by directory, and stage EXPLICIT file paths only (never 'git add -A'/'<dir>')."
    [ -n "$ver" ] && echo "  • This session: meta-dev v${ver} — confirm other sessions run the same version."
  fi
}
concurrency_notice || true

SETTINGS="plans/_dashboard/settings.json"
[ -f "$SETTINGS" ] || exit 0

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
