---
name: meta-compact
description: Forward-moving compaction handoff. Use when a long session is getting context-heavy mid-project and you want to compact WITHOUT losing momentum — writes a durable, forward-looking handoff so the post-compaction session resumes the exact next step instead of being left hanging. Also used to proactively flag clean compaction boundaries during work. Triggered on-demand via /meta-compact or proactively when a clean boundary meets a heavy context.
---

# Meta-Compact — compact forward, never hang

Normal `/compact` produces a *backward* summary: "here is what happened." That is fine for recovery, but mid-project it leaves you **hanging** — the next session has to re-discover the working state, re-find the files, and risks re-litigating decisions or re-hitting traps you already cleared.

`meta-compact` makes compaction **forward-moving**: before you compact, it writes a durable handoff whose center of gravity is the **single next concrete action**, plus exactly the state needed to execute it. After compaction the first move is to read that file and *continue* — no re-orientation, no lost momentum.

**This skill does not run `/compact`** (only the user or auto-compact can). It produces the handoff that makes the compaction safe, then tells you to pull the trigger.

## Three entry points

1. **On-demand** — `/meta-compact`. You decide it's time; the skill finds the nearest clean boundary and writes the handoff.
2. **Proactive watch** — during normal work, when a clean boundary coincides with a heavy context, surface a *single* one-line offer (don't nag):
   > 🪶 Clean boundary + heavy context — good moment to compact forward. Run `/meta-compact` and I'll write the handoff.
   Offer once per boundary. If the user keeps going, drop it until the next boundary.
3. **Watchdog-triggered (long orchestration runs)** — during a multi-phase `/auto-execute` or `/meta-execute --deep|--glm|--codex` playbook, the conductor checks `scripts/context-gauge.py` at each phase/wave seam. When it reads `CONTEXT_VERDICT=OVER` (default 300000 tokens; `META_DEV_CONTEXT_THRESHOLD` to tune), the loop invokes this skill automatically at that committed boundary. Here the handoff's **▶ NEXT ACTION is "resume the playbook at the next phase/wave"** (name the plan path + next phase file). This pre-empts the harness's blunt hard auto-compact with a graceful forward seam. See agentic-exec-loop → "Context watchdog".

## When it is a clean boundary (timing judgment — the whole point)

A forward-compact is only safe at a **seam**. Fire when:

- ✅ A logical unit of work just finished **and is committed** (clean tree).
- ✅ You are about to start a large new phase that will need lots of fresh context anyway.
- ✅ The session is long / context is heavy, and you are at a natural pause (not mid-thought).

NEVER fire when:

- ❌ Mid-edit or mid-multi-file change — finish the unit and commit first.
- ❌ Tree is dirty *inside* a task — the handoff must point at committed state, not half-applied edits. Commit (or capture exactly why it's dirty) first.
- ❌ Mid-debug with unsaved reasoning — write the findings into the handoff's Gotchas before compacting, or they die.

**Rule:** if it isn't safe to compact yet, say so and name the one thing to finish first. A clean boundary is earned, not declared.

## Where the handoff goes — one unique file per compaction, in the active plan's folder

Every compaction writes a **NEW** file. Never overwrite. Never a single rolling "LATEST". This keeps the full handoff history per plan, so multiple compactions during one effort never erase each other.

1. **Find the active plan folder.** Prefer the plan this session is actively working on (you usually know it from context). If unclear, auto-detect — the most-recently-modified plan file's parent directory:
   ```bash
   find plans -type f -name '*.md' -not -path '*/_archive/*' -not -path '*/_dashboard/*' -printf '%T@\t%p\n' 2>/dev/null | sort -rn | head -1
   ```
   `--plan <path>` overrides either.
2. **Placement.** If the plan has a dedicated folder (e.g. `plans/app/VECTOR-TO-TILE-RENAME/`), write the handoff **into it**. If the plan is a loose file directly under `plans/<repo>/` (no project folder), fall back to `plans/_dashboard/handoffs/`.
3. **Filename is unique per compaction:** `handoff-<YYYY-MM-DD>-<HHMM>.md` (date + time, so same-day compactions don't collide). If that exact name already exists, append `-2`, `-3`, … — **never clobber an existing handoff**.

The newest `handoff-*.md` in a folder is the de-facto current one for that plan. Resume uses the exact path (echoed in step 6), not a rolling pointer. Legacy `handoff-LATEST.md` files from older versions are left in place, not migrated or overwritten.

## The handoff artifact

Write the unique file per the rules above. Use this exact skeleton; fill every field, delete none:

```markdown
# Forward Handoff — <subject>

**Written:** <YYYY-MM-DD, session seam>  ·  **Resume by:** reading this file, then doing ▶ NEXT ACTION.

## 🎯 Mission
<1–2 lines: the north star of the current work. Why we're doing this, what "done" looks like.>

## ▶ NEXT ACTION  (do this first)
<The single, concrete, immediately-executable next step. Specific enough to start without thinking:
exact command / file / function / decision. Not "continue the work" — the actual move.>

## 📍 State now
- **Done:** <committed units, with commit hashes where useful>
- **In flight:** <anything started-not-finished, or "nothing — clean seam">
- **Git:** <branch · clean/dirty · last commit hash + subject · pushed?>

## 🗂 Working set
<Key files + line refs currently in play — path:line, one per line, with a 3-word "why".>

## 🔒 Decisions locked  (do NOT re-litigate)
<Choices already settled this session. Each: the decision + one-line reason. Stops the next session re-debating them.>

## ⚠️ Gotchas
<Traps discovered this session: the non-obvious thing that wasted time, so it isn't re-hit. Be concrete.>

## 🚫 Out of scope / do-not-touch
<Paths, actions, refactors explicitly NOT part of this work. Guardrails against wandering.>
```

The ordering is deliberate: **NEXT ACTION sits above the backward state** because the next session reads top-down and should be executing within seconds.

## Procedure

1. **Check the seam.** Assess the boundary against the criteria above. If not safe, STOP — report the one thing to finish first (offer to do it), do not write a handoff against dirty mid-task state.
2. **Capture git state.** `git status -s` + `git log -1 --oneline` + branch + pushed?/ahead. This is the spine of "State now".
3. **Distill, don't dump.** Fill the skeleton. NEXT ACTION must be executable cold. Working set = only files that matter for the next step. Pull Decisions/Gotchas from THIS session's reasoning — that's the knowledge a backward summary loses.
4. **Write the unique handoff file** in the active plan folder per the "Where the handoff goes" rules (create the dir if missing). NEVER overwrite an existing handoff — on name collision, increment the `-N` suffix.
5. **Echo a 4-line preview** to the user: Mission, ▶ NEXT ACTION, git state, and the **exact handoff path** just written.
6. **Hand the trigger back** with that exact path:
   > Handoff written → `<plan-folder>/handoff-<YYYY-MM-DD>-<HHMM>.md`. Compact now with:
   > `/compact read <plan-folder>/handoff-<YYYY-MM-DD>-<HHMM>.md and continue from ▶ NEXT ACTION`

## After compaction (resume contract)

The next session's first action is: **read the exact handoff path from the compact instruction, then execute ▶ NEXT ACTION.** If the path isn't handy, read the newest handoff in the active plan folder — `ls -t <plan-folder>/handoff-*.md | head -1`. Do not re-summarize, do not re-explore — the handoff IS the orientation. If the custom `/compact read <path>` instruction above was used, this is automatic.

## Rules

- **Never run `/compact` yourself** — produce the handoff, hand the trigger to the user.
- **Never write a handoff against dirty mid-task state** — a forward-compact points at a committed seam. Finish + commit, or capture why-dirty explicitly, first.
- **NEXT ACTION is mandatory and must be concrete** — if you can't name the next move, the work isn't at a seam; say so.
- **Distill, never dump** — the value is signal density, not a transcript. A backward summary already exists; this adds the *forward* delta.
- **Never overwrite a handoff — unique per compaction** — every compaction writes a new `handoff-<date>-<time>.md` in the active plan folder. The history is the audit trail; the newest file is the resume target. (Legacy `handoff-LATEST.md` files are left in place, not migrated.)
