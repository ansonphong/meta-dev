---
name: guard
description: Alias of /meta-guard — identical command (pure redirect: `Execute /meta-guard $ARGUMENTS`). /guard and /meta-guard are the SAME skill — invoke either, there is nothing to choose between them.
argument-hint: [enable | disable | status | scope <path>]
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep]
model: opus
---

# /guard → /meta-guard (alias — same command)

`/guard` and `/meta-guard` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-guard` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-guard.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
