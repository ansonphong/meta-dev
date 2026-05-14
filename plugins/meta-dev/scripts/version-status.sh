#!/usr/bin/env bash
set -euo pipefail
VERSIONING_FILE="plans/_dashboard/versioning.json"
[ -f "$VERSIONING_FILE" ] || { echo "No versioning.json found. Run /meta-init first."; exit 1; }

python3 -c "
import json
with open('$VERSIONING_FILE') as f:
    data = json.load(f)
print(f\"Strategy: {data.get('strategy', 'semver')}\")
for repo in data.get('repos', []):
    follows = f\" → follows {repo['follows']}\" if repo.get('follows') else ''
    print(f\"  {repo['id']}: {repo['current_version']} ({repo['name']}){follows}\")
"
