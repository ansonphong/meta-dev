# Completion Banner Layout Spec

Shared layout spec for `completion-render.py`.

## Banner Structure

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ✦  meta-dev — COMPLETE  ✦                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

  Subject:      <name>
  Stages:       <from> → <to>
  Duration:     <time>
  Completed:    <datetime>

  ── Phase Results ──
  ✅ brainstorm          pass   → plans/<name>/brainstorm.md
  ✅ design              pass   → plans/<name>/design.md
  ✅ execute             pass   14/14 tasks DONE
  ❌ review              fail   grade D — needs fixes

  Tasks:    <N> total → <M> done, <K> failed
  Commits:  <N>
  Files:    <N> changed across <M> modules

  Deploy:   ✅ Deployed to production (build #N)
  Archive:  plans/_archive/<name>/

  ══════════════════════════════════════════════════════════════════════════════

  Follow-ups:
    • <item>
    • <item>
```

## Phase Status Icons

| Status | Icon |
|--------|------|
| pass   | ✅   |
| fail   | ❌   |
| skip   | ⏸   |

## Width Budget

- Max width: 100 columns
- Banner box: 100 chars (border included)
- Content lines: 2-space indent, content ≤ 96 chars
- Phase results: icon(2) + name(20) + status(6) + detail(≤68)
