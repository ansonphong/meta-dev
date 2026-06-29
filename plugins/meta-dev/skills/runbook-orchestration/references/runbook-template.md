# Campaign Runbook — Template, Frontmatter Schema & Dashboard Format

This is the canonical skeleton + contract for a **campaign runbook** (`_runbook-YYYY-MM-DD.md`).
`/runbook new` scaffolds from it; `scripts/runbook-render.py` owns the computed progress block;
humans author the narrative around it.

> **Terminology — do not conflate.**
> - **META runbook** = `plans/meta-runbook.md` — the ONE global, cross-repo editorial ledger
>   (`## Sequence` + milestones). `plan-index.py` calls this "the runbook."
> - **Campaign runbook** = `_runbook-YYYY-MM-DD.md` — a per-arc orchestration manuscript that
>   sequences N member plans and drives them through the waterfall. THIS file is one of those.

---

## 1. Frontmatter schema (REQUIRED — this is what makes a runbook discoverable + chainable)

```yaml
---
type: runbook              # REQUIRED literal — marks this file a campaign runbook
status: active             # active | done
repo: app                  # app | www | gallery | meta
stage: 5                   # the lead stage of the campaign (1-6); informational
feature: UNIFIED-EDITING-CANVAS   # the arc / campaign name (usually the parent dir)
updated: 2026-06-29        # YYYY-MM-DD, refreshed by runbook-render.py
why: one-line campaign goal
members:                   # ORDERED execution sequence — the heart of the runbook.
  - plans/app/UNIFIED-EDITING-CANVAS/17-REPLAYABLE-PROVENANCE/00-master-plan.md
  - plans/app/UNIFIED-EDITING-CANVAS/16-TOOLBAR/followup-1/00-design.md
  - plans/app/UNIFIED-EDITING-CANVAS/21-UPSCALE-FLOW/00-master-plan.md
  - plans/app/UNIFIED-EDITING-CANVAS/18-LOADABLE-RENDER-CONFIG/00-master-plan.md
  - plans/app/UNIFIED-EDITING-CANVAS/20-IMAGE-OFFSET/00-master-plan.md
predecessor: plans/app/UNIFIED-EDITING-CANVAS/_runbook-2026-06-26.md   # daisy-chain back-link, or null
successor: null            # forward-link, set when a successor runbook breaks off
---
```

- `status`/`stage`/`repo` are the same three keys `plan-index.py` requires of any tracked file, so a
  runbook is self-describing even though it is **excluded** from the plan scan (it is not a plan).
- `members` is an **ordered** list (topologically sorted from each member's `depends`/`blocks`
  frontmatter at `new` time). Order = execution order. Each entry is the member's tracked file
  (its `00-master-plan.md` / `00-design.md` / dated master).
- `predecessor`/`successor` form the **daisy chain** (see SKILL.md → Daisy-chaining).

---

## 2. Manuscript skeleton

