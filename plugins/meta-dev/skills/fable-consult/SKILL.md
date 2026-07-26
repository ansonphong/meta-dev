---
name: fable-consult
description: "Consult Fable 5 before escalating a judgment call to the human. Use when a long-horizon or autonomous run hits a hard architecture / design / implementation-taste decision it would otherwise stop and ask the human approver about. Fable answers with a recommendation, a confidence score, and a falsifier; a verdict that clears 0.90 AND carries evidence is adopted and logged, anything weaker escalates to the human with Fable's recommendation as the lead option. Safety-class decisions (destructive, deploy, security, money, schema, cross-repo) never route here — they always reach the human."
---

# Fable Consult — ask the smartest model before you wake the human

An execution run that stops to ask a question costs the user a round-trip and,
on an overnight run, costs them the whole night. Most of what gets escalated is
not a question only the human approver can answer — it is a hard question the run was not
confident enough to answer itself. **Those go to Fable first.**

This skill is the standard escalation pre-step. It does not remove the human
gate; it stops the human gate from firing on questions a stronger model can
close out.

## When to consult

Consult Fable when the run is about to halt on a **judgment call**:

- Architecture — which of two structures to build, where a boundary belongs
- Design — how to model state, name a contract, shape an API
- Implementation taste — pattern choice, module structure, two defensible paths
- Ambiguity in the plan — the plan under-specifies and you must interpret it
- A hard bug the run cannot crack, where the next move is genuinely unclear
- Trade-off calls — performance vs. clarity, coupling vs. duplication

Consult Fable **before** you emit the escalation, never after. The escalation
you eventually send (if you send one) must already contain Fable's answer.

## When NOT to consult — the veto list

These reach the human **regardless of what Fable says and regardless of
confidence**. Fable's opinion never unlocks them. Do not consult; escalate
directly (or, under `--autonomous`, halt that subject and report — see the
plugin-level `autonomous-mode` reference).

| Class | Examples |
|---|---|
| Irreversible / destructive | deleting data, dropping a table, rewriting history, force-push |
| Deploy / release | shipping to prod, `npm publish`, cutting a release, migrations run for real |
| Security boundary | auth, crypto, Ed25519 licensing keys, permission checks, secrets |
| Money path | payments, pricing, Stripe, anything that moves value |
| Schema / migration | DB schema change, migration authoring, serialization format change |
| Cross-repo contract | an API surface APP/WWW/GALLERY share |
| Spend or send | anything costing real money or emailing real users |
| Scope expansion | building something the plan does not contain |

**Product taste is a special case.** Brand, naming, pricing copy, and the shape
of a user-facing flow belong to the human approver, not Fable. But under `--autonomous` these
must not halt the run: take Fable's **most reversible** option, mark it
`REVIEW-ME`, and land it in the morning punch list. Authority preserved, sleep
preserved.

## The confidence threshold is not a vibe check

**A self-reported confidence number is not a measurement.** A model asked "how
sure are you" produces a number that tracks its own fluency, not its
correctness, and it skews high. A gate that trusts a bare `0.95` will pass
essentially everything and quietly become an autonomy rubber stamp.

So the 0.90 bar is **never applied to the number alone.** It is applied to a
number that has survived three structural checks. Any verdict failing any check
is **capped at 0.89 and escalates**, whatever it claimed:

1. **It must name a falsifier.** `what_would_make_this_wrong` must describe a
   concrete, checkable condition. "Nothing, this is clearly right" is a failed
   check, not a strong one — confidence without a stated way to be wrong is the
   signature of a model that has not modelled its own uncertainty.
2. **It must cite evidence.** `evidence` must carry real `file:line` references
   the consult actually read. A recommendation reasoned from the packet alone,
   with no code inspected, does not clear the bar.
3. **It must declare what it could not verify.** If `unverified` is non-empty
   and any entry is load-bearing for the recommendation, the verdict is capped.

This is the whole reason the gate is worth having. Strip these and you have not
built a check — you have built a way for the run to authorize itself.

## Procedure

### 1. Build the consult packet

Self-contained — the consult is a *fresh* process with none of your context:

- **question** — the single decision, stated as a decision, not a topic
- **why_blocked** — what the run cannot do until this is answered
- **options** — every path considered, with the trade-off you already see
- **constraints** — plan text, conventions, CLAUDE.md rules that bind the answer
- **files** — the paths Fable should read to ground itself (be generous)
- **reversibility** — is the resulting change cheap or expensive to undo?

### 2. Dispatch

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/fable-consult.sh \
  --question "<the decision>" \
  --packet <path-to-packet.md> \
  --plan <plan-path> \
  [--autonomous]
```

The script pins `--backend fable --readonly --effort xhigh`, enforces the caps
and the veto list mechanically, applies the calibration caps above, writes the
decision log, and exits with the routing verdict. **Read only its exit code and
its printed verdict block** — do not pull the raw transcript into your context.

Read-only is deliberate: a consult **advises**, it never edits. The run applies
the decision, so the decision stays attributable to the run that made it.

### 3. Route on the exit code

| Exit | Verdict | What you do |
|---|---|---|
| `0` | **ADOPT** | Fable cleared the bar. Take the recommendation, note it in your report, continue. Do not re-litigate it. |
| `10` | **ESCALATE — low confidence** | Ask the human. The recommendation still leads the options (below). |
| `11` | **ESCALATE — veto class** | The question was never Fable's to answer. Ask the human. |
| `12` | **DEFER** | `--autonomous` + reversible + user-visible taste. Apply Fable's most reversible option, mark `REVIEW-ME`, keep going. |
| `2` | error | Consult itself failed. Treat as ESCALATE — never as ADOPT. Fail closed. |

**Fail closed, always.** A consult that errors, times out, returns malformed
JSON, or cannot reach the backend is an escalation, never an adoption. The
absence of an objection is not an approval.

### 4. When you escalate, lead with Fable's answer

An escalation after a consult is **never** a bare question. Present it so the
human can approve in one word:

```
⟡ DECISION NEEDED — <the question>

  Blocked: <what cannot proceed>

  ▸ FABLE RECOMMENDS (confidence 0.72):
      <recommendation>
      Why: <reasoning, 1–2 lines>
      Wrong if: <the falsifier>
      Unverified: <what it could not check>

  Other options:
    [B] <option> — <trade-off>
    [C] <option> — <trade-off>
```

The confidence number goes in the report **exactly as returned**. Do not round
it up, do not editorialize it, and do not present a 0.55 recommendation with
the same weight as a 0.89 one — the number is the user's signal for how hard to
look at it.

## Caps — a consult loop is worse than an escalation

- **One consult per question.** Same question a second time → escalate. A run
  that re-asks is a run going in circles, and Fable will not break the circle.
- **Default 5 consults per run** (`META_DEV_FABLE_CONSULT_CAP`). On the cap:
  escalate everything after it. A run burning consults is a run whose plan was
  under-hardened — that is a signal to surface, not to spend through.
- **Never consult about tree state.** Dirty files, peer sessions, lock
  contention are not judgment calls. Commit and charge on (CLAUDE.md Rule #2).

## The decision log — the morning report

Every consult appends one line to `plans/_dashboard/fable-decisions.jsonl`,
whatever the outcome. This is the point of the feature on an overnight run:
The human approver receives an auditable list of what was decided in their absence, with the
confidence and the falsifier attached, and can reverse any of it.

A decision made autonomously and *not* logged is indistinguishable from a
decision nobody made. Log first, then act.

Render the log at the end of any `--autonomous` run (see the plugin-level
`autonomous-mode` reference → Autonomous Run Report).
