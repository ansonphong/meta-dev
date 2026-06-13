# Loop-Gap Report Card — Layout Spec

The structured dashboard rendered by `/meta-loop-gap` at completion. Mirrors `execute-report-card.md` so a hardening pass reads like an execution pass. Follow this spec exactly — no sprawl, no per-wave narration, no re-cap of the plan/design.

## Design Principles

- **Concise, not chatty.** The user walked away and came back. They want the verdict — what got hardened, what was committed, what (if anything) is left — not the play-by-play of 40 agents.
- **Every section mandatory.** If a section has no content, write "(none)" — never omit.
- **No emoji inside the box border.** Same rule as `dashboard-layout.md` / `execute-report-card.md` — emoji are width-2 but many renderers draw them at 1 cell, misaligning borders. Confine emoji to the header line outside the box; ✅/⚠️/❌ in indented content lines below the box are fine.
- **Width budget:** 74 columns (matches dashboard + execute report card). Content lines indent 2 spaces.
- **One report card per run.** It appears once, at the very end — after the loop converges (single-iteration) or after the final iteration (multi-iteration). No incremental card per wave or per iteration.

## Layout

```
╔══════════════════════════════════════════════════════════════════════╗
║           /meta-loop-gap — GAP SCAN REPORT CARD                    ║
╚══════════════════════════════════════════════════════════════════════╝

  Scope:        <scope-name>
  Path:         <plan-dir | target path>
  Mode:         plan | project | code | feature
  Status:       HARDENED — NO GAPS REMAINING
                (or "GAPS REMAIN — <N> unresolved")
  Duration:     <elapsed — e.g. 3 iterations · 42 agents · 88k tokens>

  ── Scan ──
  <N> files · <budget> budget · waves W0+W1+W2+W3 · <I> iteration(s)

  ── Gaps ──
  ✅ <fixed>/<found> fixed   <flagged> flagged   <remaining> remaining
     severity:  <H> high · <M> med · <L> low
     category:  <top 3 categories by count, e.g. contract_schema×4, stub×2>

  ── Files Hardened ──
  <file>                                        <K> fixed
  <file>                                        <K> fixed

  ── Commits (on <repo> master, all pushed) ──
  <short-sha>  <one-line description>                    <K gaps>
  <short-sha>  <one-line description>                    <K gaps>

  ── Review Gate ──
  ✅ Wave 3 review CLEAN — fixes verified, no scope creep
  (or)
  ⚠️  <N> review issues — all resolved
  (or)
  ⏸  Wave 3 not run (budget: <low|medium>)

  ── Remaining Gaps ──
  • <file:line> — <category> — sev:<H> conf:<X.XX> — <why unresolved>
  • (none)

  ── Follow-ups ──
  • <item> — <action> — <owner>
  • (none)
```

## Section Rules

### Scope + Status

One line each.

- **Scope** — the `{SCOPE_NAME}` from `loop-gap.md` (e.g. the plan/initiative name or the source module set).
- **Path** — the plan directory (plan/project mode) or target path (code/feature mode).
- **Mode** — `plan` | `project` | `code` | `feature`, as resolved in Step 0/2.
- **Status** — one of:
  - `HARDENED — NO GAPS REMAINING` — loop converged, zero open gaps (this is the loop-gap analogue of "NO GAPS REMAINING" — Stage 4 exit criteria met)
  - `HARDENED — <N> advisories` — zero fixable gaps left, only low-confidence report-only items remain
  - `GAPS REMAIN — <N> unresolved` — max iterations hit or budget exhausted with open high/med gaps
- **Duration** — compact: iterations run · total agents spawned · tokens.

### Scan

File count, budget tier (`low`/`medium`/`high`), which waves actually ran, iteration count. If a wave was skipped by budget, omit it from the list (e.g. `waves W0+W1` for a low-budget run).

### Gaps

Compact ratio line: `<fixed>/<found> fixed`. `flagged` = the 0.5–0.79 confidence band (fixed but flagged for review). `remaining` = open gaps not auto-fixed. Then two breakdown lines — by severity and by top categories. Use the gap categories from the gap-report format (`contract_schema`, `stub`, `dependency`, etc.).

### Files Hardened

One row per file that received ≥1 fix. Columns: file path (truncate with `…` to fit width), gap count fixed. Read-only consumer/reference files that were only inspected do NOT appear here. If no files were modified (clean scan), write `(none — scan clean, no fixes needed)`.

### Commits

Table: short SHA (9 chars), one-line description (truncate to ~46 chars with `…`), gaps-fixed count. One row per fix commit produced during the scan. If loop-gap made no commits (e.g. report-only run, or fixes batched into a single commit), reflect that honestly. If the scan ran but the user hasn't committed yet, write `(uncommitted — N files modified, awaiting commit)`.

### Review Gate

State the Wave 3 outcome:
- `✅ Wave 3 review CLEAN — fixes verified, no scope creep` — Opus review agent (3a) passed
- `⚠️ <N> review issues — all resolved` — review found issues with the fixes, now resolved
- `⏸ Wave 3 not run (budget: <tier>)` — Wave 3 skipped (low budget, or medium budget with prior gaps ≥ 3)

### Remaining Gaps

The honest "what's left" list — this is what makes hardening status obvious. Each item: `file:line — category — sev/conf — why unresolved`. Include every gap NOT fixed (below the auto-fix threshold, cross-file gaps needing manual judgment, or items deferred at max-iterations). If the loop converged clean, write `(none)`.

### Follow-ups

Structured list. Each item: `• <what> — <action needed> — <owner>`. Include:
- Next-stage prompt — when status is HARDENED, the natural follow-up is `Ready for /meta-execute <plan>` (plan mode) — owner `you`.
- Any report-only advisories the user should eyeball.
- Source-mode gaps that touch read-only consumer files (loop-gap won't fix those — surface them).
- Recurring-pattern detections that patched `meta-planner` (Step 6) — note the LP id.

Owner is `you` (the user), `me` (the session), or a role. Empty list → `(none)`.

## Anti-Sprawl Rules

1. **Do NOT re-describe the plan or the gap categories in prose.** The card is a scan summary, not the scanner spec.
2. **Do NOT narrate the waves.** The Scan + Gaps lines ARE the narrative. No "Wave 1 found X, then Wave 2…".
3. **Do NOT list every gap fixed.** Files Hardened + counts is enough; only OPEN gaps get enumerated (Remaining Gaps).
4. **Do NOT add a conversational sign-off.** The report card IS the sign-off. No "Done!", "Let me know…", "The plan is now ready…". The Follow-ups line carries the next action.
5. **One card per run**, at the very end — never one per iteration.
6. **Be honest about convergence.** If gaps remain, Status says `GAPS REMAIN` and they appear under Remaining Gaps. Never render `NO GAPS REMAINING` while the Remaining Gaps list is non-empty.
