"""Claude as the writer: the request it gets, and the guards on what it sends back."""
import copy
import json

import pytest

from app.ai import author
from app.data import repositories as repo
from app.services import proposals as svc
from tests.conftest import make_inputs

IDEA = "نبي نركز على الرياض ونجيب مشاهير"


@pytest.fixture()
def celebs_list():
    repo.celebrities.clear()
    repo.celebrities.add_many([
        {"name": "سارة الرياض", "platforms": "سناب شات", "followers": "1,200,000", "category": "لايف ستايل", "city": "الرياض"},
        {"name": "فهد جدة", "platforms": "تيك توك", "followers": "800,000", "category": "سيارات", "city": "جدة"},
        {"name": "نورة القهوة", "platforms": "إنستقرام", "followers": "450,000", "category": "قهوة ومطاعم", "city": "الرياض"},
    ], source="test.xlsx")
    yield
    repo.celebrities.clear()


def _answer(**over):
    base = {
        "cover_subtitle": "خطة حضور في الرياض مع مشاهير المدينة",
        "intro": {"subtitle": "لماذا الرياض", "lead": "نقترح أن تبدأ الحملة من أحياء الرياض. حققنا 250% نموًا لعملاء سابقين.",
                  "paragraphs": ["فقرة ثانية محددة."]},
        "idea": {"subtitle": "الفكرة", "name": "مشوار الرياض", "idea": "فكرة كبيرة تُبنى حول مشاوير الرياض اليومية.",
                 "message": "الرسالة.", "slogans": ["شعار ١", "شعار ٢", "شعار ٣"], "why": "لأن الجمهور يعيش في الرياض.",
                 "execution": ["خطوة أولى", "خطوة ثانية"]},
        "celebrities": {"subtitle": "", "intro": "اخترنا من القائمة.", "criteria": ["القرب من الجمهور"],
                        "picks": [{"ref": "c1", "role": "وجه الحملة", "content": "مشاوير يومية", "why": "تعيش في الرياض ولها 5 ملايين متابع"},
                                  {"ref": "c99", "role": "دخيل", "content": "x", "why": "y"},
                                  {"ref": "محمد عبده", "role": "ليس في القائمة", "content": "x", "why": "y"}]},
        "methodology": {"subtitle": "", "intro": "مراحل التنفيذ.", "phases": [
            {"title": "التخطيط مع العميل", "role": "plan", "weight": 2, "goal": "هدف", "activities": ["أ", "ب"], "outputs": ["خطة"], "owner": "مدير المشروع"},
            {"title": "التعاقد مع المشاهير", "role": "prepare", "weight": 3, "goal": "هدف", "activities": ["ج"], "outputs": [], "owner": "مسؤول المشاهير"},
            {"title": "إطلاق مشوار الرياض", "role": "execute", "weight": 6, "goal": "هدف", "activities": ["د", "هـ"], "outputs": [], "owner": "فريق المحتوى"},
            {"title": "التقرير الختامي", "role": "report", "weight": 1, "goal": "هدف", "activities": ["و"], "outputs": [], "owner": "مدير المشروع"}]},
        "deliverables": {"subtitle": "", "intro": "", "rows": [{"title": "مقاطع مشاهير", "description": "وصف", "qty": 12, "unit": "مقطع", "timing": "التنفيذ"},
                                                             {"title": "تقرير", "description": "وصف", "qty": None, "unit": "", "timing": "النهاية"}]},
    }
    base.update(over)
    return base


def test_request_builds_on_the_idea_and_carries_profile_and_list(celebs_list, library, settings):
    inputs = make_inputs(project={"type": "influencer", "description": IDEA, "platforms": ["snapchat"]})
    lib, st = svc._context(inputs)
    assert [p["name"] for p in lib["celebrities"]][:2] == ["سارة الرياض", "نورة القهوة"]  # Riyadh first
    stage1 = svc.ai_request(inputs=inputs)
    assert stage1["stage"] == 1 and stage1["requests"][0]["sections"] == ["idea", "activations"]
    stage2 = svc.ai_request(inputs=inputs, concept={"idea": {"name": "مشوار الرياض"}})
    groups = [r["sections"] for r in stage2["requests"]]
    assert ["celebrities", "content_plan"] in groups and not any("team" in g for g in groups)
    assert all("مشوار الرياض" in r["prompt"] and "cover_subtitle" not in r["schema"]["properties"] for r in stage2["requests"])
    req = next(r for r in stage2["requests"] if "celebrities" in r["sections"])
    assert "ابنِ عليها ولا تنسخها" in req["prompt"] and IDEA in req["prompt"]
    assert "c1 | سارة الرياض" in req["prompt"]
    assert stage1["requests"][0]["schema"]["required"][0] == "cover_subtitle"
    assert "لا تخترع أرقامًا" in req["system"]


