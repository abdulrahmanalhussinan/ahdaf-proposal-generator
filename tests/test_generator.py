import json
import re

import pytest

from app.core import arabic as ar
from app.generator import engine
from app.generator.knowledge.project_types import TYPE_ORDER
from tests.conftest import make_inputs

REQUIRED = {"intro", "understanding", "objectives", "idea", "activations", "scope", "methodology", "deliverables",
            "timeline", "kpis", "conclusion"}
OPTIONAL = {"team", "governance", "assumptions", "risks"}
ALL_EXTRA = {"extra_sections": sorted(OPTIONAL)}
NARRATIVE = {"paragraph", "lead", "callout"}


def narrative_texts(doc):
    for s in doc["sections"]:
        if s["type"] == "about":  # official company copy from settings
            continue
        for b in s["blocks"]:
            if b["type"] in NARRATIVE:
                yield s["type"], b["text"]
            for it in b.get("items") or []:
                if isinstance(it, dict) and b["type"] in ("cards", "objectives"):
                    yield s["type"], it.get("text", "")


@pytest.mark.parametrize("ptype", TYPE_ORDER)
def test_every_project_type_generates_all_required_sections(ptype, library, settings):
    out = engine.generate(make_inputs(project={"type": ptype, "name": f"مشروع {ptype}"}), library, settings, seed=3)
    types = {s["type"] for s in out["doc"]["sections"]}
    assert REQUIRED <= types
    assert not types & OPTIONAL  # filler sections are off unless asked for
    assert out["doc"]["cover"]["title"] == f"مشروع {ptype}"


def test_optional_sections_come_back_when_asked_for(library, settings):
    out = engine.generate(make_inputs(preferences=ALL_EXTRA), library, settings, seed=3)
    assert OPTIONAL <= {s["type"] for s in out["doc"]["sections"]}


def test_team_idea_is_not_pasted_into_the_document(library, settings):
    idea = "نبي نركز على الرياض ونجيب مشاهير يزورون الفروع"
    inputs = make_inputs(project={"description": idea}, preferences={"requirements": "التسليم قبل رمضان"})
    doc = engine.generate(inputs, library, settings, seed=2)["doc"]
    text = json.dumps(doc, ensure_ascii=False)
    assert idea not in text and "التسليم قبل رمضان" not in text
    und = next(s for s in doc["sections"] if s["type"] == "understanding")
    assert "الرياض" in json.dumps(und, ensure_ascii=False)  # the city focus is understood and built on


@pytest.mark.parametrize("ptype", TYPE_ORDER)
def test_no_invented_numbers(ptype, library, settings):
    """Every digit in generated narrative must come from the inputs, the dates/duration derived from
    them, or the number of methodology phases — never from thin air."""
    inputs = make_inputs(project={"type": ptype, "name": "مشروع الاختبار"}, preferences=ALL_EXTRA)
    out = engine.generate(inputs, library, settings, seed=11)
    allowed = set(re.findall(r"\d+", json.dumps(inputs, ensure_ascii=False)))
    allowed |= {"2026", "2027", "1", "2", "6", "30"}  # start/end years, durations, day numbers of dates
    for s in out["doc"]["sections"]:
        for b in s["blocks"]:
            if b["type"] == "phases":
                allowed.add(str(len(b["items"])))
    offenders = []
    for sec, text in narrative_texts(out["doc"]):
        for n in re.findall(r"\d+", text):
            if n not in allowed:
                offenders.append((sec, n, text[:80]))
    assert not offenders, offenders


def test_missing_audience_is_proposed_from_the_sector(library, settings):
    out = engine.generate(make_inputs(), library, settings, seed=1)
    assert out["meta"]["missing"] == []
    assert "الجمهور المستهدف" in out["meta"]["suggested"]
    und = next(s for s in out["doc"]["sections"] if s["type"] == "understanding")
    cards = next(b for b in und["blocks"] if b["type"] == "cards")
    audience = next(c for c in cards["items"] if c["title"].startswith("الجمهور المستهدف"))
    assert "المسافرون" in audience["text"] and "[[" not in audience["text"]


def test_system_proposes_creative_sections_from_surface_inputs(library, settings):
    minimal = {"client": {"name": "شركة النموذج"}, "project": {"name": "حساب تيك توك", "type": "social_media"},
               "preferences": {}}
    doc = engine.generate(minimal, library, settings, seed=3)["doc"]
    types = [s["type"] for s in doc["sections"]]
    assert {"idea", "activations", "content_plan"} <= set(types)
    idea = next(s for s in doc["sections"] if s["type"] == "idea")
    assert any(b["type"] == "callout" and b["label"] == "الرسالة الأساسية" for b in idea["blocks"])
    acts = next(b for s in doc["sections"] if s["type"] == "activations" for b in s["blocks"] if b["type"] == "cards")
    assert len(acts["items"]) >= 4
    week = next(b for s in doc["sections"] if s["type"] == "content_plan" for b in s["blocks"] if b["type"] == "table")
    assert len(week["rows"]) == 7
    assert "[[" not in json.dumps(doc, ensure_ascii=False)


