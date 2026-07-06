#!/usr/bin/env python3
"""Recompute the LIVE EXECUTION DASHBOARD progress block inside a campaign-runbook
markdown file, writing ONLY the span between two sentinel comments.  Idempotent.

CLI: runbook-render.py <runbook-file-path>
"""

import glob
import os
import re
import subprocess
import sys
import importlib.util
import pathlib

# ── import sibling plan-index.py (hyphenated filename) ──────────────────────
_p = pathlib.Path(__file__).with_name("plan-index.py")
_spec = importlib.util.spec_from_file_location("plan_index", _p)
plan_index = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plan_index)

# ── constants ───────────────────────────────────────────────────────────────
# The dashboard is driven by each plan's WATERFALL STAGE (frontmatter `stage:` 1..6),
# NOT its `status:` word. `status: done` at Stage 3 means "planning done", not shipped —
# a plan only reads as ✅ DONE once it has REACHED Stage 6 (REVIEW) with a done status.
STAGE_NAME = {
    0: "not started",
    1: "BRAINSTORM",
    2: "DESIGN",
    3: "PLAN",
    4: "HARDEN",
    5: "EXECUTE",
    6: "REVIEW",
}
STAGE_CIRCLED = {0: "○", 1: "①", 2: "②", 3: "③", 4: "④", 5: "⑤", 6: "⑥"}

SENTINEL_START = "<!-- RUNBOOK:PROGRESS:START"
SENTINEL_END = "<!-- RUNBOOK:PROGRESS:END -->"

MEMBERS_KEY = re.compile(r"^members:")
MEMBER_ITEM = re.compile(r"^\s+-\s+(.+)$")


# ── helpers ─────────────────────────────────────────────────────────────────
def parse_members(text):
    """Extract the ordered members: list from runbook frontmatter.

    plan-index.parse_frontmatter is a FLAT parser that won't return YAML
    lists, so we hand-roll this: after a line matching ``^members:`` collect
    subsequent lines matching ``^\\s+-\\s+(.+)$`` until a non-indented line.
    """
    members = []
    in_members = False
    for line in text.split("\n"):
        if MEMBERS_KEY.match(line):
            in_members = True
            continue
        if in_members:
            m = MEMBER_ITEM.match(line)
            if m:
                members.append(m.group(1).strip())
            elif line.strip() and not line.startswith(" "):
                break  # non-indented, non-empty line ends the list
    return members


