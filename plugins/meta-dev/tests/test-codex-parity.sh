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
echo "=== Codex Parity: command-router resolution ==="

ROUTER="$PLUGIN_ROOT/skills/command-router/SKILL.md"
if [ -f "$ROUTER" ]; then
  ok "command-router skill present"
else
  bad "command-router skill MISSING — Codex has no path to the 67 commands"
fi

# The router tells Codex commands/ is two levels up from the SKILL.md.
if [ -d "$PLUGIN_ROOT/skills/command-router/../../commands" ]; then
  ok "router path claim holds (../../commands resolves)"
else
  bad "router path claim BROKEN — ../../commands does not resolve"
fi

# Every meta-<name> must have a bare <name> twin, or the router's step-2
# fallback advertises a name that does not exist.
MISSING_TWIN=""
for f in "$PLUGIN_ROOT"/commands/meta-*.md; do
  base="$(basename "$f" .md)"; short="${base#meta-}"
  # meta-dev and meta-init are documented exceptions with no bare twin rule
  case "$short" in dev|init) continue ;; esac
  [ -f "$PLUGIN_ROOT/commands/$short.md" ] || MISSING_TWIN="$MISSING_TWIN $short"
done
if [ -z "$MISSING_TWIN" ]; then
  ok "every meta-<name> has a bare <name> twin"
else
  bad "meta-<name> without bare twin:$MISSING_TWIN"
fi

echo
echo "=== Doctrine: retired claims must not return ==="

# These claims were retired 2026-07-19: bare /meta-execute is NATIVE to the host
# harness, and Codex is a first-class executor. If a phrase reappears, some doc
# has drifted back and Codex workers will obey the wrong rule.
RETIRED='deepseek[- ]first|deepseek.{0,24}(\(cheapest, default\)|\(default\)|\bdefault[/ -](mechanical|execution|executor|worker|backend|tier)\b|\bdefault via\b|\bis (the )?default\b)|\bdefault[[:space:]]+deepseek\b|\bdefault[[:space:]]*(→|:|=)[[:space:]]*deepseek\b|codex is off (the|this)|code review only|review-only lens'
HITS="$(grep -rniE "$RETIRED" \
  "$PLUGIN_ROOT/commands" "$PLUGIN_ROOT/skills" "$PLUGIN_ROOT/references" \
  2>/dev/null | grep -viE '^\S+:[0-9]+: *#' || true)"

if [ -z "$HITS" ]; then
  ok "no retired default/review-only claims in commands, skills, references"
else
  bad "retired doctrine claims resurfaced:"
  echo "$HITS" | sed 's/^/        /'
fi

echo
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
