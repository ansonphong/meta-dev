---
name: meta-ux
description: UX evaluation and improvement — heuristic + design-system + accessibility audit against the configured design system, with iterative fix rounds
argument-hint: "[plan-path | \"running app\" | feature:<name> | <repo>] [--depth shallow|standard|deep] [--focus <area>] [--rounds N]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-ux

Experience audit — NOT a code review or functional test. Evaluates a target against first-principles heuristics, the configured design system, and accessibility standards, then optionally applies fixes and re-evaluates.

Full protocol: **`references/ux-protocol.md`**. All project-specific material (design-system rules, focus areas, scoring weights, depth/rounds defaults) is config-driven.

## When to Use

- Before implementation — assess a plan's planned UX
- After feature completion — evaluate the implemented experience
- Periodic health check — a repo's UX surface
- When something feels "off" — systematic friction diagnosis

## Flow

### 1. Resolve target + flags
Parse `$ARGUMENTS` per `references/ux-protocol.md` (Argument & Target Resolution): plan path / `running app` / `feature:<name>` / `<repo>` / no-arg cross-surface. Read flags `--depth`, `--focus`, `--rounds`. Load config:

```
bash scripts/config-get.sh meta_dev.ux              # focus areas, rules, weights, defaults
bash scripts/config-get.sh meta_dev.paths.design_doc
```

Depth sets the model tier per the protocol's scaling table. If the target is `running app`/url and `meta_dev.eval.health_checks` is set, do the health check first; bail if down.

### 2. Wave 1 — context gathering
Skip on `--depth shallow`. Else dispatch the two capped agents (Design System Audit, Platform/Surface State) in parallel — see protocol Wave 1.

### 3. Wave 2 — assessment
Score three rubrics: 6 first-principles heuristics (6th = configurable domain-context), design-system compliance (driven by `meta_dev.ux.design_system_rules`), and the WCAG AA accessibility checklist. See protocol Wave 2.

### 4. Score + report
Weighted `/100` (First Principles 30 / Design Compliance 30 / Accessibility 20 / Coherence 20, overridable via `meta_dev.ux.scoring`). Emit the `UX AUDIT` report — CRITICAL/HIGH/MEDIUM tiers, each finding with `file:line` + rule citation + `-> Fix:`, plus a DESIGN SYSTEM NOTES block. Apply the Anti-Sycophancy Rules.

### 5. --rounds N (editable targets only)
If `N > 1` and the target is editable, apply fixes at/above `meta_dev.ux.fix_min_severity` via Edit/Write, re-evaluate, and stop when the score stabilizes (≤1 pt), clears the threshold with no critical/high, or `N` is exhausted. Read-only plans degrade to a single annotated pass. See protocol --rounds loop.

Config block: `meta_dev.ux` (see `references/config-cascade.md`).
