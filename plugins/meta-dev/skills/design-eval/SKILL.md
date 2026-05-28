---
name: design-eval
description: Design quality rubric scoring — evaluates implementation against design doc on 4 dimensions
---

# Design Evaluation Skill

Scores an implementation against its design doc on 4 dimensions. Reads the design doc path from `bash scripts/config-get.sh meta_dev.paths.design_doc`.

## 4 Scoring Dimensions

Each dimension scored 1-10:

1. **Visual Accuracy** — Does the UI match the design's visual spec? Colors, spacing, typography, layout.
2. **Interaction Fidelity** — Do interactions match the design's behavior spec? Animations, transitions, state changes.
3. **Component Consistency** — Are shared components used where the design specifies them? No ad-hoc re-implementations.
4. **Accessibility** — Does the implementation meet the design's accessibility requirements? Contrast, labels, keyboard nav.

## Rubric

| Score | Label | Criteria |
|-------|-------|----------|
| 9-10 | A | Design-accurate; minor acceptable deviations documented |
| 7-8  | B | Close match; a few deviations but no user-visible regressions |
| 5-6  | C | Noticeable deviations; some design specs missed |
| 3-4  | D | Major deviations; significant rework needed |
| 1-2  | F | Does not match design; needs full reimplementation |

## Process

1. Read the design doc from the configured path
2. Read the implementation files
3. Score each dimension independently
4. Compute weighted average: Visual 30%, Interaction 25%, Component 25%, Accessibility 20%
5. Output structured report with per-dimension scores, overall grade, and specific findings

## Output Format

```markdown
## Design Quality Evaluation

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Visual Accuracy | X/10 | 30% | X.X |
| Interaction Fidelity | X/10 | 25% | X.X |
| Component Consistency | X/10 | 25% | X.X |
| Accessibility | X/10 | 20% | X.X |
| **Overall** | | | **X.X/10 (Grade X)** |

### Findings
- [severity] file:line — description
```