```markdown
# <FEATURE> Runbook — YYYY-MM-DD · <one-line theme>

**Status:** ACTIVE — orchestration manuscript for <member id list>.
**Updated:** YYYY-MM-DD
**Scope:** <member plan paths / what this campaign drives>
**Predecessor:** _runbook-<prev>.md  (drove <prev arc>; this builds on that landed foundation)

## 🎯 LIVE EXECUTION DASHBOARD

> **Updated live as each phase lands.** <execution-mode note — serial/parallel, gating>
> The **Stage** column = the plan's waterfall stage (①BRAINSTORM ②DESIGN ③PLAN ④HARDEN ⑤EXECUTE ⑥REVIEW). **✅ DONE only at Stage 6** — a merely-planned/hardened plan shows its stage, not DONE. Status: ✅ done · 🔄 executing now (◄ NOW) · ⬜ queued · ! blocked.

<!-- RUNBOOK:PROGRESS:START — computed by scripts/runbook-render.py; do not hand-edit between sentinels -->
### Execution order & package progress

> **17** ✅ → **16** ✅ → **21** ✅ → **18** 🔄 → **20** ⬜ → **Stage 6** ⬜

**Plans done:** 3 / 5  ·  **Now:** 18-LOADABLE-RENDER-CONFIG — Stage 5 EXECUTE (1/6 phases)

| # | Plan | Stage | Phases | Progress | Status |
|:--:|------|------|:------:|----------|:------:|
| 1 | **17** REPLAYABLE-PROVENANCE | ⑥ REVIEW | 6/6 | `▰▰▰▰▰▰▰` | ✅ DONE |
| 2 | **16** TOOLBAR followup-1 | ⑥ REVIEW | 3/3 | `▰▰▰▰` | ✅ DONE |
| 3 | **21** UPSCALE-FLOW | ⑥ REVIEW | 7/7 | `▰▰▰▰▰▰▰` | ✅ DONE |
| 4 | **18** LOADABLE-RENDER-CONFIG ◄ NOW | ⑤ EXECUTE | 1/6 | `▰▱▱▱▱▱` | 🔄 EXECUTING |
| 5 | **20** IMAGE-OFFSET (tail) | ③ PLAN | 0/8 | `▱▱▱▱▱▱▱▱` | ⬜ QUEUED |
| — | **Stage 6** review · archive · runbook | — | — | `▱▱▱▱` | ⬜ QUEUED |
<!-- RUNBOOK:PROGRESS:END -->

### ◄ CURRENT — `21-UPSCALE-FLOW` phase tracker

> <one-line current-plan note — what it builds, how each phase lands>
> Authored (with commit SHAs); NOT computed — the script owns only the PROGRESS block above.

- [x] **P1** — <what it built>  ·  app `<sha>` · meta `<sha>`
- [ ] **P2** — <what it builds>
- [ ] **INT** — <acceptance capstone>

### Queued plan summaries (expanded into a phase tracker when each becomes current)

- **18 LOADABLE-RENDER-CONFIG** — <one-line scope + backend tier>
- **20 IMAGE-OFFSET** — <one-line scope + backend tier>
- **Stage 6** — per-plan /meta-eval, context sync, archive each plan, move META-runbook Sequence→Shipped.

---

## 0. THE HIGHER CONCEPT
<the unifying idea the campaign converged on — 1-3 short paragraphs>

## 1. THE PACKAGE (one executable unit, N plans)
<table: # | Plan | What | Status — one row per member>

## 2. DEPENDENCY ORDER (why this sequence)
<the topo order + rationale; an ASCII DAG; independence/parallelism notes>

## 3. GATES & INVARIANTS (binding)
<numbered list: design-first, sacred formats, serial-execution, acceptance tests>

## 4. LIVE STATUS
<table: Plan | Stage | Next action | Owner — the per-plan next-move ledger>
```

---

## 3. The computed PROGRESS block — contract for `runbook-render.py`

The script owns **only** the text between `<!-- RUNBOOK:PROGRESS:START ... -->` and
`<!-- RUNBOOK:PROGRESS:END -->`. It is **idempotent** (re-running with no member changes is a no-op)
and writes **only** that span — never the narrative, never the CURRENT phase tracker (which carries
human-authored SHAs and notes).

**Two independent signals per plan — DONE is stage-gated.** Each row shows BOTH:
- the **waterfall stage** (its own `Stage` column) from the plan's `stage:` frontmatter (1..6),
  rendered as a circled glyph + name (③ PLAN, ④ HARDEN, ⑥ REVIEW);
- the **phase progress** (the `Phases` count + `Progress` bar) from the plan's internal
  `phase-*.md` files + checkbox completion — i.e. how far *execution* has gotten within the plan.

**✅ DONE appears ONLY for members at Stage 6 with a done/completed status.** A `status: done` at
an earlier stage means *that stage's* work is done (e.g. planning/hardening), NOT that the plan
shipped — so it reads as its stage (③ PLAN / ④ HARDEN), never DONE. This is the whole point: the
dashboard never says DONE for a plan that has only been planned or hardened. "Plans done" counts
only Stage-6-done members.

Per member plan it derives, reusing `plan-index.py` (`read_plan_file`, `parse_frontmatter`,
`count_checkboxes`):

| Field | Source |
|-------|--------|
| **waterfall stage** | member frontmatter `stage:` (1..6) → the `Stage` column + the DONE gate |
| **Phases / ▰▱ bar** | `phase-*.md` files in the member dir (count) + `count_checkboxes` completion → done/total + the progress bar (a DONE plan fills its bar) |
| **◄ NOW marker** | the first member not DONE and not BLOCKED is the current focus; its row gets `◄ NOW` + 🔄 EXECUTING |
| **✅ DONE** | only when `stage >= 6` AND `status` is `done`/`completed` |

The script emits, between the sentinels, exactly: the `### Execution order & package progress`
heading, then:
- the **execution-order glyph line** — `> **<id>** <glyph> → …  → **Stage 6** ⬜` in `members` order
  (✅ done · 🔄 current · ⬜ queued · ! blocked; short id = leading token of the member dir name).
- `**Plans done:** X / N  ·  **Now:** <current dir> — Stage S NAME (P/T phases)`.
- the package table (`# · Plan · Stage · Phases · Progress · Status`).

Everything OUTSIDE the sentinels is authored and never touched: the `## 🎯 LIVE EXECUTION DASHBOARD`
heading, the `> Updated live…` / legend lines, the `### ◄ CURRENT phase tracker` (with
its human SHAs), and the queued summaries. If the script cannot find both sentinels it **exits non-zero
without writing** (never appends a second block).
