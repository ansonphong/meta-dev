# Meta-Dev Plugin — Development Guide

## Repository contract

This file is the complete, canonical doctrine for this repository. Host adapters
may import it but must not repeat it. Durable project context belongs in
`docs/agent-context/`; canonical skills belong in `.agents/skills/`; vendor
directories are adapters only.

The project-contract discovery order is root `AGENTS.md`, routed durable
context, canonical skills, then vendor adapters. Legacy root `CLAUDE.md` and
`.claude/CLAUDE.md` are compatibility inputs only. Report them for migration;
do not emit them as the preferred contract.

## Version and release rule

Every plugin change intended for marketplace users needs a patch bump in both
plugin manifests, followed by a commit and push to `origin/main`. The manifest
base versions must match.

## Structure

Everything editable is under `plugins/meta-dev/`. Commands are thin entry
points; skills hold reusable procedures; scripts hold deterministic operations;
schemas hold JSON contracts; templates hold bootstrap files; references hold
package documentation. Do not search for these directories at repository root.

## Principles

1. Prefer skills to commands for reuse.
2. Prefer scripts to LLMs for deterministic work.
3. Prefer event-driven work to polling.
4. Keep customization in JSON with schemas.
5. Keep the plugin project-agnostic. Do not hardcode host names, paths,
   domains, stacks, brands, endpoints, or platform assumptions.

## Project information contract

Project-specific structured settings use the JSON cascade: plugin defaults,
project `plans/_dashboard/settings.json`, then local overrides. Project prose
rules come from the discovered root `AGENTS.md` and routed durable context. If
the needed fact is absent, use a safe portable default, then ask.

## State layer

Markdown plans are git truth. The disposable SQLite read-model is a cache.
`planctl` is the only state write door. Invoke it through:

```bash
bash plugins/meta-dev/scripts/planctl.sh <verb> [--json]
```

## Testing and git discipline

Use focused checks during task work and report actual output. Use explicit paths
for staging and commits. Never use tree-wide staging, stash, reset, restore,
clean, rebase, or non-fast-forward merge. In a shared worktree, commit with:

```bash
git -C <absolute-repository-root> commit --only -m "type: summary" -- <paths>
```

## Conventions

- Use `${PLUGIN_ROOT}` or `${META_DEV_PLUGIN_ROOT}` for plugin-relative paths.
- Use `${PROJECT_ROOT}` or `plans/` for project-relative paths.
- Use conventional commit prefixes such as `feat:`, `fix:`, `chore:`, and `docs:`.
- Commands are small adapters. Procedures belong in skills or references.
- Match surrounding naming and comment density. Keep writing short, direct, and
  specific.

## Compatibility adapters

The Claude adapter is `.claude/CLAUDE.md` and contains only `@../AGENTS.md`.
Other host adapters may exist in vendor directories. They may add host loading
syntax but may not become a second source of repository rules.
