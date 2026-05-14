#!/usr/bin/env bash
set -euo pipefail
# PostToolUse hook: fires after Edit/Write/MultiEdit tool calls.
# Matcher: Edit|Write|MultiEdit in plugin.json.
# Input: JSON payload on stdin — { tool_name, tool_input:{file_path,...}, ... }
# Detects edits to plan files → emits plan_edit event (overlord trigger source).

PAYLOAD=$(cat)
PATH_EDITED=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // ""')
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

case "$PATH_EDITED" in
  *plans/*plan*.md)
    EVENT=$(jq -nc --arg f "$PATH_EDITED" --arg t "$(date -u +%FT%TZ)" \
      '{event:"plan_edit",file:$f,time:$t}')
    bash "$PLUGIN_ROOT/scripts/state-append.sh" "$EVENT" 2>/dev/null || true

    # If overlord watching this plan, signal it
    OVERLORD_WATCHING=$(bash "$PLUGIN_ROOT/scripts/state-read.sh" overlord.watching 2>/dev/null || echo "")
    if [ -n "$OVERLORD_WATCHING" ] && [ "$OVERLORD_WATCHING" != "null" ]; then
      case "$PATH_EDITED" in
        *"$OVERLORD_WATCHING"*)
          echo "meta-dev: overlord trigger — plan edited ($(basename "$PATH_EDITED")), review queued"
          ;;
      esac
    fi
    ;;
esac