def test_apply_writes_sections_and_drops_what_is_not_true(celebs_list, library, settings):
    inputs = make_inputs(project={"type": "influencer", "description": IDEA, "platforms": ["snapchat"]})
    lib, st = svc._context(inputs)
    from app.generator import engine
    out = engine.generate(inputs, lib, st, seed=3)
    doc = out["doc"]
    written = author.apply(doc, _answer(), inputs, lib, st)
    assert {"intro", "idea", "celebrities", "methodology", "deliverables", "timeline"} <= set(written)
    text = json.dumps(doc, ensure_ascii=False)
    assert "250%" not in text and "نقترح أن تبدأ الحملة من أحياء الرياض" in text  # invented figure dropped, rest kept
    assert "5 ملايين" not in text  # the model may not state follower numbers…
    table = next(b for s in doc["sections"] if s["type"] == "celebrities" for b in s["blocks"] if b["type"] == "table")
    assert [r["name"] for r in table["rows"]] == ["سارة الرياض"]  # …and may not name anyone off the list
    assert "1,200,000" in table["rows"][0]["reach"]  # numbers come from the team's sheet
    tl = next(b for s in doc["sections"] if s["type"] == "timeline" for b in s["blocks"] if b["type"] == "timeline")
    assert {r["phase"] for r in tl["rows"]} == {"التخطيط مع العميل", "التعاقد مع المشاهير", "إطلاق مشوار الرياض", "التقرير الختامي"}
    assert any(r["owner"] == "مسؤول المشاهير" for r in tl["rows"])
    assert doc["cover"]["subtitle"] == "خطة حضور في الرياض مع مشاهير المدينة"
    rows = next(b for s in doc["sections"] if s["type"] == "deliverables" for b in s["blocks"] if b["type"] == "deliverables")["rows"]
    assert rows[0]["qty"] == 12 and rows[1]["qty"] is None


def test_writer_failure_keeps_the_rules_document(library, settings, monkeypatch):
    monkeypatch.setattr(author, "provider", lambda: "cli")

    def boom(req):
        raise author.AuthorError("offline")
    monkeypatch.setattr(author, "call", boom)
    p = svc.create_from_inputs(make_inputs(project={"description": IDEA}))
    assert p["doc"]["ai"]["error"] and len(p["doc"]["sections"]) > 8


def test_server_writer_is_used_for_generation_and_section_rewrite(celebs_list, monkeypatch):
    monkeypatch.setattr(author, "provider", lambda: "cli")
    calls = []

    def fake(req):
        calls.append(req)
        if "النسخة الحالية من القسم" in req["prompt"]:
            return {"intro": {"subtitle": "", "lead": "افتتاحية جديدة مختلفة تمامًا.", "paragraphs": []}}
        return {k: v for k, v in _answer().items() if k in req["sections"] or k == "cover_subtitle"}
    monkeypatch.setattr(author, "call", fake)
    p = svc.create_from_inputs(make_inputs(project={"type": "influencer", "description": IDEA}))
    assert "مشوار الرياض" in json.dumps(p["doc"], ensure_ascii=False)
    intro = next(s for s in p["doc"]["sections"] if s["type"] == "intro")
    new = svc.regenerate_section(p["id"], intro["id"])
    assert new["blocks"][0]["text"] == "افتتاحية جديدة مختلفة تمامًا." and new["regen"] == 1
    assert len(calls) >= 4  # creative core, then the parallel groups
    assert calls[-1]["sections"] == ["intro"] and "مشوار الرياض" in calls[-1]["prompt"]


def test_browser_edition_applies_content_it_fetched(celebs_list):
    inputs = make_inputs(project={"type": "influencer", "description": IDEA})
    p = svc.create_from_inputs(copy.deepcopy(inputs), ai_content=_answer())
    assert p["doc"]["ai"]["provider"] == "browser" and "idea" in p["doc"]["ai"]["sections"]


def test_clean_keeps_counts_and_years_but_not_invented_metrics():
    allowed = {"6"}
    assert author.clean("ننتج 12 مقطعًا خلال 3 أشهر.", allowed) == "ننتج 12 مقطعًا خلال 3 أشهر."
    assert author.clean("يتماشى مع رؤية 2030.", allowed) == "يتماشى مع رؤية 2030."
    assert author.clean("نرفع المبيعات 40%. ونبني الحضور.", allowed) == "ونبني الحضور."
    assert author.clean("جمهور يتجاوز 500 ألف شخص.", allowed) == ""
    assert author.clean("خلال 6 أشهر.", allowed) == "خلال 6 أشهر."
