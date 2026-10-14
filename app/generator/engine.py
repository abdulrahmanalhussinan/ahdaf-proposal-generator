"""Proposal generator.

`generate()` turns wizard inputs into a block-based proposal document.
`regenerate_section()` rebuilds one section with a new variation seed (and optionally another tone)
without touching the rest of the document.

Every section is composed from the analysis (type, sector, platforms, services, objectives,
duration, audience) — not from a fixed template — and information that was not provided is either
left as a visible placeholder `[[...]]` or phrased generally, never invented.
"""
from __future__ import annotations

import random
import re
import uuid
from datetime import date, timedelta

from app.core import arabic as ar
from app.generator import phrases as P
from app.generator.analyzer import DETAILS, TONES, Analysis, analyze
from app.generator.knowledge import ideas as I
from app.generator.knowledge.objectives import OBJECTIVES
from app.generator.knowledge.platforms import PLATFORMS
from app.generator.knowledge.project_types import PROJECT_TYPES
from app.generator.knowledge.services import CATEGORIES

SECTION_ORDER = ["about", "intro", "understanding", "objectives", "idea", "activations", "content_plan",
                 "scope", "methodology", "deliverables",
                 "timeline", "team", "kpis", "governance", "assumptions", "risks", "budget", "past_projects",
                 "conclusion"]

SECTION_TITLES = {
    "about": "عن أهداف", "intro": "المقدمة", "understanding": "فهمنا للمشروع", "objectives": "أهداف المشروع",
    "idea": "الفكرة الإبداعية", "activations": "أفكار تفعيلية مقترحة", "content_plan": "محاور المحتوى وخطة النشر",
    "scope": "نطاق العمل", "methodology": "منهجية وآلية التنفيذ", "deliverables": "المخرجات",
    "timeline": "الجدول الزمني", "team": "فريق العمل", "kpis": "مؤشرات الأداء", "governance": "الحوكمة وإدارة المشروع",
    "assumptions": "الافتراضات والمتطلبات", "risks": "المخاطر وآلية التعامل معها", "budget": "الإطار المالي",
    "past_projects": "أعمال ذات صلة", "conclusion": "الخاتمة",
}
SECTION_TITLES_EN = {
    "about": "About AHDAF", "intro": "Introduction", "understanding": "Our Understanding", "objectives": "Objectives",
    "idea": "Creative Idea", "activations": "Activation Ideas", "content_plan": "Content Plan",
    "scope": "Scope of Work", "methodology": "Methodology", "deliverables": "Deliverables", "timeline": "Timeline",
    "team": "Project Team", "kpis": "KPIs", "governance": "Governance", "assumptions": "Assumptions",
    "risks": "Risk Management", "budget": "Budget", "past_projects": "Related Work", "conclusion": "Conclusion",
}
DIVIDER_SECTIONS = {"understanding", "idea", "scope", "timeline", "governance"}
CONTENT_TYPES = {"social_media", "content", "campaign", "influencer", "digital_ads"}
DESIGNS = ("ahdaf", "night", "bold", "minimal")

DETAIL_CAPS = {
    "brief": {"activities": 2, "kpis": 4, "risks": 4, "assumptions": 5, "objectives": 3, "cards": 4, "team": 5,
              "responsibilities": 1, "timeline_rows": 1},
    "medium": {"activities": 3, "kpis": 6, "risks": 6, "assumptions": 7, "objectives": 5, "cards": 6, "team": 7,
               "responsibilities": 2, "timeline_rows": 2},
    "advanced": {"activities": 5, "kpis": 8, "risks": 8, "assumptions": 10, "objectives": 6, "cards": 8, "team": 9,
                 "responsibilities": 3, "timeline_rows": 3},
}

AR_TOKEN_ALIASES = {"العميل": "client", "المشروع": "project", "القطاع": "sector", "المدة": "duration",
                    "الجمهور": "audience", "الخدمات": "services_list", "نوع_المشروع": "type_label"}


def _id() -> str:
    return uuid.uuid4().hex[:10]


def blk(type_: str, **kw) -> dict:
    return {"id": _id(), "type": type_, **kw}


# =============================================================================== writer
class Writer:
    def __init__(self, a: Analysis, library: dict, settings: dict, seed: int, used: set[str] | None = None):
        self.a = a
        self.library = library
        self.settings = settings or {}
        self.seed = seed
        self.regen = 0  # 0 = first generation (canonical order); >0 = regenerated variation
        self.used: set[str] = set(used or ())
        self.caps = DETAIL_CAPS[a.detail]
        self.kpi_lib = {k["key"]: k for k in (library.get("kpis") or [])}
        self.role_lib = {r["key"]: r for r in (library.get("roles") or [])}
        self.ctx = self._build_ctx()

    # -------------------------------------------------------------- tokens
    def _build_ctx(self) -> dict:
        a = self.a
        client = a.client or "[[اسم العميل]]"
        project = a.project or "[[اسم المشروع]]"
        event_label = f"«{project}»" if a.event_noun in project else f"{a.event_noun} «{project}»"
        if a.type_key == "exhibition":
            event_label = f"في {a.event_noun} «{project}»" if a.event_noun not in project else f"في «{project}»"
        fem = a.client_gender == "f"
        ctx = {
            "client": client,
            "li_client": ar.li(a.client) if a.client else "للعميل",
            "bi_client": ar.bi(a.client) if a.client else "بالعلامة",
            # gender agreement with the client's head noun (شركة/مؤسسة… vs بنك/مستشفى…)
            "ha": "ها" if fem else "ه",
            "v": "ت" if fem else "ي",
            "sa": "ست" if fem else "سي",
            "kana": "كانت" if fem else "كان",
            "ready": "جاهزة" if fem else "جاهزًا",
            "yubal": "تُبلَّغ" if fem else "يُبلَّغ",
            "project": project,
            "platforms": ar.join(a.platform_labels) or "المنصات المعتمدة",
            "audience": a.audience_phrase,
            "sector": a.sector.get("name", "القطاع"),
            "duration": ar.duration_phrase(a.days),
            "duration_gen": ar.duration_phrase_gen(a.days),
            "event_label": event_label,
            "type_label": a.ptype["label"],
            "services_list": ar.join([s["title"] for s in a.services][:4]),
            "conversion_tail": f"، ثم يقودهم إلى {a.conversion}" if a.conversion else "",
        }
        ctx["nature"] = self.fill(a.ptype["nature"], ctx)
        ctx["nature_short"] = self.fill(a.ptype.get("nature_short") or a.ptype["nature"], ctx)
        objs = [ar.strip_end(o.title) for o in a.objectives][:3]
        ctx["objectives_list"] = ar.join(objs) if objs else "تحقيق أهداف المشروع"
        ctx["top_objective"] = objs[0] if objs else "أهدافه"
        ctx["approach_list"] = ar.join([x["title"] for x in a.ptype.get("approach", [])][:3])
        ctx["description"] = ar.sentence(a.description) if a.description else ""
        if a.start and a.end:
            ctx["date_range"] = f"، من {ar.fmt_date(a.start)} إلى {ar.fmt_date(a.end)}"
        else:
            ctx["date_range"] = ""
        return ctx

    def fill(self, template: str, ctx: dict | None = None, **extra) -> str:
        data = {**(ctx if ctx is not None else self.ctx), **extra}

        def rep(m):
            key = AR_TOKEN_ALIASES.get(m.group(1), m.group(1))
            return str(data[key]) if key in data else m.group(0)

        return re.sub(r"\{([\w؀-ۿ]+)\}", rep, template)

    # -------------------------------------------------------------- choice
    def rng(self, section: str, regen: int) -> random.Random:
        return random.Random(f"{self.seed}|{section}|{regen}")

    def choose(self, rng: random.Random, bank, tone: str | None = None, **extra) -> str:
        if isinstance(bank, dict):
            options = list(bank.get(tone or self.a.tone) or []) or list(bank.get("default") or [])
            if not options:
                for v in bank.values():
                    options.extend(v)
        else:
            options = list(bank)
        if not options:
            return ""
        rng.shuffle(options)
        for opt in options:
            text = self.fill(opt, **extra)
            if text not in self.used:
                self.used.add(text)
                return text
        text = self.fill(options[0], **extra)
        return text

    def note(self, text: str) -> str:
        self.used.add(text)
        return text

    def shuffled(self, rng: random.Random, items: list) -> list:
        """Canonical order on first generation; a different arrangement on each regeneration."""
        items = list(items)
        if self.regen:
            rng.shuffle(items)
        return items


