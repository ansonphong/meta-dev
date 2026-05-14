#!/usr/bin/env python3
"""Merge 3-layer config cascade: defaults -> project -> local. Output merged JSON."""
import json
import os
import sys

CASCADE = [
    os.environ.get("CLAUDE_PLUGIN_ROOT", ".") + "/templates/settings.json",
    "plans/_dashboard/settings.json",
    "plans/_dashboard/settings.local.json",
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
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", ".")
    schema_path = plugin_root + "/schemas/settings.schema.json"
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
