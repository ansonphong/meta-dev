---
name: deploy-pipeline
description: Generalized deploy step for the ship pipeline. Ships one target — either push-to-branch (server auto-deploy hook) or rsync+restart over SSH, or publish a built artifact. Config-driven, no project specifics hardcoded.
---

# Deploy Pipeline

The deploy step the ship pipeline (the `meta-ship` runbook, `ship-pipeline.md`) delegates to. Given a
single resolved target profile, it makes the new code live and reports a structured
result. It performs **deploy mechanics only** — pre-flight, version bump, post-deploy
verification, and canary are the caller's job (the ship pipeline).

All specifics come from the target profile passed in (host, path, restart command,
branch, artifact paths). Nothing here is project-specific.

## Inputs

Resolved from `meta_dev.ship.targets.<name>` by the caller:

- `kind` — `server` or `artifact`
- `repo_path` — working directory
- `branch` — branch to ship from (default `main`)
- `deploy.host` / `deploy.path` / `deploy.restart_cmd` — server targets
- artifact path + publish command — artifact targets

## Deploy Modes

Pick the mode that matches the target's config:

### Mode A — push-to-branch (hook auto-deploy)
The remote has a deploy hook that ships on push. The skill only needs to land commits on
the branch.

```bash
cd "$REPO_PATH"
git branch --show-current        # must equal $BRANCH, else STATUS: WRONG_BRANCH
git push origin "$BRANCH"        # never --force, never --no-verify
# rebase-and-retry once if remote is ahead:
#   git pull --rebase origin "$BRANCH" && git push origin "$BRANCH"
git log "origin/$BRANCH" -1 --oneline   # confirm new HEAD landed
```

### Mode B — rsync + restart (SSH)
No hook; the skill copies the build and restarts the service.

```bash
# 1. Sync (exclude VCS + local junk; --delete to mirror)
rsync -az --delete \
  --exclude '.git' --exclude '__pycache__' --exclude 'node_modules' \
  "$REPO_PATH/" "root@${DEPLOY_HOST}:${DEPLOY_PATH}/"
# 2. Restart
ssh "root@${DEPLOY_HOST}" "${DEPLOY_RESTART_CMD}"   # e.g. systemctl restart myapp
```
If the restart command exits nonzero → `STATUS: RESTART_FAILED`.

### Mode C — artifact publish
A built artifact (installer/package) is uploaded/registered via the configured publish
command. Capture any returned id (release id) for the caller.

```bash
eval "$PUBLISH_CMD"   # uploads artifact + sha256; emits id on stdout
```

## Safety Rules (non-negotiable)

- Only operate inside `repo_path` / the configured `deploy.path`. Never `cd` elsewhere.
- Only ship the configured `branch`. Refuse anything else.
- **Never force-push. Never `--no-verify`. Never create branches or PRs.**
- If a pre-commit/pre-push hook fails: fix the issue and retry; do NOT bypass.
- If the diff touches secrets (`.env`, `*.pem`, `*.key`, `credentials*`, `secrets*`) →
  `STATUS: SAFETY_ABORT`.
- Migrations are gated by the **caller** (ship pipeline Step 3b); this skill does not
  apply schema changes on its own initiative.

## Return Format

Return a single structured block, nothing else:

```
TARGET: <name>
MODE: push | rsync | artifact
STATUS: OK | WRONG_BRANCH | SAFETY_ABORT | PUSH_FAILED | RESTART_FAILED | PUBLISH_FAILED | OTHER_FAILURE
HEAD: <short-sha> — <subject>        # push/rsync modes
ARTIFACT_ID: <id or —>               # artifact mode
NOTES: <one-line summary or failure reason>
```

`STATUS: OK` ⇒ caller proceeds to post-deploy verification. Any other status ⇒ caller
invokes rollback guidance keyed to the `deploy` step. Keep output tight — no full
command dumps.