# =============================================================================== helpers
def _lib_methodology(library: dict, type_key: str) -> list[dict] | None:
    for item in library.get("methodologies") or []:
        data = item.get("data") or {}
        if data.get("project_type") == type_key and data.get("phases"):
            return data["phases"]
    return None


def _role_title(w: Writer, key: str) -> tuple[str, str]:
    r = w.role_lib.get(key)
    if r:
        return r["title"], r.get("data", {}).get("title_en", "")
    return key, ""


def _phases(w: Writer) -> list[dict]:
    """Methodology phases for the project type, merged with activities from the selected services."""
    a = w.a
    base = _lib_methodology(w.library, a.type_key) or a.ptype["phases"]
    phases = [dict(p, activities=list(p.get("activities", [])), outputs=list(p.get("outputs", []))) for p in base]
    if a.days < 28:
        phases = [p for p in phases if p.get("role") != "optimize"] or phases
    all_acts = [x for p in phases for x in p["activities"]]
    for svc in a.services:
        acts = (svc.get("data") or {}).get("activities") or {}
        for role, items in acts.items():
            # a service activity can target a phase by key (e.g. "final") or by role
            target = next((p for p in phases if p.get("key") == role), None) \
                or next((p for p in phases if p.get("role") == role), None)
            if target is None and role == "final":
                prep = [p for p in phases if p.get("role") == "prepare"]
                target = prep[-1] if prep else None
            if target is None and role == "optimize":
                target = next((p for p in phases if p.get("role") == "execute"), None)
            if not target:
                continue
            for act in items:
                if not any(_similar(act, x) for x in all_acts):
                    target["activities"].append(act)
                    all_acts.append(act)
    for p in phases:
        p["activities"] = [w.fill(x) for x in p["activities"]]
        p["goal"] = w.fill(p.get("goal", ""))
    return phases


def _words(text: str) -> set[str]:
    out = set()
    for wd in ar.normalize(text).split():
        if wd.startswith("وال"):
            wd = wd[3:]
        elif wd.startswith("ال") or wd.startswith("لل"):
            wd = wd[2:]
        if len(wd) >= 3:
            out.add(wd[:5])
    return out


def _similar(a_text: str, b_text: str) -> bool:
    """Near-duplicate check for activities/deliverables (shared word stems)."""
    wa, wb = _words(a_text), _words(b_text)
    if not wa or not wb:
        return False
    shared = len(wa & wb)
    return shared >= 3 or (shared >= 2 and shared / len(wa | wb) >= 0.5)


def _schedule(w: Writer, phases: list[dict]) -> list[dict]:
    """Allocate days to phases. Returns phases with offset/days (0-based day offsets).

    One-off projects run their phases one after another, sized by weight.
    Recurring projects (monthly management) use a setup window for planning/preparation,
    then execution, optimisation and reporting run in parallel until the end — which is how
    retainer work actually happens."""
    a = w.a
    total = max(a.days, len(phases))
    if a.is_recurring:
        setup_phases = [p for p in phases if p.get("role") in ("plan", "prepare")]
        ongoing = [p for p in phases if p.get("role") not in ("plan", "prepare")]
        if setup_phases and ongoing:
            setup = int(min(45, max(14, total * 0.18)))
            sw = [max(0.02, float(p.get("weight", 0.1))) for p in setup_phases]
            cursor, out = 0, []
            for i, (p, wt) in enumerate(zip(setup_phases, sw)):
                d = max(1, round(setup * wt / sum(sw))) if i < len(setup_phases) - 1 else max(1, setup - cursor)
                out.append({**p, "offset": cursor, "days": d})
                cursor += d
            for p in ongoing:
                out.append({**p, "offset": cursor, "days": max(1, total - cursor), "recurring": True})
            return out
    weights = [max(0.02, float(p.get("weight", 1 / len(phases)))) for p in phases]
    s = sum(weights)
    spans = [max(1, round(total * wt / s)) for wt in weights]
    diff = total - sum(spans)
    idx = spans.index(max(spans))
    spans[idx] = max(1, spans[idx] + diff)
    offset = 0
    out = []
    for p, span in zip(phases, spans):
        out.append({**p, "offset": offset, "days": span})
        offset += span
    # Events: pin the event day if we know it
    if a.type_key == "event":
        day_phase = next((p for p in out if p.get("key") == "day"), None)
        if day_phase:
            if a.event_date and a.start:
                ev = max(1, min(total - 1, (a.event_date - a.start).days))
            else:
                ev = day_phase["offset"]
            before = [p for p in out if p["offset"] < day_phase["offset"]]
            after = [p for p in out if p["offset"] > day_phase["offset"]]
            # rescale before-phases into [0, ev) and after-phases into (ev, total)
            _rescale(before, 0, ev)
            day_phase["offset"], day_phase["days"] = ev, 1
            _rescale(after, ev + 1, total)
    return out


