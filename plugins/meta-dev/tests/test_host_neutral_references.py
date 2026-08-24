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
CLAUDE_AUTHORITY = re.compile(
    r"\b(?:authorit(?:y|ative)|binding|canonical|convention|constraint|derive|"
    r"doctrine|follow|grant|govern|permission|require|rule|select|source|toolchain)\w*\b",
    re.IGNORECASE,
)

LIVE_ROOTS = (
    ROOT / "agents",
    ROOT / "commands",
    ROOT / "references",
    ROOT / "templates",
    ROOT / "workflow-skills",
)


def test_live_instructions_do_not_restore_claude_first_paths():
    offenders: list[str] = []
    for directory in LIVE_ROOTS:
        for path in directory.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for phrase in FORBIDDEN:
                if phrase in text:
                    offenders.append(f"{path.relative_to(ROOT)}: {phrase}")

    assert not offenders, "\n".join(offenders)


def test_live_instructions_do_not_treat_claude_md_as_authority():
    offenders: list[str] = []
    for directory in LIVE_ROOTS:
        for path in directory.rglob("*.md"):
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
                if CLAUDE_REFERENCE.search(line_normalized) and (
                    CLAUDE_AUTHORITY.search(line_normalized)
                    or not ALLOWED_CLAUDE_CONTEXT.search(normalized)
                ):
                    offenders.append(f"{path.relative_to(ROOT)}:{index + 1}: {line.strip()}")

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
    assert claude_manifest["version"] == codex_manifest["version"] == "1.4.30"

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
    assert "## 1.4.30" in changelog
