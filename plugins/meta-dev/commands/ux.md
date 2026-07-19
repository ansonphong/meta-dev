---
name: ux
description: "Alias of /meta-ux — identical command (pure redirect: `Execute /meta-ux $ARGUMENTS`). /ux and /meta-ux are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: "[plan-path | \"running app\" | feature:<name> | <repo>] [--depth shallow|standard|deep] [--focus <area>] [--rounds N]"
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /ux → /meta-ux (alias — same command)

`/ux` and `/meta-ux` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-ux` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-ux.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
