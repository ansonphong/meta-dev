#!/usr/bin/env bash
set -euo pipefail
# Meta-Dev Plugin Test Suite
# Usage: test-plugin.sh [--check-schemas] [--check-scripts] [--check-skills] [--check-commands] [--check-agents] [--check-hooks] [--check-init] [--check-all]

PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0

green() { echo -e "\033[32m$1\033[0m"; }
red() { echo -e "\033[31m$1\033[0m"; }

check_schemas() {
  echo "=== Schema Validation ==="
  for f in "$PLUGIN_DIR"/schemas/*.schema.json; do
    if python3 -c "import json,jsonschema; s=json.load(open('$f')); jsonschema.Draft7Validator.check_schema(s); print('OK')" 2>&1; then
      PASS=$((PASS+1)); green "  PASS: $(basename "$f")"
    else
      FAIL=$((FAIL+1)); red "  FAIL: $(basename "$f")"
    fi
  done
}

check_templates() {
  echo "=== Template Validation ==="
  for name in settings versioning changelog state; do
    schema="$PLUGIN_DIR/schemas/${name}.schema.json"
    template="$PLUGIN_DIR/templates/${name}.json"
    if [ -f "$template" ]; then
      if python3 -c "import json,jsonschema; s=json.load(open('$schema')); t=json.load(open('$template')); jsonschema.validate(t,s); print('OK')" 2>&1; then
        PASS=$((PASS+1)); green "  PASS: templates/$name.json"
      else
        FAIL=$((FAIL+1)); red "  FAIL: templates/$name.json"
      fi
    fi
  done
}

check_scripts() {
  echo "=== Script Lint ==="
  if command -v shellcheck &>/dev/null; then
    for f in "$PLUGIN_DIR"/scripts/*.sh "$PLUGIN_DIR"/hooks/scripts/*.sh; do
      if shellcheck -S warning -x "$f" 2>&1; then
        PASS=$((PASS+1)); green "  PASS shellcheck: $(basename "$f")"
      else
        FAIL=$((FAIL+1)); red "  FAIL shellcheck: $(basename "$f")"
      fi
    done
  else
    echo "  SKIP: shellcheck not installed"
  fi
  for f in "$PLUGIN_DIR"/scripts/*.py; do
    if python3 -m py_compile "$f" 2>&1; then
      PASS=$((PASS+1)); green "  PASS py_compile: $(basename "$f")"
    else
      FAIL=$((FAIL+1)); red "  FAIL py_compile: $(basename "$f")"
    fi
  done
}

check_skill_frontmatter() {
  local skill_file="$1"
  python3 -c "
import re
with open('$skill_file') as f:
    content = f.read()
assert content.startswith('---'), 'No frontmatter'
parts = content.split('---', 2)
assert len(parts) >= 3, 'Malformed frontmatter'
fm = parts[1]
assert 'name:' in fm, 'Missing name in frontmatter'
assert 'description:' in fm, 'Missing description in frontmatter'
print('OK')
"
}

check_skills() {
  echo "=== Skill Validation ==="
  for skill_dir in "$PLUGIN_DIR"/skills/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    skill_file="$skill_dir/SKILL.md"
    if [ -f "$skill_file" ]; then
      if check_skill_frontmatter "$skill_file" 2>&1; then
        PASS=$((PASS+1)); green "  PASS skill: $skill_name"
      else
        FAIL=$((FAIL+1)); red "  FAIL skill: $skill_name"
      fi
      # Check references exist
      refs=$(grep -o 'references/[a-zA-Z0-9_/.-]*\.md' "$skill_file" 2>/dev/null || true)
      for ref in $refs; do
        ref_path="$skill_dir/$ref"
        if [ ! -f "$ref_path" ]; then
          FAIL=$((FAIL+1)); red "  FAIL: $skill_name — missing reference: $ref"
        fi
      done
    fi
  done
}

check_command_frontmatter() {
  local cmd_file="$1"
  python3 -c "
import os
# Heavy procedure-commands carry their full spec in the command body by design
# (massively-parallel agent swarms, wave protocols). Thin-delegate commands stay <=50.
HEAVY = {'meta-dev', 'meta-loop-gap', 'meta-probe', 'meta-visual-critique', 'meta-planner', 'meta-execute', 'housekeeping', 'deep-execute', 'glm-execute', 'sonnet-execute', 'opus-execute', 'fable-execute', 'codex-execute', 'grok-execute', 'auto-execute'}
name = os.path.basename('$cmd_file')[:-3]
with open('$cmd_file') as f:
    content = f.read()
assert content.startswith('---'), 'No frontmatter'
parts = content.split('---', 2)
assert len(parts) >= 3, 'Malformed frontmatter'
fm = parts[1]
assert 'name:' in fm, 'Missing name'
assert 'description:' in fm, 'Missing description'
body = parts[2].strip()
lines = body.count('\n') + 1
if name not in HEAVY:
    assert lines <= 50, f'Body too long: {lines} lines (max 50) — keep thin or add to HEAVY allowlist'
print('OK')
"
}

check_commands() {
  echo "=== Command Validation ==="
  for cmd_file in "$PLUGIN_DIR"/commands/*.md; do
    cmd_name=$(basename "$cmd_file" .md)
    if check_command_frontmatter "$cmd_file" 2>&1; then
      PASS=$((PASS+1)); green "  PASS command: $cmd_name"
    else
      local err
      err=$(check_command_frontmatter "$cmd_file" 2>&1)
      FAIL=$((FAIL+1)); red "  FAIL command: $cmd_name — $err"
    fi
  done
}

check_agent_frontmatter() {
  local agent_file="$1"
  python3 -c "
with open('$agent_file') as f:
    content = f.read()
assert content.startswith('---'), 'No frontmatter'
parts = content.split('---', 2)
assert len(parts) >= 3, 'Malformed frontmatter'
fm = parts[1]
assert 'name:' in fm, 'Missing name'
assert 'description:' in fm, 'Missing description'
assert 'model:' in fm, 'Missing model'
print('OK')
"
}

check_agents() {
  echo "=== Agent Validation ==="
  for agent_file in "$PLUGIN_DIR"/agents/*.md; do
    [ -f "$agent_file" ] || continue
    agent_name=$(basename "$agent_file" .md)
    if check_agent_frontmatter "$agent_file" 2>&1; then
      PASS=$((PASS+1)); green "  PASS agent: $agent_name"
    else
      FAIL=$((FAIL+1)); red "  FAIL agent: $agent_name"
    fi
  done
}

check_hooks() {
  echo "=== Hook Validation ==="
  for hook in "$PLUGIN_DIR"/hooks/scripts/*.sh; do
    [ -f "$hook" ] || continue
    if [ -x "$hook" ]; then
      PASS=$((PASS+1)); green "  PASS executable: $(basename "$hook")"
    else
      chmod +x "$hook" 2>/dev/null || true
      if [ -x "$hook" ]; then
        PASS=$((PASS+1)); green "  PASS executable (fixed): $(basename "$hook")"
      else
        FAIL=$((FAIL+1)); red "  FAIL not executable: $(basename "$hook")"
      fi
    fi
    if head -1 "$hook" | grep -q '^#!/'; then
      PASS=$((PASS+1)); green "  PASS shebang: $(basename "$hook")"
    else
      FAIL=$((FAIL+1)); red "  FAIL shebang: $(basename "$hook")"
    fi
  done
}

check_init() {
  echo "=== Init Test ==="
  local FIXTURE="$PLUGIN_DIR/tests/fixtures/blank-project"
  if [ -d "$FIXTURE" ]; then
    local TMPDIR
    TMPDIR=$(mktemp -d)
    cp -r "$FIXTURE" "$TMPDIR/test-project"
    cd "$TMPDIR/test-project"
    if CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" AUTO=true bash "$PLUGIN_DIR/scripts/init-project.sh" 2>&1; then
      for f in plans/_dashboard/settings.json plans/_dashboard/state.json plans/meta-runbook.md; do
        if [ -f "$f" ]; then
          PASS=$((PASS+1)); green "  PASS init creates: $f"
        else
          FAIL=$((FAIL+1)); red "  FAIL init missing: $f"
        fi
      done
    else
      FAIL=$((FAIL+1)); red "  FAIL init-project.sh returned non-zero"
    fi
    rm -rf "$TMPDIR"
  else
    echo "  SKIP: blank-project fixture not found"
  fi
}

check_headless() {
  echo "=== Headless Runner Smoke ==="
  local claude_exec="$PLUGIN_DIR/scripts/claude-headless-exec"
  local codex_exec="$PLUGIN_DIR/scripts/codex-headless-exec"
  local topo="$PLUGIN_DIR/scripts/lib/repo-topology.py"

  # claude-headless-exec exists, executable, shebang
  if [ -f "$claude_exec" ]; then
    PASS=$((PASS+1)); green "  PASS exists: scripts/claude-headless-exec"
  else
    FAIL=$((FAIL+1)); red "  FAIL missing: scripts/claude-headless-exec"
  fi
  if [ -x "$claude_exec" ]; then
    PASS=$((PASS+1)); green "  PASS executable: scripts/claude-headless-exec"
  else
    FAIL=$((FAIL+1)); red "  FAIL not executable: scripts/claude-headless-exec"
  fi
  if head -1 "$claude_exec" | grep -q '^#!/'; then
    PASS=$((PASS+1)); green "  PASS shebang: scripts/claude-headless-exec"
  else
    FAIL=$((FAIL+1)); red "  FAIL missing shebang: scripts/claude-headless-exec"
  fi

  # codex-headless-exec exists, executable, shebang
  if [ -f "$codex_exec" ]; then
    PASS=$((PASS+1)); green "  PASS exists: scripts/codex-headless-exec"
  else
    FAIL=$((FAIL+1)); red "  FAIL missing: scripts/codex-headless-exec"
  fi
  if [ -x "$codex_exec" ]; then
    PASS=$((PASS+1)); green "  PASS executable: scripts/codex-headless-exec"
  else
    FAIL=$((FAIL+1)); red "  FAIL not executable: scripts/codex-headless-exec"
  fi
  if head -1 "$codex_exec" | grep -q '^#!/'; then
    PASS=$((PASS+1)); green "  PASS shebang: scripts/codex-headless-exec"
  else
    FAIL=$((FAIL+1)); red "  FAIL missing shebang: scripts/codex-headless-exec"
  fi

  # Offline topology resolution (NO real backend call)
  local TMPDIR
  TMPDIR=$(mktemp -d)
  mkdir -p "$TMPDIR/.claude"
  cat > "$TMPDIR/.claude/meta-dev-repos.json" <<'EOF'
{
  "root": "..",
  "repos": {
    "test-repo": "test-repo-dir"
  }
}
EOF
  mkdir -p "$TMPDIR/test-repo-dir"
  local resolved
  resolved=$(cd "$TMPDIR" && python3 "$topo" test-repo 2>/dev/null || true)
  if [ -n "$resolved" ] && [ -d "$resolved" ]; then
    PASS=$((PASS+1)); green "  PASS repo-topology resolves known name"
  else
    FAIL=$((FAIL+1)); red "  FAIL repo-topology resolution (got: '$resolved')"
  fi
  resolved=$(cd "$TMPDIR" && python3 "$topo" nope 2>/dev/null || true)
  if [ -z "$resolved" ]; then
    PASS=$((PASS+1)); green "  PASS repo-topology empty for unknown name"
  else
    FAIL=$((FAIL+1)); red "  FAIL repo-topology should be empty for unknown name (got: '$resolved')"
  fi
  rm -rf "$TMPDIR"

  # ── context-gauge: exists + threshold logic (hermetic via HOME override) ──
  local gauge="$PLUGIN_DIR/scripts/context-gauge.py"
  if [ -x "$gauge" ]; then
    PASS=$((PASS+1)); green "  PASS exists+exec: scripts/context-gauge.py"
  else
    FAIL=$((FAIL+1)); red "  FAIL missing/!exec: scripts/context-gauge.py"
  fi
  local GHOME GSID gdir gout
  GHOME=$(mktemp -d); GSID="testsession-0001"; gdir="$GHOME/.claude/projects/proj"
  mkdir -p "$gdir"
  printf '%s\n' '{"message":{"usage":{"input_tokens":10,"cache_read_input_tokens":350000,"cache_creation_input_tokens":0}}}' > "$gdir/$GSID.jsonl"
  gout=$(HOME="$GHOME" CLAUDE_CODE_SESSION_ID="$GSID" python3 "$gauge" --threshold 300000 2>/dev/null || true)
  if echo "$gout" | grep -q 'CONTEXT_VERDICT=OVER'; then
    PASS=$((PASS+1)); green "  PASS context-gauge OVER above threshold"
  else
    FAIL=$((FAIL+1)); red "  FAIL context-gauge should be OVER (got: $(echo "$gout" | tr '\n' ' '))"
  fi
  gout=$(HOME="$GHOME" CLAUDE_CODE_SESSION_ID="$GSID" python3 "$gauge" --threshold 900000 2>/dev/null || true)
  if echo "$gout" | grep -q 'CONTEXT_VERDICT=OK'; then
    PASS=$((PASS+1)); green "  PASS context-gauge OK below threshold"
  else
    FAIL=$((FAIL+1)); red "  FAIL context-gauge should be OK (got: $(echo "$gout" | tr '\n' ' '))"
  fi
  rm -rf "$GHOME"
}

# Main
cd "$PLUGIN_DIR/../.."  # cd to repo root

case "${1:-}" in
  --check-schemas) check_schemas; check_templates ;;
  --check-scripts) check_scripts ;;
  --check-skills) check_skills ;;
  --check-commands) check_commands ;;
  --check-agents) check_agents ;;
  --check-hooks) check_hooks ;;
  --check-init) check_init ;;
  --check-headless) check_headless ;;
  *)
    check_schemas
    check_templates
    check_scripts
    check_skills
    check_commands
    check_agents
    check_hooks
    check_init
    check_headless
    ;;
esac

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -eq 0 ]; then green "ALL CHECKS PASSED"; else red "SOME CHECKS FAILED"; fi
exit "$FAIL"
