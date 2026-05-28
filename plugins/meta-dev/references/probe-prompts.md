# Probe Prompts — User Interview, Budget-Tiered Agents, Council Verdict

Supplements `references/probe-debiasing.md` (the de-biasing engine). This file adds the user-interview protocol, budget-tiered agent prompts, and council verdict gate.

## User Interview Protocol (Q1-Q6)

Before spawning any agent, conduct a structured interview. Ask these 6 questions ONE AT A TIME:

**Q1: What exactly is happening?** (symptoms, not theories)
**Q2: What did you expect to happen instead?** (desired outcome)
**Q3: When did this start?** (timeline, triggering event)
**Q4: What have you already tried?** (builds the forbidden-rut list — T8)
**Q5: What's your leading theory?** (captures the anchor to invert — T1)
**Q6: What information do you have that I don't?** (hidden context, private repos, API keys, recent changes not in git)

Each answer shapes the neutral problem statement fed to Wave 0.

## Budget-Tiered Agent Prompts

### Low Budget (2-4 agents, Haiku/Sonnet)

Minimal but diverse. 4 agents with different perspectives:

1. **Root-cause agent:** "Given this problem statement, trace the most likely root cause. Base your analysis on evidence from the codebase, not speculation."
2. **Best-practice agent:** "How would this problem typically be solved in this tech stack? Reference specific patterns from this codebase."
3. **UX agent:** "What does the user see? Walk through the user journey from trigger to failure."
4. **Security agent:** "Are there security implications? Check auth boundaries, input validation, data exposure."

### Medium Budget (6-8 agents, Sonnet)

Full DMAD spread (T2 — diverse strategies):

1. Root-cause | 2. Best-practice | 3. UX | 4. Elegance (simplest fix)
5. Robustness/FMEA (what could go wrong) | 6. Security | 7. Performance
8. Git-archaeology (when was this introduced? git log/blame)

### High Budget (10-12 agents, Sonnet + Opus synthesis)

Full DMAD + adversarial:

1-8 from medium, plus:
9. Empirical reproduction (reproduce the issue, instrument)
10. Analogical (find similar problems solved elsewhere in this codebase)
11. Assumption-inversion (assume the opposite of the leading theory — T1)
12. Adversarial (actively try to break proposed solutions)

**Synthesis agent (all budgets):** One agent reads ALL angle-agent outputs. Identifies convergent themes and divergent opinions. Flags contradictions. Prepares synthesis for council.

## Council Verdict Protocol (High Budget, Opus)

After synthesis, the council (1 Opus agent) issues a verdict:

**Verdict types:**
- **CONFIRMED** — high confidence, multiple agents converged, evidence-backed
- **TENTATIVE** — plausible but needs verification, one decisive experiment identified
- **REJECTED** — hypothesis survived scrutiny but evidence contradicts, or pre-mortem failed

**Council instructions:**
```
You are the council. You have:
- The neutral problem statement
- N angle-agent reports from diverse perspectives
- A synthesis report identifying convergence + divergence
- The forbidden-rut list (T8)

Your job: issue a verdict. CONFIRMED, TENTATIVE, or REJECTED.

Rules:
- You are NOT allowed to generate new hypotheses — only judge what was presented
- A hypothesis survives only by withstanding the STRONGEST counterargument (T7)
- Majority vote is BANNED — one well-evidenced dissenter outweighs 10 shallow agree-ers
- If genuinely undecidable, say TENTATIVE and name the single experiment that would resolve it
- Cite specific evidence (file:line, command output, doc reference) for every claim
```
