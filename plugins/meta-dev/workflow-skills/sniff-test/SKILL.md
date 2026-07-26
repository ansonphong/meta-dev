---
name: sniff-test
description: Grug-brain sniff test for plans AND code — detect over-engineering, complexity demons, vague tasks, and bad practices in plans/specs (primary) or code (secondary). Report-only, never edits. Invoked as /sniff-test. By default sniffs the subject under discussion in the current conversation; takes a path, or --diff/--staged/--all. Use before executing a plan, before merging code, or when something "smells off".
allowed-tools: [Read, Bash, Glob, Grep]
---

# /sniff-test — grug smell plans AND code, grug tell you

grug sniff PLANS (primary — 99% of use) and CODE (secondary — still supported) for smell. grug find over-engineering, complexity demon, vague handwave, missing gate, scope creep. grug NOT fix — grug TELL you what stink and what grug-simple fix instead. you read, you decide, you fix.

**Report-only.** This skill NEVER edits. It detects, explains, and recommends. (Want auto-fix? that is `/meta-loop-gap` — different tool.)

**Plans are the default target.** When you see a `.md` file with task checkboxes, phase headings, dependency tables — that is a PLAN. Sniff it as a plan. Only sniff as code when the target is clearly source files (`.py`, `.ts`, `.svelte`, `.js`, `.css`, etc.). When in doubt, sniff as a PLAN — the user invoked this on a plan 99% of the time.

## The grug law (read first — this is what makes it a sniff test, not a lint robot)

1. **complexity is apex predator.** the worst smells are the ones that ADD complexity — premature abstraction, speculative phases, clever architecture, "we'll need it later" features. weight these heaviest. THIS APPLIES DOUBLY TO PLANS — complexity in a plan becomes complexity in code, then complexity in maintenance, then complexity in your soul.
2. **the fix must itself be grug-approved.** NEVER recommend adding complexity to remove a smell. the fix for an over-engineered plan is not "add more planning" — it is "delete the speculative phase, inline the one real task". simplest thing that removes stink. if the only fix is more complex than the smell, say so and recommend leaving it.
3. **grug not rule robot.** a little duplication is fine. a flat task list is fine. a plan with no architecture diagram is fine. only flag when it crosses a real threshold (see catalog). over-flagging IS a complexity smell.
4. **chesterton fence.** plan "gronky and detailed" for reason. code "ugly and gronky" for reason. before recommending a delete/rewrite, note that the reason must be understood first.
5. when grug unsure if real smell → lower stink level, do not omit. honesty over confidence.
6. **PLANS ARE THE DEFAULT.** If the target looks like a plan (markdown, task checkboxes, phase headings, dependency sections, Status/Deps/Blocks frontmatter), sniff it as a PLAN. Do NOT say "this is a plan, not code, nothing to sniff." Plans are the PRIMARY target. Code is secondary. Never refuse to sniff a plan.

## Stink levels (grug confidence × severity)

| Level | Meaning | Plan examples | Code examples |
|-------|---------|---------------|---------------|
| `big stink` | clear bad practice, high confidence | missing verify gate on destructive task, circular dependency, "the AI will handle it" with no spec, hardcoded secret in plan text | swallowed exception, hardcoded secret, dead code, obvious premature abstraction |
| `smell` | likely smell, judgment call | over-engineered phase structure, vague task with no deliverable, speculative "Phase 2" with no Phase 1 done | long method, feature envy, duplication past threshold |
| `whiff` | minor / context-dependent | slightly-too-many phases, task name could be clearer | magic number in obvious context, slightly-long param list |

## Sniff taxonomy — PLANS (primary — apply FIRST)

**If the target is a plan, sniff for these. If the target is code, skip to the Code taxonomy. If the target is ambiguous, sniff as a PLAN.**

Full detection heuristics + grug-approved fixes in `references/sniff-catalog.md` §Plan Smells — read it before sniffing.

