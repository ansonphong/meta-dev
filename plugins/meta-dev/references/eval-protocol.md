# Evaluation Protocol — Health Check, Multi-Round Loop, Report

## Environment Health Check

Before running evaluation agents, verify the target application is running:

1. Read health check endpoints from config: `bash scripts/config-get.sh meta_dev.eval.health_checks`
2. For each endpoint: curl with timeout, confirm 2xx response
3. If any endpoint fails → report "Cannot evaluate: service not running at <url>", exit
4. If no health checks configured → skip, warn that eval runs against static code only

## Multi-Round Evaluation Loop

1. **Round 1:** Dispatch all 8 agents (from `references/eval-agents.md`). Collect findings.
2. **Triage:** Classify findings by severity. Auto-fix trivials. Bundle the rest.
3. **Fix round:** Apply fixes for all findings. Commit.
4. **Round 2:** Re-dispatch agents. Check if findings resolved. Check for regressions.
5. **Grade:** If grade < B after Round 2 → flag for human review. If grade ≥ B → pass.
6. **Max rounds:** 3. After 3 rounds, report best grade achieved.

## Dead-Ends & Regression Check

Before evaluating, read any `FAILURES.md` in the plan directory. Cross-reference:
- Did this implementation re-attempt any documented dead-end approach?
- If yes → flag as regression risk (the same failure may recur)

## Structured Report Template

```markdown
# Evaluation Report — <plan-name>

**Date:** <YYYY-MM-DD>
**Evaluator model:** <model>
**Rounds:** N
**Final grade:** <grade>

## Agent Findings Summary

| Agent | Critical | High | Medium | Low | Notes |
|-------|----------|------|--------|-----|-------|
| API Contract | 0 | 1 | 2 | 0 | ... |
| Completeness | 0 | 0 | 1 | 3 | ... |
| ... | | | | | |

## Design Quality

| Dimension | Score |
|-----------|-------|
| Visual Accuracy | X/10 |
| Interaction Fidelity | X/10 |
| Component Consistency | X/10 |
| Accessibility | X/10 |
| **Overall Grade** | **X.X/10** |

## Resolved in Round 2

- [finding] → fixed in <sha>

## Unresolved

- [finding] → reason not fixed

## Verdict

<OVERALL_ASSESSMENT>
```

## Tuning Rules for Evaluators

1. Be skeptical — assume nothing works until you see it work
2. Test like an end user — click through flows, don't just read code
3. Grade against the design doc, not against "what's reasonable to expect"
4. Specific findings > vague impressions — always cite file:line
5. If a design doc is vague, flag that as a design gap (don't guess)
6. Cross-reference: if Agent A and Agent B both flag the same file, escalate severity
7. Dead-end recurrence = automatic critical finding
8. Empty stub grep = minimum bar, not evidence of quality
