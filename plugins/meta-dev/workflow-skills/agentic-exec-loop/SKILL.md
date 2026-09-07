---
name: agentic-exec-loop
description: "Shared host-neutral execute-review-fix loop with adaptive ownership, focused causal verification, durable commits, and native review."
---

# Agentic Execute → Review → Fix Loop

Read `../../references/workflows/protocol.md` and
`../../references/adaptive-workflow.md`. Follow
`../../commands/meta-execute.md` for task/slice scheduling and acceptance.

Native review is the default; external reviewers are opt-in. Keep a separate
result per handle even when one worker owns a coherent slice.
At committed seams use the session-bound context watchdog described in
`references/loop-protocol.md`; unsupported telemetry is UNKNOWN, not a reason
to inspect another session or invent a compaction threshold.
