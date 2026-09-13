# Execution briefs

Routing: `references/work-ladder.md`. Ownership and depth:
`references/adaptive-workflow.md`. Shared brief:
`references/execute-dispatch.md`.

Use direct, bounded tasks on every backend. Inline only relevant task excerpts,
contracts, file paths, acceptance criteria, and inspected revision. A coherent
slice may include multiple handles, each with its own acceptance record.
Collect/inventory work needs a question and return format, not a harness manual.
Do not force every backend into a different prose style without measured need.

Headless runners inject their tool/host constraints through
`scripts/lib/execute-brief.sh`. Model and effort must be supported by that
runner. Host-native delegation uses the available native surface, not assumed
Claude syntax. Never send a Claude slash command to a Codex/Grok/Cursor/Antigravity headless worker.

For write work include the exact repository root, declared paths, focused
verification, shared-worktree rules, and explicit-path commit form. Workers
never push; the conductor owns authorized remote synchronization. Read-only
review does not permit source edits or a commit.

A campaign member worker coordinates one plan using `commands/meta-execute.md`;
it is not permission for unbounded nested agents. Share the host-wide worker cap
across member conductors, task/slice workers, and fixers. Use `planctl` for state.
