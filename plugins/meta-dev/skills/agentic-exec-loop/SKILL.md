---
name: agentic-exec-loop
description: The shared execute→review→fix loop for headless plan execution. A fresh worker per task (DeepSeek default via claude-headless-exec, GLM/Sonnet-200K on flag, Codex review-only) executes and self-runs its task Verify hook; review gates at the PHASE boundary (not per task) via the meta-dev:review-agent Opus subagent, which computes its own git diff and returns a verdict; a fixer worker repairs on non-pass (tier-specific fix ladder). Only N worker lines + one phase verdict return to the conductor — diffs never enter the main thread. Used by /meta-execute --deep|--glm|--sonnet|--codex and /auto-execute. Protocol: references/loop-protocol.md.
---

# Agentic Execute → Review → Fix Loop

Conductor stays thin — task list + one verdict per phase. All heavy reading
(worker output, git diffs, review prose) happens inside dispatched agents and
headless worker processes. See references/loop-protocol.md.

On long playbooks the conductor runs a **context watchdog** at each phase seam
(`scripts/context-gauge.py`, default 300000 tokens): when its own context goes
`OVER`, it pauses at that committed boundary and invokes `/meta-compact` to
compact forward before the harness's hard auto-compact fires — then resumes at
the next phase. Protocol: references/loop-protocol.md → "Context watchdog".