def resolve_repo_root(runbook_path):
    """Run ``git -C <dir> rev-parse --show-toplevel`` to find the repo root."""
    runbook_dir = os.path.dirname(os.path.abspath(runbook_path))
    result = subprocess.run(
        ["git", "-C", runbook_dir, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Error: git rev-parse failed in {runbook_dir}: {result.stderr.strip()}",
              file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def parse_id_name(dir_basename):
    """Split a directory basename like '17-REPLAYABLE-PROVENANCE' into id + name.

    Leading token before the first '-' is the short id; remainder is the
    display name.  '13.5-SOURCE-ROOTED-GRAPH' → ('13.5', 'SOURCE-ROOTED-GRAPH').
    """
    if "-" in dir_basename:
        dash = dir_basename.index("-")
        return dir_basename[:dash], dir_basename[dash + 1:]
    return dir_basename, dir_basename


def read_plan(plan_path):
    """Read a plan file; return (text, fm_dict).  Missing file → (None, {})."""
    try:
        with open(plan_path, "r", encoding="utf-8") as f:
            text = f.read()
    except (FileNotFoundError, OSError):
        return None, {}
    fm, _ = plan_index.parse_frontmatter(text)
    return text, fm


def count_dir_checkboxes(member_dir, master_path):
    """Sum checkbox completion across the WHOLE member dir, not just the master.

    The execution checkboxes for a multi-phase plan live in its ``phase-*.md``
    files, NOT the ``00-master-plan.md`` index — so counting only the master
    badly under-reports progress (a plan 85% done through its phases shows 0%).
    Aggregate ``count_checkboxes`` over every ``*.md`` in the member dir (the
    master is one of them), and return ``(done, total, frac)``.
    """
    md_files = set(glob.glob(os.path.join(member_dir, "*.md")))
    md_files.add(master_path)
    done = total = 0
    for f in sorted(md_files):
        txt, _ = read_plan(f)
        if txt is None:
            continue
        cb = plan_index.count_checkboxes(txt)
        done += cb["done"]
        total += cb["total"]
    frac = (done / total) if total else 0.0
    return done, total, frac


def build_member_rows(members, repo_root):
    """Process each member plan into a dashboard row.

    Two INDEPENDENT signals per plan, shown in two columns:
      • WATERFALL STAGE — the plan's `stage:` frontmatter (1..6) → the "Stage" column.
        A plan reads ✅ DONE only once it has REACHED Stage 6 (REVIEW) with a
        done/completed status. `status: done` at an earlier stage means *that stage's*
        work is done (e.g. planning), NOT that the plan shipped — so it does NOT read
        as DONE. This is what keeps a merely-planned/hardened plan from saying DONE.
      • PHASE PROGRESS — the plan's internal phase-*.md files + checkbox completion →
        the "Phases" count + the Progress bar (execution progress within the plan).
    """
    rows = []
    for i, rel in enumerate(members):
        plan_path = os.path.join(repo_root, rel)
        member_dir = os.path.dirname(plan_path)
        dir_base = os.path.basename(member_dir)
        short_id, display_name = parse_id_name(dir_base)

        text, fm = read_plan(plan_path)
        if text is None:
            rows.append({
                "num": i + 1, "id": short_id, "name": display_name,
                "stage": 0, "stage_name": STAGE_NAME[0], "circled": STAGE_CIRCLED[0],
                "phases_done": 0, "phases_total": 1, "bar": "▱▱▱▱",
                "cb_done": 0, "cb_total": 0, "frac": 0.0,
                "is_done": False, "is_blocked": False, "is_current": False,
                "is_drift": False,
                "what": "", "rel_link": "",
            })
            continue

        status = str(fm.get("status", "draft")).strip().lower()
        try:
            stage = int(str(fm.get("stage", "0")).strip() or 0)
        except ValueError:
            stage = 0
        stage = max(0, min(6, stage))

        is_blocked = status == "blocked"
        is_done = stage >= 6 and status in ("done", "completed")

        # "What" column — frontmatter why: (fallback: H1 title), truncated ~50 chars
        what_raw = fm.get("why", "")
        if not what_raw and text:
            for line in text.split("\n"):
                if line.startswith("# ") and not line.startswith("## "):
                    what_raw = line[2:].strip().rstrip("#").strip()
                    break
        what_display = (what_raw[:50] + "…") if len(what_raw) > 50 else what_raw

        # relative link for → column
        rel_link = f"{dir_base}/{os.path.basename(plan_path)}"

        # checkbox completion across the WHOLE member dir (master + phase-*.md),
        # not just the master index — see count_dir_checkboxes.
        _done, _total, frac = count_dir_checkboxes(member_dir, plan_path)

        # phase-*.md files in the member's directory (non-recursive) = the phase count
        phase_files = glob.glob(os.path.join(member_dir, "phase-*.md"))
        phases_total = len(phase_files) if phase_files else 1
        phases_done = phases_total if is_done else round(frac * phases_total)

        # STAGE DRIFT — a plan ~fully checked off but still parked below Stage 6
        # (the "did the work, forgot to advance" failure that lets a handoff
        # silently overclaim "done"). Flag at ≥95% boxes AND stage < 6.
        is_drift = (not is_done) and stage < 6 and _total > 0 and frac >= 0.95

        bar_width = max(4, phases_total)
        bar = "▰" * phases_done + "▱" * (bar_width - phases_done)

        rows.append({
            "num": i + 1, "id": short_id, "name": display_name,
            "stage": stage, "stage_name": STAGE_NAME.get(stage, "?"),
            "circled": STAGE_CIRCLED.get(stage, "?"),
            "phases_done": phases_done, "phases_total": phases_total, "bar": bar,
            "cb_done": _done, "cb_total": _total, "frac": frac,
            "is_done": is_done, "is_blocked": is_blocked, "is_current": False,
            "is_drift": is_drift,
            "what": what_display, "rel_link": rel_link,
        })
    return rows


def compose_block(rows, members, repo_root):
    """Build the progress block: execution-order chain + per-plan table.

    Columns: # · Plan · Stage (waterfall 1..6) · Progress (bar + %) · What (why:/H1) · → (link).
    """
    # CURRENT = first member not yet DONE and not BLOCKED (serial execution order)
    current_idx = None
    for idx, row in enumerate(rows):
        if not row["is_done"] and not row["is_blocked"]:
            current_idx = idx
            break
    if current_idx is not None:
        rows[current_idx]["is_current"] = True

    done_count = sum(1 for r in rows if r["is_done"])
    n = len(rows)

    def chain_glyph(r):
        if r["is_done"]:
            return "✅"
        if r["is_blocked"]:
            return "!"
        if r["is_current"]:
            return "🔄"
        return "⬜"

    chain = " → ".join(f"**{r['id']}** {chain_glyph(r)}" for r in rows)
    chain += " → **Stage 6** ⬜"

    # now line — name the current plan AND its waterfall stage (no false "executing")
    if current_idx is not None:
        cur = rows[current_idx]
        cur_dir = os.path.basename(
            os.path.dirname(os.path.join(repo_root, members[current_idx]))
        )
        now_line = (f"{cur_dir} — Stage {cur['stage']} {cur['stage_name']} "
                    f"({cur['phases_done']}/{cur['phases_total']} phases)")
    else:
        now_line = "none — all plans through Stage 6"

    lines = []
    lines.append("")
    lines.append("### Execution order & package progress")
    lines.append("")
    lines.append(f"> {chain}")
    lines.append("")
    lines.append(f"**Plans done:** {done_count} / {n}  ·  **Now:** {now_line}")
    lines.append("")
    lines.append("| # | Plan | Stage | Progress | What | → |")
    lines.append("|---|------|-------|----------|------|---|")

    for row in rows:
        name_display = f"**{row['id']}** {row['name']}"
        if row["is_current"]:
            name_display += " ◄ NOW"
        stage_cell = f"{row['circled']} {row['stage_name']}"
        if row["is_drift"]:
            stage_cell += " ⚠"
        if row["is_blocked"]:
            stage_cell += " ⛔ BLOCKED"
        progress_cell = f"`{row['bar']}` {round(row['frac'] * 100)}%"
        what_cell = row.get("what", "")
        link_cell = f"[plan]({row.get('rel_link', '')})" if row.get("rel_link") else ""
        lines.append(
            f"| {row['num']} | {name_display} | {stage_cell} | {progress_cell} "
            f"| {what_cell} | {link_cell} |"
        )

    lines.append(
        "| — | **Stage 6** review · archive · runbook | — "
        "| `▱▱▱▱` | | |"
    )

    # STAGE-DRIFT note — surface "did the work, forgot to advance" so a handoff
    # can't silently overclaim done. Only emitted when at least one member drifts.
    drift = [r for r in rows if r["is_drift"]]
    if drift:
        lines.append("")
        detail = ", ".join(
            f"**{r['id']}** ({r['cb_done']}/{r['cb_total']} boxes, Stage {r['stage']})"
            for r in drift
        )
        lines.append(
            f"> ⚠ **Stage drift:** {detail} — ~fully checked off but still below "
            "Stage 6. Advance the plan's `stage:` (and run review) or it under-reports."
        )

    lines.append("")
    return "\n".join(lines)


def replace_block(original_text, block):
    """Insert *block* between the two sentinel lines, keeping the sentinels.

    Returns the new full-file text, or None if sentinels are missing.
    """
    lines = original_text.split("\n")
    start_line = end_line = None
    for i, line in enumerate(lines):
        if SENTINEL_START in line:
            start_line = i
        if start_line is not None and SENTINEL_END in line:
            end_line = i
            break

    if start_line is None or end_line is None:
        return None

    new_lines = lines[:start_line + 1] + [block] + lines[end_line:]
    return "\n".join(new_lines)


def update_frontmatter_date(text, fm, today):
    """If frontmatter has an 'updated:' key that differs from *today*, replace it."""
    current = fm.get("updated", "")
    if current and current != today:
        # Replace only the first occurrence (frontmatter) via partition trick
        needle = f"updated: {current}"
        if needle in text:
            return text.replace(needle, f"updated: {today}", 1)
    return text


# ── main ────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <runbook-file-path>", file=sys.stderr)
        sys.exit(1)

    runbook_path = sys.argv[1]
    if not os.path.isfile(runbook_path):
        print(f"Error: not a file: {runbook_path}", file=sys.stderr)
        sys.exit(1)

    repo_root = resolve_repo_root(runbook_path)

    # read runbook
    with open(runbook_path, "r", encoding="utf-8") as f:
        runbook_text = f.read()

    # parse members from frontmatter (hand-rolled — flat parser can't do lists)
    members = parse_members(runbook_text)
    if not members:
        print("Error: no members list found in runbook frontmatter", file=sys.stderr)
        sys.exit(1)

    # parse frontmatter for updated: tracking
    runbook_fm, _ = plan_index.parse_frontmatter(runbook_text)

    # build rows & compose the progress block
    rows = build_member_rows(members, repo_root)
    block = compose_block(rows, members, repo_root)

    # surface stage drift to stderr (visible to /runbook refresh + CI)
    for r in rows:
        if r["is_drift"]:
            print(
                f"⚠ stage-drift: {r['id']} is {r['cb_done']}/{r['cb_total']} boxes "
                f"({round(r['frac'] * 100)}%) but still Stage {r['stage']} — advance it.",
                file=sys.stderr,
            )

    # inject between sentinels
    new_text = replace_block(runbook_text, block)
    if new_text is None:
        print("Error: sentinel comments "
              f"('{SENTINEL_START}…' / '{SENTINEL_END}') "
              "not found in runbook", file=sys.stderr)
        sys.exit(1)

    # optionally bump updated: date
    today = subprocess.run(
        ["date", "+%Y-%m-%d"], capture_output=True, text=True
    ).stdout.strip()
    new_text = update_frontmatter_date(new_text, runbook_fm, today)

    # write back
    with open(runbook_path, "w", encoding="utf-8") as f:
        f.write(new_text)


if __name__ == "__main__":
    main()
