#!/usr/bin/env python3
"""Batch review results renderer. Reads JSON from stdin, prints one card.

Uses the ONE card standard — the open-right chassis in references/status-cards.md
(CARD_W = 74). The old hand-drawn 80-col ``╔═╗`` banner (whose right border never
lined up) and its trailing ``══`` rule are gone.
"""
import json
import os
import sys

# ── shared render primitives — ONE source (planctl.render_lib) ────────────────
# planctl/ is a sibling package inside scripts/, so scripts/ is what goes on the
# path. There is deliberately NO try/except fallback: a silent inline copy is
# exactly how renderers drift from render_lib while appearing to import it. A
# missing module must fail loudly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from planctl.render_lib import (
    CARD_FIELD,
    mark,
    clip,
    card_top, card_sep, card_row, card_bottom,
)


DIMENSIONS = ("correctness", "safety", "patterns", "coverage", "scope")


def validate(data):
    """Reject incomplete evidence before a review can be reported as accepted."""
    single = isinstance(data, dict) and "reviews" not in data and "verdict" in data
    items = [data] if single else data.get("reviews") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("reviews must be a nonempty array")
    for number, item in enumerate(items, 1):
        label = f"review {number}"
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")
        for field in (("summary",) if single else ("target", "summary")):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"{label}: {field} is required")
        verdict = item.get("verdict")
        if verdict not in ("PASS", "CONDITIONAL_PASS", "FAIL"):
            raise ValueError(f"{label}: invalid verdict")
        confidence = item.get("confidence")
        if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
            raise ValueError(f"{label}: confidence must be between 0 and 1")
        if item.get("blast_radius") not in (
            "isolated", "file", "module", "cross-cutting", "dependency-graph"
        ):
            raise ValueError(f"{label}: invalid blast_radius")
        dimensions = item.get("dimensions")
        if not isinstance(dimensions, dict) or any(
            dimensions.get(name) not in ("PASS", "NEEDS_FIX", "NEEDS_REVIEW")
            for name in DIMENSIONS
        ):
            raise ValueError(f"{label}: all five dimensions need a score")
        issues = item.get("issues")
        if not isinstance(issues, list):
            raise ValueError(f"{label}: issues must be an array")
        if verdict == "PASS" and (issues or any(dimensions[name] != "PASS" for name in DIMENSIONS)):
            raise ValueError(f"{label}: PASS requires no issues and five PASS scores")
        if issues and all(dimensions[name] == "PASS" for name in DIMENSIONS):
            raise ValueError(f"{label}: findings require a non-PASS dimension")
        if verdict != "PASS" and not issues and all(dimensions[name] == "PASS" for name in DIMENSIONS):
            raise ValueError(f"{label}: non-PASS needs findings or incomplete dimensions")
        if verdict == "CONDITIONAL_PASS" and any(
            isinstance(issue, dict) and issue.get("severity") in ("critical", "high")
            for issue in issues
        ):
            raise ValueError(f"{label}: critical/high issues require FAIL")
        for index, issue in enumerate(issues, 1):
            name = f"{label} issue {index}"
            if not isinstance(issue, dict):
                raise ValueError(f"{name} must be an object")
            if issue.get("severity") not in ("critical", "high", "medium", "low"):
                raise ValueError(f"{name}: invalid severity")
            if type(issue.get("line")) is not int or issue["line"] < 1:
                raise ValueError(f"{name}: positive line is required")
            for field in ("file", "title", "description", "failure_path",
                          "violated_requirement", "missing_evidence", "suggested_fix"):
                if not isinstance(issue.get(field), str) or not issue[field].strip():
                    raise ValueError(f"{name}: {field} is required")


def render(data):
    if not isinstance(data, dict) or "reviews" not in data:
        raise ValueError("render input must contain reviews")
    validate(data)
    items = data.get("reviews", [])
    passed = [i for i in items if i.get("verdict") == "PASS"]
    failed = [i for i in items if i.get("verdict") != "PASS"]
    critical = sum(iss["severity"] in ("critical", "high") for i in items for iss in i["issues"])

    lines = [card_top("Batch Review Results")]
    lines.append(card_row(
        f"Total: {len(items)}  ·  Pass: {len(passed)}  ·  Fail: {len(failed)}"
        f"  ·  Critical issues: {critical}"
    ))
    if failed:
        lines.append(card_sep("Failures"))
        for item in failed:
            lines.append(card_row(clip(
                f"{mark('blocked')} {item.get('target','?')} — {item.get('verdict','?')}"
                f" (confidence: {item.get('confidence',0)})"
            )))
    if passed:
        lines.append(card_sep("Passed"))
        for item in passed:
            lines.append(card_row(clip(f"{mark('done')} {item.get('target','?')}")))
    lines.append(card_bottom())
    if any(item["issues"] for item in items):
        lines.extend(("", "Findings:"))
        for item in items:
            for issue in item["issues"]:
                lines.extend((
                    f"- {item['target']}: [{issue['severity'].upper()}] {issue['title']} — {issue['file']}:{issue['line']}",
                    f"  Failure path: {issue['failure_path']}",
                    f"  Requirement: {issue['violated_requirement']}",
                    f"  Missing evidence: {issue['missing_evidence']}",
                    f"  Evidence and impact: {issue['description']}",
                    f"  Suggested fix: {issue['suggested_fix']}",
                ))
    return "\n".join(lines)

if __name__ == "__main__":
    try:
        if sys.argv[1:] not in ([], ["--validate-only"]):
            raise ValueError("usage: review-batch-render.py [--validate-only]")
        data = json.load(sys.stdin)
        if sys.argv[1:]:
            validate(data)
        else:
            print(render(data))
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"review-batch-render: {exc}", file=sys.stderr)
        sys.exit(2)
