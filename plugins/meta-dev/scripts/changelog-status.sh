#!/usr/bin/env bash
set -euo pipefail
CHANGELOG_DIR="plans/_archive/changelogs"
PRESENT_FILE=$(ls "$CHANGELOG_DIR"/*--present.md 2>/dev/null | head -1)

if [ -z "$PRESENT_FILE" ]; then
  echo "No active changelog period."
  exit 0
fi

TOTAL=$(grep -c '^- \[' "$PRESENT_FILE" 2>/dev/null || echo 0)
BREAKING=$(grep -c 'breaking' "$PRESENT_FILE" 2>/dev/null || echo 0)
FEAT=$(grep -c 'feat' "$PRESENT_FILE" 2>/dev/null || echo 0)
FIX=$(grep -c 'fix' "$PRESENT_FILE" 2>/dev/null || echo 0)
CHORE=$(grep -c 'chore' "$PRESENT_FILE" 2>/dev/null || echo 0)

BUMP="patch"
[ "$BREAKING" -gt 0 ] && BUMP="major"
[ "$BREAKING" -eq 0 ] && [ "$FEAT" -gt 0 ] && BUMP="minor"

echo "Active: $(basename "$PRESENT_FILE")"
echo "Entries: $TOTAL"
echo "  breaking: $BREAKING  feat: $FEAT  fix: $FIX  chore: $CHORE"
echo "Suggested bump: $BUMP"
