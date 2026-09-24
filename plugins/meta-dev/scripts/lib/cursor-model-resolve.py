#!/usr/bin/env python3
# ============================================================================
# cursor-model-resolve.py — map /cursor-execute aliases onto live
# `cursor-agent --list-models` catalog ids (verified 2026-09-12).
#
# Prints ONE id to stdout. Exit 2 on bad effort/family. Does not call the API.
#
# Usage:
#   cursor-model-resolve.py [--model ID] [--family grok] [--grok-version 4.6]
#       [--effort xhigh] [--fast] [--shape collect|ordinary|hard]
#       [--budget low|medium|high]
# ============================================================================
from __future__ import annotations

import argparse
import sys

FAMILIES = (
    "composer",
    "grok",
    "opus",
    "sol",
    "sonnet",
    "luna",
    "fable",
    "codex",
)

GROK_EFFORTS = ("low", "medium", "high", "xhigh")
SOL_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
OPUS_EFFORTS = ("low", "medium", "high", "xhigh", "max")
CODEX_EFFORTS = ("low", "high", "xhigh")


def _warn(msg: str) -> None:
    print(f"[WARN] cursor-model-resolve: {msg}", file=sys.stderr)


def _fast_suffix(fast: bool) -> str:
    return "-fast" if fast else ""


def _clamp(value: str, allowed: tuple[str, ...], fallback: str, label: str) -> str:
    if value in allowed:
        return value
    _warn(f"{label} has no '{value}' — using {fallback}")
    return fallback


def default_id(shape: str | None, budget: str | None, fast: bool) -> str:
    """Unspecified runs stay on the Cursor Models pool (Composer / Cursor Grok)."""
    shape = (shape or "").lower()
    budget = (budget or "").lower()
    if shape in ("collect", "mechanical") or budget == "low":
        return "composer-2.5" + _fast_suffix(fast)
    if shape == "hard" or budget == "high":
        return "cursor-grok-4.6-xhigh" + _fast_suffix(fast)
    return "cursor-grok-4.6-high" + _fast_suffix(fast)


def family_id(
    family: str,
    *,
    grok_version: str | None,
    effort: str | None,
    fast: bool,
) -> str:
    family = family.lower()
    effort = (effort or "").lower() or None
    grok_version = grok_version or "4.6"

    if family == "composer":
        if effort:
            _warn("Composer 2.5 has no effort in the catalog id — using standard/fast only")
        return "composer-2.5" + _fast_suffix(fast)

    if family == "grok":
        if grok_version not in ("4.5", "4.6", "4.7"):
            print(
                f"[ERROR] --grok version must be 4.5, 4.6, or 4.7 (got {grok_version})",
                file=sys.stderr,
            )
            sys.exit(2)
        eff = effort or "high"
        if grok_version == "4.5":
            eff = _clamp(eff, ("low", "medium", "high"), "high", "Cursor Grok 4.5")
            return f"cursor-grok-4.5-{eff}{_fast_suffix(fast)}"
        if grok_version == "4.6":
            eff = _clamp(eff, GROK_EFFORTS, "high", "Cursor Grok 4.6")
            return f"cursor-grok-4.6-{eff}{_fast_suffix(fast)}"
        # Live `cursor-agent --list-models` (2026-09-24): grok-4.7-<effort>,
        # not cursor-grok-4.7-<effort>.
        eff = _clamp(eff, GROK_EFFORTS, "high", "Cursor Grok 4.7")
        return f"grok-4.7-{eff}{_fast_suffix(fast)}"

    if family == "opus":
        eff = _clamp(effort or "high", OPUS_EFFORTS, "high", "Opus 5")
        return f"claude-opus-5-thinking-{eff}{_fast_suffix(fast)}"

    if family == "sol":
        eff = _clamp(effort or "high", SOL_EFFORTS, "high", "GPT-5.6 Sol")
        return f"gpt-5.6-sol-{eff}{_fast_suffix(fast)}"

    if family == "sonnet":
        eff = effort or "high"
        if eff not in ("high", "xhigh"):
            _warn(f"Sonnet 5 thinking catalog is high|xhigh — using high (got {eff})")
            eff = "high"
        # Live catalog has no -fast on sonnet-5 thinking ids.
        if fast:
            _warn("claude-sonnet-5-thinking has no -fast id — omitting --fast")
        return f"claude-sonnet-5-thinking-{eff}"

    if family == "luna":
        if effort and effort != "high":
            _warn("gpt-5.6-luna-high is the only Luna catalog id — ignoring --effort")
        if fast:
            _warn("gpt-5.6-luna-high has no -fast id — omitting --fast")
        return "gpt-5.6-luna-high"

    if family == "fable":
        eff = effort or "high"
        if eff not in ("high", "xhigh"):
            _warn(f"Fable 5 thinking catalog is high|xhigh — using high (got {eff})")
            eff = "high"
        if fast:
            _warn("claude-fable-5-thinking has no -fast id — omitting --fast")
        return f"claude-fable-5-thinking-{eff}"

    if family == "codex":
        if not effort:
            return "gpt-5.3-codex" + _fast_suffix(fast)
        eff = _clamp(effort, CODEX_EFFORTS, "high", "GPT-5.3 Codex")
        if eff == "low":
            return "gpt-5.3-codex-low" + _fast_suffix(fast)
        return f"gpt-5.3-codex-{eff}{_fast_suffix(fast)}"

    print(f"[ERROR] unknown --family '{family}'", file=sys.stderr)
    sys.exit(2)


