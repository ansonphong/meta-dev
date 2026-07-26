---
name: meta-probe
description: Exhaustive deep-investigation probe — fans diverse agents across every angle, debates adversarially, breaks LLM bias loops, collapses to one report that opens a conversation
argument-hint: <issue text | file:line | feature:name | inbox-id | "question"> [--budget low|medium|high|insane] [--rounds N] [--background] [--no-converge]
allowed-tools: [Read, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /meta-probe — Deep-Investigation Probe

The deepest, most expensive thinking tool in the harness. Point it at ONE hard question and it throws the kitchen sink: many agents, many angles, adversarial debate, real experiments, run for as long as it takes — then collapses everything into a single report that **opens a conversation** instead of closing one.

Use it when a problem is mission-critical, when you're tired of re-explaining the same thing into a loop that keeps making the same mistake, or when an answer matters enough that cost is no object.

**This command never edits source and never commits.** It investigates. The only file it writes is its report under `plans/meta/`. Fixing is a separate `/meta-execute` step that the report can recommend.

**Loop-breaking is the core feature, not a garnish.** The wave structure mechanically enforces the de-biasing protocol — read it first: see [probe-debiasing.md](../../references/probe-debiasing.md). Every wave below maps to techniques T1–T8 there.

**Agent philosophy.** Be extremely liberal spawning agents — but **never spawn two agents that think the same way** (T2/DMAD). Each agent owns a distinct strategy or stance. Deep reasoning agents are dispatched as **opus** (mission-critical); mechanical indexing/archaeology agents may be **haiku**. Agent count scales with budget: low ≈ 8, medium ≈ 18, high ≈ 30, insane ≈ 50+ (and recursive).

## Prompts & Interview Protocol

When user-interview mode is active, read `references/probe-prompts.md` for the Q1-Q6 protocol and budget-tiered agent prompts.

## Usage

```
/meta-probe "why does the feed query slow down only after ~2k rows"
/meta-probe backend/app/services/feed.py:142 --budget high
/meta-probe feature:checkout-timeout --budget insane
/meta-probe "should we cut over to UUID PKs now or after launch" --budget high --background
/meta-probe inbox:af83 --budget medium --no-converge
```

## Step 0 — Parse arguments

**Target mode:** free text → `question` | `path:line` → `code` | `feature:{name}` → `feature` | `inbox:{id}` → pull the inbox item body as the question.

**Budget** (default `medium`):

| Budget | Wave 1 angles | Wave 2 debate rounds | Wave 3 experiments | Recursion | Stop rule |
|--------|---------------|----------------------|--------------------|-----------|-----------|
| low | ~6 core angles | 1 round | only to break an unresolved tie | none | single pass |
| medium | ~12 angles | 2 rounds | tie-break only | none | converge or 2 rounds |
| high | ~20–30 angles | 3+ rounds | yes, on every surviving hypothesis | none | converge or rounds cap |
| **insane** | all angles + per-sub-question agents (50+) | until stable | yes, aggressively | **recursive sub-probe per surviving hypothesis** | convergence, stall (2 flat rounds), OR ceiling — see Long-Horizon Discipline; **min 3 rounds**, no early exit on convergence |

**Flags:**
- `--rounds N` — override the Wave 2 debate-round cap.
- `--no-converge` — disable the convergence early-exit; force maximum depth even if an answer looks settled (catches premature confidence).
- `--background` — detach, run to completion across turns, write the report, post an inbox advisory. Default is interactive.

## Step 0.5 — Read learned patterns

Read this command's `## Learned Patterns` footer. Each entry is a **recurring bias rut** found by prior probes — pre-load every one into the Wave 0 forbidden-rut list so this probe starts already inoculated against it.

---

## Wave 0 — Frame & De-bias (always; the loop-breaker setup)

This wave decides whether the whole probe escapes the rut. Do it carefully.

1. **Neutral re-frame (T1).** Rewrite the target into a blame-free, assumption-free problem statement. Strip "it keeps", "the model is dumb about", "obviously". State only what is observed and what is asked.
2. **Surface stated assumptions.** List every assumption baked into the question (explicit and implicit). These become candidates for inversion.
3. **Loop-detection → forbidden ruts (T8).** Mine for what has already been tried and failed:
   - `git log --oneline -40` and `git log -p` around any named file — recent attempts and reverts.
   - Prior reports: `find plans/meta -name "probe-*.md" 2>/dev/null` — read any on a related topic.
   - The conversation framing itself — what fix/assumption is the user implicitly stuck on?
   - Emit a **Forbidden Ruts** list: each rut = `{what was tried} → {why it failed/why it's a rut}`. Agents may NOT re-propose these unless they bring new evidence overturning the prior failure.
4. **Divergent hypothesis space.** Brainstorm a wide set of candidate explanations/answers — deliberately include unlikely and "stupid" ones (the rut lives in the space of likely-looking answers). Aim for 6–15 distinct hypotheses. Invoke `superpowers:brainstorming` if the space feels narrow.
5. **Assign inversions (T1).** Mark 1–2 hypotheses that invert the leading assumption — these get honest advocates in Wave 1.

Output of Wave 0: neutral statement, assumptions, **forbidden ruts**, hypothesis space. All downstream agents receive these — but **not** any prior conclusion stated as fact.

---

## Wave 1 — Multi-angle investigation (parallel, diverse strategies — T2)

Spawn one agent per angle **in a single parallel message**. Each uses a genuinely different method. Each agent's prompt includes: the neutral statement, the forbidden ruts, the hypothesis space, and an explicit ban on re-treading ruts. **No agent receives the prior conclusions.** A subset receives an inverted premise.

Core angles (low budget picks ~6; higher budgets run all + variants):

| Angle | Model | Strategy |
|-------|-------|----------|
| Root-cause / first-principles | opus | 5-whys to bedrock; build the causal chain. |
| Best-practices | opus | What does the canonical/industry-standard solution look like? How *should* this be done? |
| User-experience | sonnet | Impact on real users, flows, edge users, what "good" feels like. |
| Code-elegance / design | opus | Simplicity, coupling, design smells, the cost of the current shape. |
| Engineering-robustness / FMEA | opus | Failure modes under load/edge/concurrency; what breaks and how. |
| Security / threat | opus | Abuse paths, trust boundaries, data exposure. |
| Performance / scale | opus | Hot paths, algorithmic complexity, resource cost, measured if cheap. |
| Historical / git-archaeology | haiku | When/why introduced, what changed near it (`git log -p`, blame). |
| Empirical / reproduction | opus | Reproduce + instrument the actual behavior. Uses `superpowers:systematic-debugging`. Ground truth. |
| Analogical | sonnet | How do other systems / libraries / domains solve this exact shape? |
| Assumption-inversion | opus | Take each stated assumption, negate it, follow the consequences honestly. |
| Adversarial / devil's-advocate | opus | Everything the other angles will conclude is wrong — here's the case. |

**Every angle agent MUST return (T5/T6):**
- Findings, each anchored to evidence (`file:line`, command output, doc) — unsupported assertions are rejected.
- **At least one concrete counterexample to its own leading conclusion** (consider-the-opposite).
- A confidence (0.0–1.0) and which hypotheses its evidence supports / refutes.

**Insane budget:** additionally spawn one agent per sub-question in the hypothesis space, and re-run any angle whose evidence was thin.

---

## Wave 2 — Adversarial debate / hypothesis tournament (T3, T4, T7)

Now pit the surviving hypotheses against each other. Majority vote is **banned** — survival is by withstanding the strongest counterargument.

Per round:
1. **Preset-stance advocates (T3).** Assign each leading hypothesis a fixed advocate (opus) whose only job is to defend it with the strongest evidence-backed case — including the unlikely/inverted ones. Stances are assigned, never self-selected.
2. **External critique (T4).** For each hypothesis, a *different* agent (that did not advocate it) builds the strongest attack. No agent critiques its own stance.
3. **Pre-mortem (T5).** On the current leading hypothesis: "assume the obvious fix shipped and the problem persists — explain why." A hypothesis that can't survive its own pre-mortem is demoted.
4. **Fresh-context judge (T7).** Inject one agent that has NOT seen this round's debate; it judges the hypotheses from scratch on evidence alone. Compare its verdict to the entrenched debate — divergence is a bias signal.
5. **Cull + carry.** Drop hypotheses with no surviving evidence. Carry survivors to the next round with the sharpened counterarguments attached.

**Round count by budget** (or `--rounds N`): low 1, medium 2, high 3+, insane until stable (min 3). Stop a round early only if one hypothesis dominates on evidence AND `--no-converge` is not set.

---

## Wave 3 — Experiment & ground-truth (conditional — T6)

Run only when analysis cannot separate surviving hypotheses, or budget is high/insane and an experiment would raise confidence. Pure analysis is the default.

- Design the **single most decisive experiment** per unresolved fork: reproduce the behavior, instrument it, run a targeted test, measure the metric.
- **Read-only on the real tree.** Any scratch code, fixtures, or temp instrumentation goes in a temp dir or a throwaway scratch path — never edit tracked source, never commit. Clean up after.
- Feed results back as confidence 1.0 evidence. An experiment that refutes the leading hypothesis is the most valuable result — surface it loudly.

---

## Wave 4 — Synthesis collapse

Collapse all surviving evidence into ONE report via **adversarial synthesis** (evidence + survival, not vote). Rank hypotheses by how much evidence supports them and how well they survived the strongest counter. Pick the terminal state: **convergence**, **exhaustion**, or **stable uncertainty** (see probe-debiasing.md). Stable uncertainty is honest and valid — name the decisive experiment that would resolve it.

**Recursion (insane only):** spawn a fresh sub-probe (Wave 0→4) **only** for a surviving-but-unsettled hypothesis that has a non-trivial frontier item — an unexplored avenue that could decide it (LH5). A hypothesis that is unsettled but has no remaining avenue to settle it does NOT get a sub-probe — it goes to the report as stable-uncertainty with its decisive experiment named. Inherit the parent's forbidden ruts. Continue until one hypothesis dominates with evidence, OR the frontier is dry (exhaustion), OR a ceiling is hit.

---

## Long-Horizon Discipline (high / insane — multi-hour runs)

A multi-hour probe fails from **context rot, coordination drift, and wheel-spinning**, not lack of effort. These rules keep a long run *productive* — reaching real conclusions, not a confident drift into nonsense. Mandatory at `high`/`insane`; cheap to apply at `low`/`medium`.

**LH1 — Context isolation (load-bearing).** The orchestrator NEVER holds raw agent transcripts. Every dispatched agent returns a **distilled artifact only** (≤ ~200 words: claim · evidence cites · confidence · one counterexample). Verbose exploration, file dumps, and reasoning chains die inside the subagent's context — this is what lets the run survive hours without the orchestrator filling up and losing the plot.

**LH2 — Externalized state ledger.** Maintain `plans/meta/{YYYY-MM-DD}-probe-{slug}.state.md` — a sidecar to the report below, so ledger and report sort adjacent (`references/plan-artifacts.md`). Updated after **every wave and every round** — the durable memory the run reads from, not accumulated chat. Contents:
- **Hypotheses** — each with status (alive / demoted / refuted / confirmed) and current confidence.
- **Evidence ledger** — every load-bearing fact, **provenance-tagged** to its source (`file:line`, command + output, doc). Ground truth.
- **Forbidden ruts** — carried and extended.
- **Frontier (LH5)** — live list of unexplored avenues, each with its value-of-information note; the probe runs until dry. Add when an angle opens a new question, strike when pursued or judged zero-VOI.
- **Round log** — round N: what changed (eliminated / new evidence / forks opened-or-closed) + progress score (LH5) + frontier size.
- **Current best verdict** — always present, even mid-run.

The final report is generated FROM this ledger; the ledger is the resume point for `--background` runs and the source of truth after any compaction.

**LH3 — Compaction checkpoints.** After each round (sooner if context is heavy), discard raw debate and re-initialize the working context from the ledger + neutral statement. Carry the ledger, never chatter.

**LH4 — Provenance + re-anchoring (anti coordination-drift).** A claim advancing between rounds is **re-verified against its ORIGINAL evidence** (the `file:line`/command in the ledger), never a prior agent's summary. Summaries route attention; only source evidence decides. Stops one agent's early error from becoming the whole tree's "fact."

**LH5 — Exploration frontier (productivity guardrail).** Compute is justified only while an **unexplored avenue could plausibly change the verdict**. Keep an explicit **frontier** in the ledger: not-yet-pursued avenues (untried angle, unread file/region, unrun experiment, unresolved fork, hypothesis with no decisive evidence either way), each with a one-line **value-of-information** note: *what could this change, and how likely?* Each round's continue/stop decision:
- **Continue** iff ≥1 frontier item has non-trivial VOI — could move the verdict, flip a hypothesis, or close a fork. Pursue highest-VOI first.
- **Stop (exhaustion)** when the frontier is empty, OR every remaining item is unable to change the conclusion (low/zero VOI: cosmetic, redundant, already-decided). Then **conclude** — don't spin a round to look busy.

Compute a **progress score** per round = (hypotheses eliminated-with-evidence) + (net-new provenance-tagged evidence) + (forks resolved); log it. Two consecutive ≈0-progress rounds strongly signals a dry frontier — verify it's genuinely exhausted, then conclude. Long is fine when avenues remain; **flat with a dry frontier means stop**. Never burn a round, agent, or recursion with no plausible payoff.

**End-of-round contemplation (mandatory gate).** At every round's close, before continue/stop, write into the ledger:
1. *Any other avenue to look down?* — actively generate new frontier items: an untried angle, an unread file/region, an un-inverted assumption, an unrun experiment, an undrawn analogy, an untaken perspective. Accept "none" only after a genuine search.
2. *Have we been exhaustive?* — is every surviving hypothesis decided by evidence or blocked only by a named decisive experiment? Is the frontier truly dry, or merely *tiring*?

Continue iff Q1 surfaces a non-trivial avenue; conclude iff Q1 yields nothing AND Q2 is yes. This is the gate — progress score and stall counter only inform it.

**LH6 — Hard ceilings (even on insane).** "Unbounded" = not artificially short, not literally forever. Default ceilings (configurable via `--rounds` / settings): ≤ 12 debate rounds, ≤ 3 recursion depth, ≤ 80 total agents. Any ceiling is a **graceful terminal**: write the best-supported verdict + remaining forks and each decisive experiment. Never crash-stop; land the plane.

**LH7 — Incremental report (checkpoint value).** Update the report file after every wave so an interrupted or ceiling-stopped run still yields the full value gathered. Never defer output to a final one-shot write.

**LH8 — Trajectory review / course-correction.** Every 3 rounds (and before any recursion), a **fresh-context lead-reviewer agent** reads ONLY the ledger and answers: (a) still answering the *original* question, or drifted? (b) in a rut the forbidden-list should have caught? (c) marginal value still positive, or terminate? Its verdict can re-plan, prune branches, or stop the probe. External, not self-judged.

---

## Output — the report that opens a conversation

Write `plans/meta/{YYYY-MM-DD}-probe-{slug}.md` (slug from the neutral statement; **date leads** — see `references/plan-artifacts.md`), generated from the state ledger (LH2) and updated incrementally (LH7). The companion `{YYYY-MM-DD}-probe-{slug}.state.md` ledger stays on disk beside it as the audit trail and resume point. Report structure:

```markdown
# Probe — {neutral question}

> /meta-probe {target} --budget {budget}  ·  {ISO timestamp}  ·  terminal: {convergence|stall|ceiling|stable-uncertainty}  ·  rounds: {N}  ·  agents: {M}

## Verdict
{single most-supported conclusion}  ·  confidence {0.0–1.0}
So what: {one line — what this means / what to do}

## The question, neutrally framed
{statement}
**Stated assumptions:** {list}

## Hypothesis tournament
| Rank | Hypothesis | Evidence FOR | Strongest counter | Survived? | Conf |
|------|-----------|--------------|-------------------|-----------|------|

## Per-angle findings
{collapsible: what each lens saw, evidence-anchored}

## Ruled OUT — and why
{so the conversation never re-treads these}

## Forbidden ruts detected
{the loop(s) / repeated mistakes named explicitly}

## Open questions
{each + the decisive experiment/info that would resolve it}

## Recommended next actions
{ranked; may include a /meta-execute or /loop-gap follow-up}

## Conversation starters
{3–5 pointed questions back to the user}
```

**Interactive mode (default):** stream a one-line progress note per wave as you go. At the end, present the **Verdict** + **Conversation starters** inline and stop — wait for the user to pull a thread. Do not auto-act on the recommendations.

**`--background` mode:** run to completion across turns. On wake, re-anchor from the state ledger (LH2) — never trust accumulated context after a resume. Write the report incrementally, then post an advisory:
```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/inbox-add.sh" \
  --source probe_done \
  --kind advisory \
  --severity moderate \
  --title "probe done on {slug} — {terminal state}" \
  --body "Verdict: {one line} (conf {X}). {N} hypotheses, {M} survived." \
  --options '[{"label":"Open report","command":"cat plans/meta/{date}-probe-{slug}.md"},{"label":"Re-probe deeper","command":"/meta-probe {target} --budget insane"}]' \
  --ref-file "plans/meta/{date}-probe-{slug}.md"
```

---

## Rules

- **Never edit tracked source; never commit.** Only writable artifact is the report under `plans/meta/`; experiments are scratch-only, cleaned up.
- **Diversity mandatory (T2)** — never two same-strategy agents; drop duplicate angles for distinct ones.
- **Evidence or it didn't happen (T6)** — every load-bearing claim cites `file:line`, command output, or doc; unsupported reasoning rejected.
- **No self-critique as primary check (T4)** — other agents attack each hypothesis.
- **Majority vote banned (T7)** — survival is adversarial, not popular.
- **Honor forbidden ruts (T8)** — re-proposing a rut requires new evidence overturning the prior failure.
- **Stable uncertainty is valid** — don't manufacture confidence to "finish"; name the decisive experiment.
- **Long-horizon discipline mandatory at high/insane (LH1–LH8)** — distilled artifacts only, state in the ledger, every round scores progress, ceilings graceful; flat rounds end it.
- Respect budget and `--rounds` / `--no-converge`. Insane: min 3 rounds, no early convergence exit; stall (LH5) and ceilings (LH6) always apply.

---

## Step — Self-Improving Detection (post-probe)

After the report is written, check whether the same **bias rut** has now appeared in 2+ separate probes (`find plans/meta -name "probe-*.md"` → compare Forbidden-ruts sections). If so, generalize it into a Learned Pattern and append it below so future probes pre-load it in Wave 0.

## Learned Patterns

<!-- Auto-maintained. Each entry is a recurring bias rut to pre-load into Wave 0 forbidden ruts. -->
<!-- Generalized only — no project-specific one-offs. Max 20; meta-audit enforces the cap. Append-only except via meta-audit. -->

(No patterns yet. Patterns are added automatically when the same rut recurs across 2+ separate probes.)
