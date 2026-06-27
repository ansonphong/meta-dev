#!/usr/bin/env python3
"""Live source-of-truth scanner for the unified plan-tracking system.

Scan model (runbook-first):
  * The set of TRACKED plans is the ordered `plans/...md` list under the
    `## Sequence` section of plans/meta-runbook.md. Each is read individually —
    frontmatter parsed, checkboxes counted IN THAT FILE ONLY (phase files are
    never summed in).
  * If meta-runbook.md is absent (pre-migration), fall back to discovering
    allowlisted master/loose plan files (`*master-plan*.md`, `00-*.md`, loose
    dated `plans/<repo>/YYYY-MM-DD-*.md`) that carry a frontmatter block, so the
    scanner is still useful before the runbook exists.

Runs from the PROJECT ROOT (same CWD assumption as dashboard-data.sh — run
where plans/ lives). Emits ONE consolidated JSON object to stdout.

Deterministic, no LLM, no third-party deps (hand-rolled frontmatter parser —
never imports yaml). MUST NEVER crash on bad input: every per-file parse is
wrapped, and a malformed plan becomes a flagged entry rather than an exception.
"""
import argparse
import glob
import json
import os
import re
import sys

# Files we NEVER read/parse/emit (sensitive) or that are legacy ledgers.
SENSITIVE = "plans/exec-order-2026-06-26.md"
EXCLUDE_BY_NAME = {
    "plans/exec-order-2026-06-26.md",
    "plans/STATUS.md",
    "plans/exec-order.md",
}
# Directories pruned from the discovery walk entirely (perf + correctness).
EXCLUDE_DIRS = {"_archive", "_future", "_research", "_dashboard"}
REQUIRED_KEYS = ("status", "stage", "repo")
RUNBOOK = "plans/meta-runbook.md"

CHECKBOX = re.compile(r"^\s*[-*]\s*\[([ xX])\]")
# Markdown ## / ### headings — used for the per-section breakdown in --scope FILE
# focus mode (group 2 is the heading text, trailing #'s and whitespace stripped).
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*#*\s*$")
MILESTONE = re.compile(r"^=+\s*MILESTONE:\s*(.+?)\s*=+\s*$")
DATED = re.compile(r"^\d{4}-\d{2}-\d{2}-.*\.md$")
# Noise files that are NEVER standalone tracked plans (phase docs, designs,
# handoffs, configs). Excluded from the allowlist regardless of frontmatter.
NOISE = re.compile(
    r"^(phase-.*\.md|design\.md|handoff.*|.*-config\.md|\.loop-gap-config\.md)$",
    re.IGNORECASE,
)


def is_allowlisted(rel):
    """True if the file is a master/loose plan candidate (not a noise file)."""
    base = rel.rsplit("/", 1)[-1]
    if NOISE.match(base):
        return False
    if "master-plan" in base:
        return True
    if base.startswith("00-") and base.endswith(".md"):
        return True
    if DATED.match(base):
        return True
    return False


# ── frontmatter parser (flat subset) ───────────────────────────────────────────
def _strip_comment(val):
    """Drop a trailing ` # comment` from a value line (not inside quotes/brackets)."""
    in_s = in_d = in_b = False
    for i, ch in enumerate(val):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "[" and not in_s and not in_d:
            in_b = True
        elif ch == "]" and not in_s and not in_d:
            in_b = False
        elif ch == "#" and not in_s and not in_d and not in_b:
            if i == 0 or val[i - 1] in " \t":
                return val[:i]
    return val


def _parse_scalar(val):
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    return val


def _parse_value(val):
    """Return a parsed value: inline list -> list, else scalar string."""
    val = _strip_comment(val).strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p) for p in inner.split(",") if p.strip()]
    return _parse_scalar(val)


def parse_frontmatter(text):
    """Parse a leading --- delimited frontmatter block.

    Returns (data_dict, present_bool). present=False means no block at all
    (a plain doc); data may still be {} when the block is empty/garbled.
    """
    lines = text.split("\n")
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines) or lines[i].strip() != "---":
        return {}, False
    start = i + 1
    end = None
    for j in range(start, len(lines)):
        if lines[j].strip() == "---":
            end = j
            break
    if end is None:
        return {}, False
    data = {}
    for line in lines[start:end]:
        raw = line.rstrip("\n")
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        key = key.strip()
        if not key:
            continue
        data[key] = _parse_value(val)
    return data, True


