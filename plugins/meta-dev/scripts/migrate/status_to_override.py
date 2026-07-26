#!/usr/bin/env python3
"""status_to_override.py — M1 frontmatter normalization one-shot.

Walks host active plans (same allowlist as plan-index.py walk_candidates) PLUS
type:runbook files (_runbook-*.md). Parses frontmatter, applies the
status→override mapping table, and either prints a full mapping report
(--report / --dry-run, the DEFAULT) or rewrites files via planctl.mutate
(--apply — gated behind explicit human approval).

Stdlib only. Imports planctl.parse + planctl.mutate from the sibling package.

Mapping table (from phase-1-normalize-truth.md):
  in_progress / active / pending / draft / planning / done / completed → DELETE
  blocked    → override: blocked  + note: <reason or "migrated from status: blocked">
  parked     → override: parked   + note: …
  superseded / "superseded by X" → override: superseded + note: X
  freeform   → note: <string> if it carries a WHY, else DELETE (flagged for review)
  updated:   → ALWAYS DELETE

Inline-comment preservation (P1-D): a trailing # comment on the status: line
is moved into note: (both for the delete and override branches).
"""
import argparse
import json
import os
import re
import sys
import textwrap

# ── path setup: import planctl from the sibling package ───────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_SCRIPTS = os.path.dirname(_SCRIPT_DIR)  # plugins/meta-dev/scripts/
if _PLUGIN_SCRIPTS not in sys.path:
    sys.path.insert(0, _PLUGIN_SCRIPTS)

# ── plan-index.py constants (replicated so this script is self-contained) ─────
EXCLUDE_DIRS = {"_archive", "_future", "_research", "_dashboard"}
SENSITIVE = "plans/exec-order-2026-06-26.md"
EXCLUDE_BY_NAME = {
    "plans/exec-order-2026-06-26.md",
    "plans/STATUS.md",
    "plans/exec-order.md",
}
NOISE_RE = re.compile(
    r"^(phase-.*\.md|design\.md|handoff.*|.*-config\.md|\.loop-gap-config\.md"
    r"|_exec-order-.*\.md)$",
    re.IGNORECASE,
)
DATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-.*\.md$")


def is_allowlisted(rel):
    """True if the file is a master/loose plan candidate (not a noise file)."""
    base = rel.rsplit("/", 1)[-1]
    if NOISE_RE.match(base):
        return False
    if "master-plan" in base:
        return True
    if base.startswith("00-") and base.endswith(".md"):
        return True
    if DATED_RE.match(base):
        return True
    return False


def is_runbook_file(rel):
    """True if this is a runbook file (P1-C scope inclusion)."""
    base = rel.rsplit("/", 1)[-1]
    return base.startswith("_runbook-") and base.endswith(".md")


# ── semantic mapping ──────────────────────────────────────────────────────────
# Values that map to DELETE (derivation handles them).
DELETE_VALUES = {
    "in_progress", "active", "pending", "draft", "planning",
    "done", "completed",
}

# Values that map to override: <value>.
OVERRIDE_MAP = {
    "blocked": "blocked",
    "parked": "parked",
}


def _anchor_pos(lines, anchor_keys):
    """Insertion index AFTER the last ``anchor_keys`` entry — block-scalar safe.

    A YAML block scalar (``why: >`` / ``why: |``) owns every indented line that
    follows it. Anchoring at ``j+1`` therefore inserts INSIDE the block, which
    silently breaks the scalar and everything under it:

        why: >
        note: …          <- injected here, orphaning the continuation below
          Mobius Warp "Twist" is …

    So when the anchor line opens a block scalar, skip past its continuation
    lines first. (Cost one real corrupted plan before this existed.)"""
    pos = len(lines)
    for j, ln in enumerate(lines):
        s = ln.strip()
        if ":" not in s or s.startswith("#"):
            continue
        key, _, val = s.partition(":")
        if key.strip() not in anchor_keys:
            continue
        end = j + 1
        if val.strip() in (">", "|", ">-", "|-", ">+", "|+"):
            while end < len(lines) and (
                    not lines[end].strip() or lines[end][:1] in (" ", "\t")):
                end += 1
        pos = end
    return pos


