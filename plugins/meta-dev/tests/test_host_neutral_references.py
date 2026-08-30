"""Regression guard for AGENTS-first live harness instructions."""
from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

# These phrases select a Claude-first *canonical* instruction.  Compatibility
# detection belongs in host-project-contract.md and agent-surface-doctor.py,
# not in the procedures that guide a host project.
FORBIDDEN = (
    "references/host-claude-contract.md",
    "host-claude-contract",
    ".claude/context/",
    "host CLAUDE.md",
    "host project's `CLAUDE.md`",
    "Read CLAUDE.md",
    "target repo's `CLAUDE.md`",
    "CLAUDE.md →",
    "host `CLAUDE.md`",
)

CLAUDE_REFERENCE = re.compile(r"\bCLAUDE\.md\b", re.IGNORECASE)
LIVE_ROOTS = (
    ROOT / "agents",
    ROOT / "commands",
    ROOT / "references",
    ROOT / "templates",
    ROOT / "workflow-skills",
)

# Scripts are live operational doctrine too.  Do not scan tests or fixtures:
# they describe guard cases rather than host-project instructions.  The
# initializer's migration and adapter references are compatibility logic and
# are recognized by CLAUDE_MD_LINE_ALLOWLIST, not by a whole-script exemption.
LIVE_SCRIPT_ROOT = ROOT / "scripts"
LIVE_SCRIPT_SUFFIXES = {".sh", ".py"}

# The doctor detects legacy context links while it audits a host project.  That
# exact detector is compatibility logic, not host-project instruction.  Allow
# only its exact stripped line: any other ".claude/context/" occurrence in the
# doctor must still fail the guard.
CLAUDE_PATH_CONTEXT_LINE_ALLOWLIST = {
    (
        Path("scripts/agent-surface-doctor.py"),
        r'for target in re.findall(r"(?:docs/agent-context/|\.claude/context/)([^\s)`]+)", file.read_text(encoding="utf-8", errors="ignore")):',
    ),
}

# The host-neutral ABI describes generated Claude adapters and names the exact
# ".claude/skills/" path it hashes.  Allow only that one stripped line; any
# other ".claude/skills/" occurrence, anywhere in live instructions or scripts,
# must still fail the guard.  (sync-agent-skill-adapters.py has no literal
# ".claude/skills/" occurrence and needs no exception.)
CLAUDE_SKILL_ADAPTER_ALLOWLIST = {
    (
        Path("references/host-project-contract.md"),
        "`.claude/skills/` and records SHA-256 values in",
    ),
}

