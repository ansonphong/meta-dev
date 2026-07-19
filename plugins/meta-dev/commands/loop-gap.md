---
name: loop-gap
description: "Alias of /meta-loop-gap — identical command (pure redirect: `Execute /meta-loop-gap $ARGUMENTS`). /loop-gap and /meta-loop-gap are the SAME skill — invoke either, there is nothing to choose between them."
argument-hint: <plan-dir | feature:name | code-path | project> [--budget auto|low|medium|high] [--iterations N] [--fix-backend deep|glm|opus|sonnet|haiku|fable|inline] [--deep|--glm|--opus|--sonnet|--haiku|--fable]
allowed-tools: [Skill, Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /loop-gap → /meta-loop-gap (alias — same command)

`/loop-gap` and `/meta-loop-gap` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-loop-gap` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-loop-gap.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