def _rescale(items: list[dict], start: int, end: int) -> None:
    if not items:
        return
    span = max(len(items), end - start)
    total = sum(p["days"] for p in items) or 1
    cursor = start
    for i, p in enumerate(items):
        d = max(1, round(span * p["days"] / total)) if i < len(items) - 1 else max(1, start + span - cursor)
        p["offset"], p["days"] = cursor, d
        cursor += d


def _period_label(a: Analysis, offset: int, days: int, recurring: bool = False) -> str:
    if recurring:
        if a.start:
            return f"من {ar.fmt_date(a.start + timedelta(days=offset))} حتى نهاية المشروع"
        return f"من الأسبوع {offset // 7 + 1} حتى نهاية المشروع"
    if a.start:
        s = a.start + timedelta(days=offset)
        e = a.start + timedelta(days=offset + days - 1)
        if s == e:
            return ar.fmt_date(s)
        if s.year == e.year:
            return f"{ar.fmt_short(s)} – {ar.fmt_date(e)}"
        return f"{ar.fmt_date(s)} – {ar.fmt_date(e)}"
    w1 = offset // 7 + 1
    w2 = (offset + days - 1) // 7 + 1
    return f"الأسبوع {w1}" if w1 == w2 else f"الأسبوع {w1} – {w2}"


def _kpi_name(w: Writer, key: str) -> str | None:
    k = w.kpi_lib.get(key)
    return k["title"] if k else None


def _section(sec_id: str, w: Writer, rng: random.Random, blocks: list[dict], regen: int, tone: str | None) -> dict:
    sub = w.choose(rng, P.SUBTITLES.get(sec_id, {"default": [""]}), tone)
    title = SECTION_TITLES[sec_id]
    if sec_id == "idea":
        title = I.IDEA_TITLES.get(w.a.type_key, title)
    return {
        "id": sec_id, "type": sec_id, "title": title, "title_en": SECTION_TITLES_EN[sec_id],
        "subtitle": sub, "visible": True, "divider": sec_id in DIVIDER_SECTIONS, "regen": regen,
        "tone": tone or w.a.tone, "blocks": blocks,
    }


# =============================================================================== sections
def build_about(w: Writer, rng, tone):
    st = w.settings
    blocks = []
    about = st.get("company_about") or ""
    if about:
        blocks.append(blk("lead", text=about))
    stats = [s for s in (st.get("company_stats") or []) if s.get("value")]
    if stats:
        blocks.append(blk("stats", items=stats[:4], note=st.get("company_stats_note", "")))
    pillars = st.get("company_pillars") or []
    if pillars:
        blocks.append(blk("cards", title="تخصصاتنا", items=[{"title": p.get("title", ""), "text": p.get("text", ""), "icon": p.get("icon", "spark")} for p in pillars], columns=min(4, len(pillars))))
    return blocks


def build_intro(w: Writer, rng, tone):
    a = w.a
    blocks = []
    tpl_id = a.prefs.get("intro_template")
    lib_tpl = next((t for t in w.library.get("intro_templates") or [] if t["id"] == tpl_id), None) if tpl_id and tpl_id != "auto" else None
    if lib_tpl:
        blocks.append(blk("lead", text=w.note(w.fill((lib_tpl.get("data") or {}).get("text", "")))))
    else:
        blocks.append(blk("lead", text=w.choose(rng, P.INTRO_OPENING, tone)))
    t = tone or a.tone
    if t != "concise" or a.detail != "brief":
        purpose = w.choose(rng, P.INTRO_PURPOSE, tone)
        approach = w.choose(rng, P.INTRO_APPROACH, tone) if a.ptype.get("approach") else ""
        blocks.append(blk("paragraph", text=f"{purpose} {approach}".strip()))
    if t == "detailed" or a.detail == "advanced":
        blocks.append(blk("paragraph", text=w.choose(rng, P.INTRO_DETAILED_EXTRA)))
    return blocks


def build_understanding(w: Writer, rng, tone):
    a = w.a
    caps = w.caps
    blocks = []
    drivers = list(a.sector.get("drivers") or [])
    rng.shuffle(drivers)  # drivers are equally weighted; any three read naturally
    first = []
    if a.client_about:
        first.append(ar.sentence(a.client_about))
    if drivers:
        first.append(w.choose(rng, P.UNDERSTANDING_SECTOR, tone, drivers=ar.join(drivers[:3])))
    if first:
        blocks.append(blk("paragraph", text=" ".join(first)))
    if a.description:
        blocks.append(blk("paragraph", text=w.choose(rng, P.UNDERSTANDING_REQUEST, tone)))

    cards = []
    challenges = w.shuffled(rng, a.ptype.get("challenges") or [])
    opportunities = w.shuffled(rng, a.ptype.get("opportunities") or [])
    if a.challenge:
        cards.append({"title": "التحدي كما ورد", "text": ar.sentence(a.challenge), "icon": "flag"})
    if challenges:
        cards.append({"title": "التحدي", "text": w.note(w.fill(challenges[0])), "icon": "alert"})
    if opportunities:
        cards.append({"title": "الفرصة", "text": w.note(w.fill(opportunities[0])), "icon": "spark"})
    cards.append({"title": "الجمهور المستهدف المقترح" if a.audience_suggested else "الجمهور المستهدف",
                  "text": ar.sentence(ar.join(a.segments)) if a.audience_suggested else ar.sentence(a.audience),
                  "icon": "users"})
    if a.event_date or a.location:
        parts = []
        if a.event_date:
            parts.append(f"التاريخ: {ar.fmt_date(a.event_date)}")
        if a.location:
            parts.append(f"الموقع: {a.location}")
        cards.append({"title": "تفاصيل التنفيذ", "text": "، ".join(parts) + ".", "icon": "pin"})
    for p in a.platforms[: (2 if a.detail == "brief" else 3)]:
        cards.append({"title": f"دور {PLATFORMS[p]['label']}", "text": ar.sentence(PLATFORMS[p]["role"]), "icon": "chat"})
    if len(challenges) > 1 and a.detail != "brief":
        cards.append({"title": "ما يجب الانتباه له", "text": w.note(w.fill(challenges[1])), "icon": "eye"})
    seasons = a.sector.get("seasons") or []
    if seasons and (a.is_recurring or a.type_key in ("campaign", "influencer")):
        cards.append({"title": "مواسم يمكن البناء عليها", "text": ar.join(seasons[:4]) + ".", "icon": "calendar"})
    angles = list(a.sector.get("angles") or [])
    if angles and a.type_key in ("social_media", "content", "influencer", "campaign", "production"):
        angles = w.shuffled(rng, angles)
        cards.append({"title": "زوايا محتوى مناسبة للقطاع", "text": ar.join(angles[:3]) + ".", "icon": "pen"})
    cons = a.sector.get("considerations") or []
    if cons and a.detail != "brief":
        cards.append({"title": "اعتبارات تنظيمية", "text": ar.sentence(cons[0]), "icon": "shield"})
    blocks.append(blk("cards", items=cards[: caps["cards"]], columns=2 if len(cards[: caps["cards"]]) <= 4 else 3))

    if a.special_requirements:
        blocks.append(blk("list", title="متطلبات خاصة أكد عليها العميل", items=[ar.sentence(r) for r in a.special_requirements], style="check"))

    insight = w.choose(rng, P.INSIGHTS.get(a.type_key, P.INSIGHTS["other"]))
    blocks.append(blk("callout", label="الخلاصة", text=insight))
    return blocks


