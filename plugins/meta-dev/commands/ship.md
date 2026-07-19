---
name: ship
description: "Alias of /meta-ship — identical command (pure redirect: `Execute /meta-ship $ARGUMENTS`). /ship and /meta-ship are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: <target> [--dry-run] [--resume] [--abort] [--reset <version>] [--hotfix]
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /ship → /meta-ship (alias — same command)

`/ship` and `/meta-ship` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-ship` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-ship.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
