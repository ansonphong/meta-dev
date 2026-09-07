---
name: execute
description: Execute an approved plan with adaptive scoped ownership, focused verification, and durable commits. Requires an explicit go.
---

# Execute

Use this host-neutral workflow, not a slash-command interface. A plan is not permission: require an explicit
go for its scope; the current implementation request may already supply it.

1. Read `../../references/workflows/protocol.md` and
   `../../references/adaptive-workflow.md`.
2. Follow `../../commands/meta-execute.md` for policy resolution, scheduling,
   per-handle acceptance, and native review. Apply host-native tool equivalents.
3. Read `../../references/execute-dispatch.md` before delegating write work.
   Workers own exact-path local commits; the conductor owns planctl state.
4. Read `../../workflow-skills/agentic-exec-loop/SKILL.md` for loop routing.
   At context seams follow
   `../../workflow-skills/agentic-exec-loop/references/loop-protocol.md`.
5. Review through `../../workflow-skills/code-review-protocol/SKILL.md`.

Keep individual task visibility even when a capable worker owns a coherent
slice. Honor host delegation limits and never substitute a paid external model
without authorization. Report actual evidence and remaining acceptance gates.
