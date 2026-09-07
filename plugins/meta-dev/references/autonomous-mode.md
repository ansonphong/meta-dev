# Autonomous Mode — `--autonomous`

`--autonomous` is valid **anywhere in any meta-dev command's arguments**. It is
a global modifier, not a per-command flag, and it needs no explanation from the
user. It means:

> Continue unattended within the task's existing scope.

The user typing `--autonomous` has authorized unattended progress within the
selected task's existing scope, not a materially different action.
Make reversible decisions within that scope. Material ambiguity or new authority
parks the affected branch; independent authorized work can continue.

`--autonomous` supplies explicit Stage-5 permission only for a scoped implementation request;
when modifying a read-only audit/review, it preserves that read-only boundary.
For implementation it satisfies the execution gate subject to the root
`AGENTS.md` permission policy. Neither this flag nor a stage ceiling (`--to 6`)
turns a read-only request into authorization to edit its findings.

## Detection

Recognized when the token `--autonomous` appears anywhere in `$ARGUMENTS`, on
any command. The `on-stage-prompt.sh` UserPromptSubmit hook detects it on the
raw prompt and injects the contract, so it applies even on commands whose
markdown never mentions it. Synonyms in prose ("overnight", "while I sleep",
"unattended run to the end") carry the same intent — honor them.

`--autonomous` **implies and supersedes** cruise: it sets cruise mode, `--gate
none` and `--no-pause` for optional cadence prompts, not permission or human
acceptance gates. Optional external consultation still requires its own
configured authorization. Do not ask the user to
also pass `--cruise`; do not treat the two as conflicting.

## What it suppresses

| Suppressed | Was |
|---|---|
| Stage-transition prompts | "Stage N complete. Ready for N+1?" → auto-advance |
| Optional cadence pauses | continue only already-authorized work; safety vetoes still park the affected subject |
| "Proceed? / ready? / shall I dispatch?" | already banned by the Anti-Paranoia Charter; now doubly so |
| Judgment-call escalations | decide within granted scope or park with evidence; optional consultants require authorization |
| Human-verify gates mid-run | **deferred to the end**, collected in a punch list |
| Per-stage confirmation of plan/design artifacts | auto-accept at the stage's exit criteria |

## The hard floor — what `--autonomous` NEVER suppresses

`--autonomous` buys *unattended*, not *unsafe*. These hold in autonomous mode
exactly as they hold everywhere, because none of them is a question about the
user's preference:

1. **Guard-hook denies.** `rebase`, `stash`, `push --force`, `DROP TABLE`,
   `curl|bash`, tree-wide staging. Mechanically denied; no flag reaches them.
2. **The git bans.** No `rebase`/`pull`/`merge` without `--ff-only`, no
   `stash`, no `--amend`, no `checkout`/`restore` of a peer's work.
3. **Deploy, ship, publish, release.** An unattended run does not push to
   production, does not `npm publish`, does not run a real migration. It
   prepares them and stops at the door.
4. **The safety veto list** — destructive,
   security, money-path, schema, cross-repo contract, spend-or-send, scope
   expansion. These halt the subject and land in the report. This safety floor
   applies without calling or installing a consultant.
5. **Human-verify checkboxes stay unchecked.** `by eye` / `by hand` / `gpu` /
   `manual` boxes are the user's smoke test. `planctl` mechanically refuses to
   flip them without `--human`, and **autonomous mode must never pass
   `--human`.** Flipping the user's eyes-on gate on their behalf while they
   are absent is forging a verification, not automating one. Defer, never flip.
6. **TRUE BLOCKERs still halt** — but they halt *that subject only*. Other
   queued work continues. The blocker goes in the report, not into a prompt.

**Halting is not the same as asking.** In autonomous mode a hard stop parks the
affected subject, records why, and lets the run continue elsewhere. The run
ends when no authorized unblocked work remains. Do not keep polling for authority.

## Deferred gates — the punch list

Every gate that would have paused for human eyes accumulates instead:

- Human-verify checkboxes (`by eye`/`gpu`/`manual`) — left unchecked, listed
- Visual/UI review of anything rendered
- Smoke tests needing an interactive runtime or separately authorized environment
- Slow / integration / GPU test markers deferred by the Fast Test Doctrine
- `REVIEW-ME` reversible product-taste decisions requiring operator acceptance

Do not automatically run broad or separately authorized checks at the end.
Run only declared focused checks within existing authorization. What genuinely needs the operator's eyes is what the
punch list is for.

## Judgment calls

Make reversible decisions within granted scope and record the rationale.
Material ambiguity, scope expansion, or a permission boundary parks that branch.
An optional configured consultant may help only when authorized; autonomous mode
never adds paid external dispatch permission. Its confidence does not override
security or acceptance evidence. See `references/work-ladder.md`.

## Autonomous Run Report — the deliverable

The report is the durable record of the unattended run.

> **Card format:** open-right chassis, 9-glyph vocabulary, `CARD_W = 74` —
> see [`status-cards.md`](status-cards.md). The row labels below are what is
> specific to this report.

Close every `--autonomous` run with:

```
┌─ AUTONOMOUS RUN REPORT — <subject> ─────────────────────────────────────
│ <start> → <end>
├─ LANDED ────────────────────────────────────────────────────────────────
│ ✅  <n> tasks · <n> commits · <plans touched>
├─ DECIDED ───────────────────────────────────────────────────────────────
│ ✅  <n> decisions within granted scope
│ ▸ <question> → <decision> · <evidence and rationale>
├─ PARKED ────────────────────────────────────────────────────────────────
│ ⏺  <n> subjects halted
│ ▸ <subject> — <why> · <what would unblock>
├─ YOUR EYES ─────────────────────────────────────────────────────────────
│ 🔒  <n> deferred gates
│ ▸ [ ] <by-eye item>
│ ▸ [ ] REVIEW-ME: <reversible decision needing acceptance>
├─ RESIDUAL ──────────────────────────────────────────────────────────────
│ <the honest risk statement>
└─────────────────────────────────────────────────────────────────────────
```

Report what actually happened. A red test says red, a skipped step says
skipped. Include consultant identity and confidence only if an authorized
consultation actually occurred; never invent either. Read-only runs report
findings, not implementation commits. Unresolved human gates stay unresolved.
