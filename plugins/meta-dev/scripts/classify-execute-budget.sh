#!/usr/bin/env bash
# classify-execute-budget.sh — print the resolved execution budget for a task.
# Doctrine: references/execute-budget.md
#
# Usage:
#   classify-execute-budget.sh [--campaign auto|low|medium|high] -- <task text>
#
# Prints one word: low | medium | high
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/execute-budget.sh
source "$SCRIPT_DIR/lib/execute-budget.sh"

CAMPAIGN="auto"
TASK=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --campaign) CAMPAIGN="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        --) shift; TASK="$*"; break ;;
        *) TASK="$*"; break ;;
    esac
done

if [[ -z "${TASK//[[:space:]]/}" ]]; then
    echo "[ERROR] classify-execute-budget: empty task — nothing to classify." >&2
    exit 1
fi

CAMPAIGN="$(md_normalize_budget_word "$CAMPAIGN")"
if [[ -z "$CAMPAIGN" ]]; then
    echo "[ERROR] Invalid --campaign. Use auto, low, medium, or high." >&2
    exit 1
fi

TASK_LEVEL="$(md_classify_budget_from_text "$TASK")"
md_clamp_budget "$TASK_LEVEL" "$CAMPAIGN"
