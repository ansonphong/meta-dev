#!/usr/bin/env bash
# Legacy Claude compatibility guards. These keep the full Claude command and
# skill surface healthy; native Codex package coverage lives in
# test-codex-package-surface.sh.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0; FAIL=0
ok()   { echo -e "\033[32m  PASS: $1\033[0m"; PASS=$((PASS+1)); }
bad()  { echo -e "\033[31m  FAIL: $1\033[0m"; FAIL=$((FAIL+1)); }

echo "=== Claude legacy compatibility: skill + command frontmatter ==="
VALIDATOR_OK=0
if PARITY_OUT="$(python3 - "$PLUGIN_ROOT" <<'PY'
import glob, os, sys, yaml
root = sys.argv[1]
bad = []
files = sorted(glob.glob(os.path.join(root, "workflow-skills", "*", "SKILL.md")))
files += sorted(glob.glob(os.path.join(root, "commands", "*.md")))
for f in files:
    raw = open(f, encoding="utf-8").read()
    try:
        d = yaml.safe_load(raw.split("---")[1])
        assert isinstance(d, dict) and d.get("name") and d.get("description")
    except Exception as e:
        bad.append(os.path.relpath(f, root))
print(len(files))
print("|".join(bad))
PY
)"; then
  FRONTMATTER_COUNT="$(echo "$PARITY_OUT" | sed -n 1p)"
  FRONTMATTER_BAD="$(echo "$PARITY_OUT" | sed -n 2p)"
  if [[ "$FRONTMATTER_COUNT" =~ ^[0-9]+$ ]]; then
    VALIDATOR_OK=1
  else
    bad "strict-YAML validator returned malformed output"
  fi
else
  validator_rc=$?
  bad "strict-YAML validator failed to execute (python3/PyYAML, exit $validator_rc)"
fi

if [ "$VALIDATOR_OK" -eq 1 ]; then
  if [ "$FRONTMATTER_COUNT" -gt 0 ] && [ -z "$FRONTMATTER_BAD" ]; then
    ok "all $FRONTMATTER_COUNT legacy skill/command frontmatters parse under strict YAML"
  else
    bad "invalid skill/command frontmatter — INVISIBLE in Codex: $FRONTMATTER_BAD"
  fi

fi

echo
echo "=== Claude legacy compatibility: plugin manifest ==="

MANIFEST="${CODEX_PARITY_MANIFEST:-$PLUGIN_ROOT/.claude-plugin/plugin.json}"
if MANIFEST_DETAIL="$(python3 - "$MANIFEST" "$PLUGIN_ROOT" <<'PY'
import json
from pathlib import Path
import sys

manifest_path = Path(sys.argv[1])
plugin_root = Path(sys.argv[2]).resolve()
expected_value = "./workflow-skills/"

try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual_value = manifest.get("skills")
    if actual_value != expected_value:
        raise ValueError(
            f"skills must equal {expected_value!r}, found {actual_value!r}"
        )

    skills_dir = (plugin_root / actual_value).resolve(strict=True)
    expected_dir = (plugin_root / "workflow-skills").resolve(strict=True)
    if skills_dir != expected_dir or not skills_dir.is_dir():
        raise ValueError(f"skills resolves outside the real skills directory: {skills_dir}")

except (OSError, ValueError, json.JSONDecodeError) as exc:
    print(exc)
    sys.exit(1)
PY
)"
then
  ok "manifest skills path is exact and resolves to shared Claude workflows"
else
  bad "manifest skills wiring invalid — EVERY shared Claude skill is invisible: $MANIFEST_DETAIL"
fi

echo
echo "=== Codex command compatibility: exact skills plus alias fallback ==="

ROUTER="$PLUGIN_ROOT/skills/command-router/SKILL.md"
if [ -f "$ROUTER" ]; then
  ok "command-router skill present"
else
  bad "command-router skill MISSING — Codex has no fallback for bare aliases"
fi

if python3 "$PLUGIN_ROOT/scripts/sync-codex-command-skills.py" >/dev/null; then
  ok "canonical command skills are complete and synchronized"
else
  bad "canonical command skills are missing or drifted"
fi

