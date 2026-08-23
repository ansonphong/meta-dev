# UX Protocol — Heuristic Rubric, Accessibility, Scoring, Report, Rounds Loop

A UX audit is an **experience** audit, not a code review or functional test. It assesses how a target (plan, running app, feature, or repo surface) serves a user against first-principles heuristics, the project's configured design system, and accessibility standards.

All project-specific material (design-system rules, focus areas, scoring weights, depth/rounds defaults) is read from config — this protocol stays generic.

```
DESIGN_DOC = bash scripts/config-get.sh meta_dev.paths.design_doc
UX_CFG     = bash scripts/config-get.sh meta_dev.ux          # whole block
```

---

## Argument & Target Resolution

Parse `$ARGUMENTS` into a target + flags.

| Input form | Meaning |
|------------|---------|
| `<plan-path>` (`.md` under plans root) | Evaluate **planned** UX before implementation |
| `running app` / `<url>` | Evaluate the **live** application (do an env health check first if `meta_dev.eval.health_checks` is set) |
| `feature:<name>` | Focus on one feature's flow |
| `<repo>` (one of `meta_dev.paths.plan_subdirs`) | Audit that repo's UX surface |
| *(no argument)* | Cross-surface UX audit across all configured repos |

**Flags:**
- `--depth shallow|standard|deep` (default from `meta_dev.ux.default_depth`)
- `--focus <area>` — restrict scope to one configured focus area (see below)
- `--rounds N` — iterative fix-and-re-evaluate (default from `meta_dev.ux.default_rounds`)

**Focus areas** come from `meta_dev.ux.focus_areas` (config-driven, project-specific). Always-available built-ins regardless of config: `accessibility`, `onboarding`, `mobile`. If `--focus` names something not in the merged list, list valid areas and stop.

**Depth → model-tier scaling:**

| Depth | Context agents | Assessment | Verdict |
|-------|----------------|------------|---------|
| `shallow` | skip — single checklist pass | Haiku (low) | inline, no separate verdict agent |
| `standard` | 2× Haiku (low) parallel | Sonnet (xhigh) | Sonnet (xhigh) |
| `deep` | 2× Haiku (low) parallel | Sonnet (xhigh) | Opus (xhigh), adds competitive/a11y deep-dive |

---

## Wave 1: Context Gathering

Skip on `--depth shallow`. Otherwise dispatch the two agents in parallel. Each has a hard word cap and an explicit extraction list — return only the list, no prose preamble.

### Agent 1.1 — Design System Audit (max 300 words)
Read the configured design doc (`DESIGN_DOC`). If `null`, note that and fall back to the target repo's root `AGENTS.md` and routed design/conventions context. Extract:
- Color token inventory + usage rules (which token is the accent, where it's allowed)
- Surface / border / radius conventions
- Z-index scale and stacking contexts
- Typography scale and spacing tokens
- Component patterns (button variants, form controls, overlays)
- Any explicit "never do X" rules (e.g. no glow, no responsive variants on styled components)

Return: a token map + any stale/missing tokens.

### Agent 1.2 — Platform / Surface State (max 300 words)
Read the target repo's root `AGENTS.md` and routed context files. Extract:
- Current UX surface (pages, components, routes)
- Known UX debt / pain points
- Accessibility baseline (ARIA usage, keyboard nav, screen-reader support)
- Responsive / mobile state

Return: a UX-surface inventory.

---

## Wave 2: Assessment

Score the target on three rubrics in order of impact.

### 2.1 — First-Principles Heuristics (6)

Each heuristic carries concrete probing questions. The 6th is a **domain-context heuristic** that is parameterized by config (`meta_dev.ux.domain_context`) so it adapts per project.

1. **Visibility of system status** — Can the user always see what they need? Is current state (progress, async job status, validation state) surfaced? Is there feedback for every action?
2. **Affordance** — Do interactive elements look interactive? Do controls use the correct surface tokens for their action weight (primary vs secondary vs destructive)? Is clickable-vs-static unambiguous?
3. **Consistency** — Is the visual language uniform across surfaces? Same accent usage, same component patterns, same interaction idioms? Are framework patterns applied consistently (e.g. one state/reactivity model, not mixed)?
4. **Efficiency** — Are the common/critical paths optimized — fewest steps, sensible defaults, no dead-ends? Are power-user shortcuts present without cluttering the default path?
5. **Error Prevention & Recovery** — Are destructive/irreversible actions guarded? When things fail, are errors specific, human-readable, and actionable? Is the user-supplied input recoverable after an error (no lost work)?
6. **Domain Context** *(configurable)* — Does the UI honestly communicate the realities of this product's domain? Pull the domain framing from `meta_dev.ux.domain_context` (a short string describing the product's defining constraint — e.g. async/long-running compute, real-time collaboration, offline-first, regulated data). Probe: are domain-specific states (queue position, ETA, capacity/pressure, sync status, latency, permission tier) made legible instead of hidden behind a generic spinner?

If `meta_dev.ux.domain_context` is unset, default the 6th heuristic to **"Latency & State Honesty"**: does the UI tell the truth about waits, capacity, and partial states rather than faking instantaneity?

### 2.2 — Design-System Compliance

