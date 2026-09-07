#!/usr/bin/env bash
# Behavioral coverage of focused acceptance and adaptive host dispatch.
set -euo pipefail
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PLUGIN_ROOT"
python3 -m pytest -q -p no:cacheprovider \
  tests/test_adaptive_workflow_contract.py \
  tests/test_verify_scope.py \
  tests/test_planner_validate.py
