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

# Scaffold repo-topology config from template (discrete — not the dashboard loop above)
mkdir -p .claude
[ -f .claude/meta-dev-repos.json ] || cp "$TEMPLATES_DIR/repo-topology.json" .claude/meta-dev-repos.json

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

# Create meta-runbook.md if missing — the single hand-maintained ledger.
# Status/stage/% live in each plan's YAML frontmatter (read live by the
# dashboard via plan-index.py); this file is the EDITORIAL layer ONLY:
# priority order (## Sequence), milestones, wave strategy, and shipped log.
RUNBOOK_FILE="plans/meta-runbook.md"
if [ ! -f "$RUNBOOK_FILE" ]; then
  cat > "$RUNBOOK_FILE" <<EOF
# Meta-Runbook — Build Order & Release Ledger — $PROJECT_NAME

> Editorial layer ONLY. Status/stage/% are NOT stored here — the dashboard reads them live
> from each plan's YAML frontmatter + checkboxes. Edit this file to change PRIORITY ORDER,
> MILESTONES, or wave strategy — nothing else.

## Wave Strategy / Critical Path

_What to work on right now, in what order. Update as waves complete._

## Sequence

_Ordered list of ACTIVE plan paths (build order). One \`plans/...\` path per line._
_Insert \`=== MILESTONE: TYPE · label ===\` markers between entries to mark releases._

## Shipped

_Completed plans, newest first (\`plans/.../00-master-plan.md — Title  (archived: ...)\`)._
EOF
  echo "Created $RUNBOOK_FILE"
fi

# Validate JSON files
if command -v python3 &>/dev/null; then
  for jf in plans/_dashboard/*.json; do
    [ -f "$jf" ] && python3 -m json.tool "$jf" > /dev/null 2>&1 && echo "  VALID $jf" || echo "  INVALID $jf"
  done
fi

echo "meta-dev harness initialized in $PROJECT_NAME"
