# Design Review Protocol — AI-Slop Detection, Rubrics, Scoring, Anti-Sycophancy, Self-Improvement

This is the substance behind `/meta-review-design`. It audits the **original quality** of a UI implementation — coherence, originality, craft, functionality — and detects AI-slop patterns. It is **distinct** from the `design-eval` skill: `design-eval` scores implementation-vs-design-doc *fidelity* (did the build match the spec); this protocol scores *intrinsic design quality* whether or not a spec exists.

All project-specific values (brand color, token source, design-system rules, repo→token mapping, slop toggles, scoring weights, grade threshold) come from config under `meta_dev.review_design`. Read them at startup:

```
bash scripts/config-get.sh meta_dev.review_design
bash scripts/config-get.sh meta_dev.review_design.design_doc      # design-system / token source-of-truth
bash scripts/config-get.sh meta_dev.review_design.token_map       # repo → token-namespace map
bash scripts/config-get.sh meta_dev.review_design.scoring         # weights + grade_threshold
bash scripts/config-get.sh meta_dev.review_design.slop_patterns   # per-pattern enable toggles
```

When a config key is absent, fall back to the defaults stated inline below. Nothing in this protocol hard-codes a color, token name, or repo name — those are resolved from config or from the configured `design_doc`.

---

## Step 0: Parse Arguments

Input: `$ARGUMENTS` — `<component-path | page-url | "current">` `[--scope full|diff] [--fix] [--depth shallow|standard|deep]`

1. **Component path** — Read the source file; identify the UI element.
2. **Page URL** — If browser automation is available, screenshot; otherwise read template source.
3. **"current"** — Inspect `git diff` for recently changed view/style files (extensions from `meta_dev.review_design.target_globs`, default `*.svelte *.css *.postcss *.html *.tsx *.jsx *.vue`).
4. **`--scope diff`** — Review only changed lines (`git diff` against the configured base, default `HEAD~1`). Default scope is `full` (entire component).
5. **`--fix`** — After scoring, apply remediation for findings below the grade threshold (see Step 6).
6. **`--depth`** — Selects the model tier and the work performed (see Depth Tiers).

### Depth Tiers

| Depth | Model tier | What it does |
|-------|-----------|--------------|
| `shallow` | Haiku low | AI-slop detection table ONLY (Step 2). Grep-driven, no rubric scoring, no report narrative — emits the slop table + a pass/fail on slop count. Use for fast pre-commit screening. |
| `standard` (default) | Sonnet xhigh | Full pass: slop detection + 4-dimension rubric scoring + structured report with Must/Should/Nice findings. No second-pass verdict agent. |
| `deep` | Opus xhigh (final verdict only) | Standard pass, then a separate Opus agent re-reads the findings and component to issue the final verdict and catch rationalized-away issues. Use before shipping high-visibility surfaces. |

Read tiers from `meta_dev.review_design.depth` (default `standard`) and `meta_dev.models` for the model mapping.

---

## Step 0.5: Read Learned Patterns

Before evaluating, read the `## Learned Patterns` section at the bottom of this file. For each active pattern:

- If the pattern **adds a scoring dimension or check**, extend the relevant rubric's Check list.
- If the pattern **identifies a recurring design failure**, increase that failure's severity/deduction weight for this run.
- If the pattern **adds a slop signature**, append it to the Step 2 scan.

Record which patterns were active in the report metadata (`Patterns active:` line).

---

## Step 1: Gather Context

1. **Read the configured design source-of-truth** — `meta_dev.review_design.design_doc` (e.g. a design-system doc). This is the authority for tokens, surfaces, brand color, typography scale, z-index, and "never do X" rules. If unset, note "no design system configured — scoring against general craft principles only."
2. **Read the target component/page source** — full file contents (or the diff hunk if `--scope diff`).
3. **Detect the repo** of the target (match the path against `meta_dev.review_design.token_map` keys) so the correct token namespace / token-mapping is applied. If no entry matches, use the default namespace.
4. **Read imported style files** — follow `@import`, `<style>` blocks, and CSS module imports referenced by the component so craft scoring sees the real styles, not just markup.
5. **Resolve configured values** — brand/accent color, token names, and any "forbidden" craft rules (e.g. a no-glow rule) are read from config / the design doc, never assumed.

---

## Step 2: AI-Slop Detection (Automatic)

Scan for the patterns below. Each enabled pattern that is **found** is an automatic deduction against the named dimension. Honor `meta_dev.review_design.slop_patterns.<key>` toggles — a pattern disabled in config is skipped (report it as `N/A (disabled)`). Report every detected pattern with a `file:line` reference.

