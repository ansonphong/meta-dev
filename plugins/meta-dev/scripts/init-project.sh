#!/usr/bin/env bash
set -euo pipefail
LEGACY_CLAUDE_INIT=false
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -z "${META_DEV_PLUGIN_ROOT:-}" ] && [ -z "${PLUGIN_ROOT:-}" ] && LEGACY_CLAUDE_INIT=true
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/plugin-root.sh
source "$SCRIPT_DIR/lib/plugin-root.sh"
PLUGIN_ROOT="$(_md_plugin_root)"
DRY_RUN="${DRY_RUN:-false}"
AUTO="${AUTO:-false}"

# The doctor is the sole production contract classifier. Do this before any
# bootstrap write so conflicts never leave a half-initialized project behind.
CLASSIFICATION="$(python3 "$SCRIPT_DIR/agent-surface-doctor.py" --project-root "$(pwd -P)" --classify)"
CONTRACT_STATE="$(python3 -c 'import json, sys; print(json.load(sys.stdin)["projects"][0]["contract"]["state"])' <<<"$CLASSIFICATION")"
case "$CONTRACT_STATE" in
  missing|canonical|adapter) ;;
  compatibility) echo "Migration warning: legacy Claude contract detected; AGENTS.md is now canonical" ;;
  casefold_alias|duplicate_copy|conflict)
    echo "Refusing to initialize: contract discovery state is $CONTRACT_STATE" >&2
    exit 1
    ;;
  *) echo "Refusing to initialize: unknown contract discovery state $CONTRACT_STATE" >&2; exit 1 ;;
esac

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

# Scaffold the neutral project contract. Legacy Claude files remain readable
# compatibility inputs, but AGENTS-first paths are always the initializer output.
mkdir -p .meta-dev docs/agent-context .agents/skills
[ -f .meta-dev/repos.json ] || cp "$TEMPLATES_DIR/repo-topology.json" .meta-dev/repos.json
if [ "$LEGACY_CLAUDE_INIT" = true ]; then
  mkdir -p .claude
  [ -f .claude/meta-dev-repos.json ] || cp "$TEMPLATES_DIR/repo-topology.json" .claude/meta-dev-repos.json
fi

if [ "$CONTRACT_STATE" = "missing" ] || [ "$CONTRACT_STATE" = "compatibility" ]; then
  cat > AGENTS.md <<'EOF'
# Project Agent Contract

This is the canonical project doctrine. Put durable routed context in
`docs/agent-context/` and canonical skills in `.agents/skills/`. Vendor
directories are adapters and must not repeat these rules.
EOF
  echo "Created AGENTS.md"
fi

# Append .gitignore entries
GITIGNORE_SRC="$TEMPLATES_DIR/gitignore.template"
if [ -f "$GITIGNORE_SRC" ]; then
  touch .gitignore
  while IFS= read -r line; do
    grep -qxF "$line" .gitignore 2>/dev/null || echo "$line" >> .gitignore
  done < "$GITIGNORE_SRC"
  echo "Appended .gitignore entries"
fi

# Legacy CLAUDE files are preserved for compatibility. Do not modify or create
# them here; AGENTS.md is the only preferred contract output.

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

# Create meta-runbook.md if missing — the single hand-maintained LIVE ledger.
# Status/stage/% live in each plan's YAML frontmatter (read live by the
# dashboard via plan-index.py); this file is the EDITORIAL layer ONLY:
# priority order (## Sequence), milestones, wave strategy. Keep it LEAN
# (~≤150 lines). Cold history goes to meta-runbook-archive.md — never
# paste closeout novels into the live file.
RUNBOOK_FILE="plans/meta-runbook.md"
if [ ! -f "$RUNBOOK_FILE" ]; then
  cat > "$RUNBOOK_FILE" <<EOF
# Meta-Runbook — Build Order & Release Ledger — $PROJECT_NAME

> Editorial layer ONLY. Status/stage/% are NOT stored here — the dashboard reads them live
> from each plan's YAML frontmatter + checkboxes. Edit this file to change PRIORITY ORDER,
> MILESTONES, or wave strategy — nothing else.
> **Lean rules:** path must exist · no \`/_archive/\` in Sequence · no status novels · one path once.
> **Cold history:** [meta-runbook-archive.md](meta-runbook-archive.md)

## Wave Strategy / Critical Path

_What to work on right now, in what order. Update as waves complete. Keep short._

## Sequence

_Ordered list of ACTIVE plan paths (build order). One \`plans/...\` path per line._
_Insert \`=== MILESTONE: TYPE · label ===\` markers between entries to mark releases._
_Active campaigns: \`=== RUNBOOK: plans/.../_runbook-….md · label ===\`._

## Residual / Not Auto-Tracked

_Short bullets only (blockers without a clean live plan path)._

## Shipped

> Full history: [meta-runbook-archive.md](meta-runbook-archive.md)
> After Stage 6: drop from Sequence; append one compact line to the archive file.
EOF
  echo "Created $RUNBOOK_FILE"
fi

ARCHIVE_FILE="plans/meta-runbook-archive.md"
if [ ! -f "$ARCHIVE_FILE" ]; then
  cat > "$ARCHIVE_FILE" <<EOF
# Meta-Runbook Archive — Cold History — $PROJECT_NAME

> Cold history only. Live ledger: [meta-runbook.md](meta-runbook.md).
> Do not load this into routine session context.
> Append one compact line per archived plan (newest first).

## Shipped

_Completed plans, newest first._
EOF
  echo "Created $ARCHIVE_FILE"
fi

# Validate JSON files
if command -v python3 &>/dev/null; then
  for jf in plans/_dashboard/*.json; do
    [ -f "$jf" ] && python3 -m json.tool "$jf" > /dev/null 2>&1 && echo "  VALID $jf" || echo "  INVALID $jf"
  done
fi

echo "meta-dev harness initialized in $PROJECT_NAME"
