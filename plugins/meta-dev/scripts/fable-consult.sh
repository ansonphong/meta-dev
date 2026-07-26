#!/usr/bin/env bash
# fable-consult — ask Fable 5 a judgment call before waking the human.
#
# The escalation pre-step for long-horizon and --autonomous runs. Dispatches a
# READ-ONLY Fable worker, applies the veto list / calibration caps / consult
# caps MECHANICALLY (prose gates get skipped; a script does not), logs the
# decision, and exits with the routing verdict.
#
#   0  ADOPT             cleared 0.90 WITH evidence and a falsifier
#   10 ESCALATE          low confidence, capped confidence, cap hit, or repeat
#   11 ESCALATE (veto)   safety class — never Fable's to answer
#   12 DEFER             --autonomous + reversible taste → REVIEW-ME, keep going
#   2  ERROR             consult failed → treat as ESCALATE. FAIL CLOSED.
#
# Contract, calibration rationale and the veto list: skills/fable-consult/SKILL.md
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/plugin-root.sh
source "$SCRIPT_DIR/lib/plugin-root.sh"
PLUGIN_ROOT="$(_md_plugin_root)"
QUESTION=""; PACKET=""; PLAN=""; REPO=""; AUTONOMOUS=0; REVERSIBLE=0; TASTE=0
CAP="${META_DEV_FABLE_CONSULT_CAP:-5}"

# Anchor the log to the PROJECT root, never the cwd. A consult fired from a
# child repo must not scatter a second decisions log there — the whole point is
# one durable record the user reads in the morning. Walking up for `plans/`
# beats asking git: this tree nests four independent repos and
# `rev-parse --show-toplevel` returns whichever one the shell happens to sit in
# (the banned-for-cause idiom in CLAUDE.md → Directory Awareness).
_resolve_project_root() {
  [ -n "${META_DEV_PROJECT_ROOT:-}" ] && { printf '%s' "$META_DEV_PROJECT_ROOT"; return; }
  [ -n "${CLAUDE_PROJECT_DIR:-}" ]    && { printf '%s' "$CLAUDE_PROJECT_DIR";    return; }
  local d; d="$(pwd -P 2>/dev/null || echo .)"
  while [ "$d" != "/" ] && [ -n "$d" ]; do
    [ -d "$d/plans" ] && { printf '%s' "$d"; return; }
    d="$(dirname "$d")"
  done
  pwd -P 2>/dev/null || echo .   # no plans/ anywhere — caller's cwd, created below
}
PROJECT_ROOT="$(_resolve_project_root)"
LOG_DIR="$PROJECT_ROOT/plans/_dashboard"
LOG="$LOG_DIR/fable-decisions.jsonl"

while [ $# -gt 0 ]; do
  case "$1" in
    --question)   QUESTION="$2"; shift 2 ;;
    --packet)     PACKET="$2";   shift 2 ;;
    --plan)       PLAN="$2";     shift 2 ;;
    --repo)       REPO="$2";     shift 2 ;;
    --autonomous) AUTONOMOUS=1;  shift ;;
    --reversible) REVERSIBLE=1;  shift ;;
    --taste)      TASTE=1;       shift ;;
    --cap)        CAP="$2";      shift 2 ;;
    -h|--help)    sed -n '2,18p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *)            echo "fable-consult: unknown arg '$1'" >&2; exit 2 ;;
  esac
done

[ -z "$QUESTION" ] && { echo "fable-consult: --question is required" >&2; exit 2; }
mkdir -p "$LOG_DIR" 2>/dev/null || true

# ── logging ───────────────────────────────────────────────────────────────
# Log FIRST on every terminal path. A decision made autonomously and not
# logged is indistinguishable from a decision nobody made.
log_decision() {  # verdict conf recommendation falsifier
  python3 - "$LOG" "$QUESTION" "$PLAN" "$1" "$2" "$3" "$4" <<'PY' 2>/dev/null || true
import json, sys, datetime
log, q, plan, verdict, conf, rec, fals = sys.argv[1:8]
row = {"event":"fable_consult","time":datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
       "plan":plan,"question":q,"verdict":verdict,
       "confidence":(float(conf) if conf not in ("","-") else None),
       "recommendation":rec,"wrong_if":fals}
with open(log,"a") as f: f.write(json.dumps(row)+"\n")
PY
}

emit() {  # verdict conf recommendation falsifier unverified reasoning
  echo
  echo "── FABLE CONSULT ──────────────────────────────────────────────"
  echo "  QUESTION   : $QUESTION"
  echo "  VERDICT    : $1${2:+  (confidence $2)}"
  [ -n "${3:-}" ] && echo "  RECOMMENDS : $3"
  [ -n "${6:-}" ] && echo "  BECAUSE    : $6"
  [ -n "${4:-}" ] && echo "  WRONG IF   : $4"
  [ -n "${5:-}" ] && echo "  UNVERIFIED : $5"
  echo "───────────────────────────────────────────────────────────────"
}

