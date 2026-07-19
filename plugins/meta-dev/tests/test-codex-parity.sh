#!/usr/bin/env bash
# Codex-parity guards. Claude Code is lenient about frontmatter; Codex is not.
# A skill or command with invalid YAML is SILENTLY INVISIBLE in Codex.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0; FAIL=0
ok()   { echo -e "\033[32m  PASS: $1\033[0m"; PASS=$((PASS+1)); }
bad()  { echo -e "\033[31m  FAIL: $1\033[0m"; FAIL=$((FAIL+1)); }

echo "=== Codex Parity: skill + command frontmatter ==="
VALIDATOR_OK=0
if PARITY_OUT="$(python3 - "$PLUGIN_ROOT" <<'PY'
import glob, os, sys, yaml
root = sys.argv[1]
bad = []
skill_files = sorted(glob.glob(os.path.join(root, "skills", "*", "SKILL.md")))
files = skill_files + sorted(glob.glob(os.path.join(root, "commands", "*.md")))
for f in files:
    raw = open(f, encoding="utf-8").read()
    try:
        d = yaml.safe_load(raw.split("---")[1])
        assert isinstance(d, dict) and d.get("name") and d.get("description")
    except Exception as e:
        bad.append(os.path.relpath(f, root))
print(len(files))
print("|".join(bad))
print(len(skill_files))
PY
)"; then
  FRONTMATTER_COUNT="$(echo "$PARITY_OUT" | sed -n 1p)"
  FRONTMATTER_BAD="$(echo "$PARITY_OUT" | sed -n 2p)"
  SKILL_COUNT="$(echo "$PARITY_OUT" | sed -n 3p)"
  if [[ "$FRONTMATTER_COUNT" =~ ^[0-9]+$ && "$SKILL_COUNT" =~ ^[0-9]+$ ]]; then
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
    ok "all $FRONTMATTER_COUNT skill/command frontmatters parse under strict YAML (Codex-visible)"
  else
    bad "invalid skill/command frontmatter — INVISIBLE in Codex: $FRONTMATTER_BAD"
  fi

  if [ "$SKILL_COUNT" -lt 17 ]; then
    bad "expected >=17 skills, found $SKILL_COUNT (command-router missing?)"
  else
    ok "skill count $SKILL_COUNT >= 17"
  fi
fi

echo
echo "=== Codex Parity: command-router resolution ==="

ROUTER="$PLUGIN_ROOT/skills/command-router/SKILL.md"
if [ -f "$ROUTER" ]; then
  ok "command-router skill present"
else
  bad "command-router skill MISSING — Codex has no path to the command catalog"
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

for implementation in meta_commands:
    short = implementation.stem.removeprefix("meta-")
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
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
