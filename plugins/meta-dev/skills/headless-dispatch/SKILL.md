---
name: headless-dispatch
description: "Dispatch a Claude Code headless worker from a non-Claude harness such as Codex or Grok. Covers the Codex sandbox network precondition, doctor preflight, and shell invocation form. Use when asked to hand a task to a Claude model from Codex."
allowed-tools: [Read, Bash, Glob, Grep]
---

# headless-dispatch — spawn a Claude worker from Codex

`claude-headless-exec` is a plain bash script. You have a shell, so you can run
it.

## Preflight — check this first, once per session

    bash <plugin-root>/scripts/codex-doctor.sh

The doctor checks the plugin cache, local tooling, credentials, and two sandbox
preconditions — **network egress** and **`.git` writability**. Continue only when
both pass.

### `.git` writability — the second sandbox precondition

Codex `workspace-write` treats `.git` as a **protected path**: read-only,
recursively, even inside an otherwise-writable root (upstream default,
documented under "Protected paths in writable roots"). A worker in that sandbox
cannot honor COMMIT-ON-RED, so its edits sit unowned until a peer's broad
`git add` adopts them.

Probe directly with `test -w "$(git rev-parse --absolute-git-dir)"`.

**If it is read-only, fix the sandbox — never the brief.** Telling workers to
"run no git commands, the conductor commits" is a per-backend exemption written
into prose; it carries no scope marker and leaks onto backends it never applied
to (it did exactly that on 2026-07-20, reaching Claude workers that could commit
fine). Instead:

- **Per-invocation, preferred when you control the launch:**
  `-c 'sandbox_workspace_write.writable_roots=["<abs>/.git"]'`
- **Permanent:** add the repo's `.git` to `[sandbox_workspace_write]
  writable_roots` in `~/.codex/config.toml`. Unlike `network_access = true`,
  this is **path-scoped** — list specific repos, never a wildcard — so it grants
  nothing outside the repos you name. Still Phong's call to make.

`codex-headless-exec` already grants this per-run, so a failure here means you
are on a launch path that bypasses it: **interactive `codex`, a bare
`codex exec`, or a fresh machine with no global config.**

The direct network probe is:

    curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://api.anthropic.com/v1/models

`000` means your sandbox blocks DNS and every worker will die at `rc=6`.
**STOP; do not dispatch a worker from this session.** An already-running blocked
session cannot grant itself network access. Choose a policy and restart Codex:

- Prefer a narrow launch override when you control the Codex invocation:
  `-c sandbox_workspace_write.network_access=true`. This grants network access
  only to that invocation.
- Never edit global `~/.codex/config.toml` without Phong's explicit approval.
  A global `[sandbox_workspace_write] network_access = true` permanently weakens
  every workspace-write Codex session on this machine, across every project.

Do not attempt to work around the sandbox from the blocked session.

## Backends and flags

`skills/headless-worker/SKILL.md` covers general headless-execution principles
only. The authoritative backend, tier, selection, and flag guidance is:

    bash <plugin-root>/scripts/claude-headless-exec --help

## Invoke

    bash <plugin-root>/scripts/claude-headless-exec \
      --backend opus \
      --repo app \
      --effort high \
      '<complete, self-contained task spec with acceptance criteria>'

The worker shares no context with you: give it a complete, self-contained task
specification with acceptance criteria.