# The router tells Codex commands/ is two levels up from the SKILL.md.
if [ -d "$PLUGIN_ROOT/skills/command-router/../../commands" ]; then
  ok "router path claim holds (../../commands resolves)"
else
  bad "router path claim BROKEN — ../../commands does not resolve"
fi

# Every meta-<name> must have a bare <name> twin whose body is the literal
# one-line redirect promised by the command-pairing invariant.
TWIN_VALIDATOR_OK=0
if TWIN_OUT="$(python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import sys

commands = Path(sys.argv[1]) / "commands"
missing = []
bad_bodies = []
meta_commands = sorted(commands.glob("meta-*.md"))

# Claude Code ships built-in /compact, /config, /init and /goal. A bare twin
# using one of those names would shadow the built-in rather than redirect to our
# command, so these are deliberately meta-only. The pairing invariant is about
# reachability, and `/meta-compact` is already reachable — inventing `/compact`
# would break the CLI to satisfy a naming rule. `/goal` is the sharpest case:
# `/meta-goal` exists precisely to FEED the built-in `/goal`, so shadowing it
# would break the very command this one is built to serve.
BUILTIN_COLLISIONS = {"compact", "config", "init", "goal"}

for implementation in meta_commands:
    short = implementation.stem.removeprefix("meta-")
    if short in BUILTIN_COLLISIONS:
        continue
    twin = commands / f"{short}.md"
    if not twin.is_file():
        missing.append(short)
        continue

    raw = twin.read_bytes()
    if not raw.startswith(b"---\n"):
        bad_bodies.append(short)
        continue
    _, separator, body = raw[4:].partition(b"\n---\n")
    expected = f"Execute /{implementation.stem} $ARGUMENTS\n".encode()
    if not separator or body != expected:
        bad_bodies.append(short)

print(len(meta_commands))
print("|".join(missing))
print("|".join(bad_bodies))
PY
)"; then
  TWIN_COUNT="$(echo "$TWIN_OUT" | sed -n 1p)"
  MISSING_TWIN="$(echo "$TWIN_OUT" | sed -n 2p)"
  BAD_TWIN_BODY="$(echo "$TWIN_OUT" | sed -n 3p)"
  if [[ "$TWIN_COUNT" =~ ^[1-9][0-9]*$ ]]; then
    TWIN_VALIDATOR_OK=1
  else
    bad "command-twin validator returned malformed output"
  fi
else
  twin_validator_rc=$?
  bad "command-twin validator failed to execute (python3, exit $twin_validator_rc)"
fi

if [ "$TWIN_VALIDATOR_OK" -eq 1 ]; then
  if [ -z "$MISSING_TWIN" ]; then
    ok "every meta-<name> has a bare <name> twin ($TWIN_COUNT pairs)"
  else
    bad "meta-<name> without bare twin: $MISSING_TWIN"
  fi

  if [ -z "$BAD_TWIN_BODY" ]; then
    ok "all bare twin bodies are exact one-line redirects"
  else
    bad "bare twins with non-redirect bodies: $BAD_TWIN_BODY"
  fi
fi

echo
echo "=== Shared execution contract: worker commit-on-red ==="

if COMMIT_CONTRACT_DETAIL="$(python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = {
    "references/execute-dispatch.md": [
        "3. **COMMIT-ON-RED:**",
        "4. **COMMIT-ON-RED:**",
        "blocks DONE/push, not",
        "After `FOCUSED_PASS` or `BASELINE_RED`",
    ],
    "references/execute-charter.md": [
        "**COMMIT-ON-RED INVARIANT.**",
        "A later review does not rewrite task",
    ],
    "commands/meta-execute.md": [
        "including on red verification",
        "push only after both are green",
    ],
    "commands/codex-execute.md": ["red blocks DONE and remote push, not persistence"],
    "workflow-skills/agentic-exec-loop/references/loop-protocol.md": [
        "creates a local commit before",
    ],
    "workflow-skills/repair-loop/SKILL.md": ["before every return after editing"],
    "scripts/lib/framework-preamble.py": ["4. COMMIT-ON-RED:"],
    "scripts/codex-headless-exec": [
        "6. COMMIT-ON-RED:",
        "NEVER `git push`, `git pull`, `git fetch`, `git rebase`, or `git merge`",
    ],
    "scripts/claude-headless-exec": ["HARD WORKER PERSISTENCE RULE"],
}
forbidden = {
    "references/execute-dispatch.md": [
        "Green = done, red = STOP.",
        "fix inline, commit, push",
    ],
    "commands/meta-execute.md": ["fix inline, commit, push"],
    "commands/codex-execute.md": ["Codex changes are never automatically committed."],
    "scripts/claude-headless-exec": ["workers are COMMIT-FREE"],
}

