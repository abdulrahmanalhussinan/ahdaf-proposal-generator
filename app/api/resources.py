"""Library, clients, templates, settings, meta, dashboard and uploads."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app import config
from app.core.schemas import ClientIn, LibraryItemIn, SettingsIn, TemplateIn
from app.core.security import User, get_current_user
from app.data import repositories as repo
from app.services import catalog
from app.services.catalog import LIBRARY_LABELS

router = APIRouter(prefix="/api", tags=["resources"])


# ------------------------------------------------------------------ meta & dashboard
@router.get("/meta")
def meta(user: User = Depends(get_current_user)):
    return catalog.meta(user.name, user.role)


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user)):
    return catalog.dashboard()


# ------------------------------------------------------------------ library
def _kind(kind: str) -> str:
    if kind not in LIBRARY_LABELS:
        raise HTTPException(status_code=404, detail="نوع غير معروف")
    return kind


@router.get("/library")
def library_overview(user: User = Depends(get_current_user)):
    return catalog.library_overview()


@router.get("/library/{kind}")
def library_list(kind: str, user: User = Depends(get_current_user)):
    return {"items": repo.library.list(_kind(kind))}


@router.post("/library/{kind}", status_code=201)
def library_create(kind: str, body: LibraryItemIn, user: User = Depends(get_current_user)):
    return repo.library.create(_kind(kind), body.title, body.data, key=body.key, sort=body.sort, active=body.active)


@router.put("/library/{kind}/{item_id}")
def library_update(kind: str, item_id: str, body: LibraryItemIn, user: User = Depends(get_current_user)):
    item = repo.library.get(item_id)
    if not item or item["kind"] != _kind(kind):
        raise HTTPException(status_code=404, detail="العنصر غير موجود")
    return repo.library.update(item_id, body.model_dump(exclude_none=True))


@router.delete("/library/{kind}/{item_id}", status_code=204)
def library_delete(kind: str, item_id: str, user: User = Depends(get_current_user)):
    item = repo.library.get(item_id)
    if not item or item["kind"] != _kind(kind):
        raise HTTPException(status_code=404, detail="العنصر غير موجود")
    repo.library.delete(item_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ clients
@router.get("/clients")
def clients_list(q: str = "", user: User = Depends(get_current_user)):
    return {"items": repo.clients.list(q)}


@router.post("/clients", status_code=201)
def clients_create(body: ClientIn, user: User = Depends(get_current_user)):
    if repo.clients.find_by_name(body.name):
        raise HTTPException(status_code=409, detail="يوجد عميل بهذا الاسم")
    return repo.clients.create(body.model_dump())


@router.get("/clients/{client_id}")
def clients_get(client_id: str, user: User = Depends(get_current_user)):
    c = repo.clients.get(client_id)
    if not c:
        raise HTTPException(status_code=404, detail="العميل غير موجود")
    return {**c, "proposals": repo.proposals.list(client_id=client_id)}


@router.put("/clients/{client_id}")
def clients_update(client_id: str, body: ClientIn, user: User = Depends(get_current_user)):
    if not repo.clients.get(client_id):
        raise HTTPException(status_code=404, detail="العميل غير موجود")
    return repo.clients.update(client_id, body.model_dump())


@router.delete("/clients/{client_id}", status_code=204)
def clients_delete(client_id: str, user: User = Depends(get_current_user)):
    repo.clients.delete(client_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ templates
@router.get("/templates")
def templates_list(user: User = Depends(get_current_user)):
    return {"items": repo.templates.list()}


@router.post("/templates", status_code=201)
def templates_create(body: TemplateIn, user: User = Depends(get_current_user)):
    return repo.templates.create(body.name, body.description, body.project_type, body.inputs)


@router.put("/templates/{tid}")
def templates_update(tid: str, body: TemplateIn, user: User = Depends(get_current_user)):
    if not repo.templates.get(tid):
        raise HTTPException(status_code=404, detail="القالب غير موجود")
    return repo.templates.update(tid, body.model_dump())


@router.delete("/templates/{tid}", status_code=204)
def templates_delete(tid: str, user: User = Depends(get_current_user)):
    repo.templates.delete(tid)
    return Response(status_code=204)


# ------------------------------------------------------------------ settings
@router.get("/settings")
def settings_get(user: User = Depends(get_current_user)):
    return catalog.settings_values()


@router.put("/settings")
def settings_put(body: SettingsIn, user: User = Depends(get_current_user)):
    return catalog.save_settings(body.values)


# ------------------------------------------------------------------ uploads
@router.post("/uploads", status_code=201)
async def upload(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    ext = config.ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=415, detail="الصيغ المسموحة: PNG، JPG، WEBP، SVG")
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="الحد الأقصى لحجم الصورة 8 ميجابايت")
    if ext == ".svg" and (b"<script" in data.lower() or b"javascript:" in data.lower()):
        raise HTTPException(status_code=415, detail="ملف SVG يحتوي على شيفرة غير مسموحة")
    stored = f"{uuid.uuid4().hex}{ext}"
    (config.UPLOAD_DIR / stored).write_bytes(data)
    return repo.uploads.create(file.filename or stored, file.content_type, len(data), stored)
