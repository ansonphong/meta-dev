---
name: agentic-exec-loop
description: "The shared host-neutral execute→review→fix loop: fresh scoped workers, focused causal verification, durable commits, and one native phase review."
---

# Agentic Execute → Review → Fix Loop

Conductor stays thin — task list + one verdict per phase. All heavy reading
(worker output, git diffs, review prose) happens inside dispatched agents and
headless worker processes. See references/loop-protocol.md.

Read `../../references/workflows/protocol.md` first. The native reviewer is
selected by the host adapter: Codex defaults to configured Sol/high; Claude Code
keeps its configured reviewer. External reviewers are explicit opt-ins.

On long playbooks the conductor runs a **context watchdog** at each phase seam
(`scripts/context-gauge.py`, default 300000 tokens): when its own context goes
`OVER`, it pauses at that committed boundary and invokes `/meta-compact` to
compact forward before the harness's hard auto-compact fires — then resumes at
the next phase. Protocol: references/loop-protocol.md → "Context watchdog".