Cross-reference the UI against the rules extracted in Agent 1.1, **driven by `meta_dev.ux.design_system_rules`** (a config list of `{ id, rule, severity }`). For each rule, find concrete violations with `file:line`. Generic rule shapes the config typically encodes:
- **Accent discipline** — the brand/accent token is used only for the configured purpose (e.g. brand accent / primary interaction), never as decoration or for non-interactive fills.
- **Emphasis style** — emphasis uses the configured mechanism (e.g. borders/weight) and avoids forbidden ones (e.g. glow/shadow).
- **Z-index consistency** — overlays, modals, tooltips, dropdowns use the defined scale, no ad-hoc magic numbers.
- **Component styling invariants** — e.g. no responsive variants on styled components; shared components reused, not re-implemented.

If `meta_dev.ux.design_system_rules` is empty, derive the checks from the design doc / `CLAUDE.md` conventions discovered in Wave 1, and note that no explicit rule list was configured.

### 2.3 — Accessibility (WCAG-oriented checklist)

- **Focus management** — logical tab order; focus moves into and is trapped within modals/dialogs; focus returns to the trigger on close; skip links to main content where appropriate.
- **Contrast** — all text and meaningful UI meets **WCAG AA** (4.5:1 body, 3:1 large text / UI components) against its actual background.
- **Semantics / ARIA** — icon-only buttons have accessible names (`aria-label`); images/generated media have meaningful `alt` text; roles and states (`aria-expanded`, `aria-selected`, live regions for async updates) are correct.
- **Full keyboard operability** — every interaction works without a mouse; no keyboard traps; visible focus indicators throughout.

When `--focus accessibility` (or `--depth deep`), expand this into a per-component pass and verify against assistive-tech expectations, not just static attribute presence.

---

## Scoring Rubric (weighted, /100)

Default weights (overridable via `meta_dev.ux.scoring`):

```
SCORE/100 = First Principles (30)
          + Design Compliance (30)
          + Accessibility    (20)
          + Coherence        (20)
```

- **First Principles /30** — average heuristic health × 30.
- **Design Compliance /30** — start at 30, subtract per violation weighted by the rule's configured severity (critical > high > medium).
- **Accessibility /20** — fraction of checklist items passing × 20; any keyboard trap or sub-AA primary text is an automatic cap at 12/20.
- **Coherence /20** — holistic: does it feel like one product made by one team? Subtract for jarring inconsistencies the per-rule checks miss.

Map to a letter only for gating: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, F < 60. Gate threshold for "pass" defaults to `meta_dev.ux.grade_threshold` (fallback B).

---

## Findings Report Template

```
UX AUDIT — {target}
Date:  {YYYY-MM-DD}
Depth: {shallow|standard|deep}   Focus: {area|all}   Round: {n}/{N}
===========================================================

FINDINGS (by tier)

[CRITICAL]
 1. {finding}  ({file}:{line})  — violates {rule-id|heuristic}
    -> Fix: {token-level, specific, actionable}

[HIGH]
 2. {finding}  ({file}:{line})  — violates {rule-id|heuristic}
    -> Fix: {token-level, specific, actionable}

[MEDIUM]
 3. {finding}  ({file}:{line})  — violates {rule-id|heuristic}
    -> Fix: {token-level, specific, actionable}

DESIGN SYSTEM NOTES
 - {consistency observation / cross-surface pattern}
 - {missing token or pattern gap in the design doc itself}

SCORE: {total}/100   (Grade {letter})
 - First Principles:  {score}/30
 - Design Compliance: {score}/30
 - Accessibility:     {score}/20
 - Coherence:         {score}/20
```

Every finding MUST include a `file:line` (or flow-step for a plan), the rule/heuristic it violates, and a `-> Fix:` line. No finding without a fix.

---

## --rounds N Iterative Fix Loop

When `N > 1` and the target is editable (running app / repo, not a read-only plan):

1. **Round 1** — run Waves 1–2, produce the report + score.
2. **Apply fixes** — for findings at or above the configured fix tier (`meta_dev.ux.fix_min_severity`, default `high`), apply remediation directly via **Edit/Write**. Make the smallest token-level change that resolves the finding; do not touch unrelated styling.
3. **Re-evaluate** — re-run Wave 2 (and Wave 1.1 if design tokens changed). Recompute score.
4. **Stop conditions** — stop when ANY of:
   - score reaches/exceeds the grade threshold AND no critical/high remain, OR
   - score change between consecutive rounds is ≤ 1 point (stabilized), OR
   - `N` rounds exhausted.
5. **Report best round.** List what was resolved per round and what remains unresolved with the reason.

If the target is a read-only plan, `--rounds` degrades to a single pass and the report annotates recommended fixes instead of applying them.

---

## Anti-Sycophancy Rules

1. **Grade honestly.** A beautiful UI with a keyboard trap gets a failing accessibility score — say so plainly. Aesthetics never buy back broken access.
2. **Token-level specificity.** "Improve the button's affordance" is useless. "The primary upload button uses the `surface-raised` token but it's the primary action — fill it with the accent token or promote it to `surface-accent`" is actionable.
3. **No hedges.** Ban "generally", "mostly", "might be some minor issues". Name the exact page, element, and token.
4. **Every finding cites a rule.** Each finding references a design-system rule id OR a first-principles heuristic. If nothing is violated and you still flag it, you're guessing — drop it or flag the design doc for a missing rule.
5. **Don't reward intent.** Score what's implemented/specified, not what was meant. A described-but-absent feature is a gap, not partial credit.
