#!/usr/bin/env bash
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"
STATUS="open"; SOURCE_FILTER=""; SEVERITY_FILTER=""; LIMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --status) STATUS="$2"; shift 2 ;;
    --source) SOURCE_FILTER="$2"; shift 2 ;;
    --severity) SEVERITY_FILTER="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

INBOX_FILE="plans/_dashboard/inbox/inbox.jsonl"
[ -f "$INBOX_FILE" ] || { echo "[]"; exit 0; }

python3 "$PLUGIN_ROOT/scripts/inbox-render.py" --json --status "$STATUS" \
  ${SOURCE_FILTER:+--source "$SOURCE_FILTER"} \
  ${SEVERITY_FILTER:+--severity "$SEVERITY_FILTER"} \
  ${LIMIT:+--limit "$LIMIT"} 2>/dev/null
