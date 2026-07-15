#!/usr/bin/env bash
# on-run-complete.sh — Stop hook. Deterministically enforces DONE at end-of-run.
#
# PRIME DIRECTIVE: after any execution run, the plan MUST read 100% DONE on the
# dashboard automatically (no human step), or the run MUST FAIL LOUDLY. Ending
# silently in a stale in-between state — stage 5, boxes maybe-open, never
# advanced to 6 — must be structurally impossible.
#
# WHY THIS EXISTS: the conductor's end-of-run steps (checkbox flip, stage→6
# bump, dashboard render) are MODEL DISCIPLINE the run can silently skip. There
# was a UserPromptSubmit hook that hardened stage ENTRY (on-stage-prompt.sh →
# stage-emit execute in_progress) but ZERO Stop-hook coverage, so completion was
# unguarded. This hook makes completion a property of STATE, not memory.
#
# DONE ≡ execution complete AND code review complete.
#   - execution complete = zero open EXECUTION checkboxes across the plan dir
#     (HUMAN-VERIFY gates excluded — those are the user's smoke test, never
#     auto-checked; see HUMAN_TAG_RE / HUMAN_SECTION_RE below).
#   - code review complete = a review_verdict(pass) event on record for the plan
#     (persisted by the conductor after the post-run review resolves).
# DONE is NOT gated on: the user's smoke test (they do it themselves, after —
# never prompt/wait), archiving (user-requested, later), or housekeeping.
#
# FIRE MODEL (status-based hybrid — no separate run-marker file):
#   The START is already deterministic: on-stage-prompt.sh writes
#   stage_transition(execute, in_progress) the instant the execute command is
#   submitted. This hook keys off that same state trail. For EACH plan found at
#   stage 5 (execute) under plans/:
#     stage5 + clean exec boxes + review PASS  → STAMP DONE (stage 6) + render.  [happy]
#     stage5 + status:completed + open boxes   → FAIL LOUD (claimed done, lied). [the bug]
#     stage5 + clean boxes + NO review pass    → don't stamp; flag review-missing.
#     stage5 + open boxes + in_progress/blocked→ no-op (run alive / intentionally halted).
#     no stage-5 plan                          → no-op (ordinary chat stops never trigger).
#
# This hook NEVER blocks the stop (no decision:block — that risks loops) and
# NEVER auto-archives. Fail-loud = loud stderr banner + durable inbox item +
# state event. Exit 0 always: a dashboard gate must never disrupt the user.
#
# TWO PASSES on every stop (see bottom of file):
#   (a) DONE-stamp — the stage-5 decision matrix above (stamp / fail-loud / wait).
#   (b) RUNBOOK RECONCILE — re-render EVERY campaign runbook UNCONDITIONALLY, so
#       the dashboard tracks member frontmatter no matter HOW a member reached
#       its stage (hook stamp, conductor hand-flip at closeout, direct
#       stage-emit, manual edit). Pass (b) exists because welding the re-render
#       into pass (a)'s stamp branch froze any runbook whose member advanced by
#       a non-hook path — the plan leaves stage 5, so pass (a) never revisits it.
#
# CWD-INDEPENDENT: resolves the project root from CLAUDE_PROJECT_DIR (fallback:
# walk up) and cd's there, so a leaked child-repo cwd can't misfire the gate.
#
# Reuses existing primitives — does NOT rebuild logic:
#   box-clean check   → the grep already in archive-guard.sh:54 (here per-line,
#                       human-verify-aware, across the plan dir)
#   stage advance     → scripts/stage-emit.sh <plan> review completed  (= stage 6)
#   dashboard render  → scripts/runbook-render.py <runbook>  (members only;
#                       standalone plans have no persistent dashboard file —
#                       /meta-dashboard computes live from YAML, so the
#                       stage-emit stamp IS the render for them)
set -uo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -z "$PLUGIN_ROOT" ] && PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Never run inside another stop-hook pass (defensive; we never block). -----
PAYLOAD="$(cat 2>/dev/null || true)"
if printf '%s' "$PAYLOAD" | python3 -c 'import json,sys; sys.exit(0 if json.loads(sys.stdin.read() or "{}").get("stop_hook_active") else 1)' 2>/dev/null; then
  exit 0
