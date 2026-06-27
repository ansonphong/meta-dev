#!/usr/bin/env bash
set -euo pipefail
# Dashboard data gatherer — deterministic, no LLM. Outputs JSON to stdout.
# Run from project root. Reads plans (via plan-index.py), git, state, inbox.

# Project name from directory or git
PROJECT=$(basename "$(pwd)")
GIT_REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*[:/]\(.*\)\.git/\1/' || echo "$PROJECT")

# Plans: delegate ALL plan scanning to plan-index.py — the single source of
# truth. It parses the runbook Sequence (display order), milestones, and each
# plan's status/stage/progress from frontmatter + checkboxes. This script no
# longer reads plans/ directly, nor STATUS.md / exec-order.md (both retired).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLAN_INDEX_JSON="{}"
if [ -f "$SCRIPT_DIR/plan-index.py" ]; then
    PLAN_INDEX_JSON=$(python3 "$SCRIPT_DIR/plan-index.py" 2>/dev/null || echo "{}")
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

# Recent commits
COMMITS_JSON=$(git log --oneline -10 --format='%h %s' 2>/dev/null | python3 -c "
import json, sys
commits = []
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    parts = line.split(' ', 1)
    sha = parts[0] if parts else '?'
    msg = parts[1][:72] if len(parts) > 1 else '?'
    commits.append({'sha': sha, 'msg': msg, 'ago': '—'})
print(json.dumps(commits[:8]))
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
export PLAN_INDEX_JSON SESSIONS SWEEP_JSON COMMITS_JSON
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
    'refresh_rate': 'once',
    'agent_count': 0,
    'dirty_count': $DIRTY,
    'unpushed_count': $UNPUSHED
}
print(json.dumps(data))
"
