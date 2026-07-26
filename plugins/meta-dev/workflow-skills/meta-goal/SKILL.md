---
name: meta-goal
description: Consolidate everything this conversation put in swing into one itemized ≤1000-char GOAL string to paste into Claude Code's /goal, so the session drives itself to completion instead of needing a prompt per step. Use when the user asks to "make a goal", "wrap this thread into a goal", "consolidate what's in swing", or wants to go autonomous on the current thread's open work.
---

# Meta-Goal — collapse the thread into one autonomous goal

Claude Code's `/goal <condition>` keeps a session driving toward a stated condition and re-checks completion with a **read-only evaluator that can only see the transcript**. That makes it the cheapest autonomy lever available: one paste, and the thread stops needing a prompt per step.

The bottleneck is authorship. A goal written loosely either terminates early (vague items evaluate as "close enough") or never terminates (items whose completion never appears as literal output). This skill writes the goal that actually closes.

**Scope is THIS CONVERSATION.** Not the project, not the plan tree, not the inbox. The thread is the input; anything the thread never touched is out, however open it is elsewhere.

## Procedure

### 1. Harvest the thread

Walk the conversation start to now and pull every distinct thing **in swing** — asked but not delivered, started but not finished, found but not fixed, decided but not written down. Look for:

- Explicit asks from the user, including ones deferred with "later" / "after this" / "then we'll…"
- Work begun and left incomplete — a partial edit, a dispatched agent whose result was never applied
- Bugs, gaps, or review findings surfaced in-thread and not yet closed
- Decisions reached in conversation that exist nowhere on disk yet
- Open items in the runtime task list
- Plan checkboxes **this thread** advanced or promised to advance

Exclude: work already landed and committed in this thread · anything the user explicitly dropped · pure Q&A with no deliverable · anything in swing elsewhere in the project that this thread never mentioned.

### 2. Sharpen or drop

Merge duplicates. Then test each survivor: **can it be stated as an observable end state?** If yes, sharpen it to that. If no, drop it. Never carry a fuzzy item forward — a vague item cannot evaluate as met, so it holds the entire goal open forever and silently converts the whole thing into an infinite loop. One dropped item costs a follow-up prompt; one vague item costs the run.

### 3. Order by dependency

Blockers first; anything that unblocks another item precedes it. The goal is executed top-down, so the order **is** the plan.

### 4. Attach a proof to every item

This is the load-bearing step. The evaluator sees the transcript and nothing else — not the filesystem, not git, not your intentions. An item whose completion never appears as **literal output in the transcript** can never be judged done.

| ✅ Valid proof | 🚫 Invalid proof |
|---|---|
| commit sha, printed | "committed it" |
| a focused test's real stdout | "tests pass" |
| the `planctl check` line as emitted | "flipped the checkbox" |
| the file path + its Write/Edit landing | "wrote the file" |
| a command's actual stdout | "verified" / "looks good" / "done" |

Each proof must also be **reachable without the user** — a proof that requires human eyes (by-eye render check, GPU smoke test) belongs on the STOP line, not on an item.

### 5. Compress to budget

Default **1000 characters**, hard. Compression rules, in order of preference:

1. Drop articles and filler; digits not words; path stems not full paths (`library-trash-unification`, not `plans/app/2026-07-25-library-trash-unification.md` — unless the path is the deliverable)
2. One line per item, no preamble, no blank lines
3. Still over? **Cut whole items from the bottom** (lowest priority) and report exactly what was cut

**Never compress by making items vaguer.** Trading precision for length reintroduces the step-2 failure. A goal of 6 sharp items beats 11 mushy ones — the 6 close, the 11 spin.

### 6. Emit

One fenced block, copy-paste clean, nothing above or below it inside the fence:

```
DONE when all land, committed, in order:
1 <item> — <proof>
2 <item> — <proof>
3 <item> — <proof>
EACH: path-scoped commit, flip plan checkbox before next item
STOP: no deploy/publish/prod-push; leave human-verify boxes unchecked + list them
END: reply "GOAL MET" + item→sha table
```

Under the fence, three lines and nothing more:

- `<n>/1000 chars`
- `Dropped for budget: <items>` — omit the line entirely if nothing was dropped
- `▶ **NEXT — you:** paste that into `/goal` and the thread runs itself to the end.`

The three trailing directives are fixed and always present:

- **EACH** enforces durable per-item state so a mid-run stop leaves committed work, not a pile of loose edits
- **STOP** carries the autonomous hard floor (`references/autonomous-mode.md`) into the goal string itself, where the loop actually reads it. Deploy/publish/prod-push and human-verify boxes are never inside a goal.
- **END** gives the evaluator an unambiguous terminal signal. Without it, a satisfied goal can still fail to close.

## Rules

- **Emit only — never invoke.** `/goal` is the user's to type. Print the block and stop.
- **Thread scope is absolute.** Do not read the plan tree, inbox, or git for extra items. If the thread is thin, the goal is short — say so rather than padding it from project state.
- **Never invent items.** Everything in the goal was in the conversation. A goal containing work the user never asked for is how an autonomous run wanders.
- **Report the cut.** Anything dropped for budget is named under the fence. Silent truncation reads as "that's everything" when it isn't.
- **Re-runnable.** Called again later in the same thread, re-harvest from scratch — landed items fall out, new ones enter.
