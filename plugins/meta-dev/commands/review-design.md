---
name: review-design
description: "Alias of /meta-review-design — identical command (pure redirect: `Execute /meta-review-design $ARGUMENTS`). /review-design and /meta-review-design are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: <component-path | page-url | "current"> [--scope full|diff] [--fix] [--depth shallow|standard|deep]
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /review-design → /meta-review-design (alias — same command)

`/review-design` and `/meta-review-design` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-review-design` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-review-design.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