def build_objectives(w: Writer, rng, tone):
    a = w.a
    items = []
    for o in a.objectives[: w.caps["objectives"]]:
        measures = [n for n in (_kpi_name(w, m) for m in o.measures) if n]
        items.append({
            "title": ar.strip_end(o.title),
            "text": ar.sentence(o.statement),
            "measure": ar.join(measures) if measures else "",
            "target": o.target or "يُحدد بعد قياس خط الأساس",
            "suggested": o.source == "suggested",
        })
    blocks = [blk("paragraph", text=w.choose(rng, P.OBJECTIVES_INTRO, tone)), blk("objectives", items=items)]
    return blocks


def build_scope(w: Writer, rng, tone):
    a = w.a
    blocks = [blk("paragraph", text=w.choose(rng, P.SCOPE_INTRO, tone))]
    if a.scope_text:
        blocks.append(blk("paragraph", text=f"ويشمل ذلك تحديدًا: {ar.sentence(a.scope_text)}"))
    groups: dict[str, list] = {}
    for s in a.services:
        data = s.get("data") or {}
        cat = data.get("category", "pm")
        text = data.get("description", "")
        if a.platforms and s["key"] in ("social_management", "content_strategy", "paid_ads"):
            text = text.rstrip(".") + f"، على {ar.join(a.platform_labels)}."
        groups.setdefault(cat, []).append({"title": s["title"], "text": text})
    ordered = []
    for cat_key, cat in CATEGORIES.items():
        if cat_key in groups:
            ordered.append({"title": cat["label"], "icon": cat["icon"], "items": groups.pop(cat_key)})
    for cat_key, items in groups.items():
        ordered.append({"title": cat_key, "icon": "spark", "items": items})
    if a.custom_services:
        ordered.append({"title": "خدمات مخصصة لهذا المشروع", "icon": "plus",
                        "items": [{"title": c["title"].strip(), "text": (c.get("description") or "").strip()} for c in a.custom_services]})
    blocks.append(blk("services", groups=ordered))
    if a.out_of_scope:
        blocks.append(blk("list", title="خارج نطاق العمل", items=[ar.sentence(x) for x in a.out_of_scope], style="minus"))
    return blocks


def build_methodology(w: Writer, rng, tone):
    a = w.a
    phases = _schedule(w, _phases(w))
    items = []
    for p in phases:
        acts = p["activities"][: w.caps["activities"]]
        item = {"title": p["name"], "goal": p.get("goal", ""), "activities": acts,
                "period": _period_label(a, p["offset"], p["days"], p.get("recurring", False))}
        if a.detail != "brief":
            item["outputs"] = p.get("outputs", [])
        items.append(item)
    blocks = [blk("paragraph", text=w.choose(rng, P.METHODOLOGY_INTRO, tone, phase_count=ar.count(len(items), "phase")))]
    if a.is_recurring:
        bank = P.METHODOLOGY_RECURRING.get(a.type_key) or P.METHODOLOGY_RECURRING["default"]
        blocks.append(blk("callout", label="دورة العمل", text=w.choose(rng, bank)))
    blocks.append(blk("phases", items=items))
    return blocks


def _library_deliverables(w: Writer) -> list[dict]:
    """Deliverables of the selected services with quantities computed for this project's duration."""
    a = w.a
    phases = _schedule(w, _phases(w))
    timing_by_role = {}
    for p in phases:
        timing_by_role.setdefault(p.get("role"), _period_label(a, p["offset"], p["days"], p.get("recurring", False)))
    months = a.months if a.days >= 25 else 1
    rows, seen = [], set()
    for s in a.services:
        for d in (s.get("data") or {}).get("deliverables") or []:
            key = ar.normalize(d["title"])
            if key in seen:
                continue
            seen.add(key)
            mode = d.get("mode", "fixed")
            qty = d.get("qty")
            desc = d.get("description", "")
            timing = timing_by_role.get(d.get("phase"), "")
            per_month = None
            if mode == "monthly":
                per_month = qty
                if qty and qty > 1:
                    desc = f"{desc} — بمعدل {qty} شهريًا" if desc else f"بمعدل {qty} شهريًا"
                qty = qty * months if qty else None
                timing = "شهريًا" if months > 1 else timing
            elif mode == "per_platform":
                qty = (qty or 1) * max(1, len(a.platforms))
                if a.platforms:
                    desc = f"{desc} ({ar.join(a.platform_labels)})"
            if d.get("phase") == "report" and mode == "fixed":
                timing = "نهاية المشروع"
            rows.append({"id": _id(), "title": d["title"], "description": desc, "qty": qty, "unit": d.get("unit", ""),
                         "timing": timing, "source": "library", "_mode": mode, "_base_desc": d.get("description", ""),
                         "_per_month": per_month})
    return rows