| # | Key | Pattern | Deduction | Detection method |
|---|-----|---------|-----------|------------------|
| 1 | `generic_gradients` | Generic gradient backgrounds (esp. blue→purple linear) | −1 Originality | grep `bg-gradient-to-`, `linear-gradient(` with stock color stops |
| 2 | `hero_stock_phrases` | Oversized hero with stock phrases ("Revolutionize", "Transform", "Empower", "Unlock", "Supercharge") | −1 Originality, −1 Coherence | grep hero blocks `>50vh` + generic marketing verbs |
| 3 | `identical_card_grids` | Excessive identical card grids (>3 cards, same structure) | −0.5 Originality | detect repeated card component with identical markup |
| 4 | `unstyled_component_libs` | Default Material/Bootstrap/shadcn/Chakra components, unstyled | −1 Coherence | detect default component-lib output with no project customization |
| 5 | `excessive_loaders` | Skeleton loaders / spinners everywhere (>3 loading states per view) | −0.5 Craft | count loading states; >3 per view is suspicious |
| 6 | `placeholder_content` | Placeholder content ("Lorem ipsum", "John Doe", "example@") | −1 Functionality | grep common placeholder strings |
| 7 | `generic_ctas` | Generic CTAs ("Learn More", "Get Started", "Click Here") | −0.5 Originality | grep generic CTA text |
| 8 | `no_type_hierarchy` | Default system fonts, no typography hierarchy | −1 Craft | check for missing font-family decls, no display/body/ui distinction |
| 9 | `craft_heuristic` | **Configurable craft heuristic** — forbidden visual treatments per the design system (default: glow effects & gratuitous `box-shadow` with spread `>8px`) | −1 Craft | grep the patterns listed in `meta_dev.review_design.craft_heuristic.forbidden` (default: `glow`, `shadow-glow`, `box-shadow` spread `>8px`, `drop-shadow` blur `>8px`) |
| 10 | `stock_photos` | Generic stock-photo placeholders | −0.5 Originality | check for placeholder image URLs, unsplash defaults |

> **Generalizing #9:** the original local protocol hard-coded "NEVER use glow/box-shadow." That is one project's craft rule. Here it is a configurable heuristic: `craft_heuristic.forbidden` is a list of regex/literal signatures (default the no-glow set), `craft_heuristic.deduction` is the points off (default −1), and `craft_heuristic.dimension` is the target dimension (default Craft). A project with a different craft taboo (e.g. "no pure-black text on white") configures it here without editing this file.

**Slop count = N/10 (or N/enabled) patterns detected.** Carry the per-pattern deductions into Step 3 scoring.

---

## Step 3: Scoring Rubric

Score each dimension **0–10** using the score-band criteria, then apply the slop deductions from Step 2. All bracketed `{config}` values resolve from the design doc / `meta_dev.review_design` (e.g. `{accent_color}` = `meta_dev.review_design.accent_color`; `{token_source}` = the configured design doc).

### Design Coherence (weight: `scoring.weights.coherence`, default 0.30)

| Score | Criteria |
|-------|----------|
| 9–10 | Unified mood, consistent identity, matches `{token_source}` tokens exactly |
| 7–8 | Mostly cohesive; minor inconsistencies in mood or identity |
| 5–6 | Recognizable identity but with notable deviations |
| 3–4 | Generic with some project elements |
| 0–2 | Could be any app — no project identity |

**Check:** theme mode (dark/light per `{token_source}`), accent/brand color (`{accent_color}`), surface hierarchy, z-index scale, spacing scale — all per the configured design source.

### Originality (weight: `scoring.weights.originality`, default 0.25)

| Score | Criteria |
|-------|----------|
| 9–10 | Custom, intentional design choices; nothing generic |
| 7–8 | Mostly original; 1–2 patterns could be more distinctive |
| 5–6 | Mix of custom and generic patterns |
| 3–4 | Mostly generic with minor customization |
| 0–2 | Template-level — could be any app |

**Check:** custom design decisions visible, avoids template defaults, asymmetric/intentional layouts where appropriate, no AI-slop signatures from Step 2.

### Craft (weight: `scoring.weights.craft`, default 0.25)

| Score | Criteria |
|-------|----------|
| 9–10 | Precise typography hierarchy, spacing rhythm, color harmony; obeys the configured craft rules |
| 7–8 | Strong craft; minor spacing or color inconsistencies |
| 5–6 | Adequate craft; several imprecise elements |
| 3–4 | Sloppy — inconsistent spacing, wrong font sizes, poor contrast |
| 0–2 | No craft evident — default everything |

**Check:** typography hierarchy (sizes/weights/colors per `{token_source}`), spacing-scale consistency, adequate contrast, and compliance with `craft_heuristic.forbidden` (no forbidden treatments).

### Functionality (weight: `scoring.weights.functionality`, default 0.20)

| Score | Criteria |
|-------|----------|
| 9–10 | All states handled (loading, error, empty, success), responsive, accessible |
| 7–8 | Most states handled; responsive; minor accessibility gaps |
| 5–6 | Core flow works but missing edge states |
| 3–4 | Incomplete — missing loading/error states, not responsive |
| 0–2 | Broken or unusable |

**Check:** loading / error / empty / success states, responsive behavior, keyboard accessibility, aria labels.

### Overall Score

```
Overall = Coherence × w_coherence
        + Originality × w_originality
        + Craft × w_craft
        + Functionality × w_functionality
```

