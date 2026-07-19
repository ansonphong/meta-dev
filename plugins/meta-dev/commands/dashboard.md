---
name: dashboard
description: "Alias of /meta-dashboard — identical command (pure redirect: `Execute /meta-dashboard $ARGUMENTS`). /dashboard and /meta-dashboard are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: "[SCOPE] [--commits[=N]] [--only a,b] [--no a,b] [--repo R] [--status S] [--all]"
allowed-tools: [Skill, Read, Bash, Glob, Grep]
model: opus
---

# /dashboard → /meta-dashboard (alias — same command)

`/dashboard` and `/meta-dashboard` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-dashboard` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-dashboard.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