def build_deliverables(w: Writer, rng, tone):
    a = w.a
    library_rows = _library_deliverables(w)
    months = a.months if a.days >= 25 else 1
    rows = []
    consumed = set()
    for d in a.deliverables_input:
        # Match what the user typed ("12 فيديو شهريًا") with a library deliverable to reuse its proper title/description
        match = next((r for r in library_rows if r["id"] not in consumed and _stem_match(d["title"], r["title"])), None)
        qty, monthly = d["qty"], d["monthly"]
        if match:
            consumed.add(match["id"])
            title, unit, base = match["title"], match["unit"], match["_base_desc"]
            monthly = monthly or match["_mode"] == "monthly"
        else:
            title, unit, base = d["title"], "", ""
        if monthly and qty:
            desc = f"{base} — بمعدل {qty} شهريًا" if base else f"بمعدل {qty} شهريًا"
            qty = qty * months
            timing = "شهريًا" if months > 1 else (match["timing"] if match else "")
        else:
            desc = base or "وفق ما ورد في متطلبات المشروع"
            timing = match["timing"] if match else ""
        rows.append({"id": _id(), "title": title, "description": desc, "qty": qty, "unit": unit, "timing": timing,
                     "source": "user"})
    for r in library_rows:
        if r["id"] in consumed:
            continue
        rows.append({k: v for k, v in r.items() if not k.startswith("_")})
    blocks = [blk("paragraph", text=w.choose(rng, P.DELIVERABLES_INTRO, tone)), blk("deliverables", rows=rows)]
    return blocks


def _stem_match(user_title: str, lib_title: str) -> bool:
    uw, lw = _words(user_title), _words(lib_title)
    if not uw or not lw:
        return False
    hits = sum(1 for x in uw if any(x[:4] == y[:4] for y in lw))
    return hits >= max(1, min(len(uw), 2)) if len(uw) <= 2 else hits >= 2


def build_timeline(w: Writer, rng, tone):
    a = w.a
    phases = _schedule(w, _phases(w))
    team_keys = {m for m in _team_keys(w)}
    rows = []
    n_rows = w.caps["timeline_rows"]
    for p in phases:
        acts = p["activities"][: (1 if p.get("recurring") else n_rows)] or [p["name"]]
        span = p["days"]
        k = len(acts)
        owner_key = p.get("owner") if p.get("owner") in team_keys else "project_manager"
        owner = _role_title(w, owner_key)[0]
        for i, act in enumerate(acts):
            if k == 1 or span < k or p.get("recurring"):
                off, d = p["offset"], span
            else:
                seg = span / k
                off = p["offset"] + int(round(i * seg))
                d = max(1, int(round((i + 1) * seg)) - int(round(i * seg)))
            rows.append({"id": _id(), "phase": p["name"], "activity": act, "offset": off, "days": d, "owner": owner})
    milestones = [{"id": _id(), "label": "اجتماع الانطلاق", "offset": 0}]
    if a.type_key == "event":
        day = next((p for p in phases if p.get("key") == "day"), None)
        if day:
            milestones.append({"id": _id(), "label": "يوم الفعالية" if a.event_date else "يوم الفعالية (موعد مقترح)", "offset": day["offset"]})
    if a.is_recurring:
        m = 1
        while m * 30 < a.days - 5:
            milestones.append({"id": _id(), "label": f"تقرير الشهر {m}", "offset": m * 30})
            m += 1
    milestones.append({"id": _id(), "label": "التقرير الختامي", "offset": max(0, a.days - 1)})
    blocks = [
        blk("paragraph", text=w.choose(rng, P.TIMELINE_INTRO, tone)),
        blk("timeline", start_date=a.start.isoformat() if a.start else None, total_days=a.days, rows=rows, milestones=milestones),
    ]
    return blocks


def _team_keys(w: Writer) -> list[str]:
    a = w.a
    scores: dict[str, float] = {}
    for i, key in enumerate(a.ptype.get("team_core", [])):
        scores[key] = scores.get(key, 0) + 60 - i * 3
    for s in a.services:
        for key in (s.get("data") or {}).get("roles", []):
            scores[key] = scores.get(key, 0) + 12
    for key in list(scores):
        base = (w.role_lib.get(key, {}).get("data") or {}).get("weight", 40)
        scores[key] += base / 4
    scores["project_manager"] = 10_000
    wants_coord = (a.team_size or 0) >= 3 or (a.team_size is None and a.days >= 30)
    if wants_coord:
        scores["project_coordinator"] = max(scores.get("project_coordinator", 0), 5_000)
    ranked = [k for k, _ in sorted(scores.items(), key=lambda kv: -kv[1]) if k in w.role_lib]
    limit = a.team_size if a.team_size else w.caps["team"]
    return ranked[: max(1, min(limit, len(ranked)))]


def build_team(w: Writer, rng, tone):
    a = w.a
    keys = _team_keys(w)
    counts = {k: 1 for k in keys}
    if a.team_size and a.team_size > len(keys):
        extra = a.team_size - len(keys)
        pool = [k for k in ("designer", "production_team", "social_media_specialist", "content_specialist",
                            "operations_coordinator", "video_editor", "copywriter") if k in counts] or keys[1:] or keys
        i = 0
        while extra > 0:
            counts[pool[i % len(pool)]] += 1
            extra -= 1
            i += 1
    members = []
    for k in keys:
        role = w.role_lib[k]
        data = role.get("data") or {}
        members.append({"id": _id(), "role": role["title"], "role_en": data.get("title_en", ""),
                        "responsibilities": (data.get("responsibilities") or [])[: w.caps["responsibilities"]],
                        "count": counts[k]})
    return [blk("paragraph", text=w.choose(rng, P.TEAM_INTRO, tone)), blk("team", members=members)]


def build_kpis(w: Writer, rng, tone):
    a = w.a
    order: list[str] = []
    for o in a.objectives:
        order += o.measures
    order += a.ptype.get("kpis", [])
    for p in a.platforms:
        order += PLATFORMS[p].get("kpis", [])
    for s in a.services:
        if s["key"] == "paid_ads":
            order += ["ctr", "cpa"]
        if s["key"] == "influencer_marketing":
            order += ["influencer_views", "cpe"]
        if s["key"] == "media_monitoring":
            order += ["sentiment"]
    seen, keys = set(), []
    for k in order:
        if k in w.kpi_lib and k not in seen:
            seen.add(k)
            keys.append(k)
    targets = {}
    for o in a.objectives:
        if o.target:
            for m in o.measures:
                targets.setdefault(m, o.target)
    items = []
    for k in keys[: w.caps["kpis"]]:
        kp = w.kpi_lib[k]
        data = kp.get("data") or {}
        target = targets.get(k)
        if not target:
            for name, val in a.kpi_targets.items():
                if name in (ar.normalize(kp["title"]), ar.normalize(data.get("name_en", ""))):
                    target = val
        items.append({"id": _id(), "name": kp["title"], "name_en": data.get("name_en", ""),
                      "definition": data.get("definition", ""), "measurement": data.get("measurement", ""),
                      "frequency": data.get("frequency", ""), "target": target or "يُحدد مع العميل"})
    return [blk("paragraph", text=w.choose(rng, P.KPIS_INTRO, tone)), blk("kpis", items=items)]


