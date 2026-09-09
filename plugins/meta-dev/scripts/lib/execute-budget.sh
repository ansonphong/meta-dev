#!/usr/bin/env bash
# ============================================================================
# lib/execute-budget.sh — resolve --budget into turns / timeout / effort /
# depth preamble. SOURCED, not executed.
#
# Doctrine: references/execute-budget.md
#
# Caller provides (all optional except after parse):
#   BUDGET                 auto|low|medium|high|med  (default auto)
#   MAX_TURNS_EXPLICIT     0|1
#   TIMEOUT_EXPLICIT       0|1
#   EFFORT_EXPLICIT        0|1
#   BACKEND                deep|glm|sonnet|opus|fable|grok|codex|agy  (optional)
#   MAX_TURNS, TIMEOUT, EFFORT, PROMPT
#
# md_resolve_budget mutates:
#   BUDGET_RESOLVED, MAX_TURNS, TIMEOUT, EFFORT, PROMPT, BUDGET_PREAMBLE
# ============================================================================

md_normalize_budget_word() {
    case "${1:-}" in
        ''|auto) echo auto ;;
        low) echo low ;;
        med|medium) echo medium ;;
        high) echo high ;;
        *) echo "" ;;
    esac
}

md_budget_rank() {
    case "${1:-medium}" in
        low) echo 1 ;;
        medium) echo 2 ;;
        high) echo 3 ;;
        *) echo 2 ;;
    esac
}

md_budget_from_rank() {
    case "${1:-2}" in
        1) echo low ;;
        3) echo high ;;
        *) echo medium ;;
    esac
}

# Heuristic auto-select from task text. Unsure → medium. Never default high.
md_classify_budget_from_text() {
    local text="${1:-}"
    local lower
    lower="$(printf '%s' "$text" | tr '[:upper:]' '[:lower:]')"

    case "$lower" in
        *rename*|*find-replace*|*boilerplate*|*changelog*|*typo*|*one-file*|*codemod*|*mechanical*)
            echo low
            return 0
            ;;
    esac
    case "$lower" in
        *"find replace"*|*"one file"*|*"string edit"*)
            echo low
            return 0
            ;;
    esac
    case "$lower" in
        *auth*|*payment*|*stripe*|*schema*|*migration*|*architecture*|*render-pipeline*|*already-failed*|*root-cause*|*end-to-end*)
            echo high
            return 0
            ;;
    esac
    case "$lower" in
        *"render pipeline"*|*"already failed"*|*"root cause"*|*"end to end"*)
            echo high
            return 0
            ;;
    esac
    echo medium
}

# Clamp a task level so it cannot exceed a campaign ceiling.
# campaign auto → no clamp.
md_clamp_budget() {
    local task="${1:-medium}"
    local campaign="${2:-auto}"
    campaign="$(md_normalize_budget_word "$campaign")"
    task="$(md_normalize_budget_word "$task")"
    [[ "$task" == "auto" || -z "$task" ]] && task="medium"
    if [[ "$campaign" == "auto" || -z "$campaign" ]]; then
        echo "$task"
        return 0
    fi
    local tr cr
    tr="$(md_budget_rank "$task")"
    cr="$(md_budget_rank "$campaign")"
    if [[ "$tr" -gt "$cr" ]]; then
        echo "$campaign"
    else
        echo "$task"
    fi
}

md_budget_turns() {
    case "${1:-medium}" in
        low) echo 12 ;;
        high) echo 80 ;;
        *) echo 32 ;;
    esac
}

md_budget_timeout_ms() {
    # Headless workers routinely run 30+ min. These walls are the session
    # backstop, not a "hurry up" hint. low used to be 15 min and medium 45 —
    # both cut real DeepSeek/Codex/Grok/Opus jobs mid-flight.
    case "${1:-medium}" in
        low) echo 1800000 ;;     # 30 min
        high) echo 10800000 ;;   # 180 min
        *) echo 5400000 ;;       # 90 min
    esac
}

# Parse --timeout into milliseconds.
# Accepts 30m / 2h / 1800s / 7200000ms / bare integers.
# Bare integers < 1000 are SECONDS (15 → 15s), never milliseconds — a 15ms
# worker timeout is always a unit mix-up from a host tool.
md_parse_timeout_to_ms() {
    local raw="${1:-}"
    raw="${raw// /}"
    if [[ -z "$raw" ]]; then
        echo "[ERROR] empty --timeout" >&2
        return 1
    fi
    if [[ "$raw" =~ ^([0-9]+)ms$ ]]; then
        echo "${BASH_REMATCH[1]}"
        return 0
    fi
    if [[ "$raw" =~ ^([0-9]+)(\.[0-9]+)?s$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 1000 ))
        return 0
    fi
    if [[ "$raw" =~ ^([0-9]+)m(in)?$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 60000 ))
        return 0
    fi
    if [[ "$raw" =~ ^([0-9]+)h(r|ours?)?$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 3600000 ))
        return 0
    fi
    if [[ "$raw" =~ ^[0-9]+$ ]]; then
        if [[ "$raw" -lt 1000 ]]; then
            echo "[timeout] '$raw' < 1000 — treating as SECONDS (${raw}s), not milliseconds" >&2
            echo $(( raw * 1000 ))
        else
            echo "$raw"
        fi
        return 0
    fi
    echo "[ERROR] Invalid --timeout '$raw'. Use milliseconds, or a suffix: 30s / 30m / 2h." >&2
    return 1
}

