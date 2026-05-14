#!/usr/bin/env bash
set -euo pipefail
# Dashboard data gatherer — deterministic, no LLM. Outputs JSON to stdout.
# Run from project root. Reads plans/, git, state, inbox.
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

# Project name from directory or git
PROJECT=$(basename "$(pwd)")
GIT_REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*[:/]\(.*\)\.git/\1/' || echo "$PROJECT")

# Plans: parse STATUS.md for active initiatives
PLANS_JSON="[]"
if [ -f plans/STATUS.md ]; then
    PLANS_JSON=$(python3 -c "
import json, re, sys
plans = []
try:
    with open('plans/STATUS.md') as f:
        content = f.read()
    # Match lines like: - **Plan Name**: status (N/M tasks)
    # Also match: ## Plan Name or ### Active
    for line in content.split('\n'):
        line = line.strip()
        # Pattern: bullet with bold name and status
        m = re.match(r'[-*]\s+\*\*(.+?)\*\*:?\s*(.+)', line)
        if m:
            name = m.group(1).strip()
            rest = m.group(2).strip()
            # Extract status and counts
            status = 'pending'
            done = 0; total = 0
            if 'done' in rest.lower() or 'complete' in rest.lower() or 'shipped' in rest.lower():
                status = 'done'
            elif 'inflight' in rest.lower() or 'active' in rest.lower() or 'in progress' in rest.lower() or 'in-flight' in rest.lower():
                status = 'inflight'
            elif 'blocked' in rest.lower():
                status = 'blocked'
            # Extract N/M if present
            nm = re.search(r'(\d+)/(\d+)', rest)
            if nm:
                done = int(nm.group(1))
                total = int(nm.group(2))
            plans.append({'name': name, 'tasks_done': done, 'tasks_total': total, 'status': status})
except Exception:
    pass
print(json.dumps(plans))
" 2>/dev/null || echo "[]")
fi

# Exec order: current position
EXEC_POS=""
if [ -f plans/exec-order.md ]; then
    EXEC_POS=$(head -20 plans/exec-order.md 2>/dev/null | grep -i "current\|next\|now" | head -1 | sed 's/^#*\s*//' | cut -c1-80 || echo "")
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

# Output full JSON
python3 -c "
import json, sys, os
data = {
    'project': '$GIT_REPO',
    'plans': json.loads('''$PLANS_JSON'''),
    'exec_position': '$EXEC_POS',
    'active_sessions': json.loads('''$SESSIONS'''),
    'inbox': {
        'advisories': $INBOX_ADVISORIES,
        'issues_open': $INBOX_OPEN,
        'auto_clearable': $INBOX_AUTO
    },
    'sweep_log': json.loads('''$SWEEP_JSON'''),
    'recent_commits': json.loads('''$COMMITS_JSON'''),
    'refresh_rate': 'once',
    'agent_count': 0,
    'dirty_count': $DIRTY,
    'unpushed_count': $UNPUSHED
}
print(json.dumps(data))
"