def build_governance(w: Writer, rng, tone):
    a = w.a
    gov = a.ptype.get("governance", {})
    meetings = gov.get("meetings", [])
    reports = ("تحديث أسبوعي مختصر بما أُنجز وما هو قادم، وتقرير شهري مفصل بالأداء والتوصيات."
               if a.is_recurring else "تحديث أسبوعي بحالة الإنجاز مقابل الجدول، وتقرير ختامي بالنتائج.")
    cards = [
        {"title": "قنوات التواصل", "icon": "chat",
         "text": w.fill("مدير المشروع هو نقطة التواصل الرئيسية مع {client}، مع مجموعة عمل مشتركة للمتابعة اليومية، والبريد الإلكتروني للاعتمادات والقرارات الرسمية.")},
        {"title": "الاجتماعات", "icon": "calendar", "text": ar.join(meetings) + "." if meetings else "اجتماع انطلاق، ومتابعة أسبوعية، واجتماع ختامي."},
        {"title": "التقارير", "icon": "chart", "text": reports},
        {"title": "اعتماد المحتوى", "icon": "check", "text": w.fill(gov.get("approvals", "تُعتمد المخرجات على مراحل متفق عليها.")) + " ونقترح أن يُرد على طلبات الاعتماد خلال يومي عمل."},
        {"title": "إدارة المهام", "icon": "kanban",
         "text": w.fill("تُدار المهام على منصة مشتركة يطّلع عليها فريق {client}، وتظهر فيها حالة كل مهمة وموعدها والمسؤول عنها.")},
        {"title": "متابعة الإنجاز", "icon": "progress",
         "text": w.fill("نقارن الإنجاز الفعلي بالجدول أسبوعيًا، و{yubal} {client} بأي انحراف قبل أن يؤثر على المواعيد.")},
    ]
    for extra in gov.get("extra", []):
        cards.append({"title": extra["title"], "text": w.fill(extra["text"]), "icon": "shield"})
    blocks = [blk("paragraph", text=w.choose(rng, P.GOVERNANCE_INTRO, tone))]
    if a.detail == "brief":
        cards.append({"title": "التصعيد", "icon": "alert",
                      "text": "يُرفع أي تأخير إلى مدير المشروع خلال يوم عمل، ثم إلى الإدارة التنفيذية إن هدد الجدول أو النطاق."})
        blocks.append(blk("cards", items=cards, columns=3))
    else:
        blocks.append(blk("cards", items=cards, columns=3))
        blocks.append(blk("table", title="مستويات التصعيد", columns=[
            {"key": "level", "label": "المستوى"}, {"key": "case", "label": "الحالة"},
            {"key": "owner", "label": "المسؤول"}, {"key": "time", "label": "مدة المعالجة"}],
            rows=[
                {"id": _id(), "level": "الأول", "case": "ملاحظة تشغيلية أو تأخير بسيط في مهمة", "owner": "منسق المشروع", "time": "خلال يوم عمل"},
                {"id": _id(), "level": "الثاني", "case": "تأخير يؤثر على موعد مخرج أو مرحلة", "owner": "مدير المشروع", "time": "خلال يومي عمل"},
                {"id": _id(), "level": "الثالث", "case": "عائق يهدد الجدول الزمني أو النطاق", "owner": w.fill("الإدارة التنفيذية في أهداف وممثل {client}"), "time": "اجتماع خلال 3 أيام عمل"},
            ]))
    return blocks


def build_assumptions(w: Writer, rng, tone):
    a = w.a
    items = [w.fill(x) for x in a.ptype.get("assumptions", [])]
    keys = {s["key"] for s in a.services}
    if "branding" not in keys and a.type_key != "branding":
        items.append("تزويد الفريق بالهوية البصرية وأدلة الاستخدام والملفات المصدرية للشعار")
    items.append(w.fill("تحديد ممثل واحد من {client} مخوّل باعتماد المخرجات والقرارات"))
    if "paid_ads" in keys and a.type_key != "digital_ads":
        items.append("ميزانية الإعلانات الممولة تُحتسب بشكل منفصل عن أتعاب الإدارة والإنتاج ما لم يُتفق على غير ذلك")
    if "influencer_marketing" in keys and a.type_key != "influencer":
        items.append("أتعاب المؤثرين تُعتمد بعد اعتماد قائمة الترشيح، وتُحتسب وفق ما يُتفق عليه")
    action_heads = ("استيفاء", "مراجعة", "الحصول", "الالتزام", "إظهار", "اعتماد", "التحقق")
    for c in a.sector.get("considerations") or []:
        if c.startswith(action_heads):  # only considerations phrased as an actionable requirement
            items.append(c)
    items.append("الالتزام بمواعيد الاعتماد المتفق عليها؛ إذ يؤثر أي تأخير فيها على الجدول الزمني بالمدة نفسها")
    if a.detail == "advanced":
        items.append("أي خدمة أو مخرج خارج النطاق الوارد في هذا العرض يُعامل كطلب إضافي يُتفق على مدته وتكلفته كتابيًا")
    seen, out = set(), []
    for x in items:
        k = ar.normalize(x)
        if k not in seen:
            seen.add(k)
            out.append(ar.sentence(x))
    blocks = [blk("paragraph", text=w.choose(rng, P.ASSUMPTIONS_INTRO, tone)),
              blk("list", items=out[: w.caps["assumptions"]], style="check")]
    if a.out_of_scope and not any(b.get("title") == "خارج نطاق العمل" for b in blocks):
        pass  # out-of-scope is listed in the scope section
    return blocks


