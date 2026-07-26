# Plan Artifacts — the ONE naming rule

> **This file is the single source of truth for where a plan-attached artifact
> is written and what it is called.** No command, skill, or reference spells out
> its own artifact path. If you are about to type a path with `gap-report`,
> `loop-gap`, `design-review`, or `plan-validation` in it, link here instead.

## Why this file exists

The rule was previously restated at five write-sites, each phrased slightly
differently, and the copies drifted into **five incompatible layouts**:

| Shape | Example | Problem |
|-------|---------|---------|
| sidecar | `2026-07-15-nav-stepper-sibling-card.gap-report-codex.md` | ✅ correct, but only by accident |
| in-dir | `hextile-arm-grid-controller/gap-report-deep.md` | ✅ correct |
| prefix | `loop-gap-2026-07-25-spot-context-menu-in-page.md` | sorts nowhere near its plan |
| dated orphan | `gap-report-codex-2026-07-25.md` | names **no plan at all** |
| bare | `loop-gap.md` at the repo's plans root | ambiguous — which plan? |

The last two are the same bug. Every write-site was written for the
**directory-plan** case (`<plan-dir>/<artifact>.md`); nobody specified the
**single-file-plan** case, so `<plan-dir>` silently degraded to the plans root
and the artifact lost all association with the plan that produced it.

## The rule

> **A plan-attached artifact is named after its plan and sorts next to it.**

Two cases, decided by what the plan *is*:

| Plan form | Artifact path |
|-----------|---------------|
| **Directory plan** — `plans/<repo>/<slug>/00-master-plan.md` | `plans/<repo>/<slug>/<artifact>.md` — bare name **inside** the dir |
| **Single-file plan** — `plans/<repo>/<stem>.md` | `plans/<repo>/<stem>.<artifact>.md` — **sibling** carrying the plan's full stem |

`<stem>` is the plan filename minus `.md`, verbatim — date prefix included.

```
plans/app/2026-07-25-directional-prompts-bar.md                     ← the plan
plans/app/2026-07-25-directional-prompts-bar.gap-report-codex.md    ← its report
```

Both forms guarantee the property that matters: **the artifact is impossible to
encounter without also seeing which plan it belongs to** — by containment in the
directory case, by adjacent alphabetical sort in the file case.

## Artifact vocabulary

`<artifact>` is one of these, optionally suffixed `-<backend>`:

| `<artifact>` | Written by | What it is |
|--------------|-----------|------------|
| `loop-gap` | `/loop-gap` (Stage 4) | the scanner state + prompt file, re-read on re-scan |
| `gap-report-<backend>` | Stage 4.5 cross-family audit | a one-shot read-only audit report |
| `design-review` | `/review-design` | design quality audit |
| `plan-validation` | plan-validation skill | structural plan checks |
| `loop-gap-config` | `/meta-planner` | scan config `/loop-gap` reads at start — **dot-prefixed in the directory case** (`.loop-gap-config.md`), plain in the sidecar case |

`<backend>` is the executor slug (`codex`, `deep`, `glm`, `grok`, `sonnet`,
`opus`, `fable`) and may carry a model qualifier the executor already uses
(`codex-sol`). Omit it when only one producer exists for that artifact.

## Three things the name must NOT carry

- **No date.** A single-file plan's stem already begins with one, and git holds
  the revision history. A date in the artifact makes every re-run a new file and
  turns the plan directory into a graveyard.
- **No counter** (`-1`, `-2`). A re-run by the same backend **overwrites its own
  report** — that is the desired behavior for a live artifact. Counters
  accumulate stale reports nobody prunes, and readers cannot tell which is current.
- **No uppercase.** Everything under `plans/` is lowercase kebab-case; caps sort
  into a separate block on case-sensitive listings, defeating the adjacency the
  rule exists to create.

## Non-plan artifacts

**One-shot audits** with no plan behind them — repo-wide security audits, docs
audits, release-readiness sweeps — are standalone plan documents in their own
right and follow the ordinary plan naming convention
(`plans/meta/YYYY-MM-DD-<slug>.md`). They are dated because nothing else dates
them. Do not sidecar them onto an unrelated plan.

**The date leads.** `YYYY-MM-DD-security-audit.md`, never
`security-audit-YYYY-MM-DD.md` — a trailing date sorts by topic and scatters a
series across the directory, which is the same readability failure the sidecar
rule exists to prevent.

**Scope scans** — `/loop-gap` pointed at a feature, a code path, or the whole
project — likewise have no plan to attach to, but they are *re-read state files*,
not one-shot reports: the next scan diffs against the prior run's `git_sha`. They
therefore keep a **stable, undated** name at the plans root,
`plans/<repo>/loop-gap-<scope>.md`, so the re-scan can find the file it wrote
last time. Git holds the history; the filename must not move.

**Never** write any of these into a source tree or `docs/`.

## Consumers

These sites reference this rule and must not restate it:
`commands/meta-loop-gap.md` · `references/dev-swarms.md` (Stage 4.5) ·
`references/design-review-protocol.md` · `references/loopgap-config-gen.md`.
