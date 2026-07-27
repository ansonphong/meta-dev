# Meta-Dev Skills

| Skill | Purpose | Invoked By |
|-------|---------|------------|
| `hotl-classification` | Classify tasks as HOTL-safe or HITL-required | `/meta-classify`, `/meta-dev` |
| `dod-contract` | Generate definition-of-done contracts | `/meta-dod` |
| `repair-loop` | 3-attempt auto-fix with failure dossier | `/meta-repair` |
| `code-review-protocol` | Structured code review with verdict routing | overlord, `/meta-review-batch` |
| `headless-worker` | `claude -p` patterns for headless execution | `/meta-headless` |
| `changelog-engine` | Batched changelog management | `/meta-changelog` |
| `version-manager` | Multi-repo version bumping with cascades | `/meta-version` |
| `inbox-clearer` | Autonomous inbox clearing with model tier discipline | `/meta-inbox clear` |

| `waterfall-tracking` | Visible stage-level task list for the 6-stage waterfall (autopilot/walk) | `/meta-dev` |
| `fable-consult` | Ask Fable 5 a judgment call before escalating to the human; adopt at ≥0.90 with evidence + falsifier, else escalate carrying the recommendation | any run about to stop and ask; always under `--autonomous` |
