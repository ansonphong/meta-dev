#!/usr/bin/env bash
set -euo pipefail
# Dashboard data gatherer — deterministic, no LLM. Outputs JSON to stdout.
# Run from project root. Reads plans/, git, state, inbox.

# Project name from directory or git
PROJECT=$(basename "$(pwd)")
GIT_REPO=$(git remote get-url origin 2>/dev/null | sed 's/.*[:/]\(.*\)\.git/\1/' || echo "$PROJECT")

# Plans: scan active plan units (dirs with a master plan, plus loose top-level
# plan files) and derive progress from task checkboxes. This is authoritative —
# the ledger itself — rather than parsing STATUS.md prose. Active-first, capped.
PLANS_JSON="[]"
if [ -d plans ]; then
    PLANS_JSON=$(python3 -c "
import json, os, re, glob
ROOTS = ['app', 'www', 'gallery', 'meta']
EXCL = ('_archive', '_future', '_research', '_dashboard')
CHECKBOX = re.compile(r'^\s*[-*]\s*\[([ xX])\]')  # anchored: skips inline prose

def excluded(path):
    parts = path.replace('\\\\', '/').split('/')
    return any(e in parts for e in EXCL)

units = []  # (display_name, file_to_count)
for r in ROOTS:
    base = 'plans/' + r
    if not os.path.isdir(base):
        continue
    for pat in ('00-master-plan.md', '*master-plan*.md'):
        for mp in glob.glob(base + '/**/' + pat, recursive=True):
            if not excluded(mp):
                units.append((os.path.basename(os.path.dirname(mp)), mp))
    for f in glob.glob(base + '/*.md'):
        if os.path.basename(f) not in ('STATUS.md', 'exec-order.md', 'README.md'):
            units.append((os.path.splitext(os.path.basename(f))[0], f))

seen, plans = set(), []
for name, f in units:
    if f in seen:
        continue
    seen.add(f)
    done = todo = 0
    try:
        with open(f, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                m = CHECKBOX.match(line)
                if m:
                    if m.group(1) in 'xX':
                        done += 1
                    else:
                        todo += 1
    except Exception:
        pass
    total = done + todo
    if total == 0 or done == 0:
        status = 'pending'
    elif todo == 0:
        status = 'done'
    else:
        status = 'inflight'
    nm = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', name)[:24]
    plans.append({'name': nm, 'tasks_done': done, 'tasks_total': total, 'status': status})

order = {'inflight': 0, 'blocked': 1, 'pending': 2, 'done': 3}
plans.sort(key=lambda p: (order.get(p['status'], 4), -p['tasks_total']))
print(json.dumps(plans[:12]))
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
