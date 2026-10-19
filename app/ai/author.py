"""Claude writes the proposal.

The rules engine (app.generator) always builds a complete document first: section order, the
schedule maths, the KPI library and AHDAF's official copy. When a writer is available, Claude then
thinks the project through and writes the substance of every section from the brief, the team's own
idea, the client's profile and the team's celebrity list. The team's words are treated as a
direction to build on, never as text to paste.

Writers, in order of preference (AI_PROVIDER=auto):
  - "api": an Anthropic API key on the server (ANTHROPIC_API_KEY in .env);
  - "cli": Claude Code installed on this machine (`claude -p`), using the account it is signed in to;
  - in the browser edition the visitor's own key is used from their browser (web/js/lib/ai.js) with
    the request built by `build_request()` and the answer applied by `apply()`.

Facts stay facts: celebrity names can only come from the list (by reference id), follower numbers
are taken from the list rather than from the model, and sentences with figures that appear nowhere
in the inputs, the profile or the list are dropped. Any failure falls back to the rules-engine text.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from app import config
from app.core import arabic as ar
from app.data import repositories as repo
from app.generator import engine as E
from app.generator.analyzer import DETAILS, TONES, analyze
from app.services import celebrities as celebs

log = logging.getLogger("ahdaf.ai")
PROMPTS_DIR = Path(__file__).parent / "prompts"

# Sections Claude writes. Everything else (cover facts, «عن أهداف», budget, past projects) is not his to write.
WRITABLE = ["intro", "understanding", "objectives", "idea", "activations", "celebrities", "content_plan", "scope",
            "methodology", "deliverables", "kpis", "conclusion", "team", "governance", "assumptions", "risks", "custom"]
ROLES = ["plan", "prepare", "execute", "event_day", "optimize", "report"]
# Writing happens in two stages so it takes minutes, not many minutes: first the creative core (the
# idea and the activations built on it), then the rest in parallel calls that all build on that core.
STAGE_ONE = ["idea", "activations"]
STAGE_TWO = [["intro", "understanding", "conclusion"], ["objectives", "kpis", "scope"], ["celebrities", "content_plan"],
             ["methodology", "deliverables"], ["team", "governance", "assumptions", "risks"]]
COUNTS = {  # how much to write, by detail level
    "brief": {"activations": 4, "celebrities": 4, "objectives": 3, "kpis": 4, "deliverables": 7, "phases": "3 إلى 4", "pillars": 3, "cards": 4},
    "medium": {"activations": 6, "celebrities": 6, "objectives": 4, "kpis": 6, "deliverables": 10, "phases": "4 إلى 5", "pillars": 4, "cards": 5},
    "advanced": {"activations": 9, "celebrities": 8, "objectives": 5, "kpis": 8, "deliverables": 14, "phases": "5 إلى 6", "pillars": 5, "cards": 6},
}
ICONS = ["spark", "users", "flag", "chat", "pin", "calendar", "pen", "eye", "chart", "shield", "star", "target"]
MAX_PROFILE_CHARS = 45_000


class AuthorError(Exception):
    pass


# =============================================================================== availability
def _cli_path() -> str | None:
    if config.CLAUDE_CLI:
        return config.CLAUDE_CLI if Path(config.CLAUDE_CLI).exists() or shutil.which(config.CLAUDE_CLI) else None
    found = shutil.which("claude")
    if found:
        return found
    for cand in (Path.home() / ".local" / "bin" / "claude.exe", Path.home() / ".local" / "bin" / "claude",
                 Path.home() / ".claude" / "local" / "claude"):
        if cand.exists():
            return str(cand)
    return None


@lru_cache(maxsize=1)
def provider() -> str | None:
    mode = config.AI_PROVIDER
    if mode in ("rules", "off", "none"):
        return None
    if mode in ("auto", "claude", "api") and config.ANTHROPIC_API_KEY:
        return "api"
    if mode in ("auto", "cli") and _cli_path():
        return "cli"
    return None


def status() -> dict:
    p = provider()
    labels = {"api": "Claude عبر مفتاح API على الخادم", "cli": "Claude عبر Claude Code المثبت على هذا الجهاز"}
    model = config.CLAUDE_MODEL if p == "api" else config.CLAUDE_CLI_MODEL if p == "cli" else None
    return {"provider": p or "rules", "enabled": bool(p), "model": model, "label": labels.get(p, "محرك الكتابة الداخلي")}


# =============================================================================== prompt
@lru_cache(maxsize=8)
def _prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _s(desc: str = "") -> dict:
    return {"type": "string", "description": desc} if desc else {"type": "string"}


def _arr(items: dict, desc: str = "") -> dict:
    out = {"type": "array", "items": items}
    if desc:
        out["description"] = desc
    return out


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


TITLED = _obj({"title": _s(), "text": _s()})
CUSTOM = _obj({"title": _s(), "subtitle": _s(), "paragraphs": _arr(_s()), "points": _arr(_s()), "cards": _arr(TITLED)})
SECTION_SCHEMAS = {
    "intro": _obj({"subtitle": _s(), "lead": _s(), "paragraphs": _arr(_s())}),
    "understanding": _obj({"subtitle": _s(), "paragraphs": _arr(_s()), "cards": _arr(TITLED), "insight": _s()}),
    "objectives": _obj({"subtitle": _s(), "intro": _s(), "items": _arr(_obj({"title": _s(), "text": _s(), "measure": _s(), "target": _s()}))}),
    "idea": _obj({"subtitle": _s(), "name": _s(), "idea": _s(), "message": _s(), "slogans": _arr(_s()), "why": _s(),
                  "execution": _arr(_s())}),
    "activations": _obj({"subtitle": _s(), "intro": _s(), "items": _arr(TITLED)}),
    "celebrities": _obj({"subtitle": _s(), "intro": _s(), "picks": _arr(_obj({"ref": _s("معرّف الشخص من قائمة المرشحين مثل c12"),
                                                                                "role": _s(), "content": _s(), "why": _s()})),
                         "criteria": _arr(_s())}),
    "content_plan": _obj({"subtitle": _s(), "intro": _s(), "pillars": _arr(_obj({"title": _s(), "text": _s(), "examples": _arr(_s())})),
                          "week": _arr(_obj({"day": _s(), "platform": _s(), "format": _s(), "pillar": _s(), "idea": _s()}))}),
    "scope": _obj({"subtitle": _s(), "intro": _s(), "groups": _arr(_obj({"title": _s(), "items": _arr(TITLED)}))}),
    "methodology": _obj({"subtitle": _s(), "intro": _s(), "phases": _arr(_obj({
        "title": _s(), "role": {"type": "string", "enum": ROLES}, "weight": {"type": "integer", "description": "الوزن النسبي لمدة المرحلة من 1 إلى 10"},
        "goal": _s(), "activities": _arr(_s()), "outputs": _arr(_s()), "owner": _s("المسؤول، مثل: مدير المشروع، فريق المحتوى")})),
        "timeline_subtitle": _s(), "timeline_intro": _s()}),
    "deliverables": _obj({"subtitle": _s(), "intro": _s(), "rows": _arr(_obj({
        "title": _s(), "description": _s(), "qty": {"type": ["integer", "null"]}, "unit": _s(), "timing": _s()}))}),
    "kpis": _obj({"subtitle": _s(), "intro": _s(), "items": _arr(_obj({"name": _s(), "definition": _s(), "measurement": _s(),
                                                                         "frequency": _s(), "target": _s()}))}),
    "conclusion": _obj({"subtitle": _s(), "lead": _s(), "paragraph": _s(), "next_steps": _arr(TITLED)}),
    "team": _obj({"subtitle": _s(), "intro": _s(), "members": _arr(_obj({"role": _s(), "count": {"type": "integer"},
                                                                          "responsibilities": _arr(_s())}))}),
    "governance": _obj({"subtitle": _s(), "intro": _s(), "cards": _arr(TITLED)}),
    "assumptions": _obj({"subtitle": _s(), "intro": _s(), "items": _arr(_s())}),
    "custom": CUSTOM,
    "custom_sections": _arr(CUSTOM),
    "risks": _obj({"subtitle": _s(), "intro": _s(), "rows": _arr(_obj({
        "risk": _s(), "likelihood": {"type": "string", "enum": ["مرتفعة", "متوسطة", "منخفضة"]},
        "impact": {"type": "string", "enum": ["مرتفع", "متوسط", "منخفض"]}, "mitigation": _s()}))}),
}

GUIDE = {
    "intro": "lead: افتتاحية خاصة بهذا العميل وهذا المشروع في جملتين، تقول ماذا نقترح بالتحديد. paragraphs: فقرة أو فقرتان تلخصان الفكرة والنهج ولماذا يناسبان هذا العميل الآن.",
    "understanding": "paragraphs: فقرتان عن العميل وموقفه وجمهوره والفرصة (من الملف التعريفي إن وُجد). cards: {cards} بطاقات محددة (مثل: من هو العميل، الجمهور وما يحركه، التحدي الحقيقي، الفرصة، السياق أو المكان أو الموسم). insight: الخلاصة الاستراتيجية التي يُبنى عليها العرض في جملة واحدة قوية.",
    "objectives": "{objectives} أهداف محددة لهذا المشروع. measure: كيف يُقاس الهدف. target: الرقم إن أعطاه الفريق فقط، وإلا «يُحدد مع العميل».",
    "idea": "name: اسم قصير جذاب للفكرة/الحملة. idea: شرح الفكرة الكبيرة في 4 إلى 6 جمل: ما هي، وكيف يعيشها الجمهور، وما الذي يجعلها تخص هذا العميل. message: الرسالة الأساسية في جملة. slogans: 3 شعارات مختلفة. why: لماذا تنجح هذه الفكرة مع هذا الجمهور (فقرة). execution: 5 إلى 7 خطوات تحوّل الفكرة إلى تنفيذ فعلي.",
    "activations": "{activations} أفكار تفعيلية مختلفة ومفصلة مبنية على الفكرة. لكل فكرة: title اسم الفكرة، text من 2 إلى 4 جمل: ماذا يحدث بالضبط، وأين، ومتى في المشروع، وعلى أي منصة، وما الذي يخرج منها.",
    "celebrities": "اختر حتى {celebrities} أشخاص من «قائمة المرشحين» فقط، الأنسب للفكرة والمدينة والجمهور، واكتب ref بالمعرّف كما هو. role: دوره في الحملة. content: المحتوى المحدد المقترح له. why: لماذا هو (من بيانات القائمة، دون أرقام من عندك). criteria: 3 أو 4 معايير اخترنا بها.",
    "content_plan": "pillars: {pillars} محاور محتوى، لكل محور text يشرح هدفه و examples من 2 إلى 3 أفكار منشورات محددة. week: نموذج أسبوع من الأحد إلى السبت (7 صفوف) بمحتوى محدد مرتبط بالفكرة، والمنصات من منصات المشروع.",
    "scope": "groups: من 3 إلى 5 مجموعات تغطي كل ما سننفذه (مثل: الاستراتيجية، المحتوى والإنتاج، المشاهير، التفعيلات، الإعلانات، القياس). لكل بند text محدد بهذا المشروع.",
    "methodology": "phases: من {phases} مراحل مرتبة زمنيًا، أسماؤها خاصة بهذا المشروع. role من القائمة المسموحة، weight وزن نسبي لطول المرحلة، goal، activities من 3 إلى 5 أنشطة محددة، outputs، owner. timeline_subtitle و timeline_intro: سطر وجملتان لقسم الجدول الزمني تصفان إيقاع هذا المشروع تحديدًا.",
    "custom": "اكتب هذا القسم من جديد بنفس عنوانه وغرضه: paragraphs و points و cards (ما يناسبه منها).",
    "custom_sections": "أقسام إضافية لكل ما طلبه الفريق صراحةً في «طلب الفريق بالتفصيل» ولا تغطيه الأقسام الأخرى (حتى 3 أقسام)، لكل قسم title واضح ومحتوى كامل. إن لم يطلب شيئًا كهذا فأعد مصفوفة فارغة.",
    "deliverables": "rows: نحو {deliverables} مخرجات ملموسة نسلّمها، بكميات منطقية لمدة المشروع (الكمية رقم صحيح أو null إن لم تكن قابلة للعد)، والوحدة، والتوقيت.",
    "kpis": "{kpis} مؤشرات أداء مرتبطة بالأهداف والفكرة. target: الرقم إن أعطاه الفريق فقط، وإلا «يُحدد مع العميل».",
    "conclusion": "lead: خاتمة خاصة بهذا العرض في جملتين. paragraph: فقرة قصيرة. next_steps: 3 أو 4 خطوات تالية عملية.",
    "team": "members: الأدوار الفعلية التي يحتاجها هذا المشروع فقط، مع العدد ومسؤوليتين لكل دور.",
    "governance": "cards: 4 أو 5 بطاقات عملية عن التواصل والاعتمادات والتقارير الخاصة بهذا المشروع.",
    "assumptions": "items: من 5 إلى 7 متطلبات وافتراضات عملية يحتاجها التنفيذ من العميل.",
    "risks": "rows: من 4 إلى 6 مخاطر حقيقية لهذا المشروع مع آلية التعامل.",
}


def _profile_text(inputs: dict) -> tuple[str, dict | None]:
    prof = (inputs.get("client") or {}).get("profile") or {}
    doc = repo.documents.get(prof["id"]) if isinstance(prof, dict) and prof.get("id") else None
    if not doc:
        return "", None
    return (doc.get("text") or "")[:MAX_PROFILE_CHARS], doc


def _candidates_table(pool: list[dict]) -> str:
    lines = []
    for i, p in enumerate(pool, 1):
        parts = [f"c{i}", p["name"]]
        for k, label in (("platforms", "المنصات"), ("followers", "المتابعون"), ("category", "المجال"), ("city", "المدينة"),
                         ("gender", "الجنس"), ("notes", "ملاحظات")):
            if p.get(k):
                parts.append(f"{label}: {p[k]}")
        extra = {k: v for k, v in (p.get("extra") or {}).items() if not re.search(r"سعر|price|تكلف|cost|rate|fee|جوال|phone|ايميل|email|واتس", k, re.I)}
        parts += [f"{k}: {v}" for k, v in list(extra.items())[:4]]
        lines.append(" | ".join(str(x) for x in parts))
    return "\n".join(lines)


def _brief(inputs: dict, a, meta: dict) -> str:
    c = inputs.get("client") or {}
    p = inputs.get("project") or {}
    g = inputs.get("goals") or {}
    t = inputs.get("timeline") or {}
    pr = inputs.get("preferences") or {}
    audience = list(p.get("audience") or []) if isinstance(p.get("audience"), list) else [p.get("audience") or ""]
    audience += [p.get("audience_other") or ""]
    audience = [x for x in audience if x]
    from app.generator.knowledge.objectives import OBJECTIVES
    objectives = [OBJECTIVES[k]["label"] for k in g.get("objective_keys") or [] if k in OBJECTIVES]
    if g.get("objectives"):
        objectives.append(g["objectives"])
    rows = [
        ("العميل", c.get("name")),
        ("القطاع", a.sector.get("name")),
        ("نشاط العميل كما كتبه الفريق (افهمه وابنِ عليه ولا تنسخه)", c.get("about")),
        ("اسم المشروع", p.get("name")),
        ("نوع المشروع", p.get("type_other") or a.ptype["label"]),
        ("فكرة الفريق وتوجيهه (ابنِ عليها ولا تنسخها)", p.get("description")),
        ("ملاحظات الفريق (راعِها في البناء ولا تنسخها)", pr.get("requirements")),
        ("طلب الفريق بالتفصيل (أهم مدخل: نفّذ كل ما فيه بدقة، ثم أكمله وابنِ عليه بأفكارك)", p.get("brief")),
        ("الجمهور المستهدف", "، ".join(audience) if audience else "لم يُحدد: اقترحه أنت"),
        ("الأهداف التي اختارها الفريق", "، ".join(objectives) if objectives else "لم تُحدد: اقترحها أنت"),
        ("المنصات", "، ".join(a.platform_labels) or "لم تُحدد: اقترح المناسب"),
        ("الخدمات المطلوبة", "، ".join(meta.get("service_labels") or [])),
        ("مدة المشروع", ar.duration_phrase(a.days)),
        ("تاريخ البداية", t.get("start_date")),
        ("تاريخ الفعالية", p.get("event_date")),
        ("الموقع", p.get("location")),
        ("أسلوب الكتابة", pr.get("tone_other") or TONES.get(pr.get("tone") or a.tone, "")),
        ("مستوى التفصيل", DETAILS.get(a.detail, "")),
    ]
    return "\n".join(f"- {k}: {v}" for k, v in rows if v)


def stages(sections: list[str]) -> tuple[list[str], list[list[str]]]:
    """(creative core, parallel groups) for the sections a document has."""
    first = [x for x in STAGE_ONE if x in sections]
    rest = [[x for x in g if x in sections] for g in STAGE_TWO]
    rest = [g for g in rest if g]
    placed = set(first) | {x for g in rest for x in g}
    left = [x for x in sections if x in SECTION_SCHEMAS and x not in placed]
    if left:
        rest.append(left)
    if not first and rest:
        first = rest.pop(0)
    return first, rest


def build_request(inputs: dict, library: dict, settings: dict, meta: dict, sections: list[str],
                  current: dict | None = None, tone: str | None = None, concept: dict | None = None) -> dict:
    """Everything a writer needs for one call: system prompt, user prompt, output schema.

    `sections` are section types to write. `concept` is the creative core already written (stage
    one), which these sections must build on. `current` (regeneration) is the section being rewritten,
    so the new version differs from it."""
    a, _, plan = E.planned(inputs, library)
    if tone and tone in TONES:
        a.tone = tone
        inputs = {**inputs, "preferences": {**(inputs.get("preferences") or {}), "tone": tone, "tone_other": ""}}
    sections = [s for s in sections if s in SECTION_SCHEMAS]
    if current is None and "conclusion" in sections and ((inputs.get("project") or {}).get("brief") or "").strip():
        sections.append("custom_sections")
    pool = library.get("celebrities") or []
    if not pool:
        sections = [s for s in sections if s != "celebrities"]
    counts = {**COUNTS[a.detail]}
    if plan and plan["stretch"] > 1.05:  # more pages than the detail level fills: more of everything
        for k in ("activations", "objectives", "kpis", "deliverables", "pillars", "cards"):
            counts[k] = round(counts[k] * plan["stretch"])
    counts["celebrities"] = min(counts["celebrities"], len(pool)) if pool else 0
    profile, doc = _profile_text(inputs)
    parts = [_prompt("author").format(brief=_brief(inputs, a, meta), company=(settings.get("company_about") or "")[:900])]
    if profile:
        parts.append(f"## الملف التعريفي للعميل (من ملف «{doc['filename']}»)\nاقرأه وافهم منه العميل، ولا تنسخ فقراته.\n<profile>\n{profile}\n</profile>")
    if pool and "celebrities" in sections:
        parts.append("## قائمة المرشحين من المشاهير والمؤثرين (القائمة المعتمدة لدى أهداف)\n"
                     "لا تذكر أي اسم من خارجها. استخدم المعرّف (c1، c2…) في ref.\n" + _candidates_table(pool))
    elif celebs.wanted(inputs, a.type_key) or any(w in ar.normalize(_brief(inputs, a, meta)) for w in ("مشاهير", "مشهور", "مؤثر")):
        parts.append("## المشاهير\nلا توجد قائمة مشاهير مرفوعة: لا تذكر أي اسم لمشهور أو مؤثر، واكتب الدور ومعايير الاختيار فقط.")
    if concept:
        parts.append("## الفكرة الإبداعية المعتمدة لهذا العرض\nكتبها زميلك في الجزء الأول من العرض. ابنِ عليها كل ما تكتبه، "
                     "واستخدم اسمها وأسماء التفعيلات كما هي، ولا تكرر شرحها حرفيًا:\n" + json.dumps(concept, ensure_ascii=False)[:15000])
    if current:
        parts.append("## إعادة كتابة\nهذه هي النسخة الحالية من القسم. اكتب نسخة جديدة مختلفة عنها في الزاوية والصياغة والأفكار، "
                     "ومتسقة مع فكرة العرض:\n" + json.dumps(current, ensure_ascii=False)[:12000])
    room = (plan or {}).get("per_section", {})
    guide = "\n".join(f"- {s}: {GUIDE[s].format(**counts)}" + (f" (المساحة: نحو {room[s]} صفحة)" if s in room else "") for s in sections)
    if plan:
        parts.append(f"## حجم العرض\nالعرض كاملًا نحو {plan['target']} صفحة (شرائح 16:9). التزم بالمساحة المحددة لكل قسم: "
                     "لا تزد فيتجاوز العرض العدد المطلوب، ولا تنقص فيبدو فارغًا.")
    parts.append("## المطلوب\nاكتب الأقسام التالية، وكلها مرتبطة بفكرة واحدة واضحة:\n" + guide +
                 "\n- subtitle في كل قسم: سطر قصير جدًا تحت عنوان القسم، خاص بهذا المشروع."
                 + ("\n- cover_subtitle: سطر واحد للغلاف يصف العرض في 12 كلمة أو أقل." if current is None and concept is None else ""))
    props = {s: SECTION_SCHEMAS[s] for s in sections}
    if current is None and concept is None:
        props = {"cover_subtitle": _s(), **props}
    return {
        "system": _prompt("author_system"),
        "prompt": "\n\n".join(parts),
        "schema": _obj(props),
        "max_tokens": 16000 if current is None else 8000,
        "sections": sections,
    }


# =============================================================================== calling Claude
def _parse(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise AuthorError("unexpected answer")
    return data


def _call_cli(req: dict) -> dict:
    exe = _cli_path()
    if not exe:
        raise AuthorError("Claude Code not found")
    work = config.DATA_DIR / "ai-work"
    work.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-p", "--output-format", "json", "--json-schema", json.dumps(req["schema"], ensure_ascii=False),
           "--tools", "", "--no-session-persistence", "--model", config.CLAUDE_CLI_MODEL, "--safe-mode",
           "--strict-mcp-config", "--system-prompt", req["system"]]
    proc = subprocess.run(cmd, input=req["prompt"].encode("utf-8"), capture_output=True, cwd=work,
                          timeout=config.AI_TIMEOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    out = proc.stdout.decode("utf-8", "replace").strip()
    try:
        data = json.loads(out)
    except ValueError:
        raise AuthorError(f"Claude Code: {(proc.stderr or b'').decode('utf-8', 'replace')[:300] or out[:300]}")
    usage = data.get("usage") or {}
    log.info("Claude Code call %s: %.0fs, %s output tokens", req.get("sections"), (data.get("duration_ms") or 0) / 1000,
             usage.get("output_tokens"))
    if data.get("is_error") or data.get("subtype") not in (None, "success"):
        raise AuthorError(f"Claude Code: {str(data.get('result') or data.get('subtype'))[:300]}")
    if isinstance(data.get("structured_output"), dict):
        return data["structured_output"]
    return _parse(data.get("result") or "")


_client = None


def _call_api(req: dict) -> dict:
    global _client
    if _client is None:
        import anthropic  # only needed with a server-side key

        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=config.AI_TIMEOUT)
    with _client.messages.stream(
        model=config.CLAUDE_MODEL, max_tokens=req["max_tokens"], system=req["system"],
        messages=[{"role": "user", "content": req["prompt"]}],
        extra_body={"output_config": {"format": {"type": "json_schema", "schema": req["schema"]}}},
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise AuthorError("declined")
    return _parse("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"))


def set_client(client) -> None:
    """Inject an API client (tests)."""
    global _client
    _client = client


def call(req: dict) -> dict:
    p = provider()
    if p == "api":
        return _call_api(req)
    if p == "cli":
        return _call_cli(req)
    raise AuthorError("no writer available")


# =============================================================================== guards
_NUM = re.compile(r"[0-9٠-٩][0-9٠-٩,.،٬]*")
_BIG_WORDS = re.compile(r"(ألف|آلاف|الف|مليون|ملايين|مليار|ريال|ر\.س|SAR|%|٪|K\b|M\b)")
_SENT = re.compile(r"(?<=[.!؟?؛\n])\s+")


def _digits(s: str) -> str:
    return re.sub(r"[,.،٬]", "", re.sub(r"[٠-٩]", lambda m: str(ord(m.group()) - 0x0660), s))


class Facts(set):
    """Numbers found in the inputs, the profile and the celebrity list, plus that text itself
    (so «5 ملايين» is only accepted if those words appear there)."""
    blob: str = ""


def _squash(text: str) -> str:
    return re.sub(r"[\s,.،٬]+", "", _digits_keep(text))


def _digits_keep(text: str) -> str:
    return re.sub(r"[٠-٩]", lambda m: str(ord(m.group()) - 0x0660), text or "")


def sources_numbers(inputs: dict, library: dict, settings: dict) -> Facts:
    blob = json.dumps(inputs, ensure_ascii=False) + _profile_text(inputs)[0]
    blob += json.dumps(library.get("celebrities") or [], ensure_ascii=False)
    blob += json.dumps({k: settings.get(k) for k in ("company_about", "company_stats")}, ensure_ascii=False)
    facts = Facts(_digits(m) for m in _NUM.findall(blob))
    facts.blob = _squash(blob)
    return facts


def _suspicious(sentence: str, allowed: set[str]) -> bool:
    blob = getattr(allowed, "blob", "")
    for m in _NUM.finditer(sentence):
        n = _digits(m.group())
        if not n:
            continue
        tail = sentence[m.end():m.end() + 9].strip()
        head = sentence[max(0, m.start() - 2):m.start()]
        unit = _BIG_WORDS.match(tail)
        if unit or "%" in head:
            # a magnitude or a percentage must appear as such in what the team gave us
            phrase = _squash(m.group() + (unit.group() if unit else ""))
            if not (blob and phrase in blob):
                return True
            continue
        if n in allowed:
            continue
        value = int(n) if n.isdigit() else 0
        if 1990 <= value <= 2040:
            continue  # a year (e.g. رؤية 2030) is not an invented metric
        if value >= 100:
            return True
    return False


def clean(text, allowed: set[str]) -> str:
    """Drop sentences that carry figures the model could not have known."""
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if not text:
        return ""
    kept = [s for s in _SENT.split(text) if not _suspicious(s, allowed)]
    return " ".join(kept).strip()


# =============================================================================== applying the answer
def _texts(items, allowed) -> list[str]:
    return [t for t in (clean(x, allowed) for x in (items or []) if isinstance(x, str)) if t]


def _cards(items, allowed, offset: int = 0) -> list[dict]:
    out = []
    for i, it in enumerate(items or []):
        if not isinstance(it, dict):
            continue
        title, text = clean(it.get("title"), allowed), clean(it.get("text"), allowed)
        if title or text:
            out.append({"title": title, "text": text, "icon": ICONS[(i + offset) % len(ICONS)]})
    return out


def _target(value, allowed) -> str:
    v = clean(value, allowed)
    return v if v and v != "." else "يُحدد مع العميل"


def _blocks_for(sec: str, c: dict, w, allowed: set[str], pool: list[dict], ai_phases_holder: dict) -> list[dict] | None:
    blk = E.blk
    a = w.a
    if sec == "intro":
        lead = clean(c.get("lead"), allowed)
        if not lead:
            return None
        return [blk("lead", text=lead)] + [blk("paragraph", text=t) for t in _texts(c.get("paragraphs"), allowed)]
    if sec == "understanding":
        blocks = [blk("paragraph", text=t) for t in _texts(c.get("paragraphs"), allowed)]
        cards = _cards(c.get("cards"), allowed)
        if cards:
            blocks.append(blk("cards", items=cards, columns=2 if len(cards) <= 4 else 3))
        if clean(c.get("insight"), allowed):
            blocks.append(blk("callout", label="الخلاصة", text=clean(c.get("insight"), allowed)))
        return blocks or None
    if sec == "objectives":
        items = [{"title": clean(o.get("title"), allowed), "text": clean(o.get("text"), allowed), "measure": clean(o.get("measure"), allowed),
                  "target": _target(o.get("target"), allowed), "suggested": True} for o in c.get("items") or [] if isinstance(o, dict)]
        items = [o for o in items if o["title"]]
        if not items:
            return None
        return ([blk("paragraph", text=clean(c.get("intro"), allowed))] if clean(c.get("intro"), allowed) else []) + [blk("objectives", items=items)]
    if sec == "idea":
        name = clean(c.get("name"), allowed).strip("«»\"' ")
        idea = clean(c.get("idea"), allowed)
        if not (name and idea):
            return None
        w.ctx["concept"] = name
        blocks = [blk("lead", text=f"«{name}»: {idea}")]
        if clean(c.get("message"), allowed):
            blocks.append(blk("callout", label="الرسالة الأساسية", text=clean(c.get("message"), allowed)))
        slogans = [s.strip("«»\"' ") for s in _texts(c.get("slogans"), allowed)]
        if slogans:
            blocks.append(blk("cards", title="مقترحات للشعار", columns=min(3, len(slogans)),
                              items=[{"title": f"«{s}»", "text": "", "icon": "quote"} for s in slogans]))
        if clean(c.get("why"), allowed):
            blocks.append(blk("paragraph", text=clean(c.get("why"), allowed)))
        steps = _texts(c.get("execution"), allowed)
        if steps:
            blocks.append(blk("list", title="كيف تتحول الفكرة إلى تنفيذ", items=[ar.sentence(x) for x in steps], style="check"))
        return blocks
    if sec == "activations":
        cards = _cards(c.get("items"), allowed, offset=2)
        if not cards:
            return None
        intro = clean(c.get("intro"), allowed)
        return ([blk("paragraph", text=intro)] if intro else []) + [blk("cards", items=cards, columns=2 if len(cards) <= 4 else 3)]
    if sec == "celebrities":
        rows, seen = [], set()
        for pick in c.get("picks") or []:
            if not isinstance(pick, dict):
                continue
            ref = str(pick.get("ref") or "").strip().lower()
            person = None
            m = re.fullmatch(r"c(\d+)", ref)
            if m and 1 <= int(m.group(1)) <= len(pool):
                person = pool[int(m.group(1)) - 1]
            if person is None:
                person = celebs.find(ref, pool)
            if person is None or person["id"] in seen:
                continue  # never name anyone who is not on the team's list
            seen.add(person["id"])
            reach = " · ".join(x for x in (person.get("platforms"), person.get("followers")) if x)
            rows.append({"id": E._id(), "name": person["name"] + (f"\n{person['handle']}" if person.get("handle") else ""),
                         "reach": reach or "—", "category": person.get("category") or "—",
                         "role": " ".join(x for x in (clean(pick.get("role"), allowed), clean(pick.get("content"), allowed)) if x),
                         "why": clean(pick.get("why"), allowed)})
        if not rows:
            return None
        blocks = []
        if clean(c.get("intro"), allowed):
            blocks.append(blk("paragraph", text=clean(c.get("intro"), allowed)))
        blocks.append(blk("table", title="المرشحون من قائمة المشاهير", columns=[
            {"key": "name", "label": "الاسم"}, {"key": "reach", "label": "المنصات والمتابعون"}, {"key": "category", "label": "المجال"},
            {"key": "role", "label": "دوره والمحتوى المقترح"}, {"key": "why", "label": "لماذا نرشحه"}], rows=rows))
        crit = _texts(c.get("criteria"), allowed)
        if crit:
            blocks.append(blk("list", title="معايير الترشيح", items=[ar.sentence(x) for x in crit], style="check"))
        blocks.append(blk("callout", label="ملاحظة", text="الأسماء من قائمة المشاهير المعتمدة لدى أهداف، والأرقام كما وردت فيها. يُؤكَّد التوفر والأتعاب بعد اعتماد الترشيحات."))
        return blocks
    if sec == "content_plan":
        pillars = []
        for i, pl in enumerate(c.get("pillars") or []):
            if not isinstance(pl, dict) or not clean(pl.get("title"), allowed):
                continue
            ex = _texts(pl.get("examples"), allowed)
            text = clean(pl.get("text"), allowed) + (f" أمثلة: {'، '.join(e.rstrip('.') for e in ex)}." if ex else "")
            pillars.append({"title": clean(pl.get("title"), allowed), "text": text.strip(), "icon": "pen"})
        week = [{"id": E._id(), **{k: clean(r.get(k), allowed) for k in ("day", "platform", "format", "pillar", "idea")}}
                for r in c.get("week") or [] if isinstance(r, dict)]
        if not pillars:
            return None
        blocks = ([blk("paragraph", text=clean(c.get("intro"), allowed))] if clean(c.get("intro"), allowed) else [])
        blocks.append(blk("cards", items=pillars, columns=2 if len(pillars) <= 4 else 3))
        if week:
            blocks.append(blk("table", title="نموذج أسبوع نشر", columns=[
                {"key": "day", "label": "اليوم"}, {"key": "platform", "label": "المنصة"}, {"key": "format", "label": "الصيغة"},
                {"key": "pillar", "label": "المحور"}, {"key": "idea", "label": "الفكرة"}], rows=week))
        return blocks
    if sec == "scope":
        groups = []
        for i, g in enumerate(c.get("groups") or []):
            if not isinstance(g, dict):
                continue
            items = [{"title": x["title"], "text": x["text"]} for x in _cards(g.get("items"), allowed) if x["title"]]
            if clean(g.get("title"), allowed) and items:
                groups.append({"title": clean(g.get("title"), allowed), "icon": ICONS[i % len(ICONS)], "items": items})
        if not groups:
            return None
        intro = clean(c.get("intro"), allowed)
        return ([blk("paragraph", text=intro)] if intro else []) + [blk("services", groups=groups)]
    if sec == "methodology":
        phases = []
        for p in c.get("phases") or []:
            if not isinstance(p, dict) or not clean(p.get("title"), allowed):
                continue
            role = p.get("role") if p.get("role") in ROLES else "execute"
            phases.append({"name": clean(p.get("title"), allowed), "role": "execute" if role == "event_day" else role,
                           "key": "day" if role == "event_day" else None,
                           "weight": max(1, min(10, int(p.get("weight") or 3))) / 10, "goal": clean(p.get("goal"), allowed),
                           "activities": _texts(p.get("activities"), allowed), "outputs": _texts(p.get("outputs"), allowed),
                           "owner_title": clean(p.get("owner"), allowed) or "مدير المشروع"})
        if len(phases) < 2:
            return None
        scheduled = E._schedule(w, phases)
        ai_phases_holder["phases"] = scheduled
        ai_phases_holder["timeline_intro"] = clean(c.get("timeline_intro"), allowed)
        ai_phases_holder["timeline_subtitle"] = clean(c.get("timeline_subtitle"), allowed)
        intro = clean(c.get("intro"), allowed)
        return ([blk("paragraph", text=intro)] if intro else []) + [blk("phases", items=E.methodology_items(w, scheduled))]
    if sec == "deliverables":
        rows = []
        for r in c.get("rows") or []:
            if not isinstance(r, dict) or not clean(r.get("title"), allowed):
                continue
            qty = r.get("qty")
            qty = qty if isinstance(qty, int) and 0 < qty <= 2000 else None
            rows.append({"id": E._id(), "title": clean(r.get("title"), allowed), "description": clean(r.get("description"), allowed),
                         "qty": qty, "unit": clean(r.get("unit"), allowed), "timing": clean(r.get("timing"), allowed), "source": "ai"})
        if not rows:
            return None
        intro = clean(c.get("intro"), allowed)
        return ([blk("paragraph", text=intro)] if intro else []) + [blk("deliverables", rows=rows)]
    if sec == "kpis":
        items = [{"id": E._id(), "name": clean(k.get("name"), allowed), "name_en": "", "definition": clean(k.get("definition"), allowed),
                  "measurement": clean(k.get("measurement"), allowed), "frequency": clean(k.get("frequency"), allowed),
                  "target": _target(k.get("target"), allowed)} for k in c.get("items") or [] if isinstance(k, dict)]
        items = [k for k in items if k["name"]]
        if not items:
            return None
        intro = clean(c.get("intro"), allowed)
        return ([blk("paragraph", text=intro)] if intro else []) + [blk("kpis", items=items)]
    if sec == "conclusion":
        lead = clean(c.get("lead"), allowed)
        if not lead:
            return None
        blocks = [blk("lead", text=lead)]
        if clean(c.get("paragraph"), allowed):
            blocks.append(blk("paragraph", text=clean(c.get("paragraph"), allowed)))
        steps = [{"title": x["title"], "text": x["text"]} for x in _cards(c.get("next_steps"), allowed) if x["title"]]
        if steps:
            blocks.append(blk("steps", title="الخطوات التالية", items=steps))
        return blocks
    if sec == "team":
        members = [{"id": E._id(), "role": clean(m.get("role"), allowed), "role_en": "", "count": max(1, min(20, int(m.get("count") or 1))),
                    "responsibilities": _texts(m.get("responsibilities"), allowed)[:3]} for m in c.get("members") or [] if isinstance(m, dict)]
        members = [m for m in members if m["role"]]
        if not members:
            return None
        intro = clean(c.get("intro"), allowed)
        return ([blk("paragraph", text=intro)] if intro else []) + [blk("team", members=members)]
    if sec == "governance":
        cards = _cards(c.get("cards"), allowed)
        if not cards:
            return None
        intro = clean(c.get("intro"), allowed)
        return ([blk("paragraph", text=intro)] if intro else []) + [blk("cards", items=cards, columns=3)]
    if sec == "assumptions":
        items = [ar.sentence(x) for x in _texts(c.get("items"), allowed)]
        if not items:
            return None
        intro = clean(c.get("intro"), allowed)
        return ([blk("paragraph", text=intro)] if intro else []) + [blk("list", items=items, style="check")]
    if sec == "custom":
        blocks = [blk("paragraph", text=t) for t in _texts(c.get("paragraphs"), allowed)]
        points = _texts(c.get("points"), allowed)
        if points:
            blocks.append(blk("list", items=[ar.sentence(x) for x in points], style="check"))
        cards = _cards(c.get("cards"), allowed)
        if cards:
            blocks.append(blk("cards", items=cards, columns=2 if len(cards) <= 4 else 3))
        return blocks or None
    if sec == "risks":
        rows = [{"id": E._id(), "risk": clean(r.get("risk"), allowed), "likelihood": r.get("likelihood") or "متوسطة",
                 "impact": r.get("impact") or "متوسط", "mitigation": clean(r.get("mitigation"), allowed)}
                for r in c.get("rows") or [] if isinstance(r, dict)]
        rows = [r for r in rows if r["risk"]]
        if not rows:
            return None
        intro = clean(c.get("intro"), allowed)
        return ([blk("paragraph", text=intro)] if intro else []) + [blk("risks", rows=rows)]
    return None


def apply(doc: dict, content: dict, inputs: dict, library: dict, settings: dict, only: list[str] | None = None) -> list[str]:
    """Write Claude's sections into the document. Returns the section types that were replaced;
    anything missing or rejected keeps the rules-engine version."""
    a = E.planned(inputs, library)[0]
    w = E.Writer(a, library, settings, doc.get("seed", 1))
    allowed = sources_numbers(inputs, library, settings)
    pool = library.get("celebrities") or []
    holder: dict = {}
    written = []
    by_type = {s.get("type"): s for s in doc.get("sections", [])}
    idea = by_type.get("idea")
    if idea:
        lead = next((b.get("text", "") for b in idea.get("blocks", []) if b.get("type") == "lead"), "")
        if lead.startswith("«") and "»" in lead:
            w.ctx["concept"] = lead[1:lead.index("»")]
    for sec in (only or WRITABLE):
        c = content.get(sec)
        target = by_type.get(sec)
        if not isinstance(c, dict) or target is None:
            continue
        try:
            blocks = _blocks_for(sec, c, w, allowed, pool, holder)
        except (TypeError, ValueError, KeyError) as exc:
            log.warning("AI section %s skipped: %s", sec, exc)
            blocks = None
        if not blocks:
            continue
        target["blocks"] = blocks
        sub = clean(c.get("subtitle"), allowed)
        if sub:
            target["subtitle"] = sub
        target["ai"] = True
        written.append(sec)
    # the timeline follows the phases Claude planned
    if holder.get("phases") and by_type.get("timeline"):
        tl = by_type["timeline"]
        tl["blocks"] = E.timeline_blocks(w, holder["phases"], intro=holder.get("timeline_intro") or tl["blocks"][0].get("text"))
        if holder.get("timeline_subtitle"):
            tl["subtitle"] = holder["timeline_subtitle"]
        tl["ai"] = True
        written.append("timeline")
    # sections the team asked for in its detailed request that no standard section covers
    extra = [x for x in (content.get("custom_sections") or []) if isinstance(x, dict)][:3] if only is None else []
    for c in extra:
        title = clean(c.get("title"), allowed)
        blocks = _blocks_for("custom", c, w, allowed, pool, holder) if title else None
        if not blocks:
            continue
        sec = {"id": E._id(), "type": "custom", "title": title, "title_en": "", "subtitle": clean(c.get("subtitle"), allowed),
               "visible": True, "divider": False, "regen": 0, "tone": a.tone, "blocks": blocks, "ai": True}
        sections = doc.setdefault("sections", [])
        at = next((i for i, x in enumerate(sections) if x.get("type") == "conclusion"), len(sections))
        sections.insert(at, sec)
        written.append("custom")
    if only is None and clean(content.get("cover_subtitle"), allowed):
        doc["cover"]["subtitle"] = clean(content.get("cover_subtitle"), allowed)
    return written


# =============================================================================== entry points (server)
def write_document(doc: dict, inputs: dict, library: dict, settings: dict, meta: dict) -> dict:
    """Have Claude write the document's sections. No-op without a writer; never raises."""
    if not provider():
        return doc
    sections = [s["type"] for s in doc.get("sections", []) if s.get("type") in WRITABLE]
    started = time.time()
    try:
        first, rest = stages(sections)
        content = call(build_request(inputs, library, settings, meta, first))
        concept = {k: content[k] for k in first if k in content}
        with ThreadPoolExecutor(max_workers=max(1, len(rest))) as pool:
            jobs = [pool.submit(call, build_request(inputs, library, settings, meta, g, concept=concept)) for g in rest]
            failed = []
            for g, job in zip(rest, jobs):
                try:
                    content.update({k: v for k, v in job.result().items() if k in g or k == "custom_sections"})
                except Exception as exc:
                    log.warning("AI sections %s failed, retrying: %s", g, exc)
                    failed.append(g)
        for g in failed:
            try:
                content.update({k: v for k, v in call(build_request(inputs, library, settings, meta, g, concept=concept)).items()
                                if k in g or k == "custom_sections"})
            except Exception as exc:  # those sections keep the rules-engine text
                log.warning("AI sections %s skipped: %s", g, exc)
        written = apply(doc, content, inputs, library, settings)
        doc["ai"] = {"provider": provider(), "model": status()["model"], "sections": written, "seconds": round(time.time() - started)}
    except Exception as exc:  # generation must never fail because of the writer
        log.warning("AI writing skipped: %s", exc)
        doc["ai"] = {"provider": provider(), "error": str(exc)[:300], "sections": []}
    return doc


