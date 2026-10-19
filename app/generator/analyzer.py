"""Turns raw wizard inputs into an `Analysis`: what kind of project this is, for whom,
on which platforms, for how long, and — importantly — what information is missing.
Missing information is recorded, never guessed."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.core import arabic as ar
from app.generator.knowledge.ideas import SEGMENTS
from app.generator.knowledge.objectives import DEFAULTS_BY_TYPE, OBJECTIVES
from app.generator.knowledge.places import mentioned_cities
from app.generator.knowledge.platforms import PLATFORM_ORDER, PLATFORMS
from app.generator.knowledge.project_types import PROJECT_TYPES
from app.generator.knowledge.sectors import SECTORS

TONES = {
    "formal": "رسمي", "corporate": "Corporate", "luxury": "فاخر",
    "marketing": "تسويقي", "concise": "مختصر", "detailed": "تفصيلي",
}
DETAILS = {"brief": "مختصر", "medium": "متوسط", "advanced": "متقدم"}

FEMININE_HEADS = ("شركة", "مؤسسة", "مجموعة", "وزارة", "هيئة", "جامعة", "مدرسة", "جمعية", "وكالة", "منصة",
                  "أكاديمية", "إمارة", "أمانة", "بلدية", "عيادة", "علامة")
MASCULINE_HEADS = ("بنك", "مصرف", "مستشفى", "نادي", "مركز", "مطعم", "متجر", "مصنع", "فندق", "معهد", "مجمع",
                   "صندوق", "برنامج", "منتجع", "مقهى", "معرض", "مكتب")

EVENT_NOUNS = ["مؤتمر", "ملتقى", "منتدى", "حفل", "افتتاح", "تدشين", "معرض", "مهرجان", "ورشة", "احتفال", "قمة"]

CONVERSION_BY_OBJECTIVE = {
    "bookings": "الحجز", "sales": "الشراء", "leads": "التواصل وطلب الخدمة", "downloads": "تحميل التطبيق",
    "attendance": "الحضور", "traffic": "زيارة المتجر أو الموقع",
}


@dataclass
class Objective:
    key: str
    title: str
    statement: str
    measures: list[str]
    target: str | None
    source: str  # "user" | "suggested"


@dataclass
class Analysis:
    inputs: dict
    client: str
    client_gender: str
    client_about: str
    project: str
    type_key: str
    ptype: dict
    secondary_types: list[str]  # other types the project combines (chosen by the team, then detected)
    sector_key: str
    sector: dict
    platforms: list[str]
    audience: str | None
    description: str
    challenge: str
    location: str
    scope_text: str
    out_of_scope: list[str]
    special_requirements: list[str]
    start: date | None
    end: date | None
    days: int
    event_date: date | None
    services: list[dict]
    custom_services: list[dict]
    objectives: list[Objective]
    objectives_suggested: bool
    deliverables_input: list[dict]
    kpi_targets: dict[str, str]
    team_size: int | None
    budget: str
    show_budget: bool
    tone: str
    detail: str
    prefs: dict
    missing: list[dict] = field(default_factory=list)
    event_noun: str = "فعالية"
    audience_suggested: bool = False
    segments: list[str] = field(default_factory=list)
    extra_platforms: list[str] = field(default_factory=list)
    suggested: list[str] = field(default_factory=list)  # what the system proposed on its own
    cities: list[str] = field(default_factory=list)  # cities the brief focuses on
    chosen_types: list[str] = field(default_factory=list)  # project types the team picked, main one first

    # ------------------------------------------------------------------ derived helpers
    @property
    def months(self) -> int:
        return max(1, math.ceil(self.days / 30.4 - 0.15))

    @property
    def is_recurring(self) -> bool:
        return bool(self.ptype.get("recurring")) and self.days >= 45

    @property
    def platform_labels(self) -> list[str]:
        return [PLATFORMS[p]["label"] for p in self.platforms] + list(self.extra_platforms)

    @property
    def audience_phrase(self) -> str:
        # The user's own audience text is shown verbatim in its own card; inside generated
        # sentences we use a neutral phrase because free text cannot be inflected grammatically.
        return "الجمهور المستهدف"

    @property
    def conversion(self) -> str:
        for o in self.objectives:
            if o.key in CONVERSION_BY_OBJECTIVE:
                return CONVERSION_BY_OBJECTIVE[o.key]
        return ""

    def missing_add(self, field_key: str, label: str, hint: str, step: int) -> None:
        if not any(m["field"] == field_key for m in self.missing):
            self.missing.append({"field": field_key, "label": label, "hint": hint, "step": step})


# ---------------------------------------------------------------------- parsing helpers
def _parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _duration_days(value, unit) -> int | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    factor = {"day": 1, "week": 7, "month": 30.4, "year": 365}.get(unit or "month", 30.4)
    return int(round(n * factor))


def _gender(name: str) -> str:
    first = (name or "").strip().split(" ")[0] if name else ""
    if first in MASCULINE_HEADS:
        return "m"
    return "f"


def detect_platforms(*texts: str, selected: list[str] | None = None) -> list[str]:
    found = list(dict.fromkeys(selected or []))
    blob = " ".join(t for t in texts if t).lower()
    for key in PLATFORM_ORDER:
        if key in found:
            continue
        for pat in PLATFORMS[key]["patterns"]:
            if re.search(pat, blob, flags=re.IGNORECASE):
                found.append(key)
                break
    return [p for p in PLATFORM_ORDER if p in found]


def detect_type(text: str) -> str | None:
    blob = ar.normalize(text)
    best, best_score = None, 0
    for key, t in PROJECT_TYPES.items():
        score = sum(1 for kw in t.get("keywords", []) if ar.normalize(kw) in blob)
        if score > best_score:
            best, best_score = key, score
    return best


def find_sector(value: str, library_sectors: list[dict], *texts: str) -> tuple[str, dict]:
    """Match the chosen sector (key or name) against the library; fall back to keyword detection."""
    sectors = library_sectors or [{"key": s["key"], "title": s["name"], "data": s} for s in SECTORS]

    def as_profile(item: dict) -> dict:
        data = dict(item.get("data") or {})
        data["name"] = item.get("title") or data.get("name")
        data.setdefault("key", item.get("key"))
        return data

    if value:
        nv = ar.normalize(value)
        for item in sectors:
            prof = as_profile(item)
            if nv in (ar.normalize(prof.get("key", "")), ar.normalize(prof.get("name", ""))):
                return prof["key"], prof
        for item in sectors:
            prof = as_profile(item)
            if any(ar.normalize(a) in nv or nv in ar.normalize(a) for a in prof.get("aliases", []) if a):
                return prof["key"], prof
    blob = ar.normalize(" ".join(t for t in texts if t))
    best, best_score = None, 0
    for item in sectors:
        prof = as_profile(item)
        score = sum(1 for a in prof.get("aliases", []) if a and ar.normalize(a) in blob)
        if score > best_score:
            best, best_score = prof, score
    if best:
        return best["key"], best
    general = next((as_profile(i) for i in sectors if (i.get("key") == "general")), None)
    if general is None:
        general = next(s for s in SECTORS if s["key"] == "general")
    if value:  # custom sector typed by the user: keep their wording
        general = {**general, "name": value.strip(), "key": "custom"}
    return general.get("key", "general"), general


_NUM = r"[\d٠-٩][\d٠-٩,.،]*"
_TARGET_RE = re.compile(rf"(\+?\s*{_NUM}\s*(?:%|٪|ألف|الف|مليون|مليار|k|m)?(?:\s+[؀-ۿ]+){{0,2}})", re.IGNORECASE)


def extract_target(text: str) -> str | None:
    m = _TARGET_RE.search(text or "")
    if not m:
        return None
    return ar.strip_end(m.group(1)).strip()


def classify_objective(text: str) -> str:
    nt = ar.normalize(text)
    best, best_score = "awareness", 0
    for key, obj in OBJECTIVES.items():
        score = sum(len(kw) for kw in obj["keywords"] if ar.normalize(kw) in nt)
        if score > best_score:
            best, best_score = key, score
    return best


_QTY_RE = re.compile(rf"^\s*({_NUM})\s*(.+)$")
_QTY_SUFFIX_RE = re.compile(rf"^(.+?)\s*[:×x\-–]?\s*\(?({_NUM})\)?\s*([؀-ۿ]+)?$")


def parse_deliverable(line: str) -> dict:
    """'12 فيديو شهريًا' -> qty 12, title 'فيديو', timing 'شهريًا'."""
    text = line.strip()
    monthly = bool(re.search(r"شهري|شهريا|شهريًا|كل شهر|في الشهر", text))
    m = _QTY_RE.match(text)
    qty, title = None, text
    if m:
        qty = _to_number(m.group(1))
        title = m.group(2)
    else:
        m2 = _QTY_SUFFIX_RE.match(text)
        if m2 and m2.group(2):
            qty = _to_number(m2.group(2))
            title = m2.group(1) + (" " + m2.group(3) if m2.group(3) else "")
    title = re.sub(r"\s*(شهري[اًا]*|شهريًا|كل شهر|في الشهر)\s*", " ", title).strip(" -–:،,")
    return {"title": title or text, "qty": qty, "monthly": monthly, "raw": text}


def _to_number(s: str) -> int | None:
    s = re.sub(r"[٠-٩]", lambda m: str(ord(m.group()) - 0x0660), s).replace(",", "").replace("،", "")
    try:
        return int(float(s))
    except ValueError:
        return None


# ---------------------------------------------------------------------- main
def analyze(inputs: dict, library: dict[str, list[dict]]) -> Analysis:
    client_in = inputs.get("client") or {}
    project_in = inputs.get("project") or {}
    scope_in = inputs.get("scope") or {}
    services_in = inputs.get("services") or {}
    timeline_in = inputs.get("timeline") or {}
    goals_in = inputs.get("goals") or {}
    prefs = inputs.get("preferences") or {}

    client = (client_in.get("name") or "").strip()
    project = (project_in.get("name") or "").strip()
    description = (project_in.get("description") or "").strip()
    scope_text = (scope_in.get("description") or "").strip()
    all_text = " ".join([project, description, scope_text, project_in.get("challenge") or ""])

    # project type(s): the team may pick several; the first is the main one. "other" carries their own wording.
    chosen = [k for k in dict.fromkeys(project_in.get("types") or [project_in.get("type")]) if k in PROJECT_TYPES]
    type_key = chosen[0] if chosen else (detect_type(all_text) or "other")
    ptype = dict(PROJECT_TYPES[type_key])
    type_other = (project_in.get("type_other") or "").strip()
    if type_key == "other" and type_other:
        ptype.update(label=type_other, nature=f"{type_other} {{li_client}}", nature_short=type_other)
    secondary = [k for k in chosen[1:]]
    if len(chosen) > 1:
        labels = [type_other if k == "other" and type_other else PROJECT_TYPES[k]["label"] for k in chosen if k != "other" or type_other]
        ptype["label"] = ar.join(labels)
        ptype["default_days"] = max(PROJECT_TYPES[k]["default_days"] for k in chosen)
        ptype["default_services"] = list(dict.fromkeys(x for k in chosen for x in PROJECT_TYPES[k]["default_services"]))
    for key, t in PROJECT_TYPES.items():
        if key in (type_key, "other") or key in secondary:
            continue
        if sum(1 for kw in t["keywords"] if ar.normalize(kw) in ar.normalize(all_text)) >= 2:
            secondary.append(key)

    # sector (library profile, completed with built-in knowledge for older libraries)
    sector_key, sector = find_sector(client_in.get("sector") or "", library.get("sectors", []),
                                     client, client_in.get("about") or "", all_text)
    builtin = next((x for x in SECTORS if x["key"] == sector_key), None)
    if builtin:
        sector = {**builtin, **{k: v for k, v in sector.items() if v}}

    platforms = detect_platforms(all_text, scope_text, selected=project_in.get("platforms") or [])
    extra_platforms = ar.split_lines(project_in.get("platforms_other") or "")

    # dates
    start = _parse_date(timeline_in.get("start_date"))
    end = _parse_date(timeline_in.get("end_date"))
    days = _duration_days(timeline_in.get("duration_value"), timeline_in.get("duration_unit"))
    if start and end and end > start:
        days = (end - start).days + 1
    elif start and days:
        end = start + timedelta(days=days - 1)
    elif end and days:
        start = end - timedelta(days=days - 1)
    duration_suggested = not days
    if not days:
        days = ptype["default_days"]
        if start:
            end = start + timedelta(days=days - 1)
    event_date = _parse_date(project_in.get("event_date"))

    # services: chosen ones + "other" text; none chosen -> the system proposes the usual set for the type
    lib_services = {s["key"]: s for s in library.get("services", [])}
    selected = [k for k in (services_in.get("selected") or []) if k in lib_services]
    custom_services = [c for c in (services_in.get("custom") or []) if (c.get("title") or "").strip()]
    custom_services += [{"title": line, "description": ""} for line in ar.split_lines(services_in.get("other") or "")]
    services_suggested = not selected
    if services_suggested:
        selected = [k for k in ptype["default_services"] if k in lib_services]
    services = [lib_services[k] for k in selected]

    # audience: the user's chips/text, otherwise segments proposed from the sector
    aud_in = project_in.get("audience")
    aud_list = [x for x in (aud_in if isinstance(aud_in, list) else ar.split_lines(aud_in or "")) if x]
    aud_list += ar.split_lines(project_in.get("audience_other") or "")
    segments = list(SEGMENTS.get(sector_key) or SEGMENTS["general"])
    audience_suggested = not aud_list
    audience = ar.join(aud_list) if aud_list else ar.join(segments[:3])

    # objectives: chosen categories + "other" text lines; none -> proposed for the project type
    tokens_ctx = {"client": client or "العميل", "bi_client": ar.bi(client) if client else "بالعلامة",
                  "project": project or "المشروع", "audience": "الجمهور المستهدف"}
    objectives: list[Objective] = []
    for key in goals_in.get("objective_keys") or []:
        if key in OBJECTIVES:
            obj = OBJECTIVES[key]
            objectives.append(Objective(key=key, title=obj["label"], statement=_fill(obj["statement"], tokens_ctx),
                                        measures=obj["measures"], target=None, source="user"))
    for line in ar.split_lines(goals_in.get("objectives") or ""):
        key = classify_objective(line)
        obj = OBJECTIVES[key]
        objectives.append(Objective(key=key, title=line, statement=_fill(obj["statement"], tokens_ctx),
                                    measures=obj["measures"], target=extract_target(line), source="user"))
    objectives_suggested = not objectives
    if objectives_suggested:
        default_keys = list(dict.fromkeys(k for t in (chosen or [type_key]) for k in DEFAULTS_BY_TYPE.get(t, ["awareness"])))
        for key in default_keys[:6]:
            obj = OBJECTIVES[key]
            objectives.append(Objective(key=key, title=obj["label"], statement=_fill(obj["statement"], tokens_ctx),
                                        measures=obj["measures"], target=None, source="suggested"))

    kpi_targets = {}
    for line in ar.split_lines(goals_in.get("kpi_targets") or ""):
        if ":" in line:
            k, _, v = line.partition(":")
            kpi_targets[ar.normalize(k)] = v.strip()

    deliverables_input = [parse_deliverable(line) for line in ar.split_lines(goals_in.get("deliverables") or "")]

    team_size = None
    try:
        team_size = int(timeline_in.get("team_size")) if timeline_in.get("team_size") else None
    except (TypeError, ValueError):
        team_size = None

    event_noun = "فعالية"
    for noun in EVENT_NOUNS:
        if noun in all_text:
            event_noun = noun
            break

    a = Analysis(
        inputs=inputs, client=client, client_gender=_gender(client), client_about=(client_in.get("about") or "").strip(),
        project=project, type_key=type_key, ptype=ptype, secondary_types=secondary, sector_key=sector_key, sector=sector,
        platforms=platforms, audience=audience, description=description,
        challenge=(project_in.get("challenge") or "").strip(), location=(project_in.get("location") or "").strip(),
        scope_text=scope_text, out_of_scope=ar.split_lines(scope_in.get("out_of_scope") or ""),
        special_requirements=ar.split_lines(prefs.get("requirements") or ""),
        start=start, end=end, days=days, event_date=event_date, services=services, custom_services=custom_services,
        objectives=objectives, objectives_suggested=objectives_suggested, deliverables_input=deliverables_input,
        kpi_targets=kpi_targets, team_size=team_size, budget=(goals_in.get("budget") or "").strip(),
        show_budget=bool(goals_in.get("show_budget")), tone=prefs.get("tone") if prefs.get("tone") in TONES else "corporate",
        detail=prefs.get("detail") if prefs.get("detail") in DETAILS else "medium", prefs=prefs, event_noun=event_noun,
        audience_suggested=audience_suggested, segments=segments, extra_platforms=extra_platforms,
        chosen_types=chosen,
        cities=mentioned_cities(" ".join([project, description, prefs.get("requirements") or "", project_in.get("location") or ""])),
    )

    # ---- only the essentials are required; everything else the system proposes and lists for review
    if not client:
        a.missing_add("client.name", "اسم العميل", "اسم العميل مطلوب ليظهر في الغلاف والنصوص.", 1)
    if not project:
        a.missing_add("project.name", "اسم المشروع", "اسم المشروع مطلوب للغلاف والعناوين.", 1)
    if audience_suggested:
        a.suggested.append("الجمهور المستهدف")
    if objectives_suggested:
        a.suggested.append("أهداف المشروع")
    if services_suggested:
        a.suggested.append("الخدمات")
    if duration_suggested:
        a.suggested.append(f"المدة ({ar.duration_phrase(days)})")
    if not client_in.get("sector"):
        a.suggested.append(f"القطاع ({sector.get('name', '')})")
    return a


def _fill(template: str, ctx: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), m.group(0))), template)
