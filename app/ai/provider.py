"""AI writing layer.

The built-in rules engine (app.generator) always produces the full proposal. When a Claude API
key is configured on the server (ANTHROPIC_API_KEY in .env), this module asks Claude to polish the
narrative text of the generated sections. Structure, tables, quantities and dates are never sent for
rewriting, and every rewritten segment passes two guards before it is accepted:
  - every [[placeholder]] in the original must survive unchanged;
  - no number may appear that is not in the original text or in the user's inputs.
Segments that fail a guard keep the original wording. Any API error falls back silently to the
rules-engine text, so generation never breaks because of the AI provider.

The API key lives only on the server; the browser only learns whether AI is enabled.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from app import config
from app.generator.analyzer import DETAILS, TONES

log = logging.getLogger("ahdaf.ai")
PROMPTS_DIR = Path(__file__).parent / "prompts"

NARRATIVE_BLOCKS = {"paragraph", "lead", "callout"}
CARD_BLOCKS = {"cards"}
SKIP_SECTIONS = {"about"}  # official company copy is never rewritten

_PLACEHOLDER = re.compile(r"\[\[[^\]]+\]\]")
_NUMBER = re.compile(r"[0-9٠-٩]+(?:[.,][0-9٠-٩]+)?")

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
                "required": ["id", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["segments"],
    "additionalProperties": False,
}


def provider_name() -> str:
    if config.AI_PROVIDER == "rules":
        return "rules"
    if config.AI_PROVIDER in ("claude", "auto") and config.ANTHROPIC_API_KEY:
        return "claude"
    return "rules"


def status() -> dict:
    name = provider_name()
    return {"provider": name, "enabled": name == "claude", "model": config.CLAUDE_MODEL if name == "claude" else None}


@lru_cache(maxsize=4)
def _prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic  # imported lazily: only needed when AI is enabled

        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def set_client(client) -> None:
    """Inject a client (used by tests)."""
    global _client
    _client = client


# ------------------------------------------------------------------ facts & segments
def project_facts(inputs: dict, meta: dict) -> str:
    c = inputs.get("client") or {}
    p = inputs.get("project") or {}
    s = inputs.get("scope") or {}
    g = inputs.get("goals") or {}
    t = inputs.get("timeline") or {}
    a = (meta or {}).get("analysis") or {}
    lines = [
        f"العميل: {c.get('name') or 'غير محدد'}",
        f"نبذة عن العميل: {c.get('about') or 'غير متوفرة'}",
        f"القطاع: {a.get('sector') or c.get('sector') or 'غير محدد'}",
        f"اسم المشروع: {p.get('name') or 'غير محدد'}",
        f"نوع المشروع: {a.get('type') or ''}",
        f"وصف المشروع: {p.get('description') or 'غير متوفر'}",
        f"التحدي كما ذكره العميل: {p.get('challenge') or 'غير مذكور'}",
        f"الجمهور المستهدف: {p.get('audience') or 'غير محدد'}",
        f"المنصات: {'، '.join(a.get('platforms') or []) or 'غير محددة'}",
        f"المدة: {a.get('duration') or ''}",
        f"تاريخ البداية: {t.get('start_date') or 'غير محدد'}",
        f"نطاق العمل: {s.get('description') or ''}",
        f"الخدمات: {'، '.join((meta or {}).get('service_labels') or [])}",
        f"الأهداف: {g.get('objectives') or 'لم تُذكر (الأهداف في العرض مقترحة)'}",
        f"متطلبات خاصة: {(inputs.get('preferences') or {}).get('requirements') or 'لا يوجد'}",
    ]
    return "\n".join(lines)


def _segments(sections: list[dict]) -> list[dict]:
    out = []
    for s in sections:
        if s.get("type") in SKIP_SECTIONS or not s.get("visible", True):
            continue
        for b in s.get("blocks", []):
            if b.get("type") in NARRATIVE_BLOCKS and b.get("text"):
                out.append({"id": f"{s['id']}|{b['id']}|text", "section": s.get("title", ""), "kind": b["type"], "text": b["text"]})
            elif b.get("type") in CARD_BLOCKS:
                for i, item in enumerate(b.get("items") or []):
                    if item.get("text"):
                        out.append({"id": f"{s['id']}|{b['id']}|item{i}", "section": s.get("title", ""),
                                    "kind": f"بطاقة: {item.get('title', '')}", "text": item["text"]})
            elif b.get("type") == "objectives":
                for i, item in enumerate(b.get("items") or []):
                    if item.get("text"):
                        out.append({"id": f"{s['id']}|{b['id']}|item{i}", "section": s.get("title", ""),
                                    "kind": f"هدف: {item.get('title', '')}", "text": item["text"]})
    return out


def _guard(original: str, rewritten: str, facts: str) -> bool:
    if not rewritten or not rewritten.strip():
        return False
    if set(_PLACEHOLDER.findall(original)) - set(_PLACEHOLDER.findall(rewritten)):
        return False
    allowed = set(_NUMBER.findall(original)) | set(_NUMBER.findall(facts))
    if set(_NUMBER.findall(rewritten)) - allowed:
        return False
    return len(rewritten) <= max(400, len(original) * 2.5)


def _apply(sections: list[dict], rewrites: dict[str, str], originals: dict[str, str], facts: str) -> int:
    applied = 0
    for s in sections:
        for b in s.get("blocks", []):
            key = f"{s['id']}|{b['id']}|text"
            if key in rewrites and _guard(originals[key], rewrites[key], facts):
                b["text"] = rewrites[key].strip()
                applied += 1
            for i, item in enumerate(b.get("items") or []) if isinstance(b.get("items"), list) else []:
                ikey = f"{s['id']}|{b['id']}|item{i}"
                if ikey in rewrites and isinstance(item, dict) and _guard(originals[ikey], rewrites[ikey], facts):
                    item["text"] = rewrites[ikey].strip()
                    applied += 1
    return applied


def _rewrite(sections: list[dict], inputs: dict, meta: dict, tone: str | None) -> int:
    segs = _segments(sections)
    if not segs:
        return 0
    prefs = inputs.get("preferences") or {}
    tone_key = tone or prefs.get("tone") or "corporate"
    facts = project_facts(inputs, meta)
    user = _prompt("rewrite").format(
        project_facts=facts,
        tone=prefs.get("tone_other") or TONES.get(tone_key, tone_key),
        detail=DETAILS.get(prefs.get("detail") or "medium", "متوسط"),
        segments=json.dumps([{k: v for k, v in s.items()} for s in segs], ensure_ascii=False, indent=1),
    )
    client = _get_client()
    response = client.beta.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        system=_prompt("system"),
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        log.warning("AI rewrite declined; keeping rules-engine text")
        return 0
    text = next((b.text for b in response.content if b.type == "text"), "")
    data = json.loads(text)
    rewrites = {seg["id"]: seg["text"] for seg in data.get("segments", []) if isinstance(seg, dict)}
    originals = {s["id"]: s["text"] for s in segs}
    return _apply(sections, rewrites, originals, facts)


# ------------------------------------------------------------------ public API
def enhance_document(doc: dict, inputs: dict, meta: dict) -> dict:
    if provider_name() != "claude":
        return doc
    try:
        n = _rewrite(doc.get("sections", []), inputs, meta, None)
        doc["ai"] = {"provider": "claude", "model": config.CLAUDE_MODEL, "segments": n}
    except Exception as exc:  # never block generation on the AI provider
        log.warning("AI enhancement skipped: %s", exc)
    return doc


def enhance_section(section: dict, inputs: dict, meta: dict, tone: str | None = None) -> dict:
    if provider_name() != "claude":
        return section
    try:
        _rewrite([section], inputs, meta, tone)
    except Exception as exc:
        log.warning("AI section enhancement skipped: %s", exc)
    return section
