# Sniff Report Card — Layout Spec

The structured card rendered by `/sniff` at completion. Same boxed style as `references/execute-report-card.md` and `references/loopgap-report-card.md` so a sniff reads like the other harness reports — but in grug voice. Report-only: the card recommends, it never claims to have changed anything.

## Design Principles

- **Concise.** The card is the verdict, not a lecture. Findings already carry the detail.
- **Every section mandatory.** No content → write "(none — grug smell nothing here)". Never omit.
- **No emoji inside the box border.** Width-2 emoji misalign borders in many renderers. Keep emoji to the header line outside the box and to the indented content lines below it (🦗 / 🤢 are fine in content, never in the ╔═╗ border rows).
- **Width budget:** 74 columns. Content indents 2 spaces.
- **One card per run**, at the very end. Never one per file.
- **Report-only honesty:** the card never says "fixed". It says what stinks and what grug recommends. The owner of every fix is `you`.

## Layout

```
╔══════════════════════════════════════════════════════════════════════╗
║              /sniff — GRUG SNIFF REPORT                            ║
╚══════════════════════════════════════════════════════════════════════╝

  Target:       <path | "working diff" | "staged">
  Files:        <N> sniffed
  Stink level:  <overall verdict — see scale below>

  ── Stink tally ──
  🤢🤢🤢 <big-stink count> big stink   🤢🤢 <smell count> smell   🤢 <whiff count> whiff
     by group:  complexity-demon×N · hack×N · coupling×N · …

  ── Findings (worst stink first) ──
  🦗 <smell-name>  [big stink]  <file>:<line>
     grug see:   <one line>
     grug smell: <one line>
     grug say:   <one line — the fix>
  🦗 <smell-name>  [smell]  <file>:<line>
     grug see:   …
     grug smell: …
     grug say:   …

  ── grug final word ──
  <one-line verdict — see below>
```

## Section Rules

### Header block

- **Target** — what was sniffed: a path, `working diff`, or `staged`.
- **Files** — count of files actually read/sniffed.
- **Stink level** — overall verdict, pick by worst-present finding:
  - `clean — grug smell nothing, code good` (zero findings)
  - `mostly clean — few whiff, nothing serious` (only whiffs)
  - `some smell — worth a wipe` (has `smell`, no `big stink`)
  - `big stink — grug hold nose, fix before merge` (any `big stink`)

### Stink tally

One count line by level, then a `by group` breakdown using the catalog group names (`complexity-demon`, `big-thing`, `repeat-or-abstract`, `hack`, `coupling-demon`, `fear-spooky`, `chesterton-fence`). Omit groups with zero findings.

### Findings

Worst stink first (`big stink` → `smell` → `whiff`). Each finding is the three grug lines + location from the SKILL format. Keep each grug line to ONE line — truncate with `…` to fit 74 cols. If there are many findings, show all `big stink` + `smell` in full; `whiff`-level may be collapsed to a one-line list at the bottom (`whiffs: file:line magic-number · file:line long-params · …`) so the card stays scannable.

If zero findings: write `(none — grug smell nothing here, code is grug-good)` and skip straight to the final word.

### grug final word

Exactly one line. The honest bottom line, in grug voice but actionable:
- clean: `grug approve. ship it.`
- whiffs only: `grug mostly happy. wipe the whiffs when convenient, no blocker.`
- smells: `grug recommend fix the <N> smell before merge — see grug say lines.`
- big stink: `grug say NO merge yet — <N> big stink (e.g. hardcoded secret, swallowed error) must fix first.`

## Anti-Sprawl Rules

1. **Do NOT re-explain the catalog or the grug philosophy in the card.** The findings carry it.
2. **Do NOT narrate the passes** ("first grug grepped, then grug read…"). The tally IS the narrative.
3. **Do NOT claim any fix was made.** Report-only. Every `grug say` is a recommendation; owner is `you`.
4. **Do NOT add a conversational sign-off** after the card. The "grug final word" line IS the sign-off.
5. **One card per run**, at the very end.
