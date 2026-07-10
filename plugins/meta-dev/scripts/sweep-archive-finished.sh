#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$SCRIPT_DIR/lib/anchor-root.sh"
# sweep-archive-finished.sh — archive ONLY finished plans. Never by age.
#
# Age is NEVER a reason to archive. A plan that is old but unfinished STAYS.
# A plan is archived if and only if the deterministic archive-guard says PASS
# (YAML status: Done, no unchecked boxes, no active-work markers, not listed
# active in meta-runbook.md `## Sequence`). This is the same guard /housekeeping
# uses — single source of truth for "is this plan finished?".
#
# Never delete — move only.

GUARD="$SCRIPT_DIR/archive-guard.sh"
PLANS_DIR="plans"

[ -f "$GUARD" ] || { echo "error: archive-guard.sh not found at $GUARD" >&2; exit 1; }
[ -d "$PLANS_DIR" ] || { echo "no plans/ dir — nothing to sweep"; exit 0; }

find "$PLANS_DIR" -name "*.md" -not -path "*/_archive/*" -not -path "*/_dashboard/*" -print0 \
  | while IFS= read -r -d '' file; do
  # The guard is the ONLY archive criterion. PASS => finished => archive.
  if guard_out="$(bash "$GUARD" "$file" 2>&1)"; then
    rel="${file#"$PLANS_DIR"/}"        # e.g. app/feature/00-master-plan.md
    repo="${rel%%/*}"                  # e.g. app
    if [ "$repo" = "$rel" ]; then
      dest="$PLANS_DIR/_archive"       # top-level plan file
    else
      dest="$PLANS_DIR/$repo/_archive"
    fi
    mkdir -p "$dest"
    echo "archive (finished): $file → $dest/"
    mv "$file" "$dest/"
  else
    # guard BLOCKed — plan is unfinished/in-development. Leave it. Say why.
    echo "keep: $file (${guard_out})"
  fi
done
