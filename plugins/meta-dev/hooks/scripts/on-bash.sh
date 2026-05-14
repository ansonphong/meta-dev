#!/usr/bin/env bash
set -euo pipefail
# PostToolUse hook: fires after Bash tool calls.
# Matcher: Bash(git commit:*) in plugin.json.
# Input: JSON payload on stdin — { tool_name, tool_input:{command,...}, tool_response, ... }
# Detects git commits, emits state event + auto-changelog.

PAYLOAD=$(cat)
CMD=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.command // ""')
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

case "$CMD" in
  *"git commit"*)
    SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "")
    MSG=$(git log -1 --pretty=%s 2>/dev/null || echo "")
    # JSON-safe escape via jq
    EVENT=$(jq -nc --arg sha "$SHA" --arg msg "$MSG" --arg t "$(date -u +%FT%TZ)" \
      '{event:"commit",sha:$sha,message:$msg,time:$t}')
    bash "$PLUGIN_ROOT/scripts/state-append.sh" "$EVENT" 2>/dev/null || true

    # Auto-add to changelog if enabled
    CHANGELOG_AUTO=$(bash "$PLUGIN_ROOT/scripts/config-get.sh" meta_dev.changelog.auto_add_on_commit 2>/dev/null || echo "false")
    if [ "$CHANGELOG_AUTO" = "true" ]; then
      # Derive tag from commit message prefix
      TAG="chore"
      case "$MSG" in
        breaking*) TAG="breaking" ;;
        *!:*) TAG="breaking" ;;
        feat*) TAG="feat" ;;
        fix*) TAG="fix" ;;
        docs*) TAG="docs" ;;
        refactor*) TAG="refactor" ;;
        test*) TAG="test" ;;
        chore*) TAG="chore" ;;
      esac
      bash "$PLUGIN_ROOT/scripts/changelog-add.sh" \
        --tag "$TAG" --title "$MSG" --sha "$SHA" 2>/dev/null || true
    fi
    ;;
esac
