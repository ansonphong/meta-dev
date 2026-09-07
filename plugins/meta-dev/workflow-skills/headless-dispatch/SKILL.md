---
name: headless-dispatch
description: "Dispatch a Claude Code headless worker from a non-Claude harness such as Codex or Grok. Codex exposes fable-execute, opus-execute, sonnet-execute, deep-execute, and glm-execute as exact native command skills; all are one script and one --backend flag, mapped below. Use when asked to run a task on fable, opus, sonnet, deepseek, or glm from Codex, spawn a headless/background worker, or hand work off the main thread. Covers network egress, .git writability, doctor preflight, and shell invocation."
allowed-tools: [Read, Bash, Glob, Grep]
---

# headless-dispatch — spawn a Claude worker from Codex

`claude-headless-exec` is a plain bash script. You have a shell, so you can run
it.

## Preflight — check this first, once per session

    bash <plugin-root>/scripts/codex-doctor.sh

The doctor checks the plugin cache, local tooling, credentials, and two sandbox
preconditions — **network egress** and **`.git` writability**. Network access is
required for remote workers; `.git` writability is required only for authorized
implementation work that must commit, not a read-only review.

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
  writable_roots` in the Codex configuration file. Unlike `network_access = true`,
  this is **path-scoped** — list specific repos, never a wildcard — so it grants
  nothing outside the repos you name. Still the human approver's call to make.

`codex-headless-exec` already grants this per-run, so a failure here means you
are on a launch path that bypasses it: **interactive `codex`, a bare
`codex exec`, or a fresh machine with no global config.**

The direct network probe is:

    curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://api.anthropic.com/v1/models

`000` means the connectivity probe failed; inspect its error to distinguish
DNS, network policy, authentication transport, and service availability.
**STOP; do not dispatch a worker from this session.** An already-running blocked
session cannot grant itself network access. Choose a policy and restart Codex:

- Prefer a narrow launch override when you control the Codex invocation:
  `-c sandbox_workspace_write.network_access=true`. This grants network access
  only to that invocation.
- Never edit global Codex configuration without the human approver's explicit approval.
  A global `[sandbox_workspace_write] network_access = true` permanently weakens
  every workspace-write Codex session on this machine, across every project.

Do not attempt to work around the sandbox from the blocked session.

## The `*-execute` commands are one script and one flag

Claude Code exposes `/fable-execute`, `/opus-execute`, `/sonnet-execute`,
`/deep-execute` and `/glm-execute` as five slash commands. **They are not five
things.** Each is a thin wrapper that ends up at the same script with a different
`--backend`. In Codex, `$meta-dev:fable-execute` and its peers are exact native
skills that adapt these command procedures. When already inside this skill,
run the script directly:

| Claude Code command | `--backend` | Model | Reach for it when |
|---|---|---|---|
| `/fable-execute`  | `fable`  | `claude-fable-5`  | explicit user authorization |
| `/opus-execute`   | `opus`   | `claude-opus-5`   | bounded implementation slice or independent review |
| `/sonnet-execute` | `sonnet` | `claude-sonnet-5` | bounded implementation or review |
| `/deep-execute`   | `deep`   | `deepseek-v4-pro` (`--flash` / `--vision`) | selected by user or configured eligible pool |
| `/glm-execute`    | `glm`    | `glm-5.2`         | selected by user or configured eligible pool |

Resolve backend eligibility and pauses from the JSON cascade. No account-specific
quota restriction ships in the plugin. Resolve the actual executor and risk with
`scripts/workflow-policy.py` before assigning task or slice ownership. Preserve
per-task verification and progress without forcing a nested worker per checkbox.
See `references/work-ladder.md` and `references/adaptive-workflow.md`.

`sonnet`/`opus`/`fable` are **real Anthropic via your ambient Claude login** —
no API key. `deep` needs `DEEPSEEK_API_KEY`, `glm` needs `GLM_API_KEY`; the doctor
reports which are visible. Confirm actual model access, supported context size,
and billing with the target host. A separate process is not a cost guarantee.

Three commands are **not** on this script and take their own: `/codex-execute` →
`codex-headless-exec`, `/grok-execute` → `grok-headless-exec`,
`/antigravity-execute` (`/agy-execute`) → `agy-headless-exec`. Antigravity
default is Gemini 3.7 Flash (1M context, native multimodal, Search). `--opus`
there is Claude Opus 4.6 on Google quota, not Claude Code. Parked / named-only.

Full flag reference — the authoritative source, prefer it over this table when
they disagree:

    bash <plugin-root>/scripts/claude-headless-exec --help

## Invoke

    bash <plugin-root>/scripts/claude-headless-exec \
      --backend opus \
      --repo <configured-alias> \
      --effort high \
      '<complete, self-contained task spec with acceptance criteria>'

Use the plugin root supplied by the loaded skill or `META_DEV_PLUGIN_ROOT`;
do not scan versioned caches and accidentally select a different installation.
Discover repository aliases through `.meta-dev/repos.json` and the topology
helper; legacy `.claude/meta-dev-repos.json` is compatibility-only.

`--repo <alias>` takes a configured alias, not an assumed project directory.
Add `--readonly` when the worker only investigates and reports —
a read-only worker cannot write, so handing it a code-writing task fails.

The worker shares no context with you: give it a complete, self-contained task
specification with acceptance criteria. What comes back is its final text plus a
**manifest** listing exactly the files it touched.

**The worker commits its own scoped edits** — that is harness law, not a per-task
choice. Never write "run no git command, the conductor commits" into a worker
spec; if a worker genuinely cannot commit, that is an executor to fix or a
routing decision, not prose to add. See the `.git` writability section above.
