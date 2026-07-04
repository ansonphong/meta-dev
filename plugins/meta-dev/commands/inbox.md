---
name: inbox
description: Alias of /meta-inbox — identical command (pure redirect: `Execute /meta-inbox $ARGUMENTS`). /inbox and /meta-inbox are the SAME skill — invoke either, there is nothing to choose between them.
argument-hint: [list | add | resolve <id> | dismiss <id> | clear | render]
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep]
model: opus
---

# /inbox → /meta-inbox (alias — same command)

`/inbox` and `/meta-inbox` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-inbox` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-inbox.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
