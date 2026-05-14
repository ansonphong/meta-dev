---
name: meta-ux
description: Comprehensive UX evaluation and improvement — iterative multi-wave assessment from first principles, brand identity, blue ocean strategy
argument-hint: [plan-path | "running app" | feature:<name>] [--depth shallow|standard|deep] [--focus <area>] [--rounds N]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-ux

Multi-wave UX evaluation. Not a code review — an experience audit.

## Waves

1. Context gathering (parallel haiku agents): platform understanding, state audit, competitive landscape, personas
2. First-principles assessment: value proposition, core loop, IA, emotional design, friction audit, mobile readiness
3. Flow-vs-Defense audit (MANDATORY) — 5 rules calibration
4. Ethical Boundary audit (MANDATORY) — money/consent/content check. Violation = blocker.
5. Opportunity mapping: blue ocean, open source leverage, engagement patterns, accessibility
6. Synthesis: score card, top 10 improvements, UX debt inventory, roadmap

Output: `plans/meta/ux-assessment-{date}.md`. Config: `plans/_dashboard/settings.json`.
