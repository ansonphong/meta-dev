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
| Subtask granularity | none — task-level only | cross-layer propagation only | one per file |
| Code sketches | contract / signature only | sketch where ambiguous | full verified sketch |
| Ground-truth depth | symbols + data flow | + guards + callers | + full anchor inventory |
| Verify-hook detail | acceptance condition, agent picks the command | one focused command | command + expected output |
| Phase-size cap | ~6 tasks | ~3 tasks | ~3 tasks |

Why `lean` exists: OpenAI retired the dev-message "Planning" section for GPT-5-Codex
because the model plans well unaided, and Anthropic's Opus guidance says explicit
verification instructions now cause *over*-verification. Prescription that a capable
model does not need is not free — it is context that competes with the actual work.

## Tier ↔ backend

| Tier | Expected executor |
|---|---|
| `lean` | Opus 5 · Grok 4.5 · Codex Sol |
| `standard` | Sonnet 5 · Codex Terra |
| `explicit` | DeepSeek · Codex Spark · Luna · Haiku |

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
