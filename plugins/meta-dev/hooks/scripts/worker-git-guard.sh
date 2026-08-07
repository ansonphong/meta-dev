#!/usr/bin/env bash
set -euo pipefail
# ============================================================================
# worker-git-guard.sh — PreToolUse hook, HEADLESS-WORKER context only.
#
# Headless workers COMMIT THEIR OWN WORK (policy change 2026-07-19). Modular,
# per-task commits beat one end-of-run conductor sweep: the history reads as
# coherent units, and finished work is durable the moment it is done instead of
# sitting uncommitted until the conductor gets to it.
#
# What the 2026-07-05 incident was ACTUALLY about was never `commit` — it was
# TREE-WIDE STAGING and TREE-MUTATING commands in a SHARED working tree with
# many concurrent agents. `git add -A` sweeps a peer's in-flight lines into your
# commit; checkout/reset/stash/restore DESTROY them. Those stay blocked. A
# commit of explicitly-named paths is additive, recoverable, and safe.
#
# The shared policy (scripts/lib/git_policy.py) is a DESTRUCTIVE-ONLY denylist:
# it blocks the sweep and the destroyers and allows every other git command with
# no required flag shape. It is the same policy the interactive guard runs — a
# worker is not held to a stricter contract than the conductor, it just runs in
# a context where a sweep is likelier to hit a peer.
#
# Injected by claude-headless-exec via `--settings` (the worker is a separate
# `claude -p` process that does NOT inherit the project's plugin hooks). It
# fires even under `--permission-mode bypassPermissions`, because PreToolUse
# hooks are a separate enforcement layer from the permission engine — which is
# exactly why --disallowedTools is not a reliable substitute here.
#
# Self-gating: active ONLY when META_WORKER_MANIFEST is set (the wrapper sets
# it). In any other context it allows unconditionally, so it can never
# accidentally constrain a normal interactive session that happens to load it.
#
# PreToolUse protocol: exit 0 with a JSON permissionDecision on stdout.
# ============================================================================

emit_allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n'
  exit 0
}

emit_deny() {
  jq -nc --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason},systemMessage:"meta-dev worker-guard BLOCK: unsafe git mutation attempted in headless-worker context."}'
  exit 0
}

# Not a headless worker → do nothing.
[ -n "${META_WORKER_MANIFEST:-}" ] || emit_allow

PAYLOAD=$(cat)
TOOL=$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // empty' 2>/dev/null || echo "")
[ "$TOOL" = "Bash" ] || emit_allow

CMD=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")
[ -n "$CMD" ] || emit_allow
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY="$SCRIPT_DIR/../../scripts/lib/git_policy.py"
set +e
REASON=$(python3 "$POLICY" --command "$CMD" 2>&1)
RC=$?
set -e
[ "$RC" -eq 0 ] || emit_deny "BLOCKED: $REASON"

emit_allow
