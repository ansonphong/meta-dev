---
name: meta-review-design
description: Design quality audit — scores UI against coherence, originality, craft, functionality with AI slop detection and anti-sycophancy rules
argument-hint: <component-path | page-url | "current"> [--fix] [--depth shallow|standard|deep]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-review-design

Design quality scoring. Detects AI slop patterns. Anti-sycophantic — grades honestly, never hedges.

## Rubric

- **Design Coherence** (30%): unified mood, dark theme, purple/gold, glass morphism
- **Originality** (25%): custom decisions, dream-themed, NOT generic SaaS
- **Craft** (25%): typography hierarchy, spacing rhythm, color harmony, motion
- **Functionality** (20%): states (loading/error/empty), responsive, accessible

AI slop detection (10 patterns) auto-deducts from scores.

Quality bar: B (7.0) passes. C requires fixes. D/F blocks.

With `--fix`: applies remediation for below-B findings.

Config: `plans/_dashboard/settings.json` (depth default, fix toggle).
