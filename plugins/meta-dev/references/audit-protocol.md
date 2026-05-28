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
