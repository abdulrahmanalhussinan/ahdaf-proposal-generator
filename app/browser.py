"""In-browser backend for the GitHub Pages edition.

The static site runs this package inside the visitor's browser with Pyodide. `handle()` receives
the same method/path/body the web app would send to the HTTP API and answers with the same JSON,
by calling the same service functions the FastAPI routes use. Data lives in a SQLite file in the
browser's own storage (IndexedDB) and never leaves the device.

Claude writing works here with the visitor's own API key, kept in their browser only: the page asks
`/api/ai/request` for the prompt, calls Claude itself (web/js/lib/ai.js), and sends the answer back
as `ai_content`, which goes through the same guards as on the server. Uploaded files arrive as base64.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any, Callable

from app.data import repositories as repo
from app.data.seed import ensure_seeded
from app.services import catalog, documents, files
from app.services import celebrities as celebs
from app.services import proposals as svc

LOCAL_USER = ("أنت (نسخة المتصفح)", "admin")
STATUS_KEYS = set(svc.STATUSES)
CLIENT_FIELDS = ("name", "sector", "contact_name", "contact_email", "contact_phone", "about", "website", "logo")


class HttpError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


_ROUTES: list[tuple[str, re.Pattern, Callable]] = []


def route(method: str, pattern: str):
    regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$")

    def deco(fn):
        _ROUTES.append((method, regex, fn))
        return fn

    return deco


def _get(fn, *args):
    try:
        return fn(*args)
    except svc.NotFound:
        raise HttpError(404, "العرض غير موجود")


# ------------------------------------------------------------------ meta
@route("GET", "/api/meta")
def _meta(q, b):
    data = catalog.meta(*LOCAL_USER)
    data["edition"] = "browser"
    return data


@route("GET", "/api/dashboard")
def _dashboard(q, b):
    return catalog.dashboard()


# ------------------------------------------------------------------ proposals
@route("GET", "/api/proposals")
def _list(q, b):
    return {"items": repo.proposals.list(q=q.get("q", ""), status=q.get("status", ""), project_type=q.get("type", ""),
                                         year=q.get("year", ""), client_id=q.get("client_id", "")),
            "years": repo.proposals.years()}


@route("POST", "/api/proposals/analyze")
def _analyze(q, b):
    return svc.analyze_inputs(b.get("inputs") or {})


@route("POST", "/api/proposals/generate")
def _generate(q, b):
    inputs = b.get("inputs") or {}
    if not ((inputs.get("client") or {}).get("name") or "").strip():
        raise HttpError(422, "اسم العميل مطلوب")
    if not ((inputs.get("project") or {}).get("name") or "").strip():
        raise HttpError(422, "اسم المشروع مطلوب")
    status = b.get("status") if b.get("status") in STATUS_KEYS else "draft"
    return svc.create_from_inputs(inputs, status=status, owner="browser", ai_content=_ai(b))


def _ai(b: dict) -> dict | None:
    content = b.get("ai_content")
    return content if isinstance(content, dict) else None


@route("POST", "/api/ai/request")
def _ai_request(q, b):
    try:
        return svc.ai_request(inputs=b.get("inputs"), proposal_id=b.get("proposal_id"), section_id=b.get("section_id"),
                              tone=b.get("tone"), concept=b.get("concept") if isinstance(b.get("concept"), dict) else None)
    except svc.NotFound:
        raise HttpError(404, "العرض غير موجود")


@route("GET", "/api/proposals/{pid}")
def _one(q, b, pid):
    return _get(svc.get, pid)


@route("PUT", "/api/proposals/{pid}")
def _update(q, b, pid):
    changes = {k: v for k, v in b.items() if k in ("doc", "inputs", "status") and v is not None}
    if "status" in changes and changes["status"] not in STATUS_KEYS:
        raise HttpError(422, "حالة غير صحيحة")
    return _get(svc.update, pid, changes)


@route("DELETE", "/api/proposals/{pid}")
def _delete(q, b, pid):
    _get(svc.get, pid)
    repo.proposals.delete(pid)
    return None


@route("POST", "/api/proposals/{pid}/duplicate")
def _duplicate(q, b, pid):
    return _get(svc.duplicate, pid)


@route("GET", "/api/proposals/{pid}/reuse")
def _reuse(q, b, pid):
    return {"inputs": _get(svc.reuse_inputs, pid)}


@route("POST", "/api/proposals/{pid}/sections/{sid}/regenerate")
def _regen_section(q, b, pid, sid):
    try:
        return _get(svc.regenerate_section, pid, sid, b.get("tone"), _ai(b))
    except ValueError as exc:
        raise HttpError(400, str(exc))


@route("POST", "/api/proposals/{pid}/regenerate")
def _regen_all(q, b, pid):
    return _get(svc.regenerate_all, pid, b.get("inputs"), _ai(b))


@route("POST", "/api/proposals/{pid}/versions")
def _version(q, b, pid):
    return _get(svc.new_version, pid, str(b.get("note") or "")[:300])


@route("GET", "/api/proposals/{pid}/revisions")
def _revisions(q, b, pid):
    _get(svc.get, pid)
    return {"items": repo.proposals.revisions(pid)}


@route("POST", "/api/proposals/{pid}/revisions/{rid}/restore")
def _restore(q, b, pid, rid):
    return _get(svc.restore_revision, pid, rid)


@route("POST", "/api/proposals/{pid}/save-as-template")
def _save_tpl(q, b, pid):
    name = str(b.get("name") or "").strip()[:120]
    if not name:
        raise HttpError(422, "اسم القالب مطلوب")
    return _get(svc.save_as_template, pid, name, str(b.get("description") or "")[:500])


# ------------------------------------------------------------------ library
def _kind(kind: str) -> str:
    if kind not in catalog.LIBRARY_LABELS:
        raise HttpError(404, "نوع غير معروف")
    return kind


@route("GET", "/api/library")
def _lib_overview(q, b):
    return catalog.library_overview()


@route("GET", "/api/library/{kind}")
def _lib_list(q, b, kind):
    return {"items": repo.library.list(_kind(kind))}


@route("POST", "/api/library/{kind}")
def _lib_create(q, b, kind):
    title = str(b.get("title") or "").strip()
    if not title:
        raise HttpError(422, "الاسم مطلوب")
    return repo.library.create(_kind(kind), title[:200], b.get("data") or {}, key=b.get("key"), sort=b.get("sort"),
                               active=b.get("active", True) is not False)


@route("PUT", "/api/library/{kind}/{iid}")
def _lib_update(q, b, kind, iid):
    item = repo.library.get(iid)
    if not item or item["kind"] != _kind(kind):
        raise HttpError(404, "العنصر غير موجود")
    return repo.library.update(iid, {k: v for k, v in b.items() if k in ("title", "data", "active", "sort", "key") and v is not None})


@route("DELETE", "/api/library/{kind}/{iid}")
def _lib_delete(q, b, kind, iid):
    item = repo.library.get(iid)
    if not item or item["kind"] != _kind(kind):
        raise HttpError(404, "العنصر غير موجود")
    repo.library.delete(iid)
    return None


# ------------------------------------------------------------------ clients
def _client_body(b: dict) -> dict:
    out = {f: (b.get(f) or None) for f in CLIENT_FIELDS}
    out["name"] = str(b.get("name") or "").strip()[:200]
    if not out["name"]:
        raise HttpError(422, "اسم العميل مطلوب")
    return out


@route("GET", "/api/clients")
def _clients(q, b):
    return {"items": repo.clients.list(q.get("q", ""))}


@route("POST", "/api/clients")
def _client_create(q, b):
    body = _client_body(b)
    if repo.clients.find_by_name(body["name"]):
        raise HttpError(409, "يوجد عميل بهذا الاسم")
    return repo.clients.create(body)


@route("GET", "/api/clients/{cid}")
def _client(q, b, cid):
    c = repo.clients.get(cid)
    if not c:
        raise HttpError(404, "العميل غير موجود")
    return {**c, "proposals": repo.proposals.list(client_id=cid)}


@route("PUT", "/api/clients/{cid}")
def _client_update(q, b, cid):
    if not repo.clients.get(cid):
        raise HttpError(404, "العميل غير موجود")
    return repo.clients.update(cid, _client_body(b))


@route("DELETE", "/api/clients/{cid}")
def _client_delete(q, b, cid):
    repo.clients.delete(cid)
    return None


# ------------------------------------------------------------------ templates
@route("GET", "/api/templates")
def _templates(q, b):
    return {"items": repo.templates.list()}


@route("POST", "/api/templates")
def _tpl_create(q, b):
    return repo.templates.create(str(b.get("name") or "قالب")[:120], str(b.get("description") or "")[:500],
                                 str(b.get("project_type") or "")[:40], b.get("inputs") or {})


@route("PUT", "/api/templates/{tid}")
def _tpl_update(q, b, tid):
    if not repo.templates.get(tid):
        raise HttpError(404, "القالب غير موجود")
    return repo.templates.update(tid, {k: b[k] for k in ("name", "description", "project_type", "inputs") if k in b})


@route("DELETE", "/api/templates/{tid}")
def _tpl_delete(q, b, tid):
    repo.templates.delete(tid)
    return None


# ------------------------------------------------------------------ settings
@route("GET", "/api/settings")
def _settings(q, b):
    return catalog.settings_values()


@route("PUT", "/api/settings")
def _settings_put(q, b):
    return catalog.save_settings(b.get("values") or {})


# ------------------------------------------------------------------ celebrities & documents
def _file(b: dict) -> tuple[str, bytes]:
    try:
        return str(b.get("filename") or "ملف")[:200], base64.b64decode(b.get("data") or "")
    except (ValueError, TypeError):
        raise HttpError(422, "تعذر قراءة الملف")


@route("GET", "/api/celebrities")
def _celebs(q, b):
    return celebs.overview(q.get("q", ""))


@route("POST", "/api/celebrities/import")
def _celebs_import(q, b):
    try:
        return celebs.import_file(*_file(b))
    except files.FileError as exc:
        raise HttpError(415, str(exc))


@route("DELETE", "/api/celebrities")
def _celebs_clear(q, b):
    if q.get("source"):
        repo.celebrities.delete_source(q["source"])
    else:
        repo.celebrities.clear()
    return None


@route("DELETE", "/api/celebrities/{cid}")
def _celeb_delete(q, b, cid):
    repo.celebrities.delete(cid)
    return None


@route("POST", "/api/documents")
def _doc_upload(q, b):
    try:
        return documents.store(*_file(b), keep_file=False)  # browser storage keeps the text only
    except files.FileError as exc:
        raise HttpError(415, str(exc))


# ------------------------------------------------------------------ entry points
def init() -> None:
    ensure_seeded()


def handle(method: str, path: str, query_json: str = "{}", body_json: str = "null") -> str:
    """Return JSON text: {"status": int, "body": any}."""
    try:
        query: dict[str, Any] = json.loads(query_json or "{}")
        body = json.loads(body_json or "null") or {}
        for m, regex, fn in _ROUTES:
            if m != method:
                continue
            match = regex.match(path)
            if match:
                result = fn(query, body, **match.groupdict())
                status = 204 if result is None else 201 if method == "POST" and path.endswith(("/generate", "/duplicate", "/save-as-template", "/import", "/documents")) else 200
                return json.dumps({"status": status, "body": result}, ensure_ascii=False, default=str)
        raise HttpError(404, "غير موجود")
    except HttpError as exc:
        return json.dumps({"status": exc.status, "body": {"detail": exc.detail}}, ensure_ascii=False)
    except Exception as exc:  # surface as an API-style error, like the server's handler does
        return json.dumps({"status": 500, "body": {"detail": f"حدث خطأ غير متوقع: {exc}"}}, ensure_ascii=False)


def export_pptx(proposal_id: str) -> bytes:
    from app.exporters.pptx_export import build_pptx
    return build_pptx(_get(svc.get, proposal_id), repo.settings.get_all())