# A CLAUDE.md occurrence is safe only as an exact (relative path, stripped
# line) compatibility/adapter/detection reference.  Every line that mentions
# CLAUDE.md must match one of these entries; a new authority-style "Read
# CLAUDE.md" line anywhere in these files fails the guard.  No semantic
# paragraph exemption, whole-file skip, or line-number matching.
CLAUDE_MD_LINE_ALLOWLIST = {
    # references/host-project-contract.md — describes the Claude adapter and
    # compatibility/migration inputs, never an authority to consult.
    (
        Path("references/host-project-contract.md"),
        "Root `CLAUDE.md` and `.claude/CLAUDE.md` remain compatibility inputs. Report a",
    ),
    (
        Path("references/host-project-contract.md"),
        "never create root `CLAUDE.md`. Their required generated output is the thin",
    ),
    (
        Path("references/host-project-contract.md"),
        "adapter `.claude/CLAUDE.md` with exactly `@../AGENTS.md` followed by a newline.",
    ),
    (
        Path("references/host-project-contract.md"),
        "| adapter | Root `AGENTS.md` resolves normally and `.claude/CLAUDE.md` is exactly `@../AGENTS.md`. | Use the root doctrine first and the adapter only for that host. |",
    ),
    (
        Path("references/host-project-contract.md"),
        "Legacy candidates include both root `CLAUDE.md` and `.claude/CLAUDE.md`.",
    ),
    (
        Path("references/host-project-contract.md"),
        "separator; it removes root `CLAUDE.md` and writes `.claude/CLAUDE.md` exactly",
    ),
    # references/workflows/command-adapter.md — tells the Codex adapter not to
    # treat CLAUDE.md as an authority.
    (
        Path("references/workflows/command-adapter.md"),
        "neutral context. Do not consult `CLAUDE.md` for project details. Inspect it",
    ),
    # scripts/agent-surface-doctor.py — detection logic over legacy and adapter
    # contract inputs, not host-project instruction.
    (
        Path("scripts/agent-surface-doctor.py"),
        'legacy_root = root / "CLAUDE.md"',
    ),
    (
        Path("scripts/agent-surface-doctor.py"),
        'adapter = root / ".claude" / "CLAUDE.md"',
    ),
    (
        Path("scripts/agent-surface-doctor.py"),
        'elif not any("AGENTS.md" in value for value in instructions) or not any("CLAUDE.md" in value for value in instructions):',
    ),
    (
        Path("scripts/agent-surface-doctor.py"),
        'errors.append("live_grok_inspect.project_instructions must record AGENTS.md and CLAUDE.md compatibility")',
    ),
    (
        Path("scripts/agent-surface-doctor.py"),
        'for rel in ("AGENTS.md", ".claude/CLAUDE.md"):',
    ),
    (
        Path("scripts/agent-surface-doctor.py"),
        'root_claude = root / "CLAUDE.md"',
    ),
    (
        Path("scripts/agent-surface-doctor.py"),
        'add(findings, "error", "root_claude", root_claude, "root CLAUDE.md is forbidden")',
    ),
    (
        Path("scripts/agent-surface-doctor.py"),
        'if path.is_symlink() and (path.name.casefold() in {"agents.md", "claude.md"} or "agent-context" in path.parts):',
    ),
    # scripts/init-project.sh — migration writes remove legacy CLAUDE.md and
    # emit the thin adapter; these are shell operations, not instructions.
    (
        Path("scripts/init-project.sh"),
        'if [ -f CLAUDE.md ]; then',
    ),
    (
        Path("scripts/init-project.sh"),
        'cat CLAUDE.md > "$migration_tmp"',
    ),
    (
        Path("scripts/init-project.sh"),
        'if [ -f .claude/CLAUDE.md ]; then',
    ),
    (
        Path("scripts/init-project.sh"),
        "printf '\\n\\n<!-- Migrated from .claude/CLAUDE.md -->\\n\\n' >> \"$migration_tmp\"",
    ),
    (
        Path("scripts/init-project.sh"),
        'cat .claude/CLAUDE.md >> "$migration_tmp"',
    ),
    (
        Path("scripts/init-project.sh"),
        'rm -f CLAUDE.md',
    ),
    (
        Path("scripts/init-project.sh"),
        "printf '@../AGENTS.md\\n' > .claude/CLAUDE.md",
    ),
    (
        Path("scripts/init-project.sh"),
        'echo "Created .claude/CLAUDE.md adapter"',
    ),
}


def live_instruction_paths() -> list[Path]:
    return [
        path
        for directory in LIVE_ROOTS
        for path in directory.rglob("*.md")
    ]


def live_script_paths() -> list[Path]:
    """Live scripts include suffixed and suffixless text entry points.

    Suffixless entry points (agent-surface-check, claude-headless-exec, ...)
    are regular executable text scripts.  Skip symlinks, cache directories,
    and binary artifacts so only live doctrine is scanned.
    """
    paths: list[Path] = []
    for path in LIVE_SCRIPT_ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix in LIVE_SCRIPT_SUFFIXES:
            paths.append(path)
        elif path.suffix == "":
            try:
                path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            paths.append(path)
    return paths


def forbidden_path_offenders(relative_path: Path, text: str) -> list[str]:
    """Report forbidden phrases per line, honoring the exact-line context allowlist."""
    offenders: list[str] = []
    for index, line in enumerate(text.splitlines()):
        for phrase in FORBIDDEN:
            if phrase not in line:
                continue
            if (
                phrase == ".claude/context/"
                and (relative_path, line.strip())
                in CLAUDE_PATH_CONTEXT_LINE_ALLOWLIST
            ):
                continue
            offenders.append(f"{relative_path}:{index + 1}: {phrase}")
    return offenders


def skill_adapter_offenders(relative_path: Path, text: str) -> list[str]:
    """Report ".claude/skills/" occurrences per line, honoring the exact-line adapter allowlist."""
    offenders: list[str] = []
    for index, line in enumerate(text.splitlines()):
        if ".claude/skills/" not in line:
            continue
        if (relative_path, line.strip()) in CLAUDE_SKILL_ADAPTER_ALLOWLIST:
            continue
        offenders.append(f"{relative_path}:{index + 1}: .claude/skills/")
    return offenders