# ── 1. Veto list — mechanical, BEFORE spending a consult ──────────────────
# These are never Fable's to answer at any confidence. Matched on the question
# and packet together. A false positive here costs one human question; a false
# negative lets an unattended run decide something irreversible. Fail toward
# the human.
VETO_RE='delete|destroy|drop table|truncate|force.?push|rewrite histor|reset --hard|migrat|schema chang|alembic|deploy|publish|release to prod|production|npm publish|ship it|stripe|payment|pricing|billing|money|invoice|refund|auth|oauth|password|secret|credential|api.?key|token|crypto|ed25519|licens|signing key|permission boundar|send email|email.*(user|customer)|cross-repo (api|contract)'
HAYSTACK="$QUESTION"
[ -n "$PACKET" ] && [ -f "$PACKET" ] && HAYSTACK="$HAYSTACK
$(cat "$PACKET" 2>/dev/null)"

if printf '%s' "$HAYSTACK" | grep -qiE "$VETO_RE"; then
  MATCH="$(printf '%s' "$HAYSTACK" | grep -oiE "$VETO_RE" | head -1)"
  log_decision "escalate_veto" "-" "" ""
  emit "ESCALATE — VETO CLASS ('$MATCH')" "" \
       "Not Fable's call at any confidence. Ask the human." "" "" \
       "Safety-class decisions always reach a person (skills/fable-consult/SKILL.md → veto list)."
  exit 11
fi

# ── 2. Caps — a consult loop is worse than an escalation ──────────────────
if [ -f "$LOG" ]; then
  QHASH="$(printf '%s' "$QUESTION" | md5sum | cut -d' ' -f1)"
  PRIOR="$(python3 - "$LOG" "$QUESTION" <<'PY' 2>/dev/null || echo "0 0"
import json,sys
log,q=sys.argv[1],sys.argv[2]
n=dup=0
try:
    for line in open(log):
        try: r=json.loads(line)
        except Exception: continue
        if r.get("event")!="fable_consult": continue
        n+=1
        if r.get("question")==q: dup+=1
except FileNotFoundError: pass
print(n,dup)
PY
)"
  TOTAL="${PRIOR%% *}"; DUP="${PRIOR##* }"
  if [ "${DUP:-0}" -gt 0 ]; then
    log_decision "escalate_repeat" "-" "" ""
    emit "ESCALATE — ALREADY ASKED" "" \
         "This exact question was consulted before. Fable will not break the loop." "" "" \
         "A run that re-asks is going in circles; surface it instead of spending another consult."
    exit 10
  fi
  if [ "${TOTAL:-0}" -ge "$CAP" ]; then
    log_decision "escalate_cap" "-" "" ""
    emit "ESCALATE — CONSULT CAP ($TOTAL/$CAP)" "" \
         "Escalate everything from here." "" "" \
         "A run burning consults is an under-hardened plan — surface that, do not spend through it."
    exit 10
  fi
fi

# ── 3. Build the consult prompt ───────────────────────────────────────────
PACKET_TEXT="(none supplied)"
[ -n "$PACKET" ] && [ -f "$PACKET" ] && PACKET_TEXT="$(cat "$PACKET")"

PROMPT="You are being consulted as the DECIDING authority on one hard judgment call
that an autonomous execution run hit. The run is blocked. The human is asleep and
must not be woken unless you genuinely cannot close this out.

DECISION: $QUESTION

CONTEXT PACKET:
$PACKET_TEXT

You are READ-ONLY. Read the code before answering — a recommendation reasoned
from this packet alone will be rejected.

Return ONLY a fenced json block, no prose outside it:

