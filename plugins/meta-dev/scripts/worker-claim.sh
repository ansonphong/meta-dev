#!/usr/bin/env bash
# worker-claim.sh — cross-session work-claim registry.
# SHIM: delegates claim/release to planctl claim/release (M3a — unified state layer).
#
# Usage:
#   worker-claim.sh claim   <scope> [--pid N] [--session S] [--ttl SECS]
#   worker-claim.sh release <scope>
#   worker-claim.sh check   <scope>
#   worker-claim.sh list
#   worker-claim.sh sweep
#
# Exit codes:  claim → 0 granted / 3 blocked / 2 usage / 1 lock-busy
#              check → 0 free    / 3 blocked
set -euo pipefail

VERB="${1:-}"; shift 2>/dev/null || true
SCOPE=""; PID_ARG=""; SESSION_ARG=""; TTL="${WORKER_CLAIM_TTL:-7200}"
while [ $# -gt 0 ]; do
  case "$1" in
    --pid)     [ $# -ge 2 ] || { echo "worker-claim.sh: --pid requires a value" >&2; exit 2; }; PID_ARG="${2}";     shift 2 ;;
    --session) [ $# -ge 2 ] || { echo "worker-claim.sh: --session requires a value" >&2; exit 2; }; SESSION_ARG="${2}"; shift 2 ;;
    --ttl)     [ $# -ge 2 ] || { echo "worker-claim.sh: --ttl requires a value" >&2; exit 2; }; TTL="${2}";     shift 2 ;;
    *)         [ -z "$SCOPE" ] && SCOPE="$1"; shift ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PCTL=(bash "$SCRIPT_DIR/planctl.sh")

# WORKER_CLAIM_DIR is retired — claims now live in planctl's unified claims table
# (off-9p, in state.db). Remapping state dir would fork the claims view between
# wrapper invocations and plain planctl calls.
if [ -n "${WORKER_CLAIM_DIR:-}" ]; then
  echo "[worker-claim] WORKER_CLAIM_DIR is retired — claims live in planctl's claims table; ignoring." >&2
fi

case "$VERB" in
  claim)
    [ -n "$SCOPE" ] || { echo "usage: worker-claim.sh claim <scope>" >&2; exit 2; }
    PCTL_ARGS=(claim "$SCOPE")
    [ -n "$PID_ARG" ]     && PCTL_ARGS+=(--pid "$PID_ARG")
    [ -n "$SESSION_ARG" ] && PCTL_ARGS+=(--session "$SESSION_ARG")
    [ -n "$TTL" ]         && PCTL_ARGS+=(--ttl "$TTL")
    exec "${PCTL[@]}" "${PCTL_ARGS[@]}"
    ;;

  release)
    [ -n "$SCOPE" ] || { echo "usage: worker-claim.sh release <scope>" >&2; exit 2; }
    PCTL_ARGS=(release "$SCOPE")
    [ -n "$PID_ARG" ]     && PCTL_ARGS+=(--pid "$PID_ARG")
    [ -n "$SESSION_ARG" ] && PCTL_ARGS+=(--session "$SESSION_ARG")
    exec "${PCTL[@]}" "${PCTL_ARGS[@]}"
    ;;

  check)
    [ -n "$SCOPE" ] || { echo "usage: worker-claim.sh check <scope>" >&2; exit 2; }
    # Capture planctl exit code BEFORE any pipe — pipe swallows it.
    PCTL_OUT=""; PCTL_RC=0
    PCTL_OUT=$("${PCTL[@]}" list --json 2>/dev/null) || PCTL_RC=$?
    if [ "$PCTL_RC" -ne 0 ]; then
      echo "[worker-claim] planctl list failed (rc=$PCTL_RC) — cannot determine claim status" >&2
      exit 1
    fi
    # Validate JSON — unparseable output is false success for a lock primitive.
    if ! echo "$PCTL_OUT" | python3 -c "import json,sys; json.loads(sys.stdin.read() or '[]')" 2>/dev/null; then
      echo "[worker-claim] planctl list returned unparseable output" >&2
      exit 1
    fi
    LIVE="$PCTL_OUT"
    NORM_SCOPE="$(printf '%s' "$SCOPE" | sed -e 's#//*#/#g' -e 's#/*$##' -e 's#^\./##')"
    # Check prefix-overlap: our scope starts with a listed scope OR vice versa.
    OVERLAP=$(python3 -c "
import json, sys
scopes = [e['scope'] for e in json.loads(sys.stdin.read())]
s = sys.argv[1]
for c in scopes:
    if s == c or s.startswith(c + '/') or c.startswith(s + '/'):
        print(c)
        sys.exit(0)
sys.exit(1)
" "$NORM_SCOPE" <<< "$LIVE" 2>/dev/null) || true
    if [ -n "${OVERLAP:-}" ]; then
      echo "BLOCKED: '$SCOPE' overlaps live claim '$OVERLAP'"
      exit 3
    fi
    echo "FREE: '$SCOPE' is claimable"
    exit 0
    ;;

  list)
    # planctl list --json auto-sweeps stale claims. Field names .scope/.session/.pid
    # are pinned (WC-4) — jq contract preserved for on-session-start.sh banner.
    #
    # SHAPE matters as much as field names: the legacy `list` emitted ONE JSON
    # object PER LINE (jq -c per lock dir), or the literal "(no active claims)".
    # on-session-start.sh pipes this output straight into
    #   jq -r '"  - " + (.scope|tostring) + …'
    # which CANNOT index a JSON ARRAY — emitting planctl's raw `[...]` here makes
    # the banner (a) fire on EVERY session start (the string "[]" is non-empty, so
    # the `grep -v '(no active claims)'` guard passes) and (b) print an EMPTY claim
    # list when claims DO exist (jq errors, silenced by 2>/dev/null). Re-emit as
    # newline-delimited objects so the banner keeps working until 3b rewires it.
    LIVE=$("${PCTL[@]}" list --json) || exit $?
    printf '%s' "$LIVE" | python3 -c '
import json, sys
try:
    rows = json.loads(sys.stdin.read() or "[]")
except ValueError:
    rows = []
if not rows:
    print("(no active claims)")
else:
    for r in rows:
        print(json.dumps(r))
'
    exit 0
    ;;

  sweep)
    # planctl list auto-sweeps stale claims before listing. Capture exit code
    # BEFORE any pipe — planctl failure must never look like success.
    PCTL_RC=0
    "${PCTL[@]}" list --json >/dev/null 2>&1 || PCTL_RC=$?
    if [ "$PCTL_RC" -ne 0 ]; then
      echo "[worker-claim] planctl list failed (rc=$PCTL_RC) — sweep incomplete" >&2
      exit 1
    fi
    echo "[worker-claim] swept stale claims (ttl=${TTL}s)"
    exit 0
    ;;

  *)
    echo "usage: worker-claim.sh {claim|release|check|list|sweep} <scope> [--pid N] [--session S] [--ttl S]" >&2
    exit 2
    ;;
esac
