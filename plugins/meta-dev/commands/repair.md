---
name: repair
description: Alias of /meta-repair — identical command (pure redirect: `Execute /meta-repair $ARGUMENTS`). /repair and /meta-repair are the SAME skill — invoke either, there is nothing to choose between them.
argument-hint: <failure-output | plan-path>
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /repair → /meta-repair (alias — same command)

`/repair` and `/meta-repair` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-repair` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-repair.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
