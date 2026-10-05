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
from planctl.review_evidence import validate_verdict


def render(data):
    if not isinstance(data, dict) or "reviews" not in data:
        raise ValueError("render input must contain reviews")
    validate_verdict(data)
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
            validate_verdict(data)
        else:
            print(render(data))
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"review-batch-render: {exc}", file=sys.stderr)
        sys.exit(2)