fi

# --- Resolve the project root cwd-INDEPENDENTLY, then anchor there. -----------
# Prefer the harness-provided project dir: a leaked child-repo cwd (the #1
# recurring bug — an earlier `cd 360-HEXTILE-APP` persists across Bash calls)
# must NEVER point the gate at a forked child plans/ tree, or at nothing.
# CLAUDE_PROJECT_DIR is the reliable anchor Claude Code sets for hooks; only
# walk up from cwd if it is unset. Once resolved, `cd` there so every relative
# `plans/…` path below (and every child script that inherits this cwd) is right.
PROJECT_ROOT=""
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -d "${CLAUDE_PROJECT_DIR}/plans" ]; then
  PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
else
  _d="$(pwd)"
  while [ -n "$_d" ] && [ "$_d" != "/" ]; do
    if [ -d "$_d/plans" ]; then PROJECT_ROOT="$_d"; break; fi
    _d="$(dirname "$_d")"
  done
fi
[ -z "$PROJECT_ROOT" ] && exit 0
cd "$PROJECT_ROOT" || exit 0
PLANS_DIR="plans"
[ -d "$PLANS_DIR" ] || exit 0

emit_event() {
  # emit_event <event> <plan-rel> <result> <iso-time>
  local ev="$1" plan="$2" result="$3" t="$4"
  local json
  json="$(python3 -c 'import json,sys; print(json.dumps({"event":sys.argv[1],"plan":sys.argv[2],"result":sys.argv[3],"time":sys.argv[4]}))' "$ev" "$plan" "$result" "$t" 2>/dev/null)" || return 0
  [ -n "$json" ] && bash "$PLUGIN_ROOT/scripts/state-append.sh" "$json" >/dev/null 2>&1 || true
}

inbox_fail() {
  # inbox_fail <plan-rel> <severity> <body> <iso-time>
  local plan="$1" sev="$2" body="$3" t="$4"
  bash "$PLUGIN_ROOT/scripts/inbox-add.sh" \
    --source done-gate \
    --severity "$sev" \
    --title "DONE-gate: $plan not done" \
    --body "$body" \
    --tag done-gate \
    --tag execution \
    --ref-file "$plan" >/dev/null 2>&1 || true
}

run_gate() {
  # run_gate <plan-master-path> <scope-dir-or-file> <status> <plan-rel>
  local PLAN="$1" SCOPE="$2" STATUS="$3" REL="$4"
  local NOW; NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo '')"

  # --- Analyze checkboxes across the plan scope (human-verify-aware). --------
  # Prints: "<open_exec>\t<total_boxes>\t<human_open>" then one "file:line: text"
  # line per open EXECUTION box (for the fail-loud listing).
  local ANALYSIS
  ANALYSIS="$(python3 - "$SCOPE" <<'PYEOF'
import os, sys, re
scope = sys.argv[1]
files = []
if os.path.isdir(scope):
    for fn in sorted(os.listdir(scope)):
        if fn.endswith('.md'):
            files.append(os.path.join(scope, fn))
else:
    files = [scope]
