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

# A CLAUDE.md reference is safe only when it describes a host adapter or a
# compatibility/migration input, or makes AGENTS.md the controlling source.
# Keep this rule semantic rather than accumulating one-off forbidden phrases.
CLAUDE_REFERENCE = re.compile(r"\bCLAUDE\.md\b", re.IGNORECASE)
ALLOWED_CLAUDE_CONTEXT = re.compile(
    r"\b(?:adapter|compatibility|legacy|migration)\b"
    r"|\bAGENTS\.md\s+(?:points?\s+to|is\s+exactly|constrains?)\b",
    re.IGNORECASE,
)
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
# are recognized semantically by ALLOWED_CLAUDE_CONTEXT, not by a whole-script
# exemption.
LIVE_SCRIPT_ROOT = ROOT / "scripts"
LIVE_SCRIPT_SUFFIXES = {".sh", ".py"}

# The doctor detects legacy context links while it audits a host project.  That
# exact detector is compatibility logic, not host-project instruction; keep
# the exception smaller than a whole-script exemption.
CLAUDE_PATH_COMPATIBILITY_ALLOWLIST = {
    (Path("scripts/agent-surface-doctor.py"), ".claude/context/"),
}

# These are the two places where a Claude adapter path is itself the subject:
# the host-neutral ABI describes generated adapters, and the generator writes
# them. Everywhere else, live instructions must name canonical Agent Skills.
CLAUDE_SKILL_ADAPTER_ALLOWLIST = {
    Path("references/host-project-contract.md"),
    Path("scripts/sync-agent-skill-adapters.py"),
}

# The doctor enumerates the Claude adapter path as a discovery input, not an
# authority.  Allow exactly that one line and nothing else in the file; a
# semantic broadening or a whole-file exemption would defeat the guard.
CLAUDE_ADAPTER_DISCOVERY_ALLOWLIST = {
    (
        Path("scripts/agent-surface-doctor.py"),
        'for rel in ("AGENTS.md", ".claude/CLAUDE.md"):',
    ),
}


def live_instruction_paths() -> list[Path]:
    return [
        path
        for directory in LIVE_ROOTS
        for path in directory.rglob("*.md")
    ]


def live_script_paths() -> list[Path]:
    return [
        path
        for path in LIVE_SCRIPT_ROOT.rglob("*")
        if path.suffix in LIVE_SCRIPT_SUFFIXES
    ]


def test_live_instructions_do_not_restore_claude_first_paths():
    offenders: list[str] = []
    for path in [*live_instruction_paths(), *live_script_paths()]:
        relative_path = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        for phrase in FORBIDDEN:
            if (relative_path, phrase) in CLAUDE_PATH_COMPATIBILITY_ALLOWLIST:
                continue
            if phrase in text:
                offenders.append(f"{relative_path}: {phrase}")

    assert not offenders, "\n".join(offenders)


def test_live_script_corpus_includes_the_agent_surface_doctor():
    assert ROOT / "scripts" / "agent-surface-doctor.py" in live_script_paths()


def test_live_instructions_do_not_treat_claude_md_as_authority():
    offenders: list[str] = []
    for path in [*live_instruction_paths(), *live_script_paths()]:
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            start = index
            while start and lines[start - 1]:
                start -= 1
            end = index + 1
            while end < len(lines) and lines[end]:
                end += 1
            normalized = "\n".join(lines[start:end]).replace("`", "")
            line_normalized = line.replace("`", "")
            if (
                CLAUDE_REFERENCE.search(line_normalized)
                and not ALLOWED_CLAUDE_CONTEXT.search(normalized)
                and (path.relative_to(ROOT), line_normalized.strip())
                not in CLAUDE_ADAPTER_DISCOVERY_ALLOWLIST
            ):
                offenders.append(f"{path.relative_to(ROOT)}:{index + 1}: {line.strip()}")

    assert not offenders, "\n".join(offenders)


def test_live_instructions_do_not_use_claude_skill_adapters_operationally():
    offenders: list[str] = []
    for path in [*live_instruction_paths(), *live_script_paths()]:
        relative_path = path.relative_to(ROOT)
        if relative_path in CLAUDE_SKILL_ADAPTER_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if ".claude/skills/" in text:
            offenders.append(f"{relative_path}: .claude/skills/")

    assert not offenders, "\n".join(offenders)


def test_live_instructions_name_the_host_project_contract():
    contract = ROOT / "references" / "host-project-contract.md"
    assert contract.is_file()
    assert "Root `AGENTS.md` is the canonical project doctrine." in contract.read_text(
        encoding="utf-8"
    )


def test_portability_release_keeps_manifests_and_marketplaces_in_lockstep():
    claude_manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    codex_manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert claude_manifest["version"] == codex_manifest["version"] == "1.4.32"

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
    assert "## 1.4.32" in changelog
