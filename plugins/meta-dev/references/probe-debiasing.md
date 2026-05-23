# Probe De-biasing Protocol — breaking LLM tunnel-vision loops

The loop-breaking engine behind `/meta-probe`. Each technique below is grounded in research and stated as an **operational rule** the command's waves enforce. The whole point: when a hard problem keeps drawing the same wrong answer, the structure must make it *mechanically impossible* for agents to re-tread the rut.

> **Core finding.** Homogeneous agents converge on the *same* bias. Majority-vote is unreliable when agents share priors. So depth alone does not help — **structured diversity + adversarial pressure + ground truth** do.

---

## T1 — Anti-anchoring: neutral re-framing + premise inversion

**Rule.** Wave 0 rewrites the issue into a **neutral problem statement** stripped of blame/framing language ("it keeps failing", "the model is dumb about X"). Angle agents receive the neutral statement, **never the prior conclusions as fact**. A subset of agents is handed the **inverted premise** (assume the opposite of the leading assumption is true) and told to follow it honestly.

**Why.** Prior framing anchors every downstream token. Inversion forces exploration of the branch the rut never visits.

---

## T2 — DMAD: diverse strategies, never clones

**Rule.** Every Wave 1 agent uses a **different investigative method** (root-cause, best-practice, UX, elegance, robustness/FMEA, security, performance, git-archaeology, empirical reproduction, analogical, assumption-inversion, adversarial). Never spawn two agents that do the same kind of thinking.

**Why.** Diverse Multi-Agent Debate breaks "mental set" — a fixed mindset that fixates on one solution path. Identical agents just amplify the shared error. ([breaking mental set](https://openreview.net/forum?id=t6QHYUOQL7), [belief entrenchment → robust reasoning](https://arxiv.org/pdf/2503.16814))

---

## T3 — Preset opposing stances (counterfactual debate)

**Rule.** In Wave 2, assign each competing hypothesis a **fixed advocate** whose job is to defend that stance as hard as possible — even the unlikely ones. Stances are assigned, not chosen.

**Why.** Counterfactual debating with preset stances eliminates hallucination/entrenchment better than open-ended debate, because no agent is allowed to quietly defect to the consensus. ([counterfactual debating](https://arxiv.org/pdf/2406.11514))

---

## T4 — External critique over self-critique

**Rule.** No agent reviews its own output. Each hypothesis is attacked by a **separate critique agent** that did not produce it. Self-refine / "are you sure?" passes are forbidden as the primary check.

**Why.** Models can't reliably assess their own reasoning (egocentrism); critiquing *someone else's* answer reliably invokes critical thinking. ([verify-first is almost free](https://arxiv.org/pdf/2511.21734))

---

## T5 — Consider-the-opposite + pre-mortem (mandatory)

**Rule.** Every angle agent must produce **a concrete counterexample to its own conclusion**. Before any hypothesis is accepted, run a **pre-mortem**: "assume the obvious fix shipped and the problem persists — explain why." A hypothesis that can't survive its own pre-mortem is demoted.

**Why.** Asking the model to generate counterexamples consistently cuts confirmation bias (rule-discovery 42%→56%). ([failing to falsify](https://arxiv.org/pdf/2604.02485), [confirmation bias in CoT](https://arxiv.org/pdf/2506.12301))

---

## T6 — Ground-truth injection (break the cognitive island)

**Rule.** Every load-bearing claim must be **anchored to evidence** — a code line read (`file:line`), a command run, a measured result, a cited doc. Unsupported assertion is rejected. When analysis can't separate two hypotheses, Wave 3 **runs an experiment** (reproduce / instrument / targeted test) to settle it with real data. Read-only on the tree; experiments in scratch; never edit or commit.

**Why.** Injecting external knowledge breaks "cognitive islands" where agents reinforce each other's unfounded beliefs. Evidence beats eloquence — LLMs can be talked into falsehoods by confident, verbose reasoning. ([learning to break](https://www.sciencedirect.com/science/article/abs/pii/S0925231224018344))

---

## T7 — Fresh-context entrenchment guard + banned majority vote

**Rule.** Each debate round injects **one fresh-context agent** that has not seen the prior debate, to judge from scratch. **Majority vote is BANNED** as the decision rule. A hypothesis survives only by **withstanding the strongest counterargument** (adversarial synthesis), not by being the most popular.

**Why.** Two LLMs will both be certain they won a debate; consensus among similar agents signals shared bias, not truth. A naive vote launders that bias into a confident wrong answer. ([two LLMs debate, both certain](https://arxiv.org/html/2505.19184v1), [adaptive stability detection](https://arxiv.org/html/2510.12697v1))

---

## T8 — Forbidden ruts (the explicit loop-breaker)

**Rule.** Wave 0 builds a **forbidden-rut list**: mistakes, assumptions, and fixes already tried (mined from recent `git log`, prior `plans/meta/probe-*.md` reports, and the conversation framing). Every agent receives this list and is **forbidden to propose anything on it** unless it brings *new evidence* that overturns why it failed before. Recurring ruts are promoted into the command's `## Learned Patterns` footer so future probes pre-load them.

**Why.** This is the direct antidote to "the loop keeps making the same mistake." If the rut is named and banned up front, the only remaining moves are new ones.

---

## Terminal states

A probe ends in exactly one of:
- **Convergence** — one hypothesis dominates, evidence-backed, survived strongest counter.
- **Stall** — 2 consecutive rounds with ≈0 progress score (see meta-probe LH5). Long is fine; flat is not. Emit best-conclusion-so-far.
- **Ceiling** — a hard cap hit (rounds / recursion depth / agent count, LH6). Graceful: land the best-supported verdict + remaining forks.
- **Exhaustion** — the exploration frontier is dry: the end-of-round contemplation (meta-probe LH5) surfaces no remaining avenue that could change the verdict. This is the *intended* deep terminal — be exhaustive, then conclude. Don't spin rounds with no plausible payoff.
- **Stable uncertainty** — genuinely undecidable from available evidence; the report names the single decisive experiment that *would* resolve it. This is a valid, honest outcome — not a failure.

---

## Sources

- [Breaking Mental Set to Improve Reasoning through Diverse Multi-Agent Debate](https://openreview.net/forum?id=t6QHYUOQL7)
- [From Belief Entrenchment to Robust Reasoning in LLM Agents](https://arxiv.org/pdf/2503.16814)
- [Counterfactual Debating with Preset Stances for Hallucination Elimination](https://arxiv.org/pdf/2406.11514)
- [Asking LLMs to Verify First is Almost Free Lunch](https://arxiv.org/pdf/2511.21734)
- [Failing to Falsify: Evaluating and Mitigating Confirmation Bias in LMs](https://arxiv.org/pdf/2604.02485)
- [Unveiling Confirmation Bias in Chain-of-Thought Reasoning](https://arxiv.org/pdf/2506.12301)
- [Learning to Break: Knowledge-enhanced reasoning in multi-agent debate](https://www.sciencedirect.com/science/article/abs/pii/S0925231224018344)
- [Two LLMs Debate, Both Are Certain They've Won](https://arxiv.org/html/2505.19184v1)
- [Multi-Agent Debate for LLM Judges with Adaptive Stability Detection](https://arxiv.org/html/2510.12697v1)
