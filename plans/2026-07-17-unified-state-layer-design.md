---
status: draft
stage: 2
repo: meta
updated: 2026-07-17
why: Unify runbook/dashboard/meta-execute state into one derived, self-fresh, token-cheap memory layer
context: none
docs: none
---

# Unified State Layer — Design Doc (`planctl`)

> **One sentence:** Markdown stays the git-tracked source of truth; a disposable SQLite read-model (off-9p) makes every view fast and fresh; ONE atomic Python CLI (`planctl`) is the only way state changes; `status` is never typed again — it is derived.

**Research basis:** validated against 2026 best practice (Yegge's beads, Fossil SCM's rebuildable-cache doctrine, CQRS/event-sourcing, Anthropic long-running-harness guidance, Nate B Jones's OB1). All six spine elements validated; three must-fix adjustments incorporated (§3 invariants I5–I7). Key precedent: beads-classic (files-in-git truth + SQLite cache) failed on *bidirectional* sync and a *single hot JSONL* — this design is strictly unidirectional and spreads truth across ~2,000 files, which removes both failure modes.

---

## 0. Goals (the five promises)

| # | Promise | Today | Target |
|---|---------|-------|--------|
| G1 | **Never stale** | Dashboard pull-only; runbooks re-rendered only by slow Stop hook; frontmatter rots | Every reader self-syncs incrementally (<400ms); views always reflect live checkbox truth |
| G2 | **Fewer tokens** | Agents read plan files/ledger prose to learn state (1–3k tokens each); dashboard walks 1,946 files | `planctl brief`/`--json` answers in 100–600 tokens; no file-reading for status, ever |
| G3 | **Responsive** | Stop hook re-renders every `_runbook-*.md` (seconds, every stop) | Stop hook budget <1s typical; single-file reindex ~10–30ms on edit |
| G4 | **Reliable statuses** | ~40 freeform `status:` variants; `completed`≠`done` mis-count; hand-maintained rot | One derived vocabulary, one interpreter, schema-gated writes — drift is structurally impossible |
| G5 | **Unified memory** | runbook-render / plan-index / task-done / stage-emit / claims each own private logic | One index + one event log + one CLI feeds dashboard, runbooks, meta-execute, overlord, session briefs |

## 1. The disease (ground truth, 2026-07-17)

- `status:` field drifted to ~40 variants where schema allows 4; `plan-index.py` counts only `done` while `runbook-render.py` accepts `done|completed` → shipped work reads 0% on the control plane (documented in AUDIT runbook: "52 sat at 0% while its code was already in the tree").
- Frontmatter is hand-maintained *derived* state → rots the moment work happens; checkboxes (the real ledger) stay accurate but update nothing else.
- Global `/meta-dashboard` is pull-only and ephemeral; per-campaign runbook dashboards auto-render only via a Stop-hook `find … -name '_runbook-*.md'` loop that is both **slow** (renders all, every stop) and **blind** to master-plan-style campaigns.
- Nested runbooks (a `_runbook-*.md` listed as another runbook's member) render as dead leaves — `○ not started`, no rollup, dead links silent.
- The global ledger (`plans/meta-runbook.md`) is hand-curated and lags reality: largest active campaign (23-member AUDIT wave) unregistered; Shipped section is 141 entries of unbounded prose; parenthetical status notes duplicate (and contradict) frontmatter.
- 9,406-item inbox = accumulated exhaust of status/docs-declaration drift firing the DONE-gate repeatedly.

## 2. Architecture overview

```
┌─ TRUTH (git-tracked markdown — humans + planctl write, nothing else) ────────────┐
│  plan files: `- [ ]` checkboxes (task truth) + frontmatter DECLARED facts only:   │
│    stage · repo · override/note · depends/blocks · why   (status: DELETED)        │
│  runbook files: type:runbook + members[] (ordered)                                │
│  ledger: plans/meta-runbook.md — human-authored ORDER + MILESTONE/RUNBOOK markers │
└───────────────────────────────────────────────────────────────────────────────────┘
        │ one-way derive (files → index; the DB NEVER writes back)          [I1]
        ▼
┌─ READ MODEL (disposable — ~/.cache/meta-dev/<proj>/state.db, ext4, gitignored) ──┐
│  SQLite: files · plans · tasks · membership · edges · claims · meta               │
│  derived_status computed by ONE interpreter, version-stamped (DERIVE_V)     [I2]  │
│  `rm state.db` always heals: full rebuild from markdown in seconds          [I3]  │
└───────────────────────────────────────────────────────────────────────────────────┘
        ▲ incremental sync: git-diff/porcelain → reparse changed files only  [I4]
        │
┌─ MUTATION CLI — planctl (python3 stdlib only; THE single write door) ────────────┐
│  check/uncheck · task add · stage · override · claim · runbook add/render · sync  │
│  every write: atomic MD edit → upsert index → O_APPEND event line     [I5][I6]    │
│  schema gate: rejects any value outside canon at the door              [I7]       │
└───────────────────────────────────────────────────────────────────────────────────┘
        │ consumed by
        ▼
  /meta-dashboard · /runbook boxed views · /meta-execute · overlord · hooks · briefs
```

**Invariants (non-negotiable):**

- **I1 — Unidirectional forever.** The index never writes markdown. No auto-mirroring derived status back into frontmatter. (The exact bidirectional trap that sank beads-classic.)
- **I2 — One interpreter.** `derive()` lives in one module; every consumer imports/queries it. `DERIVE_V` version constant stamped into the index; mismatch → automatic full rebuild (Fossil `rebuild` / OB1 model-tagging pattern).
- **I3 — Disposable cache.** Corruption is a non-event: detect → delete → rebuild. Never repaired, never backed up, never in git.
- **I4 — Readers self-sync.** No reader trusts the index without first running the incremental sync (bounded, <400ms typical).
- **I5 — Off-9p.** `state.db` + `events.jsonl` live on native ext4 (`~/.cache/meta-dev/<project-slug>/`). SQLite locking and atomic appends are both broken on 9p — documented corruption class.
- **I6 — Atomic everything.** MD edits: temp-file + `os.replace` (already the runbook-render pattern). Event log: single-line ≤4KB O_APPEND writes on ext4.
- **I7 — The CLI is the schema gate.** Writes that don't parse against canon (stage 0–6 int, override enum, member exists, no membership cycles) are REJECTED loudly at the door. This — not 2,000 file audits — is what kills drift at the source.

## 3. Layer specs

### 3.1 Markdown truth schema

**Plan frontmatter (after migration) — declared facts only:**

```yaml
---
stage: 5                 # 1–6 waterfall stage — declared by the waterfall/conductor
repo: app                # app | www | gallery | meta
override: blocked        # OPTIONAL: blocked | parked | superseded — wins over derivation
note: waiting on GPU box # OPTIONAL: free text — the WHY of the override (shown in views)
depends: [plans/...]     # optional, unchanged
blocks:  [plans/...]     # optional, unchanged
why: one-liner           # optional, unchanged
context: [...] | none    # unchanged (Stage-3 declaration, DONE-gate evidence)
docs:    [...] | none    # unchanged
---
```

**`status:` is deleted.** It exists only as a derived value. `updated:` is deleted too (git history + event log carry time truth; a hand-typed date is derived-state rot in miniature).

**Checkboxes** stay exactly as they are — the one ledger, `- [ ]` / `- [x]`, in `00-master-plan.md` (or the single plan file). Two additions:

1. **Stable task IDs (beads-style).** Canonical form: a trailing ` #a3f8` tag (4-hex content-hash, collision-checked per file; hierarchical `#a3f8.1` for subtasks). `planctl stamp <plan>` adds tags to untagged boxes; indexing tolerates untagged boxes (addressed by unique text-prefix match as fallback) but all *new* tasks created via `planctl task add` are born tagged. Existing human handles (`T3.2`) remain addressable aliases when unambiguous.
2. **Human-verify convention formalized:** boxes whose line carries `by eye|by hand|gpu|manual` or sit under an acceptance/human-verify heading are flagged `human_verify` in the index (same regex the DONE-gate already uses) — excluded from execution-done math, surfaced separately in views.

**Runbooks** keep `type: runbook` + ordered `members:` (paths). A member may be a plan file **or another runbook file** — now first-class (§4). `status:`/`updated:` deleted here too; `stage:` optional and ignored by derivation (a runbook's stage is computed).

### 3.2 The derivation (one interpreter)

```
derive(plan) -> status:
  1. override present ............................ → override value (+ note)   [blocked|parked|superseded]
  2. stage >= 6 .................................. → done
  3. tasks_total > 0 and tasks_done == total ..... → needs-review   (work complete, not yet stage 6)
  4. tasks_done > 0 .............................. → executing
  5. stage in 3..5 ............................... → ready          (planned/hardened, no boxes flipped)
  6. stage <= 2 .................................. → draft

derive(runbook) -> rollup (recursive, cycle-guarded):
  members_done / members_total   (member done ≡ derived done)
  tasks_done   / tasks_total     (recursive sum incl. nested runbooks)
  effective_stage = min(stage of non-done members)  ·  now = first non-done, non-blocked member
  runbook done ≡ all members done
```

Derived vocabulary (canon, closed): `draft · ready · executing · needs-review · done` + override `blocked · parked · superseded`. Flexibility lives in `note:` (free text, always displayed beside the override) — expressive where humans need words, closed where machines need counting.

- **Glyph map:** `draft ◦ · ready ▹ · executing → · needs-review ⊙ · done ✓ · blocked ! · parked ‖ · superseded ⌀`.
- `needs-review` **is** the old stage-drift warning promoted to a first-class state — ≥100% boxes at stage 5 is no longer an anomaly to warn about, it's a named queue (feeds the review pipeline).
- **Drift guard:** `stage >= 6` with open execution boxes derives `done` but sets a `drift` flag rendered loudly (`✓⚠`) in every view and listed by `doctor`/`reconcile` — declared-done-with-open-work can never pass silently (replaces the old status:completed fail-loud case, which keyed on a field that no longer exists).
- The old `status: completed`/`in_progress`/`pending`/freeform strings: gone (migration §7 maps semantic ones to overrides, deletes the rest).
- `DERIVE_V = 1`. Bump on any rule change → index auto-rebuilds; mixed-semantics rows are impossible.

### 3.3 SQLite read model

Location: `~/.cache/meta-dev/<project-slug>/state.db` (slug = sanitized abs path of project root, same scheme Claude Code uses). WAL mode. Stdlib `sqlite3` only.

```sql
meta(key TEXT PK, value TEXT);          -- derive_v, last_commit, project_root, schema_v
files(path PK, kind, sha1, mtime_ns, size, parse_err);        -- kind: plan|runbook|ledger
plans(path PK, repo, stage, override, note, why, title,
      tasks_done, tasks_total, human_open, derived_status);
tasks(plan_path, tid, line_no, checked, human_verify, section, text,
      PRIMARY KEY(plan_path, tid));
membership(parent PK¹, child PK¹, ord, child_kind);           -- runbook → member edges
edges(src, dst, kind);                                        -- depends|blocks from frontmatter
claims(scope PK, session, host, ts, status);                  -- absorbs worker-claims.jsonl
```

**Incremental sync (`planctl sync`)** — the freshness engine:

1. `git -C <root> status --porcelain -- plans/` (uncommitted) ∪ `git diff --name-only <last_commit>..HEAD -- plans/` (committed since watermark) → candidate set. One git call, ~50ms.
2. Re-parse candidates only (frontmatter + checkboxes; ~1–5ms/file), upsert rows, recompute derived fields for touched plans + their ancestor runbooks (membership walk).
3. Update watermark. `--file F` skips git and reindexes one file (the PostToolUse path). `--full` drops and rebuilds everything (corruption / `DERIVE_V` bump / doctor).

Trust model: sha1 short-circuit (unchanged content → skip). mtime is a hint only (unreliable on 9p), sha decides.

### 3.4 `planctl` — the mutation CLI

`plugins/meta-dev/scripts/planctl/` (python package, `__main__.py`, stdlib only) + bash shim `scripts/planctl`. Every verb: `--json` structured output (beads doctrine — agents never parse prose). Every mutation: atomic MD write → index upsert → event append, in that order, single process.

| Verb | Does | Absorbs / replaces |
|------|------|--------------------|
| `sync [--file F] [--full]` | incremental reindex (§3.3) | plan-index.py's per-run rescans |
| `status <plan> [--json]` | derived status, tasks, drift for one plan | hand-reading frontmatter |
| `brief [--repo R] [--runbook RB] [--json]` | ≤600-token "where things stand": active/blocked/needs-review/next | reading meta-runbook.md + dashboards at session start |
| `check <plan> <tid…>` / `uncheck` | flip box(es) atomically by stable id | hand-Edits of checkbox lines; conductor `task-done` |
| `task add <plan> "<text>" [--section S]` | append a born-tagged box, returns tid | hand-adding checkbox lines |
| `stamp <plan>` | add ` #hash` ids to untagged boxes | — (one-time + lazy) |
| `stage <plan> <1-6>` | set declared stage + event | `stage-emit.sh` |
| `override <plan> blocked\|parked\|superseded --note "…"` / `clear` | set/clear override | freeform status strings |
| `claim <plan>` / `release <plan>` | atomic work-claim for parallel agents (beads `--claim`) | worker-claims.jsonl + `.task-lock` files |
| `next [--runbook RB] [--json]` | ready-work: unclaimed, unblocked (edges + claims + rollup), in ledger order | beads `bd ready`; overlord's private polling |
| `runbook render <rb>` | write the sentinel dashboard block (only if changed) | `runbook-render.py` (logic moves in, file stays as shim) |
| `runbook add <rb> <plan-or-rb>` | insert member at dependency-correct slot; **cycle-refused at the door** | hand-editing members |
| `ledger check` | ledger ⇄ reality diff: unregistered active runbooks, dead entries, marker drift | nothing (the AUDIT-wave invisibility class) |
| `ledger shipped` | regenerate compact Shipped index from archive events (one line each) | 141-entry hand-prose Shipped section |
| `doctor` | integrity: cycles, missing members, malformed frontmatter, 9p placement, derive_v | scattered validate scripts |

**Verification gate on `check`:** optional `--verify "<cmd>"` runs the command and only flips on exit 0 (Anthropic: "mark passing only after testing"). Task-level Verify hooks in plans map straight onto this.

### 3.5 Event log

`~/.cache/meta-dev/<project-slug>/events.jsonl` — append-only, planctl-only writer, O_APPEND single-line records: `{ts, session, event, plan, data}`. Events: `check|uncheck|stage|override|claim|release|runbook_change|done_gate|review_verdict|archive`. Rotation at 10MB → `events-<date>.jsonl` (queried transparently). The existing git-tracked `plans/_dashboard/state.events.jsonl` is **frozen read-only legacy** — done-gate's review_verdict lookups move to the new log via planctl.

### 3.6 Views

- **`/meta-dashboard`** — same boxed UX, but: data via `planctl sync` + SQL (no 1,946-file walk), and **runbook-aware**: campaign members grouped under an indented runbook header row with rollup bar (`▸ REFRAME-360 ██████░░ 11/23`), `=== RUNBOOK ===` markers honored instead of dropped. Statuses show derived glyphs incl. `⊙ needs-review` and override notes.
- **Per-runbook boxed dashboard (the original ask):** `/runbook <path>` (bare verb = current runbook status) renders the full control-plane box scoped to one campaign: rollup header, wave/member table with per-member bars, nested runbooks as indented sub-groups with their own rollups, `Now:` pointer, blocked/needs-review queues, claims. Same renderer components as `/meta-dashboard` (one render library, two entry points).
- **Embedded runbook MD blocks** (the sentinel `## 🎯 DASHBOARD`) stay — they're the git-visible artifact — but rendered *lazily from the index* only when a member actually changed (dirty-set from events), not every-file-every-stop.
- **`planctl brief`** — the session-start memory: replaces reading the 344-line ledger + dashboards with a ≤600-token structured summary (active arcs with rollups, blocked+why, needs-review queue, next actions). This is the "persistent memory system" surface: index + events ARE the harness memory; `brief` is its recall interface.

### 3.7 Hooks diet (the responsiveness fix)

| Hook | Today | After |
|------|-------|-------|
| PostToolUse Edit/Write on `plans/**` | plan-validate warnings only | + `planctl sync --file <F>` (~10–30ms) — index is hot before you even ask |
| Stop (`on-run-complete.sh`) | full-tree stage-5 python scan + DONE-gate + **unconditional render of every `_runbook-*.md`** | `planctl reconcile`: sync → DONE-gate decision matrix as SQL over the index → render only dirty runbooks (typically 0–1). Budget <1s. |
| UserPromptSubmit | stage-emit on stage commands | unchanged, but calls `planctl stage` |
| SessionStart | concurrency banner | + one-line `planctl brief --oneline` (optional) |

The DONE-gate decision matrix itself (clean+reviewed→stamp, claimed-done-with-open-boxes→fail loud, docs-evidence gate) is preserved verbatim — it just reads the index instead of re-walking and re-parsing the tree with inline python.

## 4. Nested runbooks — first-class (W4)

- `membership.child_kind` distinguishes `plan` vs `runbook` (detected by `type: runbook` frontmatter, not filename).
- Rollup is a recursive walk (SQLite recursive CTE): a nested runbook contributes its **aggregate** (members done/total, recursive task counts, effective stage) — never its own checkbox count (it has none) and never its informational `stage:`.
- **Cycle guard twice:** `runbook add` refuses cycles at the door (I7); `doctor`/indexer detects cycles introduced by hand-edits, marks both files `parse_err`, and surfaces loudly in every view (never silently renders garbage).
- **Missing member ⇒ loud.** A member path that doesn't resolve renders as `✗ MISSING <path>` in red-equivalent glyphs in every view and appears in `doctor` — the current silent `○ not started` for archived/moved members is abolished. `sweep`/archive tooling gains a reconcile step: archiving a plan updates member paths in owning runbooks (via `planctl`, atomic).

## 5. Global ledger as projection (W5)

`plans/meta-runbook.md` remains the ONE human-editorial file, but its jobs shrink to exactly what only a human can author:

- **Stays human:** `## Sequence` ordering, `=== MILESTONE ===` markers (launch line), `=== RUNBOOK ===` markers, wave-strategy prose.
- **Derived (banned from hand-editing):** any status/percent/date parenthetical on Sequence lines (views show live state; migration strips them), the `## Shipped` index (regenerated compact by `planctl ledger shipped` from archive events — one line per entry, prose post-mortems live in the archived plans themselves).
- **Enforced:** `ledger check` (run inside `reconcile`) diffs ledger vs reality — active unregistered campaign → inbox item (the AUDIT-wave bug becomes structurally impossible to miss); dead/archived entry still in Sequence → listed for one-command cleanup.
- **Inbox drain:** done-gate items become **stateful per plan** (one open item per plan+cause, auto-resolved by planctl when the cause clears) instead of append-per-stop — this both drains the 9,406 backlog (migration dedupe) and caps future growth.

## 6. Token & latency budget

| Operation | Today | Target |
|-----------|-------|--------|
| `/meta-dashboard` data pass | multi-second 1,946-file walk, every invocation | `sync` <400ms warm + SQL <50ms |
| Stop hook | seconds (full scan + render all runbooks) | <1s typical (index + 0–1 renders) |
| Agent learns a plan's state | Read 1–3k-token file(s) | `planctl status --json` ~100 tokens |
| Session orientation | read ledger (344 lines) + dashboards | `planctl brief` ≤600 tokens |
| Conductor flips a task | Edit tool round-trip on a big MD file | `planctl check p T3.2` one bash call |
| Runbook rollup incl. nested | impossible (renders wrong) | recursive CTE, exact |

## 7. Migration (incremental, each phase shippable)

- **M0 — Build alongside (no behavior change):** planctl package + index + derive + sync; `doctor`; parity harness proving index counts == current plan-index.py counts on the live tree. Plugin version bump; nothing consumes it yet.
- **M1 — Normalize truth (one-time sweep, committed):** delete `status:`/`updated:` from all live plan frontmatter (semantic values → `override:`+`note:`; `completed|done` → nothing, derivation handles it); strip ledger parentheticals; `stamp` task-ids on ACTIVE plans only (archived plans left untouched, indexed read-only).
- **M2 — Swap readers:** dashboard-data.sh + runbook-render.py + focus mode consume planctl; runbook-aware global view + `/runbook <path>` boxed view land here. Old parsers become shims.
- **M3 — Swap writers + hooks diet:** conductor `task-done`→`check`, stage-emit→`stage`, claims→`claim`; Stop hook → `planctl reconcile`; PostToolUse single-file sync. Skills/docs (task-tracking, execute-charter, runbook-orchestration, CLAUDE.md snippets) updated to name planctl as the only write path.
- **M4 — Hygiene:** inbox dedupe/drain (9,406 → per-plan stateful items); `ledger shipped` regeneration; freeze legacy state.events.jsonl; register missing campaigns (AUDIT wave) via `ledger check`.

Rollback at any phase: the markdown is never held hostage — views can always fall back to full-walk parsing (M2 shims retained one version).

## 8. Concurrency invariants (20-agent tree)

- All mutations through planctl, single short-lived process per call, WAL + busy_timeout on ext4 — no long-lived daemon, no lock server.
- MD writes atomic (temp+replace) and single-file-scoped; two agents flipping different boxes in the same file serialize on the file lock planctl takes (flock on ext4 sidecar, never on 9p).
- `claim` is the coordination primitive (atomic INSERT OR FAIL) — replaces `.task-lock` litter files.
- Worst-case index corruption (host crash mid-write): detected by `PRAGMA integrity_check` in `doctor`/`sync` → auto `--full` rebuild (I3). Truth is never at risk — it's markdown in git.

## 9. What we are NOT doing

- **No Dolt / DB-as-truth** — requirement-driven divergence: 2,000 narrative, diff-reviewable plans stay human-readable in git.
- **No auto-mirror of derived status back into frontmatter** (violates I1; the beads-classic trap).
- **No git-tracked SQLite or event log** (merge-conflict magnet; 9p corruption class).
- **No filesystem-watcher daemon / background service** — event-driven hooks + read-time sync only ("simplest thing that works").
- **No retrofit of archived plans** — they index as-is, read-only, zero migration churn.

## 10. Testing (critical-breakage only, per policy)

1. **Derivation golden table** — every (stage, boxes, override) combination → expected status; the `completed≠done` class regression-locked.
2. **Sync parity** — incremental sync result ≡ full rebuild result on a fixture tree (the silent-staleness guard).
3. **Atomicity** — concurrent `check` calls on one file lose no flips (the corruption guard).
4. **Nested rollup + cycle** — fixture with runbook-in-runbook + a deliberate cycle → exact counts + loud refusal.

Nothing else. No retrofits, targeted runs only.

## 11. Open questions (small, non-blocking)

1. CLI name: `planctl` (working name) — happy to bikeshed.
2. `brief` default scope: whole project vs current-conversation arcs (proposal: project, `--runbook` to narrow).
3. Should `/meta-dashboard` gain a `--watch` self-refreshing terminal mode post-M2? (Cheap once the index exists; deferred as candy.)
