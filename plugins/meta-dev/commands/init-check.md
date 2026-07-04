---
name: init-check
description: Alias of /meta-init-check — identical command (pure redirect: `Execute /meta-init-check $ARGUMENTS`). /init-check and /meta-init-check are the SAME skill — invoke either, there is nothing to choose between them.
argument-hint: [--quick | --full]
allowed-tools: [Skill, Read, Bash, Glob, Grep]
model: opus
---

# /init-check → /meta-init-check (alias — same command)

`/init-check` and `/meta-init-check` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-init-check` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-init-check.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
