# Dev Housekeeping — Meta-Runbook, Plan YAML, Archive Integration

Post-stage bookkeeping that `/meta-dev` runs after each stage completes (and after Stage 6 final review).

## Source-of-truth model

- **Plan YAML frontmatter** (`status`/`stage`/`repo`/`depends`/`blocks`/`why`) is the SINGLE source of truth for a plan's stage and status. Tasks are `- [ ]`/`- [x]` checkboxes inside the plan file.
- **`plans/meta-runbook.md`** is the ONLY hand-maintained ledger: `## Sequence` (ordered active plan paths), `=== MILESTONE: TYPE · label ===` markers, `## Wave Strategy / Critical Path`, `## Shipped`, `## Residual`. It REPLACES the old `STATUS.md` + `exec-order.md` pair.
- The dashboard computes live state via `scripts/plan-index.py` (reads plan YAML + checkboxes). There is no plan state stored in `state.json` / the event log.

## Paths

All paths read from config at runtime:
- `bash scripts/config-get.sh meta_dev.paths.plans_root` → plans root
- `bash scripts/config-get.sh meta_dev.paths.archive_subdir` → archive subdirectory

The runbook lives at `<plans_root>/meta-runbook.md`.

## Per-Stage Updates

Stage transitions are written ONLY by `scripts/stage-emit.sh` (a shim over `planctl stage` — the unified state layer's single write door), which sets the plan's YAML `stage:` and appends a stage event to planctl's `events.jsonl`. `on-stage-prompt.sh` calls it on stage-command submit. Do NOT hand-edit `stage:` in a plan — let stage-emit/planctl own it.

## Post-Stage-6 Housekeeping (full)

After Stage 6 (Review) completes successfully:

1. **Confirm the plan is Done:** its YAML `status:` is `done` and all checkboxes are `[x]` (the deterministic gate is `scripts/archive-guard.sh`).

2. **Archive the plan:**
   ```bash
   mv <plan-dir> <plans_root>/<archive_subdir>/<plan-name>/
   ```

3. **Update `plans/meta-runbook.md`:**
   - Remove the plan's path from `## Sequence` (it is no longer active).
   - Add a line under `## Shipped` (newest first): `<archived-path> — <Title>  (archived: <path>)`.
   - Advance `## Wave Strategy / Critical Path` if a wave/milestone just cleared.

4. **Commit:**
   ```bash
   git add <plan-dir> plans/meta-runbook.md
   git commit -m "chore: archive <plan-name>, update meta-runbook"
   git push
   ```

## Gate Housekeeping Protocol

Between stages, the gate housekeeping check:
- Verify the previous stage's commit is pushed
- Verify no uncommitted changes in the plan directory
- Verify the next stage's prerequisites are met (e.g., plan exists before harden)
