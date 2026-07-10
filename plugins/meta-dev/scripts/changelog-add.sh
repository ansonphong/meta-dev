#!/usr/bin/env bash
# shellcheck disable=SC2034
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

TAG=""; TITLE=""; BODY=""; SHA="${GIT_SHA:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --body) BODY="$2"; shift 2 ;;
    --sha) SHA="$2"; shift 2 ;;
    *) shift ;;
  esac
done

[ -z "$TAG" ] && { echo "Usage: changelog-add.sh --tag <tag> --title <title> --body <body> [--sha <sha>]"; exit 1; }
[ -z "$TITLE" ] && { echo "Missing --title"; exit 1; }

CHANGELOG_DIR="plans/_archive/changelogs"
mkdir -p "$CHANGELOG_DIR"

PRESENT_FILE=$(ls "$CHANGELOG_DIR"/*--present.md 2>/dev/null | head -1)
if [ -z "$PRESENT_FILE" ]; then
  PRESENT_FILE="$CHANGELOG_DIR/$(date +%Y-%m-%d)--present.md"
  echo "# Changelog" > "$PRESENT_FILE"
  echo "" >> "$PRESENT_FILE"
fi

SHA_STR=""
[ -n "$SHA" ] && SHA_STR=" (\`$SHA\`)"

# Append: "- [tag] Title — Body (sha7)"
ENTRY="- [\`$TAG\`] **$TITLE**"
[ -n "$BODY" ] && ENTRY="$ENTRY — $BODY"
ENTRY="$ENTRY$SHA_STR"

# Insert after header (line 3)
if grep -q "^\- " "$PRESENT_FILE"; then
  # Insert after last header line (after blank line following "# Changelog")
  sed -i '' "3a\\
$ENTRY
" "$PRESENT_FILE" 2>/dev/null || sed -i "3a\\$ENTRY" "$PRESENT_FILE"
else
  echo "$ENTRY" >> "$PRESENT_FILE"
fi

echo "Added: $ENTRY"
