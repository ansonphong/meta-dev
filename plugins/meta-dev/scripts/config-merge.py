#!/usr/bin/env python3
"""Merge 3-layer config cascade: defaults -> project -> local. Output merged JSON."""
import json
import os
import subprocess
import sys
from pathlib import Path


def plugin_root() -> Path:
    """Resolve plugin assets without depending on the caller's cwd."""
    configured = (
        os.environ.get("META_DEV_PLUGIN_ROOT")
        or os.environ.get("PLUGIN_ROOT")
        or os.environ.get("CLAUDE_PLUGIN_ROOT")
    )
    return Path(configured).resolve() if configured else Path(__file__).resolve().parents[1]


PLUGIN_ROOT = plugin_root()


def project_root(plugin: Path) -> Path:
    """Use the topology contract instead of the caller's ambient directory."""
    try:
        result = subprocess.run(
            [sys.executable, str(plugin / "scripts" / "lib" / "repo-topology.py"), "--root"],
            capture_output=True, text=True, check=False, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


PROJECT_ROOT = project_root(PLUGIN_ROOT)
CASCADE = [
    str(PLUGIN_ROOT / "templates/settings.json"),
    str(PROJECT_ROOT / "plans" / "_dashboard" / "settings.json"),
    str(PROJECT_ROOT / "plans" / "_dashboard" / "settings.local.json"),
]


def deep_merge(base: dict, override: dict) -> dict:
    """Recursive dict merge. override wins on conflict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def main():
    merged: dict = {}
    for path in CASCADE:
        if os.path.exists(path):
            with open(path) as f:
                layer = json.load(f)
            merged = deep_merge(merged, layer)

    # Validate against schema if available
    schema_path = PLUGIN_ROOT / "schemas/settings.schema.json"
    if os.path.exists(schema_path):
        try:
            import jsonschema
        except ImportError:
            print("Warning: jsonschema not installed, skipping validation", file=sys.stderr)
        else:
            with open(schema_path, encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(merged, schema)

    json.dump(merged, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
