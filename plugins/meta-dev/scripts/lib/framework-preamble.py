#!/usr/bin/env python3
"""Emit the meta-dev FRAMEWORK preamble handed to every non-Claude worker.

Why this exists
---------------
A Claude Code worker is born inside the harness: it has the plugin's skills and
slash commands, the hooks fire, and CLAUDE.md is in its context. A Codex worker
has NONE of that. Dispatch it a bare task and it will cheerfully freelance —
inventing its own review process, hand-editing checkboxes, running `git add -A`
— because it has no idea a harness exists.

So we hand it the harness: WHERE the framework lives, WHAT protocols are
available (generated from disk, so this roster can never drift from reality),
which one to reach for, and the two or three laws that are non-negotiable.

Token budget is the whole design constraint. The full skill descriptions run
~4KB and the command list ~1KB; a worker that spends its context reading a menu
has less left for the job. So descriptions are truncated to one clause and
commands are emitted as bare names — enough to know a thing EXISTS and read it
on demand, which is exactly how Codex surfaces its own skills.

Usage:  framework-preamble.py <plugin-root>
Stdout: the preamble. Stderr: nothing. Never fails the caller — a broken roster
must not take down a dispatch, so any error degrades to the static core.
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


def build(root):
    skills_dir = os.path.join(root, "skills")
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

    out = []
    out.append("=== META-DEV HARNESS (you are a worker inside it) ===")
    out.append("")
    out.append("You are NOT a general assistant on a loose task. You are executing")
    out.append("inside the meta-dev harness, which has established protocols for this")
    out.append("work. Use them instead of inventing your own.")
    out.append("")
    out.append("Framework root: %s" % root)
    out.append("  skills/<name>/SKILL.md    — protocols (read the one that fits)")
    out.append("  commands/<name>.md        — entry-point procedures")
    out.append("  references/               — deep detail referenced by the above")
    out.append("  scripts/planctl.sh        — THE state CLI (see LAWS below)")
    out.append("")
    out.append("BEFORE YOU START: if any protocol below matches your task, READ IT")
    out.append("FIRST and follow it. Reading one file is cheap; a freelanced review or")
    out.append("a hand-edited plan file is expensive to undo.")
    out.append("")

    if skills:
        out.append("PROTOCOLS (%d) — read %s/skills/<name>/SKILL.md" % (
            len(skills), root))
        for n, d in skills:
            out.append("  %-24s %s" % (n, d))
        out.append("")

    if cmds:
        out.append("PROCEDURES (%d) — read %s/commands/<name>.md" % (
            len(cmds), root))
        # Bare names, wrapped: presence is the signal; the file is the content.
        line = "  "
        for c in cmds:
            if len(line) + len(c) + 2 > 100:
                out.append(line.rstrip())
                line = "  "
            line += c + ", "
        if line.strip():
            out.append(line.rstrip().rstrip(","))
        out.append("")

    out.append("LAWS (binding — these are why the harness exists):")
    out.append("1. planctl is the ONLY write door for plan state. To flip a checkbox,")
    out.append("   set a stage, or claim work, run")
    out.append("   `bash %s/scripts/planctl.sh <verb>`." % root)
    out.append("   NEVER hand-edit a `- [ ]` checkbox in a plan .md — the index and the")
    out.append("   markdown will disagree and the dashboards will lie.")
    out.append("2. Plans live in the project's plans/ tree; CODE lives in the child")
    out.append("   repos. Never write plan files into a code repo, or vice versa.")
    out.append("3. Report honestly. If a verify command fails, say so and paste the")
    out.append("   output. A green claim over a red run is the one unrecoverable error.")
    out.append("4. Touch only what your task declares. If the task contradicts what you")
    out.append("   find on disk, STOP and report — do not improvise.")
    out.append("")
    out.append("Harness translation (that markdown is written for Claude Code):")
    out.append("  ${CLAUDE_PLUGIN_ROOT} = %s" % root)
    out.append("  You have NO Read/Grep/Glob/Task tools and NO slash commands. Read with")
    out.append("  your shell (rg/sed/cat), edit with apply_patch. Where a file says to")
    out.append("  invoke /foo or a named skill, READ THAT FILE and follow it inline.")
    out.append("  Where it says to dispatch subagents, do that work sequentially unless")
    out.append("  you have spawn_agent.")
    out.append("")
    out.append("=== END META-DEV HARNESS ===")
    return "\n".join(out)


_FALLBACK = """=== META-DEV HARNESS (you are a worker inside it) ===
You are executing inside the meta-dev harness. Protocols live in
skills/<name>/SKILL.md and commands/<name>.md under the plugin root; read the
one matching your task before starting.
LAWS: planctl (scripts/planctl.sh) is the ONLY write door for plan state —
never hand-edit a checkbox. Report failures honestly with output. Touch only
what your task declares.
=== END META-DEV HARNESS ==="""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stdout.write(_FALLBACK)
        sys.exit(0)
    try:
        sys.stdout.write(build(os.path.abspath(sys.argv[1])))
    except Exception:
        # A roster problem must never break a dispatch.
        sys.stdout.write(_FALLBACK)