def classify_status(raw):
    """Classify a raw status value → (action, target_override, target_note).

    Returns one of:
      ("delete", None, note_or_none)     — delete status line
      ("override", ov_value, note)       — write override: ov_value + note
      ("freeform", None, note_or_none)   — freeform, needs human review
      ("superseded", None, note)         — superseded/by X → override: superseded
    """
    if raw is None or raw == "":
        return ("delete", None, None)

    v = raw.strip()

    # superseded variants
    if v == "superseded":
        return ("superseded", "superseded", None)
    if v.lower().startswith("superseded"):
        # "superseded by X" → note gets the "by X" part
        rest = v[len("superseded"):].strip()
        if rest.startswith("by "):
            rest = rest[3:].strip()
        note = ("superseded by %s" % rest) if rest else "superseded"
        return ("superseded", "superseded", note)

    # known delete values
    if v.lower() in DELETE_VALUES:
        return ("delete", None, None)

    # known override values
    if v.lower() in OVERRIDE_MAP:
        return ("override", OVERRIDE_MAP[v.lower()], None)

    # everything else is freeform
    return ("freeform", None, None)


# ── frontmatter line-level helpers ────────────────────────────────────────────
def _raw_frontmatter_lines(text):
    """Return (start_line_idx, end_line_idx, lines) of the first ---…--- block.

    Returns (None, None, []) if no valid block found.
    """
    lines = text.split("\n")
    # skip leading blank lines
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines) or lines[i].strip() != "---":
        return None, None, []
    start = i + 1
    end = None
    for j in range(start, len(lines)):
        if lines[j].strip() == "---":
            end = j
            break
    if end is None:
        return None, None, []
    return start, end, lines


def _extract_raw_fm_line(lines, start, end, key):
    """Find the raw line for `key:` in the frontmatter block (first match only).

    Returns (line_idx, raw_line) or (None, None). `line_idx` is relative to the
    full file (0-indexed). `raw_line` includes trailing newline if present.
    """
    for i in range(start, end):
        raw = lines[i]
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        k, _, _ = stripped.partition(":")
        if k.strip() == key:
            return i, raw
    return None, None


def _extract_inline_comment(raw_line):
    """Extract a trailing `# comment` from a frontmatter value line.

    Returns (value_without_comment, comment_text_or_None).
    Handles the same quoting/bracket rules as plan-index.py's _strip_comment.
    """
    # Find the position after the first ':'
    colon_pos = raw_line.find(":")
    if colon_pos < 0:
        return raw_line.strip(), None
    val = raw_line[colon_pos + 1:]
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
                comment = val[i + 1:].strip()
                value = val[:i].strip()
                return value, comment if comment else None
    return val.strip(), None


def _status_value_and_comment(raw_line):
    """Parse a `status:` line → (value, inline_comment_or_none)."""
    colon_pos = raw_line.find(":")
    if colon_pos < 0:
        return "", None
    val_part = raw_line[colon_pos + 1:]
    return _extract_inline_comment(raw_line)


# ── main logic ────────────────────────────────────────────────────────────────
def discover_files(project_root):
    """Walk plans/ under project_root, return sorted list of rel paths.

    Scope: plan-index.py walk_candidates allowlist + _runbook-*.md files.
    Excludes _archive/, _dashboard/, _future/, _research/ entirely.
    """
    plans_dir = os.path.join(project_root, "plans")
    if not os.path.isdir(plans_dir):
        return []

    out = []
    for dirpath, dirnames, filenames in os.walk(plans_dir):
        # Prune excluded dirs in-place
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        rel_dir = os.path.relpath(dirpath, project_root).replace("\\", "/")
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            rel = (rel_dir + "/" + fname).replace("\\", "/")
            if rel.startswith("./"):
                rel = rel[2:]

            # Exclude by name
            if rel == SENSITIVE or rel in EXCLUDE_BY_NAME:
                continue

            # Include plans (allowlisted) OR runbook files (P1-C)
            if is_allowlisted(rel) or is_runbook_file(rel):
                out.append(rel)

    return sorted(out)


