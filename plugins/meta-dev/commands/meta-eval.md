---
name: meta-eval
description: Dedicated evaluator agent — tests implementations against design criteria, catches what self-review misses
argument-hint: <plan-path | feature-name> [--criteria design|functional|full] [--rounds N]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-eval

Evaluate implementation against design criteria. Separate evaluator (not self-review) — catches issues implementer rationalizes away.

## Scope

1. Gather context: design doc, master plan, phase files, design rubric
2. Launch parallel sonnet evaluation agents per category (API, security, error handling, integration, stubs)
3. API contract verification against cached surfaces (meta-init refresh-cache)
4. Design quality rubric scoring (if UI)
5. Plan-vs-reality verification (check claims against code)
6. Generate structured report with scores + issues + recommendation

Output: `plans/meta/eval-report-{date}.md`

Config: `plans/_dashboard/settings.json` (rounds, criteria defaults).
