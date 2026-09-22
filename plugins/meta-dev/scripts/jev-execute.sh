#!/usr/bin/env bash
# jev-execute.sh — print typed Jev answers. Does not spawn a worker.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOCK=0
STATE=""
QUESTIONS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mock) MOCK=1; shift ;;
        --json) shift ;;
        --question)
            QUESTIONS+=("${2:-}")
            shift 2
            ;;
        --) shift; STATE="$*"; break ;;
        *) STATE="$*"; break ;;
    esac
done

if [[ "$MOCK" == 1 ]]; then
    export JEV_MOCK=1
fi

export JEV_LIB="$SCRIPT_DIR/lib"
export JEV_STATE="$STATE"
JEV_QUESTIONS_RAW=""
if [[ ${#QUESTIONS[@]} -gt 0 ]]; then
    JEV_QUESTIONS_RAW="$(printf '%s\n' "${QUESTIONS[@]}")"
fi
export JEV_QUESTIONS_RAW

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

questions = {}
raw = os.environ.get("JEV_QUESTIONS_RAW") or ""
for line in raw.splitlines():
    line = line.strip()
    if not line:
        continue
    parts = line.split(":", 2)
    if len(parts) < 3:
        continue
    qid, kind, instructions = parts
    kind = kind.strip()
    spec = {"type": kind, "instructions": instructions.strip()}
    if kind == "choice":
        spec["criteria"] = {"yes": "yes", "no": "no"}
    elif kind == "score":
        spec["criteria"] = ["low", "high"]
    questions[qid.strip()] = spec

if not questions:
    questions = client.PROGNOSTICATE_QUESTIONS

result = client.evaluate(os.environ.get("JEV_STATE") or "", questions)
print(json.dumps(result, sort_keys=True))
PY
