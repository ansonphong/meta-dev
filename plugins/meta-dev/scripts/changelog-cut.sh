#!/usr/bin/env bash
# shellcheck disable=SC2034
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
PLUGIN_ROOT="$(_md_plugin_root)"
DRY_RUN=false
[ "${1:-}" = "--dry-run" ] && DRY_RUN=true

CHANGELOG_DIR="plans/_archive/changelogs"
PRESENT_FILE=$(ls "$CHANGELOG_DIR"/*--present.md 2>/dev/null | head -1)
[ -z "$PRESENT_FILE" ] && { echo "No active changelog period found."; exit 1; }

# Count entries by tag
TOTAL=$(grep -c '^- \[' "$PRESENT_FILE" 2>/dev/null || echo 0)
BREAKING=$(grep -c 'breaking' "$PRESENT_FILE" 2>/dev/null || echo 0)
FEAT=$(grep -c 'feat' "$PRESENT_FILE" 2>/dev/null || echo 0)

# Determine bump type
BUMP="patch"
[ "$BREAKING" -gt 0 ] && BUMP="major"
[ "$BREAKING" -eq 0 ] && [ "$FEAT" -gt 0 ] && BUMP="minor"

# Generate slug from first feat title or date
SLUG=$(grep '^- \[' "$PRESENT_FILE" | head -1 | sed 's/.*\*\*\(.*\)\*\*.*/\1/' | tr 'A-Z ' 'a-z-' | tr -cd 'a-z0-9-' | cut -c1-40)
[ -z "$SLUG" ] && SLUG="changelog-cut"

SINCE=$(basename "$PRESENT_FILE" | cut -d- -f1-3)
UNTIL=$(date +%Y-%m-%d)
SHA_SHORT=$(git rev-parse --short HEAD 2>/dev/null || echo "0000000")

CLOSED_FILE="$CHANGELOG_DIR/${SINCE}--${UNTIL}-${SHA_SHORT}-${SLUG}.md"
NEW_PRESENT="$CHANGELOG_DIR/${UNTIL}--present.md"

if $DRY_RUN; then
  echo "DRY RUN — would:"
  echo "  Entries: $TOTAL (breaking=$BREAKING feat=$FEAT)"
  echo "  Bump: $BUMP"
  echo "  Rename: $PRESENT_FILE → $CLOSED_FILE"
  echo "  Create: $NEW_PRESENT"
  exit 0
fi

mv "$PRESENT_FILE" "$CLOSED_FILE"
echo "# Changelog" > "$NEW_PRESENT"
echo "" >> "$NEW_PRESENT"

echo "Cut changelog:"
echo "  Closed: $CLOSED_FILE ($TOTAL entries)"
echo "  New: $NEW_PRESENT"
echo "  Suggested bump: $BUMP"

# If version-manager auto_bump_on_cut, print hint
echo "  Run: /meta-version bump --type $BUMP to apply version bump"