issues = []
texts = {}
for rel, markers in required.items():
    path = root / rel
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(f"{rel}: unreadable: {exc}")
        continue
    texts[rel] = text
    for marker in markers:
        if marker not in text:
            issues.append(f"{rel}: missing {marker!r}")

for rel, markers in forbidden.items():
    text = texts.get(rel)
    if text is None:
        continue
    for marker in markers:
        if marker in text:
            issues.append(f"{rel}: stale contradiction {marker!r}")

dispatch = texts.get("references/execute-dispatch.md", "")
commit_step = dispatch.find("4. **COMMIT-ON-RED:**")
stub_step = dispatch.find("5. Run stub grep on the committed diff")
verify_step = dispatch.find("6. If `<VERIFY_CLASS>` is `focused` or `scoped_check`")
if (
    commit_step < 0
    or stub_step < 0
    or verify_step < 0
    or not (commit_step < stub_step < verify_step)
):
    issues.append(
        "execute-dispatch.md: local commit must precede stub and Verify gates"
    )

audit_gate = dispatch.find("FIRST — audit the worker's existing local commit")
conductor_verify = dispatch.find("Then verify the existing commit")
accept_gate = dispatch.find("After `FOCUSED_PASS` or `BASELINE_RED`")
if (
    audit_gate < 0
    or conductor_verify < 0
    or accept_gate < 0
    or not (audit_gate < conductor_verify < accept_gate)
):
    issues.append(
        "execute-dispatch.md: conductor must audit+verify before checkbox/push"
    )

if issues:
    print(" | ".join(issues))
    raise SystemExit(1)
PY
)"; then
  ok "all implementation-worker paths commit scoped edits before red/BLOCKED return"
else
  bad "worker commit-on-red contract drifted: $COMMIT_CONTRACT_DETAIL"
fi

echo
echo "=== Shared execution contract: focused optimistic momentum ==="

if MOMENTUM_DETAIL="$(python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = {
    "commands/meta-execute.md": [
        "Optimistic momentum is the default control flow",
        "BROAD_VERIFY_OMITTED",
        "MUST NOT rerun a passing verifier",
    ],
    "commands/codex-execute.md": [
        "FOCUSED_PASS",
        "TASK_RED",
        "BASELINE_RED",
        "INFRA_RED",
        "BROAD_VERIFY_OMITTED",
        "not at phase end",
    ],
    "scripts/codex-headless-exec": [
        "FOCUSED VERIFICATION ONLY",
        "OPTIMISTIC MOMENTUM",
        "BASELINE_RED",
        "BROAD_VERIFY_OMITTED",
        "not at phase end",
    ],
}
forbidden = {
    "commands/meta-execute.md": ["full acceptance suite once", "Gate: all green before proceeding"],
    "commands/codex-execute.md": ["full suite in an inner cycle"],
    "scripts/codex-headless-exec": ["those run ONCE at phase end"],
}
issues = []
texts = {}
for rel, markers in required.items():
    text = (root / rel).read_text(encoding="utf-8")
    texts[rel] = text
    for marker in markers:
        if marker not in text:
            issues.append(f"{rel}: missing {marker!r}")
for rel, markers in forbidden.items():
    text = texts.get(rel) or (root / rel).read_text(encoding="utf-8")
    for marker in markers:
        if marker in text:
            issues.append(f"{rel}: stale contradiction {marker!r}")
if issues:
    print(" | ".join(issues))
    raise SystemExit(1)
PY
)"; then
  ok "native + headless Codex enforce focused tests, one green, and BASELINE_RED momentum"
else
  bad "Codex focused-momentum contract drifted: $MOMENTUM_DETAIL"
fi

echo
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
