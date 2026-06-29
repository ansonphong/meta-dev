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
STATUS_GLYPH = {
    "done": "✅",
    "completed": "✅",
    "in_progress": "🔄",
    "blocked": "!",
}

STATUS_WORD = {
    "done": "✅ DONE",
    "completed": "✅ DONE",
    "in_progress": "🔄 EXECUTING",
    "blocked": "! BLOCKED",
}

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


def build_member_rows(members, repo_root):
    """Process each member plan and return a list of row dicts."""
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
                "status": "unknown", "glyph": "⬜",
                "status_word": "⬜ QUEUED",
                "phases_done": 0, "phases_total": 1,
                "bar": "▱▱▱▱", "done": 0, "total": 0, "pct": 0.0,
            })
            continue

        status = fm.get("status", "draft")
        cb = plan_index.count_checkboxes(text)
        done = cb["done"]
        total = cb["total"]
        pct = cb["pct"] / 100.0  # integer percent → fraction

        # phase-*.md files in the member's directory (non-recursive)
        phase_files = glob.glob(os.path.join(member_dir, "phase-*.md"))
        phases_total = len(phase_files) if phase_files else 1
        # A plan marked done reads as fully complete even if its checkboxes are
        # untracked (e.g. a design-doc member with no `- [ ]` items).
        if status in ("done", "completed"):
            phases_done = phases_total
        else:
            phases_done = round(pct * phases_total)

        bar_width = max(4, phases_total)
        bar = "▰" * phases_done + "▱" * (bar_width - phases_done)

        glyph = STATUS_GLYPH.get(status, "⬜")
        status_word = STATUS_WORD.get(status, "⬜ QUEUED")

        rows.append({
            "num": i + 1, "id": short_id, "name": display_name,
            "status": status, "glyph": glyph, "status_word": status_word,
            "phases_done": phases_done, "phases_total": phases_total,
            "bar": bar, "done": done, "total": total, "pct": pct,
        })
    return rows


def compose_block(rows, members, repo_root):
    """Build the full progress-block string from row data."""
    # CURRENT = first member whose status is NOT done/completed
    current_idx = None
    for idx, row in enumerate(rows):
        if row["status"] not in ("done", "completed"):
            current_idx = idx
            break

    # Mark the CURRENT row
    if current_idx is not None:
        rows[current_idx]["is_current"] = True
        rows[current_idx]["status_word"] = "🔄 EXECUTING"

    done_count = sum(1 for r in rows if r["status"] in ("done", "completed"))
    n = len(rows)

    # header chain
    chain_parts = [f"**{r['id']}** {r['glyph']}" for r in rows]
    chain_parts.append("**Stage 6** ⬜")
    chain = " → ".join(chain_parts)

    # now-executing line
    if current_idx is not None:
        cur = rows[current_idx]
        cur_dir = os.path.basename(
            os.path.dirname(os.path.join(repo_root, members[current_idx]))
        )
        now_exec = f"{cur_dir} ({cur['done']}/{cur['total']} tasks)"
    else:
        now_exec = "none"

    lines = []
    lines.append("")  # blank after sentinel
    lines.append("### Execution order & package progress")
    lines.append("")
    lines.append(f"> {chain}")
    lines.append("")
    lines.append(f"**Plans done:** {done_count} / {n}  ·  **Now executing:** {now_exec}")
    lines.append("")
    lines.append("| # | Plan | Phases | Progress | Status |")
    lines.append("|:--:|------|:------:|----------|:------:|")

    for row in rows:
        name_display = f"**{row['id']}** {row['name']}"
        if row.get("is_current"):
            name_display += " ◄ NOW"
        phases = f"{row['phases_done']}/{row['phases_total']}"
        lines.append(
            f"| {row['num']} | {name_display} | {phases} "
            f"| `{row['bar']}` | {row['status_word']} |"
        )

    # Stage 6 footer row
    lines.append(
        "| — | **Stage 6** review · archive · runbook | — "
        "| `▱▱▱▱` | ⬜ QUEUED |"
    )
    lines.append("")  # blank before sentinel
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