# A box is HUMAN-VERIFY (the user's smoke test — never gates DONE, never
# auto-checked) if its own line carries a human tag OR it sits under a heading
# that marks an acceptance/human-verify section.
tag_re   = re.compile(r'(by\s+eye|by\s+hand|gpu|manual)', re.I)
sec_re   = re.compile(r'(acceptance|by\s+eye|by\s+hand|gpu|manual|human[-\s]*verify)', re.I)
# Match ANY checkbox ([ ] unchecked, [x]/[X] checked); capture the mark + text.
anybox_re = re.compile(r'^[ \t]*[-*][ \t]+\[([ xX])\][ \t]*(.*)$')
open_exec = total = human_open = 0
open_lines = []
for fp in files:
    try:
        with open(fp, encoding='utf-8') as f:
            lines = f.read().splitlines()
    except Exception:
        continue
    cur_section = ''
    for i, ln in enumerate(lines, 1):
        stripped = ln.lstrip()
        if stripped.startswith('#'):
            cur_section = stripped.lstrip('#').strip()
            continue
        m = anybox_re.match(ln)
        if not m:
            continue
        total += 1                       # counts checked AND unchecked
        mark, text = m.group(1), m.group(2)
        if mark != ' ':                  # checked box — done; counts toward total only
            continue
        if tag_re.search(text) or sec_re.search(cur_section):
            human_open += 1
        else:
            open_exec += 1
            open_lines.append('%s:%d: %s' % (fp, i, text.strip()[:120]))
print('%d\t%d\t%d' % (open_exec, total, human_open))
for l in open_lines:
    print(l)
PYEOF
)" || ANALYSIS="0\t0\t0"

  local HEADER OPEN_EXEC TOTAL HUMAN_OPEN OPEN_LIST
  HEADER="$(printf '%s' "$ANALYSIS" | sed -n '1p')"
  OPEN_EXEC="$(printf '%s' "$HEADER" | cut -f1)"; OPEN_EXEC="${OPEN_EXEC:-0}"
  TOTAL="$(printf '%s' "$HEADER" | cut -f2)"; TOTAL="${TOTAL:-0}"
  HUMAN_OPEN="$(printf '%s' "$HEADER" | cut -f3)"; HUMAN_OPEN="${HUMAN_OPEN:-0}"
  OPEN_LIST="$(printf '%s' "$ANALYSIS" | tail -n +2)"

  # --- Review-verdict check: latest review_verdict(pass) for this plan. ------
  local REVIEW_PASS=0
  if [ -f "plans/_dashboard/state.events.jsonl" ]; then
    REVIEW_PASS="$(python3 - "$REL" <<'PYEOF'
import json, sys, os
target = sys.argv[1].replace(os.sep, '/')
if target.startswith('./'): target = target[2:]
latest = None
try:
    with open('plans/_dashboard/state.events.jsonl', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or '"review_verdict"' not in line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get('event') != 'review_verdict':
                continue
            p = str(ev.get('plan', '')).replace(os.sep, '/')
            if p.startswith('./'): p = p[2:]
            if p == target:
                latest = str(ev.get('verdict', '')).lower()
except FileNotFoundError:
    pass
print('1' if latest == 'pass' else '0')
PYEOF
)" || REVIEW_PASS=0
  fi

  # Not a real execution plan (no checkboxes at all) → leave it alone.
  [ "${TOTAL:-0}" -eq 0 ] && return 0

  # --- Docs/context evidence gate (before stamping stage 6) ------------------
  # For each path in frontmatter context:/docs: (skip literal none): require a
  # git commit since stage-5 transition in the path's OWNING repo. Soft-warn
  # (never hard-block) when stage_5 ts or owning repo can't be resolved.
  docs_gate_block() {
    # prints BLOCK reasons to stdout; empty = ok to stamp
    python3 - "$PLAN" "$REL" <<'PYEOF'
import json, os, re, subprocess, sys
from pathlib import Path

plan_path = Path(sys.argv[1])
plan_rel = sys.argv[2].replace(os.sep, "/")
if plan_rel.startswith("./"):
    plan_rel = plan_rel[2:]

def read_fm(path: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    data = {}
    for line in text[3:end].splitlines():
        s = line.strip()
        if not s or s.startswith("#") or ":" not in s:
            continue
        k, _, v = s.partition(":")
        data[k.strip()] = v.split(" #")[0].strip()
    return data

def parse_list(val: str):
    if not val:
        return []
    v = val.strip()
    if v.lower() == "none":
        return []
    # YAML list: [a, b] or plain path
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]
    return [v.strip().strip("\"'")]

fm = read_fm(plan_path)
declared = parse_list(fm.get("context", "none" if "context" not in fm else fm.get("context", "")))
# Missing key does not block (validate already warned). Only declared paths gate.
if "context" in fm:
    declared = parse_list(fm["context"])
else:
    declared = []
if "docs" in fm:
    declared = declared + parse_list(fm["docs"])

if not declared:
    sys.exit(0)

# Resolve stage_5_transition_ts
state_dir = os.environ.get("META_DEV_STATE_DIR", "plans/_dashboard")
events = Path(state_dir) / "state.events.jsonl"
stage5_ts = None
if events.is_file():
    latest = None
    try:
        for line in events.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or "stage_transition" not in line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("event") != "stage_transition":
                continue
            p = str(ev.get("plan", "")).replace(os.sep, "/")
            if p.startswith("./"):
                p = p[2:]
            # match plan path or any file under same plan dir
            plan_dir = plan_rel.rsplit("/", 1)[0] if "/" in plan_rel else plan_rel
            if p == plan_rel or p.startswith(plan_dir + "/") or plan_rel.startswith(p.rstrip("/") + "/"):
                sn = ev.get("stage_num") or ev.get("stage")
                try:
                    sn_i = int(sn)
                except (TypeError, ValueError):
                    sn_i = 5 if str(sn).lower() in ("5", "execute") else -1
                if sn_i == 5 or str(sn).lower() == "execute":
                    latest = ev.get("time") or latest
    except Exception:
        pass
    stage5_ts = latest

if not stage5_ts:
    # Fallback: git pickaxe in meta for stage: 5 introduction
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "-S", "stage: 5", "--", str(plan_path)],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            stage5_ts = r.stdout.strip()
    except Exception:
        pass

