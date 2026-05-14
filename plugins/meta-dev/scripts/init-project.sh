#!/usr/bin/env bash
set -euo pipefail
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"
DRY_RUN="${DRY_RUN:-false}"
AUTO="${AUTO:-false}"

confirm() { [ "$AUTO" = "true" ] && return 0; read -r -p "$1 [y/N] " r; [[ "$r" =~ ^[Yy]$ ]]; }

# Detect project name
PROJECT_NAME=""
if [ -f package.json ]; then
  PROJECT_NAME=$(python3 -c "import json; print(json.load(open('package.json')).get('name',''))" 2>/dev/null || true)
fi
if [ -z "$PROJECT_NAME" ]; then
  PROJECT_NAME=$(basename "$(pwd)")
fi
echo "Project: $PROJECT_NAME"

# Create plans structure
mkdir -p plans/{_dashboard/inbox/resolved,_archive/changelogs,_orchestrator}
echo "Created plans/ structure"

# Copy templates with substitution
TEMPLATES_DIR="$PLUGIN_ROOT/templates"
for tmpl in settings.json versioning.json changelog.json state.json inbox.jsonl INBOX.md.template state.events.jsonl; do
  src="$TEMPLATES_DIR/$tmpl"
  [ ! -f "$src" ] && echo "  SKIP $tmpl (no template)" && continue
  # Determine target path
  case "$tmpl" in
    settings.json) target="plans/_dashboard/settings.json" ;;
    versioning.json) target="plans/_dashboard/versioning.json" ;;
    changelog.json) target="plans/_dashboard/changelog.json" ;;
    state.json) target="plans/_dashboard/state.json" ;;
    inbox.jsonl) target="plans/_dashboard/inbox/inbox.jsonl" ;;
    INBOX.md.template) target="plans/_dashboard/INBOX.md" ;;
    state.events.jsonl) target="plans/_dashboard/state.events.jsonl" ;;
  esac
  # Idempotency: skip if exists with $schema
  if [ -f "$target" ] && grep -q '\$schema' "$target" 2>/dev/null; then
    echo "  SKIP $target (exists with \$schema)"
    continue
  fi
  # Substitute {{var}} placeholders
  sed "s/{{project_name}}/$PROJECT_NAME/g; s/{{today}}/$(date +%Y-%m-%d)/g" "$src" > "$target"
  echo "  CREATED $target"
done

# Append .gitignore entries
GITIGNORE_SRC="$TEMPLATES_DIR/gitignore.template"
if [ -f "$GITIGNORE_SRC" ]; then
  touch .gitignore
  while IFS= read -r line; do
    grep -qxF "$line" .gitignore 2>/dev/null || echo "$line" >> .gitignore
  done < "$GITIGNORE_SRC"
  echo "Appended .gitignore entries"
fi

# Append CLAUDE.md marker
CLAUDE_MARKER="Harness: meta-dev — config at plans/_dashboard/settings.json"
if [ -f CLAUDE.md ]; then
  grep -qF "$CLAUDE_MARKER" CLAUDE.md 2>/dev/null || echo -e "\n$CLAUDE_MARKER" >> CLAUDE.md
  echo "Added CLAUDE.md marker"
fi

# Bootstrap changelog
CHANGELOG_DIR="plans/_archive/changelogs"
TODAY=$(date +%Y-%m-%d)
CHANGELOG_FILE="$CHANGELOG_DIR/${TODAY}--present.md"
if [ ! -f "$CHANGELOG_FILE" ]; then
  echo "# Changelog — $PROJECT_NAME" > "$CHANGELOG_FILE"
  echo "" >> "$CHANGELOG_FILE"
  echo "## $TODAY" >> "$CHANGELOG_FILE"
  echo "" >> "$CHANGELOG_FILE"
  echo "- Project initialized with meta-dev harness" >> "$CHANGELOG_FILE"
  echo "Created $CHANGELOG_FILE"
fi

# Create STATUS.md and exec-order.md if missing
STATUS_FILE="plans/STATUS.md"
if [ ! -f "$STATUS_FILE" ]; then
  echo "# Project Status — $PROJECT_NAME" > "$STATUS_FILE"
  echo "" >> "$STATUS_FILE"
  echo "Active period: $TODAY — present" >> "$STATUS_FILE"
  echo "- Initializing meta-dev harness" >> "$STATUS_FILE"
  echo "Created $STATUS_FILE"
fi

EXEC_ORDER_FILE="plans/exec-order.md"
if [ ! -f "$EXEC_ORDER_FILE" ]; then
  echo "# Execution Order — $PROJECT_NAME" > "$EXEC_ORDER_FILE"
  echo "" >> "$EXEC_ORDER_FILE"
  echo "1. Define goals in STATUS.md" >> "$EXEC_ORDER_FILE"
  echo "Created $EXEC_ORDER_FILE"
fi

# Validate JSON files
if command -v python3 &>/dev/null; then
  for jf in plans/_dashboard/*.json; do
    [ -f "$jf" ] && python3 -m json.tool "$jf" > /dev/null 2>&1 && echo "  VALID $jf" || echo "  INVALID $jf"
  done
fi

echo "meta-dev harness initialized in $PROJECT_NAME"
