#!/usr/bin/env python3
"""Emit a compact worker contract; the protocol catalog is explicit --full only.

A dispatch supplies task context. This adapter adds ownership/state boundaries
and host translation, without requiring another lifecycle or specialist chain.
"""
import os
import re
import sys

DESC_MAX = 155


def _frontmatter(path):
    """``(name, description)`` from a SKILL.md — tolerant, never raises."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(8192)
    except OSError:
        return None, None
    m = re.match(r"^---\n(.*?)\n---", head, re.S)
    if not m:
        return None, None
    fm = m.group(1)

    def grab(key):
        # Quoted form first (descriptions containing ': ' MUST be quoted — see
        # the strict-YAML guard in test-plugin.sh), then bare.
        q = re.search(r"^%s:\s*\"(.*?)\"\s*$" % key, fm, re.M | re.S)
        if q:
            return q.group(1)
        b = re.search(r"^%s:\s*(.+)$" % key, fm, re.M)
        return b.group(1).strip() if b else None

    return grab("name"), grab("description")


def _one_clause(desc):
    """First sentence/clause, hard-capped — the roster is an index, not docs."""
    if not desc:
        return ""
    d = " ".join(desc.split())
    cut = re.split(r"(?<=[.;])\s", d, 1)[0]
    if len(cut) > DESC_MAX:
        cut = cut[:DESC_MAX].rsplit(" ", 1)[0] + "…"
    return cut


def build(root, full=False):
    skills_dir = os.path.join(root, "workflow-skills")
    cmds_dir = os.path.join(root, "commands")

    skills = []
    try:
        for name in sorted(os.listdir(skills_dir)):
            sm = os.path.join(skills_dir, name, "SKILL.md")
            if not os.path.isfile(sm):
                continue
            n, d = _frontmatter(sm)
            skills.append((n or name, _one_clause(d)))
    except OSError:
        pass

    cmds = []
    try:
        cmds = sorted(
            f[:-3] for f in os.listdir(cmds_dir) if f.endswith(".md"))
    except OSError:
        pass

    out = [
        "=== META-DEV HARNESS (worker contract) ===",
        "Framework root: %s" % root,
        "Do the supplied scoped task with native tools; no automatic skill chain.",
        "Read a specialist protocol only when named or needed for an unresolved question.",
        "The protocol catalog below is opt-in, not an execution checklist.",
        "",
    ]

    if full:
        # Explicit discovery aid; ordinary workers receive no catalog.
        if skills:
            out.append("PROTOCOLS (%d) — read %s/workflow-skills/<name>/SKILL.md" % (
                len(skills), root))
            for n, d in skills:
                out.append("  %-24s %s" % (n, d))
            out.append("")
        if cmds:
            out.append("PROCEDURES (%d) — read %s/commands/<name>.md" % (
                len(cmds), root))
            line = "  "
            for c in cmds:
                if len(line) + len(c) + 2 > 100:
                    out.append(line.rstrip())
                    line = "  "
                line += c + ", "
            if line.strip():
                out.append(line.rstrip().rstrip(","))
            out.append("")

    out.extend([
        "Completion contract: references/execute-charter.md under the framework root.",
        "Keep ownership through ordinary repairs and whole-task acceptance checking.",
        "Resolve changed technical assumptions within scope; the existing go covers repairs.",
        "Run focused verification; return commits, actual results and unresolved requirements.",
        "Commit exact paths before a genuine stop, even red; red is not completion.",
        "Preserve peer work and exclusive file ownership. The conductor owns planctl state.",
        "Read-only work never edits or commits. Workers never push or farm sub-workers.",
        "Keep plans in the project plans tree. Do not edit checkboxes or dashboards.",
        "Translate named vendor procedures to available host tools; do not invent capabilities.",
        "${CLAUDE_PLUGIN_ROOT} = %s" % root,
        "",
    ])
    out.append("=== END META-DEV HARNESS ===")
    return "\n".join(out)


_FALLBACK = """=== META-DEV HARNESS (you are a worker inside it) ===
Own the declared task through ordinary repairs and whole-task self-check under
its existing scoped go and budget. Commit exact paths before stopping, even red;
red is durability, not completion or a reason to return. Report actual evidence
and genuine blockers. Read-only work never edits or commits. The conductor owns
planctl state; do not edit checkboxes, push or dispatch sub-workers.
=== END META-DEV HARNESS ==="""


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--full"]
    full = "--full" in sys.argv[1:]
    if not args:
        sys.stdout.write(_FALLBACK)
        sys.exit(0)
    try:
        sys.stdout.write(build(os.path.abspath(args[0]), full=full))
    except Exception:
        # A roster problem must never break a dispatch.
        sys.stdout.write(_FALLBACK)
