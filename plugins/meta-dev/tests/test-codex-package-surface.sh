#!/usr/bin/env bash
# Focused contract for the native Codex package. The legacy Claude surface is
# checked separately by test-codex-parity.sh.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PLUGIN_ROOT/../.." && pwd)"

python3 - "$PLUGIN_ROOT" "$REPO_ROOT" <<'PY'
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import yaml
import jsonschema

plugin_root = Path(sys.argv[1])
repo_root = Path(sys.argv[2])
claude = json.loads((plugin_root / ".claude-plugin/plugin.json").read_text())
codex = json.loads((plugin_root / ".codex-plugin/plugin.json").read_text())

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require_file(relative: str) -> Path:
    path = plugin_root / relative
    assert path.is_file(), f"missing required native target: {relative}"
    return path


identity = ("name", "description", "author", "homepage", "repository", "license", "keywords")
assert {key: codex[key] for key in identity} == {key: claude[key] for key in identity}
assert codex["version"].split("+", 1)[0] == claude["version"].split("+", 1)[0], "manifest base versions drifted"
assert claude["skills"] == "./workflow-skills/"
assert codex["skills"] == "./skills/"
assert "hooks" not in codex
assert codex["interface"] == {
    "displayName": "Meta Dev",
    "shortDescription": "First-class Codex command surface for the meta-dev harness.",
    "longDescription": "Canonical meta-dev commands as native Codex skills, plus compact planning, review, and operations helpers.",
    "developerName": "Phong",
    "category": "Productivity",
    "capabilities": ["Write"],
    "defaultPrompt": [
        "Write a self-contained implementation plan for a fresh agent and save it under plans/<repo>/.",
        "Execute an approved plan task with focused verification.",
        "Review my current change and report a verdict.",
    ],
}

workflow_targets = {
    "dev": ("references/workflows/protocol.md", "workflow-skills/waterfall-tracking/SKILL.md", "commands/meta-dev.md"),
    "plan": ("references/codex-writing-plans.md", "workflow-skills/dod-contract/SKILL.md", "commands/meta-planner.md", "schemas/plan-artifact.schema.json", "scripts/plan-artifact-render.py"),
    "harden": ("references/workflows/protocol.md", "workflow-skills/plan-validation/SKILL.md", "commands/meta-loop-gap.md"),
    "execute": ("references/workflows/protocol.md", "workflow-skills/agentic-exec-loop/SKILL.md", "references/execute-dispatch.md", "workflow-skills/code-review-protocol/SKILL.md"),
    "review": ("references/workflows/protocol.md", "workflow-skills/code-review-protocol/SKILL.md", "references/execute-charter.md"),
    "dashboard": ("references/workflows/protocol.md", "scripts/dashboard-data.sh", "references/dashboard-layout.md"),
    "runbook": ("references/workflows/protocol.md", "workflow-skills/runbook-orchestration/SKILL.md", "references/runbook-view.md"),
    "diagnose": ("references/workflows/protocol.md", "workflow-skills/repair-loop/SKILL.md", "references/codebase-verification.md"),
    "ops": ("workflow-skills/changelog-engine/SKILL.md", "workflow-skills/version-manager/SKILL.md"),
}
skills_root = plugin_root / "skills"
native_dirs = {path.name for path in skills_root.iterdir() if path.is_dir()}
helper_targets = {
    name: workflow_targets[name]
    for name in ("plan", "execute", "harden", "review", "runbook", "diagnose", "ops")
}
helper_text = []
for name, targets in helper_targets.items():
    path = skills_root / name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    helper_text.append(text)
    assert text.startswith("---\n"), f"{name}: missing frontmatter opener"
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["name"] == name
    assert isinstance(frontmatter["description"], str) and len(frontmatter["description"]) < 160
    for target in targets:
        assert f"../../{target}" in text, f"{name}: does not reference {target}"
        require_file(target)
assert "source-command-" not in "\n".join(helper_text), "native skills depend on generated migration skills"

routes = load_json(plugin_root / "references/workflows/routes.json")
assert routes["schema_version"] == 1
require_file(routes["protocol"])
assert set(routes["workflows"]) == set(workflow_targets)
command_files = {path.stem for path in (plugin_root / "commands").glob("*.md")}
assert command_files == set(routes["commands"]), "every legacy command must have exactly one native route"
assert len(command_files) == len(routes["commands"]), (
    f"command/route count mismatch: {len(command_files)} files vs {len(routes['commands'])} routes"
)
for workflow, specification in routes["workflows"].items():
    require_file(specification["skill"])
    assert specification["subcommands"], f"{workflow}: no workflow targets"
    for procedure in specification["subcommands"].values():
        require_file(procedure)

