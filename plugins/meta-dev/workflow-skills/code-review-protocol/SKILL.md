---
name: code-review-protocol
description: Scoped, report-only review with native routing and optional structured acceptance evidence.
---

# Code Review Protocol

Apply `../../references/workflows/protocol.md` once. Review is report-only absent
existing scoped implementation authority or explicit `--fix`; a finding does not
authorize edits or a commit.

Resolve intent, scope, baseline/delta refs, applicable rules, accepted evidence and
unresolved findings. Inspect the affected files and integration seams for:
correctness, safety, project patterns, acceptance coverage and scope. Use
`references/review-dimensions.md` only when a dimension needs clarification.

Batch every concrete, actionable finding with file/line, impact, reachable
failure path and smallest fix. Do not manufacture issues. Identify uninspected
scope and missing evidence explicitly; unknown evidence is never a pass.
Return `PASS`, `CONDITIONAL_PASS` or `FAIL` plus findings and material limits.
An urgent blocker can be reported immediately while remaining safe inspection
continues. Preserve requested delivery/final reviews; after repairs review only
affected deltas and invalidated assumptions, retaining unaffected evidence.

For structured output, inbox/remediation routing or a final planctl PASS, load
`references/verdict-routing.md`. It owns the schema, validation and source-bound
acceptance commands. A conversational verdict alone never records plan acceptance.

Use the configured native reviewer (Codex's configured Sol/high route by default),
honoring explicit available model selection. External/cross-family reviewers
require explicit selection; preserve Claude's configured review route. No extra
reviewer is implied by a stage name or executor backend. If independence is
unavailable, report it and leave the required gate open.
