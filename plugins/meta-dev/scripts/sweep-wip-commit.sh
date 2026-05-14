#!/usr/bin/env bash
set -euo pipefail
# Auto-commit untracked plan files as wip: commits.
# Only touches plans/ directory.

UNTRACKED=$(git ls-files --others --exclude-standard plans/ 2>/dev/null || true)
if [ -n "$UNTRACKED" ]; then
  echo "$UNTRACKED" | while read -r file; do
    git add "$file"
  done
  git commit -m "wip: auto-sweep $(date +%Y-%m-%d)"
  echo "sweep: wip commit on $(echo "$UNTRACKED" | wc -l | tr -d ' ') untracked files"
fi
