# Forward Handoff — worked example + watch heuristics

## Proactive-watch heuristics (when to surface the one-line offer)

The watch fires when **boundary AND heaviness** are both true — never on either alone.

**Boundary signals** (a seam just opened):
- A task/plan checkbox just flipped to done and the commit landed.
- A `/meta-execute` task finished and committed.
- A phase/stage transition is about to start (Stage N → N+1 in the waterfall).
- The user said something terminal: "ok that works", "shipped", "done with that".

**Heaviness signals** (context is getting expensive):
- The session has run long (many tool calls, large files read, big diffs absorbed).
- You've absorbed noisy output (test logs, build output, long greps) that bloated context.
- You're about to pull in a large new surface (new subsystem, many files) that needs room.

**Anti-nag rule:** offer at most once per boundary. If the user ignores it and keeps working, stay silent until the *next* boundary. Never repeat the offer for the same seam. Never interrupt mid-task to offer it.

## Worked example

```markdown
# Forward Handoff — meta-compact skill integration

**Written:** 2026-06-14, after skill files committed.  ·  **Resume by:** reading this file, then doing ▶ NEXT ACTION.

## 🎯 Mission
Add a `meta-compact` skill to the meta-dev plugin: forward-moving compaction that writes a
handoff so post-compaction work continues seamlessly. Done = skill+commands shipped, version
bumped, pushed.

## ▶ NEXT ACTION  (do this first)
Run `bash plugins/meta-dev/scripts/test-plugin.sh` from the meta-dev repo root and confirm it
passes; if green, that's the last gate before push.

## 📍 State now
- **Done:** SKILL.md + meta-compact.md + compact.md authored; plugin.json bumped 1.1.12→1.1.13 (commit a1b2c3d).
- **In flight:** nothing — clean seam.
- **Git:** master · clean · last commit a1b2c3d "feat(compact): add meta-compact skill" · NOT pushed.

## 🗂 Working set
- plugins/meta-dev/skills/meta-compact/SKILL.md — the skill body
- plugins/meta-dev/commands/meta-compact.md — full command
- plugins/meta-dev/commands/compact.md — thin alias
- plugins/meta-dev/.claude-plugin/plugin.json:3 — version field

## 🔒 Decisions locked  (do NOT re-litigate)
- Both trigger modes (proactive watch + on-demand /meta-compact) — user chose "both".
- Handoff lives in the active plan's folder as a unique `handoff-<date>-<time>.md` — never overwritten, one file per compaction (full history kept per plan).
- Skill never runs /compact itself — hands trigger to user.

## ⚠️ Gotchas
- HARD RULE #1: every push MUST bump plugin.json patch or the version-keyed cache won't rebuild.
- Cache resolves versions with `ls | head -1` (lexical) — stale lower versions can shadow the new one; delete them.

## 🚫 Out of scope / do-not-touch
- The child application repositories — this is the meta-dev plugin only.
- Don't touch the model frontmatter of other commands — already all-opus.
```

Note how NEXT ACTION is a runnable command, Decisions kills re-debate, and Gotchas carries the
two traps (version bump + lexical cache resolution) that a backward summary would silently drop.
That forward delta is the entire value of the skill.
