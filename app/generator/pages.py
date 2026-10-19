"""Sizing a proposal to the number of pages the team asked for (preferences.pages).

Pages are laid out in the browser, so the server can only plan: it estimates how many pages each
section takes at each detail level, then picks the detail level, turns divider pages and the
optional extras on or off, and drops the least essential sections until the estimate fits. The
writer (Claude) also gets a page budget per section. The editor shows the real count afterwards and
can trim further («ملاءمة لعدد الصفحات»).
"""
from __future__ import annotations

# Estimated landscape pages per section at the medium detail level
WEIGHTS = {
    "about": 1.0, "intro": 1.0, "understanding": 1.5, "objectives": 1.0, "idea": 1.5, "activations": 1.6,
    "celebrities": 1.4, "content_plan": 2.0, "scope": 1.4, "methodology": 1.8, "deliverables": 1.4, "timeline": 1.4,
    "kpis": 1.3, "team": 1.0, "governance": 1.0, "assumptions": 0.8, "risks": 1.1, "budget": 0.6, "past_projects": 1.0,
    "conclusion": 1.0, "custom": 1.0,
}
DETAIL_FACTOR = {"brief": 0.72, "medium": 1.0, "advanced": 1.4}
DIVIDER_SECTIONS = 4
# Dropped first when the target is small; idea, activations, deliverables and conclusion always stay.
DROP_ORDER = ["about", "content_plan", "methodology", "kpis", "scope", "objectives", "understanding", "intro",
              "celebrities", "timeline"]
# Never padded with filler (team/governance/...): with room to spare the sections themselves grow.
ADD_ORDER = ["content_plan"]
MIN_PAGES, MAX_PAGES = 5, 80


def target_of(prefs: dict) -> int | None:
    try:
        n = int(prefs.get("pages") or 0)
    except (TypeError, ValueError):
        return None
    return n if MIN_PAGES <= n <= MAX_PAGES else None


def estimate(sections: list[str], detail: str, dividers: bool) -> float:
    body = sum(WEIGHTS.get(s, 1.0) for s in sections) * DETAIL_FACTOR[detail]
    fixed = 2 + (1 if len(sections) > 2 else 0) + (DIVIDER_SECTIONS if dividers else 0)  # cover, closing, contents
    return body + fixed


def plan(target: int, sections: list[str], optional_available: list[str]) -> dict:
    """Detail level, dividers and section list whose estimated size is closest to `target` pages."""
    sections = list(sections)
    dividers = target >= 18
    for detail in ("advanced", "medium", "brief"):
        if estimate(sections, detail, dividers) <= target + 0.5:
            break
    else:
        detail = "brief"
        dividers = False
        for sec in DROP_ORDER:
            if estimate(sections, detail, dividers) <= target + 0.5:
                break
            if sec in sections:
                sections.remove(sec)
    # room to spare: bring back the optional extras, then let sections grow
    added = []
    for sec in ADD_ORDER:
        if sec in optional_available and sec not in sections and estimate(sections + [sec], detail, dividers) <= target - 0.5:
            sections.insert(sections.index("conclusion") if "conclusion" in sections else len(sections), sec)
            added.append(sec)
    est = estimate(sections, detail, dividers)
    fixed = est - sum(WEIGHTS.get(s, 1.0) for s in sections) * DETAIL_FACTOR[detail]
    stretch = max(1.0, min(1.8, (target - fixed) / max(1.0, est - fixed)))
    per_section = {s: round(WEIGHTS.get(s, 1.0) * DETAIL_FACTOR[detail] * stretch, 1) for s in sections}
    return {"target": target, "detail": detail, "dividers": dividers, "sections": sections, "added": added,
            "stretch": round(stretch, 2), "per_section": per_section, "estimate": round(est * stretch - fixed * (stretch - 1))}
