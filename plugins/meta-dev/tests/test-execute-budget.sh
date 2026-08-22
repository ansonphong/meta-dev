#!/usr/bin/env bash
# Focused contract: --budget resolves turns/timeout/effort and auto-classifies.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../scripts/lib/execute-budget.sh
source "$PLUGIN_ROOT/scripts/lib/execute-budget.sh"

PASS=0
FAIL=0
ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

echo "=== execute-budget contract ==="

# classify
got="$(md_classify_budget_from_text "Rename getCwd across the project")"
[[ "$got" == "low" ]] && ok "classify rename → low" || bad "classify rename → $got"

got="$(md_classify_budget_from_text "Fix the Stripe payment webhook signature")"
[[ "$got" == "high" ]] && ok "classify payment → high" || bad "classify payment → $got"

got="$(md_classify_budget_from_text "Add a focused verify hook to task T3.2")"
[[ "$got" == "medium" ]] && ok "classify ordinary → medium" || bad "classify ordinary → $got"

got="$(md_clamp_budget high low)"
[[ "$got" == "low" ]] && ok "clamp high under campaign low" || bad "clamp → $got"

got="$(md_clamp_budget low high)"
[[ "$got" == "low" ]] && ok "clamp keeps lower task" || bad "clamp keep → $got"

# runner resolve: auto → medium, fills turns/timeout
BUDGET="auto"
MAX_TURNS=""
TIMEOUT=""
EFFORT=""
MAX_TURNS_EXPLICIT=0
TIMEOUT_EXPLICIT=0
EFFORT_EXPLICIT=0
BACKEND="grok"
PROMPT="do the thing"
md_resolve_budget
[[ "$BUDGET_RESOLVED" == "medium" ]] && ok "auto → medium" || bad "auto resolved $BUDGET_RESOLVED"
[[ "$MAX_TURNS" == "32" ]] && ok "medium turns 32" || bad "turns $MAX_TURNS"
[[ "$TIMEOUT" == "2700000" ]] && ok "medium timeout 45m" || bad "timeout $TIMEOUT"
[[ -z "$EFFORT" ]] && ok "medium leaves effort default" || bad "effort $EFFORT"

BUDGET="low"
MAX_TURNS=""
TIMEOUT=""
EFFORT="high"
MAX_TURNS_EXPLICIT=0
TIMEOUT_EXPLICIT=0
EFFORT_EXPLICIT=0
BACKEND="grok"
md_resolve_budget
[[ "$MAX_TURNS" == "12" && "$EFFORT" == "low" && "$TIMEOUT" == "900000" ]] && ok "low maps turns/effort/timeout" || bad "low map t=$MAX_TURNS e=$EFFORT to=$TIMEOUT"

BUDGET="high"
MAX_TURNS="5"
MAX_TURNS_EXPLICIT=1
TIMEOUT=""
EFFORT="medium"
EFFORT_EXPLICIT=1
TIMEOUT_EXPLICIT=0
BACKEND="opus"
md_resolve_budget
[[ "$MAX_TURNS" == "5" ]] && ok "explicit max-turns wins" || bad "turns clobber $MAX_TURNS"
[[ "$EFFORT" == "medium" ]] && ok "explicit effort wins" || bad "effort clobber $EFFORT"
[[ "$TIMEOUT" == "7200000" ]] && ok "high timeout when not explicit" || bad "high timeout $TIMEOUT"

BUDGET="low"
BACKEND="deep"
EFFORT=""
EFFORT_EXPLICIT=0
MAX_TURNS=""
MAX_TURNS_EXPLICIT=0
TIMEOUT=""
TIMEOUT_EXPLICIT=0
md_resolve_budget
[[ -z "$EFFORT" ]] && ok "deep does not get effort from budget" || bad "deep effort $EFFORT"

md_budget_wrap_prompt
case "$PROMPT" in
    *"EXECUTION BUDGET: low"*) ok "preamble wrapped" ;;
    *) bad "preamble missing" ;;
esac

got="$("$PLUGIN_ROOT/scripts/classify-execute-budget.sh" --campaign medium -- "Rename foo")"
[[ "$got" == "low" ]] && ok "cli classify+clamp rename under medium" || bad "cli $got"

got="$("$PLUGIN_ROOT/scripts/classify-execute-budget.sh" --campaign low -- "Fix the Stripe webhook")"
[[ "$got" == "low" ]] && ok "cli campaign ceiling" || bad "cli ceiling $got"

if grep -q -- '--budget' "$PLUGIN_ROOT/scripts/claude-headless-exec" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/scripts/grok-headless-exec" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/scripts/codex-headless-exec"; then
    ok "three runners advertise --budget"
else
    bad "runner --budget missing"
fi

if grep -q -- '--budget' "$PLUGIN_ROOT/commands/meta-execute.md" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/commands/grok-execute.md" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/commands/deep-execute.md" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/commands/codex-execute.md"; then
    ok "execute commands document --budget"
else
    bad "command --budget docs missing"
fi

echo
echo "passed=$PASS failed=$FAIL"
[[ "$FAIL" -eq 0 ]]
