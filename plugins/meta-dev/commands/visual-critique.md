---
name: visual-critique
description: "Alias of /meta-visual-critique — identical command (pure redirect: `Execute /meta-visual-critique $ARGUMENTS`). /visual-critique and /meta-visual-critique are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: "[free-form context, e.g. \"landing page hero\" | \"mobile nav\" | \"dashboard card\"] (images attached separately)"
allowed-tools: [Skill, Read, Bash, Glob, Grep]
model: opus
---

# /visual-critique → /meta-visual-critique (alias — same command)

`/visual-critique` and `/meta-visual-critique` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-visual-critique` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-visual-critique.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