if not stage5_ts:
    print(
        "WARN docs-gate: no stage_5 transition ts on record "
        "(event log + pickaxe miss) — soft-pass, not hard-blocking",
        file=sys.stderr,
    )
    sys.exit(0)

def owning_repo(path: Path):
    cur = path if path.is_dir() else path.parent
    cur = cur.resolve()
    for _ in range(40):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None

blocks = []
for rel in declared:
    # path may be repo-relative from meta root
    abs_p = Path(rel)
    if not abs_p.is_absolute():
        abs_p = Path.cwd() / rel
    repo = owning_repo(abs_p if abs_p.exists() else Path.cwd() / rel)
    if repo is None:
        print(f"WARN docs-gate: unresolvable repo for {rel!r} — advisory, not blocking", file=sys.stderr)
        continue
    try:
        rel_in_repo = str(abs_p.resolve().relative_to(repo.resolve()))
    except Exception:
        # untracked / outside
        print(f"WARN docs-gate: path not under repo for {rel!r} — advisory, not blocking", file=sys.stderr)
        continue
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "log", "--since", stage5_ts, "--oneline", "--", rel_in_repo],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode != 0 or not r.stdout.strip():
            # also accept dirty (uncommitted) modification as evidence of write-in-progress?
            # Design: require modified since stage 5 via git log — unmodified blocks.
            blocks.append(f"declared path unmodified since stage 5 ({stage5_ts}): {rel}")
    except Exception as e:
        print(f"WARN docs-gate: git log failed for {rel!r}: {e}", file=sys.stderr)

if blocks:
    for b in blocks:
        print(b)
    sys.exit(1)
