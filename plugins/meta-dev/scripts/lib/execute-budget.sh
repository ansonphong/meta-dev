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
#   BACKEND                deep|glm|sonnet|opus|fable|grok|codex  (optional)
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
    case "${1:-medium}" in
        low) echo 900000 ;;
        high) echo 7200000 ;;
        *) echo 2700000 ;;
    esac
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
    local timeout_ms="${3:-2700000}"
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
    local raw resolved turns timeout_ms suggested_effort
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
    if [[ "${TIMEOUT_EXPLICIT:-0}" != "1" && "${TIMEOUT_EXPLICIT:-false}" != "true" ]]; then
        TIMEOUT="$timeout_ms"
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
