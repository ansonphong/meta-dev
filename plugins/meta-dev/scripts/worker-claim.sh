#!/usr/bin/env bash
set -euo pipefail
# ============================================================================
# worker-claim.sh — cross-session directory CLAIM REGISTRY (file-based, no daemon)
#
# The meta working tree is SHARED across concurrent Claude Code sessions. Two
# sessions that dispatch headless plan-editing workers to the SAME directory
# race the same files (last-writer-wins) and tangle each other's edits
# (incident 2026-07-05). This registry COORDINATES instead of isolating: a
# conductor claims a plan-directory scope BEFORE dispatching a worker there; an
# overlapping live claim makes the second dispatch refuse/queue rather than
# race. It is the no-worktree alternative to filesystem isolation.
#
# Mechanism (mirrors the _dashboard/*.jsonl pattern — append-only, shared tree):
#   • plans/_dashboard/.worker-locks/<hash>/meta.json  — one persistent lock
#     dir per claimed scope. `mkdir` is the ATOMIC mutex.
#   • plans/_dashboard/.worker-locks/.registry.lock    — a short-lived GLOBAL
#     mutex held only across the scan+create critical section, so two dispatches
#     claiming OVERLAPPING-but-different scopes can't both pass the overlap scan
#     (closes the check-then-claim TOCTOU that a per-scope lock alone leaves).
#   • plans/_dashboard/worker-claims.jsonl             — append-only audit log.
#
# Stale claims auto-expire (dead pid OR ts older than TTL, default 30 min) so a
# crashed session never permanently wedges a scope.
#
# Usage:
#   worker-claim.sh claim   <scope> [--pid N] [--session S] [--ttl SECS]
#   worker-claim.sh release <scope>
#   worker-claim.sh check   <scope>
#   worker-claim.sh list
#   worker-claim.sh sweep
#
# Exit codes:  claim → 0 granted / 3 blocked / 2 usage / 1 lock-timeout
#              check → 0 free    / 3 blocked
# Run from the project root (or set WORKER_CLAIM_DIR to the _dashboard path).
# ============================================================================

VERB="${1:-}"; shift 2>/dev/null || true
SCOPE=""; PID_ARG=""; SESSION_ARG=""; TTL="${WORKER_CLAIM_TTL:-1800}"
while [ $# -gt 0 ]; do
  case "$1" in
    --pid)     PID_ARG="${2:-}";     shift 2 ;;
    --session) SESSION_ARG="${2:-}"; shift 2 ;;
    --ttl)     TTL="${2:-1800}";     shift 2 ;;
    *)         [ -z "$SCOPE" ] && SCOPE="$1"; shift ;;
  esac
done

DASH="${WORKER_CLAIM_DIR:-plans/_dashboard}"
LOCKS="$DASH/.worker-locks"
LOG="$DASH/worker-claims.jsonl"
GLOCK="$LOCKS/.registry.lock"
mkdir -p "$LOCKS"

now()   { date +%s; }
host()  { hostname 2>/dev/null || echo "?"; }
keyof() { printf '%s' "$1" | md5sum | cut -c1-16; }
alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }

# Normalize a scope path: collapse //, strip trailing / and leading ./
norm() { printf '%s' "$1" | sed -e 's#//*#/#g' -e 's#/*$##' -e 's#^\./##'; }

# Two scopes overlap if equal or one is a path-prefix (ancestor) of the other.
overlaps() {
  local a b; a="$(norm "$1")"; b="$(norm "$2")"
  [ "$a" = "$b" ] && return 0
  case "$b/" in "$a/"*) return 0 ;; esac
  case "$a/" in "$b/"*) return 0 ;; esac
  return 1
}

append_log() { # status scope pid session
  printf '{"ts":%s,"status":%s,"scope":%s,"pid":%s,"session":%s,"host":%s}\n' \
    "$(now)" \
    "$(jq -nc --arg v "$1" '$v')" "$(jq -nc --arg v "$2" '$v')" \
    "$(jq -nc --arg v "${3:-}" '$v')" "$(jq -nc --arg v "${4:-}" '$v')" \
    "$(jq -nc --arg v "$(host)" '$v')" >> "$LOG"
}

# Global critical-section mutex — held only across scan+create (sub-second).
acquire_glock() {
  local i age
  for i in $(seq 1 100); do
    if mkdir "$GLOCK" 2>/dev/null; then
      trap 'rmdir "$GLOCK" 2>/dev/null || true' EXIT
      return 0
    fi
    if [ -d "$GLOCK" ]; then           # break a wedged lock (should be sub-second)
      age=$(( $(now) - $(stat -c %Y "$GLOCK" 2>/dev/null || echo 0) ))
      [ "$age" -gt 15 ] && rmdir "$GLOCK" 2>/dev/null || true
    fi
    sleep 0.1
  done
  return 1
}

