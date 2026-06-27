---
name: agentic-exec-loop
description: The shared execute→review→fix loop for headless plan execution. A fresh worker per task (DeepSeek default via claude-headless-exec, GLM/Codex on flag/escalation) executes and self-runs its task Verify hook; review gates at the PHASE boundary (not per task) via the meta-dev:review-agent Opus subagent, which computes its own git diff and returns a verdict; a fixer worker repairs on non-pass (deep→glm ladder). Only N worker lines + one phase verdict return to the conductor — diffs never enter the main thread. Used by /meta-execute --deep|--glm|--codex and /auto-execute. Protocol: references/loop-protocol.md.
---

# Agentic Execute → Review → Fix Loop

Conductor stays thin — task list + one verdict per phase. All heavy reading
(worker output, git diffs, review prose) happens inside dispatched agents and
headless worker processes. See references/loop-protocol.md.
