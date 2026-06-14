---
name: sniff
description: Grug-brain sniff test — detect code smells, hacks, and bad practices in a diff/file/directory and recommend the simplest best-practice fix for each. Report-only, never edits code.
argument-hint: "[path | (empty=working diff)] [--staged] [--all]"
allowed-tools: [Read, Bash, Glob, Grep]
model: opus
---

# /sniff — grug smell your code

Invoke the **`sniff-test`** skill and run it against `$ARGUMENTS`.

- No argument → sniff the working `git diff` (changed + staged files).
- A path (file or directory) → sniff that.
- `--staged` → staged changes only. `--all` → whole repo (warn if large).

The skill detects smells across the grug taxonomy (complexity demon, bloaters, repeat-or-abstract, hacks, coupling, fear-the-spooky, chesterton fence), and for each prints **grug see / grug smell / grug say** with the simplest best-practice fix. It is **report-only** — it never edits code. Read `skills/sniff-test/references/sniff-catalog.md` for detection thresholds and `skills/sniff-test/references/sniff-report.md` for the report card layout. End with the grug Sniff Report card.

> Want smells FIXED automatically, not just reported? Use `/meta-loop-gap <path> --budget medium` (code mode) instead — that one edits.