redirect_re = re.compile(r"Execute /[a-z0-9-]+ \$ARGUMENTS")
canonical_commands = set()
for command in (plugin_root / "commands").glob("*.md"):
    text = command.read_text(encoding="utf-8")
    body = text.split("---", 2)[2].strip() if text.startswith("---\n") else text.strip()
    if not redirect_re.fullmatch(body):
        canonical_commands.add(command.stem)
assert len(canonical_commands) == 42, f"expected 42 canonical commands, found {len(canonical_commands)}"
helper_only = {"plan", "execute", "harden", "review", "diagnose", "ops"}
assert native_dirs == canonical_commands | helper_only | {"command-router"}
assert len(native_dirs) == 49, f"expected 42 commands, 6 helpers, and router; found {len(native_dirs)}"

generated_marker = "<!-- generated by scripts/sync-codex-command-skills.py -->"
discovery_bytes = 0
for name in sorted(native_dirs):
    path = skills_root / name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{name}: missing frontmatter opener"
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert set(frontmatter) == {"name", "description"}, f"{name}: unsupported frontmatter"
    assert frontmatter["name"] == name
    assert isinstance(frontmatter["description"], str) and len(frontmatter["description"]) < 160
    discovery_bytes += len(
        f"meta-dev:{name}\t{frontmatter['description']}\tskills/{name}/SKILL.md\n".encode("utf-8")
    )
    if name in canonical_commands:
        procedure = require_file(f"commands/{name}.md")
        assert f"../../commands/{procedure.name}" in text, f"{name}: canonical procedure missing"
        assert "../../references/workflows/command-adapter.md" in text
        if name != "runbook":
            assert generated_marker in text, f"{name}: generated command marker missing"
# 41 command skills + helpers. 5000 was the 40-command budget.
assert discovery_bytes < 5500, f"Codex discovery metadata is {discovery_bytes} bytes before cache prefix"

generator = require_file("scripts/sync-codex-command-skills.py")
sync = subprocess.run(
    [sys.executable, str(generator)],
    text=True, capture_output=True, check=False,
)
assert sync.returncode == 0, sync.stdout + sync.stderr

for command, target in routes["commands"].items():
    assert target.count(".") == 1, f"{command}: malformed route {target}"
    workflow, subcommand = target.split(".")
    assert subcommand in routes["workflows"][workflow]["subcommands"], f"{command}: invalid target {target}"
    procedure = routes["workflows"][workflow]["subcommands"][subcommand]
    canonical_name = Path(procedure).stem
    assert canonical_name in canonical_commands
    assert (skills_root / canonical_name / "SKILL.md").is_file(), (
        f"{command}: route does not resolve to first-class skill {canonical_name}"
    )

command_route_count = len(routes["commands"])
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
route_schema = schema["definitions"]["codex_model_route"]
assert route_schema["properties"]["tier"]["enum"] == ["spark", "terra", "sol", "astra"]
astra_efforts = ["low", "medium", "high", "xhigh", "max", "ultra"]
assert route_schema["properties"]["effort"]["enum"] == astra_efforts
for effort in astra_efforts:
    configured = json.loads(json.dumps(settings))
    configured["meta_dev"]["codex"]["models"]["execute"] = {"tier": "astra", "effort": effort}
    jsonschema.validate(configured, schema)
assert not jsonschema.Draft7Validator(route_schema).is_valid({"tier": "astra", "effort": "none"})
assert set(codex_schema["properties"]["models"]["properties"]) == set(routes["models"])
for route in routes["models"].values():
    assert route["tier"] in schema["definitions"]["codex_model_route"]["properties"]["tier"]["enum"]
    assert route["effort"] in schema["definitions"]["codex_model_route"]["properties"]["effort"]["enum"]
