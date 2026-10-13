"""Business logic for proposals: generation, editing, regeneration, duplication.
API routes call these functions; they in turn use the generator, the AI provider and the repositories."""
from __future__ import annotations

import copy
from datetime import date

from app.ai import provider as ai
from app.data import repositories as repo
from app.data.seed import search_text_for
from app.generator import engine
from app.generator.analyzer import analyze

STATUSES = {"draft": "مسودة", "review": "قيد المراجعة", "sent": "مُرسل للعميل", "approved": "معتمد", "rejected": "غير معتمد"}


class NotFound(Exception):
    pass


def _context() -> tuple[dict, dict]:
    return repo.library.all_active(), repo.settings.get_all()


def _client_for(inputs: dict) -> dict | None:
    c = inputs.get("client") or {}
    name = (c.get("name") or "").strip()
    if c.get("id"):
        existing = repo.clients.get(c["id"])
        if existing:
            return existing
    if not name:
        return None
    return repo.clients.upsert_by_name(name, c.get("sector"), {
        "about": c.get("about"), "contact_name": c.get("contact_name"), "website": c.get("website"), "logo": c.get("logo")})


def analyze_inputs(inputs: dict) -> dict:
    library, _ = _context()
    a = analyze(inputs, library)
    return engine.build_meta(a)


def create_from_inputs(inputs: dict, status: str = "draft", is_demo: bool = False, created_at: str | None = None,
                       today: date | None = None, seed: int | None = None, owner: str | None = None) -> dict:
    library, settings = _context()
    result = engine.generate(inputs, library, settings, seed=seed, today=today)
    doc, meta = result["doc"], result["meta"]
    doc = ai.enhance_document(doc, inputs, meta)  # no-op unless an AI provider is configured
    client = _client_for(inputs)
    if client:
        inputs.setdefault("client", {})["id"] = client["id"]
    record = {
        "number": repo.settings.next_proposal_number(),
        "client_id": client["id"] if client else None,
        "client_name": doc["cover"]["client"],
        "project_name": doc["cover"]["title"],
        "project_type": meta["type"],
        "sector": meta["sector"],
        "status": status,
        "version": doc["cover"].get("version", "1.0"),
        "inputs": inputs,
        "doc": doc,
        "meta": meta,
        "is_demo": is_demo,
        "owner": owner,
    }
    if created_at:
        record["created_at"] = record["updated_at"] = created_at
    record["search_text"] = search_text_for({**record, "created_at": created_at or repo.now_iso()}, meta)
    return repo.proposals.create(record)


def get(proposal_id: str) -> dict:
    p = repo.proposals.get(proposal_id)
    if not p:
        raise NotFound(proposal_id)
    return p


def update(proposal_id: str, changes: dict) -> dict:
    p = get(proposal_id)
    patch: dict = {}
    if "doc" in changes and isinstance(changes["doc"], dict):
        patch["doc"] = changes["doc"]
        cover = changes["doc"].get("cover") or {}
        if cover.get("title"):
            patch["project_name"] = cover["title"]
        if cover.get("client"):
            patch["client_name"] = cover["client"]
        if cover.get("version"):
            patch["version"] = cover["version"]
    if "status" in changes and changes["status"] in STATUSES:
        patch["status"] = changes["status"]
    if "inputs" in changes and isinstance(changes["inputs"], dict):
        patch["inputs"] = changes["inputs"]
    merged = {**p, **patch}
    patch["search_text"] = search_text_for(merged, merged.get("meta") or {})
    return repo.proposals.update(proposal_id, patch)


def regenerate_section(proposal_id: str, section_id: str, tone: str | None = None) -> dict:
    p = get(proposal_id)
    library, settings = _context()
    section = engine.regenerate_section(p["inputs"], p["doc"], section_id, library, settings, tone=tone)
    section = ai.enhance_section(section, p["inputs"], p.get("meta") or {}, tone=tone)
    doc = p["doc"]
    doc["sections"] = [section if s["id"] == section_id else s for s in doc["sections"]]
    repo.proposals.update(proposal_id, {"doc": doc})
    return section


def regenerate_all(proposal_id: str, inputs: dict | None = None) -> dict:
    p = get(proposal_id)
    inputs = inputs or p["inputs"]
    library, settings = _context()
    result = engine.generate(inputs, library, settings)
    doc = ai.enhance_document(result["doc"], inputs, result["meta"])
    old_cover = p["doc"].get("cover") or {}
    doc["cover"]["image"] = old_cover.get("image")
    doc["cover"]["client_logo"] = old_cover.get("client_logo") or doc["cover"].get("client_logo")
    repo.proposals.add_revision(p, note="قبل إعادة التوليد الكاملة")
    record = {"doc": doc, "inputs": inputs, "meta": result["meta"], "project_type": result["meta"]["type"],
              "sector": result["meta"]["sector"], "client_name": doc["cover"]["client"], "project_name": doc["cover"]["title"]}
    record["search_text"] = search_text_for({**p, **record}, result["meta"])
    return repo.proposals.update(proposal_id, record)


def duplicate(proposal_id: str) -> dict:
    p = get(proposal_id)
    doc = copy.deepcopy(p["doc"])
    doc["cover"]["title"] = f"{doc['cover']['title']} (نسخة)"
    doc["cover"]["version"] = "1.0"
    record = {
        "number": repo.settings.next_proposal_number(), "client_id": p.get("client_id"), "client_name": p["client_name"],
        "project_name": doc["cover"]["title"], "project_type": p.get("project_type"), "sector": p.get("sector"),
        "status": "draft", "version": "1.0", "inputs": copy.deepcopy(p["inputs"]), "doc": doc,
        "meta": copy.deepcopy(p.get("meta") or {}), "is_demo": False,
    }
    record["search_text"] = search_text_for({**record, "created_at": repo.now_iso()}, record["meta"])
    return repo.proposals.create(record)


def reuse_inputs(proposal_id: str) -> dict:
    """Inputs for starting a new proposal from an old one: same project setup, client cleared."""
    p = get(proposal_id)
    inputs = copy.deepcopy(p["inputs"])
    inputs["client"] = {}
    proj = inputs.get("project") or {}
    proj.pop("event_date", None)
    inputs["project"] = proj
    tl = inputs.get("timeline") or {}
    tl.pop("start_date", None)
    tl.pop("end_date", None)
    inputs["timeline"] = tl
    return inputs


def new_version(proposal_id: str, note: str = "") -> dict:
    p = get(proposal_id)
    repo.proposals.add_revision(p, note=note or f"النسخة {p.get('version', '1.0')}")
    try:
        major, minor = (p.get("version") or "1.0").split(".")[:2]
        version = f"{major}.{int(minor) + 1}"
    except ValueError:
        version = "1.1"
    doc = p["doc"]
    doc["cover"]["version"] = version
    return repo.proposals.update(proposal_id, {"doc": doc, "version": version})


def restore_revision(proposal_id: str, revision_id: str) -> dict:
    p = get(proposal_id)
    rev = repo.proposals.get_revision(revision_id)
    if not rev or rev["proposal_id"] != proposal_id:
        raise NotFound(revision_id)
    repo.proposals.add_revision(p, note="قبل الاسترجاع")
    return repo.proposals.update(proposal_id, {"doc": rev["doc"], "inputs": rev["inputs"]})


def save_as_template(proposal_id: str, name: str, description: str = "") -> dict:
    p = get(proposal_id)
    inputs = reuse_inputs(proposal_id)
    return repo.templates.create(name or p["project_name"], description, p.get("project_type") or "", inputs)