def test_ideas_differ_by_sector_and_regenerate_offers_another_concept(library, settings):
    car = engine.generate(make_inputs(), library, settings, seed=3)["doc"]
    food = engine.generate(make_inputs(client={"name": "مطعم", "sector": "food_beverage"}), library, settings, seed=3)["doc"]
    lead = lambda d: next(b["text"] for s in d["sections"] if s["type"] == "idea" for b in s["blocks"] if b["type"] == "lead")
    assert lead(car) != lead(food)
    idea = next(s for s in car["sections"] if s["type"] == "idea")
    again = engine.regenerate_section(make_inputs(), car, idea["id"], library, settings)
    assert next(b["text"] for b in again["blocks"] if b["type"] == "lead") != lead(car)


def test_other_fields_are_used(library, settings):
    inputs = make_inputs(project={"type": "other", "type_other": "تنظيم رحلة تعريفية للإعلاميين", "platforms_other": "ثريدز"},
                         services={"other": "تصميم كتيب الرحلة"})
    out = engine.generate(inputs, library, settings, seed=2)
    assert out["meta"]["type_label"] == "تنظيم رحلة تعريفية للإعلاميين"
    assert "تصميم كتيب الرحلة" in out["meta"]["service_labels"]
    assert "ثريدز" in out["meta"]["analysis"]["platforms"]


def test_objective_numbers_become_targets(library, settings):
    out = engine.generate(make_inputs(goals={"objectives": "نمو المتابعين 30%\nرفع الوعي بالعلامة"}), library, settings, seed=2)
    obj = next(b for s in out["doc"]["sections"] if s["type"] == "objectives" for b in s["blocks"] if b["type"] == "objectives")
    assert obj["items"][0]["target"] == "30%"
    assert obj["items"][1]["target"].startswith("يُحدد")
    kpis = next(b for s in out["doc"]["sections"] if s["type"] == "kpis" for b in s["blocks"] if b["type"] == "kpis")
    growth = next(k for k in kpis["items"] if k["name_en"] == "Follower Growth")
    assert growth["target"] == "30%"
    assert all(k["target"] for k in kpis["items"])


def test_suggested_objectives_are_flagged(library, settings):
    out = engine.generate(make_inputs(), library, settings, seed=2)
    assert out["meta"]["objectives_suggested"] is True
    obj = next(b for s in out["doc"]["sections"] if s["type"] == "objectives" for b in s["blocks"] if b["type"] == "objectives")
    assert all(i["suggested"] for i in obj["items"])


def test_projects_of_different_nature_produce_different_proposals(library, settings):
    tiktok = engine.generate(make_inputs(preferences=ALL_EXTRA), library, settings, seed=5)["doc"]
    event = engine.generate(make_inputs(client={"name": "مجموعة الأفق العقارية", "sector": "real_estate"},
                                        project={"type": "event", "name": "حفل تدشين المشروع", "platforms": [],
                                                 "description": "حفل تدشين للمشروع السكني بحضور الشركاء والإعلام."},
                                        timeline={"duration_value": 6, "duration_unit": "week"}, preferences=ALL_EXTRA),
                            library, settings, seed=5)["doc"]

    def phases(doc):
        return [i["title"] for s in doc["sections"] if s["type"] == "methodology" for b in s["blocks"] if b["type"] == "phases" for i in b["items"]]

    def roles(doc):
        return {m["role"] for s in doc["sections"] if s["type"] == "team" for b in s["blocks"] if b["type"] == "team" for m in b["members"]}

    assert set(phases(tiktok)).isdisjoint(phases(event))
    assert "مدير الفعالية" in roles(event) and "مدير الفعالية" not in roles(tiktok)
    t_text = " ".join(t for _, t in narrative_texts(tiktok))
    e_text = " ".join(t for _, t in narrative_texts(event))
    assert "تيك توك" in t_text and "تيك توك" not in e_text
    assert "الضيف" in e_text


def test_sentences_are_not_repeated_across_sections(library, settings):
    doc = engine.generate(make_inputs(goals={"objectives": "زيادة الحجوزات"}), library, settings, seed=8)["doc"]
    texts = [t for _, t in narrative_texts(doc) if len(t) > 40]
    assert len(texts) == len(set(texts))


def test_tone_changes_the_writing(library, settings):
    formal = engine.generate(make_inputs(preferences={"tone": "formal"}), library, settings, seed=4)["doc"]
    marketing = engine.generate(make_inputs(preferences={"tone": "marketing"}), library, settings, seed=4)["doc"]
    lead = lambda d: next(b["text"] for s in d["sections"] if s["type"] == "intro" for b in s["blocks"] if b["type"] == "lead")
    assert lead(formal) != lead(marketing)
    assert lead(formal).startswith(("يسر", "تتقدم"))


