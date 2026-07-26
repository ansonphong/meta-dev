#!/usr/bin/env bash
set -euo pipefail
# risk-tag.sh — Deterministic risk classification from task text.
#
# Ships a GENERIC baseline keyword set per category. Projects add their own
# domain keywords (no plugin edit needed) via the settings cascade at:
#   meta_dev.execute.risk_keywords.<category>
# where <category> is one of:
#   schema_drift | security_boundary | release_stability | money_path | perf_cache
# Project keywords are merged into the baseline at match time.
#
# Usage: echo "$task_body" | bash scripts/risk-tag.sh
# Output: comma-separated tags, or "none"

TEXT=$(cat)
TAGS=""

# Word-boundary helper: \b plus underscore (for code identifiers like validate_token)
B='(\b|_)'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/plugin-root.sh
source "$SCRIPT_DIR/lib/plugin-root.sh"
PLUGIN_ROOT="$(_md_plugin_root)"

# Pull project-supplied extra keywords once (failure-safe: empty on any error / no config).
EXTRA_ALL=$(python3 -c '
import json, subprocess, sys
cats = ["schema_drift", "security_boundary", "release_stability", "money_path", "perf_cache"]
try:
    out = subprocess.run(["python3", sys.argv[1] + "/scripts/config-merge.py"],
                         capture_output=True, text=True, timeout=10).stdout
    rk = json.loads(out).get("meta_dev", {}).get("execute", {}).get("risk_keywords", {})
    if not isinstance(rk, dict):
        rk = {}
except Exception:
    rk = {}
for c in cats:
    kw = rk.get(c, []) if isinstance(rk.get(c, []), list) else []
    print(c + "\t" + "|".join(str(k).strip() for k in kw if str(k).strip()))
' "$PLUGIN_ROOT" 2>/dev/null || true)

# extra <category> -> project keyword alternation (may be empty)
extra() { printf '%s\n' "$EXTRA_ALL" | awk -F'\t' -v c="$1" '$1==c{print $2}'; }

# match <category> <baseline-alternation>
match() {
  local base="$2" ex
  ex=$(extra "$1")
  [ -n "$ex" ] && base="${base}|${ex}"
  echo "$TEXT" | grep -qiE "${B}(${base})${B}"
}

if match schema_drift      "migration|alembic|schema|postgres|sqlite|mysql|ALTER TABLE|CREATE TABLE|DROP TABLE|ddl"; then TAGS="${TAGS}schema-drift,"; fi
if match security_boundary "permission|license|auth|authz|jwt|token|oauth|session|credential|password|secret|private.key|api.key|signing.key"; then TAGS="${TAGS}security-boundary,"; fi
if match release_stability "release|version.string|version.manifest|signature|changelog|semver|git.tag"; then TAGS="${TAGS}release-stability,"; fi
if match money_path        "payment|billing|charge|refund|subscription|invoice|checkout|webhook|balance"; then TAGS="${TAGS}money-path,"; fi
if match perf_cache        "cache|redis|memcache|celery|queue|worker|throttle|rate.limit|pipeline"; then TAGS="${TAGS}perf/cache,"; fi

if [ -z "$TAGS" ]; then
  echo "none"
else
  echo "${TAGS%,}"
fi