\`\`\`json
{
  \"recommendation\": \"the decision, stated as an instruction the run can execute\",
  \"reasoning\": \"1-3 sentences on why this over the alternatives\",
  \"confidence\": 0.0,
  \"what_would_make_this_wrong\": \"a concrete, checkable condition that would falsify this\",
  \"evidence\": [\"path/to/file.ts:120\", \"...\"],
  \"unverified\": [\"anything load-bearing you could not check\"],
  \"is_product_taste\": false,
  \"is_reversible\": true
}
\`\`\`

CALIBRATION — read this before you pick a number. Your confidence is checked,
not trusted. State the number you would defend if someone audited this decision
tomorrow against the real codebase.
 - No concrete falsifier => your verdict is capped and escalated. 'Nothing would
   make this wrong' is treated as a FAILURE to model uncertainty, not strength.
 - No file:line evidence you actually read => capped and escalated.
 - Load-bearing entries in 'unverified' => capped and escalated.
 - Overconfidence costs the human more than escalation does. If you are at 0.85,
   say 0.85. An honest 0.85 routes correctly; an inflated 0.95 does not.
Set is_product_taste=true if this is a call about brand, naming, pricing, or the
shape of a user-facing flow — those belong to the human even when you are sure."

# ── 4. Dispatch (read-only; a consult advises, it never edits) ────────────
OUT="$(bash "$PLUGIN_ROOT/scripts/claude-headless-exec" \
        --backend fable --readonly --effort xhigh \
        ${REPO:+--repo "$REPO"} -- "$PROMPT" 2>&1)"
RC=$?
OUTPUT_FILE="$(printf '%s' "$OUT" | grep -oE '^OUTPUT_FILE=.*' | head -1 | cut -d= -f2-)"

if [ $RC -ne 0 ] || [ -z "$OUTPUT_FILE" ] || [ ! -f "$OUTPUT_FILE" ]; then
  log_decision "error" "-" "" ""
  emit "ERROR — CONSULT FAILED (rc=$RC)" "" \
       "Treat as ESCALATE. Never as ADOPT." "" "" \
       "Absence of an objection is not an approval — fail closed."
  exit 2
fi

# ── 5. Parse + apply the calibration caps ─────────────────────────────────
VERDICT="$(python3 - "$OUTPUT_FILE" "$AUTONOMOUS" "$REVERSIBLE" "$TASTE" <<'PY'
import json, re, sys
path, autonomous, rev_flag, taste_flag = sys.argv[1], sys.argv[2]=="1", sys.argv[3]=="1", sys.argv[4]=="1"
def die(msg):
    print("\t".join(["error","-","",msg,"",""])); sys.exit(0)
try:
    res = json.load(open(path)).get("result","")
except Exception as e:
    die(f"unreadable output ({e})")
m = re.search(r"```json\s*(\{.*?\})\s*```", res, re.S) or re.search(r"(\{.*\})", res, re.S)
if not m: die("no JSON verdict in response")
try:
    v = json.loads(m.group(1))
except Exception as e:
    die(f"malformed JSON verdict ({e})")

rec   = (v.get("recommendation") or "").strip()
why   = (v.get("reasoning") or "").strip()
fals  = (v.get("what_would_make_this_wrong") or "").strip()
ev    = [str(x) for x in (v.get("evidence") or []) if str(x).strip()]
unver = [str(x) for x in (v.get("unverified") or []) if str(x).strip()]
try: conf = float(v.get("confidence", 0))
except Exception: conf = 0.0
taste = bool(v.get("is_product_taste")) or taste_flag
rev   = bool(v.get("is_reversible", True)) or rev_flag

if not rec: die("verdict carried no recommendation")

# Calibration caps — the number is only as good as what backs it.
capped = []
NULL_FALS = re.compile(r"^(nothing|n/?a|none|no( |thing)|-|unknown)\b", re.I)
if not fals or NULL_FALS.match(fals):
    capped.append("no falsifier")
if not any(re.search(r"[^\s:]+:\d+", e) for e in ev):
    capped.append("no file:line evidence")
if unver:
    capped.append("unverified load-bearing assumptions")
if capped:
    conf = min(conf, 0.89)

# Route.
if taste and rev and autonomous:
    verdict = "defer"          # REVIEW-ME, keep going; human owns it in the morning
elif conf >= 0.90:
    verdict = "adopt"
else:
    verdict = "escalate"
note = ("capped: " + ", ".join(capped)) if capped else ""
print("\t".join([verdict, f"{conf:.2f}", rec, fals, "; ".join(unver), why, note]))
PY
)"

IFS=$'\t' read -r V CONF REC FALS UNVER WHY NOTE <<< "$VERDICT"

case "$V" in
  adopt)
    log_decision "adopt" "$CONF" "$REC" "$FALS"
    emit "ADOPT" "$CONF" "$REC" "$FALS" "$UNVER" "$WHY"
    echo "  → Take this recommendation and continue. Do not re-litigate it."
    exit 0 ;;
  defer)
    log_decision "defer" "$CONF" "$REC" "$FALS"
    emit "DEFER — REVIEW-ME" "$CONF" "$REC" "$FALS" "$UNVER" "$WHY"
    echo "  → Product taste is the human's. Apply the most reversible option,"
    echo "    mark REVIEW-ME, keep going. It lands in the morning punch list."
    exit 12 ;;
  escalate)
    log_decision "escalate_lowconf" "$CONF" "$REC" "$FALS"
    emit "ESCALATE — LOW CONFIDENCE${NOTE:+ ($NOTE)}" "$CONF" "$REC" "$FALS" "$UNVER" "$WHY"
    echo "  → Ask the human. Lead the options with this recommendation and"
    echo "    show the confidence EXACTLY as returned — do not round it up."
    exit 10 ;;
  *)
    log_decision "error" "-" "" "${FALS:-parse failure}"
    emit "ERROR — ${FALS:-unparseable verdict}" "" \
         "Treat as ESCALATE. Never as ADOPT." "" "" "Fail closed."
    exit 2 ;;
esac
