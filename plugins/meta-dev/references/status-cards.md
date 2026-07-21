# Status Cards — the ONE card standard

> **This file is the single source of truth for every card meta-dev prints.**
> No other spec, command, or script defines box art, glyphs, or widths. If you
> are about to draw a box somewhere else, you are creating the tenth format —
> link here instead.

Implementation: `scripts/planctl/render_lib.py`. Markdown surfaces follow the
same rules by hand.

## Why this file exists

meta-dev grew **9 card formats** independently: 4 border styles (`╔═╗`, `╭╮`,
`━━`, none), 5 widths (62/68/72/74/100), and **3 parallel glyph vocabularies**
that disagreed on nearly every status — *done* was `✅` or `✓`, *running* was
`🟡` or `→` or `🔄`, *blocked* was `❌` or `🔴` or `⛔` or `!`.

The cause was structural, not aesthetic: two specs were duplicated verbatim into
their own commands and the copies drifted from the originals, while the shared
render module that was supposed to prevent exactly this
(`planctl/render_lib.py`) was **silently never imported** — `dashboard-render.py`
had one `dirname()` too many in its `sys.path` insert, so a hidden inline
fallback ran in production for months.

Hence the rule at the top. One definition, referenced — never restated.

## The chassis — open-right

```
┌─ ORCHESTRATION ─────────────────────────────────────────────────────────
│ ✅  T1   facetPick→tilePick             930e8b015    spark
│ 🔄  T2   atomic feature rename          running      sol/high
│ ⏸   T3   backend names                  queued       spark
├─ Gates ─────────────────────────────────────────────────────────────────
│ 🔒  T5   human acceptance gate          held for your opt-in
└─────────────────────────────────────────────────────────────────────────
```

`┌─ TITLE ─…` top rule · `│ ` row prefix · `├─ Label ─…` section divider ·
`└─…` bottom rule · **no right border**.

**The missing right border is load-bearing.** Emoji are double-width (2 terminal
cells) but many renderers — including inline markdown — draw them at 1 cell. Any
right-hand `│` therefore drifts and can never be reliably aligned. Removing it
is what makes emoji safe in every card, permanently.

This reverses the old doctrine ("never emoji inside boxes"), and the reversal is
the point: the ban existed only to protect a right border we no longer draw.

Two consequences that are enforced by test
(`tests/planctl/test_render_lib_cards.py`):

- **Rules measure `dwidth()`, never `len()`** — so an emoji in a title or
  section label consumes two cells of the rule and the card stays exactly
  `CARD_W`.
- **No row ever ends in whitespace.** With no right border there is nothing to
  pad to, and trailing spaces are silently eaten by markdown renderers and
  copy/paste. `card_row()` always `rstrip()`s.

## The vocabulary — 10 status keys, 9 distinct glyphs

| Glyph | Status | Reads as |
|---|---|---|
| `✅` | `done` | done |
| `🔄` | `executing` | running |
| `⏸` | `draft`, `ready` | queued |
| `⏳` | `needs-review` | awaiting verdict |
| `🔒` | `gated` | human gate — waiting on Phong |
| `⛔` | `blocked` | blocked |
| `⏺` | `parked` | paused |
| `🚫` | `superseded` | superseded |
| `❓` | `missing` | missing |

`⚠️` is a **suffix**, not a status — appended to any drift-bearing glyph
(`✅⚠️`) so a newly introduced status cannot silently hide drift.
Unknown status → `❔` (`UNKNOWN`), never a `KeyError`. This is the safe fallback
from `mark()`, not a status in `STATUS`, and it is not retired.

`draft` and `ready` deliberately collapse to one glyph: the distinction matters
to `derive.py`, not to someone scanning a card.

**Retired — do not reintroduce:** `✓ ✔ ▹ ⊙ ‖ ⌀ ◦ ◌ ▸ → ! ✗ ❌ 🟡 🔴 ⬜ 📝 ▶️ 👀`
as *status markers*. (`→` survives only as a prose arrow, never a status.)

## Width

**`CARD_W = 74`. Zero exceptions.** One constant, every card, every renderer.
A "just this one is wider" exception is how five widths happened the first time.

Progress bars use `█`/`░` via `render_lib.bar(done, total, width)` — width is a
parameter, not a new bar. Never invent a second glyph pair (the runbook's old
`▰▱` is retired).

## The four card types

All four are the same chassis. They differ only in what fills the rows.

**1. Progress card** — live during orchestration. One row per task/wave.

```
┌─ ORCHESTRATION ─────────────────────────────────────────────────────────
│ ✅  T1   facetPick→tilePick             930e8b015    spark
│ 🔄  T2   atomic feature rename          running      sol/high
└─────────────────────────────────────────────────────────────────────────
```

**2. Report card** — end of a run (`/meta-execute`, `/meta-loop-gap`). Sections
via `card_sep()`.

```
┌─ /meta-execute — EXECUTION REPORT ──────────────────────────────────────
├─ Tasks ─────────────────────────────────────────────────────────────────
│ ✅  6/6 completed · 0 failed · 0 deferred
├─ Code Review ───────────────────────────────────────────────────────────
│ ✅  CLEAN — 0 findings
└─────────────────────────────────────────────────────────────────────────
```

**3. Next Steps card** — the mandatory end-of-response capstone. One `NOW` row.

```
┌─ NEXT STEPS ────────────────────────────────────────────────────────────
│ 🔄  Codex SOL crash-sim (xhigh)                running
│ ✅  Ledger updated — findings + 6 invariants   committed
│ ⛔  Hard stop after Stage 2 — needs a new go
└─────────────────────────────────────────────────────────────────────────
```

**4. Control-plane view** — `/meta-dashboard`, `/meta-overlord`, `/runbook`.
Adds progress bars and tables inside the same chassis.

## API

```python
from planctl.render_lib import (
    CARD_W, CARD_FIELD, STATUS, DRIFT, UNKNOWN,
    mark, label,                                   # status → glyph / word
    card_top, card_sep, card_row, card_rule, card_bottom,
    cols, card,                                    # row alignment / whole card
    bar, bar_frac, pct,
)
```

`cols(cells, widths)` fits every cell **except the last**, which is left
unpadded — so a wide glyph in the final column costs nothing. That is the
mechanism that makes emoji free here.

`card(title, sections)` takes `[(label|None, [lines]), …]`; the first section's
label is omitted because the title already heads the card.

## Rules

- **Never restate this format elsewhere.** Link to this file.
- **Never pad a row's tail.** `card_row()` rstrips; keep it that way.
- **Never add a width.** `CARD_W` is 74.
- **Never add a status glyph** without adding the status to `STATUS` — the
  closed-vocabulary test will fail, which is the intended behaviour.
- Cards are the **last** thing in a response, not buried under prose.
