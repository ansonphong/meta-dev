#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$SCRIPT_DIR/lib/anchor-root.sh"
# Dashboard data gatherer — deterministic, no LLM. Outputs JSON to stdout.
# Anchors itself to the project root. Reads plans (via plan-index.py), git, state, inbox.

# Project name from directory or git
PROJECT=$(basename "$(pwd)")
GIT_REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*[:/]\(.*\)\.git/\1/' || echo "$PROJECT")

# ── Arguments ────────────────────────────────────────────────────────────────
# Bare `meta-dashboard` behaves exactly as before; every arg below is optional.
#   SCOPE (positional): a plans/ DIR (narrow the Plans panel) OR a single .md
#                       plan FILE (focus view — frontmatter + per-section bars).
#   --commits[=N]       focus on commits: N (default 25), expanded with dates.
#   --only a,b / --no a,b   select / hide sections.
#   --repo / --status   filter the plan set.   --all  include archive/future.
SCOPE=""; ONLY=""; NO=""; REPO=""; STATUS=""; ALL=0
COMMITS_FLAG=0; COMMITS_EXPANDED=0; COMMIT_COUNT=10
while [ $# -gt 0 ]; do
    case "$1" in
        --commits)    COMMITS_FLAG=1; COMMITS_EXPANDED=1; COMMIT_COUNT=25 ;;
        --commits=*)  COMMITS_FLAG=1; COMMITS_EXPANDED=1; COMMIT_COUNT="${1#*=}" ;;
        --only)       ONLY="${2:-}"; shift ;;
        --only=*)     ONLY="${1#*=}" ;;
        --no)         NO="${2:-}"; shift ;;
        --no=*)       NO="${1#*=}" ;;
        --repo)       REPO="${2:-}"; shift ;;
        --repo=*)     REPO="${1#*=}" ;;
        --status)     STATUS="${2:-}"; shift ;;
        --status=*)   STATUS="${1#*=}" ;;
        --all)        ALL=1 ;;
        -h|--help)
            cat <<'HELP'
meta-dashboard [SCOPE] [flags]
  SCOPE            plans/ directory (narrow Plans) OR a .md plan file (focus view)
  --commits[=N]    focus on commits — N (default 25), expanded with dates
  --only a,b,c     render only these sections
  --no a,b,c       render every section except these
  --repo NAME      only plans whose repo: matches
  --status NAME    only plans whose status: matches
  --all            include _archive/_future/_research plans
  -h, --help       show this help
Sections: plans focus milestones sessions inbox sweep commits
HELP
            exit 0 ;;
        --*)          echo "meta-dashboard: unknown flag: $1" >&2; exit 2 ;;
        *)            SCOPE="$1" ;;
    esac
    shift
done
# Guard COMMIT_COUNT against non-numeric input (e.g. --commits=abc).
case "$COMMIT_COUNT" in ''|*[!0-9]*) COMMIT_COUNT=10 ;; esac

# Plans: delegate ALL plan scanning to plan-index.py — the single source of
# truth. It parses the runbook Sequence (display order), milestones, and each
# plan's status/stage/progress from frontmatter + checkboxes. This script no
# longer reads plans/ directly, nor STATUS.md / exec-order.md (both retired).
PLAN_INDEX_JSON="{}"
if [ -f "$SCRIPT_DIR/plan-index.py" ]; then
    PI_ARGS=()
    [ -n "$SCOPE" ]   && PI_ARGS+=(--scope "$SCOPE")
    [ -n "$REPO" ]    && PI_ARGS+=(--repo "$REPO")
    [ -n "$STATUS" ]  && PI_ARGS+=(--status "$STATUS")
    [ "$ALL" = 1 ]    && PI_ARGS+=(--all)
    PLAN_INDEX_JSON=$(python3 "$SCRIPT_DIR/plan-index.py" "${PI_ARGS[@]+"${PI_ARGS[@]}"}" 2>/dev/null || echo "{}")
fi

