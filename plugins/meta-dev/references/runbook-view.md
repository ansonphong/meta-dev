# Runbook Boxed View

Detail for `/runbook` — the per-campaign control-plane box. The command itself is at
`commands/runbook.md`; the full orchestration procedure lives in
`skills/runbook-orchestration/`.

## Architecture

```
plans/meta-runbook.md          META runbook — global cross-repo ledger (one entry per campaign)
  └─ _runbook-YYYY-MM-DD.md     CAMPAIGN runbook — what /runbook manages
       └─ plan dirs/files        members — each driven by /meta-dev or /meta-execute
```

## Two surfaces, one render source

| Surface | Trigger | What renders |
|---------|---------|--------------|
| **Sentinel block** (git-visible) | `planctl runbook render <rb>` (or via shim `runbook-render.py`) | Writes `<!-- RUNBOOK:PROGRESS:START -->…END -->` block; lazy dirty-set (sync-first, skip-if-unchanged). The git artifact. |
| **Boxed view** (terminal) | `/runbook` (bare) or `/runbook <path>` | Interactive terminal surface: rollup header, wave/member table with bars, nested runbooks as indented sub-groups, `Now:` pointer, blocked + needs-review queues, live claims. Rendered by `planctl runbook <path>`. |

## Sentinel contract

- START: `<!-- RUNBOOK:PROGRESS:START` — PREFIX match (annotation text may precede `-->`).
- END: `<!-- RUNBOOK:PROGRESS:END -->` — exact match.
- The `## 🎯 DASHBOARD` heading is an AUTHORED heading, NOT part of the sentinel.
- The block between them is **fully computed** — never hand-edit. Outside it, author
  only the ≤3-sentence purpose, `## DEPENDENCY ORDER`, and `## GATES & INVARIANTS`.
- Missing sentinel → planctl appends one on first render (graceful, never aborts a
  batch).

## Boxed view layout

- Rollup header: members done/total, tasks done/total with bar, derived status glyph.
- Member table: # · Plan · Stage · Progress (bar + %) · Status (glyph + word) · → (link).
- Nested runbooks render as indented sub-groups with their own rollups.
- `Now:` pointer = first non-done non-blocked member (serial execution order).
- Blocked queue: members with override set.
- Needs-review queue: members with `derived_status = needs-review`.
- Claims: live worker claims on member plans.

## Rules

- **Track it.** Stand up a TaskCreate list (one entry per member) for `execute` runs.
- **EXECUTE is gated.** `execute` writes code → needs Phong's explicit "go" per member.
- **Delegate.** Authoring + topo-sort = Opus. Driving members = DeepSeek→GLM.
  Gate reviews = Codex (review-only).
- **Status truth lives in member frontmatter + checkboxes** — the sentinel block is
  derived, never authored.
- **Closeouts** go in the member's master plan (`## Closeout`), never the runbook.
- **Refresh after each phase/plan** so the dashboard stays live.
