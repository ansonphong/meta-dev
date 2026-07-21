# Autonomous Mode — `--autonomous`

`--autonomous` is valid **anywhere in any meta-dev command's arguments**. It is
a global modifier, not a per-command flag, and it needs no explanation from the
user. It means exactly one thing:

> **Run to the end. Do not wake me. I am asleep.**

The user typing `--autonomous` has pre-authorized the whole run and has left.
Every ambiguity resolves toward *keep going and report in the morning*, and
every gate that can be deferred is deferred rather than asked.

`--autonomous` **is** the explicit Stage-5 permission (CLAUDE.md's supreme
banner). It authorizes execution the same way `--to 6` or a spoken "go" does.

## Detection

Recognized when the token `--autonomous` appears anywhere in `$ARGUMENTS`, on
any command. The `on-stage-prompt.sh` UserPromptSubmit hook detects it on the
raw prompt and injects the contract, so it applies even on commands whose
markdown never mentions it. Synonyms in prose ("overnight", "while I sleep",
"unattended run to the end") carry the same intent — honor them.

`--autonomous` **implies and supersedes** cruise: it sets cruise mode, `--gate
none`, `--no-pause`, and turns the Fable consult on. Do not ask the user to
also pass `--cruise`; do not treat the two as conflicting.

## What it suppresses

| Suppressed | Was |
|---|---|
| Stage-transition prompts | "Stage N complete. Ready for N+1?" → auto-advance |
| Pause gates (`execute-charter.md` → Pause Gates) | money-path/release-stability auto-pause → still verified, not paused |
| "Proceed? / ready? / shall I dispatch?" | already banned by the Anti-Paranoia Charter; now doubly so |
| Judgment-call escalations | routed to `fable-consult` first — see below |
| Human-verify gates mid-run | **deferred to the end**, collected in a punch list |
| Per-stage confirmation of plan/design artifacts | auto-accept at the stage's exit criteria |

## The hard floor — what `--autonomous` NEVER suppresses

`--autonomous` buys *unattended*, not *unsafe*. These hold in autonomous mode
exactly as they hold everywhere, because none of them is a question about the
user's preference — each is a thing that cannot be undone in the morning:

1. **Guard-hook denies.** `rebase`, `stash`, `push --force`, `DROP TABLE`,
   `curl|bash`, tree-wide staging. Mechanically denied; no flag reaches them.
2. **The git bans.** No `rebase`/`pull`/`merge` without `--ff-only`, no
   `stash`, no `--amend`, no `checkout`/`restore` of a peer's work.
3. **Deploy, ship, publish, release.** An unattended run does not push to
   production, does not `npm publish`, does not run a real migration. It
   prepares them and stops at the door.
4. **The veto list** in `skills/fable-consult/SKILL.md` — destructive,
   security, money-path, schema, cross-repo contract, spend-or-send, scope
   expansion. These halt the subject and land in the report.
5. **Human-verify checkboxes stay unchecked.** `by eye` / `by hand` / `gpu` /
   `manual` boxes are the user's smoke test. `planctl` mechanically refuses to
   flip them without `--human`, and **autonomous mode must never pass
   `--human`.** Flipping the user's eyes-on gate on their behalf while they
   sleep is forging a verification, not automating one. Defer, never flip.
6. **TRUE BLOCKERs still halt** — but they halt *that subject only*. Other
   queued work continues. The blocker goes in the report, not into a prompt.

**Halting is not the same as asking.** In autonomous mode a hard stop parks the
affected subject, records why, and lets the run continue elsewhere. The run
ends when work runs out — never because it is waiting on a human who is asleep.

## Deferred gates — the punch list

Every gate that would have paused for human eyes accumulates instead:

- Human-verify checkboxes (`by eye`/`gpu`/`manual`) — left unchecked, listed
- Visual/UI review of anything rendered
- Smoke tests needing a running app, GPU, or Tauri shell
- Slow / integration / GPU test markers deferred by the Fast Test Doctrine
- `REVIEW-ME` product-taste calls Fable made reversibly (fable-consult → DEFER)

Run the **whole** deferred set at the END of the run, in one batch, as far as
it can be run without a human. What genuinely needs Phong's eyes is what the
punch list is for.

## Judgment calls → Fable, not the user

Under `--autonomous`, any decision that would otherwise stop the run to ask the
user routes through `skills/fable-consult` **first**. Fable's verdict is
adopted at ≥0.90 with evidence and a falsifier; below that, or on the veto
list, the subject parks and the question goes in the report with Fable's
recommendation as the lead option. Full contract and the calibration guard:
`skills/fable-consult/SKILL.md`.

## Autonomous Run Report — the deliverable

An autonomous run's real output is what the user reads over coffee.

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
│ ✅  <n> Fable consults — adopted <n>, deferred <n>
│ ▸ <question> → <decision> (0.94)
├─ PARKED ────────────────────────────────────────────────────────────────
│ ⏺  <n> subjects halted
│ ▸ <subject> — <why> · <what would unblock>
├─ YOUR EYES ─────────────────────────────────────────────────────────────
│ 🔒  <n> deferred gates
│ ▸ [ ] <by-eye item>
│ ▸ [ ] REVIEW-ME: <taste call Fable made reversibly>
├─ RESIDUAL ──────────────────────────────────────────────────────────────
│ <the honest risk statement>
└─────────────────────────────────────────────────────────────────────────
```

Report what actually happened. A red test says red, a skipped step says
skipped, a Fable decision shows its real confidence. An autonomous run the user
cannot trust the report of is worth less than no autonomous run at all — they
were asleep, this report is the entire record, and it is the only thing
standing between an unattended run and an unverifiable one.
