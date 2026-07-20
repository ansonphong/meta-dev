#!/usr/bin/env python3
"""Live source-of-truth scanner for the unified plan-tracking system.

Thin shim delegating to planctl (the unified state layer). Kept for one version
as a rollback path (design §7). parse_frontmatter(text) + count_checkboxes(text)
keep their PURE-TEXT bodies — runbook-render.py imports them with raw strings,
not paths. main() / build_entry() / walk_candidates() delegate to planctl reads.

Deterministic, no LLM, no third-party deps. MUST NEVER crash on bad input.
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
# Declared-truth keys only. `status` is NOT here: it is DERIVED by
# planctl/derive.py and never typed into frontmatter (stage.py refuses to write
# it). Requiring it marked 54 of 60 live master plans "malformed" whenever the
# planctl read-model was unavailable and this fallback ran.
REQUIRED_KEYS = ("stage", "repo")
RUNBOOK = "plans/meta-runbook.md"

CHECKBOX = re.compile(r"^\s*[-*]\s*\[([ xX])\]")
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*#*\s*$")
MILESTONE = re.compile(r"^=+\s*MILESTONE:\s*(.+?)\s*=+\s*$")
DATED = re.compile(r"^\d{4}-\d{2}-\d{2}-.*\.md$")
NOISE = re.compile(
    r"^(phase-.*\.md|design\.md|handoff.*|.*-config\.md|\.loop-gap-config\.md"
    r"|_runbook-.*\.md|_exec-order-.*\.md)$",
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
            "text": text,
            "progress": count_checkboxes(text)}


# ── planctl delegation (lazy — import-time side-effect-free) ────────────────────
def _derive_legacy_status(derived_status, override):
    """Map a planctl derived_status to the legacy 4-word vocabulary the old
    dashboard-render.py's GLYPH map understands (done/blocked/active/draft).
    Mirror for one version alongside derived_status (W2A-3 rollback)."""
    if override:
        return "blocked"
    if derived_status in ("done", "draft"):
        return derived_status
    if derived_status in ("executing", "ready", "needs-review"):
        return "active"
    if derived_status == "blocked":
        return "blocked"
    return "draft"


def _planctl_data():
    """Query the planctl DB for plan data. Returns (plans, runbooks, plan_to_runbook,
    order, milestones, trailing, untracked, counts, focus, scope, scope_kind)
    or None when planctl is unavailable (import error / no DB / stale schema)."""
    try:
        from planctl import db as _db, statedir as _statedir, sync as _sync
    except ImportError:
        return None

    try:
        conn = _db.open_db()
    except Exception:
        return None

    try:
        # Ensure freshness (cheap — ensure_fresh, not full sync)
        root = _statedir.project_root()
        try:
            _sync.ensure_fresh(conn, root)
        except Exception:
            pass  # non-fatal: use whatever is indexed

        # ── query plans ──────────────────────────────────────────────────────
        plan_rows = conn.execute(
            "SELECT p.path, p.repo, p.stage, p.override, p.note, p.why, "
            "p.tasks_done, p.tasks_total, p.drift, p.derived_status, "
            "p.stage_state, p.smoke_total, "
            "f.parse_err FROM plans p JOIN files f ON f.path=p.path "
            "WHERE f.kind='plan' ORDER BY p.path"
        ).fetchall()

        # ── query runbooks ───────────────────────────────────────────────────
        rb_rows = conn.execute(
            "SELECT p.path, p.repo, p.stage, p.override, p.note, p.why, "
            "p.tasks_done, p.tasks_total, p.derived_status "
            "FROM plans p JOIN files f ON f.path=p.path "
            "WHERE f.kind='runbook' ORDER BY p.path"
        ).fetchall()

        # ── query edges ──────────────────────────────────────────────────────
        edge_rows = conn.execute(
            "SELECT src, dst, kind FROM edges ORDER BY src, dst"
        ).fetchall()
        edges_by_src = {}
        for src, dst, kind in edge_rows:
            edges_by_src.setdefault(src, {"depends": [], "blocks": []})
            edges_by_src[src][kind].append(dst)

        # ── query membership ─────────────────────────────────────────────────
        member_rows = conn.execute(
            "SELECT parent, child FROM membership ORDER BY parent, child"
        ).fetchall()
        plan_to_runbook = {}  # child → parent (first runbook a plan belongs to)
        rb_members = {}       # parent → [child, ...]
        for parent, child in member_rows:
            plan_to_runbook.setdefault(child, parent)
            rb_members.setdefault(parent, []).append(child)

        # ── parse runbook sequence FIRST (order + milestones from meta-runbook.md)
        order, milestones, trailing_paths = parse_runbook_sequence()
        order_set = set(order)

        # ── build all plan entries (from DB, before Sequence filtering) ─────
        all_plans = []
        for row in plan_rows:
            (path, repo, stage, override, note, why,
             td, tt, drift, dstatus, stage_state, smoke_total, parse_err) = row
            legacy = _derive_legacy_status(dstatus, override)
            edges = edges_by_src.get(path, {"depends": [], "blocks": []})
            pct_val = round(100 * td / tt) if tt else 0
            all_plans.append({
                "path": path,
                "status": legacy,              # mirrored for old render (W2A-3)
                "derived_status": dstatus,     # NEW — the new render reads this
                "stage": stage or 0,
                "stage_state": stage_state,
                "smoke": smoke_total or 0,   # badge count; never in progress math
                "drift": bool(drift),
                "repo": repo or "",
                "why": why or "",
                "depends": edges.get("depends", []),
                "blocks": edges.get("blocks", []),
                "progress": {"done": td or 0, "total": tt or 0, "pct": pct_val},
                "archived": "/_archive/" in path,
                "malformed": bool(parse_err),
                "runbook_group": plan_to_runbook.get(path),  # NEW
            })

        plan_by_path = {p["path"]: p for p in all_plans}

        # ── when Sequence order is available, restrict plans[] to exactly the
        #    Sequence-ordered set; everything else becomes untracked ──────────
        if order:
            plans = [plan_by_path[p] for p in order if p in plan_by_path]
            untracked = [p["path"] for p in all_plans if p["path"] not in order_set]
        else:
            plans = list(all_plans)
            untracked = []

        # ── build runbook rollups ────────────────────────────────────────────
        runbooks = []
        for row in rb_rows:
            (path, repo, stage, override, note, why,
             td, tt, dstatus) = row
            try:
                rollup = _sync.compute_rollup(conn, path) or {}
            except Exception:
                rollup = {}
            runbooks.append({
                "path": path,
                "repo": repo or "",
                "stage": stage or 0,
                "derived_status": dstatus,
                "members_done": rollup.get("members_done", 0),
                "members_total": rollup.get("members_total", 0),
                "tasks_done": rollup.get("tasks_done", td or 0),
                "tasks_total": rollup.get("tasks_total", tt or 0),
                "effective_stage": rollup.get("effective_stage"),
                "now": rollup.get("now"),
            })

        # ── build counts (tracked = Sequence set size when order present) ─────
        counts = {
            "tracked": len(plans),
            "malformed": sum(1 for p in plans if p.get("malformed")),
            "archived": sum(1 for p in plans if p.get("archived")),
        }

        # Fill milestone + trailing done counts (done = derived_status == "done")
        status_by_path = {p["path"]: p for p in plans}
        for m in milestones:
            paths = m.get("plan_paths", [])
            m["plans_total"] = len(paths)
            m["plans_done"] = sum(
                1 for p in paths
                if status_by_path.get(p, {}).get("derived_status") == "done"
            )

        trailing = {
            "plans_total": len(trailing_paths),
            "plans_done": sum(
                1 for p in trailing_paths
                if status_by_path.get(p, {}).get("derived_status") == "done"
            ),
            "plan_paths": trailing_paths,
        }

        return (plans, runbooks, order, milestones, trailing, untracked, counts)
    finally:
        conn.close()


def build_entry(rel, info):
    """Build a plan entry dict from a read_plan_file() info blob (shim — kept
    for backward compat; new code paths use _planctl_data directly)."""
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

    progress = info.get("progress", {"done": 0, "total": 0, "pct": 0})

    # Status is DERIVED, never read from frontmatter. This fallback runs only
    # when the planctl read-model is unavailable, and it used to publish
    # fm['status'] verbatim — which almost no plan declares, so a COMPLETED plan
    # surfaced as '' and every consumer read that as 'draft'. done_for() (the
    # milestone roll-up) tests status == 'done' directly, so completed plans
    # silently stopped counting toward their milestone. Derive it with the same
    # interpreter the primary path uses so the two agree.
    # The counts fed to derive MUST be execution-only. The primary path splits
    # human-verify boxes ("by eye"/"by hand"/GPU/manual) out before deriving;
    # feeding it raw checkbox totals instead makes a plan whose code is finished
    # but whose by-eye gates are open derive 'executing' rather than
    # 'needs-review' — the exact completed-is-not-done confusion this whole axis
    # exists to remove. Same parse module as the primary path: one interpreter.
    derived = ""
    drift = False
    degraded = False
    try:
        from planctl import derive as _derive, parse as _parse
    except ImportError:
        # planctl genuinely unusable — this fallback's whole reason to exist.
        degraded = True
    else:
        try:
            text = info.get("text")
            if text is not None:
                tasks, _err = _parse.parse_tasks(text)
                exec_done, exec_total = _parse.count_split(tasks)[:2]
            else:
                exec_done = progress.get("done", 0)
                exec_total = progress.get("total", 0)
            derived, drift = _derive.derive_plan(fm, exec_done, exec_total)
        except Exception:
            # A real derivation bug must stay VISIBLE. Substituting the declared
            # status here would launder it into a plausible-looking answer — a
            # stale 'status: done' on a stage-3 0/10 plan would read as done.
            degraded = True

    if degraded:
        # We cannot know the status, so do not guess one. Use a declared status
        # if the plan actually has one, else mark the row unreliable rather than
        # letting it default to 'draft' and silently drop out of milestone math.
        declared = str(fm.get("status", "") or "").strip().lower()
        derived = declared
        if not declared:
            entry["malformed"] = True

    stage_state = fm.get("stage_state")
    if isinstance(stage_state, str):
        stage_state = stage_state.strip().lower() or None

    # `status` carries the LEGACY 4-word vocabulary in both paths (the primary
    # path mirrors it via _derive_legacy_status for the old render's GLYPH map
    # and for --status filtering). Emitting the raw new-vocabulary value here
    # would make the two paths disagree: 'needs-review' is not a legacy word.
    entry.update({
        "status": (_derive_legacy_status(derived, fm.get("override"))
                   if derived else ""),
        "derived_status": derived,
        "drift": bool(drift),
        "stage": stage,
        "stage_state": stage_state,
        "repo": fm.get("repo", ""),
        "why": fm.get("why", "") or "",
        "depends": as_list(fm.get("depends")),
        "blocks": as_list(fm.get("blocks")),
        "progress": progress,
    })
    if missing:
        entry["malformed"] = True
    return entry


def walk_candidates(exclude_dirs=EXCLUDE_DIRS):
    """Walk plans/, return allowlisted candidate paths (excluded dirs pruned).

    Delegates to planctl DB when available; falls back to filesystem walk."""
    # Try planctl DB first
    try:
        from planctl import db as _db
        conn = _db.open_db()
        try:
            rows = conn.execute(
                "SELECT path FROM files WHERE kind='plan' ORDER BY path"
            ).fetchall()
            out = [r[0] for r in rows]
            if exclude_dirs:
                out = [p for p in out
                       if not any(d in p.split("/") for d in exclude_dirs)]
            return out
        finally:
            conn.close()
    except Exception:
        pass

    # Fallback: filesystem walk (original behavior)
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
    scope = norm_path(args.scope) if args.scope else None

    # --scope resolution
    focus = None
    scope_kind = None
    if scope and (scope == SENSITIVE or scope in EXCLUDE_BY_NAME):
        focus = build_focus(scope)
        scope_kind = "file"
    elif scope and os.path.isfile(scope):
        focus = build_focus(scope)
        scope_kind = "file"
    elif scope and os.path.isdir(scope):
        scope_kind = "dir"
    elif scope:
        scope_kind = "missing"

    # ── try planctl DB first ─────────────────────────────────────────────────
    pdata = _planctl_data()
    if pdata is not None:
        plans, runbooks, order, milestones, trailing, untracked, counts = pdata
        using_planctl = True
    else:
        # ── fallback: old filesystem walk ────────────────────────────────────
        using_planctl = False
        exclude_dirs = set() if args.all else EXCLUDE_DIRS

        runbook_present = os.path.isfile(RUNBOOK)
        order, milestones, trailing_paths = parse_runbook_sequence()

        discovered = []
        for rel in walk_candidates(exclude_dirs):
            info = read_plan_file(rel)
            if not info.get("ok_read"):
                discovered.append((rel, info))
                continue
            if not info.get("has_fm"):
                continue
            discovered.append((rel, info))
        discovered_map = dict(discovered)

        plans = []
        status_by_path = {}

        if runbook_present and order:
            for rel in order:
                info = discovered_map.get(rel) or read_plan_file(rel)
                entry = build_entry(rel, info)
                plans.append(entry)
                status_by_path[rel] = entry
        else:
            for rel, info in discovered:
                entry = build_entry(rel, info)
                plans.append(entry)
                status_by_path[rel] = entry

        order_set = set(order)
        untracked = [rel for rel, _ in discovered if rel not in order_set]
        runbooks = []

        # Fill milestone + trailing done counts (done = status == "done")
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

    # ── scope DIR: narrow to plans under the dir ──────────────────────────────
    if scope_kind == "dir":
        prefix = scope + "/"

        def under(p):
            if isinstance(p, dict):
                return p.get("path", "") == scope or p.get("path", "").startswith(prefix)
            return p == scope or p.startswith(prefix)

        plans = [p for p in plans if under(p)]
        untracked = [u for u in untracked if under(u)]
    elif scope_kind in ("file", "missing"):
        plans = []
        untracked = []
        runbooks = []

    # ── repo / status filters ─────────────────────────────────────────────────
    if args.repo:
        plans = [p for p in plans if p.get("repo") == args.repo]
        runbooks = [r for r in runbooks if r.get("repo") == args.repo]
    if args.status:
        if using_planctl:
            # Filter by derived_status (the new vocabulary)
            plans = [p for p in plans if p.get("derived_status") == args.status]
        else:
            plans = [p for p in plans if p.get("status") == args.status]

    # ── emit JSON ─────────────────────────────────────────────────────────────
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
    # NEW keys (phase 2a): runbook rollups for the render to group on
    if runbooks:
        out["runbooks"] = runbooks

    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