sys.exit(0)
PYEOF
  }

  # --- Decision matrix -------------------------------------------------------
  # (1) clean + reviewed → STAMP DONE (covers both in_progress & completed lag).
  if [ "${OPEN_EXEC:-0}" -eq 0 ] && [ "$REVIEW_PASS" = "1" ]; then
    # Docs/context evidence (if declared) must land before stage 6.
    local DOCS_OUT=""
    set +e
    DOCS_OUT="$(docs_gate_block 2>&1)"
    local DOCS_RC=$?
    set -e
    if [ "$DOCS_RC" -ne 0 ]; then
      emit_event "done_gate" "$REL" "docs_missing" "$NOW"
      inbox_fail "$REL" "medium" \
        "Execution + review pass but declared context:/docs: paths lack git evidence since stage 5 — NOT stamped DONE. ${DOCS_OUT}" \
        "$NOW"
      printf '[done-gate] %s — docs/context gate blocked stamp:\n%s\n' "$REL" "$DOCS_OUT" >&2
      return 0
    fi
    # surface soft warnings from docs_gate_block
    if [ -n "$DOCS_OUT" ]; then
      printf '%s\n' "$DOCS_OUT" >&2
    fi
    bash "$PLUGIN_ROOT/scripts/stage-emit.sh" "$PLAN" review completed >/dev/null 2>&1 || true
    # Render the owning runbook if this plan is a campaign member (standalone
    # plans need no render — /meta-dashboard reads the freshly-stamped YAML).
    local RB=""
    RB="$(grep -rlF --include='_runbook-*.md' "$REL" plans/ 2>/dev/null | head -1 || true)"
    if [ -n "$RB" ]; then
      python3 "$PLUGIN_ROOT/scripts/runbook-render.py" "$RB" >/dev/null 2>&1 || true
    fi
    emit_event "done_gate" "$REL" "done" "$NOW"
    printf '[done-gate] %s -> DONE (stage 6) — execution + review complete.\n' "$REL" >&2
    return 0
  fi

  # (2) clean but NOT reviewed → don't stamp; flag review-missing.
  if [ "${OPEN_EXEC:-0}" -eq 0 ] && [ "$REVIEW_PASS" != "1" ]; then
    emit_event "done_gate" "$REL" "review_missing" "$NOW"
    inbox_fail "$REL" "medium" \
      "Execution checkboxes are all flipped but no review_verdict(pass) is on record — NOT stamped DONE. Run (or record) the mandatory post-run code review, then the gate will advance it on the next stop." \
      "$NOW"
    printf '[done-gate] %s — exec boxes clean but NO review PASS on record; left at stage 5.\n' "$REL" >&2
    return 0
  fi

  # (3) open boxes + status:completed → FAIL LOUD (claimed done, boxes disagree).
  if [ "${OPEN_EXEC:-0}" -gt 0 ] && [ "$STATUS" = "completed" ]; then
    emit_event "done_gate" "$REL" "fail_open_boxes" "$NOW"
    local body="Status is 'execute completed' but ${OPEN_EXEC} execution checkbox(es) remain unchecked (human-verify gates excluded):"
    body="$body"$'\n'"$(printf '%s\n' "$OPEN_LIST" | head -25)"
    inbox_fail "$REL" "high" "$body" "$NOW"
    printf '[done-gate] FAIL LOUD — %s claimed execute completed but %s execution checkbox(es) still open:\n' "$REL" "$OPEN_EXEC" >&2
    printf '%s\n' "$OPEN_LIST" 2>/dev/null | head -25 >&2
    return 0
  fi

  # (4) open boxes + in_progress/blocked → run alive or intentionally halted.
  return 0
}

# --- Find stage-5 plans + their status (dedup by plan scope). ----------------
# Prints lines: <plan-master-path>\t<scope>\t<status>\t<plan-rel>
MAP="$(python3 - "$PLANS_DIR" <<'PYEOF'
import os, sys, re
plans_dir = sys.argv[1]
stage_re  = re.compile(r'^stage:\s*([0-9]+)\s*$')
status_re = re.compile(r'^status:\s*(\S+)', re.I)

def frontmatter(path):
    try:
        with open(path, encoding='utf-8') as f:
            lines = f.read(4096).splitlines()
    except Exception:
        return None, None
    if not lines or lines[0].strip() != '---':
        return None, None
    st = stat = None
    for ln in lines[1:]:
        if ln.strip() == '---':
            break
        m = stage_re.match(ln)
        if m:
            st = m.group(1)
        m2 = status_re.match(ln)
        if m2:
            stat = m2.group(1).lower()
    return st, stat

