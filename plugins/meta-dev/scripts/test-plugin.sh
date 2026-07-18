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
      # Check references exist. A ref may be skill-local ("references/x.md") OR
      # cross-skill ("other-skill/references/x.md") — capture the optional
      # leading skill segment so a cross-skill ref resolves against skills/,
      # not against THIS skill dir (which reported false missing-reference
      # failures for every cross-skill pointer).
      refs=$(grep -oE '[a-zA-Z0-9_.-]*/?references/[a-zA-Z0-9_/.-]*\.md' "$skill_file" 2>/dev/null || true)
      for ref in $refs; do
        case "$ref" in
          references/*) ref_path="$skill_dir/$ref" ;;
          *)            ref_path="$PLUGIN_DIR/skills/$ref" ;;
        esac
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

  # ── Offline topology resolution (NO real backend call) ──────────────────
  # These are cwd-INDEPENDENCE regressions. A conductor's shell keeps its cwd
  # between Bash calls, so a stray `cd child-repo/` used to (a) make every name
  # unresolvable, and (b) make the runners silently fall back to that cwd — so
  # `--repo www` ran a worker in the app repo, and plans/state forked into it.
  # `env -u` keeps a developer's real environment from leaking into the fixture.
  local anchor="$PLUGIN_DIR/scripts/lib/anchor-root.sh"
  # Array, not a string: keeps `env -u` from word-splitting at each call site.
  local -a HERM=(env -u META_DEV_REPOS_FILE -u CLAUDE_PROJECT_DIR)
  # NOTE: `local TMPDIR` shadows mktemp's own base-dir variable, so NOCFG must be
  # created BEFORE TMPDIR is assigned — otherwise it lands *inside* the fixture
  # and inherits its config, silently voiding the no-config assertions below.
  local NOCFG; NOCFG=$(mktemp -d)
  local TMPDIR
  TMPDIR=$(mktemp -d)
  mkdir -p "$TMPDIR/.claude" "$TMPDIR/test-repo-dir/deep/nested"
  cat > "$TMPDIR/.claude/meta-dev-repos.json" <<'EOF'
{
  "root": "..",
  "repos": {
    "test-repo": "test-repo-dir"
  }
}
EOF
  local NESTED="$TMPDIR/test-repo-dir/deep/nested"
  local resolved rc

  resolved=$(cd "$TMPDIR" && "${HERM[@]}" python3 "$topo" test-repo 2>/dev/null || true)
  if [ "$resolved" = "$TMPDIR/test-repo-dir" ]; then
    PASS=$((PASS+1)); green "  PASS repo-topology resolves known name"
  else
    FAIL=$((FAIL+1)); red "  FAIL repo-topology resolution (got: '$resolved')"
  fi

  # THE regression: resolve correctly from a cwd deep inside a child repo.
  resolved=$(cd "$NESTED" && "${HERM[@]}" python3 "$topo" test-repo 2>/dev/null || true)
  if [ "$resolved" = "$TMPDIR/test-repo-dir" ]; then
    PASS=$((PASS+1)); green "  PASS repo-topology resolves from nested child cwd (walks up)"
  else
    FAIL=$((FAIL+1)); red "  FAIL repo-topology from nested cwd (got: '$resolved')"
  fi

  # Unknown name must be FATAL (exit 1) — never a silent cwd fallback.
  rc=0
  resolved=$(cd "$NESTED" && "${HERM[@]}" python3 "$topo" nope 2>/dev/null) || rc=$?
  if [ "$rc" -ne 0 ] && [ -z "$resolved" ]; then
    PASS=$((PASS+1)); green "  PASS repo-topology exits nonzero for unknown name"
  else
    FAIL=$((FAIL+1)); red "  FAIL unknown name must exit nonzero + empty (rc=$rc out='$resolved')"
  fi

  # --root and the built-in meta alias, both from the nested cwd.
  resolved=$(cd "$NESTED" && "${HERM[@]}" python3 "$topo" --root 2>/dev/null || true)
  if [ "$resolved" = "$TMPDIR" ]; then
    PASS=$((PASS+1)); green "  PASS repo-topology --root from nested cwd"
  else
    FAIL=$((FAIL+1)); red "  FAIL repo-topology --root (got: '$resolved')"
  fi
  resolved=$(cd "$NESTED" && "${HERM[@]}" python3 "$topo" meta 2>/dev/null || true)
  if [ "$resolved" = "$TMPDIR" ]; then
    PASS=$((PASS+1)); green "  PASS repo-topology built-in 'meta' alias -> project root"
  else
    FAIL=$((FAIL+1)); red "  FAIL 'meta' alias (got: '$resolved')"
  fi

  # anchor-root.sh must cd a script back to the project root from a nested cwd.
  resolved=$(cd "$NESTED" && "${HERM[@]}" bash -c "source '$anchor' && pwd" 2>/dev/null || true)
  if [ "$resolved" = "$TMPDIR" ]; then
    PASS=$((PASS+1)); green "  PASS anchor-root.sh cds to project root from nested cwd"
  else
    FAIL=$((FAIL+1)); red "  FAIL anchor-root.sh (got: '$resolved')"
  fi

  # No config anywhere: --root must fail, and the anchor must leave cwd alone.
  rc=0
  (cd "$NOCFG" && "${HERM[@]}" python3 "$topo" --root >/dev/null 2>&1) || rc=$?
  if [ "$rc" -ne 0 ]; then
    PASS=$((PASS+1)); green "  PASS repo-topology --root exits nonzero with no config"
  else
    FAIL=$((FAIL+1)); red "  FAIL --root should fail when no config exists"
  fi
  resolved=$(cd "$NOCFG" && "${HERM[@]}" bash -c "source '$anchor' && pwd" 2>/dev/null || true)
  if [ "$resolved" = "$NOCFG" ]; then
    PASS=$((PASS+1)); green "  PASS anchor-root.sh leaves cwd alone with no config"
  else
    FAIL=$((FAIL+1)); red "  FAIL anchor-root.sh should not move cwd (got: '$resolved')"
  fi
  rm -rf "$TMPDIR" "$NOCFG"

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

check_runbook_gate() {
  echo "=== Runbook DONE-gate reconcile (on-run-complete Stop hook) ==="
  local hook="$PLUGIN_DIR/hooks/scripts/on-run-complete.sh"
  local render="$PLUGIN_DIR/scripts/runbook-render.py"

  if [ -f "$hook" ]; then
    PASS=$((PASS+1)); green "  PASS exists: hooks/scripts/on-run-complete.sh"
  else
    FAIL=$((FAIL+1)); red "  FAIL missing: hooks/scripts/on-run-complete.sh"; return
  fi

  # Hermetic project fixture. The member is ALREADY at stage 6 / done — the state
  # a conductor's closeout hand-flip leaves it in — while the campaign runbook
  # still shows the STALE stage-5 EXECUTING snapshot. This is the exact
  # frozen-dashboard bug: the plan left stage 5 before the hook could stamp+
  # render, and the OLD hook (re-render welded INSIDE the stage-5 branch) never
  # revisited it. Only the UNCONDITIONAL reconcile pass can refresh it.
  local RG; RG=$(mktemp -d)
  ( cd "$RG" && git init -q && git config user.email t@t.t && git config user.name t ) 2>/dev/null || true
  mkdir -p "$RG/plans/CAMPAIGN/50-FOO" "$RG/plans/_dashboard"
  cat > "$RG/plans/CAMPAIGN/50-FOO/00-master-plan.md" <<'EOF'
---
status: done
stage: 6
repo: app
why: congruent editor
updated: 2026-07-10
---
# 50-FOO — Master Plan
- [x] DONE Task 1
- [x] DONE Task 2
EOF
  cat > "$RG/plans/CAMPAIGN/_runbook-test.md" <<'EOF'
---
name: test-campaign
type: runbook
members:
  - plans/CAMPAIGN/50-FOO/00-master-plan.md
predecessor: null
---
# Test Campaign
<!-- RUNBOOK:PROGRESS:START (computed) -->
STALE frozen snapshot: 50 FOO stage 5 EXECUTING 95%
<!-- RUNBOOK:PROGRESS:END -->
EOF
  local RB="$RG/plans/CAMPAIGN/_runbook-test.md"

  # Fire the Stop hook. MAP is empty (no stage-5 plan under plans/), so ONLY the
  # unconditional reconcile can refresh — precisely the path the old hook lacked.
  echo '{}' | env CLAUDE_PROJECT_DIR="$RG" CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" bash "$hook" >/dev/null 2>&1 || true
  if grep -qi 'done' "$RB" && ! grep -qi 'EXECUTING' "$RB"; then
    PASS=$((PASS+1)); green "  PASS reconciles a hand-flipped stage-6 member to DONE (no stamp branch)"
  else
    FAIL=$((FAIL+1)); red "  FAIL runbook not reconciled (still EXECUTING / no DONE)"
  fi

  # cwd-INDEPENDENCE: re-stale the block, fire the hook from a FOREIGN cwd (a
  # leaked child-repo shell). It must still refresh, because it anchors on
  # CLAUDE_PROJECT_DIR — not on wherever the session's shell happens to sit.
  python3 - "$RB" <<'PYEOF'
import sys, re
p = sys.argv[1]
t = open(p, encoding='utf-8').read()
t = re.sub(r'(RUNBOOK:PROGRESS:START.*?-->).*?(<!-- RUNBOOK:PROGRESS:END)',
           r'\1\nSTALE again EXECUTING\n\2', t, flags=re.S)
open(p, 'w', encoding='utf-8').write(t)
PYEOF
  echo '{}' | ( cd / && env CLAUDE_PROJECT_DIR="$RG" CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" bash "$hook" >/dev/null 2>&1 ) || true
  if grep -qi 'done' "$RB" && ! grep -qi 'EXECUTING' "$RB"; then
    PASS=$((PASS+1)); green "  PASS reconciles from a foreign cwd (anchors on CLAUDE_PROJECT_DIR)"
  else
    FAIL=$((FAIL+1)); red "  FAIL foreign-cwd reconcile failed"
  fi

  # IDEMPOTENT render: a second render of an already-fresh runbook is a true
  # no-op on disk (content stable) — so the per-Stop reconcile never churns
  # mtimes (which would dirty the tree + defeat the dirty-file idle gate).
  local sha1 sha2
  sha1=$(md5sum "$RB" | cut -d' ' -f1)
  python3 "$render" "$RB" >/dev/null 2>&1 || true
  sha2=$(md5sum "$RB" | cut -d' ' -f1)
  if [ "$sha1" = "$sha2" ]; then
    PASS=$((PASS+1)); green "  PASS runbook-render.py idempotent (no-op on unchanged runbook)"
  else
    FAIL=$((FAIL+1)); red "  FAIL runbook-render.py rewrote an unchanged runbook"
  fi

  rm -rf "$RG"
}

# ── Deterministic task tracking (task-stamp / task-done / task-undone) ───────

check_task_stamp() {
  echo "=== Task Stamp ==="
  local S="$PLUGIN_DIR/scripts/task-stamp.py"
  local FIX
  FIX=$(mktemp -d)
  cat > "$FIX/master.md" <<'EOF'
# Fixture

### Phase 1 — Alpha
- [ ] First box
- [ ] Second box

**Phase 2 — Bold style**
- [ ] Bold phase box

### Phase 4a — Alphanumeric
- [ ] Alpha a box
- [x] Already done

### Phase 4b
- [ ] Beta box
EOF

  # T1.5 three heading styles
  python3 "$S" --check "$FIX/master.md" >"$FIX/check.out" 2>"$FIX/check.err" || true
  if grep -q 'T1\.1' "$FIX/check.out" \
     && grep -q 'T2\.1' "$FIX/check.out" \
     && grep -q 'T4a\.1' "$FIX/check.out" \
     && grep -q 'T4b\.1' "$FIX/check.out"; then
    PASS=$((PASS+1)); green "  PASS three heading styles (### / bold / 4a+4b)"
  else
    FAIL=$((FAIL+1)); red "  FAIL three heading styles"; cat "$FIX/check.out"
  fi

  python3 "$S" "$FIX/master.md" >/dev/null
  cp "$FIX/master.md" "$FIX/after1.md"
  python3 "$S" "$FIX/master.md" >/dev/null
  # T1.6 idempotent
  if cmp -s "$FIX/after1.md" "$FIX/master.md"; then
    PASS=$((PASS+1)); green "  PASS stamper idempotent (second run byte-identical)"
  else
    FAIL=$((FAIL+1)); red "  FAIL stamper not idempotent"
  fi

  # T1.14 regexes still count stamped lines
  local open_n
  open_n=$(grep -cE '^[[:space:]]*[-*][[:space:]]+\[[[:space:]]\]' "$FIX/master.md" || true)
  if [ "${open_n:-0}" -ge 1 ] && grep -qE '^\s*[-*]\s*\[[ xX]\]\s*`T' "$FIX/master.md"; then
    # plan-index CHECKBOX pattern
    if python3 -c "
import re,sys
CHECKBOX=re.compile(r'^\s*[-*]\s*\[([ xX])\]')
n=sum(1 for ln in open('$FIX/master.md',encoding='utf-8') if CHECKBOX.match(ln))
sys.exit(0 if n>=5 else 1)
"; then
      PASS=$((PASS+1)); green "  PASS stamped lines still match plan-index/archive-guard regexes"
    else
      FAIL=$((FAIL+1)); red "  FAIL plan-index regex miss on stamped lines"
    fi
  else
    FAIL=$((FAIL+1)); red "  FAIL stamped open boxes not greppable"
  fi

  rm -rf "$FIX"
}

check_task_done() {
  echo "=== Task Done / Undone ==="
  local DONE="$PLUGIN_DIR/scripts/task-done.sh"
  local UNDONE="$PLUGIN_DIR/scripts/task-undone.sh"
  local STAMP="$PLUGIN_DIR/scripts/task-stamp.py"
  local PCTL="$PLUGIN_DIR/scripts/planctl.sh"
  # Live-project event log (if present). Concurrent sessions may append to it;
  # hermetic proof is: our fixture plan path must NEVER appear in the live log.
  local LIVE_EVENTS=""
  if [ -f "$PLUGIN_DIR/../../../plans/_dashboard/state.events.jsonl" ]; then
    LIVE_EVENTS="$(cd "$PLUGIN_DIR/../../.." 2>/dev/null && pwd)/plans/_dashboard/state.events.jsonl"
  elif [ -f "${CLAUDE_PROJECT_DIR:-}/plans/_dashboard/state.events.jsonl" ]; then
    LIVE_EVENTS="$CLAUDE_PROJECT_DIR/plans/_dashboard/state.events.jsonl"
  fi

  local FIX
  FIX=$(mktemp -d)
  export META_DEV_STATE_DIR="$FIX/state"
  export META_DEV_ROOT="$FIX"
  mkdir -p "$META_DEV_STATE_DIR"
  # Unique marker so we can prove live log never received our events
  local HERMETIC_MARK="hermetic-task-done-$RANDOM$RANDOM"

  cat > "$FIX/master.md" <<EOF
### Phase 1
- [ ] Alpha $HERMETIC_MARK
- [ ] Beta
- [x] Already
### Acceptance
- [ ] by eye smoke
- [ ] Untagged under acceptance heading
EOF
  python3 "$STAMP" "$FIX/master.md" >/dev/null

  # T1.7 flip only target
  cp "$FIX/master.md" "$FIX/before.md"
  bash "$DONE" "$FIX/master.md" T1.1 >/dev/null
  if grep -qE '\[x\].*`T1\.1`' "$FIX/master.md" \
     && grep -qE '\[ \].*`T1\.2`' "$FIX/master.md"; then
    # other non-target open boxes unchanged besides T1.1
    if python3 -c "
b=open('$FIX/before.md').read().splitlines()
a=open('$FIX/master.md').read().splitlines()
assert len(a)==len(b)
changed=0
for i,(x,y) in enumerate(zip(a,b)):
    if x!=y:
        changed+=1
        assert 'T1.1' in x and '[x]' in x
assert changed==1
"; then
      PASS=$((PASS+1)); green "  PASS task-done flips only targeted box"
    else
      FAIL=$((FAIL+1)); red "  FAIL task-done changed more than target"
    fi
  else
    FAIL=$((FAIL+1)); red "  FAIL task-done did not flip T1.1 only"
  fi

  # T1.8 already [x] no-op exit 0
  cp "$FIX/master.md" "$FIX/before2.md"
  if bash "$DONE" "$FIX/master.md" T1.3 >/dev/null 2>&1; then
    if cmp -s "$FIX/before2.md" "$FIX/master.md"; then
      PASS=$((PASS+1)); green "  PASS already-[x] is no-op exit 0"
    else
      FAIL=$((FAIL+1)); red "  FAIL already-[x] mutated file"
    fi
  else
    FAIL=$((FAIL+1)); red "  FAIL already-[x] non-zero exit"
  fi

  # T1.9 unknown + remaining still processed
  cp "$FIX/master.md" "$FIX/before3.md"
  set +e
  bash "$DONE" "$FIX/master.md" T_BAD T1.2 >/dev/null 2>"$FIX/err9"
  local rc9=$?
  set -e
  if [ "$rc9" -ne 0 ] && grep -qE '\[x\].*`T1\.2`' "$FIX/master.md"; then
    PASS=$((PASS+1)); green "  PASS unknown handle non-zero + remaining handles processed"
  else
    FAIL=$((FAIL+1)); red "  FAIL unknown-handle continue (rc=$rc9)"
  fi

  # T1.10 human-gate both forms
  set +e
  bash "$DONE" "$FIX/master.md" T1.4 >/dev/null 2>"$FIX/err10a"
  local rc10a=$?
  bash "$DONE" "$FIX/master.md" T1.5 >/dev/null 2>"$FIX/err10b"
  local rc10b=$?
  set -e
  if [ "$rc10a" -ne 0 ] && [ "$rc10b" -ne 0 ] \
     && grep -qE '\[ \].*`T1\.4`' "$FIX/master.md" \
     && grep -qE '\[ \].*`T1\.5`' "$FIX/master.md"; then
    bash "$DONE" --human "$FIX/master.md" T1.4 T1.5 >/dev/null
    if grep -qE '\[x\].*`T1\.4`' "$FIX/master.md" \
       && grep -qE '\[x\].*`T1\.5`' "$FIX/master.md"; then
      PASS=$((PASS+1)); green "  PASS human-gate refuse (inline+section) + --human flips"
    else
      FAIL=$((FAIL+1)); red "  FAIL --human did not flip both forms"
    fi
  else
    FAIL=$((FAIL+1)); red "  FAIL human-gate did not refuse (rc a=$rc10a b=$rc10b)"
  fi

  # T1.11 ambiguous bare plan number
  mkdir -p "$FIX/plans/50-FOO" "$FIX/plans/50-BAR"
  echo '- [ ] `T1.1` x' > "$FIX/plans/50-FOO/00-master-plan.md"
  echo '- [ ] `T1.1` y' > "$FIX/plans/50-BAR/00-master-plan.md"
  set +e
  ( cd "$FIX" && bash "$DONE" 50 T1.1 >/dev/null 2>"$FIX/err11" )
  local rc11=$?
  set -e
  if [ "$rc11" -ne 0 ] \
     && grep -qE '\[ \]' "$FIX/plans/50-FOO/00-master-plan.md" \
     && grep -qE '\[ \]' "$FIX/plans/50-BAR/00-master-plan.md" \
     && grep -qiE 'match|candidate' "$FIX/err11"; then
    PASS=$((PASS+1)); green "  PASS ambiguous bare plan fails loud, touches nothing"
  else
    FAIL=$((FAIL+1)); red "  FAIL ambiguous bare plan (rc=$rc11)"; cat "$FIX/err11" || true
  fi

  # T1.12 concurrent flip — planctl uses mutation_lock (flock on state-dir sidecar,
  # not a plan-adjacent .task-lock). Assert both flips land; NO .task-lock sidecar.
  cat > "$FIX/race.md" <<'EOF'
### Phase 1
- [ ] `T1.1` A
- [ ] `T1.2` B
EOF
  local race_ok=1
  local i
  for i in $(seq 1 20); do
    cat > "$FIX/race.md" <<'EOF'
### Phase 1
- [ ] `T1.1` A
- [ ] `T1.2` B
EOF
    bash "$DONE" "$FIX/race.md" T1.1 >/dev/null 2>&1 &
    bash "$DONE" "$FIX/race.md" T1.2 >/dev/null 2>&1 &
    wait
    if ! grep -qE '\[x\].*`T1\.1`' "$FIX/race.md" \
       || ! grep -qE '\[x\].*`T1\.2`' "$FIX/race.md"; then
      race_ok=0
      break
    fi
  done
  # planctl uses state-dir locks (off-9p), NOT plan-adjacent .task-lock sidecars.
  if [ "$race_ok" -eq 1 ] && [ ! -f "$FIX/race.md.task-lock" ]; then
    PASS=$((PASS+1)); green "  PASS concurrent flip both land (planctl lock, 20× race, no .task-lock)"
  else
    FAIL=$((FAIL+1)); red "  FAIL concurrent flip lost update or .task-lock reappeared"
  fi

  # T1.13 check event in planctl events.jsonl (NOT legacy state.events.jsonl)
  if grep -q '"event":"check"' "$META_DEV_STATE_DIR/events.jsonl" 2>/dev/null \
     && grep -q '"T1.1"' "$META_DEV_STATE_DIR/events.jsonl"; then
    PASS=$((PASS+1)); green "  PASS check event in planctl events.jsonl under META_DEV_STATE_DIR"
  else
    FAIL=$((FAIL+1)); red "  FAIL check event missing in planctl events.jsonl"
  fi
  # refuse → no extra event for unknown
  local ev_before
  ev_before=$(wc -l < "$META_DEV_STATE_DIR/events.jsonl" || echo 0)
  set +e
  bash "$DONE" "$FIX/master.md" T_NOPE >/dev/null 2>&1
  set -e
  local ev_after
  ev_after=$(wc -l < "$META_DEV_STATE_DIR/events.jsonl" || echo 0)
  if [ "$ev_after" -eq "$ev_before" ]; then
    PASS=$((PASS+1)); green "  PASS no event when flip refused/failed"
  else
    FAIL=$((FAIL+1)); red "  FAIL event appended on failed flip"
  fi

  # undone round-trip — planctl writes "uncheck" event to events.jsonl
  bash "$UNDONE" "$FIX/master.md" T1.1 >/dev/null 2>&1 || true
  if grep -qE '\[ \].*`T1\.1`' "$FIX/master.md" \
     && grep -q '"event":"uncheck"' "$META_DEV_STATE_DIR/events.jsonl"; then
    PASS=$((PASS+1)); green "  PASS task-undone reopens + uncheck event in planctl events.jsonl"
  else
    FAIL=$((FAIL+1)); red "  FAIL task-undone"
  fi

  # T1.15 hermetic: fixture events landed in planctl events.jsonl; live legacy log
  # must not contain our marker path. (task_done events no longer land in legacy log
  # — M3a writer swap; planctl writes to its own off-9p events.jsonl.)
  if [ -n "$LIVE_EVENTS" ] && [ -f "$LIVE_EVENTS" ]; then
    if grep -qF "$FIX/master.md" "$LIVE_EVENTS" 2>/dev/null \
       || grep -qF "$HERMETIC_MARK" "$LIVE_EVENTS" 2>/dev/null; then
      FAIL=$((FAIL+1)); red "  FAIL live state.events.jsonl received hermetic fixture events"
    else
      PASS=$((PASS+1)); green "  PASS live state.events.jsonl free of fixture events (planctl events.jsonl hermetic)"
    fi
  else
    PASS=$((PASS+1)); green "  PASS (skip live-events check — no live log in this tree)"
  fi

  # planctl events.jsonl has our check/uncheck events (not legacy state.events.jsonl)
  if [ -f "$META_DEV_STATE_DIR/events.jsonl" ] \
     && grep -q '"event":"check"' "$META_DEV_STATE_DIR/events.jsonl"; then
    PASS=$((PASS+1)); green "  PASS planctl events.jsonl present + contains check events"
  else
    FAIL=$((FAIL+1)); red "  FAIL planctl events.jsonl missing or no check events"
  fi

  unset META_DEV_STATE_DIR
  unset META_DEV_ROOT
  rm -rf "$FIX"
}

check_docs_gate() {
  echo "=== Docs / Context Gate ==="
  # T3.4 — plan-validate warns on missing context/docs at stage>=3; never blocks.
  # Hook only validates paths under plans/, so fixture lives there.
  local VAL="$PLUGIN_DIR/hooks/scripts/plan-validate.sh"
  local FIX
  FIX=$(mktemp -d)
  mkdir -p "$FIX/plans/meta"
  cat > "$FIX/plans/meta/plan.md" <<'EOF'
---
status: active
stage: 3
repo: meta
---
# X
EOF
  local WARN
  WARN=$(printf '%s' "{\"tool_input\":{\"file_path\":\"$FIX/plans/meta/plan.md\"}}" | bash "$VAL" 2>&1 || true)
  if echo "$WARN" | grep -qiE 'context|docs'; then
    PASS=$((PASS+1)); green "  PASS plan-validate warns on missing context/docs (stage>=3)"
  else
    FAIL=$((FAIL+1)); red "  FAIL plan-validate missing context/docs warning: $WARN"
  fi

  cat > "$FIX/plans/meta/plan-ok.md" <<'EOF'
---
status: active
stage: 3
repo: meta
context: none
docs: none
---
# X
EOF
  WARN=$(printf '%s' "{\"tool_input\":{\"file_path\":\"$FIX/plans/meta/plan-ok.md\"}}" | bash "$VAL" 2>&1 || true)
  if [ -z "$WARN" ] || ! echo "$WARN" | grep -qiE 'context|docs'; then
    PASS=$((PASS+1)); green "  PASS plan-validate silent when context/docs: none"
  else
    FAIL=$((FAIL+1)); red "  FAIL plan-validate warned on explicit none: $WARN"
  fi

  rm -rf "$FIX"
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
  --check-runbook-gate) check_runbook_gate ;;
  --check-task-stamp) check_task_stamp ;;
  --check-task-done) check_task_done ;;
  --check-docs-gate) check_docs_gate ;;
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
    check_runbook_gate
    check_task_stamp
    check_task_done
    check_docs_gate
    ;;
esac

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -eq 0 ]; then green "ALL CHECKS PASSED"; else red "SOME CHECKS FAILED"; fi
exit "$FAIL"
