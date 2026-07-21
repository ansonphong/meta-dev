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

def render(data):
    items = data.get("reviews", [])
    passed = [i for i in items if i.get("verdict") == "PASS"]
    failed = [i for i in items if i.get("verdict") != "PASS"]
    critical = sum(len(i.get("issues", [])) for i in items if any(iss.get("severity") in ("critical","high") for iss in i.get("issues",[])))

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
            for issue in item.get("issues", [])[:3]:
                lines.append(card_row(clip(
                    f"   • [{issue.get('severity','?').upper()}] {issue.get('title','?')}"
                    f" — {issue.get('file','?')}:{issue.get('line','?')}"
                )))
            if len(item.get("issues", [])) > 3:
                lines.append(card_row(f"   … and {len(item['issues'])-3} more issues"))
    if passed:
        lines.append(card_sep("Passed"))
        for item in passed:
            lines.append(card_row(clip(f"{mark('done')} {item.get('target','?')}")))
    lines.append(card_bottom())
    return "\n".join(lines)

if __name__ == "__main__":
    data = json.load(sys.stdin) if not sys.argv[1:] else {"reviews":[]}
    print(render(data))