def build_risks(w: Writer, rng, tone):
    a = w.a
    rows = [dict(r) for r in a.ptype.get("risks", [])]
    rows += [dict(r) for r in a.sector.get("risks") or []]
    if a.days < a.ptype["default_days"] * 0.6:
        rows.insert(0, {"risk": "ضيق الجدول الزمني مقارنةً بحجم المخرجات", "likelihood": "مرتفعة", "impact": "مرتفع",
                        "mitigation": "تنفيذ متوازٍ لبعض المراحل، واعتماد سريع متفق عليه، وتقليص جولات التعديل"})
    rows.append({"risk": "تغير النطاق أو إضافة مخرجات أثناء التنفيذ", "likelihood": "متوسطة", "impact": "متوسط",
                 "mitigation": "توثيق أي تغيير وأثره على الجدول والتكلفة واعتماده قبل التنفيذ"})
    seen, out = set(), []
    for r in rows:
        k = ar.normalize(r["risk"])
        if k in seen:
            continue
        seen.add(k)
        out.append({"id": _id(), "risk": w.fill(r["risk"]), "likelihood": r["likelihood"], "impact": r["impact"],
                    "mitigation": w.fill(r["mitigation"])})
    return [blk("paragraph", text=w.choose(rng, P.RISKS_INTRO, tone)), blk("risks", rows=out[: w.caps["risks"]])]


def build_budget(w: Writer, rng, tone):
    a = w.a
    return [
        blk("stats", items=[{"value": a.budget, "label": "الميزانية التقديرية للمشروع"}]),
        blk("paragraph", text="تُفصّل بنود التكلفة وشروط الدفع في العرض المالي المرفق بشكل منفصل."),
    ]


def build_past_projects(w: Writer, rng, tone):
    a = w.a
    items = []
    for p in w.library.get("past_projects") or []:
        d = p.get("data") or {}
        relevant = d.get("sector") == a.sector_key or d.get("project_type") == a.type_key
        if not relevant:
            continue
        title = p["title"] + (" (تجريبي)" if p.get("is_demo") else "")
        text = d.get("summary", "")
        if d.get("results"):
            text = f"{text} {d['results']}".strip()
        items.append({"title": title, "text": text, "icon": "briefcase"})
    if not items:
        return [blk("paragraph", text="[[أضف أعمالًا سابقة ذات صلة من مكتبة المحتوى]]")]
    return [blk("cards", items=items[:4], columns=2)]


def build_conclusion(w: Writer, rng, tone):
    a = w.a
    blocks = []
    tpl_id = a.prefs.get("conclusion_template")
    lib_tpl = next((t for t in w.library.get("conclusion_templates") or [] if t["id"] == tpl_id), None) if tpl_id and tpl_id != "auto" else None
    if lib_tpl:
        blocks.append(blk("lead", text=w.note(w.fill((lib_tpl.get("data") or {}).get("text", "")))))
    else:
        blocks.append(blk("lead", text=w.choose(rng, P.CONCLUSION_MAIN, tone)))
        part = w.choose(rng, P.CONCLUSION_PARTNERSHIP, tone)
        if part:
            blocks.append(blk("paragraph", text=part))
    phases = _phases(w)
    first = phases[0]["name"] if phases else "المرحلة الأولى"
    steps = []
    for s in P.NEXT_STEPS:
        text = s["text"].replace("{handover}", P.HANDOVER_BY_TYPE.get(a.type_key, P.HANDOVER_BY_TYPE["other"]))
        text = text.replace("{first_phase}", f"البدء في مرحلة «{first}» وفق الجدول المعتمد.")
        steps.append({"title": s["title"], "text": w.fill(text)})
    blocks.append(blk("steps", title="الخطوات التالية", items=steps))
    return blocks


# ------------------------------------------------------------------ creative sections (the system proposes)
def _concept(w: Writer, rng) -> dict:
    options = list(I.CONCEPTS.get(w.a.sector_key) or []) + list(I.CONCEPTS["general"])
    if not w.regen:
        return options[0]
    return options[(w.regen + rng.randrange(len(options))) % len(options)]


def build_idea(w: Writer, rng, tone):
    a = w.a
    c = _concept(w, rng)
    name = c["name"]
    w.ctx["concept"] = name
    execution = [w.fill(x, concept=name) for x in I.EXECUTION.get(a.type_key, I.EXECUTION["other"])]
    lines = list(c["lines"])
    blocks = [
        blk("lead", text=w.note(f"«{name}»: " + w.fill(c["idea"]))),
        blk("callout", label="الرسالة الأساسية", text=w.note(w.fill(c["message"]))),
        blk("cards", title="مقترحات للشعار", columns=3,
            items=[{"title": f"«{line}»", "text": "", "icon": "quote"} for line in lines]),
        blk("list", title="كيف تتحول الفكرة إلى تنفيذ", items=[ar.sentence(x) for x in execution], style="check"),
    ]
    return blocks


def build_activations(w: Writer, rng, tone):
    a = w.a
    concept = w.ctx.get("concept") or _concept(w, rng)["name"]
    pool = [dict(x) for x in I.SECTOR_ACTIVATIONS.get(a.sector_key, I.SECTOR_ACTIVATIONS["general"])]
    pool += [dict(x) for x in I.TYPE_ACTIVATIONS.get(a.type_key, I.TYPE_ACTIVATIONS["other"])]
    pool = w.shuffled(rng, pool)
    count = {"brief": 4, "medium": 6, "advanced": 8}[a.detail]
    items = []
    for x in pool[:count]:
        items.append({"title": w.fill(x["title"], concept=concept), "text": w.fill(x["text"], concept=concept),
                      "icon": x.get("icon", "spark")})
    intro = w.fill("أفكار عملية نقترحها {li_client} لتحويل الفكرة إلى تفاعل ونتائج. كل فكرة قابلة للتطوير أو الاستبدال بعد مناقشتها مع فريقكم.")
    return [blk("paragraph", text=w.note(intro)), blk("cards", items=items, columns=2 if count <= 4 else 3)]


