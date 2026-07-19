---
name: overlord
description: "Alias of /meta-overlord — identical command (pure redirect: `Execute /meta-overlord $ARGUMENTS`). /overlord and /meta-overlord are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: "[start | stop | status]"
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /overlord → /meta-overlord (alias — same command)

`/overlord` and `/meta-overlord` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-overlord` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-overlord.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
