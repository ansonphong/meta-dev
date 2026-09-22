#!/usr/bin/env bash
# jev-decide.sh — keyword budget + risk-tag + optional Jev suggestion.
# Missing key fails open. Does not spawn a worker and does not run git.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_BUDGET=""
MOCK=0
TASK=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --budget) USER_BUDGET="${2:-}"; shift 2 ;;
        --mock) MOCK=1; shift ;;
        --) shift; TASK="$*"; break ;;
        *) TASK="$*"; break ;;
    esac
done

if [[ -z "${TASK//[[:space:]]/}" ]]; then
    printf '%s\n' '{"fail_open":true,"reason":"empty_task","budget":"medium","hotl":null,"answers":{}}'
    exit 0
fi

BUDGET="$(bash "$SCRIPT_DIR/classify-execute-budget.sh" -- "$TASK")"
TAGS="$(printf '%s' "$TASK" | bash "$SCRIPT_DIR/risk-tag.sh")"
if [[ "$MOCK" == 1 ]]; then
    export JEV_MOCK=1
fi

export JEV_LIB="$SCRIPT_DIR/lib"
export JEV_TASK="$TASK"
export JEV_BUDGET="$BUDGET"
export JEV_TAGS="$TAGS"
export JEV_USER_BUDGET="$USER_BUDGET"

python3 - <<'PY'
import importlib.util
import json
import os

def load(filename):
    path = os.path.join(os.environ["JEV_LIB"], filename)
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_").replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

client = load("jev-client.py")
compose_mod = load("jev-compose.py")
result = client.evaluate(os.environ["JEV_TASK"], client.DISPATCH_QUESTIONS)
user_budget = os.environ.get("JEV_USER_BUDGET") or None
out = compose_mod.compose(
    os.environ["JEV_BUDGET"],
    os.environ["JEV_TAGS"],
    result.get("answers") or {},
    fail_open=bool(result.get("fail_open")),
    user_budget=user_budget,
)
out["mock"] = bool(result.get("mock"))
out["reason"] = result.get("reason") or ""
print(json.dumps(out, sort_keys=True))
PY
