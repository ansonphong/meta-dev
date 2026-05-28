# Audit Protocol — Assumption Extraction, Evidence Collection, Classification, Pattern Ecosystem Review

## Component Inventory

List every pipeline component (commands, skills, scripts, agents, hooks, schemas, templates).

## Assumption Extraction

For each component, extract:
| Component | Assumed dependency | Assumed invariant | Last verified |
|-----------|-------------------|-------------------|---------------|

## Evidence Collection

For each assumption:
1. **Read the actual code** — don't trust docs
2. **Run the component** — does it still execute?
3. **Check git log** — when was it last changed?
4. **Check callers** — is anything still using it?

## Classification

Each component gets one label:

| Label | Criteria | Action |
|-------|----------|--------|
| **Load-bearing** | In active use, critical path, no replacement | Maintain |
| **Insurance** | Rarely triggered but prevents catastrophe | Keep, test periodically |
| **Overhead** | Cost > benefit, rarely used or duplicated | Consider removal or consolidation |
| **Migrating** | Being replaced by another component | Track migration progress, remove when done |

### Hard Classification Rules

1. **Security components are ALWAYS load-bearing.** Security skills (e.g. meta-security), permission enforcement, guard hooks, and input-validation patterns must NEVER be classified as "overhead" regardless of model capability. Security is application correctness, not scaffolding — an improved model does not make these removable. Always assign them **Load-bearing**.
2. **Model-specific findings are labeled with the model version.** A component that is overhead for one model may be essential for a weaker one.

## Comparison Run (`--compare`)

When invoked with `--compare`, select a small, well-understood feature (3–5 tasks) and run it through two paths to measure component value empirically:

**Path A — Full Pipeline:** Design doc → meta-planner → loop-gap → meta-execute → meta-eval. Record: time, cost (agent calls), output quality, issues found.

**Path B — Simplified Pipeline:** Design doc → direct execution (no meta-planner, no loop-gap, no phase files). Same feature, same success criteria. Record: time, cost, quality, issues.

**Compare:** Did Path A catch issues Path B missed? Was Path A's time/cost overhead justified by quality improvement? Which specific components provided measurable value? Feed the result into Classification — but never reclassify a security component as overhead (Hard Classification Rule 1).

## Applying Changes — Confirm-Before-Applying Gate

Removal and simplification are gated. **Never auto-simplify the pipeline.**

1. **Never remove components without evidence** — gut feelings don't count, measurements do.
2. **Present the specific changes first** — which files to modify, what to strip.
3. **Require explicit user confirmation before applying any removal or simplification.** Do not edit/commit removals until the user confirms.
4. **Err toward keeping** — if uncertain whether a component is load-bearing, keep it until you have more data. Bias every borderline call toward retention.
5. **Measure before and after** — if you simplify something, verify quality didn't drop.

The same confirm-before-applying gate and err-toward-keeping bias apply to Pattern Ecosystem pruning below.

## Pattern Ecosystem Review (Step 7)

**Only meta-audit can prune learned patterns.** Review all `## Learned Patterns` sections across all commands:

1. Count patterns per command (cap: 20)
2. Check for contradictions (two patterns giving opposite advice)
3. Check for staleness (pattern references a removed component)
4. Check for overlap (two patterns covering the same ground)
5. Consolidate or remove as needed

## LP Lazy-Load

Patterns should be loaded on-demand, not all at startup. Each command reads only its own patterns section.

## Report Format

```markdown
# Meta-Audit Report — <YYYY-MM-DD>

## Component Classification

| Component | Type | Classification | Action |
|-----------|------|---------------|--------|
| ... | ... | ... | ... |

## Assumption Validation

| Assumption | Valid? | Evidence |
|-----------|--------|----------|
| ... | ✓/✗ | ... |

## Pattern Ecosystem

- Total patterns: N
- Stale: M (list)
- Contradictory pairs: K (list)
- Consolidated: J

## Recommendations

1. ...
```
