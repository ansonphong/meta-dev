---
name: config
description: "Alias of /meta-config — identical command (pure redirect: `Execute /meta-config $ARGUMENTS`). /config and /meta-config are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: "[get <path> | set <path> <value> [--local] | reset | export | import <file>]"
allowed-tools: [Skill, Read, Write, Bash(bash:*)]
model: opus
---

# /config → /meta-config (alias — same command)

`/config` and `/meta-config` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-config` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-config.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
