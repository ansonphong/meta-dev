# Autonomous Mode — `--autonomous`

`--autonomous` is valid **anywhere in any meta-dev command's arguments**. It is
a global modifier, not a per-command flag, and it needs no explanation from the
user. It means:

> Continue unattended within the task's existing scope.

Invoking `--autonomous` authorizes unattended progress on the selected task.
Explicit authorization persists across stages, workers, repairs, verification,
and necessary integration within scope. Own the approved job through completion;
include its authority and constraints in worker briefs, resumes, and handoffs.
Make reversible decisions within scope without asking. A concrete blocker or
genuinely new authority parks only the affected branch and its dependents;
continue independent authorized work.

`--autonomous` supplies explicit Stage-5 permission only for a scoped implementation request;
when modifying a read-only audit/review, it preserves that read-only boundary.
For implementation it satisfies the execution gate subject to the root
`AGENTS.md` permission policy. Neither this flag nor a stage ceiling (`--to 6`)
turns a read-only request into authorization to edit its findings.

## Detection

The `on-stage-prompt.sh` UserPromptSubmit hook recognizes the exact, unquoted,
case-sensitive token on the first invocation line: anywhere in a leading slash
command's arguments, or as a leading flag for a bare task. For example,
`/meta-execute plans/example --autonomous` or `--autonomous implement the approved job`.
Quoted tokens, fenced examples, discussion such as "explain --autonomous", and
tokens after an option terminator (`--`) or on later discussion lines do not
activate the hook. The hook injects the contract even when the selected command's
markdown never mentions the flag.
Unambiguous instructions in prose ("own the approved job while I sleep") also
authorize unattended work; a discussion of those phrases does not.

`--autonomous` **implies and supersedes** cruise: it sets cruise mode, `--gate
none` and `--no-pause` for optional cadence prompts, not permission or human
acceptance gates. Optional external consultation uses existing authorization
when it covers that dispatch; otherwise it needs new authority. Do not ask the user to
also pass `--cruise`; do not treat the two as conflicting.

## What it suppresses

| Suppressed | Was |
|---|---|
| Stage-transition prompts | "Stage N complete. Ready for N+1?" → auto-advance |
| Optional cadence pauses | continue already-authorized work, including authorized sensitive actions |
| "Proceed? / ready? / shall I dispatch?" | already banned by the Anti-Paranoia Charter; now doubly so |
| Judgment-call escalations | decide within granted scope or park with evidence; optional consultants require authorization |
| Human-verify gates mid-run | **deferred to the end**, collected in a punch list |
| Per-stage confirmation of plan/design artifacts | advance at the stage's exit criteria unless human approval was explicitly reserved |

## The hard floor — what `--autonomous` NEVER suppresses

`--autonomous` buys *unattended*, not *unsafe*. These hold in autonomous mode
exactly as they hold everywhere, because none of them is a question about the
user's preference:

1. **Guard-hook denies.** `rebase`, `stash`, `push --force`, `DROP TABLE`,
   `curl|bash`, tree-wide staging. Mechanically denied; no flag reaches them.
2. **The git bans.** No `rebase`/`pull`/`merge` without `--ff-only`, no
   `stash`, no `--amend`, no `checkout`/`restore` of a peer's work.
3. **Mandatory protections.** Preserve the instruction hierarchy and environment protections:
   higher-priority instructions, sandbox restrictions, mandatory guards,
   and explicitly reserved human gates. Do not bypass a denial or claim unlimited authority.
4. **Authority for sensitive actions.** Perform already-authorized sensitive work
   without redundant approval. Auth, schema/migrations, payments, destructive work,
   cross-repo contracts, deployment, publishing, releases, and spend-or-send actions
   need explicit authority covering the action and target. Existing authority counts;
   a risk label alone is not a blocker. An implementation request does not by itself
   authorize a production deployment, live migration, or unrelated purchase/message.
   Use credentials only through authorized mechanisms for the approved target;
   never expose secrets or obtain broader access to bypass a blocker.
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
Park material scope ambiguity, genuinely new authority, unavailable capabilities,
mandatory protections, or reserved human gates with evidence and the concrete
unblocking action. Do not manufacture blockers from reversible implementation
choices or already-granted authority.
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
Never report a denied or unavailable operation as successful.