seen = set()
out = []
for root, dirs, files in os.walk(plans_dir):
    # Skip internals that are not plans.
    dirs[:] = [d for d in dirs if d not in ('_dashboard', 'inbox', '__pycache__')]
    for fn in files:
        if not fn.endswith('.md'):
            continue
        p = os.path.join(root, fn)
        st, stat = frontmatter(p)
        if st != '5':
            continue
        # Plan scope:
        # - has_master is EXACT '00-master-plan.md' (never bare 00-* — dirs carry
        #   00-design.md / 00-master-design.md / 00-overview.md false masters).
        # - Self-gating: when the dir has 00-master-plan.md AND every non-master
        #   *.md already carries zero checkboxes (initiative demoted), scope =
        #   master file only. Otherwise scan the whole dir so phase-as-ledger
        #   plans cannot blind the DONE gate mid-migration.
        d = os.path.dirname(p)
        master_name = '00-master-plan.md'
        has_master = master_name in files
        box_re = re.compile(r'^\s*[-*]\s*\[[ xX]\]')
        if has_master:
            master_path = os.path.join(d, master_name)
            phase_has_boxes = False
            for ff in files:
                if ff == master_name or not ff.endswith('.md'):
                    continue
                try:
                    with open(os.path.join(d, ff), encoding='utf-8') as fh:
                        for ln in fh:
                            if box_re.match(ln):
                                phase_has_boxes = True
                                break
                except Exception:
                    pass
                if phase_has_boxes:
                    break
            scope = master_path if not phase_has_boxes else d
        else:
            scope = p
        if scope in seen:
            continue
        seen.add(scope)
        rel = p.replace(os.sep, '/')
        if rel.startswith('./'):
            rel = rel[2:]
        # Prefer the master path as PLAN when has_master
        plan_out = os.path.join(d, master_name) if has_master else p
        out.append('\t'.join([plan_out, scope, stat or '', rel if not has_master else plan_out.replace(os.sep, '/')]))
print('\n'.join(out))
PYEOF
)" || MAP=""

# --- (a) DONE-stamp pass: advance clean+reviewed stage-5 plans to stage 6. ----
# Only stage-5 plans appear in MAP; a plan already past stage 5 is intentionally
# not re-stamped here — its dashboard freshness is guaranteed by pass (b) below.
if [ -n "$MAP" ]; then
  while IFS=$'\t' read -r PLAN SCOPE STATUS REL; do
    [ -n "$PLAN" ] && run_gate "$PLAN" "$SCOPE" "$STATUS" "$REL"
  done <<< "$MAP"
fi

# --- (b) Runbook reconcile pass: UNCONDITIONAL, every runbook, every stop. ----
# THE fix for the frozen-dashboard bug. The re-render used to live ONLY inside
# the stage-5→6 stamp branch (run_gate case 1), so the instant a member reached
# stage 6 by ANY other path — a conductor hand-flipping frontmatter at closeout,
# a direct stage-emit, a manual YAML edit — it dropped off the stage-5 radar and
# its runbook froze forever (it is never stage 5 again, so the branch never runs
# again). Re-rendering every campaign runbook on every stop makes the dashboard
# a pure projection of live member frontmatter, refreshed no matter how a member
# advanced. runbook-render.py is idempotent on disk (writes only when content
# changed), so unchanged runbooks are not touched — no mtime churn, no spurious
# dirty files. Runs even when MAP is empty (a stop with zero stage-5 plans is
# exactly when a just-closed-out member needs its dashboard caught up).
while IFS= read -r RB; do
  [ -n "$RB" ] || continue
  python3 "$PLUGIN_ROOT/scripts/runbook-render.py" "$RB" >/dev/null 2>&1 || true
done < <(find "$PLANS_DIR" -type f -name '_runbook-*.md' 2>/dev/null)

exit 0