def claude_md_offenders(relative_path: Path, text: str) -> list[str]:
    """Report every CLAUDE.md line not matched by the exact line allowlist."""
    offenders: list[str] = []
    for index, line in enumerate(text.splitlines()):
        if not CLAUDE_REFERENCE.search(line.replace("`", "")):
            continue
        if (relative_path, line.strip()) in CLAUDE_MD_LINE_ALLOWLIST:
            continue
        offenders.append(f"{relative_path}:{index + 1}: {line.strip()}")
    return offenders


def test_live_instructions_do_not_restore_claude_first_paths():
    offenders: list[str] = []
    for path in [*live_instruction_paths(), *live_script_paths()]:
        offenders.extend(
            forbidden_path_offenders(
                path.relative_to(ROOT), path.read_text(encoding="utf-8")
            )
        )

    assert not offenders, "\n".join(offenders)


def test_context_path_line_allowlist_reports_extra_doctor_occurrences():
    relative_path = Path("scripts/agent-surface-doctor.py")
    (allowed_line,) = (
        line
        for (path, line) in CLAUDE_PATH_CONTEXT_LINE_ALLOWLIST
        if path == relative_path
    )
    text = allowed_line + "\n" + "# a second .claude/context/ reference\n"
    offenders = forbidden_path_offenders(relative_path, text)
    assert offenders == [f"{relative_path}:2: .claude/context/"]


def test_live_script_corpus_includes_live_entry_points():
    scripts = live_script_paths()
    for name in (
        "agent-surface-doctor.py",
        "init-project.sh",
        "agent-surface-check",
        "claude-headless-exec",
    ):
        assert ROOT / "scripts" / name in scripts, name


def test_live_instructions_do_not_treat_claude_md_as_authority():
    offenders: list[str] = []
    for path in [*live_instruction_paths(), *live_script_paths()]:
        offenders.extend(
            claude_md_offenders(
                path.relative_to(ROOT), path.read_text(encoding="utf-8")
            )
        )

    assert not offenders, "\n".join(offenders)


def test_live_instructions_do_not_use_claude_skill_adapters_operationally():
    offenders: list[str] = []
    for path in [*live_instruction_paths(), *live_script_paths()]:
        offenders.extend(
            skill_adapter_offenders(
                path.relative_to(ROOT), path.read_text(encoding="utf-8")
            )
        )

    assert not offenders, "\n".join(offenders)


def test_skill_adapter_allowlist_reports_extra_contract_occurrences():
    relative_path = Path("references/host-project-contract.md")
    (allowed_line,) = (
        line
        for (path, line) in CLAUDE_SKILL_ADAPTER_ALLOWLIST
        if path == relative_path
    )
    text = allowed_line + "\n" + "# a second .claude/skills/ reference\n"
    offenders = skill_adapter_offenders(relative_path, text)
    assert offenders == [f"{relative_path}:2: .claude/skills/"]


def test_claude_md_allowlist_reports_appended_authority_line():
    for relative_path in sorted({path for (path, _) in CLAUDE_MD_LINE_ALLOWLIST}):
        text = "# unrelated line\nRead CLAUDE.md before AGENTS.md.\n"
        offenders = claude_md_offenders(relative_path, text)
        assert offenders == [
            f"{relative_path}:2: Read CLAUDE.md before AGENTS.md."
        ], offenders


def test_live_instructions_name_the_host_project_contract():
    contract = ROOT / "references" / "host-project-contract.md"
    assert contract.is_file()
    assert "Root `AGENTS.md` is the canonical project doctrine." in contract.read_text(
        encoding="utf-8"
    )


def test_portability_release_keeps_manifests_and_marketplaces_in_lockstep():
    claude_manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    codex_manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert claude_manifest["version"] == codex_manifest["version"] == "1.4.33"

    repository = ROOT.parents[1]
    agents_marketplace = json.loads(
        (repository / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    claude_marketplace = json.loads(
        (repository / ".claude-plugin" / "marketplace.json").read_text()
    )
    agents_source = agents_marketplace["plugins"][0]["source"]["path"]
    claude_source = claude_marketplace["plugins"][0]["source"]
    assert agents_source == claude_source == "./plugins/meta-dev"
    assert "version" not in agents_marketplace["plugins"][0]
    assert "version" not in claude_marketplace["plugins"][0]

    changelog = (repository / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 1.4.33" in changelog
