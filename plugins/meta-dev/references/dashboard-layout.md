# Dashboard Layout Spec

Shared glyph vocabulary and layout rules for `dashboard-render.py` and `overlord-render.py`.

## Glyph Table

| Icon | Meaning | Status |
|------|---------|--------|
| ✅ | Done / shipped | complete |
| 🟡 | In-flight / active | in progress |
| ⬜ | Pending / queued | not started |
| 🔴 | Blocked / failed | needs attention |
| ⏸ | Paused | temporarily stopped |

## Progress Bar Rules

- Bar width: 10 characters
- Filled: `█` (U+2588) — number = round(BAR_W * done / total)
- Empty: `░` (U+2591) — remaining
- Ratio: `NN/TT` right-aligned, zero-padded to 2 digits
- Percentage: ` NN%` right-aligned to 3 characters

## Terminal Width Budget

- **Max width: 100 columns**
- Plan name column: 30 chars (truncate with `…` if longer)
- Session table: Session(16) + Plan(20) + Task(8) + Stage(10) = 54 + borders
- Sweep log lines: prefix `  ✓ ` + message (truncate to 88 chars)
- Footer: nav links at full width

## Color (for color-capable terminals)

- Headers: bold
- Blocked: red text
- Done: green text
- In-flight: yellow text
- Totals: bold
