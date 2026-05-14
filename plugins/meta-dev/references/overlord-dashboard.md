# Overlord Dashboard Layout Spec

ASCII dashboard for `overlord-render.py`. Shares glyph vocab with `dashboard-layout.md`.

## Layout Sections (top-to-bottom)

```
[Shield Icon] Overlord Dashboard — {plan_slug}
Tick {N} · {date} · poll: {interval} · executor: {label}

Progress
  {phase name:<20} {████████░░} {done}/{total}  {icon}
  ─────────────────────────────────────────────
  TOTAL                {████████░░} {done}/{total}  {NN%}

Last {N} commits ({executor} trail)
  Commit     Task                     Verdict
  ────────── ──────────────────────── ────────────────────────────────
  {sha}      {task name}              {icon} {note}

🔴 Findings (N)
  {i}. [{severity}] {desc} — {ref} — {action}

Next checkpoint
  Up next: {id} ({title})
  Checkpoint: {checkpoint}
```

## Glyph Table

| Glyph | Meaning | Status |
|-------|---------|--------|
| `✅` | Task done or verdict clean | complete |
| `\U0001f7e1` | In-flight or drift (yellow circle) | partial |
| `⬜` | Pending / not started | queued |
| `\U0001f534` | Blocked or failed | needs attention |
| `⏸` | Paused / gated | temporarily stopped |
| `⏳` | Verdict pending (hourglass) | awaiting review |
| `❓` | Unknown verdict | edge case |
| `█` (full block) | Progress bar filled segment | done portion |
| `░` (light shade) | Progress bar empty segment | pending portion |

## Progress Bar Rules

- Bar width: exactly 10 characters
- Filled: `█` — count = round(10 * done / total)
- Empty: `░` — remaining
- Ratio: `{done}/{total}` right-aligned
- Percentage: `{NN}%` right-aligned to 3 chars

## Terminal Width Budget

- **Max width: 100 columns**
- Phase name column: 20 chars (truncate with `…` if longer)
- Commit SHA: 8 chars
- Task column: 22 chars
- Verdict note: 28 chars
- Finding ref: variable, truncated at 60 chars total line

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