def count_checkboxes(text):
    done = open_ = 0
    for line in text.split("\n"):
        m = CHECKBOX.match(line)
        if m:
            if m.group(1) in "xX":
                done += 1
            else:
                open_ += 1
    total = done + open_
    pct = round(100 * done / total) if total else 0
    return {"done": done, "total": total, "pct": pct}


def section_breakdown(text):
    """Per-heading checkbox tally for focus mode (--scope FILE).

    Walks the file, attributing each anchored checkbox to the most recent
    ## / ### heading. Returns only sections that actually contain checkboxes,
    in document order, each as {title, done, total, pct}.
    """
    out = []
    cur = None
    for line in text.split("\n"):
        h = HEADING.match(line)
        if h:
            cur = {"title": h.group(2).strip(), "done": 0, "total": 0}
            out.append(cur)
            continue
        m = CHECKBOX.match(line)
        if m and cur is not None:
            cur["total"] += 1
            if m.group(1) in "xX":
                cur["done"] += 1
    res = []
    for s in out:
        if s["total"]:
            s["pct"] = round(100 * s["done"] / s["total"])
            res.append(s)
    return res


def norm_path(p):
    """Normalize a user-supplied scope path: backslashes -> /, strip trailing /."""
    if not p:
        return p
    p = p.replace("\\", "/").strip()
    while len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def build_focus(scope):
    """Build the single-plan deep-dive object for --scope FILE.

    Hard-refuses the sensitive/excluded ledgers BEFORE any open() — a restricted
    path is reported as restricted and never read.
    """
    rel = norm_path(scope)
    if rel == SENSITIVE or rel in EXCLUDE_BY_NAME:
        return {"path": rel, "restricted": True}
    if not os.path.isfile(rel):
        return {"path": rel, "missing": True}
    try:
        with open(rel, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except Exception:
        return {"path": rel, "malformed": True}
    try:
        fm, _present = parse_frontmatter(text)
    except Exception:
        fm = {}
    stage_raw = fm.get("stage", "")
    try:
        stage = int(str(stage_raw).strip())
    except (ValueError, TypeError):
        stage = stage_raw or "?"
    base = rel.rsplit("/", 1)[-1]
    if "master-plan" in base and "/" in rel:
        name = rel.rsplit("/", 2)[-2]
    else:
        name = re.sub(r"\.md$", "", base)
        name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)
    return {
        "path": rel,
        "name": name,
        "status": fm.get("status", "") or "draft",
        "stage": stage,
        "repo": fm.get("repo", "") or "",
        "why": fm.get("why", "") or "",
        "progress": count_checkboxes(text),
        "sections": section_breakdown(text),
    }


def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [v] if v.strip() else []
    return [v]