def test_detail_level_changes_depth(library, settings):
    brief = engine.generate(make_inputs(preferences={"detail": "brief", **ALL_EXTRA}), library, settings, seed=4)["doc"]
    adv = engine.generate(make_inputs(preferences={"detail": "advanced", **ALL_EXTRA}), library, settings, seed=4)["doc"]
    count = lambda d, t, key: len(next(b[key] for s in d["sections"] if s["type"] == t for b in s["blocks"] if key in b and isinstance(b[key], list) and b["type"] in ("kpis", "risks")))
    assert count(brief, "kpis", "items") < count(adv, "kpis", "items")
    assert count(brief, "risks", "rows") < count(adv, "risks", "rows")


def test_regenerate_section_gives_new_wording_and_keeps_identity(library, settings):
    inputs = make_inputs(goals={"objectives": "رفع الوعي"})
    doc = engine.generate(inputs, library, settings, seed=9)["doc"]
    und = next(s for s in doc["sections"] if s["type"] == "understanding")
    und["title"] = "عنوان عدّله المستخدم"
    new = engine.regenerate_section(inputs, doc, und["id"], library, settings)
    assert new["id"] == und["id"] and new["title"] == "عنوان عدّله المستخدم"
    assert new["regen"] == 1
    old_text = json.dumps(und["blocks"], ensure_ascii=False)
    new_text = json.dumps(new["blocks"], ensure_ascii=False)
    assert old_text != new_text
    tone = engine.regenerate_section(inputs, doc, doc["sections"][1]["id"], library, settings, tone="formal")
    assert tone["tone"] == "formal"


def test_timeline_is_inside_project_dates_and_event_day_is_pinned(library, settings):
    inputs = make_inputs(project={"type": "event", "name": "حفل", "event_date": "2026-12-10", "platforms": []},
                         timeline={"duration_value": 7, "duration_unit": "week", "start_date": "2026-10-25"})
    doc = engine.generate(inputs, library, settings, seed=1)["doc"]
    tl = next(b for s in doc["sections"] if s["type"] == "timeline" for b in s["blocks"] if b["type"] == "timeline")
    assert tl["start_date"] == "2026-10-25" and tl["total_days"] == 49
    assert all(0 <= r["offset"] and r["offset"] + r["days"] <= tl["total_days"] + 1 for r in tl["rows"])
    day = next(m for m in tl["milestones"] if m["label"].startswith("يوم الفعالية"))
    assert day["offset"] == 46  # 10 Dec - 25 Oct


def test_user_deliverables_merge_with_library_and_scale_monthly(library, settings):
    inputs = make_inputs(services={"selected": ["reels", "reporting"]}, goals={"deliverables": "12 فيديو شهريًا"})
    doc = engine.generate(inputs, library, settings, seed=1)["doc"]
    rows = next(b for s in doc["sections"] if s["type"] == "deliverables" for b in s["blocks"] if b["type"] == "deliverables")["rows"]
    reels = next(r for r in rows if "ريلز" in r["title"])
    assert reels["qty"] == 72 and "12 شهريًا" in reels["description"]
    assert sum(1 for r in rows if "فيديو" in r["title"]) == 1


def test_team_size_is_respected(library, settings):
    doc = engine.generate(make_inputs(timeline={"team_size": 3}, preferences={"extra_sections": ["team"]}), library, settings, seed=1)["doc"]
    members = next(b for s in doc["sections"] if s["type"] == "team" for b in s["blocks"] if b["type"] == "team")["members"]
    assert sum(m["count"] for m in members) == 3
    assert members[0]["role"] == "مدير المشروع"


def test_arabic_helpers():
    assert ar.li("الشركة") == "للشركة" and ar.li("شركة أ") == "لشركة أ" and ar.li("Nike") == "لـNike"
    assert ar.join(["أ", "ب", "ج"]) == "أ، وب، وج"
    assert ar.count(1, "month") == "شهر واحد" and ar.count(2, "month") == "شهران"
    assert ar.count(5, "month") == "5 أشهر" and ar.count(12, "month") == "12 شهرًا"
    assert ar.normalize("أهداف") == ar.normalize("اهداف")
    assert ar.normalize("مؤسسة") == ar.normalize("مؤسسه")


@pytest.mark.parametrize("design", ["ahdaf", "night", "bold", "minimal"])
def test_every_design_exports_to_powerpoint(design, library, settings):
    import io
    import zipfile
    from app.exporters.pptx_export import build_pptx
    inputs = make_inputs(preferences={"design": design})
    doc = engine.generate(inputs, library, settings, seed=4)["doc"]
    assert doc["theme"] == design
    data = build_pptx({"doc": doc, "number": "AHD-T"}, settings)
    assert len([n for n in zipfile.ZipFile(io.BytesIO(data)).namelist() if n.startswith("ppt/slides/slide")]) > 15