def expand_model(model: str, *, effort: str | None, fast: bool) -> str:
    """Pass catalog ids through; expand informal names."""
    raw = model.strip()
    key = raw.lower()

    aliases = {
        "composer": "composer",
        "composer-2.5": "composer",
        "opus": "opus",
        "sonnet": "sonnet",
        "sol": "sol",
        "luna": "luna",
        "fable": "fable",
        "codex": "codex",
        "grok": "grok",
        "grok-4.7": "grok",
        "cursor-grok-4.7": "grok",
        "grok-4.6": "grok",
        "cursor-grok-4.6": "grok",
        "grok-4.5": "grok",
        "cursor-grok-4.5": "grok",
    }
    if key in aliases:
        ver = None
        if "4.7" in key:
            ver = "4.7"
        elif "4.5" in key:
            ver = "4.5"
        elif "4.6" in key or key in ("grok",):
            ver = "4.6"
        return family_id(
            aliases[key], grok_version=ver, effort=effort, fast=fast
        )

    if fast and not key.endswith("-fast"):
        return f"{raw}-fast"
    return raw


def apply_context(model: str, context: str | None) -> str:
    """500k is opt-in for Cursor Grok 4.7. Omitted context stays the 256k id."""
    if context is None or context == "" or context == "256k":
        return model
    if context != "500k":
        print(
            f"[ERROR] --context must be 256k or 500k (got {context})",
            file=sys.stderr,
        )
        sys.exit(2)
    if "[context=500k" in model:
        return model
    fast = model.endswith("-fast")
    base = model[: -len("-fast")] if fast else model
    prefix = "grok-4.7-"
    if not base.startswith(prefix) or base[len(prefix):] not in GROK_EFFORTS:
        print(
            "[ERROR] --context 500k is only for Cursor Grok 4.7 "
            f"(got {model})",
            file=sys.stderr,
        )
        sys.exit(2)
    effort = base[len(prefix):]
    flag = "true" if fast else "false"
    return f"grok-4.7[context=500k,effort={effort},fast={flag}]"


def resolve(
    *,
    model: str | None = None,
    family: str | None = None,
    grok_version: str | None = None,
    effort: str | None = None,
    fast: bool = False,
    shape: str | None = None,
    budget: str | None = None,
    context: str | None = None,
) -> str:
    if model:
        chosen = expand_model(model, effort=effort, fast=fast)
    elif family:
        chosen = family_id(
            family, grok_version=grok_version, effort=effort, fast=fast
        )
    else:
        chosen = default_id(shape, budget, fast)
    return apply_context(chosen, context)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a Cursor catalog model id")
    parser.add_argument("--model")
    parser.add_argument("--family", choices=FAMILIES)
    parser.add_argument("--grok-version", default=None)
    parser.add_argument("--effort")
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--shape", choices=("collect", "mechanical", "ordinary", "hard"))
    parser.add_argument("--budget", choices=("low", "medium", "high", "auto"))
    parser.add_argument("--context", choices=("256k", "500k"))
    args = parser.parse_args()
    budget = args.budget if args.budget != "auto" else "medium"
    print(
        resolve(
            model=args.model,
            family=args.family,
            grok_version=args.grok_version,
            effort=args.effort,
            fast=args.fast,
            shape=args.shape,
            budget=budget,
            context=args.context,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
