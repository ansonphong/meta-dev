# shellcheck shell=bash
# ============================================================================
# stall-watchdog.sh — shared liveness watchdog for headless workers
# ----------------------------------------------------------------------------
# A headless worker that HANGS (silent loop, wedged tool call, dead socket)
# keeps its process alive but stops emitting events — so its RAW event-stream
# file stops GROWING. The 120-min wall-clock `timeout(1)` cap is only a backstop;
# without this watchdog a wedged worker sits idle for the full two hours.
#
# This watches RAW_FILE's byte-size. If it stays frozen for STALL_SECS while the
# worker is still alive, the worker is declared stuck: we kill it, then AUTO-RESET
# (re-dispatch the identical attempt on a fresh worker) up to STALL_MAX_RESETS
# times. After the budget is exhausted on a still-stalling worker we STOP and
# surface — the caller returns a distinct halt code so the conductor PAUSES the
# run instead of treating the silence as success.
#
# ── Caller contract ─────────────────────────────────────────────────────────
# The caller defines a shell function `stall_launch_worker` that:
#   • launches the real worker in the BACKGROUND (`… &`),
#   • redirects stdout→RAW_FILE and stderr→STDERR_FILE,
#   • sets WORKER_PID to the backgrounded PID (`WORKER_PID=$!`),
#   • returns immediately (does NOT wait).
# Then the caller calls `run_with_stall_watchdog` and afterward reads the globals
# it sets: STALL_EXIT (final attempt exit code), STALL_RESETS (# resets done),
# STALL_HALTED ("true" if the reset budget was exhausted on a stuck worker).
#
# ── Tunables (env; caller may pre-set, all have safe defaults) ───────────────
#   STALL_SECS        no-growth seconds → declare stuck   (default 300 = 5 min)
#                     set 0 to DISABLE the watchdog entirely (pure 120-min cap)
#   STALL_POLL_SECS   size-poll interval                  (default 30)
#   STALL_MAX_RESETS  auto-resets after the first stall   (default 3 → ≤4 runs)
# ============================================================================

# stall_monitor <worker_pid> <raw_file> <stall_secs> <poll_secs> <marker_file>
# Polls raw_file size while worker_pid is alive. On a stall, writes a one-line
# reason to marker_file and kills the worker (TERM, then KILL after a grace).
# Returns 0 always (it is a background helper; liveness is signalled via marker).
# _fsize <file> — portable byte-size. `stat -c%s` is GNU-only; on macOS BSD stat
# it errors ("illegal option -- c") and the old `|| echo 0` made the watchdog read
# EVERY file as 0 bytes → output looked permanently frozen → it killed healthy
# long-running workers every STALL_SECS (false stall → exit 125). `wc -c` is
# universal; strip whitespace BSD wc may pad with.
_fsize() {
    local s; s=$(wc -c < "$1" 2>/dev/null); s=${s//[^0-9]/}; printf '%s' "${s:-0}"
}

stall_monitor() {
    local pid="$1" file="$2" stall="$3" poll="${4:-30}" marker="$5"
    [[ "${stall:-0}" -le 0 ]] && return 0          # 0 → watchdog disabled
    local last_size=-1 last_change size now
    last_change=$(date +%s)
    while kill -0 "$pid" 2>/dev/null; do
        sleep "$poll"
        size=$(_fsize "$file")
        now=$(date +%s)
        if [[ "$size" != "$last_size" ]]; then
            last_size="$size"; last_change="$now"
        elif (( now - last_change >= stall )); then
            echo "stalled: RAW output frozen at ${size}B for ${stall}s" > "$marker"
            # TERM the watched PID — for a `timeout … cmd` pipeline this is the
            # `timeout` process, which forwards the signal to its child; for a
            # bare `env … claude` it is the worker itself. KILL backstops a
            # process that ignores TERM.
            kill -TERM "$pid" 2>/dev/null
            sleep 3
            kill -KILL "$pid" 2>/dev/null
            return 0
        fi
    done
    return 0
}

# run_with_stall_watchdog — drive stall_launch_worker through the reset budget.
# Sets globals: STALL_EXIT, STALL_RESETS, STALL_HALTED.
run_with_stall_watchdog() {
    local stall_secs="${STALL_SECS:-300}"
    local poll_secs="${STALL_POLL_SECS:-30}"
    local max_resets="${STALL_MAX_RESETS:-3}"
    local marker="${RAW_FILE}.stalled"
    STALL_RESETS=0
    STALL_HALTED=false
    STALL_EXIT=0

    while :; do
        rm -f "$marker"
        stall_launch_worker                         # caller backgrounds → WORKER_PID
        local mon_pid=""
        if [[ "$stall_secs" -gt 0 ]]; then
            stall_monitor "$WORKER_PID" "$RAW_FILE" "$stall_secs" "$poll_secs" "$marker" &
            mon_pid=$!
        fi
        STALL_EXIT=0
        wait "$WORKER_PID" || STALL_EXIT=$?
        if [[ -n "$mon_pid" ]]; then
            kill "$mon_pid" 2>/dev/null || true
            wait "$mon_pid" 2>/dev/null || true
        fi

        if [[ -f "$marker" ]]; then                 # worker was stall-killed
            if [[ "$STALL_RESETS" -lt "$max_resets" ]]; then
                STALL_RESETS=$((STALL_RESETS + 1))
                echo "[stall-watchdog] worker stalled — auto-reset ${STALL_RESETS}/${max_resets}, re-dispatching" >&2
                continue
            fi
            STALL_HALTED=true
            STALL_EXIT=125                           # distinct: stalled-and-halted
            echo "[stall-watchdog] worker stalled again after ${max_resets} resets — HALTING; run paused for review" >&2
            break
        fi
        break                                       # clean finish (or non-stall error)
    done
    rm -f "$marker"
    return 0
}
