---
name: sniff
description: Grug-brain sniff test — detect code smells, hacks, and bad practices and recommend the simplest best-practice fix for each. Report-only, never edits code. Invoked as /sniff. By default sniffs the code under discussion in the current conversation; takes a path, or --diff/--staged/--all. Use when reviewing code quality, before merging, or when something "smells off".
allowed-tools: [Read, Bash, Glob, Grep]
---

# /sniff — grug smell code, grug tell you

grug sniff code for smell. grug find bad practice, hack, complexity demon spirit. grug NOT fix — grug TELL you what stink and what best practice instead. you read, you decide, you fix.

**Report-only.** This skill NEVER edits code. It detects, explains, and recommends. (Want auto-fix? that is `/meta-loop-gap` code mode — different tool.)

## The grug law (read first — this is what makes it a sniff test, not a lint robot)

1. **complexity is apex predator.** the worst smells are the ones that ADD complexity — premature abstraction, clever code, speculative generality. weight these heaviest.
2. **the fix must itself be grug-approved.** NEVER recommend adding complexity to remove a smell. the fix for a `switch` is not "Strategy pattern" — it is usually "leave switch alone" or "table lookup". simplest thing that removes stink. if the only fix is more complex than the smell, say so and recommend leaving it.
3. **grug not rule robot.** a little duplication is fine. a `switch` is fine. a long-but-flat function is fine. only flag when it crosses a real threshold (see catalog). over-flagging IS a complexity smell.
4. **chesterton fence.** code "ugly and gronky" for reason. before recommending a delete/rewrite, note that the reason must be understood first.
5. when grug unsure if real smell → lower stink level, do not omit. honesty over confidence.

## Stink levels (grug confidence × severity)

| Level | Meaning | When |
|-------|---------|------|
| `big stink` | clear bad practice, high confidence | swallowed exception, hardcoded secret, dead code, obvious premature abstraction |
| `smell` | likely smell, judgment call | long method, feature envy, duplication past threshold |
| `whiff` | minor / context-dependent | magic number in obvious context, slightly-long param list |

## Smell taxonomy

Seven groups. Full detection heuristics + grug-approved fixes in `references/sniff-catalog.md` — read it before sniffing.

1. **complexity demon** — speculative generality, premature abstraction (interface/factory with one impl), arrow-code nesting, clever one-liners, god object
2. **big thing** (bloaters) — long method, long parameter list, large class, data clumps
3. **repeat-or-abstract** — real copy-paste AND premature/wrong DRY (both stink in grug world)
4. **hack & shortcut** — TODO/FIXME/HACK, swallowed exceptions, magic numbers/strings, hardcoded secrets, commented-out code, dead code, boolean-trap params, stringly-typed
5. **coupling demon** — feature envy, message chains, middle man, reaching into internals
6. **fear-the-spooky** — shared mutable global state, premature optimization (no profile), missing logging on error paths
7. **chesterton fence** — risky deletion/rewrite in a diff with no stated reason

## Procedure

1. **Resolve target (priority order — STOP at the first that matches).**
   - **Explicit path** in `$ARGUMENTS` (file or dir) → sniff exactly that.
   - **`--diff`** → the working `git diff` (changed + staged). **`--staged`** → staged only. **`--all`** → whole repo (warn if large, suggest a path instead).
   - **No argument → the conversation focus (DEFAULT).** Sniff the code that is the live subject of *this* conversation: files you just read/edited/wrote, the module/symbol under discussion, the change you and the user have been working through. Pick the most recent, most-relevant code in context.
   - **No clear target in context → ASK, do not guess.** If the conversation has no concrete code subject yet (e.g. only a design was discussed, no code written), say so in grug voice and ask what to sniff — offer `--diff` as the option for "just sniff my working changes". **NEVER silently fall back to `git diff`** — the working tree often holds unrelated scratch/leftover files (a stale rename script, a scratch test) that have nothing to do with the conversation, and sniffing those wastes the run and confuses the user.
2. **Read the code.** Load target files. For a diff target, sniff the changed regions but read enough surrounding context to judge (a smell needs its neighborhood).
3. **Mechanical pass (fast).** grep the hack patterns from catalog §4 (TODO/FIXME/HACK, empty `catch`/`except: pass`, hardcoded `password=`/`api_key=`/`secret`, magic-number literals, large commented-out blocks). Every hit is a candidate at high confidence.
4. **Semantic pass (judgment).** Read for the structural smells (groups 1,2,3,5,6,7). These need understanding, not grep. Apply the catalog thresholds — do NOT flag below threshold.
5. **grug judgment filter.** For every candidate: (a) is it ACTUALLY a problem here, or is grug being precious? drop the precious ones. (b) is the recommended fix simpler than the smell? if not, downgrade to "leave it, here's why" and lower stink. (c) de-dup (same file+line+smell = one).
6. **Write each finding** in the three-line grug format (see below).
7. **Render the Sniff Report card** at the end — layout in `references/sniff-report.md`. One card per run.

## Finding format

Each finding is exactly three grug lines + location:

```
[<stink>] <smell-name>  <file>:<line>
   grug see:   <what is there — one line, concrete>
   grug smell: <which principle/smell it violates — why grug no like>
   grug say:   <the simplest best-practice fix — concrete and actionable>
```

The `[<stink>]` tag is the only marker — no decorative emoji on finding lines (it is noise, not signal). The grug see/smell/say triad carries the meaning.

`grug say` must be a real, minimal change — not "consider refactoring". Name the constant. Handle the error. Inline the abstraction. Move the method to the data. If the honest answer is "leave it", say that and why.

## Report

Render the grug Sniff Report — exact layout in `references/sniff-report.md`. **Summary first:** a one-line target header + a one-line plain-text stink tally, so the reader knows scope and severity before reading anything. Then the findings (worst stink first). Then exactly one `— grug final word —` verdict line, with the single most important caveat folded into it. No ASCII box, no emoji tally, no "see above" pointer, no trailing prose after the verdict — that line IS the wrap-up.

## Rules

- **Never edit code.** This is a sniff test. Detect, explain, recommend. That is all.
- **Never recommend more complexity than the smell costs.** This is the cardinal rule (grug law #2).
- **Never flag below catalog threshold.** Over-flagging is itself a smell.
- **Be specific:** `file:line`, exact construct, exact fix. No vague "this could be cleaner".
- **Honest stink:** unsure → lower the level, don't drop the finding and don't inflate it.
