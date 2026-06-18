---
name: meta-compact
description: Forward-moving compaction — write a durable handoff at a clean seam so the post-compaction session resumes the exact next step instead of being left hanging. Does not run /compact; produces the handoff and hands the trigger back.
argument-hint: [--check | --now]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
model: opus
---

# /meta-compact

Invoke the `meta-compact` skill to produce a **forward handoff** before compaction.

## Behavior

1. Check the seam (clean boundary + committed state). If not safe, report the one thing to finish first — do NOT write a handoff against dirty mid-task state.
2. Capture git state, distill this session's decisions/gotchas, write the forward handoff.
3. Write a **unique** `handoff-<YYYY-MM-DD>-<HHMM>.md` **in the active plan's folder** (auto-detected, or `--plan <path>`). Never overwrite — one file per compaction, full history kept per plan.
4. Echo a 4-line preview + the exact handoff path, and hand the `/compact` trigger back to the user.

## Flags

- `--check` — only assess whether now is a clean boundary; report verdict, write nothing.
- `--now` — skip the proactive offer; write the handoff immediately (still refuses on dirty mid-task state).
- `--plan <path>` — write the handoff into `<path>` (a plan folder) instead of auto-detecting the active one.

## Resume contract

After compaction, the next session's first action is: read the **exact handoff path** from the compact instruction (or the newest `handoff-*.md` in the active plan folder), then execute its **▶ NEXT ACTION**.

Detail: skill `meta-compact` in `plugins/meta-dev/skills/meta-compact/`.
