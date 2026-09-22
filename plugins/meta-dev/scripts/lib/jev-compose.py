"""Pure compose of keyword budget, risk tags, and Jev answers.

Risk tags money-path, security-boundary, and schema-drift force high / HITL.
Fail-open keeps the keyword budget and leaves the extra-family suggestion absent.
"""

from __future__ import annotations

FORCE_TAGS = ("money-path", "security-boundary", "schema-drift")
BUDGETS = ("low", "medium", "high")


def _tags(risk_tags):
    if not risk_tags or risk_tags.strip() == "none":
        return []
    return [part.strip() for part in risk_tags.split(",") if part.strip() and part.strip() != "none"]


def _choice(answers, key):
    item = answers.get(key) if isinstance(answers, dict) else None
    if not isinstance(item, dict):
        return None, 0.0
    if item.get("type") != "choice":
        return None, 0.0
    try:
        confidence = float(item.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    choice = item.get("choice")
    return (choice if isinstance(choice, str) else None), confidence


def _noul(answers, key):
    item = answers.get(key) if isinstance(answers, dict) else None
    if not isinstance(item, dict) or item.get("type") != "noul":
        return None
    try:
        return float(item.get("noul"))
    except (TypeError, ValueError):
        return None


def compose(keyword_budget, risk_tags, answers, *, fail_open=False, user_budget=None):
    tags = _tags(risk_tags)
    forced = any(tag in FORCE_TAGS for tag in tags)
    budget = keyword_budget if keyword_budget in BUDGETS else "medium"
    result = {
        "budget": budget,
        "rung": None,
        "extra_family_skip": None,
        "hotl": None,
        "fail_open": bool(fail_open),
        "risk_tags": tags or ["none"],
    }
    if user_budget in BUDGETS:
        result["budget"] = user_budget
    if forced:
        result["budget"] = "high"
        result["hotl"] = False
        result["extra_family_skip"] = False
        result["fail_open"] = bool(fail_open)
        return result
    if fail_open or not isinstance(answers, dict):
        return result

    jev_budget, budget_confidence = _choice(answers, "budget")
    if jev_budget in BUDGETS and budget_confidence >= 0.6 and user_budget not in BUDGETS:
        result["budget"] = jev_budget

    rung, rung_confidence = _choice(answers, "rung")
    if rung and rung_confidence >= 0.6:
        result["rung"] = rung

    hotl = _noul(answers, "hotl")
    if hotl is not None:
        result["hotl"] = hotl > 0.5

    cross = _noul(answers, "needs_cross_family")
    if cross is not None:
        result["extra_family_skip"] = cross < 0.5
    return result
