# Dev Housekeeping — Meta-Runbook, Plan YAML, Archive Integration

Post-stage bookkeeping that `/meta-dev` runs after each stage completes (and after Stage 6 final review).

## Source-of-truth model

- **Plan Markdown** is the SINGLE source of truth: frontmatter declares `stage`/`stage_state`/`override`/`repo`/dependencies, tasks are `- [ ]`/`- [x]`, and planctl derives status from those facts. Never type `status:`.
- **`plans/meta-runbook.md`** is the ONLY hand-maintained **live** ledger: `## Sequence` (ordered active plan paths), `=== MILESTONE: TYPE · label ===` markers, `## Wave Strategy / Critical Path`, short `## Residual`, and a **Shipped pointer**. It REPLACES the old `STATUS.md` + `exec-order.md` pair.
- **`plans/meta-runbook-archive.md`** is the **cold history** file: full Shipped prose, dumped dead Sequence blocks, archaeology. Do **not** load it into routine session context. Dashboard scanners do **not** read it.
- The dashboard computes live state via `scripts/plan-index.py` / planctl (reads plan YAML + checkboxes + Sequence order). There is no plan state stored in the live ledger's parentheticals.

## Lean Meta-Runbook (binding — keep the live file small)

> Target: live `meta-runbook.md` stays **~≤150 lines / ~20KB**. History never re-bloats it.

1. **`## Sequence` only lists live work** — path must exist on disk; **no `/_archive/` paths**; no `/_future/` individual rows (one Residual park pointer is enough).
2. **No status novels** — no stage/percent/date parentheticals on Sequence lines. Live status = plan YAML + `/meta-dashboard`.
3. **One path once** — no duplicates even "also under wave X".
4. **Launch-line geography** — above `=== MILESTONE: PRODUCT LAUNCH ===` = launch-required; below = post-launch.
5. **Active runbook markers only** — `=== RUNBOOK: … ===` for non-done, non-archived campaigns.
6. **After Stage 6:** drop from Sequence; append **one compact line** to `plans/meta-runbook-archive.md` (newest first), **not** a multi-paragraph closeout in the live file. Optional: `planctl ledger shipped`.
7. **Hygiene:** `planctl ledger check` — expect zero dead Sequence entries, zero marker drift for archived runbooks, zero parenthetical status dumps.

Campaign `_runbook-*.md` lean shape is separate: see `plans/meta/2026-07-05-lean-runbook-doctrine.md` (3-zone dashboard + contract).

## Paths

All paths read from config at runtime:
- `bash scripts/config-get.sh meta_dev.paths.plans_root` → plans root
- `bash scripts/config-get.sh meta_dev.paths.archive_subdir` → archive subdirectory

Live ledger: `<plans_root>/meta-runbook.md`  
Cold history: `<plans_root>/meta-runbook-archive.md`

## Per-Stage Updates

Stage transitions are written ONLY by `scripts/stage-emit.sh` (a shim over `planctl stage` — the unified state layer's single write door), which sets the plan's YAML `stage:` and appends a stage event to planctl's `events.jsonl`. `on-stage-prompt.sh` calls it on stage-command submit. Do NOT hand-edit `stage:` in a plan — let stage-emit/planctl own it.

## Post-Stage-6 Housekeeping (full)

After Stage 6 (Review) completes successfully:

1. **Confirm the plan is Done:** `scripts/archive-guard.sh` must derive `done`, find every checkbox checked, find no explicit active-task marker, and confirm the plan is absent from the live Sequence.

2. **Archive the plan:**
   ```bash
   mv <plan-dir> <plans_root>/<archive_subdir>/<plan-name>/
   ```

3. **Update the ledger (lean):**
   - Remove the plan's path from `plans/meta-runbook.md` `## Sequence` (it is no longer active).
   - Append **one compact line** under `## Shipped` in `plans/meta-runbook-archive.md` (newest first):  
     `- <archived-path> — <Title> — Stage 6 DONE <date>`
   - Leave live `meta-runbook.md` `## Shipped` as a **pointer** to the archive file (do not re-paste history).
   - Advance live `## Wave Strategy / Critical Path` only if a wave/milestone just cleared.

4. **Commit:**
   ```bash
   git add <plan-dir> plans/meta-runbook.md plans/meta-runbook-archive.md
   git commit -m "chore: archive <plan-name>, update meta-runbook"
   git push
   ```

## Gate Housekeeping Protocol

Between stages, the gate housekeeping check:
- Verify the previous stage's commit is pushed
- Verify no uncommitted changes in the plan directory
- Verify the next stage's prerequisites are met (e.g., plan exists before harden)
