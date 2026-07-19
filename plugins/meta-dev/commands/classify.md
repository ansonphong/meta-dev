---
name: classify
description: "Alias of /meta-classify — identical command (pure redirect: `Execute /meta-classify $ARGUMENTS`). /classify and /meta-classify are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: <task-description | plan-path>
allowed-tools: [Skill, Read, Bash, Glob, Grep]
model: opus
---

# /classify → /meta-classify (alias — same command)

`/classify` and `/meta-classify` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-classify` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-classify.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
