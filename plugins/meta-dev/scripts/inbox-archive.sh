#!/usr/bin/env bash
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
INBOX_DIR="plans/_dashboard/inbox"
INBOX_FILE="$INBOX_DIR/inbox.jsonl"
RESOLVED_DIR="$INBOX_DIR/resolved"
mkdir -p "$RESOLVED_DIR"

[ -f "$INBOX_FILE" ] || { echo "No inbox file."; exit 0; }

MONTH=$(date +%Y-%m)
ARCHIVE_FILE="$RESOLVED_DIR/${MONTH}.jsonl"

# Move resolved items >30 days old to archive
python3 -c "
import json, os, datetime

cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
keep = []
archived = 0

with open('$INBOX_FILE') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except:
            keep.append(line)
            continue

        # Keep: non-resolve events, or resolve events for items <30 days old
        if item.get('event') == 'resolve':
            resolved_dt = item.get('resolved', '')
            if resolved_dt:
                try:
                    dt = datetime.datetime.fromisoformat(resolved_dt.replace('Z', '+00:00'))
                    if dt < cutoff:
                        with open('$ARCHIVE_FILE', 'a') as af:
                            af.write(line + '\n')
                        archived += 1
                        continue
                except: pass
        keep.append(line)

# Rewrite main file with kept lines
with open('$INBOX_FILE', 'w') as f:
    for line in keep:
        f.write(line + '\n')

print(f'Archived: {archived} items → {os.path.basename(\"$ARCHIVE_FILE\")}')
"