Default weights `0.30 / 0.25 / 0.25 / 0.20` (must sum to 1.0; read from `scoring.weights`).

| Score | Grade | Verdict |
|-------|-------|---------|
| 9.0+ | A | Exceptional — ship it |
| 8.0–8.9 | B+ | Strong — minor polish only |
| 7.0–7.9 | B | Good — passes quality bar |
| 6.0–6.9 | C+ | Acceptable — needs specific fixes |
| 5.0–5.9 | C | Below bar — iterate before shipping |
| 4.0–4.9 | D | Poor — significant rework needed |
| 0–3.9 | F | Fail — start over or fundamentally rethink |

**Quality bar = `scoring.grade_threshold` (default B / 7.0).** At or above passes; one band below requires fixes; D/F blocks.

---

## Anti-Sycophancy Rules

These are EMBEDDED in evaluator behavior. You MUST follow them — the one-line summary in the command is not enforceable; these seven rules are.

1. **Never say "That's an interesting approach."** Take a position: "This works because…" or "This fails because…"
2. **Never say "There are many ways to think about this."** Pick one: "The right approach here is…"
3. **Never say "You might want to consider…"** Say "This is wrong because…" or "Change this to…"
4. **Never say "That could work."** State whether it WILL work and WHY.
5. **Grade honestly. A C is a C.** Do not inflate grades to avoid confrontation.
6. **Specificity over diplomacy.** "`gap-3` used where the design system specifies `gap-4` at line 24" beats "spacing could be tightened."
7. **Name the anti-pattern.** If it's AI slop, call it AI slop. If it's generic, call it generic.

---

## Step 4: Generate Report

````markdown
# /meta-review-design Report — {Component/Page}

**Date:** {YYYY-MM-DD}
**Target:** {file paths}
**Repo:** {detected repo / token namespace}
**Scope:** {full | diff}
**Depth:** {shallow | standard | deep}
**Patterns active:** {LP-NNN, LP-NNN or "none"}

## AI-Slop Detection

| # | Pattern | Found? | Location | Deduction |
|---|---------|--------|----------|-----------|
| 1 | Generic gradients | Yes/No/N/A | file:line | −N |
| … | … | … | … | … |

**Slop count:** N/10 patterns detected

## Scores

| Dimension | Score | Grade | Key Issue |
|-----------|-------|-------|-----------|
| Design Coherence (30%) | X/10 | A–F | … |
| Originality (25%) | X/10 | A–F | … |
| Craft (25%) | X/10 | A–F | … |
| Functionality (20%) | X/10 | A–F | … |
| **Overall** | **X/10** | **A–F** | |

## Specific Findings

### Must Fix (blocks shipping)
1. **[DIMENSION]** Description — `file:line`

### Should Fix (improves quality)
1. **[DIMENSION]** Description — `file:line`

### Nice to Have
1. **[DIMENSION]** Description — `file:line`

## Recommendation

**Status:** PASS / CONDITIONAL PASS / FAIL
````

**Write report to:** `{plans_root}/<repo>/<feature>/design-review-{YYYY-MM-DD}.md` when a plan context exists (resolve `{plans_root}` from `meta_dev.paths.plans_root`); otherwise output inline. Never write reports into source trees or `docs/`.

---

## Step 5: Self-Improving Detection (Learned-Patterns Loop)

After scoring, look for recurring quality failures across history:

1. Find past reports: `find {plans_root} -name "*design-review*" -o -name "*review-design*" | head -20`.
2. If **3+** past reports exist, compare: which dimensions are consistently scored below the grade threshold?
3. If the **same dimension** is flagged below threshold in **3+ separate reviews across different features**:
   - Generalize the finding into a Learned Pattern (no project-specific detail).
   - Append the LP to the `## Learned Patterns` section of THIS file, and propagate to `meta-planner` and `loop-gap` Learned Patterns so the gap is prevented upstream.
   - The detecting command commits the LP (the command, not this reference, performs the commit).

LP propagation closes the loop: a recurring craft failure caught in review becomes a planning-stage rule, so it stops recurring.

---

## Step 6: Apply Fixes (`--fix`)

If `--fix` was passed and the overall grade is below `scoring.grade_threshold`:

1. For each **Must Fix** finding, edit the source file directly at the cited `file:line`.
2. After editing all Must Fix items, **re-run Steps 2–3** to re-score.
3. Emit a **before/after report**: original grade → new grade, with the per-dimension delta and the list of files changed.
4. Do not commit from this protocol — the invoking command/session owns the commit. Stop after the before/after report.

---

## Learned Patterns

<!-- Auto-maintained by the improvement loop (Step 5). Generalized only — no project-specific entries. -->
<!-- Max 20 patterns. meta-audit enforces the cap via consolidation. -->
<!-- Append-only here — only meta-audit removes patterns. -->

(No patterns yet. Patterns are added automatically when the same dimension scores below the grade threshold across 3+ separate design reviews.)
