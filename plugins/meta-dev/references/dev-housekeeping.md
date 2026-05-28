# Dev Housekeeping — Exec-Order, STATUS, Archive Integration

Post-stage bookkeeping that `/meta-dev` runs after each stage completes (and after Stage 6 final review).

## Paths

All paths read from config at runtime:
- `bash scripts/config-get.sh meta_dev.paths.exec_order` → exec-order.md path
- `bash scripts/config-get.sh meta_dev.paths.status_file` → STATUS.md path
- `bash scripts/config-get.sh meta_dev.paths.plans_root` → plans root
- `bash scripts/config-get.sh meta_dev.paths.archive_subdir` → archive subdirectory

## Per-Stage Updates

After each stage completes, update the exec-order entry for this plan:
- Format: `Stage: N/6` annotation on the plan's line
- Stage 1 done → `Stage: 1/6`
- Stage 6 done → `Stage: 6/6 Done`

## Post-Stage-6 Housekeeping (full)

After Stage 6 (Review) completes successfully:

1. **Archive the plan:**
   ```bash
   mv <plan-dir> <plans_root>/<archive_subdir>/<plan-name>/
   ```

2. **Update STATUS.md:**
   - Mark the initiative as Done in the active work table
   - Update blockers section (remove this plan's blockers)
   - Update Execution Strategy waves (move completed items, advance wave status)

3. **Update exec-order.md:**
   - Check off the completed step
   - Update `Stage: 6/6` annotation
   - Note what it unlocked

4. **Commit:**
   ```bash
   git add <plan-dir> plans/STATUS.md plans/exec-order.md
   git commit -m "chore: archive <plan-name>, update STATUS + exec-order"
   git push
   ```

## Gate Housekeeping Protocol

Between stages, the gate housekeeping check:
- Verify the previous stage's commit is pushed
- Verify no uncommitted changes in the plan directory
- Verify the next stage's prerequisites are met (e.g., plan exists before harden)