def analyze_file(abs_path):
    """Read + parse one file. Returns a dict with findings or None if skip.

    The returned dict has keys:
      path, has_fm, raw_status, status_comment, has_updated,
      action, target_override, target_note, uncertain, fm_data
    """
    try:
        with open(abs_path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
    except Exception:
        return None

    start, end, lines = _raw_frontmatter_lines(text)
    if start is None:
        return {"path": abs_path, "has_fm": False, "skip": True}

    # Extract raw status / updated lines
    status_idx, status_line = _extract_raw_fm_line(lines, start, end, "status")
    updated_idx, updated_line = _extract_raw_fm_line(lines, start, end, "updated")

    if status_idx is None and updated_idx is None:
        # Nothing to do — no status: or updated:
        return {"path": abs_path, "has_fm": True, "skip": True,
                "has_status": False, "has_updated": False}

    # Parse frontmatter via planctl for structured data
    try:
        from planctl import parse as planctl_parse
        fm_data, raw_status = planctl_parse.parse_frontmatter(text)
    except Exception:
        fm_data, raw_status = {}, None

    # Parse the raw status line for inline comments
    raw_val = ""
    status_comment = None
    if status_line is not None:
        raw_val, status_comment = _status_value_and_comment(status_line)

    # Use planctl's raw_status if we didn't get a value from the raw line
    if not raw_val and raw_status:
        raw_val = raw_status

    # Classify
    action, target_override, target_note = classify_status(raw_val)

    # Incorporate inline comment into note
    if status_comment:
        if target_note:
            target_note = target_note + "; " + status_comment
        else:
            target_note = status_comment

    # For delete values with an inline comment but no note yet: preserve the why
    if action == "delete" and status_comment and not target_note:
        target_note = status_comment

    # For blocked/parked with no note: supply a default
    if action in ("override", "superseded") and not target_note:
        target_note = "migrated from status: %s" % (raw_val or "unknown")

    # Uncertainty flag
    uncertain = (action == "freeform")

    # Check if there's already an override or note in the file
    existing_override = fm_data.get("override") if isinstance(fm_data, dict) else None
    existing_note = fm_data.get("note") if isinstance(fm_data, dict) else None

    return {
        "path": abs_path,
        "has_fm": True,
        "skip": False,
        "has_status": status_idx is not None,
        "has_updated": updated_idx is not None,
        "raw_status": raw_val,
        "status_comment": status_comment,
        "action": action,
        "target_override": target_override,
        "target_note": target_note,
        "uncertain": uncertain,
        "existing_override": existing_override,
        "existing_note": existing_note,
        "fm_data": fm_data,
        "status_line_idx": status_idx,
        "updated_line_idx": updated_idx,
    }


def compute_frontmatter_diff(text, analysis):
    """Compute old→new frontmatter diff for one file. Returns (old_block, new_block)."""
    start, end, lines = _raw_frontmatter_lines(text)
    if start is None:
        return "", ""

    old_block = "\n".join(lines[start:end])

    # Build new frontmatter: keep all non-status, non-updated lines
    new_lines = []
    for i in range(start, end):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(raw)
            continue
        if ":" not in stripped:
            new_lines.append(raw)
            continue
        k = stripped.split(":", 1)[0].strip()
        if k == "status":
            continue  # delete
        if k == "updated":
            continue  # delete
        new_lines.append(raw)

    # Append override: and note: if needed
    a = analysis
    if a.get("target_override"):
        ov_line = "override: " + a["target_override"]
        # If there was an existing override, we already kept it; but we replace
        # by deleting status + writing the correct value.
        # Check if override already exists in new_lines
        has_ov = any(
            ln.strip().split(":", 1)[0].strip() == "override"
            for ln in new_lines if ":" in ln.strip() and not ln.strip().startswith("#")
        )
        if not has_ov:
            new_lines.insert(_anchor_pos(new_lines, ("repo", "stage", "why")), ov_line)

    if a.get("target_note"):
        note_line = "note: " + a["target_note"]
        has_note = any(
            ln.strip().split(":", 1)[0].strip() == "note"
            for ln in new_lines if ":" in ln.strip() and not ln.strip().startswith("#")
        )
        if not has_note:
            new_lines.insert(
                _anchor_pos(new_lines, ("override", "repo", "stage", "why")), note_line)

    new_block = "\n".join(new_lines)
    return old_block, new_block


def run_report(project_root):
    """Walk files, analyze, print summary + per-file diff."""
    files = discover_files(project_root)

    # Accumulators
    results = []          # all non-skip analyses
    value_counts = {}     # raw_status → count
    action_counts = {}    # action → count
    updated_count = 0
    uncertain_cases = []
    skipped_no_fm = 0
    skipped_nothing = 0

    for rel in files:
        abs_path = os.path.join(project_root, rel)
        a = analyze_file(abs_path)
        if a is None:
            continue
        if a.get("skip"):
            if not a.get("has_fm"):
                skipped_no_fm += 1
            else:
                skipped_nothing += 1
            continue

        results.append((rel, a))

        # Count raw status values (only for files that actually have a status: line)
        if a["has_status"]:
            raw = a.get("raw_status", "") or "(empty)"
            value_counts[raw] = value_counts.get(raw, 0) + 1

        # Count action
        act = a["action"]
        action_counts[act] = action_counts.get(act, 0) + 1

        if a["has_updated"]:
            updated_count += 1

        if a["uncertain"]:
            uncertain_cases.append((rel, raw, a.get("target_note")))

    # ── Print report ──────────────────────────────────────────────────────────
    print("=" * 72)
    print("  M1 FRONTMATTER NORMALIZATION — DRY-RUN REPORT")
    print("  status_to_override.py  (NOT applying — inspect then run --apply)")
    print("=" * 72)
    print()
    print("  Project root :", project_root)
    print("  Files walked :", len(files))
    print("  Skipped (no frontmatter):", skipped_no_fm)
    print("  Skipped (no status:/updated:):", skipped_nothing)
    print("  Files that would change:", len(results))
    print("  Files with updated: deleted:", updated_count)
    print()

    # ── Summary table: every distinct status: value → action ──────────────────
    print("─" * 72)
    print("  STATUS VALUE → ACTION MAP (with counts)")
    print("─" * 72)
    print(f"  {'VALUE':<32s} {'COUNT':>6s}  ACTION")
    print(f"  {'─'*32}  {'─'*6}  {'─'*48}")

    # Group by action type for cleaner display
    for raw_val in sorted(value_counts.keys(), key=lambda v: (
            # Sort: known values first, then freeform
            0 if v.lower() in DELETE_VALUES else
            1 if v.lower() in OVERRIDE_MAP else
            2 if v.lower() == "superseded" or v.lower().startswith("superseded") else
            3,
            v.lower()
    )):
        count = value_counts[raw_val]
        lower = raw_val.lower().strip()

        if lower in DELETE_VALUES:
            action_desc = "DELETE (derivation handles it)"
        elif lower in OVERRIDE_MAP:
            action_desc = "→ override: %s + note" % OVERRIDE_MAP[lower]
        elif lower == "superseded" or lower.startswith("superseded"):
            action_desc = "→ override: superseded + note"
        elif raw_val == "(empty)":
            action_desc = "DELETE (empty value)"
        else:
            # Freeform — check what the actual action was for these files
            # (some become note:, some are deleted if they don't carry a WHY)
            freeform_results = [r for _, r in results
                               if r.get("raw_status", "").strip() == raw_val]
            if freeform_results and freeform_results[0].get("target_note"):
                action_desc = "→ note: <value>  ⚠ FREEFORM — HUMAN REVIEW"
            else:
                action_desc = "DELETE (no WHY detected)  ⚠ FREEFORM — HUMAN REVIEW"

        display = raw_val if len(raw_val) <= 30 else raw_val[:27] + "..."
        print(f"  {display:<32s} {count:>6d}  {action_desc}")

    print(f"  {'─'*32}  {'─'*6}")
    print(f"  {'TOTAL':32s} {sum(value_counts.values()):>6d}")
    print()

    # ── Freeform / ambiguous cases (the ones a human must decide) ─────────────
    if uncertain_cases:
        print("─" * 72)
        print("  ⚠  FREEFORM / AMBIGUOUS STATUS VALUES — NEED HUMAN DECISION")
        print("─" * 72)
        print()
        print("  These files carry a status: value that does not match any known")
        print("  vocabulary word. The current action for each is noted below —")
        print("  A human approver should review and confirm (or override) before --apply.")
        print()
        for rel, raw, note in uncertain_cases:
            short = rel.replace("plans/", "", 1) if rel.startswith("plans/") else rel
            print(f"  {short}")
            print(f"    status: {raw}")
            print(f"    → note: {note or '(empty — would be deleted)'}")
            print()

    # ── Per-file diff preview ─────────────────────────────────────────────────
    print("─" * 72)
    print("  PER-FILE DIFF PREVIEW")
    print("─" * 72)
    print()

    for rel, a in results:
        short = rel.replace("plans/", "", 1) if rel.startswith("plans/") else rel
        abs_path = os.path.join(project_root, rel)
        try:
            with open(abs_path, "r", encoding="utf-8", newline="") as f:
                text = f.read()
        except Exception:
            print(f"  {short}  [ERROR: cannot read]")
            print()
            continue

        old_block, new_block = compute_frontmatter_diff(text, a)

        changes = []
        if a["has_status"]:
            changes.append("delete status: %s" % (a.get("raw_status") or "(empty)"))
        if a["has_updated"]:
            changes.append("delete updated:")
        if a.get("target_override"):
            changes.append("add override: %s" % a["target_override"])
        if a.get("target_note"):
            note_preview = a["target_note"][:60] + "..." if len(a.get("target_note", "")) > 60 else a.get("target_note", "")
            changes.append("add note: %s" % note_preview)

        flag = " ⚠ FREEFORM" if a["uncertain"] else ""

        print(f"  {short}{flag}")
        print(f"    changes: {'; '.join(changes)}")
        if old_block != new_block:
            # Show a compact diff of just the changed/added lines
            old_set = set(old_block.split("\n"))
            new_set = set(new_block.split("\n"))
            removed = old_set - new_set
            added = new_set - old_set
            for r in sorted(removed):
                if r.strip():
                    print(f"    - {r.strip()}")
            for ad in sorted(added):
                if ad.strip():
                    print(f"    + {ad.strip()}")
        print()

    # ── Footer ────────────────────────────────────────────────────────────────
    print("=" * 72)
    print("  REPORT COMPLETE")
    print(f"  {len(results)} files would be modified")
    if uncertain_cases:
        print(f"  {len(uncertain_cases)} files have FREEFORM status values — REVIEW REQUIRED")
    print("  No files have been modified (--dry-run / --report mode)")
    print("  Run with --apply to execute the migration after human review.")
    print("=" * 72)


def run_apply(project_root):
    """Rewrite files via planctl.mutate.atomic_write_md. NOT yet authorized."""
    from planctl import mutate as planctl_mutate

    files = discover_files(project_root)
    report = {
        "project_root": project_root,
        "files_scanned": len(files),
        "files_modified": 0,
        "files_skipped": 0,
        "actions": {},
        "uncertain_applied": [],
        "errors": [],
    }

    for rel in files:
        abs_path = os.path.join(project_root, rel)
        a = analyze_file(abs_path)
        if a is None:
            report["errors"].append({"path": rel, "error": "analysis_failed"})
            continue
        if a.get("skip"):
            report["files_skipped"] += 1
            continue

        try:
            with open(abs_path, "r", encoding="utf-8", newline="") as f:
                text = f.read()
        except Exception as e:
            report["errors"].append({"path": rel, "error": str(e)})
            continue

        _, new_block = compute_frontmatter_diff(text, a)
        start, end, lines = _raw_frontmatter_lines(text)
        if start is None:
            report["errors"].append({"path": rel, "error": "fm_block_lost"})
            continue

        old_block = "\n".join(lines[start:end])
        if old_block == new_block:
            report["files_skipped"] += 1
            continue

        def mutator(lns):
            # Replace the frontmatter block
            new_lines_list = new_block.split("\n")
            # Ensure the closing --- stays
            result = lns[:start] + new_lines_list + lns[end:]
            return result, True

        try:
            planctl_mutate.atomic_write_md(abs_path, mutator)
            report["files_modified"] += 1
            act = a["action"]
            report["actions"][act] = report["actions"].get(act, 0) + 1
            if a["uncertain"]:
                report["uncertain_applied"].append({
                    "path": rel,
                    "raw_status": a["raw_status"],
                    "target_note": a.get("target_note"),
                })
        except Exception as e:
            report["errors"].append({"path": rel, "error": str(e)})

    # Write report
    report_path = os.path.join(project_root, "migrate_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("Migrate report written to", report_path)
    print(json.dumps(report, indent=2))


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args(argv):
    ap = argparse.ArgumentParser(
        prog="status_to_override.py",
        description="M1 frontmatter normalize: delete status:/updated:, map "
                    "semantic→override (one-shot migration).",
    )
    ap.add_argument("--report", action="store_true", dest="report",
                    default=False, help="print mapping report (DEFAULT when no flags)")
    ap.add_argument("--dry-run", action="store_true", dest="dry_run",
                    default=False, help="alias for --report")
    ap.add_argument("--apply", action="store_true", dest="apply",
                    default=False, help="EXECUTE the migration (gated — human "
                    "must approve the report first)")
    ap.add_argument("--project-root", default=None,
                    help="host project root (default: resolve via planctl.statedir)")
    ap.add_argument("--json", action="store_true", default=False,
                    help="output report as JSON")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)

    # Resolve project root
    if args.project_root:
        root = os.path.abspath(args.project_root)
    else:
        try:
            # Try planctl first
            from planctl import statedir
            root = statedir.project_root()
        except Exception:
            # Fallback: CLAUDE_PROJECT_DIR
            root = os.environ.get("CLAUDE_PROJECT_DIR")
            if not root:
                print("ERROR: cannot resolve project root.", file=sys.stderr)
                print("  Set --project-root, CLAUDE_PROJECT_DIR, or run from",
                      "within the host project.", file=sys.stderr)
                return 1

    if not os.path.isdir(os.path.join(root, "plans")):
        print("ERROR: plans/ directory not found under", root, file=sys.stderr)
        return 1

    # Determine mode: --apply is explicit; otherwise report
    if args.apply:
        run_apply(root)
    else:
        # Default: --report
        run_report(root)

    return 0


if __name__ == "__main__":
    sys.exit(main())
