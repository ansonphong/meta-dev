---
name: meta-review-design
description: Design quality audit — scores UI against coherence, originality, craft, functionality with AI slop detection and anti-sycophancy rules
argument-hint: <component-path | page-url | "current"> [--scope full|diff] [--fix] [--depth shallow|standard|deep]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-review-design

Audits the **intrinsic design quality** of a UI implementation — coherence, originality, craft, functionality — and detects AI-slop patterns. Anti-sycophantic: grades honestly, takes positions, never hedges. Feeds recurring failures upstream via the self-improving loop.

> **Distinct from the `design-eval` skill.** `design-eval` scores implementation-vs-design-doc *fidelity* (did the build match the spec). This command scores *original design quality* whether or not a spec exists. Do not conflate them.

## When to Use

- **Stage 2 of /meta-dev** — review the design before planning, if the feature has UI.
- **Stage 6 of /meta-dev** — when `git diff` shows view/style changes (`.svelte`, `.css`, `.postcss`, `.tsx`, …).
- **Standalone** — point at any component or page to grade it.
- **`--fix`** — apply remediation for below-threshold findings.

## Procedure

Run the full protocol in `references/design-review-protocol.md`:

1. **Parse args** (Step 0) — resolve target, `--scope`, `--fix`, and `--depth` (depth selects model tier + work scope).
2. **Read Learned Patterns** (Step 0.5) — extend rubrics / bump severities from this command's `## Learned Patterns`.
3. **Gather context** (Step 1) — read the configured design source-of-truth, the target source, imported styles; detect the repo to apply the right token namespace.
4. **AI-slop detection** (Step 2) — grep the 10-pattern table (honoring `slop_patterns` toggles), record `file:line` + deductions.
5. **Score** (Step 3) — 4 dimensions 0–10, apply slop deductions, compute the weighted overall + grade.
6. **Report** (Step 4) — emit the structured report; write to the plan dir when one exists.
7. **Self-improve** (Step 5) — if a dimension scored sub-threshold across 3+ past reports, add a Learned Pattern here and propagate to `meta-planner` + `loop-gap`, then commit the LP.
8. **Fix** (Step 6) — if `--fix` and grade < threshold, edit Must-Fix files, re-score, emit before/after. Do not commit from `--fix`.

**Anti-sycophancy rules are mandatory** — see the 7 rules in the protocol; the one-liner here is not enforceable on its own.

## Config

All project-specific values come from `meta_dev.review_design` (design-doc pointer, token map, slop toggles, scoring weights, grade threshold, default depth, craft heuristic):

```
bash scripts/config-get.sh meta_dev.review_design
```

Nothing in this command or its protocol hard-codes a color, token name, or repo. Quality bar defaults to **B (7.0)**.

## Learned Patterns

<!-- Auto-maintained by the improvement loop. Generalized only — no project-specific entries. -->
<!-- Max 20 patterns. meta-audit enforces the cap. Append-only — only meta-audit removes. -->

(No patterns yet. Added automatically when the same dimension scores below the grade threshold across 3+ separate design reviews. The full pattern list lives in `references/design-review-protocol.md`.)
