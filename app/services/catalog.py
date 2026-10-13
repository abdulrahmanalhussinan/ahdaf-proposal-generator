"""Read models shared by the HTTP API and the in-browser build: app metadata, dashboard,
library overview and the editable settings."""
from __future__ import annotations

from app.ai import provider as ai
from app.data import repositories as repo
from app.generator.analyzer import DETAILS, TONES
from app.generator.engine import SECTION_TITLES
from app.generator.knowledge.platforms import PLATFORM_ORDER, PLATFORMS
from app.generator.knowledge.project_types import PROJECT_TYPES, TYPE_ORDER
from app.generator.knowledge.services import CATEGORIES
from app.services.proposals import STATUSES

LIBRARY_LABELS = {
    "services": "الخدمات", "deliverables": "المخرجات المتكررة", "methodologies": "منهجيات العمل",
    "kpis": "مؤشرات الأداء", "intro_templates": "قوالب المقدمة", "conclusion_templates": "قوالب الخاتمة",
    "roles": "المسميات الوظيفية", "past_projects": "المشاريع السابقة", "sectors": "القطاعات",
}

# Settings the browser may change. Anything else (keys, paths, counters) is server-only.
EDITABLE_SETTINGS = {
    "company_name", "company_name_short", "company_name_en", "tagline", "website", "email", "phone", "address",
    "company_about", "company_stats", "company_stats_note", "company_pillars", "vision", "mission", "default_tone",
    "default_detail", "default_layout", "proposal_prefix", "pptx_font",
}


def meta(user_name: str, user_role: str) -> dict:
    return {
        "project_types": [{"key": k, "label": PROJECT_TYPES[k]["label"], "label_en": PROJECT_TYPES[k]["label_en"],
                           "icon": PROJECT_TYPES[k]["icon"], "default_days": PROJECT_TYPES[k]["default_days"],
                           "default_services": PROJECT_TYPES[k]["default_services"]} for k in TYPE_ORDER],
        "tones": [{"key": k, "label": v} for k, v in TONES.items()],
        "details": [{"key": k, "label": v} for k, v in DETAILS.items()],
        "statuses": [{"key": k, "label": v} for k, v in STATUSES.items()],
        "categories": [{"key": k, **v} for k, v in CATEGORIES.items()],
        "platforms": [{"key": k, "label": PLATFORMS[k]["label"]} for k in PLATFORM_ORDER],
        "sections": SECTION_TITLES,
        "library_kinds": [{"key": k, "label": v} for k, v in LIBRARY_LABELS.items()],
        "ai": ai.status(),
        "user": {"name": user_name, "role": user_role},
    }


def dashboard() -> dict:
    return {"stats": repo.proposals.stats(), "recent": repo.proposals.list(limit=6),
            "library": repo.library.counts(), "templates": len(repo.templates.list())}


def library_overview() -> dict:
    counts = repo.library.counts()
    return {"kinds": [{"key": k, "label": v, "count": counts.get(k, 0)} for k, v in LIBRARY_LABELS.items()]}


def settings_values() -> dict:
    values = {k: v for k, v in repo.settings.get_all().items() if k in EDITABLE_SETTINGS}
    return {"values": values, "ai": ai.status()}


def save_settings(values: dict) -> dict:
    repo.settings.set_many({k: v for k, v in (values or {}).items() if k in EDITABLE_SETTINGS})
    return settings_values()
