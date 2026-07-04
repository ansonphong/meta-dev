---
name: security
description: Alias of /meta-security — identical command (pure redirect: `Execute /meta-security $ARGUMENTS`). /security and /meta-security are the SAME skill — invoke either, there is nothing to choose between them.
argument-hint: "[<repo> | <path>] [--scope auth|payment|all] [--fix]"
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /security → /meta-security (alias — same command)

`/security` and `/meta-security` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-security` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-security.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