def build_content_plan(w: Writer, rng, tone):
    a = w.a
    pillars = [dict(x) for x in I.PILLARS.get(a.sector_key, I.GENERIC_PILLARS)]
    pillars = w.shuffled(rng, pillars) if w.regen else pillars
    cards = []
    for pl in pillars:
        ex = "، ".join(w.fill(e) for e in pl["examples"])
        cards.append({"title": pl["title"], "text": f"{w.fill(pl['text'])} أمثلة: {ex}.", "icon": "pen"})
    labels = a.platform_labels or ["المنصات المعتمدة"]
    formats = []
    for key in a.platforms or []:
        formats += [(PLATFORMS[key]["label"], f) for f in PLATFORMS[key]["formats"] if "بث مباشر" not in f]
    if not formats:
        formats = [(labels[0], "مقطع قصير"), (labels[0], "منشور"), (labels[0], "قصص")]
    examples = [w.fill(e) for pl in pillars for e in pl["examples"]]
    rows = []
    for i, day in enumerate(I.WEEK_DAYS):
        platform, fmt = formats[i % len(formats)]
        rows.append({"id": _id(), "day": day, "platform": platform, "format": fmt,
                     "idea": examples[i % len(examples)], "pillar": pillars[i % len(pillars)]["title"]})
    return [
        blk("paragraph", text=w.note(w.fill("نقترح أن يُبنى المحتوى على المحاور التالية، لكل محور هدف وأمثلة جاهزة للتطوير. يليها نموذج لأسبوع نشر يوضح الإيقاع المقترح."))),
        blk("cards", items=cards, columns=2),
        blk("table", title="نموذج أسبوع نشر", columns=[
            {"key": "day", "label": "اليوم"}, {"key": "platform", "label": "المنصة"}, {"key": "format", "label": "الصيغة"},
            {"key": "pillar", "label": "المحور"}, {"key": "idea", "label": "الفكرة"}], rows=rows),
    ]


BUILDERS = {
    "about": build_about, "intro": build_intro, "understanding": build_understanding,
    "objectives": build_objectives, "scope": build_scope, "methodology": build_methodology,
    "deliverables": build_deliverables, "timeline": build_timeline, "team": build_team, "kpis": build_kpis,
    "governance": build_governance, "assumptions": build_assumptions, "risks": build_risks,
    "budget": build_budget, "past_projects": build_past_projects, "conclusion": build_conclusion,
    "idea": build_idea, "activations": build_activations, "content_plan": build_content_plan,
}


def _enabled_sections(a: Analysis) -> list[str]:
    out = []
    for sec in SECTION_ORDER:
        if sec == "about" and not a.prefs.get("include_about", True):
            continue
        if sec == "budget" and not (a.budget and a.show_budget):
            continue
        if sec == "past_projects" and not a.prefs.get("include_past_projects"):
            continue
        if sec == "content_plan" and a.type_key not in CONTENT_TYPES:
            continue
        out.append(sec)
    return out


# =============================================================================== public API
def build_cover(a: Analysis, settings: dict, w: Writer, today: date | None = None) -> dict:
    today = today or date.today()
    return {
        "kicker": "عرض فني",
        "title": a.project or "[[اسم المشروع]]",
        "subtitle": ar.sentence(w.ctx["nature"]),
        "client": a.client or "[[اسم العميل]]",
        "prepared_by": settings.get("company_name", "شركة أهداف للخدمات التسويقية"),
        "date": ar.fmt_date(today, with_day=False),
        "version": (a.prefs.get("version") or "1.0"),
        "image": None,
        "client_logo": (a.inputs.get("client") or {}).get("logo") or None,
    }


def generate(inputs: dict, library: dict, settings: dict, seed: int | None = None, today: date | None = None) -> dict:
    a = analyze(inputs, library)
    seed = seed if seed is not None else random.randint(1, 10_000_000)
    w = Writer(a, library, settings, seed)
    sections = []
    for sec in _enabled_sections(a):
        rng = w.rng(sec, 0)
        blocks = BUILDERS[sec](w, rng, None)
        sections.append(_section(sec, w, rng, blocks, 0, None))
    if not a.prefs.get("dividers", True):
        for s in sections:
            s["divider"] = False
    doc = {
        "cover": build_cover(a, settings, w, today),
        "sections": sections,
        "layout": a.prefs.get("layout") if a.prefs.get("layout") in ("landscape", "portrait") else "landscape",
        "theme": a.prefs.get("design") if a.prefs.get("design") in DESIGNS else "ahdaf",
        "seed": seed,
        "tone": a.tone,
        "detail": a.detail,
    }
    return {"doc": doc, "meta": build_meta(a)}


def regenerate_section(inputs: dict, doc: dict, section_id: str, library: dict, settings: dict,
                       tone: str | None = None) -> dict:
    """Rebuild one section with the next variation; other sections are untouched."""
    a = analyze(inputs, library)
    if tone and tone in TONES:
        a.tone = tone
    current = next((s for s in doc.get("sections", []) if s["id"] == section_id), None)
    base_type = current["type"] if current else section_id
    if base_type not in BUILDERS:
        raise ValueError(f"unknown section: {section_id}")
    regen = (current.get("regen", 0) if current else 0) + 1
    used = set()
    for s in doc.get("sections", []):
        if s["id"] == section_id:
            continue
        for b in s.get("blocks", []):
            if isinstance(b.get("text"), str):
                used.add(b["text"])
    w = Writer(a, library, settings, doc.get("seed", 1), used=used)
    w.regen = regen
    idea = next((s for s in doc.get("sections", []) if s.get("type") == "idea"), None)
    if idea and base_type != "idea":
        lead = next((b.get("text", "") for b in idea.get("blocks", []) if b.get("type") == "lead"), "")
        if lead.startswith("«") and "»" in lead:
            w.ctx["concept"] = lead[1:lead.index("»")]
    rng = w.rng(base_type, regen)
    blocks = BUILDERS[base_type](w, rng, tone)
    section = _section(base_type, w, rng, blocks, regen, tone)
    if current:
        section["id"] = current["id"]
        section["title"] = current.get("title", section["title"])
        section["visible"] = current.get("visible", True)
        section["divider"] = current.get("divider", section["divider"])
        if current.get("image"):
            section["image"] = current["image"]
    return section


def build_meta(a: Analysis) -> dict:
    return {
        "missing": a.missing,
        "suggested": a.suggested,
        "type": a.type_key,
        "type_label": a.ptype["label"],
        "sector": a.sector_key,
        "sector_label": a.sector.get("name", ""),
        "platforms": a.platforms,
        "service_labels": [s["title"] for s in a.services] + [c["title"] for c in a.custom_services],
        "days": a.days,
        "objectives_suggested": a.objectives_suggested,
        "tone_label": TONES.get(a.tone, ""),
        "detail_label": DETAILS.get(a.detail, ""),
        "analysis": {
            "type": a.ptype["label"],
            "secondary": [PROJECT_TYPES[t]["label"] for t in a.secondary_types],
            "sector": a.sector.get("name", ""),
            "platforms": a.platform_labels,
            "duration": ar.duration_phrase(a.days),
            "objectives": [{"title": o.title, "category": OBJECTIVES[o.key]["label"], "target": o.target} for o in a.objectives],
        },
    }
