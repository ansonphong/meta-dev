#!/usr/bin/env python3
"""Batch review results renderer. Reads JSON from stdin. ≤100 cols."""
import json, sys

def render(data):
    items = data.get("reviews", [])
    passed = [i for i in items if i.get("verdict") == "PASS"]
    failed = [i for i in items if i.get("verdict") != "PASS"]
    critical = sum(len(i.get("issues", [])) for i in items if any(iss.get("severity") in ("critical","high") for iss in i.get("issues",[])))

    lines = []
    lines.append("╔══════════════════════════════════════════════════════════════════════════════╗")
    lines.append("║                         Batch Review Results                               ║")
    lines.append("╚══════════════════════════════════════════════════════════════════════════════╝")
    lines.append("")
    lines.append(f"  Total: {len(items)}  |  Pass: {len(passed)}  |  Fail: {len(failed)}  |  Critical issues: {critical}")
    lines.append("")
    if failed:
        lines.append("  ── Failures ──")
        for item in failed:
            lines.append(f"  ❌ {item.get('target','?')} — {item.get('verdict','?')} (confidence: {item.get('confidence',0)})")
            for issue in item.get("issues", [])[:3]:
                lines.append(f"     • [{issue.get('severity','?').upper()}] {issue.get('title','?')} — {issue.get('file','?')}:{issue.get('line','?')}")
            if len(item.get("issues", [])) > 3:
                lines.append(f"     ... and {len(item['issues'])-3} more issues")
            lines.append("")
    if passed:
        lines.append("  ── Passed ──")
        for item in passed:
            lines.append(f"  ✅ {item.get('target','?')}")
        lines.append("")
    lines.append("  ══════════════════════════════════════════════════════════════════════════════")
    return "\n".join(lines)

if __name__ == "__main__":
    data = json.load(sys.stdin) if not sys.argv[1:] else {"reviews":[]}
    print(render(data))
