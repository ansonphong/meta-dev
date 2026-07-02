---
name: meta-visual-critique
description: Visual critique of attached image(s) — daisy-chains frontend-design skill for design vocabulary, returns structured critique within user-supplied context (defaults to GUI/web UI)
argument-hint: [free-form context, e.g. "landing page hero" | "mobile nav" | "dashboard card"] (images attached separately)
allowed-tools: [Read, Bash, Glob, Grep]
model: opus
---

# /meta-visual-critique — Visual Critique of Attached Image(s)

Look at the image(s) the user attached. Produce sharp, opinionated visual critique. Daisy-chain `frontend-design:frontend-design` skill for design vocabulary + anti-AI-slop lens. Anti-sycophantic: grade honest, take positions, no hedging.

## Step 0: Parse Arguments + Detect Context

User text: `$ARGUMENTS`

- **Image(s) attached:** required — if none, stop and ask user to attach one.
- **Context text:** optional; use it to scope critique.
- **No context supplied:** assume target is a **GUI / web UI / app screen**. Default lens = frontend interface design.

Examples:
- `/meta-visual-critique landing page hero` → critique through landing-hero conventions
- `/meta-visual-critique mobile checkout` → mobile UX + conversion lens
- `/meta-visual-critique` (image only) → assume GUI, full default rubric

## Step 1: Load Design Vocabulary (Daisy-Chain)

Invoke the frontend-design skill for creative-direction vocabulary, anti-AI-slop heuristics, and craft standards:

```
Skill: frontend-design:frontend-design
```

Use the loaded principles as the rubric backbone. Do NOT generate code — critique only.

Optionally read a project-specific design file if present at `.claude/skills/*-frontend-design.md` or `plans/_build/specs/ui-design-language.md`; skip if not.

## Step 2: Observe Before Judging

For each image, write 2-4 lines of pure observation first — what is literally on screen:
- Layout structure (grid, stack, asymmetric, centered, etc.)
- Color palette (count distinct hues, note temperature, saturation)
- Typography (sans/serif, weight contrast, hierarchy levels visible)
- Spatial rhythm (density, whitespace, alignment)
- Interactive affordances visible (buttons, inputs, nav, CTAs)
- Imagery / iconography style

This grounds the critique. Skip this step and you hallucinate.

## Step 3: Score Across 5 Dimensions

Grade each A / B / C / D / F with one-sentence justification. No participation trophies — most real-world UIs score C/B.

| # | Dimension | What it measures |
|---|-----------|------------------|
| 1 | **Coherence** | Visual system holds together. Color/type/spacing rules consistent. |
| 2 | **Originality** | Distinctive vs. AI-slop generic. Has a point of view. |
| 3 | **Craft** | Pixel-level polish. Alignment, hierarchy, contrast, spacing math. |
| 4 | **Functionality** | UI communicates purpose. Affordances clear. Information legible. |
| 5 | **Emotional Tone** | Mood matches intent (luxury / playful / utilitarian / mystical / etc). |

## Step 4: AI-Slop Detection

Auto-flag any of these. Each is an automatic deduction on Originality:

- Generic blue→purple gradient backgrounds
- Floating gradient blobs / "aurora" blurs
- Cookie-cutter SaaS landing layout (hero + 3-column features + testimonial + CTA)
- Stock phrases ("Revolutionize", "Transform", "Empower", "Unleash")
- Lorem-ipsum-shaped copy that says nothing
- Stock-photo people-on-laptops imagery
- Centered hero with oversized headline + subhead + two buttons (default Tailwind starter aesthetic)
- Glassmorphism applied without intent (frosted card on solid bg)
- Icon-in-circle-in-card-with-rounded-corners feature grid
- Default shadcn/Material/Bootstrap look with no customization
- Inconsistent border-radius (12px here, 8px there, 24px somewhere else)
- Six+ distinct hues fighting each other

Call out each slop pattern observed with its location in the image.

## Step 5: Top 3 Strengths, Top 5 Problems

**Strengths** (keep / amplify): max 3 bullets, specific. "Hero typography pairing" not "looks nice."

**Problems** (ranked by severity): max 5 bullets, each with:
- **What** — concrete element
- **Why it fails** — principle violated
- **Fix** — one-line concrete suggestion

## Step 6: Anti-Sycophancy Check

Re-read your critique before returning:
- Hedged ("could maybe consider possibly")? Rewrite direct.
- Gave an A to something average? Re-grade honest.
- 10 strengths and 1 problem? Rebalance — most UIs have more problems than strengths.
- Avoided taking a position? Take one.

If asked "is this good?" — answer yes or no, then justify.

## Step 7: Final Verdict

One paragraph (3-5 sentences) overall position. Format:

> **Verdict:** [Grade]. [Single strongest signal — positive or negative]. [Single biggest blocker]. [Direction recommendation: ship / iterate / scrap].

## Output Format

```
# Visual Critique — [user context or "GUI"]

## Observation
[2-4 lines per image]

## Scores
| Dim | Grade | Note |
|-----|-------|------|
| Coherence | X | … |
| Originality | X | … |
| Craft | X | … |
| Functionality | X | … |
| Emotional Tone | X | … |

## AI-Slop Flags
- [pattern] @ [location] OR "none detected"

## Strengths
1. …
2. …
3. …

## Problems
1. **What:** … **Why:** … **Fix:** …
…

## Verdict
> …
```

## Notes

- Image-only input is valid; context is optional.
- Multiple images: critique each separately, then add a cross-image consistency note.
- Never invent UI details not in the image — the observation step keeps you honest.
- Load project-specific design files only when relevant; otherwise stay general — works on any GUI image.
