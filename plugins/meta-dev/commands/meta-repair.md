---
name: meta-repair
description: Invoke repair-loop skill — diagnose a failure, propose smallest fix, iterate until passing
argument-hint: <failure-description-or-path-to-failure-log>
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-repair

Diagnose + fix loop. Invokes `repair-loop` skill which:

1. Reads failure output (test trace, compile error, runtime stack)
2. Delegates to `failure-analyst` agent for root cause + smallest fix
3. Applies fix
4. Runs verification
5. If still failing → re-analyze, iterate (max 3 cycles)

Uses `failure-analyst` agent (`agents/failure-analyst.md`) for root-cause analysis.

## Report card

ALWAYS end with a repair report card. Chassis, glyphs, and `CARD_W` come from `references/status-cards.md` — never restate them here. One row per cycle, so an iterating repair shows what each attempt changed and whether it moved the needle:

```
┌─ /meta-repair — REPAIR REPORT ──────────────────────────────────────────
│ ⛔  Failure    test_render_lib_cards.py::test_card_row_indent
│ ✅  Cycle 1    root cause: off-by-one in indent arithmetic
│ ✅  Fix        card_row() prefix width — 1 file, 2 lines
│ ✅  Verify     164 passed / 1 skipped
└─────────────────────────────────────────────────────────────────────────
```

If the loop exhausts its 3 cycles without going green, the last row is `⛔ Unresolved after 3 cycles` plus the narrowest reproduction found — report the failure honestly, never a green card over a red suite.

Detail: skill `repair-loop` in `plugins/meta-dev/skills/repair-loop/`.
