#!/usr/bin/env bash
set -euo pipefail
# Auto-commit untracked plan files as wip: commits.
# Only touches plans/ directory.

REPO_ROOT="$(git rev-parse --show-toplevel)"
mapfile -d '' -t UNTRACKED < <(git -C "$REPO_ROOT" ls-files -z --others --exclude-standard -- plans/ 2>/dev/null || true)

if [ "${#UNTRACKED[@]}" -gt 0 ]; then
  git -C "$REPO_ROOT" add -- "${UNTRACKED[@]}"
  git -C "$REPO_ROOT" commit --only -m "wip: auto-sweep $(date +%Y-%m-%d)" -- "${UNTRACKED[@]}"
  echo "sweep: wip commit on ${#UNTRACKED[@]} untracked files"
fi
