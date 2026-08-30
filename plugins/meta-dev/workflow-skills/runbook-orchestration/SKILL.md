---
name: runbook-orchestration
description: Stand up and drive a campaign runbook — a single orchestration manuscript that sequences multiple related plans by dependency and farms host-native member conductors through the 6-stage waterfall in file-disjoint parallel waves, with a live computed dashboard. Use when coordinating a multi-plan feature arc (not a single plan — that's /meta-dev). Invoked by the /runbook command.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, TaskCreate, TaskUpdate]
---

# Runbook Orchestration Skill

A **campaign runbook** is the orchestration layer **above a single plan**. `/meta-dev` drives ONE
subject through Brainstorm→Design→Plan→Harden→Execute→Review. A runbook drives **N related plans**
through that waterfall in dependency order, with one live dashboard tracking the whole arc.

```
plans/meta-runbook.md          META live ledger (lean Sequence + milestones; keep ~≤150 lines)
plans/meta-runbook-archive.md  Cold Shipped history (not routine context)
  └─ _runbook-YYYY-MM-DD.md     CAMPAIGN runbook — sequences N member plans, drives the waterfall  ← THIS skill
       └─ plan dirs/files        individual plans — each driven by a member conductor following /meta-dev or /meta-execute
            └─ - [ ] tasks         checkboxes (per phase / per task)
```

**When a runbook, not a plan?** When the work is a *set* of interdependent plans that must land in a
specific order (a feature arc, a launch wave, a migration spanning subsystems). One plan → `/meta-dev`.
A trio of plans with a dependency DAG and a shared acceptance story → a runbook.

**What the runbook owns** that nothing else does: the **cross-plan execution order** (topo-sorted from
each member's `depends`/`blocks` frontmatter), the **wave strategy** (which members can run in parallel
by file-footprint disjointness), the **campaign-level gates/invariants**, and a **live computed
progress dashboard** embedded in the file.

**What the runbook does *not* own:** checkbox implementation, per-task commits, inner parallel waves.
Those belong to `/meta-execute` (and `/meta-dev` for stages 1–4), run by a **member conductor** child.
This thread is the campaign conductor. It farms members. It does not type member source.

Do **not** flatten a campaign into a host-specific workflow script (Grok Rhai or otherwise). The
`_runbook-*.md` file plus `planctl` is the SSOT on every host.

---

## Lifecycle (the verbs `/runbook` dispatches)

### `new <feature-dir | plan-paths…>` — scaffold a runbook
1. Resolve the member set: a feature dir (e.g. `plans/app/UNIFIED-EDITING-CANVAS/`) → its tracked
   master files (`00-master-plan.md`/`00-design.md`/dated masters; never `phase-*.md`), or an explicit
   list of plan paths.
2. Read each member's frontmatter `depends`/`blocks` and **topologically sort** into an execution
   order. Cycles or missing deps → STOP and surface; never guess an order.
3. Detect parallelizable waves: members with **disjoint file footprints** (grep their write-sets) may
   share a wave; any shared file → serialize. Footprint analysis is judgment work — note assumptions.
4. Scaffold `_runbook-<today>.md` in the feature dir from `references/runbook-template.md`: write the
   frontmatter (`type: runbook`, ordered `members:`, `predecessor:` if chaining), the
   ≤3-sentence purpose header, the dashboard sentinels, and the `## DEPENDENCY ORDER` +
   `## GATES & INVARIANTS` contract. Do NOT author PACKAGE / LIVE STATUS / queued-summaries /
   CURRENT phase-tracker / HIGHER CONCEPT sections — the runbook is exactly 3 zones.
5. Run `scripts/runbook-render.py <file>` (shim over `planctl runbook render` — the unified state layer) to fill the computed PROGRESS block.
6. **Register in the META runbook** (see below).

### `(no verb) | status | refresh` — recompute the dashboard
Run `scripts/runbook-render.py <runbook>` (shim over `planctl runbook render`) to refresh the PROGRESS block from members' **live**
frontmatter + checkboxes. Pure read→compute→write-one-span; safe to run anytime. This is the
"dashboard like /meta-dashboard" surface, scoped to the campaign.

### `execute | go` — drive the sequence (EXECUTE-gated)

**You are the campaign conductor. You do not implement member tasks on this thread.**

`/runbook execute` / `go` **is** the campaign go for every non-sensitive member. Re-ask only for
auth / schema / payment / cross-repo / destructive members (protocol `sensitive`). A runbook never
auto-starts Stage 5 without that go. Design / plan / harden waves are free.

#### 1. Inventory + tracker

Read `members` in order. For each member, record stage, `depends`/`blocks`, and the **declared
write-set** (plan Files / anchors). Recompute waves from live footprints — do not blindly trust the
authored wave list if files moved.

`TaskCreate` **one entry per member** (`<id> — <why> [Grok|Claude|spark|sol]`). Keep it live with
`TaskUpdate`. This is the campaign tracker. Inner checkbox lists belong to each member conductor.

#### 2. Host dispatch — native to THIS host

Farm a **member conductor** (not a checkbox worker) per READY member. Missing a mapping is a
host-table bug, not permission to implement the member here. `--inline` does not exist on `/runbook`.

| This host | Member conductor | How |
|-----------|------------------|-----|
| **Grok Build** | `spawn_subagent` | `subagent_type: general-purpose`, **pick grok-4.5 vs grok-4.6**, `background: true`. Brief a **direct task**. Never "run `/meta-execute`". Codex Terra/Sol when that family is the better fit. |
| **Claude Code** | pooled Grok / Codex | Background. `Execute /meta-execute <plan>` or `Execute /meta-dev --to 4 <plan>` is legal **on this host only**. The child follows `references/work-ladder.md` (Grok + Codex — do not stay local; DeepSeek paused). |
| **Codex** | `codex exec` | Member conductor = **sol / high**. Inner mechanical checkboxes may be spark. Inline the execute procedure; never "read the master and reconstruct." |

Shape the brief for that backend (`references/execute-briefs.md` → Campaign member conductor).

#### 3. Safe parallel waves (member grain)

**Parallelize when it is safe. Serialize when it would collide.** Do not walk `members` one-at-a-time
if two READY members can run together.

A member is **READY** when all of these hold:
1. Every `depends` predecessor is releasable at the stage this wave needs (execute wave: predecessor
   Stage 6 DONE, or the authored gate).
2. Its **declared write-set is disjoint** from every member conductor (and fixer) currently in flight
   from this run.
3. It is not blocked / parked / waiting on a `TASK_RED` parent member.
4. Execute wave: member is HARDEN-clean (stage ≥ 4, that stage passed). Else dispatch a stages-1–4
   conductor instead (`commands/meta-dev.md`, halt at 4).

**Dispatch:** spawn every currently-READY member as a fresh host-native member conductor, up to the
in-flight cap (**3** member conductors from this run). As each child returns, immediately fill the
empty slot with the next READY member. Do not wait for the whole wave to drain.

**Why 3:** each member conductor may farm up to **8** checkbox workers (`/meta-execute`). Three
members → ~24 writers, inside the 4–20 concurrent-agent band. Four member-executes in flight is too
many git writers on a shared worktree. Nested checkbox parallelism is the child's job. Do not also
flatten those checkboxes onto this thread.

**Serialize (do not co-dispatch) when ANY of:**
- Declared write-sets overlap (same path in two members).
- `--serial`.
- `--glm` on a member (never two GLM member conductors).
- Unknown / undeclared write-set — treat as overlapping; do not guess.
- Sensitive member waiting on a fresh human confirm.

Dirty leftover from an **in-flight** peer on an overlapping path → wait for that child (it will
commit). Unrelated dirty files → **commit them as their own discrete commit and keep moving**
(Rule #2). Never stash. Never skip the member because the tree is busy.

#### 4. Member brief (every spawn)

Self-contained. The child does not share this session's memory.

Include:
- Absolute plan path + absolute repo roots.
- Which procedure to follow, as a **file to read**, not a slash:
  - Execute-ready → read `commands/meta-execute.md` completely and run it for that one plan.
  - Not yet hardened → read `commands/meta-dev.md` and drive stages 1–4 only, then stop.
- Git: no rebase / stash / `add -A` / `commit -a` / bare commit. Form:
  `git -C <ABS> add -- <paths> && git -C <ABS> commit --only -m "…" -- <paths>`. Never push.
- Commit-on-red if any declared file was edited.
- Focused verify only; no repo-wide suite.
- Farm inner checkboxes with **that host's** worker primitive (`spawn_subagent` / `Agent` / spark-or-sol).
- Forward `--review` / `--budget` when the user passed them on `/runbook execute`.
- Return this block:

```
STATE: DONE | BLOCKED | RED
PLAN: <path>
STAGE: <n>
SHA: <or n/a>
SURPRISES: one line or none
```

**Claude-only:** `Execute /meta-execute <plan>` is fine. **Grok and Codex:** do not send a slash command. They cannot run it.

#### 5. Oversight on each return

Do not wait for the whole wave. On every child return:
1. `TaskUpdate` that member.
2. Re-render: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runbook-render.py <runbook>` (heed stderr
   `⚠ stage-drift`).
3. Commit the dashboard if it changed: `git -C <ABS> add -- <rb> && git -C <ABS> commit --only -m "chore(runbook): refresh dashboard" -- <rb>`.
4. Write member closeout into that member's `00-master-plan.md` `## Closeout` (never the runbook).
5. Fill the next READY slot.
6. Context watchdog every 3 completed members and at every campaign review seam:
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context-gauge.py`. On `CONTEXT_VERDICT=OVER` pause and
   `/meta-compact` forward before the next dispatch.

The Stop hook also re-renders every campaign runbook at end of turn. Mid-run render keeps the live
dashboard from freezing on a long arc.

A member `TASK_RED` parks **that member and its dependents**. Independent READY members continue.

#### 6. Campaign review

When the last execute-ready member lands, the campaign is not done until each member has a review
verdict on record (`planctl review` / `/meta-execute` step 6). Do not add a second campaign-wide
diff-read on this thread. If a member returned without a review, dispatch a host-native reviewer
for **that member only**.

> **Dashboard auto-syncs during member execution.** `/meta-execute` re-renders THIS runbook at every
> phase gate (loop-protocol → "Runbook dashboard sync") in addition to the return render above.

### `chain <new-feature/label>` — daisy-chain a successor
When an arc completes (or a new arc breaks off a landed foundation), create a successor
`_runbook-<today>.md` with `predecessor:` = the current runbook, and set the current runbook's
`successor:` + `status: done`. The successor's narrative opens "builds on that **landed** foundation"
(the 06-26 → 06-28 pattern). Use this to (a) keep a finished campaign's record immutable while a new one
starts, or (b) split an over-large runbook into a focused successor.

### `add <plan>` / `done <plan>` / `archive`
- `add` — insert a plan into `members` at the dependency-correct position; re-render.
- `done` — flip the member's own frontmatter + write its `## Closeout` into the member's `00-master-plan.md`; re-render. No closeout prose in the runbook.
- `archive` — when ALL members are `done`: mark the runbook `status: done`, drop its META-runbook
  marker + members from live `## Sequence`, append one compact line to `plans/meta-runbook-archive.md`,
  and (per repo convention) move the campaign to `_archive/` if the whole arc is shipped. Never
  delete a runbook; never re-paste closeout novels into live `meta-runbook.md`.

---

## Registration in the META runbook (`plans/meta-runbook.md`)

A campaign registers as a **`=== RUNBOOK: <path> · <label> ===` marker** placed in `## Sequence`
immediately above its member plan entries:

```
=== RUNBOOK: plans/app/UNIFIED-EDITING-CANVAS/_runbook-2026-06-28.md · UEC Toolbar+Provenance arc ===
plans/app/UNIFIED-EDITING-CANVAS/17-REPLAYABLE-PROVENANCE/00-master-plan.md
plans/app/UNIFIED-EDITING-CANVAS/16-TOOLBAR/followup-1/00-design.md
…member plans, in runbook order…
```

- The **member plans stay the tracked Sequence units** — the global `/meta-dashboard` counts real
  per-plan progress (the marker line starts with `===`, so `plan-index.py` never mistakes it for a
  plan path).
- The marker is the **pointer + grouping**: it says "these next plans are driven by that campaign
  runbook." Position relative to the `=== MILESTONE: PRODUCT LAUNCH … ===` marker decides pre/post
  launch, same as any plan (the host project contract defines meta-runbook geography).
- Campaign runbook files (`_runbook-*.md`) are themselves **excluded** from the plan scan
  (`plan-index.py` NOISE) — they are orchestration manuscripts, not plans, and carry the campaign
  dashboard in-file.

---

## Gates & invariants (binding)

1. **Order is binding.** `members` order = dependency order, topo-sorted from `depends`/`blocks`.
   READY waves may skip ahead of a blocked sibling; they never skip an unmet `depends`. Never
   reorder without amending the runbook + re-rendering.
2. **EXECUTE is gated.** `/runbook execute` / `go` is the campaign go. Design/plan/harden are free.
   `chain`/`new`/`refresh`/`add`/`done` are non-gated authoring/bookkeeping. Sensitive members still
   re-ask.
3. **The PROGRESS block is computed, not hand-edited.** Author everything else; let
   `runbook-render.py` own the sentineled span. Status truth lives in member frontmatter + checkboxes.
4. **File-level exclusion, not session-level.** Multiple member conductors MAY run concurrently —
   that is the default. Overlapping write-sets serialize. Cap **3** in-flight member conductors.
   Unrelated dirty files: commit discrete, keep moving. Never a tree-wide `git add`. Never stash.
5. **Daisy chain is immutable backward.** A completed runbook is never rewritten; a successor links to
   it via `predecessor`. The chain is the campaign's history.
6. **Self-maintaining rule.** A runbook has exactly 3 sections: the header (frontmatter + ≤3-sentence
   purpose), the computed `## 🎯 DASHBOARD`, and the `## DEPENDENCY ORDER` + `## GATES & INVARIANTS`
   contract. Never append run history to a runbook. Never hand-author a per-member block. If you'd write
   more than one line about a member, it goes in that member's `00-master-plan.md` `## Closeout`. The
   dashboard is regenerated by `runbook-render.py`, never hand-edited.
7. **This thread does not implement.** Campaign conductor farms member conductors. Member conductors
   farm checkboxes. Flattening either layer onto this thread is a bug.

---

## Delegation

Authoring a runbook (`new` / topo-sort / wave notes / `chain`) stays on **this session**. Driving
members uses the **Host dispatch** table above — always host-native member conductors.

Inner execute follows `/meta-execute` and `references/work-ladder.md`. Do not restate the ladder
here. Do not pin campaign authoring to Opus — Grok 4.6 and Codex Sol author just as well.

Gate reviews stay cross-family as the execute/harden commands already specify. The campaign
conductor does not read diffs.

References: `references/runbook-template.md` (skeleton + frontmatter schema + dashboard contract);
`commands/meta-execute.md` (member execute); `references/execute-briefs.md` (member-conductor brief).
