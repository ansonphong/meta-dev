---
name: review-batch
description: Alias of /meta-review-batch — identical command (pure redirect: `Execute /meta-review-batch $ARGUMENTS`). /review-batch and /meta-review-batch are the SAME skill — invoke either, there is nothing to choose between them.
argument-hint: [--since <ref> | --all]
allowed-tools: [Skill, Read, Bash, Glob, Grep, Agent]
model: opus
---

# /review-batch → /meta-review-batch (alias — same command)

`/review-batch` and `/meta-review-batch` are the SAME command — an alias pair. **Invoke the `meta-dev:meta-review-batch` skill via the Skill tool** with `$ARGUMENTS`, then follow its protocol.

Do NOT `grep`/`find`/`Read` any `.md` file to “load the protocol” — the Skill tool injects it for you. If (and only if) the Skill tool is genuinely unavailable, read exactly `${CLAUDE_PLUGIN_ROOT}/commands/meta-review-batch.md` — the installed copy — never a path found via `find`/`grep`, which may be a stale duplicate or the plugin’s source-tree clone.
