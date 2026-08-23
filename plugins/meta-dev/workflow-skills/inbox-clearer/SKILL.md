---
name: inbox-clearer
description: "Process inbox items autonomously — fix auto-clearable issues via haiku/sonnet, escalate hard items to opus, surface advisories to user. Goal: drive issue inbox to zero, surface advisories clearly."
---

# Inbox Clearer

Goal: clear all **issue**-kind items, surface all **advisory**-kind items to user (never auto-resolve advisories — those need human green-light).

## Procedure

1. Load open items: `scripts/inbox-list.sh --status open`
2. **Split by kind:**
   - `advisory` → render to user with `options`, never auto-clear; user invokes one of the `options.command` entries
   - `issue` → proceed to clearing
3. Sort issues: severity DESC, then auto_clearable DESC, then age ASC
4. For each issue, **route by model tier** (cost discipline):
   - **trivial + auto_clearable:** haiku fix-agent direct, commit, resolve
   - **moderate:** sonnet — invoke specialized agent per source:
     - `overlord_finding` → sonnet fix-agent using recommended_action
     - `review_failure` → invoke `code-review-protocol` skill → sonnet fix-agent
     - `repair_dossier` → already 3-attempts failed; convert to advisory, surface
     - `sweep_anomaly` → haiku sweep-agent
     - `classify_blocked` → re-run `/meta-classify` (sonnet)
     - `security_alert` → NEVER auto-fix; convert to advisory
   - **high:** sonnet — generate fix proposal only, mark `in_progress`, surface for approval (don't auto-commit)
   - **critical / structural:** **opus** — escalate to heavy thinking. Spawn `Agent({ model: "opus", subagent_type: "feature-dev:code-architect", ... })` for deep analysis. Output fix proposal as advisory.
5. After each resolution: commit, then `inbox-resolve.sh <id>`. Atomic.
6. After pass: print summary + render INBOX.md

## Model Tier Discipline

| Severity | Default model | When |
|----------|--------------|------|
| trivial  | haiku        | mechanical fixes (checkbox toggle, lint, format) |
| low      | haiku        | simple patches with clear recommended_action |
| moderate | sonnet       | most fixes — judgment + code change |
| high     | sonnet       | propose fix, don't commit; need user OK |
| critical | **opus**     | architecture, security, money-path, deep root-cause |

Override via `/meta-inbox clear --model opus` (forces opus for all) or settings: `inbox.clear_model_override: "opus" | "sonnet" | null`.

## Stop Conditions

- 3 consecutive failures on same item → mark `blocked`, move on
- Item requires destructive op (rm, drop, force-push) → surface, don't execute
- Item touches money/auth/migrations → surface, don't execute (hard rule from the host project contract)
- User-set `auto_clear_severity` cap exceeded → stop and surface remainder

## Invocation Modes

- `clear all` / `clear inbox` → run full pass, auto-fix everything auto-clearable
- `clear inbox with best practices recommendations` → same + invoke `code-review-protocol` per fix before commit
- `clear inbox --source overlord_finding` → filter to one source
- `clear inbox --severity trivial` → cap severity
- `clear inbox --dry-run` → list what WOULD be done, no execution

Detail: references/clearing-strategies.md, references/dispatch-table.md.
