#!/usr/bin/env bash
# Deterministic plan consistency checks. Accept a plan directory or Markdown file.
# Exit codes: 0 = clean, 1 = warnings, 2 = errors.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/planner-validate.py" "$@"
