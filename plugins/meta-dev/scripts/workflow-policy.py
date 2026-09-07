#!/usr/bin/env python3
"""Resolve a bounded workflow from the shared settings cascade; never dispatch work."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path


def load_settings(project_root=None):
    spec = importlib.util.spec_from_file_location(
        "meta_dev_config", Path(__file__).with_name("config-merge.py")
    )
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    root = Path(project_root).resolve() if project_root else config.PROJECT_ROOT
    paths = [config.PLUGIN_ROOT / "templates/settings.json",
             root / "plans/_dashboard/settings.json",
             root / "plans/_dashboard/settings.local.json"]
    merged = {}
    for path in paths:
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                layer = json.load(handle)
            if not isinstance(layer, dict):
                raise ValueError(f"settings layer must be an object: {path}")
            merged = config.deep_merge(merged, layer)
    try:
        import jsonschema
    except ImportError:
        pass  # resolve_policy also validates every field it consumes.
    else:
        with (config.PLUGIN_ROOT / "schemas/settings.schema.json").open(encoding="utf-8") as handle:
            jsonschema.validate(merged, json.load(handle))
    return merged


def choice(value, allowed, name):
    if value not in allowed:
        raise ValueError(f"{name} must be one of {', '.join(allowed)}")
    return value


def bound(value, minimum, maximum, name):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def normalize_risk(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("risk labels must be nonempty strings")
    label = value.strip().lower().replace("_", "-").replace("/", "-")
    # Keep the classifier's labels and plan-target terminology interoperable.
    return {
        "security-boundary": "security", "crypto": "security",
        "licensing": "security", "license": "security",
        "schema-drift": "migration", "schema": "migration", "migrations": "migration",
        "money-path": "payments", "payment": "payments",
        "cross-repo": "cross-service", "cross-repository": "cross-service",
    }.get(label, label)


def resolve_policy(settings, *, host="unknown", model=None, target=None, risks=(),
                   granularity=None, research=None, harden=None, cross_family=None,
                   available_workers=None):
    meta = settings["meta_dev"]
    policy = meta["workflow"]
    host = host.strip().lower()
    source = "explicit" if model else "fallback"
    if not model:
        model = policy.get("host_execute_models", {}).get(host)
        if model:
            source = "workflow.host_execute_models"
        elif host == "codex":
            route = meta.get("codex", {}).get("models", {}).get("execute", {})
            model = route.get("model") or route.get("tier")
            if model:
                source = "codex.models.execute"
        if not model:
            model = meta.get("models", {}).get("stage_overrides", {}).get("execute")
            if model:
                source = "models.stage_overrides.execute"
        if not model:
            model = meta.get("models", {}).get("default_model")
            if model:
                source = "models.default_model"
    model = (model or "unknown").strip().lower()
    aliases = policy.get("model_aliases", {})
    seen = set()
    while model in aliases:
        if model in seen:
            raise ValueError("model_aliases contains a cycle")
        seen.add(model)
        model = aliases[model]
    profiles = policy.get("model_profiles", {})
    known = model in profiles
    profile = profiles.get(model, {"plan_target": "standard", "coherent_slices": False})
    profile_target = choice(profile["plan_target"], ("lean", "standard", "explicit"), "profile target")
    if type(profile["coherent_slices"]) is not bool:
        raise ValueError("coherent_slices must be boolean")
    target = choice(target or policy["plan_target"], ("auto", "lean", "standard", "explicit"), "target")
    target = profile_target if target == "auto" else target
    # Built-in safety floors cannot be removed by replacing the configured list.
    sensitive = {"auth", "authorization", "security", "payments", "migration",
                 "cross-service", "release-stability", "destructive", "high", "critical"}
    configured_risks = policy.get("sensitive_risks", [])
    if not isinstance(configured_risks, list):
        raise ValueError("sensitive_risks must be an array")
    sensitive.update(normalize_risk(risk) for risk in configured_risks)
    normalized_risks = {normalize_risk(risk) for risk in risks}
    triggers = sorted(normalized_risks & sensitive)
    if triggers and target == "lean":
        target = "standard"
    granularity = choice(granularity or policy["execution_granularity"], ("auto", "task", "slice"), "granularity")
    if granularity == "auto":
        granularity = "slice" if profile["coherent_slices"] and not triggers else "task"
    # Risk-sensitive work keeps task boundaries even when a slice was requested.
    if triggers:
        granularity = "task"
    research = choice(research or policy["research_depth"], ("auto", "focused", "full"), "research")
    harden = choice(harden or policy["hardening_depth"], ("auto", "focused", "full"), "harden")
    research = ("full" if triggers else "focused") if research == "auto" else research
    harden = ("full" if triggers else "focused") if harden == "auto" else harden
    parallel = bound(policy["max_parallel_workers"], 1, 8, "max_parallel_workers")
    if available_workers is not None:
        parallel = min(parallel, bound(available_workers, 1, 1024, "available_workers"))
    slice_size = bound(policy["max_tasks_per_slice"], 1, 6, "max_tasks_per_slice")
    focused = bound(policy["focused_max_reviewers"], 1, 4, "focused_max_reviewers")
    full = bound(policy["full_max_reviewers"], 1, 8, "full_max_reviewers")
    rounds = bound(policy["max_review_rounds"], 1, 5, "max_review_rounds")
    cross_family = policy["cross_family_review"] if cross_family is None else cross_family
    if type(cross_family) is not bool:
        raise ValueError("cross_family_review must be boolean")
    capabilities = policy.get("host_capabilities", {}).get(host, {})
    for value in capabilities.values():
        if type(value) is not bool:
            raise ValueError("host capabilities must be boolean")
    return {
        "executor": {"host": host, "model": model, "source": source,
                     "profile": model if known else "unknown"},
        "plan_target": target,
        "execution": {"granularity": granularity,
                      "max_tasks_per_slice": slice_size if granularity == "slice" else 1,
                      "max_parallel_workers": parallel},
        "research": {"depth": research, "max_reviewers": min(parallel, full if research == "full" else focused)},
        "hardening": {"depth": harden, "max_reviewers": min(parallel, full if harden == "full" else focused),
                      "max_rounds": rounds},
        "review": {"cross_family": cross_family},
        "capabilities": {"async_tools": capabilities.get("async_tools", False),
                         "dynamic_effort": capabilities.get("dynamic_effort", False)},
        "risk_overrides": triggers,
        "invariants": ["security_checks", "permission_boundaries", "scoped_ownership",
                       "per_task_verification", "planctl_state_writes", "independent_final_review"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="unknown")
    parser.add_argument("--model")
    parser.add_argument("--target", choices=["lean", "standard", "explicit"])
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--project-root")
    parser.add_argument("--granularity", choices=["auto", "task", "slice"])
    parser.add_argument("--research", choices=["auto", "focused", "full"])
    parser.add_argument("--harden", choices=["auto", "focused", "full"])
    parser.add_argument("--cross-family", action="store_true", default=None)
    parser.add_argument("--available-workers", type=int)
    args = parser.parse_args()
    try:
        settings = load_settings(args.project_root)
        result = resolve_policy(settings, host=args.host, model=args.model, target=args.target,
                                risks=args.risk, granularity=args.granularity, research=args.research,
                                harden=args.harden, cross_family=args.cross_family,
                                available_workers=args.available_workers)
    except Exception as exc:
        print(f"workflow-policy: invalid configuration: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
