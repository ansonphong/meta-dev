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
[[ "$TIMEOUT" == "5400000" ]] && ok "medium timeout 90m" || bad "timeout $TIMEOUT"
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
[[ "$MAX_TURNS" == "12" && "$EFFORT" == "low" && "$TIMEOUT" == "1800000" ]] && ok "low maps turns/effort/timeout" || bad "low map t=$MAX_TURNS e=$EFFORT to=$TIMEOUT"

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
[[ "$TIMEOUT" == "10800000" ]] && ok "high timeout when not explicit" || bad "high timeout $TIMEOUT"

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

# --timeout unit parse + host-tool leak ignore
got="$(md_parse_timeout_to_ms 30m)"
[[ "$got" == "1800000" ]] && ok "30m → 1800000ms" || bad "30m → $got"
got="$(md_parse_timeout_to_ms 2h)"
[[ "$got" == "7200000" ]] && ok "2h → 7200000ms" || bad "2h → $got"
got="$(md_parse_timeout_to_ms 15)"
[[ "$got" == "15000" ]] && ok "bare 15 → 15s not 15ms" || bad "bare 15 → $got"
got="$(md_parse_timeout_to_ms 5400000)"
[[ "$got" == "5400000" ]] && ok "bare ms passthrough" || bad "bare ms → $got"

BUDGET="medium"
TIMEOUT="300000"
TIMEOUT_EXPLICIT=1
MAX_TURNS_EXPLICIT=0
EFFORT_EXPLICIT=0
STALL_SECS_EXPLICIT=0
BACKEND="grok"
unset META_DEV_ALLOW_SHORT_TIMEOUT || true
md_resolve_budget
[[ "$TIMEOUT" == "5400000" ]] && ok "host-leak 5min --timeout ignored" || bad "leak timeout $TIMEOUT"
[[ "$STALL_SECS" == "1350" ]] && ok "medium stall wall/4=1350" || bad "stall $STALL_SECS"

BUDGET="low"
TIMEOUT=""
TIMEOUT_EXPLICIT=0
STALL_SECS_EXPLICIT=0
md_resolve_budget
[[ "$STALL_SECS" == "1200" ]] && ok "low stall floors at 20m" || bad "low stall $STALL_SECS"

got="$("$PLUGIN_ROOT/scripts/classify-execute-budget.sh" --campaign medium -- "Rename foo")"
[[ "$got" == "low" ]] && ok "cli classify+clamp rename under medium" || bad "cli $got"

got="$("$PLUGIN_ROOT/scripts/classify-execute-budget.sh" --campaign low -- "Fix the Stripe webhook")"
[[ "$got" == "low" ]] && ok "cli campaign ceiling" || bad "cli ceiling $got"

if grep -q -- '--budget' "$PLUGIN_ROOT/scripts/claude-headless-exec" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/scripts/grok-headless-exec" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/scripts/codex-headless-exec" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/scripts/agy-headless-exec" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/scripts/cursor-headless-exec"; then
    ok "five runners advertise --budget"
else
    bad "runner --budget missing"
fi

# shellcheck source=../scripts/lib/execute-brief.sh
source "$PLUGIN_ROOT/scripts/lib/execute-brief.sh"
BACKEND=grok
PROMPT="do the thing"
md_brief_wrap_prompt
case "$PROMPT" in
    *"BACKEND BRIEF: Grok"*|*spawn_subagent*) ok "grok brief injected" ;;
    *) bad "grok brief missing" ;;
esac
BACKEND=deep
PROMPT="do the thing"
md_brief_wrap_prompt
case "$PROMPT" in
    *"BACKEND BRIEF: DeepSeek"*|*"Keep this unit SMALL"*) ok "deep brief injected" ;;
    *) bad "deep brief missing" ;;
esac
BACKEND=codex
PROMPT="do the thing"
md_brief_wrap_prompt
case "$PROMPT" in
    *"BACKEND BRIEF: Codex"*|*"not Claude Code"*) ok "codex brief injected" ;;
    *) bad "codex brief missing" ;;
esac
BACKEND=agy
PROMPT="do the thing"
md_brief_wrap_prompt
case "$PROMPT" in
    *"BACKEND BRIEF: Antigravity"*|*"not Claude Code"*) ok "agy brief injected" ;;
    *) bad "agy brief missing" ;;
esac
BACKEND=cursor
PROMPT="do the thing"
md_brief_wrap_prompt
case "$PROMPT" in
    *"BACKEND BRIEF: Cursor"*|*"not Claude Code"*) ok "cursor brief injected" ;;
    *) bad "cursor brief missing" ;;
esac

for BACKEND in grok deep codex opus sonnet fable glm agy cursor; do
    PROMPT="Review the supplied contract without edits."
    md_brief_wrap_prompt
    case "$PROMPT" in
        *"read-only work never edits or commits"*"per-outcome verification"*"Review the supplied contract without edits."*)
            ok "$BACKEND preserves intent, slice evidence, and task" ;;
        *) bad "$BACKEND lost task intent or slice evidence" ;;
    esac
    case "$PROMPT" in
        *"Farm independent pieces"*|*"REVIEW unless"*|*"One acceptance."*)
            bad "$BACKEND imposes conflicting delegation or role" ;;
        *) ok "$BACKEND leaves ownership and role to task" ;;
    esac
done

if grep -q 'md_brief_wrap_prompt' "$PLUGIN_ROOT/scripts/claude-headless-exec" \
    && grep -q 'md_brief_wrap_prompt' "$PLUGIN_ROOT/scripts/grok-headless-exec" \
    && grep -q 'md_brief_wrap_prompt' "$PLUGIN_ROOT/scripts/codex-headless-exec" \
    && grep -q 'md_brief_wrap_prompt' "$PLUGIN_ROOT/scripts/agy-headless-exec" \
    && grep -q 'md_brief_wrap_prompt' "$PLUGIN_ROOT/scripts/cursor-headless-exec"; then
    ok "five runners wrap per-backend brief"
else
    bad "runner brief wrap missing"
fi

if grep -q -- '--budget' "$PLUGIN_ROOT/commands/meta-execute.md" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/commands/grok-execute.md" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/commands/deep-execute.md" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/commands/codex-execute.md" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/commands/antigravity-execute.md" \
    && grep -q -- '--budget' "$PLUGIN_ROOT/commands/cursor-execute.md"; then
    ok "execute commands document --budget"
else
    bad "command --budget docs missing"
fi

echo
echo "passed=$PASS failed=$FAIL"
[[ "$FAIL" -eq 0 ]]
