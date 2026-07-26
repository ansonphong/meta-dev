#!/usr/bin/env bash
# Focused contract for the native Codex package and its deliberately small workflow surface.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PLUGIN_ROOT/../.." && pwd)"

python3 - "$PLUGIN_ROOT" "$REPO_ROOT" <<'PY'
import json
from pathlib import Path
import sys
import yaml
import jsonschema

plugin_root = Path(sys.argv[1])
repo_root = Path(sys.argv[2])
claude = json.loads((plugin_root / ".claude-plugin/plugin.json").read_text())
codex = json.loads((plugin_root / ".codex-plugin/plugin.json").read_text())

identity = ("name", "version", "description", "author", "homepage", "repository", "license", "keywords")
assert {key: codex[key] for key in identity} == {key: claude[key] for key in identity}
assert codex["skills"] == "./codex-skills"
assert "hooks" not in codex

expected = {
    "dev": ("skills/waterfall-tracking/SKILL.md", "commands/meta-dev.md"),
    "plan": ("skills/dod-contract/SKILL.md", "commands/meta-planner.md"),
    "harden": ("skills/plan-validation/SKILL.md", "commands/meta-loop-gap.md"),
    "execute": ("skills/agentic-exec-loop/SKILL.md", "references/execute-dispatch.md"),
    "review": ("skills/code-review-protocol/SKILL.md", "references/execute-charter.md"),
    "ship": ("skills/deploy-pipeline/SKILL.md", "references/ship-pipeline.md"),
    "dashboard": ("scripts/dashboard-data.sh", "references/dashboard-layout.md"),
    "runbook": ("skills/runbook-orchestration/SKILL.md", "references/runbook-view.md"),
    "diagnose": ("skills/repair-loop/SKILL.md", "references/codebase-verification.md"),
    "ops": ("skills/changelog-engine/SKILL.md", "skills/version-manager/SKILL.md"),
}
skills_root = plugin_root / "codex-skills"
assert {path.name for path in skills_root.iterdir() if path.is_dir()} == set(expected)
total = 0
for name, targets in expected.items():
    path = skills_root / name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    total += len(text.encode("utf-8"))
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["name"] == name
    assert len(frontmatter["description"]) < 160
    assert "host-neutral" in text and "slash-command" in text
    for target in targets:
        assert (plugin_root / target).is_file(), f"{name}: missing {target}"
assert total < 4096, f"Codex skill surface is {total} bytes"

settings = json.loads((plugin_root / "templates/settings.json").read_text())
routes = settings["meta_dev"]["codex"]
assert routes["models"] == {
    "plan": {"tier": "sol", "effort": "high"},
    "harden": {"tier": "sol", "effort": "high"},
    "review": {"tier": "sol", "effort": "high"},
    "execute": {"tier": "terra", "effort": "medium"},
    "lightweight": {"tier": "terra", "effort": "low"},
    "mechanical": {"tier": "spark", "effort": "low"},
}
assert routes["reviewer"] == "native" and routes["compat_router"] is True
assert settings["meta_dev"]["models"]["stage_overrides"]["plan"] == "sonnet"

schema = json.loads((plugin_root / "schemas/settings.schema.json").read_text())
jsonschema.validate(settings, schema)
codex_schema = schema["properties"]["meta_dev"]["properties"]["codex"]
assert codex_schema["properties"]["reviewer"]["default"] == "native"
assert codex_schema["properties"]["compat_router"]["default"] is True
assert schema["definitions"]["codex_model_route"]["properties"]["tier"]["enum"] == ["spark", "terra", "sol"]

marketplace = json.loads((repo_root / ".agents/plugins/marketplace.json").read_text())
entry = next(item for item in marketplace["plugins"] if item["name"] == "meta-dev")
assert entry["source"] == {"source": "local", "path": "./plugins/meta-dev"}
assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
assert entry["category"] == "Productivity"
print(f"PASS: Codex package surface ({len(expected)} skills, {total} bytes)")
PY
