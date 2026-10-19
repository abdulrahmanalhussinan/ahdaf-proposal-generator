"""The team's celebrity / influencer list: importing sheets and picking candidates for a proposal.

Proposals only ever name people who are in this list, with the follower numbers written in it."""
from __future__ import annotations

import re

from app.core.arabic import normalize
from app.data import repositories as repo
from app.generator.knowledge.places import mentioned_cities
from app.services import files

WANT_WORDS = ("مشاهير", "مشهور", "مؤثر", "انفلونسر", "انفلونسرز", "بلوقر", "بلوقرز", "سناب شات", "influencer", "celebrit", "ugc", "صناع المحتوى", "صانع محتوى")
CELEB_TYPES = {"influencer", "campaign", "event", "exhibition", "social_media", "pr"}

# sector key -> words that make a person's category relevant
SECTOR_HINTS = {
    "food_beverage": ["اكل", "طبخ", "مطاعم", "قهوه", "فود", "food", "طعام", "حلويات"],
    "retail": ["تسوق", "موضه", "ازياء", "ستايل", "عروض", "fashion", "lifestyle", "لايف ستايل", "جمال"],
    "automotive": ["سيارات", "سياره", "car", "auto", "تعديل", "مزادات", "رالي"],
    "real_estate": ["عقار", "ديكور", "تصميم داخلي", "بيت", "منزل", "lifestyle", "لايف ستايل"],
    "healthcare": ["صحه", "طبيب", "دكتور", "رياضه", "لياقه", "fitness", "تغذيه"],
    "fashion_beauty": ["جمال", "مكياج", "عنايه", "beauty", "makeup", "بشره", "موضه", "ازياء", "fashion", "ستايل"],
    "hospitality": ["سفر", "سياحه", "travel", "رحلات", "مغامره", "طبيعه"],
    "education": ["تعليم", "تطوير", "طلاب", "معرفه", "education"],
    "technology": ["تقنيه", "تك", "tech", "جوالات", "العاب", "gaming", "قيمنق"],
    "entertainment": ["ترفيه", "كوميدي", "فن", "comedy", "entertainment", "موسيقى"],
    "sports": ["رياضه", "كوره", "sport", "football", "لياقه"],
}


def import_file(filename: str, data: bytes) -> dict:
    people = files.parse_celebrity_sheet(filename, data)
    res = repo.celebrities.add_many(people, source=filename or "شيت")
    return {**res, "found": len(people), "total": repo.celebrities.count(), "source": filename}


def overview(q: str = "") -> dict:
    return {"items": repo.celebrities.list(q), "total": repo.celebrities.count(), "sources": repo.celebrities.sources()}


def _text_of(inputs: dict) -> str:
    p = inputs.get("project") or {}
    pr = inputs.get("preferences") or {}
    return " ".join(str(x or "") for x in (p.get("name"), p.get("description"), p.get("location"), pr.get("requirements"),
                                             p.get("audience_other"), (inputs.get("goals") or {}).get("objectives")))


def wanted(inputs: dict, type_key: str) -> bool:
    mode = (inputs.get("preferences") or {}).get("celebrities", "auto")
    if mode == "no" or repo.celebrities.count() == 0:
        return False
    if mode == "yes":
        return True
    text = normalize(_text_of(inputs))
    types = set((inputs.get("project") or {}).get("types") or []) | {type_key}
    return "influencer" in types or any(normalize(w) in text for w in WANT_WORDS) or (
        type_key in CELEB_TYPES and "influencer_marketing" in ((inputs.get("services") or {}).get("selected") or []))


def candidates(inputs: dict, sector_key: str, platform_labels: list[str], limit: int = 150) -> list[dict]:
    """People from the list ranked by fit (city named in the brief, sector, platforms), best first."""
    people = repo.celebrities.list()
    if not people:
        return []
    cities = [normalize(c) for c in mentioned_cities(_text_of(inputs))]
    hints = [normalize(h) for h in SECTOR_HINTS.get(sector_key, [])]
    plats = [normalize(p) for p in platform_labels]
    brief = normalize(_text_of(inputs))
    scored = []
    for i, p in enumerate(people):
        blob = normalize(" ".join(str(p.get(k) or "") for k in ("category", "city", "notes", "platforms")) + " " +
                         " ".join(map(str, (p.get("extra") or {}).values())))
        s = 0.0
        if cities and any(c in blob for c in cities):
            s += 5
        s += 2 * sum(1 for h in hints if h and h in blob)
        s += sum(1 for pl in plats if pl and pl in blob)
        cat = normalize(p.get("category") or "")
        if cat and any(w in brief for w in re.split(r"[\s،,/]+", cat) if len(w) >= 4):
            s += 2
        scored.append((-s, i, p))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [p for _, _, p in scored[:limit]]


def find(name: str, pool: list[dict]) -> dict | None:
    """The list entry a model-chosen name refers to (exact, then forgiving match). None = not in the list."""
    n = normalize(re.sub(r"[«»\"'@]", "", name or ""))
    if not n:
        return None
    for p in pool:
        if normalize(p["name"]) == n:
            return p
    for p in pool:
        pn = normalize(p["name"])
        if len(n) >= 4 and (n in pn or pn in n):
            return p
        if p.get("handle") and normalize(p["handle"]).lstrip("@") in (n, n.lstrip("@")):
            return p
    return None
