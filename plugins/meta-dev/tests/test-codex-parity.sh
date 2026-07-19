#!/usr/bin/env bash
# Codex-parity guards. Claude Code is lenient about frontmatter; Codex is not.
# A skill or command with invalid YAML is SILENTLY INVISIBLE in Codex.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0; FAIL=0
ok()   { echo -e "\033[32m  PASS: $1\033[0m"; PASS=$((PASS+1)); }
bad()  { echo -e "\033[31m  FAIL: $1\033[0m"; FAIL=$((FAIL+1)); }

echo "=== Codex Parity: skill + command frontmatter ==="
python3 - "$PLUGIN_ROOT" <<'PY'
import glob, os, sys, yaml
root = sys.argv[1]
bad = []
files = (sorted(glob.glob(os.path.join(root, "skills", "*", "SKILL.md")))
         + sorted(glob.glob(os.path.join(root, "commands", "*.md"))))
for f in files:
    raw = open(f, encoding="utf-8").read()
    try:
        parts = raw.split("---")
        d = yaml.safe_load(parts[1])
        assert isinstance(d, dict), "frontmatter is not a mapping"
        assert d.get("name"), "missing name"
        assert d.get("description"), "missing description"
    except Exception as e:
        bad.append((os.path.relpath(f, root), repr(e)[:120]))
print(f"__COUNT__{len(files)}")
for f, e in bad:
    print(f"__BAD__{f}\t{e}")
PY

PARITY_OUT="$(python3 - "$PLUGIN_ROOT" <<'PY'
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
)"
FRONTMATTER_COUNT="$(echo "$PARITY_OUT" | sed -n 1p)"
FRONTMATTER_BAD="$(echo "$PARITY_OUT" | sed -n 2p)"
SKILL_COUNT="$(echo "$PARITY_OUT" | sed -n 3p)"

if [ -z "$FRONTMATTER_BAD" ]; then
  ok "all $FRONTMATTER_COUNT skill/command frontmatters parse under strict YAML (Codex-visible)"
else
  bad "invalid skill/command frontmatter — INVISIBLE in Codex: $FRONTMATTER_BAD"
fi

if [ "$SKILL_COUNT" -lt 17 ]; then
  bad "expected >=17 skills, found $SKILL_COUNT (command-router missing?)"
else
  ok "skill count $SKILL_COUNT >= 17"
fi

echo
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