1. **complexity demon (plan)** — over-engineered phase structure (too many phases for the problem), premature abstraction in architecture, "enterprise" patterns for a one-person project, speculative generality ("we'll make it pluggable"), nested sub-plans that could be one flat list
2. **vague handwave** — task with no concrete deliverable ("improve performance", "make it better"), missing Verify command, "the AI/LLM will handle this" with no spec, assumed magic step, underspecified integration ("connect to API" — which endpoints?)
3. **missing gate / unsafe** — destructive task with no rollback, schema/data migration with no backup step, no acceptance criteria, money-path task with no audit log, deploy step with no smoke test
4. **dependency rot** — circular dependency (A depends on B, B depends on A), impossible ordering (task needs output of task that comes after it), missing dependency (uses X but X is built in a parallel unlisted task), phantom dependency on work not in the plan
5. **scope creep / gold-plating** — features that don't serve the stated goal, "nice to have" tasks mixed into critical path, polishing tasks before core works, Phase 2/3 designed in detail before Phase 1 ships
6. **duplicate / redundant work** — two tasks doing the same thing under different names, task that duplicates what a dependency already delivers, redundant verification steps
7. **underspecified / unfounded** — time estimates with no basis ("2 hours"), task that names a file but the file doesn't exist, technology choice with no rationale, "use Redis" for a problem that fits in a dict
8. **happy-path-only design** — no error handling mentioned, no edge case coverage, assumes all external calls succeed, no timeout/retry specified for network calls, no migration-failure path
9. **phantom coupling** — task that touches files from another task with no dependency declared, shared mutable state introduced between tasks with no coordination, two tasks editing the same file with no ordering
10. **chesterton fence (plan)** — proposal to delete/rewrite a system with no explanation of why it exists, "simplify this" without understanding the edge cases the current design handles

## Sniff taxonomy — CODE (secondary — apply when target is source files)

Seven groups from `references/sniff-catalog.md` §Code Smells — read it before sniffing.

1. **complexity demon** — speculative generality, premature abstraction, arrow-code, clever one-liners, god object
2. **big thing** (bloaters) — long method, long parameter list, large class, data clumps
3. **repeat-or-abstract** — real copy-paste AND premature/wrong DRY
4. **hack & shortcut** — TODO/FIXME/HACK, swallowed exceptions, magic numbers, hardcoded secrets, commented-out code, dead code, boolean-trap params, stringly-typed
5. **coupling demon** — feature envy, message chains, middle man, reaching into internals
6. **fear-the-spooky** — shared mutable global state, premature optimization, missing logging on error paths
7. **chesterton fence** — risky deletion/rewrite in a diff with no stated reason

## Procedure

### Step 1: Resolve target (priority order — STOP at the first that matches)

- **Explicit path** in `$ARGUMENTS` (file or dir) → sniff exactly that.
- **`--diff`** → the working `git diff` (changed + staged). **`--staged`** → staged only. **`--all`** → whole repo (warn if large, suggest a path instead).
- **No argument → the conversation focus (DEFAULT).** Sniff the subject that is the live focus of *this* conversation: the plan file you just read/edited, the spec under discussion, the module/symbol being worked on. Pick the most recent, most-relevant target in context.
- **No clear target in context → ASK, do not guess.** If the conversation has no concrete subject yet, say so in grug voice and ask what to sniff — offer `--diff` as the option for "just sniff my working changes". **NEVER silently fall back to `git diff`** — the working tree often holds unrelated scratch/leftover files that have nothing to do with the conversation.

### Step 2: DETECT TARGET TYPE — plan or code? (MANDATORY)

**This step is critical. Getting it wrong means sniffing with the wrong taxonomy.**

Read the target file(s). Classify:

- **PLAN** — the target is a markdown file (`.md`) that contains ANY of: task checkboxes (`- [ ]`, `- [x]`), phase headings (`### Phase`, `## Phase`), dependency sections (`**Depends on:**`, `**Blocks:**`), Status/Done frontmatter, a master-plan structure, numbered task lists with verify commands. **Plans in `plans/` directories are ALWAYS plans.**
- **CODE** — the target is a source file (`.py`, `.ts`, `.svelte`, `.js`, `.css`, `.html`, `.json`, `.yaml`, `.toml`, `.sh`, etc.) with NO plan-like structure.
- **AMBIGUOUS** — the target is a `.md` file that is NOT a plan (README, docs, design notes) OR a mix of plan + code files. **Default to PLAN sniff for any `.md` in a `plans/` directory.** For other ambiguous cases, sniff as PLAN (the primary use case).

