# Sniff Report — Layout Spec

The report `/sniff` renders at completion. **Report-only:** it recommends, it never claims to have changed anything. The owner of every fix is `you`.

## Design principles (why this layout)

- **Summary first.** Lead with what was sniffed and how bad it is, so the reader gets scope + severity in two lines before reading a single finding. Detail follows; it never comes before the headline.
- **One signal system.** Severity is carried by the plain-text tags `[big stink]` / `[smell]` / `[whiff]` — nothing else. No decorative emoji, no face-glyph clusters (they misalign and the count never matches the number), no ASCII box-art. Glyphs that don't carry information are noise.
- **No restatement.** The findings are listed once. The summary tallies them; it does NOT repeat them or point "see above". The verdict appears exactly once.
- **Caveat in the verdict.** The single most important honest note (e.g. "these are spent one-shot scripts — low value to fix") goes *into* the final word line, not as a trailing paragraph. Nothing comes after the verdict.
- **Concise.** The report is the verdict, not a lecture. The findings carry the detail.

## Layout

```
GRUG SNIFF — <target>
<N> files · big stink ×<a> · smell ×<b> · whiff ×<c>

[big stink] <smell-name>  <file>:<line>
   grug see:   <one line>
   grug smell: <one line>
   grug say:   <one line — the fix>

[smell] <smell-name>  <file>:<line>
   grug see:   …
   grug smell: …
   grug say:   …

[whiff] <smell-name>  <file>:<line>   ← whiffs may collapse (see below)

— grug final word —
<one line: the honest bottom line, key caveat folded in>
```

## Section rules

### Header (two lines, always)

- **Line 1 — `GRUG SNIFF — <target>`.** Target is what was actually sniffed: a path, `conversation focus (<the files/subject>)`, `working diff`, or `staged`. Name the real files when the target was the conversation, so the reader can confirm grug sniffed the right thing.
- **Line 2 — the tally.** `<N> files` sniffed, then plain counts by level: `big stink ×<a> · smell ×<b> · whiff ×<c>`. Omit a level with zero count. If nothing was found at all, write `<N> files · clean — grug smell nothing` and skip straight to the final word.

### Findings (worst stink first)

`big stink` → `smell` → `whiff`. Each is the three grug lines + location from the SKILL finding format, prefixed only by its `[stink]` tag. Keep each grug line to ONE line — truncate with `…` if needed. If there are many findings, show all `big stink` + `smell` in full; `whiff`-level may collapse to a single line at the bottom (`whiffs: file:line magic-number · file:line long-params · …`) so the report stays scannable.

If zero findings: skip this block entirely and go to the final word.

### grug final word (one line, always last)

Exactly one line. The honest bottom line in grug voice, actionable, with the most important caveat folded in:

- clean: `grug approve. ship it.`
- whiffs only: `grug mostly happy. wipe the whiffs when convenient, no blocker.`
- smells: `grug recommend fix the <N> smell before merge — see grug say lines.`
- big stink: `grug say NO merge yet — <N> big stink (e.g. hardcoded secret, swallowed error) must fix first.`
- caveat case: if the target is throwaway/spent code, say so here — `…but these are spent one-shot scripts; fixing them is low value — grug say just delete them.`

## Anti-sprawl rules

1. **No ASCII box, no emoji, no face-glyph tally.** The `[stink]` tags + plain counts are the whole visual system.
2. **Do NOT re-explain the catalog or grug philosophy** in the report. The findings carry it.
3. **Do NOT narrate the passes** ("first grug grepped, then grug read…"). The tally IS the narrative.
4. **Do NOT claim any fix was made.** Report-only. Every `grug say` is a recommendation; owner is `you`.
5. **Nothing after the final word.** No conversational sign-off, no trailing caveat paragraph — fold the caveat into the verdict line.
6. **One report per run**, at the very end. Never one per file.