runner = require_file("scripts/codex-headless-exec").read_text(encoding="utf-8")
for model in ("gpt-5.3-codex-spark", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-astra"):
    assert model in runner, f"Codex runner no longer supports configured model {model}"

hooks = load_json(plugin_root / "hooks/hooks.json")
assert set(hooks["hooks"]) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
adapter = require_file("hooks/scripts/codex-adapter.py")
adapter_text = adapter.read_text(encoding="utf-8")
compile(adapter_text, str(adapter), "exec")
for event, entries in hooks["hooks"].items():
    assert entries and entries[0]["hooks"], f"{event}: missing adapter hook"
    hook = entries[0]["hooks"][0]
    assert hook["type"] == "command"
    assert hook["command"] == 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/codex-adapter.py"'
    assert hook["timeout"] in {15, 20}
for marker in ("def main()", "PreToolUse", "PostToolUse", "SessionStart", "UserPromptSubmit", "Stop"):
    assert marker in adapter_text, f"Codex adapter missing {marker}"

plan_schema = load_json(require_file("schemas/plan-artifact.schema.json"))
assert plan_schema["properties"]["version"]["enum"] == ["1.0", "1.1"]
renderer = require_file("scripts/plan-artifact-render.py").read_text(encoding="utf-8")
assert 'VERSIONS = {"1.0", "1.1"}' in renderer and "--validate" in renderer
plan_skill = require_file("skills/plan/SKILL.md").read_text(encoding="utf-8")
assert "version `1.1`, `single-file`" in plan_skill
assert "Do not implement the plan" in plan_skill
plan_contract = require_file("references/codex-writing-plans.md").read_text(encoding="utf-8")
for marker in (
    "skilled implementation agent that has no conversation history",
    "plans/<repo>/YYYY-MM-DD-descriptive-kebab-case.md",
    "No-placeholder rule",
    "Fresh-agent test",
):
    assert marker in plan_contract, f"Codex writing-plans bridge missing {marker!r}"

portability = require_file("tests/test_runtime_portability.py").read_text(encoding="utf-8")
for marker in (
    "SCAN_DIRS = (\"commands\", \"references\", \"skills\", \"workflow-skills\", \"scripts\")",
    "PROVENANCE_ALLOWLIST",
    "SKIP_PATHS",
    "FORBIDDEN = (",
    '"360-" + "hextile"',
    '"p" + "hong"',
    '"~/" + ".codex"',
    '"~/" + ".claude"',
    "test_packaged_runtime_assets_are_host_neutral",
):
    assert marker in portability, f"portability scan contract missing {marker!r}"

marketplace = json.loads((repo_root / ".agents/plugins/marketplace.json").read_text())
entry = next(item for item in marketplace["plugins"] if item["name"] == "meta-dev")
assert entry["source"] == {"source": "local", "path": "./plugins/meta-dev"}
assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
assert entry["category"] == "Productivity"

# Exercise Codex's real local marketplace reader against a copied package. The
# isolated HOME/CODEX_HOME makes this an ingestion check, not a user-config or
# network operation. It is optional for environments without the Codex binary.
codex_cli = shutil.which("codex")
if codex_cli:
    with tempfile.TemporaryDirectory(prefix="meta-dev-codex-package-") as temporary:
        home = Path(temporary) / "home"
        (home / ".agents/plugins").mkdir(parents=True)
        (home / ".codex").mkdir()
        shutil.copytree(plugin_root, home / "plugins/meta-dev")
        shutil.copy2(repo_root / ".agents/plugins/marketplace.json", home / ".agents/plugins/marketplace.json")
        environment = dict(os.environ, HOME=str(home), CODEX_HOME=str(home / ".codex"))
        result = subprocess.run(
            [codex_cli, "plugin", "list", "--available", "--json"],
            env=environment, text=True, capture_output=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        listed = json.loads(result.stdout)
        available = next(item for item in listed["available"] if item["pluginId"] == "meta-dev@meta-dev")
        assert available["version"] == codex["version"]
        assert available["source"] == {"source": "local", "path": str(home / "plugins/meta-dev")}

        install = subprocess.run(
            [codex_cli, "plugin", "add", "meta-dev@meta-dev", "--json"],
            env=environment, text=True, capture_output=True, check=False,
        )
        assert install.returncode == 0, install.stdout + install.stderr
        prompt = subprocess.run(
            [codex_cli, "debug", "prompt-input", "$meta-dev:meta-planner test"],
            cwd=repo_root, env=environment, text=True, capture_output=True, check=False,
        )
        assert prompt.returncode == 0, prompt.stdout + prompt.stderr
        for marker in (
            "meta-dev:meta-planner",
            "skills/meta-planner/SKILL.md",
            "Run meta-planner in Codex",
        ):
            assert marker in prompt.stdout, f"installed selector omitted {marker!r}"
else:
    print("SKIP: Codex CLI unavailable; local package ingestion was not exercised")

print(
    "PASS: native Codex package "
    f"({len(canonical_commands)} commands, {len(helper_only)} helpers, "
    f"{command_route_count} routes, {discovery_bytes} discovery bytes)"
)
PY