# State: read from state.json via state-read.sh
STATE_JSON="{}"
if [ -f plans/_dashboard/state.json ]; then
    STATE_JSON=$(python3 -c "
import json
try:
    with open('plans/_dashboard/state.json') as f:
        state = json.load(f)
    # Extract active sessions
    sessions = []
    for s in state.get('active_sessions', [])[-5:]:
        sessions.append({
            'session': s.get('session_id', '?')[:16],
            'plan': (s.get('plan', '') or '—')[:20],
            'task': (s.get('task', '') or '—')[:8],
            'stage': (s.get('stage', '') or '—')[:10]
        })
    state['_sessions'] = sessions
    print(json.dumps(state))
except Exception:
    print('{}')
" 2>/dev/null || echo "{}")
fi
SESSIONS=$(echo "$STATE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('_sessions',[])))" 2>/dev/null || echo "[]")

# Inbox counts
INBOX_OPEN=0
INBOX_ADVISORIES=0
INBOX_AUTO=0
if [ -f plans/_dashboard/inbox/inbox.jsonl ]; then
    INBOX_OPEN=$(python3 -c "
import json
try:
    with open('plans/_dashboard/inbox/inbox.jsonl') as f:
        events = [json.loads(l) for l in f if l.strip()]
    state = {}
    for e in events:
        eid = e.get('id','')
        if e.get('event') == 'resolve':
            state[eid] = e.get('status','resolved')
        elif 'status' in e:
            state[eid] = e['status']
    print(sum(1 for s in state.values() if s == 'open'))
except: print(0)
" 2>/dev/null || echo 0)
    INBOX_AUTO=$(python3 -c "
import json
try:
    with open('plans/_dashboard/inbox/inbox.jsonl') as f:
        events = [json.loads(l) for l in f if l.strip()]
    state = {}
    for e in events:
        eid = e.get('id','')
        if e.get('event') == 'resolve':
            state[eid] = e.get('status','resolved')
        elif 'status' in e:
            state[eid] = e['status']
    print(sum(1 for e in events if e.get('auto_clearable') and state.get(e.get('id','')) == 'open'))
except: print(0)
" 2>/dev/null || echo 0)
fi

# Recent commits — COMMIT_COUNT rows, with relative date for expanded mode.
# Fields are \x1f-separated so commit subjects can contain anything.
COMMITS_JSON=$(git log -"$COMMIT_COUNT" --date=relative --format='%h%x1f%ad%x1f%s' 2>/dev/null | python3 -c "
import json, sys
commits = []
for line in sys.stdin:
    line = line.rstrip('\n')
    if not line: continue
    parts = line.split('\x1f')
    sha = parts[0] if parts else '?'
    ago = parts[1] if len(parts) > 1 else '—'
    msg = parts[2] if len(parts) > 2 else '?'
    commits.append({'sha': sha, 'ago': ago, 'msg': msg})
print(json.dumps(commits))
" 2>/dev/null || echo "[]")

# Dirty count
DIRTY=$(git status --short 2>/dev/null | wc -l | tr -d ' ')

# Unpushed count
UNPUSHED=$(git log --branches --not --remotes --oneline 2>/dev/null | wc -l | tr -d ' ')

# Sweep log from state
SWEEP_JSON=$(echo "$STATE_JSON" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    log = d.get('sweep_log', [])[-5:]
    print(json.dumps([s.get('action', str(s)) if isinstance(s, dict) else str(s) for s in log]))
except: print('[]')
" 2>/dev/null || echo "[]")

# Output full JSON. The plan-index payload is passed via env (not string
# interpolation) so unicode escapes / quotes in plan titles can't corrupt the
# generated Python source. Reshape plan-index's plans into the fields the
# renderer expects, ordered by the runbook Sequence first, extras after.
export PLAN_INDEX_JSON SESSIONS SWEEP_JSON COMMITS_JSON ONLY NO COMMITS_FLAG
python3 -c "
import json, os, re

def plan_name(path):
    base = os.path.basename(path)
    if 'master-plan' in base:
        nm = os.path.basename(os.path.dirname(path))
    else:
        nm = os.path.splitext(base)[0]
    return re.sub(r'^\d{4}-\d{2}-\d{2}-', '', nm)

idx = json.loads(os.environ.get('PLAN_INDEX_JSON') or '{}')
order = idx.get('order', [])
pos = {p: i for i, p in enumerate(order)}
raw = list(idx.get('plans', []))
# Sequence order first; anything not in the runbook sorts to the end.
raw.sort(key=lambda p: pos.get(p.get('path', ''), 10**6))
plans = []
for p in raw:
    prog = p.get('progress', {}) or {}
    plans.append({
        'name': plan_name(p.get('path', '?')),
        'path': p.get('path', ''),
        'repo': p.get('repo', ''),
        'tasks_done': prog.get('done', 0),
        'tasks_total': prog.get('total', 0),
        'status': p.get('status') or 'draft',
        'stage': p.get('stage', 0),
        'why': p.get('why', ''),
        'malformed': bool(p.get('malformed', False)),
    })

# Which panels render, in order. Focus mode (single-file scope) swaps the Plans
# panel for the Focus panel; --commits with no explicit selection narrows to it.
focus = idx.get('focus')
ALL_SECTIONS = ['plans', 'milestones', 'sessions', 'inbox', 'sweep', 'commits']
only = (os.environ.get('ONLY') or '').strip()
no = (os.environ.get('NO') or '').strip()
commits_flag = os.environ.get('COMMITS_FLAG') == '1'
base = ['focus', 'commits'] if focus else list(ALL_SECTIONS)
if only:
    sections = [s.strip() for s in only.split(',') if s.strip()]
elif no:
    drop = {s.strip() for s in no.split(',') if s.strip()}
    sections = [s for s in base if s not in drop]
elif commits_flag and not focus:
    sections = ['commits']
else:
    sections = base

data = {
    'project': '$GIT_REPO',
    'plans': plans,
    'milestones': idx.get('milestones', []),
    'untracked': idx.get('untracked', []),
    'counts': idx.get('counts', {}),
    'active_sessions': json.loads(os.environ.get('SESSIONS') or '[]'),
    'inbox': {
        'advisories': $INBOX_ADVISORIES,
        'issues_open': $INBOX_OPEN,
        'auto_clearable': $INBOX_AUTO
    },
    'sweep_log': json.loads(os.environ.get('SWEEP_JSON') or '[]'),
    'recent_commits': json.loads(os.environ.get('COMMITS_JSON') or '[]'),
    'focus': focus,
    'scope': idx.get('scope'),
    'scope_kind': idx.get('scope_kind'),
    'sections': sections,
    'commits_expanded': bool($COMMITS_EXPANDED),
    'refresh_rate': 'once',
    'agent_count': 0,
    'dirty_count': $DIRTY,
    'unpushed_count': $UNPUSHED
}
print(json.dumps(data))
"
