---
name: changelog
description: Alias of /meta-changelog — identical command (pure redirect: `Execute /meta-changelog $ARGUMENTS`). /changelog and /meta-changelog are the SAME skill — invoke either, there is nothing to choose between them.
argument-hint: add | cut | status [options]
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep]
model: opus
---

# /changelog → /meta-changelog (alias — same command)

`/changelog` and `/meta-changelog` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-changelog` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-changelog.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
