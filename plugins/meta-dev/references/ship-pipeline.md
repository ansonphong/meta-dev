# Ship Pipeline — Unified Release Protocol

Orchestrate the full release of a repo from pre-flight through deploy and post-deploy
verification, chaining version bump → build → test → deploy → verify into a **gated**
pipeline where each step must pass before the next begins.

Ship **gates and reports** — a failing step halts the pipeline. Nothing about a specific
project is hardcoded here: targets, hosts, restart commands, health URLs, smoke tests,
build/test commands, and prerelease channels all come from config. Read everything from
`bash scripts/config-get.sh meta_dev.ship`.

The actual deploy mechanics live in `skills/deploy-pipeline/SKILL.md` — when this protocol
says "delegate to the deploy skill," invoke that skill. It is real and resolvable.

---

## Config Surface

| Key | Meaning |
|-----|---------|
| `meta_dev.ship.default_target` | Target selected when no `<target>` arg is given |
| `meta_dev.ship.targets.<name>` | A named release target profile |
| `meta_dev.ship.targets.<name>.kind` | `artifact` (build+publish an installer/package) or `server` (deploy a running service) |
| `meta_dev.ship.targets.<name>.repo_path` | Working directory for this target |
| `meta_dev.ship.targets.<name>.branch` | Required branch for release (default `main`) |
| `meta_dev.ship.targets.<name>.version_repo_id` | `versioning.json` repo id to bump (null = skip version stage) |
| `meta_dev.ship.targets.<name>.test_cmd` | Pre-flight test command(s); array, each must exit 0 |
| `meta_dev.ship.targets.<name>.build_cmd` | Build/package command (artifact targets) |
| `meta_dev.ship.targets.<name>.deploy` | `{host, path, restart_cmd}` (server targets) — drives the deploy skill |
| `meta_dev.ship.targets.<name>.health` | `{url, expected_status, expected_body}` post-deploy verification gate |
| `meta_dev.ship.targets.<name>.smoke_tests[]` | List of `{name, url, method, expected_status, expected_body}` smoke checks |
| `meta_dev.ship.targets.<name>.migration` | `{check_cmd, upgrade_cmd, downgrade_cmd}` (null = no DB migrations) |
| `meta_dev.ship.targets.<name>.canary_target` | `meta_dev.canary.targets.<name>` profile to monitor after deploy (null = skip) |
| `meta_dev.ship.preflight.require_clean_tree` | Working tree must be clean (default true) |
| `meta_dev.ship.preflight.require_on_branch` | Must be on the target's `branch` (default true) |
| `meta_dev.ship.preflight.require_no_index_lock` | `.git/index.lock` must be absent (default true) |
| `meta_dev.ship.preflight.run_tests` | Run `test_cmd` during pre-flight (default true) |
| `meta_dev.ship.migration_gate` | Require human confirmation of pending migrations (default true) |
| `meta_dev.ship.token_budget.commit_count` | Release-notes commit ceiling before diff-stat-only mode (default 200) |
| `meta_dev.ship.token_budget.context_bytes` | Release-notes byte ceiling before diff-stat-only mode (default 80000) |
| `meta_dev.ship.channels` | Ordered prerelease channels (e.g. `["alpha","beta","production"]`; null = single-channel) |
| `meta_dev.ship.lockfile` | Path to the concurrency lock (default `plans/_dashboard/.ship.lock`) |

Resolve the active target: use `<target>` arg if present, else `default_target`. Unknown
name → list available profiles and exit.

---

## Lifecycle State

A release is a multi-step transaction. State lives in a per-target run record
(`plans/_dashboard/.ship-state.<target>.json`) written after each completed step so
`--resume` knows where to pick up. Minimum shape:

```json
{ "target": "<name>", "version": "1.4.0", "channel": "production",
  "steps_done": ["preflight","version","build","tag","deploy"], "last_step": "deploy",
  "started": "ISO-8601", "release_id": null }
```

A run is **clean** (no state file) → starts at pre-flight. A run with state → `--resume`
continues from `last_step + 1`; a fresh invocation on an existing state warns and offers
`--resume` / `--abort` / `--reset`.

---

## Step 0: Parse Arguments & Flags

Argument string: `$ARGUMENTS`. The non-flag token is the target.