# Remove expired claims (dead pid OR older than TTL). Call while holding GLOCK.
sweep_stale() {
  local d meta ts pid age sc
  for d in "$LOCKS"/*/; do
    [ -d "$d" ] || continue
    meta="$d/meta.json"
    [ -f "$meta" ] || { rmdir "$d" 2>/dev/null || true; continue; }
    ts=$(jq -r '.ts // 0' "$meta" 2>/dev/null || echo 0)
    pid=$(jq -r '.pid // ""' "$meta" 2>/dev/null || echo "")
    age=$(( $(now) - ts ))
    if [ "$age" -gt "$TTL" ] || { [ -n "$pid" ] && ! alive "$pid"; }; then
      sc=$(jq -r '.scope // "?"' "$meta" 2>/dev/null || echo "?")
      rm -f "$meta"; rmdir "$d" 2>/dev/null || true
      append_log "expired" "$sc" "$pid" ""
    fi
  done
}

# Print meta.json path of the first LIVE claim overlapping $SCOPE, else return 1.
find_overlap() {
  local d meta sc
  for d in "$LOCKS"/*/; do
    [ -d "$d" ] || continue
    meta="$d/meta.json"; [ -f "$meta" ] || continue
    sc=$(jq -r '.scope // ""' "$meta" 2>/dev/null || echo "")
    [ -n "$sc" ] || continue
    if overlaps "$SCOPE" "$sc"; then printf '%s' "$meta"; return 0; fi
  done
  return 1
}

case "$VERB" in
  claim)
    [ -n "$SCOPE" ] || { echo "usage: worker-claim.sh claim <scope>" >&2; exit 2; }
    acquire_glock || { echo "[worker-claim] could not acquire registry lock (busy)" >&2; exit 1; }
    sweep_stale
    if OV=$(find_overlap); then
      osc=$(jq -r '.scope' "$OV"); opid=$(jq -r '.pid // "?"' "$OV")
      ots=$(jq -r '.ts // 0' "$OV"); osess=$(jq -r '.session // "?"' "$OV")
      {
        echo "[worker-claim] BLOCKED: '$SCOPE' overlaps LIVE claim '$osc'"
        echo "               (session=$osess pid=$opid age=$(( $(now) - ots ))s)."
        echo "  Another session is editing that scope. Partition by directory, wait,"
        echo "  or it auto-expires after ${TTL}s (or on that pid dying)."
      } >&2
      exit 3
    fi
    d="$LOCKS/$(keyof "$(norm "$SCOPE")")"
    if ! mkdir "$d" 2>/dev/null; then
      echo "[worker-claim] BLOCKED: '$SCOPE' was just claimed by a racing dispatch." >&2
      exit 3
    fi
    pid="${PID_ARG:-$PPID}"; sess="${SESSION_ARG:-${CLAUDE_SESSION_ID:-$PPID}}"
    jq -nc --argjson ts "$(now)" --arg scope "$(norm "$SCOPE")" \
       --arg pid "$pid" --arg session "$sess" --arg host "$(host)" \
       '{ts:$ts,scope:$scope,pid:$pid,session:$session,host:$host}' > "$d/meta.json"
    append_log "claimed" "$(norm "$SCOPE")" "$pid" "$sess"
    echo "[worker-claim] GRANTED: '$SCOPE' (pid=$pid session=$sess ttl=${TTL}s)"
    exit 0
    ;;

  release)
    [ -n "$SCOPE" ] || { echo "usage: worker-claim.sh release <scope>" >&2; exit 2; }
    d="$LOCKS/$(keyof "$(norm "$SCOPE")")"
    if [ -d "$d" ]; then
      rm -f "$d/meta.json"; rmdir "$d" 2>/dev/null || true
      append_log "released" "$(norm "$SCOPE")" "" ""
      echo "[worker-claim] released '$SCOPE'"
    else
      echo "[worker-claim] no active claim for '$SCOPE'"
    fi
    exit 0
    ;;

  check)
    [ -n "$SCOPE" ] || { echo "usage: worker-claim.sh check <scope>" >&2; exit 2; }
    acquire_glock || true
    sweep_stale
    if OV=$(find_overlap); then
      osc=$(jq -r '.scope' "$OV")
      echo "BLOCKED: '$SCOPE' overlaps live claim '$osc'"; exit 3
    fi
    echo "FREE: '$SCOPE' is claimable"; exit 0
    ;;

  list)
    acquire_glock || true
    sweep_stale
    found=0
    for d in "$LOCKS"/*/; do
      [ -f "$d/meta.json" ] || continue
      found=1; jq -c . "$d/meta.json"
    done
    [ "$found" = 0 ] && echo "(no active claims)"
    exit 0
    ;;

  sweep)
    acquire_glock || true
    sweep_stale
    echo "[worker-claim] swept stale claims (ttl=${TTL}s)"
    exit 0
    ;;

  *)
    echo "usage: worker-claim.sh {claim|release|check|list|sweep} <scope> [--pid N] [--session S] [--ttl S]" >&2
    exit 2
    ;;
esac
