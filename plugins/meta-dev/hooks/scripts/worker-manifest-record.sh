#!/usr/bin/env bash
set -euo pipefail
# ============================================================================
# worker-manifest-record.sh — PostToolUse hook, HEADLESS-WORKER context only.
#
# Records every file the headless worker touches (Edit/Write/MultiEdit) to
# $META_WORKER_MANIFEST as one JSON object per line (jsonl). The CONDUCTOR
# reads this to stage EXACTLY the worker's files — `git add <those paths>` —
# instead of a tree-wide `git add`/`git diff` that would sweep a concurrent
# session's in-flight edits into this commit (commit-sweep, incident
# 2026-07-05). Recording what the worker touched (deterministic) beats
# inferring it from git in a SHARED tree (pollutable).
#
# Injected by claude-headless-exec via `--settings`. Self-gating: a strict
# no-op unless META_WORKER_MANIFEST is set, so it never writes in a normal
# interactive session. Failure to record is non-fatal — never break a worker
# tool call over telemetry.
#
# PostToolUse protocol: exit 0; no stdout decision required.
# ============================================================================

MANIFEST="${META_WORKER_MANIFEST:-}"
[ -n "$MANIFEST" ] || exit 0

PAYLOAD=$(cat 2>/dev/null || echo "")
[ -n "$PAYLOAD" ] || exit 0

# Append one {path,tool,ts} object. `select` drops calls with no file_path
# (e.g. a MultiEdit payload shape we don't recognize) so no blank lines land.
# A single O_APPEND write keeps concurrent workers' lines from interleaving.
printf '%s' "$PAYLOAD" \
  | jq -c --arg ts "$(date +%s 2>/dev/null || echo 0)" \
      '{path: (.tool_input.file_path // ""), tool: (.tool_name // "unknown"), ts: ($ts|tonumber)} | select(.path != "")' \
      >> "$MANIFEST" 2>/dev/null || true

exit 0
