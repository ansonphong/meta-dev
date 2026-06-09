# Execute Report Card — Layout Spec

The structured dashboard rendered by `/meta-execute` at completion. Follow this spec exactly — no sprawl, no conversational narration, no design-doc re-cap.

## Design Principles

- **Concise, not chatty.** The user walked away and came back. They want the score, not the play-by-play.
- **Every section mandatory.** If a section has no content, write "(none)" — never omit.
- **No emoji inside box borders.** Same rule as `dashboard-layout.md` — emoji are width-2 but many renderers draw them at 1 cell, misaligning borders. Confine emoji to the header line outside the box.
- **Width budget:** 74 columns (matches dashboard). Content lines indent 2 spaces inside the box.

## Layout

```
╔══════════════════════════════════════════════════════════════════════╗
║           /meta-execute — EXECUTION REPORT CARD                     ║
╚══════════════════════════════════════════════════════════════════════╝

  Plan:         <plan-title>
  Path:         <plan-path>
  Status:       EXECUTED + REVIEWED   (or "EXECUTED · awaiting manual gate")
  Duration:     <elapsed — e.g. 29m · 7 tasks · 90.5k tokens>

  ── Tasks ──
  ✅ <done>/<total> completed   <failed> failed   <deferred> deferred

  ── Commits (on <repo> master, all pushed) ──
  <short-sha>  <one-line description>                    <verify result>
  <short-sha>  <one-line description>                    <verify result>

  ── Code Review ──
  ✅ CLEAN — 0 findings (requesting-code-review)
  (or)
  ⚠️  <N> findings — all fixed · 0 remaining
  (or)
  ❌ <N> findings surfaced to user — see Follow-ups

  ── Acceptance ──
  pytest <pass>/<total>   vitest <pass>/<total>   check: <state>

  ── Plan Location ──
  ✅ Archived: plans/<repo>/_archive/<name>/
  (or)
  📍 Active:   plans/<repo>/<name>/   (reason: <manual gate>)

  ── Follow-ups ──
  • <item> — <action> — <owner>
  • (empty list = "(none)")
```

## Section Rules

### Plan + Status

One line each. Status uses one of:
- `EXECUTED + REVIEWED` — all tasks done, code review clean
- `EXECUTED + REVIEWED (N findings fixed)` — all tasks done, findings resolved
- `EXECUTED · awaiting manual gate` — tasks done but plan not archived (GPU acceptance, in-app verify, etc.)

### Tasks

Compact ratio line. If any tasks failed or were deferred, list them by ID:
```
✅ 6/7 completed   1 failed (Task 4: schema mismatch)   0 deferred
```

### Commits

Table format. Columns: short SHA (9 chars), description (truncated to 48 chars with `…`), verify result. One row per commit. Omit claim commits (`chore(plan): claim`). Include fixer commits.

Verify result examples: `6/6 pass`, `check clean`, `sync-verified ✓`, `12/12 pass`.

### Code Review

Always state which skill was used: `(requesting-code-review)`. Verdict on one line:
- `✅ CLEAN — 0 findings`
- `⚠️ <N> findings fixed · 0 remaining`
- `❌ <N> findings surfaced — see Follow-ups`

### Acceptance

Test suite results. Format: `<runner> <pass>/<total>`. Include lint/check state. If acceptance was skipped (manual-only gate), say so: `(manual GPU acceptance pending)`.

### Plan Location

Answer "where does the plan live NOW?":
- If archived: `✅ Archived: plans/<repo>/_archive/<name>/`
- If active: `📍 Active: plans/<repo>/<name>/ (reason: <specific gate>)`

Reasons must be specific: "manual GPU acceptance pending", "awaiting user verification of X in-app", "deploy gate not yet triggered". Never use vague reasons.

### Follow-ups

Structured list. Each item format: `• <what> — <action needed> — <owner>`. Include:
- Manual acceptance gates
- Unarchived plans + reason
- Findings surfaced from code review (file:line)
- Deploy prompts
- Any deferred or failed tasks

Owner is `you` (the user), `me` (the session), or a specific role. If list is empty, write `(none)`.

## Anti-Sprawl Rules

1. **Do NOT re-describe the plan.** The report card is an execution summary, not a design doc. The plan title + path is enough.
2. **Do NOT narrate what you did step-by-step.** The commit table IS the narrative.
3. **Do NOT repeat the code review findings verbatim** unless surfaced to the user. "0 findings" is enough when clean.
4. **Do NOT add a conversational sign-off.** The report card IS the sign-off. No "Done!", "Let me know if...", "Ready for...".
5. **One report card per run.** No incremental summaries after each phase — the report card appears once at the very end.
