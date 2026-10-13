"""First-run seeding: company settings, content library, proposal templates and DEMO data.

Company text and figures below are taken verbatim from AHDAF's own technical proposal
(«متجر شادن – نسخة 4») and ahdaf.co. Demo clients/proposals are fictional and flagged `is_demo`."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.core.arabic import normalize
from app.data import repositories as repo
from app.generator.knowledge.kpis import KPIS
from app.generator.knowledge.project_types import PROJECT_TYPES
from app.generator.knowledge.roles import ROLES
from app.generator.knowledge.sectors import SECTORS
from app.generator.knowledge.services import SERVICES

DEFAULT_SETTINGS = {
    "company_name": "شركة أهداف للخدمات التسويقية",
    "company_name_short": "أهداف",
    "company_name_en": "Ahdaf Marketing Services",
    "tagline": "نربط الإبداع بالهدف",
    "website": "www.ahdaf.co",
    "email": "info@ahdaf.co",
    "phone": "+966 53 909 0452",
    "address": "الصحافة — طريق الملك عبدالعزيز، الرياض",
    "company_about": "شركة سعودية متخصصة في التسويق والإنتاج الإعلامي، نعيد تعريف التسويق بأساليب إبداعية تواكب التحولات الرقمية، ونحول الأفكار إلى واقع يحرك الأهداف.",
    "company_stats": [
        {"value": "+748", "label": "عميل وثقوا بنا"},
        {"value": "+412", "label": "مشروع منفذ"},
        {"value": "+7,195", "label": "فيديو منتج"},
        {"value": "+3,788", "label": "مؤثر ضمن شبكتنا"},
    ],
    "company_stats_note": "",
    "company_pillars": [
        {"title": "التأثير", "text": "استراتيجيات تغير علاقة الجمهور بالعلامة، مبنية على قراءة السوق لا على التخمين.", "icon": "target"},
        {"title": "التميز", "text": "محتوى ملهم يضع الجمهور في قلب التجربة، ويصنع فرقًا يلاحظ ويذكر.", "icon": "award"},
        {"title": "الإبداع", "text": "أساليب تمزج بين الفن والرسالة والتحليل، فتخرج الفكرة قابلة للتنفيذ.", "icon": "layers"},
        {"title": "الشفافية", "text": "شراكات قائمة على الوضوح والمصداقية في كل مرحلة من مراحل العمل.", "icon": "shield"},
    ],
    "vision": "أن نكون الاسم الأول في صناعة التأثير",
    "mission": "نحول الإبداع إلى استراتيجيات، والمحتوى إلى تجربة",
    "default_tone": "corporate",
    "default_detail": "medium",
    "default_layout": "landscape",
    "proposal_prefix": "AHD",
    "proposal_seq": 1,
    "pptx_font": "Saudi Serif VF",
}

INTRO_TEMPLATES = [
    ("قالب رسمي للجهات الحكومية", "formal",
     "تتشرف شركة أهداف للخدمات التسويقية بتقديم هذا العرض الفني إلى {العميل} لتنفيذ مشروع «{المشروع}»، ويتضمن العرض فهمنا لمتطلبات المشروع، ونطاق العمل، والمنهجية، والجدول الزمني الممتد على {المدة}، وآليات الحوكمة والقياس."),
    ("قالب مباشر للشركات", "corporate",
     "عرضنا لمشروع «{المشروع}» مبني على هدف واحد: أن يحقق {العميل} نتيجة يمكن قياسها خلال {المدة}. في الصفحات التالية: ماذا سنفعل، وكيف، ومتى، ومن سيعمل عليه."),
]

CONCLUSION_TEMPLATES = [
    ("ختام رسمي", "formal",
     "تؤكد شركة أهداف للخدمات التسويقية جاهزيتها لبدء تنفيذ مشروع «{المشروع}» فور اعتماد العرض، وتتطلع إلى التعاون مع {العميل} بما يحقق أهداف المشروع."),
    ("ختام مختصر", "concise",
     "نحن جاهزون للبدء. بعد الاعتماد مباشرة نحدد موعد اجتماع الانطلاق مع فريق {العميل}."),
]

TEMPLATE_PRESETS = [
    ("إدارة حسابات التواصل — 6 أشهر", "تشغيل الحسابات وصناعة المحتوى والريلز وإدارة المجتمع والتقارير الشهرية.", "social_media",
     {"project": {"type": "social_media", "platforms": ["tiktok", "instagram", "snapchat"]},
      "services": {"selected": ["social_management", "content_strategy", "content_creation", "reels", "community_management", "reporting"]},
      "timeline": {"duration_value": 6, "duration_unit": "month"}}),
    ("تنظيم فعالية أو حفل", "من المفهوم والتجهيزات والدعوات إلى إدارة يوم الفعالية وتغطيتها.", "event",
     {"project": {"type": "event"},
      "services": {"selected": ["event_management", "event_production", "guest_management", "event_coverage", "project_management"]},
      "timeline": {"duration_value": 6, "duration_unit": "week"}}),
    ("حملة علاقات عامة — 3 أشهر", "رسائل إعلامية وبيانات صحفية وعلاقات إعلامية ورصد.", "pr",
     {"project": {"type": "pr"},
      "services": {"selected": ["press_releases", "media_relations", "media_monitoring", "crisis_management", "reporting"]},
      "timeline": {"duration_value": 3, "duration_unit": "month"}}),
    ("حملة مؤثرين لإطلاق منتج", "ترشيح وتعاقد وإحاطة ومتابعة وقياس، مع محتوى UGC.", "influencer",
     {"project": {"type": "influencer", "platforms": ["snapchat", "tiktok", "instagram"]},
      "services": {"selected": ["influencer_marketing", "creative_concept", "ugc", "paid_ads", "reporting"]},
      "timeline": {"duration_value": 6, "duration_unit": "week"}}),
    ("حملة موسمية متكاملة", "فكرة مركزية وإنتاج وإعلانات ومؤثرون لموسم محدد.", "campaign",
     {"project": {"type": "campaign"},
      "services": {"selected": ["marketing_strategy", "creative_concept", "video_production", "paid_ads", "influencer_marketing", "reporting"]},
      "timeline": {"duration_value": 2, "duration_unit": "month"}}),
    ("إنتاج فيلم تعريفي", "سيناريو وتصوير ومونتاج ونسخ للمنصات.", "production",
     {"project": {"type": "production"},
      "services": {"selected": ["video_production", "photography", "copywriting", "project_management"]},
      "timeline": {"duration_value": 4, "duration_unit": "week"}}),
    ("هوية بصرية جديدة", "اكتشاف واستراتيجية ومفاهيم ودليل هوية وتطبيقات.", "branding",
     {"project": {"type": "branding"},
      "services": {"selected": ["branding", "market_research", "project_management"]},
      "timeline": {"duration_value": 6, "duration_unit": "week"}}),
    ("جناح في معرض", "تصميم وتنفيذ الجناح والمطبوعات والتغطية.", "exhibition",
     {"project": {"type": "exhibition"},
      "services": {"selected": ["booth_design", "event_production", "print_design", "event_coverage", "project_management"]},
      "timeline": {"duration_value": 5, "duration_unit": "week"}}),
    ("حملات أداء رقمية — 3 أشهر", "إعلانات ممولة بتتبع دقيق وتحسين أسبوعي.", "digital_ads",
     {"project": {"type": "digital_ads", "platforms": ["snapchat", "tiktok", "google"]},
      "services": {"selected": ["paid_ads", "social_design", "ugc", "reporting"]},
      "timeline": {"duration_value": 3, "duration_unit": "month"}}),
]

DEMO_CLIENTS = [
    {"name": "شركة مسارات لتأجير السيارات (تجريبي)", "sector": "automotive", "contact_name": "مدير التسويق (تجريبي)",
     "about": "شركة تأجير سيارات تعمل في عدة مدن، وتقدم التأجير اليومي والشهري للأفراد والشركات."},
    {"name": "مجموعة أفق للتطوير العقاري (تجريبي)", "sector": "real_estate", "contact_name": "إدارة الاتصال المؤسسي (تجريبي)",
     "about": "مطور عقاري يطلق مشروعًا سكنيًا جديدًا في شمال الرياض."},
    {"name": "مستشفى الرعاية التخصصي (تجريبي)", "sector": "healthcare", "contact_name": "إدارة العلاقات العامة (تجريبي)"},
    {"name": "مطاعم سفرة البيت (تجريبي)", "sector": "food_beverage", "contact_name": "مدير العلامة (تجريبي)"},
]

DEMO_PROPOSALS = [
    {"client": 0, "status": "sent", "days_ago": 12, "inputs": {
        "client": {"sector": "automotive", "about": "شركة تأجير سيارات تعمل في عدة مدن، وتقدم التأجير اليومي والشهري للأفراد والشركات."},
        "project": {"name": "إدارة حساب تيك توك", "type": "social_media", "platforms": ["tiktok"],
                    "description": "إدارة حساب الشركة على تيك توك وصناعة محتوى قصير يعرض الأسطول وتجربة الحجز والاستلام، ويستهدف المسافرين والعائلات والزوار.",
                    "audience": "الشباب والعائلات والمسافرون بين المدن", "challenge": "الحساب حاليًا ينشر عروضًا فقط، والتفاعل منخفض."},
        "scope": {"description": "إدارة الحساب يوميًا، وإنتاج الفيديوهات القصيرة، والرد على التعليقات، والتقارير الشهرية.", "out_of_scope": "ميزانية الإعلانات الممولة"},
        "services": {"selected": ["social_management", "content_strategy", "reels", "community_management", "reporting"]},
        "timeline": {"duration_value": 6, "duration_unit": "month", "start_date": "2026-11-01", "team_size": 5},
        "goals": {"objectives": "رفع الوعي بالعلامة في المدن التي نعمل بها\nزيادة الحجوزات القادمة من تيك توك\nنمو المتابعين 30%", "deliverables": "12 فيديو شهريًا"},
        "preferences": {"tone": "marketing", "detail": "medium", "include_about": True}}},
    {"client": 1, "status": "approved", "days_ago": 40, "inputs": {
        "client": {"sector": "real_estate", "about": "مطور عقاري يطلق مشروعًا سكنيًا جديدًا في شمال الرياض."},
        "project": {"name": "حفل تدشين مشروع أفق السكني", "type": "event",
                    "description": "تنظيم حفل تدشين للمشروع بحضور كبار الشخصيات والشركاء والإعلام، مع جولة في الوحدة النموذجية.",
                    "audience": "الشركاء والمستثمرون والإعلام وكبار الضيوف", "location": "شمال الرياض", "event_date": "2026-12-10"},
        "services": {"selected": ["event_management", "event_production", "guest_management", "event_coverage", "press_releases"]},
        "timeline": {"duration_value": 7, "duration_unit": "week", "start_date": "2026-10-25"},
        "goals": {"objectives": "حضور نوعي من الشركاء والمستثمرين\nتغطية إعلامية في الصحف الاقتصادية\nتجربة ضيوف تليق بالمشروع"},
        "preferences": {"tone": "luxury", "detail": "advanced", "include_about": True}}},
    {"client": 2, "status": "draft", "days_ago": 3, "inputs": {
        "client": {"sector": "healthcare"},
        "project": {"name": "حملة التوعية بصحة القلب", "type": "pr",
                    "description": "حملة علاقات عامة وتوعية بالتزامن مع اليوم العالمي للقلب، تشمل لقاءات إعلامية مع أطباء المستشفى ومحتوى توعويًا."},
        "services": {"selected": ["press_releases", "media_relations", "media_monitoring", "content_creation"]},
        "timeline": {"duration_value": 3, "duration_unit": "month"},
        "goals": {"objectives": "تغطية إعلامية في القنوات والصحف\nتعزيز الصورة الذهنية للمستشفى"},
        "preferences": {"tone": "formal", "detail": "medium", "include_about": True}}},
    {"client": 3, "status": "review", "days_ago": 380, "inputs": {
        "client": {"sector": "food_beverage"},
        "project": {"name": "حملة رمضان مع المؤثرين", "type": "influencer", "platforms": ["snapchat", "tiktok"],
                    "description": "حملة مؤثرين في رمضان للتعريف بقائمة الإفطار والسحور وزيادة الطلبات عبر التطبيقات.",
                    "audience": "العائلات في الرياض وجدة"},
        "services": {"selected": ["influencer_marketing", "creative_concept", "ugc", "paid_ads", "reporting"]},
        "timeline": {"duration_value": 5, "duration_unit": "week", "start_date": "2025-02-10"},
        "goals": {"objectives": "زيادة الطلبات خلال رمضان\nرفع الوعي بقائمة رمضان"},
        "preferences": {"tone": "corporate", "detail": "brief", "include_about": False}}},
]

PAST_PROJECTS_DEMO = [
    {"title": "إدارة حسابات علامة مطاعم", "sector": "food_beverage", "project_type": "social_media", "year": "2025",
     "summary": "مثال توضيحي: إدارة حسابات وصناعة محتوى شهري لعلامة مطاعم.", "results": ""},
    {"title": "حفل تدشين مشروع سكني", "sector": "real_estate", "project_type": "event", "year": "2025",
     "summary": "مثال توضيحي: تنظيم حفل تدشين مع تغطية إعلامية.", "results": ""},
]


def search_text_for(record: dict, meta: dict) -> str:
    year = (record.get("created_at") or "")[:4]
    parts = [record.get("number", ""), record.get("client_name", ""), record.get("project_name", ""),
             meta.get("type_label", ""), meta.get("sector_label", ""), " ".join(meta.get("service_labels", [])),
             year, record.get("status", "")]
    return normalize(" ".join(p for p in parts if p))


def seed_library() -> None:
    lib = repo.library
    for i, s in enumerate(SERVICES):
        data = {k: v for k, v in s.items() if k not in ("key", "title")}
        lib.create("services", s["title"], data, key=s["key"], sort=i)
    for i, r in enumerate(ROLES):
        data = {k: v for k, v in r.items() if k not in ("key", "title")}
        lib.create("roles", r["title"], data, key=r["key"], sort=i)
    for i, k in enumerate(KPIS):
        data = {kk: v for kk, v in k.items() if kk not in ("key", "name")}
        lib.create("kpis", k["name"], data, key=k["key"], sort=i)
    for i, s in enumerate(SECTORS):
        data = {k: v for k, v in s.items()}
        lib.create("sectors", s["name"], data, key=s["key"], sort=i)
    for i, (key, t) in enumerate(PROJECT_TYPES.items()):
        lib.create("methodologies", f"منهجية {t['label']}", {"project_type": key, "phases": t["phases"]}, key=f"method_{key}", sort=i)
    seen = set()
    sort = 0
    for s in SERVICES:
        for d in s.get("deliverables", []):
            if d["title"] in seen:
                continue
            seen.add(d["title"])
            lib.create("deliverables", d["title"], {"description": d.get("description", ""), "unit": d.get("unit", ""),
                                                     "qty": d.get("qty"), "mode": d.get("mode", "fixed"), "service": s["key"]},
                       key=f"dlv_{sort}", sort=sort)
            sort += 1
    for i, (title, tone, text) in enumerate(INTRO_TEMPLATES):
        lib.create("intro_templates", title, {"tone": tone, "text": text}, sort=i)
    for i, (title, tone, text) in enumerate(CONCLUSION_TEMPLATES):
        lib.create("conclusion_templates", title, {"tone": tone, "text": text}, sort=i)
    for i, p in enumerate(PAST_PROJECTS_DEMO):
        lib.create("past_projects", p["title"], {k: v for k, v in p.items() if k != "title"}, sort=i, is_demo=True)


def seed_templates() -> None:
    for name, desc, ptype, inputs in TEMPLATE_PRESETS:
        repo.templates.create(name, desc, ptype, inputs, is_builtin=True)


def seed_demo() -> None:
    from app.services import proposals as svc  # local import to avoid a cycle

    clients = [repo.clients.create(c, is_demo=True) for c in DEMO_CLIENTS]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for p in DEMO_PROPOSALS:
        client = clients[p["client"]]
        inputs = p["inputs"]
        inputs["client"] = {**inputs.get("client", {}), "id": client["id"], "name": client["name"]}
        created = (now - timedelta(days=p["days_ago"])).isoformat()
        svc.create_from_inputs(inputs, status=p["status"], is_demo=True, created_at=created,
                               today=date.fromisoformat(created[:10]), seed=7 + p["client"])


def ensure_seeded(with_demo: bool = True) -> None:
    if repo.settings.get("company_name") is None:
        repo.settings.set_many(DEFAULT_SETTINGS)
    if repo.library.is_empty():
        seed_library()
        seed_templates()
        if with_demo:
            seed_demo()
