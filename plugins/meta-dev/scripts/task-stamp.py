#!/usr/bin/env python3
"""task-stamp.py — Assign stable `` `T<phase>.<seq>` `` handles to plan checkboxes.

Walk a master plan (or all ``00-master-plan.md`` files with ``--all``) and stamp
every unstamped checkbox line with a handle derived from the nearest phase
heading. Idempotent; never renumbers existing handles.

Usage:
  task-stamp.py [--check] <master-plan.md>
  task-stamp.py --all [--check]          # retrofit every 00-master-plan.md under plans/
  task-stamp.py --audit                  # classify MASTER vs PHASE ledger (read-only)

Handle placement: after the mark, before the rest of the line text:
  - [ ] `T4b.2` Add Tile: …

Phase heading styles (all three must parse; phase id is a token, not an int):
  ### Phase 1 — Title
  **Phase 0 — Generic Path…**
  ### Phase 4a / ### Phase 4b
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Checkbox: capture indent, bullet, mark, rest-of-line.
CHECKBOX_RE = re.compile(r"^(\s*)([-*])\s+\[([ xX])\]\s*(.*)$")
# Already-stamped handle at start of rest text.
HANDLE_RE = re.compile(r"^`T([A-Za-z0-9]+)\.(\d+)`\s*")
# Phase heading styles → phase token.
# 1) ### Phase N…  or  ## Phase N…  (ATX)
PHASE_ATX_RE = re.compile(
    r"^#{1,6}\s+Phase\s+([A-Za-z0-9]+)\b", re.IGNORECASE
)
# 2) **Phase N — …** (bold prose, not a heading)
PHASE_BOLD_RE = re.compile(
    r"^\*\*Phase\s+([A-Za-z0-9]+)\b", re.IGNORECASE
)
# 3) bare "Phase N" as first non-empty on a line (fallback for loose masters)
PHASE_LOOSE_RE = re.compile(
    r"^Phase\s+([A-Za-z0-9]+)\b", re.IGNORECASE
)
# Prose task numbering warning (Task 4.2 style)
PROSE_TASK_RE = re.compile(r"\bTask\s+(\d+[a-zA-Z]?)\.(\d+)\b")

DEFAULT_PHASE = "0"


def parse_phase_token(line: str) -> Optional[str]:
    s = line.strip()
    for rx in (PHASE_ATX_RE, PHASE_BOLD_RE, PHASE_LOOSE_RE):
        m = rx.match(s)
        if m:
            return m.group(1)
    return None


def collect_used_seqs(lines: List[str]) -> Dict[str, set]:
    """Map phase token → set of already-used seq ints from existing handles."""
    used: Dict[str, set] = {}
    for line in lines:
        m = CHECKBOX_RE.match(line)
        if not m:
            continue
        rest = m.group(4)
        hm = HANDLE_RE.match(rest)
        if not hm:
            continue
        phase, seq_s = hm.group(1), hm.group(2)
        used.setdefault(phase, set()).add(int(seq_s))
    return used


def next_seq(used: Dict[str, set], phase: str) -> int:
    s = used.setdefault(phase, set())
    n = 1
    while n in s:
        n += 1
    s.add(n)
    return n


def stamp_text(text: str, *, check: bool = False) -> Tuple[str, List[str], List[str]]:
    """Return (new_text, planned_stamp_msgs, warnings)."""
    # Preserve newline style: detect if original ended with newline.
    ends_nl = text.endswith("\n")
    # splitlines keeps no trailing empties distinction; use split("\n")
    lines = text.split("\n")
    # If text ended with \n, last element is ""; keep it for rejoin fidelity.
    used = collect_used_seqs(lines)
    current_phase = DEFAULT_PHASE
    planned: List[str] = []
    warnings: List[str] = []
    out: List[str] = []

    for i, line in enumerate(lines):
        pt = parse_phase_token(line)
        if pt is not None:
            current_phase = pt

        m = CHECKBOX_RE.match(line)
        if not m:
            # Warn if prose mentions Task N.M near checkboxes (informational).
            if PROSE_TASK_RE.search(line) and not line.lstrip().startswith("#"):
                # Only warn once-ish style — still report each line for visibility.
                warnings.append(
                    f"line {i + 1}: prose task numbering found "
                    f"(handles are checkbox seqs, not Task N.M): {line.strip()[:80]}"
                )
            out.append(line)
            continue

        indent, bullet, mark, rest = m.group(1), m.group(2), m.group(3), m.group(4)
        if HANDLE_RE.match(rest):
            out.append(line)  # already stamped — skip
            continue

        seq = next_seq(used, current_phase)
        handle = f"`T{current_phase}.{seq}`"
        new_rest = f"{handle} {rest}" if rest else handle
        new_line = f"{indent}{bullet} [{mark}] {new_rest}"
        planned.append(f"line {i + 1}: [{mark}] → {handle}  {rest[:60]}")
        out.append(new_line if not check else line)  # --check: don't rewrite

    new_text = "\n".join(out)
    if ends_nl and not new_text.endswith("\n"):
        new_text += "\n"
    # When check mode, return original for byte identity of file
    if check:
        return text, planned, warnings
    return new_text, planned, warnings


def atomic_write(path: Path, content: str) -> None:
    path = path.resolve()
    d = path.parent
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(d))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def find_masters(plans_root: Path) -> List[Path]:
    out: List[Path] = []
    if not plans_root.is_dir():
        return out
    for root, dirs, files in os.walk(plans_root):
        # skip archive / dashboard internals
        dirs[:] = [
            d
            for d in dirs
            if d not in ("_dashboard", "inbox", "__pycache__", "_archive")
            and not d.startswith(".")
        ]
        if "00-master-plan.md" in files:
            out.append(Path(root) / "00-master-plan.md")
    return sorted(out)


# ── --audit (T4.1) ──────────────────────────────────────────────────────────

CANONICAL_PHASE_RE = re.compile(
    r"(checkbox truth lives in the phase|authoritative detail lives in the phase|"
    r"phase file is canonical|no duplicate checkboxes)",
    re.IGNORECASE,
)
BOX_RE = re.compile(r"^\s*[-*]\s*\[([ xX])\]")


def count_boxes(path: Path) -> Tuple[int, int]:
    """Return (open, total) checkbox counts."""
    open_n = total = 0
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0, 0
    for line in text.splitlines():
        m = BOX_RE.match(line)
        if not m:
            continue
        total += 1
        if m.group(1) == " ":
            open_n += 1
    return open_n, total


def frontmatter_status(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else ""
    for line in block.splitlines():
        if line.strip().lower().startswith("status:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return ""


def audit_plans(plans_root: Path) -> int:
    """Classify each initiative with a 00-master-plan.md. Read-only. Always exit 0."""
    masters = find_masters(plans_root)
    print(f"=== task-ledger audit ({len(masters)} masters under {plans_root}) ===")
    print(
        f"{'CLASS':<18} {'M-open':>6} {'M-tot':>5} {'P-open':>6} {'P-tot':>5}  path"
    )
    excluded: List[str] = []
    orphans: List[str] = []
    for master in masters:
        plan_dir = master.parent
        m_open, m_tot = count_boxes(master)
        p_open = p_tot = 0
        phase_files: List[Path] = []
        for p in sorted(plan_dir.glob("*.md")):
            if p.name == "00-master-plan.md":
                continue
            o, t = count_boxes(p)
            p_open += o
            p_tot += t
            if t:
                phase_files.append(p)

        master_text = master.read_text(encoding="utf-8", errors="ignore")
        status = frontmatter_status(master)
        phase_canonical = bool(CANONICAL_PHASE_RE.search(master_text))
        doneish = status.lower() in ("done",) or "_archive" in str(plan_dir)

        if (m_open == 0 and p_open > 0) or phase_canonical:
            klass = "PHASE-as-ledger"
        elif m_tot >= p_tot and m_tot > 0:
            klass = "MASTER-as-ledger"
        elif m_tot == 0 and p_tot == 0:
            klass = "EMPTY"
        elif m_tot > 0:
            klass = "MASTER-as-ledger"
        else:
            klass = "PHASE-as-ledger"

        if doneish:
            klass = f"DONE/{klass}"
            excluded.append(str(master))
        elif klass.startswith("PHASE"):
            excluded.append(str(master))

        rel = str(master)
        print(
            f"{klass:<18} {m_open:6d} {m_tot:5d} {p_open:6d} {p_tot:5d}  {rel}"
        )

        # Orphans: phase boxes with no 1:1 master counterpart (MASTER only)
        if klass.startswith("MASTER") and p_tot > 0:
            # Heuristic: report phase file open boxes as orphan candidates when
            # phase has boxes the master does not mirror by count.
            if p_tot > m_tot:
                for pf in phase_files:
                    for i, line in enumerate(
                        pf.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
                    ):
                        if BOX_RE.match(line):
                            orphans.append(f"{pf}:{i}: {line.strip()[:100]}")

    print()
    print("=== EXCLUDED from auto-demotion (PHASE-as-ledger / done) ===")
    if excluded:
        for e in excluded:
            print(f"  EXCLUDED  {e}")
    else:
        print("  (none)")
    print()
    print("=== Orphan phase boxes (MASTER-as-ledger only; no 1:1 master counterpart by count) ===")
    if orphans:
        for o in orphans[:200]:
            print(f"  ORPHAN  {o}")
        if len(orphans) > 200:
            print(f"  … {len(orphans) - 200} more")
    else:
        print("  (none)")
    return 0


def process_one(path: Path, *, check: bool) -> int:
    if not path.is_file():
        print(f"task-stamp.py: not a file: {path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    new_text, planned, warnings = stamp_text(text, check=check)
    for w in warnings:
        print(f"WARN: {path}: {w}", file=sys.stderr)
    if check:
        if planned:
            print(f"--check {path}: {len(planned)} stamp(s) planned (no write)")
            for p in planned:
                print(f"  {p}")
        else:
            print(f"--check {path}: nothing to stamp (already complete or no boxes)")
        return 0
    if new_text == text:
        print(f"{path}: no changes (idempotent)")
        return 0
    atomic_write(path, new_text)
    print(f"{path}: stamped {len(planned)} checkbox(es)")
    for p in planned:
        print(f"  {p}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", nargs="?", help="Path to a master plan markdown file")
    ap.add_argument("--check", action="store_true", help="Dry-run: print planned stamps, write nothing")
    ap.add_argument(
        "--all",
        action="store_true",
        help="Stamp every exact 00-master-plan.md under plans/ (skip design/overview stubs)",
    )
    ap.add_argument(
        "--audit",
        action="store_true",
        help="Read-only ledger classification (MASTER vs PHASE); never modifies files",
    )
    ap.add_argument(
        "--plans-root",
        default="plans",
        help="Root of plans tree for --all/--audit (default: plans)",
    )
    args = ap.parse_args(argv)

    if args.audit:
        return audit_plans(Path(args.plans_root))

    if args.all:
        masters = find_masters(Path(args.plans_root))
        if not masters:
            print(f"task-stamp.py: no 00-master-plan.md under {args.plans_root}", file=sys.stderr)
            return 1
        rc = 0
        for m in masters:
            rc = process_one(m, check=args.check) or rc
        return rc

    if not args.plan:
        ap.print_help()
        return 2
    return process_one(Path(args.plan), check=args.check)


if __name__ == "__main__":
    sys.exit(main())
