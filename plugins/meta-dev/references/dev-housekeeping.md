# Development bookkeeping

Plan Markdown is git truth; planctl is the only state write door. Read configured
plans_root and archive_subdir; do not assume a child repo, vendor path, or branch.

At stage transitions use `stage-emit.sh`/planctl. At completion, reconcile the
owning runbook only when dirty. Maintain the live Sequence through planctl's
ledger operations; keep history in its configured archive. Do not load archived
history into routine execution context or duplicate state in prose.

Before archival require a covering review PASS and all required acceptance,
including human gates. Use `scripts/archive-guard.sh` and the existing planctl
archive/ledger workflow; never move a plan merely because implementation ended.
Partial/blocked work stays visible with its next action.

Commit actual bookkeeping changes by explicit paths using the project git
contract. Related updates may share a safe seam commit. Push only when authorized,
not after every stage. Do not launch independent audit/evaluation/housekeeping
commands merely to complete the normal Stage-6 review.
