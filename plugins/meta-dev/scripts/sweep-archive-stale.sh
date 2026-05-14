#!/usr/bin/env bash
set -euo pipefail
# Move stale plan files (no git activity in 30 days) to _archive/stale/
# Never delete — move only.

STALE_DAYS=30
PLANS_DIR="plans"
STALE_DIR="$PLANS_DIR/_archive/stale/$(date +%Y-%m)"
mkdir -p "$STALE_DIR"

find "$PLANS_DIR" -name "*.md" -not -path "*/_archive/*" -not -path "*/_dashboard/*" \
  -mtime +$STALE_DAYS -print0 | while IFS= read -r -d '' file; do
  # Check git: when was this file last committed?
  LAST_COMMIT_TS=$(git log -1 --format="%ct" -- "$file" 2>/dev/null || echo "0")
  if [ "$LAST_COMMIT_TS" = "0" ]; then
    echo "skip $file (never committed)"
  else
    NOW_TS=$(date +%s)
    AGE_DAYS=$(( (NOW_TS - LAST_COMMIT_TS) / 86400 ))
    if [ "$AGE_DAYS" -gt "$STALE_DAYS" ]; then
      echo "archive $file (last commit ${AGE_DAYS}d ago) → $STALE_DIR/"
      mv "$file" "$STALE_DIR/"
    else
      echo "skip $file (last commit ${AGE_DAYS}d ago, threshold ${STALE_DAYS}d)"
    fi
  fi
done