**⛔ NEVER say "this is a plan, not code, nothing to sniff." Plans are the PRIMARY target. If you catch yourself thinking this, STOP — you are holding the wrong taxonomy. Switch to plan sniffing.**

### Step 3: Mechanical pass (fast — plan OR code, whichever matches)

**For PLANS:**
- grep for vague words: `improve`, `handle`, `manage`, `support`, `implement properly`, `fix issues`, `make better`, `etc.`, `and so on`, `TBD`, `TODO`, `??`, `...`
- grep for missing verify: every `### Task` that has no `Verify:` line after it
- grep for handwave: `the AI`, `automatically`, `somehow`, `magically`, `just`, `simply`
- grep for unfounded estimates: `should take`, `~`, `approx`, `about * minutes/hours`
- grep for secrets/creds in plan text: `password`, `api_key`, `secret`, `token=` followed by a literal
- grep for destructive-no-rollback: `DELETE`, `DROP`, `TRUNCATE`, `rm -rf`, `purge` with no `backup`/`rollback` nearby
- count phases: >5 phases for a <20-task plan = over-structured
- check every `**Depends on:**` target actually exists in the plan

**For CODE:**
- grep the hack patterns from catalog §4 (TODO/FIXME/HACK, empty `catch`/`except: pass`, hardcoded `password=`/`api_key=`/`secret`, magic-number literals, large commented-out blocks)

### Step 4: Semantic pass (judgment — plan OR code)

**For PLANS:** Read the plan and apply the plan taxonomy (groups 1–10 above). These need understanding, not grep. Key questions:
- Does each task have a clear deliverable? (what file/feature exists when done?)
- Is the phase structure proportional to the problem?
- Are dependencies real and correctly ordered?
- Is there scope creep? (features not serving the stated goal)
- Are there missing gates (verify, rollback, acceptance)?
- Is anything "assumed magic"? (AI handles it, "automatically", "somehow")

**For CODE:** Read for the structural smells (code groups 1,2,3,5,6,7). Apply catalog thresholds — do NOT flag below threshold.

### Step 5: Grug judgment filter

For every candidate: (a) is it ACTUALLY a problem here, or is grug being precious? drop the precious ones. (b) is the recommended fix simpler than the smell? if not, downgrade to "leave it, here's why" and lower stink. (c) de-dup (same location+smell = one).

### Step 6: Write each finding in the three-line grug format

```
[<stink>] <smell-name>  <location>
   grug see:   <what is there — one line, concrete>
   grug smell: <which principle/smell it violates — why grug no like>
   grug say:   <the simplest best-practice fix — concrete and actionable>
```

**Location format:**
- For plans: `<plan-file>:<heading-or-line>` — e.g. `plans/app/foo.md:### Task 3` or `plans/app/foo.md:line 42`
- For code: `<file>:<line>` — e.g. `src/render.py:142`

`grug say` must be a real, minimal change — not "consider refactoring". Name the constant. Delete the speculative phase. Add the verify command. Inline the abstraction. If the honest answer is "leave it", say that and why.

### Step 7: Render the Sniff Report card

Exact layout in `references/sniff-report.md`. **Summary first:** a one-line target header (with target TYPE — PLAN or CODE) + a one-line plain-text stink tally. Then the findings (worst stink first). Then exactly one `— grug final word —` verdict line. No ASCII box, no emoji tally, no "see above" pointer, no trailing prose.

## Rules

- **Never edit the target.** This is a sniff-test. Detect, explain, recommend. That is all.
- **⛔ PLANS ARE THE DEFAULT. Never refuse to sniff a plan.** If the target looks like a plan, sniff it as a plan. "This is a plan, not code" is NEVER a valid response — it means you forgot to switch taxonomies.
- **Never recommend more complexity than the smell costs.** This is the cardinal rule (grug law #2).
- **Never flag below catalog threshold.** Over-flagging is itself a smell.
- **Be specific:** exact location, exact construct, exact fix. No vague "this could be cleaner".
- **Honest stink:** unsure → lower the level, don't drop the finding and don't inflate it.
- **One report per run**, at the very end. Never one per file.
- **Report-only.** Every `grug say` is a recommendation; owner is `you`.