| Flag | Effect |
|------|--------|
| `--dry-run` | Run pre-flight checks only, then stop and report. No version bump, build, deploy, push, or API calls. |
| `--resume` | Continue an interrupted run from its recorded `last_step`. Skips already-done steps. |
| `--abort` | Cancel an in-progress run that has NOT yet created a git tag or deployed: clear state file, remove any draft artifacts, release the lock. If a tag exists or a deploy completed, FAIL LOUD: "use `--reset <version>`". |
| `--reset <version>` | Full teardown for a version: delete local tag, delete local build artifacts, delete any draft, clear state, release lock, and (server) note that a deployed version cannot be auto-reset — surface manual rollback. **Confirmation-gated** (user must type `reset <version>`). |
| `--hotfix` | Bypass prerelease channel sequencing: bump patch on the most recent production tag and go straight to the `production` channel. Requires explicit confirmation. |

Handle `--abort` / `--reset` **before** anything else (they are teardown paths, not pipeline runs).

## Step 0.5: Read Learned Patterns

Read the `## Learned Patterns` section at the bottom of THIS file. Each pattern is a
generalized rule discovered from recurring release issues (often patched by meta-canary
after post-deploy failures). Apply each as an **additional pre-flight check or
verification step**, honoring its `Applies to:` field. Record which patterns were active
in the ship log.

## Step 0.6: Concurrency Lock

One release at a time. Check `meta_dev.ship.lockfile`:

```bash
LOCK="$(bash scripts/config-get.sh meta_dev.ship.lockfile)"
if [ -f "$LOCK" ] && [ "$RESUME" != "1" ]; then
  echo "BLOCKED: a release is already in progress ($(cat "$LOCK")). Use --resume, or --abort to clear."
  exit 1
fi
echo "{target} {version} $(date -u +%FT%TZ) pid:$$" > "$LOCK"
```

The lock is released on successful completion, on `--abort`, and on `--reset`. A failed
run leaves the lock in place so a stale concurrent run cannot start; `--resume` reuses it.

---

## Step 1: Pre-Flight Gate (ALL pipelines)

These checks **must ALL pass**. Any failure = stop immediately. This gate exists because
of past incidents; never skip it, even for "just a small fix."

```bash
cd "$(bash scripts/config-get.sh meta_dev.ship.targets.$TARGET.repo_path)"

# 1. Clean working tree (if require_clean_tree)
git status --porcelain        # must be empty

# 2. On the required branch (if require_on_branch)
git branch --show-current     # must equal targets.<name>.branch

# 3. No stale index lock (if require_no_index_lock)
test ! -f .git/index.lock

# 4. Test suite (if run_tests) — every test_cmd must exit 0
#    for c in targets.<name>.test_cmd[]: run c; nonzero => FAIL
```

Render a READY/BLOCKED report:

```
## Pre-Flight — {target}

| Check          | Status     | Details / Remediation |
|----------------|------------|-----------------------|
| Clean tree     | PASS/FAIL  | {dirty files} → commit or stash |
| On {branch}    | PASS/FAIL  | {current} → git checkout {branch} |
| No index lock  | PASS/FAIL  | rm -f .git/index.lock (lock only — NEVER .git/index) |
| Tests pass     | PASS/FAIL  | {N passed, M failed} → fix before shipping |

Overall: READY / BLOCKED
```

If **BLOCKED** → stop with exit code 3 (pre-flight) and the remediation list. If
`--dry-run` → stop here regardless and report pre-flight only (zero risk).

**Gate: ALL pre-flight checks pass before proceeding.**

---

## Step 2: Channel Resolution & Version Stage

Skip the version sub-steps if `version_repo_id` is null.

1. **Resolve channel.** If `meta_dev.ship.channels` is set, sequencing is enforced:
   you may only advance to channel N+1 if channel N has shipped for the current line.
   `--hotfix` bypasses this and forces `production` (patch bump on the latest production
   tag). Single-channel config (`channels: null`) always ships to the one implicit channel.
   > Note: version-manager has no channel concept — channel is a ship-layer prerelease
   > strategy. The channel is encoded as a suffix on the bumped version
   > (e.g. `1.4.0-alpha.1`, `1.4.0-beta.2`, `1.4.0`) and recorded in the ship state +
   > git tag; version-manager bumps the base MAJOR.MINOR.PATCH, ship appends the channel suffix.

