---
name: orchestrator
description: Alias of /meta-orchestrator — identical command (pure redirect: `Execute /meta-orchestrator $ARGUMENTS`). /orchestrator and /meta-orchestrator are the SAME skill — invoke either, there is nothing to choose between them.
argument-hint: <intent | plan-path>
allowed-tools: [Skill, Read, Bash, Glob, Grep]
model: opus
---

# /orchestrator → /meta-orchestrator (alias — same command)

`/orchestrator` and `/meta-orchestrator` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-orchestrator` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-orchestrator.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