def section_snapshot(section: dict) -> dict:
    """A compact view of a section's current text, sent when asking for a different version."""
    out = []
    for b in section.get("blocks", []):
        if b.get("text"):
            out.append(b["text"])
        for it in b.get("items") or []:
            if isinstance(it, dict):
                out.append(" — ".join(str(it.get(k)) for k in ("title", "text", "name") if it.get(k)))
            elif isinstance(it, str):
                out.append(it)
        for r in b.get("rows") or []:
            out.append(" — ".join(str(v) for k, v in r.items() if k != "id" and isinstance(v, str))[:300])
    return {"title": section.get("title"), "text": out[:40]}


def rewrite_section(doc: dict, section: dict, inputs: dict, library: dict, settings: dict, meta: dict,
                    tone: str | None = None) -> bool:
    """Ask Claude for a new version of one section (in place). False when no writer or on failure."""
    sec = section.get("type")
    if not provider() or sec not in WRITABLE:
        return False
    try:
        idea = next((s for s in doc.get("sections", []) if s.get("type") == "idea" and s is not section), None)
        req = build_request(inputs, library, settings, meta, [sec], current=section_snapshot(section), tone=tone,
                            concept=section_snapshot(idea) if idea else None)
        if not req["sections"]:
            return False
        content = call(req)
        # only this section changes (the editor replaces just this one); the idea gives it context
        tmp = {"seed": doc.get("seed", 1), "cover": {},
               "sections": [s for s in doc.get("sections", []) if s.get("type") == "idea" and s is not section] + [section]}
        return bool(apply(tmp, content, inputs, library, settings, only=[sec]))
    except Exception as exc:
        log.warning("AI section rewrite skipped: %s", exc)
        return False