# Host bash/tool timeouts that conductors accidentally forward as --timeout.
# 5s–5min in milliseconds. Real worker walls are budget (30–180 min).
md_timeout_looks_like_host_tool() {
    case "${1:-}" in
        1000|2000|3000|4000|5000|8000|10000|15000|20000|30000|45000|60000|90000|120000|180000|240000|300000)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Silence window before the liveness watchdog kills a worker.
# Floor 20 min (thinking models emit nothing that long); cap 45 min.
# Dynamic: 1/4 of the wall clock.
md_stall_secs_for_timeout_ms() {
    local timeout_ms="${1:-5400000}"
    [[ "$timeout_ms" =~ ^[0-9]+$ ]] || timeout_ms=5400000
    local timeout_s=$(( timeout_ms / 1000 ))
    local stall=$(( timeout_s / 4 ))
    [[ "$stall" -lt 1200 ]] && stall=1200
    [[ "$stall" -gt 2700 ]] && stall=2700
    echo "$stall"
}

# Effort suggestion. Empty string = do not override backend default.
md_budget_effort() {
    case "${1:-medium}" in
        low) echo low ;;
        high) echo xhigh ;;
        *) echo "" ;;
    esac
}

md_budget_preamble() {
    local level="${1:-medium}"
    local turns="${2:-32}"
    local timeout_ms="${3:-5400000}"
    local timeout_min=$((timeout_ms / 60000))
    local rules
    case "$level" in
        low)
            rules="Do the named task and stop. No extra investigation. No subagents. No adjacent files. First acceptance is enough."
            ;;
        high)
            rules="Go as deep as THIS task needs. Still no unrelated refactors. Cap 3 repair rounds, then report residual."
            ;;
        *)
            rules="Stay on the declared files. One repair pass. No unrelated refactors. Do not open adjacent rabbit holes."
            ;;
    esac
    cat <<EOF
=== EXECUTION BUDGET: ${level} ===
Turn cap: ${turns}. Wall: ${timeout_min} min.
Do not overthink. Do not wander.
${rules}
=== END BUDGET ===
EOF
}

md_resolve_budget() {
    local raw resolved turns timeout_ms suggested_effort parsed
    raw="$(md_normalize_budget_word "${BUDGET:-auto}")"
    if [[ -z "$raw" ]]; then
        echo "[ERROR] Invalid --budget '${BUDGET}'. Use auto, low, medium, or high." >&2
        return 1
    fi

    if [[ "$raw" == "auto" ]]; then
        resolved="medium"
        echo "[budget] auto → medium (runner fallback; dispatcher should have classified)" >&2
    else
        resolved="$raw"
    fi
    BUDGET_RESOLVED="$resolved"

    turns="$(md_budget_turns "$resolved")"
    timeout_ms="$(md_budget_timeout_ms "$resolved")"
    suggested_effort="$(md_budget_effort "$resolved")"

    if [[ "${MAX_TURNS_EXPLICIT:-0}" != "1" && "${MAX_TURNS_EXPLICIT:-false}" != "true" ]]; then
        MAX_TURNS="$turns"
    fi
    if [[ "${TIMEOUT_EXPLICIT:-0}" == "1" || "${TIMEOUT_EXPLICIT:-false}" == "true" ]]; then
        parsed="$(md_parse_timeout_to_ms "$TIMEOUT")" || return 1
        if [[ "${META_DEV_ALLOW_SHORT_TIMEOUT:-0}" != "1" ]] && md_timeout_looks_like_host_tool "$parsed"; then
            echo "[timeout] ignoring host-tool --timeout ${TIMEOUT} (${parsed}ms). That is a bash/spawn timeout, not a worker wall. Using budget ${resolved} = ${timeout_ms}ms. Pass 30m/90m/2h or set META_DEV_ALLOW_SHORT_TIMEOUT=1 for a real short run." >&2
            TIMEOUT="$timeout_ms"
            TIMEOUT_EXPLICIT=0
        else
            TIMEOUT="$parsed"
        fi
    else
        TIMEOUT="$timeout_ms"
    fi
    # Dynamic stall: thinking backends go silent for many minutes. Do not
    # override an explicit STALL_SECS (including 0 = watchdog off).
    if [[ "${STALL_SECS_EXPLICIT:-0}" != "1" && "${STALL_SECS_EXPLICIT:-false}" != "true" ]]; then
        STALL_SECS="$(md_stall_secs_for_timeout_ms "$TIMEOUT")"
    fi
    if [[ "${EFFORT_EXPLICIT:-0}" != "1" && "${EFFORT_EXPLICIT:-false}" != "true" ]]; then
        if [[ -n "$suggested_effort" ]]; then
            if [[ "${BACKEND:-}" == "deep" ]]; then
                : # DeepSeek has no effort knob
            else
                EFFORT="$suggested_effort"
            fi
        fi
    fi

    BUDGET_PREAMBLE="$(md_budget_preamble "$resolved" "${MAX_TURNS:-$turns}" "${TIMEOUT:-$timeout_ms}")"
}

md_budget_wrap_prompt() {
    local preamble="${BUDGET_PREAMBLE:-}"
    [[ -z "$preamble" ]] && return 0
    PROMPT="${preamble}

${PROMPT}"
}
