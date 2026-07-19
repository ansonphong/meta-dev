---
name: probe
description: "Alias of /meta-probe — identical command (pure redirect: `Execute /meta-probe $ARGUMENTS`). /probe and /meta-probe are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: <issue | file:line | "question"> [--budget low|medium|high|insane] [--background]
allowed-tools: [Skill, Read, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /probe → /meta-probe (alias — same command)

`/probe` and `/meta-probe` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-probe` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-probe.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
