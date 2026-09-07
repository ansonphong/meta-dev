# Plan Targets — Authoring Depth Tiers

**This file is the ONE definition of what a plan's `target` means.** `meta-planner`,
`codex-writing-plans`, and `meta-loop-gap` link here. None of them restates the table —
a second copy is drift waiting to happen.

`target` is optional plan frontmatter, written at Stage 3, read at Stages 3, 4, and 5:

```yaml
target: lean | standard | explicit    # absent means `standard`
```

It scales how much a plan *says*, to match how much the executing agent *needs told*.
It never changes what a plan must be *true about* — ground truth, contracts, and
focused verification are invariant across all three tiers.

## The tiers

| | `lean` | **`standard`** (default) | `explicit` |
|---|---|---|---|
| Task detail | coherent outcome | cross-layer steps where needed | explicit file-level steps |
| Code sketches | contract / signature only | sketch where ambiguous | full verified sketch |
| Ground-truth depth | symbols + data flow | + guards + callers | + full anchor inventory |
| Verify-hook detail | focused command + concise acceptance | focused command + acceptance | focused command + expected output and failure cases |
| Phase-size cap | ~6 tasks | ~3 tasks | ~3 tasks |

Lean depth reduces repeated instructions for capable executors while retaining
contracts, anchors, acceptance, and risk gates. It is a configurable efficiency
hypothesis, not permission to skip evidence or a measured speedup. See
`references/adaptive-workflow.md` and `references/workflow-evaluation.md`.

## Tier ↔ backend

| Profiles | Source |
|---|---|
| Exact model IDs and aliases | `meta_dev.workflow.model_profiles` and aliases in the settings cascade |

Run `scripts/workflow-policy.py` to resolve the intended executor before
choosing depth. Shipped frontier profiles cover Sol/Astra, Opus 4.8/5, and
Grok 4.6; unknown models use standard/task policy. Do not maintain a second
backend table here. Existing/explicit targets are carried forward, then risk
raises depth.

**Capability order is `lean` > `standard` > `explicit` — the INVERSE of depth order.**
A `lean` plan expects the *most* capable executor and says the *least*. Read that
sentence twice before writing any comparison; inverting it warns backwards.

## Blast radius overrides — upward only

Blast radius **raises** the effective tier and never lowers it. Regardless of the
declared `target`, author at `standard` or deeper when the work touches:

- schema or data migration
- auth, crypto, or licensing verification
- payment or value transfer
- a cross-repo or cross-service API contract

A `lean` plan for a UI tweak is correct. A `lean` plan for a migration is not — the
executor's capability was never the reason that plan needed precision.

## Dispatch mismatch — warn, never block

Before dispatching a task, compare the resolved backend against the plan's `target`.
If the backend's capability tier is **lower** than the plan's target, emit one line
naming the plan target, the chosen backend, and the risk — then **proceed**.

```
⚠️  plan target `lean` → dispatching to DeepSeek (explicit tier).
    Plan omits sketches and step detail this backend usually needs.
```

Above-tier is never warned — a more capable backend reading a more explicit plan is
always safe. **This warns and never blocks.** Running a `lean` plan on a mechanical
backend can be a deliberate call; doing it silently is the failure.
