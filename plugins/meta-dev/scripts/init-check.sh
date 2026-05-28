#!/usr/bin/env bash
set -uo pipefail
# init-check.sh — Deterministic git/lock/config health probe for one repo
# Usage: init-check.sh <repo-dir>
# Reads WSL git-corruption mitigations from the config cascade and applies them.
# Exit codes: 0 = OK, 1 = WARN, 2 = BLOCKED
#
# The ONLY auto-fixes this script performs are:
#   1. Removing a stale .git/index.lock (safe — removes the lock, never the index)
#   2. Applying the four git_corruption_mitigations from config (always safe)
# It never starts services, never installs deps, never commits, never resets.

REPO_DIR="${1:-.}"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"
STATUS=0   # 0=OK, 1=WARN, 2=BLOCKED

green()  { echo "OK    | $1"; }
yellow() { echo "WARN  | $1"; [ "$STATUS" -lt 1 ] && STATUS=1; }
red()    { echo "BLOCK | $1"; STATUS=2; }

if [ ! -d "$REPO_DIR" ]; then
  red "repo dir not found: $REPO_DIR"
  exit 2
fi

cd "$REPO_DIR" || { red "cannot cd into $REPO_DIR"; exit 2; }

if [ ! -d .git ]; then
  red "not a git repo: $REPO_DIR"
  exit 2
fi

# --- 1. Stale index-lock detection + the one safe auto-fix --------------------
# Load-bearing on WSL2/9p where crashed processes leave a stale lock that blocks
# every subsequent git operation. Removing the lock is safe; it is NOT the index.
if [ -f .git/index.lock ]; then
  rm -f .git/index.lock && green "removed stale .git/index.lock" \
    || red "stale .git/index.lock present and could not be removed"
fi

# --- 2. Git health probe (corruption detection) ------------------------------
GIT_STATUS_OUT="$(git status --porcelain 2>&1)"
GIT_STATUS_RC=$?
if [ "$GIT_STATUS_RC" -ne 0 ]; then
  # Corruption signatures: bad object, unable to read/write index, short index.
  red "git status failed (possible index corruption): $(echo "$GIT_STATUS_OUT" | head -1)"
  echo "      FIX FROM A NON-WSL (Windows) TERMINAL — do not rm .git/index or git reset from here."
else
  DIRTY_COUNT=$(printf '%s\n' "$GIT_STATUS_OUT" | grep -c . || true)
  if [ "$DIRTY_COUNT" -gt 0 ]; then
    yellow "$DIRTY_COUNT uncommitted change(s) — commit before a long run (warning, not a blocker)"
    git diff --stat HEAD 2>/dev/null | tail -1 | sed 's/^/      /' || true
  else
    green "clean working tree"
  fi
fi

# --- 3. WSL git-config verify + auto-apply -----------------------------------
# The four keys come from config (meta_dev.filesystem.git_corruption_mitigations),
# NOT hardcoded here. Map config key -> git config key.
declare -A CFG_KEYS=(
  [core_filemode]=core.filemode
  [core_preloadindex]=core.preloadindex
  [core_untrackedcache]=core.untrackedcache
  [core_fsmonitor]=core.fsmonitor
)

read_cfg() {
  # config-get returns the merged value; fall back to "false" (safe default).
  # Normalize to git's lowercase boolean spelling (Python JSON prints True/False).
  bash "$PLUGIN_ROOT/scripts/config-get.sh" "meta_dev.filesystem.git_corruption_mitigations.$1" 2>/dev/null \
    | tr '[:upper:]' '[:lower:]' \
    || echo "false"
}

applied=0
for ckey in "${!CFG_KEYS[@]}"; do
  want="$(read_cfg "$ckey")"
  [ -z "$want" ] && want="false"
  gkey="${CFG_KEYS[$ckey]}"
  have="$(git config "$gkey" 2>/dev/null || echo "")"
  if [ "$have" != "$want" ]; then
    git config "$gkey" "$want" && applied=$((applied+1))
  fi
done
if [ "$applied" -gt 0 ]; then
  green "applied $applied WSL git-config mitigation(s)"
else
  green "WSL git-config mitigations already in place"
fi

# --- 4. Summary line ----------------------------------------------------------
case "$STATUS" in
  0) echo "=== init-check[$REPO_DIR]: OK ===" ;;
  1) echo "=== init-check[$REPO_DIR]: WARN ===" ;;
  2) echo "=== init-check[$REPO_DIR]: BLOCKED ===" ;;
esac
exit "$STATUS"