# ── plan reading ────────────────────────────────────────────────────────────────
def read_plan_file(rel):
    """Read + parse one file. Returns an info dict; never raises."""
    try:
        with open(rel, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except Exception:
        return {"ok_read": False}
    try:
        fm, present = parse_frontmatter(text)
    except Exception:
        fm, present = {}, False
    return {"ok_read": True, "has_fm": present, "fm": fm,
            "progress": count_checkboxes(text)}


def build_entry(rel, info):
    """Build a plan entry dict from a read_plan_file() info blob."""
    entry = {"path": rel, "archived": "/_archive/" in rel}
    if not info.get("ok_read"):
        entry["malformed"] = True
        return entry
    fm = info.get("fm", {})
    missing = [k for k in REQUIRED_KEYS if k not in fm]

    stage_raw = fm.get("stage", "")
    try:
        stage = int(str(stage_raw).strip())
    except (ValueError, TypeError):
        stage = stage_raw

    entry.update({
        "status": fm.get("status", ""),
        "stage": stage,
        "repo": fm.get("repo", ""),
        "why": fm.get("why", "") or "",
        "depends": as_list(fm.get("depends")),
        "blocks": as_list(fm.get("blocks")),
        "progress": info.get("progress", {"done": 0, "total": 0, "pct": 0}),
    })
    # Malformed iff a frontmatter block is present but required keys are
    # missing (the file declares itself a plan but does so incompletely), OR a
    # tracked Sequence path has no frontmatter at all (no metadata to track by).
    if missing:
        entry["malformed"] = True
    return entry


# ── discovery walk ────────────────────────────────────────────────────────────
def walk_candidates(exclude_dirs=EXCLUDE_DIRS):
    """Walk plans/, return allowlisted candidate paths (excluded dirs pruned).

    The sensitive ledger and EXCLUDE_BY_NAME are pruned UNCONDITIONALLY — even
    when exclude_dirs is empty (--all), those are never surfaced.
    """
    out = []
    if not os.path.isdir("plans"):
        return out
    for path in sorted(glob.glob("plans/**/*.md", recursive=True)):
        rel = path.replace("\\", "/")
        parts = rel.split("/")
        if any(d in exclude_dirs for d in parts):
            continue
        if rel == SENSITIVE or rel in EXCLUDE_BY_NAME:
            continue
        if not is_allowlisted(rel):
            continue
        out.append(rel)
    return out


# ── runbook parse ───────────────────────────────────────────────────────────────
def parse_milestone(label_body):
    """Parse 'TYPE · label[ · vX][ · target DATE]' into a dict."""
    parts = [p.strip() for p in label_body.split("·")]
    parts = [p for p in parts if p]
    out = {"type": parts[0] if parts else "", "label": "",
           "version": None, "target": None}
    rest = parts[1:]
    label_bits = []
    for p in rest:
        low = p.lower()
        if low.startswith("v") and len(p) > 1 and p[1].isdigit():
            out["version"] = p[1:]
        elif low.startswith("target"):
            out["target"] = p[len("target"):].strip() or None
        else:
            label_bits.append(p)
    out["label"] = " · ".join(label_bits)
    return out


def parse_runbook_sequence():
    """Parse plans/meta-runbook.md ## Sequence.

    Returns (order, milestones, trailing_paths) where milestones each carry
    plan_paths (done counts filled in later once plan statuses are known).
    Absent file / no Sequence -> ([], [], []), no error.
    """
    order = []
    milestones = []
    trailing_paths = []
    if not os.path.isfile(RUNBOOK):
        return order, milestones, trailing_paths
    try:
        with open(RUNBOOK, encoding="utf-8", errors="ignore") as fh:
            lines = fh.read().split("\n")
    except Exception:
        return order, milestones, trailing_paths

    seq_start = None
    for i, line in enumerate(lines):
        if re.match(r"^#{1,6}\s+Sequence\b", line.strip(), re.IGNORECASE):
            seq_start = i + 1
            break
    if seq_start is None:
        return order, milestones, trailing_paths

    seq_end = len(lines)
    for i in range(seq_start, len(lines)):
        if re.match(r"^#{1,6}\s+\S", lines[i]):
            seq_end = i
            break

    current_bucket = []
    for raw in lines[seq_start:seq_end]:
        line = raw.strip()
        if not line:
            continue
        mm = MILESTONE.match(line)
        if mm:
            md = parse_milestone(mm.group(1))
            md["raw"] = line
            md["plan_paths"] = list(current_bucket)
            milestones.append(md)
            current_bucket = []
            continue
        body = re.sub(r"^(?:[-*]\s+|\d+\.\s+)", "", line)
        if body.startswith("plans/"):
            m = re.match(r"(plans/\S*?\.md)", body)
            if m:
                p = m.group(1)
                order.append(p)
                current_bucket.append(p)

    trailing_paths = list(current_bucket)
    return order, milestones, trailing_paths


# ── main ────────────────────────────────────────────────────────────────────────
def parse_args(argv):
    ap = argparse.ArgumentParser(
        prog="plan-index.py",
        description="Scan plans/ -> consolidated JSON for the dashboard.",
    )
    ap.add_argument("--scope", default=None,
                    help="restrict to a plans/ directory, OR focus a single .md plan file")
    ap.add_argument("--repo", default=None, help="only plans whose repo: matches")
    ap.add_argument("--status", default=None, help="only plans whose status: matches")
    ap.add_argument("--all", action="store_true",
                    help="include _archive/_future/_research (never the sensitive ledger)")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    exclude_dirs = set() if args.all else EXCLUDE_DIRS
    scope = norm_path(args.scope) if args.scope else None

    # --scope resolution. A FILE (or a restricted ledger path, even if absent)
    # becomes single-plan focus mode; a DIR narrows the plans panel.
    focus = None
    scope_kind = None
    if scope and (scope == SENSITIVE or scope in EXCLUDE_BY_NAME):
        focus = build_focus(scope)          # refused before any open()
        scope_kind = "file"
    elif scope and os.path.isfile(scope):
        focus = build_focus(scope)
        scope_kind = "file"
    elif scope and os.path.isdir(scope):
        scope_kind = "dir"
    elif scope:
        scope_kind = "missing"

    runbook_present = os.path.isfile(RUNBOOK)
    order, milestones, trailing_paths = parse_runbook_sequence()

    # Discover allowlisted candidates that carry a frontmatter block (or are
    # unreadable). These drive the fallback tracked set + the untracked list.
    discovered = []  # (rel, info)
    for rel in walk_candidates(exclude_dirs):
        info = read_plan_file(rel)
        if not info.get("ok_read"):
            discovered.append((rel, info))
            continue
        if not info.get("has_fm"):
            continue  # no frontmatter block -> a doc, not a plan
        discovered.append((rel, info))
    discovered_map = dict(discovered)

    plans = []
    status_by_path = {}

    if runbook_present and order:
        # Runbook is the source of truth: tracked = Sequence paths, read each.
        for rel in order:
            info = discovered_map.get(rel) or read_plan_file(rel)
            entry = build_entry(rel, info)
            plans.append(entry)
            status_by_path[rel] = entry
    else:
        # Pre-migration fallback: tracked = discovered allowlisted plan files.
        for rel, info in discovered:
            entry = build_entry(rel, info)
            plans.append(entry)
            status_by_path[rel] = entry

    # untracked = allowlisted plan files with frontmatter NOT in the Sequence.
    order_set = set(order)
    untracked = [rel for rel, _ in discovered if rel not in order_set]

    # ── scope DIR: narrow to plans under the dir, appending discovered-but-
    # untracked plans living there so the area view is complete.
    if scope_kind == "dir":
        prefix = scope + "/"

        def under(p):
            return p == scope or p.startswith(prefix)

        have = set()
        kept = []
        for p in plans:
            if under(p["path"]):
                kept.append(p)
                have.add(p["path"])
        for rel in untracked:
            if under(rel) and rel not in have:
                kept.append(build_entry(rel, discovered_map[rel]))
                have.add(rel)
        plans = kept
        untracked = [u for u in untracked if under(u)]
    elif scope_kind in ("file", "missing"):
        # Focus / non-existent scope: the plans panel is not the subject.
        plans = []
        untracked = []

    # ── repo / status filters (on whatever plan set remains).
    if args.repo:
        plans = [p for p in plans if p.get("repo") == args.repo]
    if args.status:
        plans = [p for p in plans if p.get("status") == args.status]

    # Fill milestone + trailing done counts (done = status == "done"). Computed
    # from the GLOBAL status map so milestone progress is scope-independent.
    def done_for(p):
        e = status_by_path.get(p)
        return bool(e) and e.get("status") == "done"

    for m in milestones:
        paths = m.get("plan_paths", [])
        m["plans_total"] = len(paths)
        m["plans_done"] = sum(1 for p in paths if done_for(p))

    trailing = {
        "plans_total": len(trailing_paths),
        "plans_done": sum(1 for p in trailing_paths if done_for(p)),
        "plan_paths": trailing_paths,
    }

    counts = {
        "tracked": len(plans),
        "malformed": sum(1 for p in plans if p.get("malformed")),
        "archived": sum(1 for p in plans if p.get("archived")),
    }

    out = {
        "plans": plans,
        "order": order,
        "milestones": milestones,
        "trailing": trailing,
        "untracked": untracked,
        "counts": counts,
        "focus": focus,
        "scope": scope,
        "scope_kind": scope_kind,
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