2. **Bump.** Invoke Skill `version-manager` (or `scripts/version-bump.py --repo <id>
   --type <major|minor|patch|auto>`) to bump the base version and update all
   `version_files`. Then commit: `git commit -m "release: bump to v{version}"`.

3. **Release notes (artifact targets, optional).** Collect commits since the last tag.
   **Token-budget guard:** if `commit_count > token_budget.commit_count` OR context
   `> token_budget.context_bytes`, switch to **diff-stat-only** mode (drop per-commit
   diffs, keep `git diff --stat`) to stay within budget. For production releases that
   follow prior alpha/beta tags, fold prior-channel notes in.

4. **Annotated tag.** `git tag -a "v{version}" -F <notes>`.

**Gate: version bump committed and tag created before build/deploy.**

---

## Step 3a: Artifact Target — Build → Publish

For `kind: artifact` targets:

1. **Build** — run `build_cmd`. Capture artifact path + `sha256`.
   - Exit code `1` (recoverable) → print error, suggest `--resume` after fixing.
   - Exit code `2` (unrecoverable) → print error, suggest `--reset <version>` + human investigation.
2. **Publish** — upload/register the artifact via the project's publish mechanism
   (the deploy skill's `artifact` path, or a configured publish command). Record any
   returned `release_id` in the ship state.
3. **Push** — `git push origin {branch} && git push origin v{version}`.

**Gate: build exits 0 and publish succeeds before push.** Skip entirely under `--dry-run`.

## Step 3b: Server Target — Migration Gate → Deploy

For `kind: server` targets:

1. **Migration review gate** (if `migration` is set AND `migration_gate` is true):
   ```bash
   eval "$MIGRATION_CHECK_CMD"   # e.g. flask db heads && flask db current
   ```
   List pending migrations. If any are pending, **require explicit confirmation** that
   they are safe before proceeding. Destructive/irreversible migrations should be called
   out. **Gate: user confirms migrations are safe.** If `migration.upgrade_cmd` is set,
   run it as part of deploy (after confirmation).

2. **Deploy** — delegate to **Skill `deploy-pipeline`** with the target's `deploy`
   config (`host`, `path`, `restart_cmd`) and `branch`. The skill performs the
   commit/push (or rsync) + service restart. **Gate: the deploy skill must report
   `STATUS: OK` (exit 0).** Skip under `--dry-run`.

---

## Step 4: Post-Deploy Verification Gate

A GATE, not a courtesy check. Skip under `--dry-run`.

1. **Health endpoint:**
   ```bash
   curl -s -o /tmp/body -w "%{http_code}" --max-time 10 "$HEALTH_URL"
   ```
   - HTTP code must equal `health.expected_status`.
   - If `health.expected_body` is set, the response body must contain it.
2. **Smoke tests** — for each `smoke_tests[]` entry, hit `url` with `method`, assert
   `expected_status` (and `expected_body` if set). Emit PASS/FAIL per check.
3. **Key user flow** — at least one smoke test should exercise a real flow (auth,
   feed, render trigger) rather than only a static health route.

```
## Post-Deploy Verification — {target}

| Check        | Result | Detail            | Status |
|--------------|--------|-------------------|--------|
| Health       | 200    | body matched      | PASS   |
| Smoke: login | 200    | redirect present  | PASS   |
| Smoke: feed  | 500    | unexpected error  | FAIL   |

Overall: PASS / FAIL
```

**Gate: health returns expected status + body AND all smoke tests PASS.** Any FAIL →
treat as a deploy failure and go to Rollback (Step 6).

---

## Step 5: Post-Deploy Monitoring (server targets)

If `canary_target` is set, chain `meta_dev.canary` against that profile (see
`references/canary-protocol.md`). The canary runs its monitoring window and **folds its
report into this ship summary** rather than writing a separate file. A canary ALERT is a
post-deploy regression → surface rollback guidance from Step 6.

---

## Step 6: Rollback Guidance (on ANY failure after pre-flight)

Rollback guidance is **mandatory** on failure — never leave the user wondering how to
recover. Key the guidance off **which step failed** (read `last_step` from ship state):

```
## Release/Deploy FAILED at {step} — {target}

What happened:     {error description}
What completed:    {steps_done list}
What needs rollback: {derived from the step}

Rollback steps:
1. {specific instruction}
2. {specific instruction}
```

**Failure-keyed rollback matrix:**

| Failed at | What completed | Rollback |
|-----------|---------------|----------|
| `preflight` | nothing | None needed. Fix remediation items, re-run (exit 3). |
| `version` | bump committed, maybe tagged | `git revert` the bump commit; `git tag -d v{version}` if tagged. Exit 1 → `--resume` after fix. |
| `build` (artifact) | tag created, no upload | Delete local build artifacts. Exit 1 recoverable → `--resume`; exit 2 → `--reset {version}`. |
| `publish` (artifact) | built, partial upload | Manually clean partial remote artifacts/manifest; the publish path is idempotent on `--resume`. |
| `migration` (server) | none, or migration applied | If `migration.downgrade_cmd` is set and the migration applied, run it to downgrade. Do NOT deploy on an unconfirmed schema. |
| `deploy` (server) | migration applied, deploy partial | Previous version should still be running. If migration applied but deploy failed, run `migration.downgrade_cmd`. Re-run deploy via `--resume`. |
| `verify` (server) | deployed, health/smoke FAIL | Redeploy the prior release (deploy skill against the previous tag), then `migration.downgrade_cmd` if the new schema is implicated. This is the highest-severity path. |
| `canary` (server) | deployed + verified, regression in window | Same as `verify` rollback — redeploy prior release; investigate logs (see canary ALERT actions). |

**Artifact rollback:** version bump reverts with `git revert`; build artifacts are
deletable; a partially-uploaded manifest needs manual cleanup (or `--reset <version>`).
**Server rollback:** if deploy failed the previous version is usually still live; applied
migrations may need `flask db downgrade` (or the configured `downgrade_cmd`); use the
deploy skill to redeploy the prior tag.

---

## Exit-Code Tiers

| Code | Tier | Meaning | Recovery |
|------|------|---------|----------|
| `0` | success | Pipeline completed; lock released; state cleared. | — |
| `1` | recoverable | A step failed in a way that's fixable in place (build flake, transient network, lint). State preserved. | `--resume` after fixing |
| `2` | unrecoverable | A step failed leaving inconsistent state (corrupt artifact, partial publish, bad migration). | `--reset <version>` + human investigation |
| `3` | preflight | A pre-flight gate blocked the run before any mutation. No state written. | Fix remediation, re-run |

---

## Ship Log

Emit a ship-log entry at the end of every run (success or failure) to the conversation.
Schema:

```markdown
## Ship Log — {YYYY-MM-DD HH:MM}

**Repo / target:** {target}
**Version / channel:** {version} / {channel}
**Commits shipped:** {git log summary since prior tag}
**Pre-flight:** PASS / BLOCKED ({details})
**Deploy / Release:** SUCCESS / FAILED@{step}
**Health:** PASS / FAIL ({status}, body matched)
**Canary:** PASS / SKIPPED / FAIL
**Patterns active:** {LP-NNN... or "none"}
```

---

## Operational Rules

1. **Never skip pre-flight.** It exists because of past incidents.
2. **Gates are non-negotiable.** A failing step halts the pipeline. Do not continue past a known failure.
3. **Dry-run when unsure.** `--dry-run` runs pre-flight only — zero risk.
4. **Commit before release.** The working tree must be clean; uncommitted changes are not in the release.
5. **One release at a time.** Honor the concurrency lock.
6. **Rollback guidance is mandatory on failure**, keyed off the failed step.
7. **Channels are sequenced** (alpha → beta → production) unless `--hotfix` or single-channel config.

---

## Skill-Output Schema Validation

When the version-manager or release-notes skill returns structured output, **validate the
schema before using it** (required keys present, parseable JSON, no surrounding markdown,
length bounds honored). **On schema failure, re-invoke ONCE** with a corrective prompt
("Re-emit strict JSON only with keys: ..."). After a second failure, abort the stage and
surface to the user. Never proceed on malformed skill output.

---

## Learned Patterns

<!-- Auto-maintained by the improvement loop. Generalized only — no project-specific entries. -->
<!-- Max 20 patterns. meta-audit enforces the cap via consolidation. -->
<!-- meta-canary detects recurring post-deploy failures and patches this section (canary Step 6). -->
<!-- Read these at Step 0.5 and apply each as an extra pre-flight/verification check. -->
<!-- Only meta-audit may remove patterns; all other commands are append-only. -->
