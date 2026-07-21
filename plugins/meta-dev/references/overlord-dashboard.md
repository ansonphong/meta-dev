# Overlord Dashboard Layout Spec

ASCII dashboard for `overlord-render.py`.

> **Card format:** open-right chassis, 9-glyph vocabulary, `CARD_W = 74` —
> see [`status-cards.md`](status-cards.md). This file defines only the
> *content* of the view: which sections it shows, from which state fields.

**Width: `CARD_W = 74`, like every other card.** Overlord was originally specced
at 100 columns; that exception is retired. The **phase-name column narrows** (and
the task / verdict-note columns with it) to fit 74 — truncate with `…`. Do not
reintroduce a wider budget.

## Layout Sections (top-to-bottom)

```
┌─ OVERLORD — {plan_slug} ────────────────────────────────────────────────
│ Tick {N} · {date} · poll: {interval} · executor: {label}
├─ Progress ──────────────────────────────────────────────────────────────
│ {glyph}  {phase name}   {████████░░}  {done}/{total}
│ TOTAL                   {████████░░}  {done}/{total}  {NN}%
├─ Last {N} commits ({executor} trail) ───────────────────────────────────
│ {glyph}  {sha}  {task name}          {note}
├─ Findings ({N}) ────────────────────────────────────────────────────────
│ ⛔  [{severity}] {desc} — {ref} — {action}
├─ Next checkpoint ───────────────────────────────────────────────────────
│ Up next: {id} ({title}) · checkpoint: {checkpoint}
└─────────────────────────────────────────────────────────────────────────
```

Progress bars go through `render_lib.bar(done, total, width)` — overlord passes
width 10.

## Color (terminal-capable)

- Header line: bold
- Blocked/failed status: red text
- Done/pass: green text
- In-flight/drift: yellow text
- TOTAL row: bold + underline
- Findings header: red + bold

## States

| State field | Values |
|-------------|--------|
| phase.status | `done`, `in_flight`, `pending`, `blocked`, `gated` |
| commit.verdict | `pass`, `drift`, `pending`, `failed` |
| finding.severity | `critical`, `high`, `moderate`, `low` |
