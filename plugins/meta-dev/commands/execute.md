---
name: execute
description: "Alias of /meta-execute — identical command (pure redirect: `Execute /meta-execute $ARGUMENTS`). /execute and /meta-execute are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: <plan-path> [--inline] [--strict] [--deploy] [--pause-before=<task-id>]
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /execute → /meta-execute (alias — same command)

`/execute` and `/meta-execute` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-execute` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-execute.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
