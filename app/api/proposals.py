from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core.schemas import (GenerateRequest, ProposalUpdate, RegenerateAll, RegenerateSection,
                              TemplateFromProposal, VersionRequest)
from app.core.security import User, get_current_user, require_print_token
from app.data import repositories as repo
from app.exporters import pdf as pdf_exporter
from app.exporters import pptx_export
from app.services import proposals as svc

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


def _or_404(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="العرض غير موجود")


def _filename(p: dict, ext: str) -> str:
    base = f"أهداف - عرض فني - {p['client_name']} - {p['project_name']}"
    base = re.sub(r'[\\/:*?"<>|\[\]]+', " ", base)
    return re.sub(r"\s+", " ", base).strip()[:150] + f".{ext}"


def _attachment(data: bytes, media_type: str, filename: str) -> Response:
    disp = f"attachment; filename=\"proposal.{filename.rsplit('.', 1)[-1]}\"; filename*=UTF-8''{quote(filename)}"
    return Response(content=data, media_type=media_type, headers={"Content-Disposition": disp})


@router.get("")
def list_proposals(q: str = "", status: str = "", type: str = "", year: str = "", client_id: str = "",
                   user: User = Depends(get_current_user)):
    return {"items": repo.proposals.list(q=q, status=status, project_type=type, year=year, client_id=client_id),
            "years": repo.proposals.years()}


@router.post("/analyze")
def analyze(body: GenerateRequest, user: User = Depends(get_current_user)):
    """Dry run used by the wizard's last step: what was understood and what is missing."""
    return svc.analyze_inputs(body.inputs)


@router.post("/generate", status_code=201)
def generate(body: GenerateRequest, user: User = Depends(get_current_user)):
    if not ((body.inputs.get("client") or {}).get("name") or "").strip():
        raise HTTPException(status_code=422, detail="اسم العميل مطلوب")
    if not ((body.inputs.get("project") or {}).get("name") or "").strip():
        raise HTTPException(status_code=422, detail="اسم المشروع مطلوب")
    return svc.create_from_inputs(body.inputs, status=body.status, owner=user.id)


@router.get("/{proposal_id}")
def get_proposal(proposal_id: str, user: User = Depends(get_current_user)):
    return _or_404(svc.get, proposal_id)


@router.get("/{proposal_id}/print-data")
def print_data(proposal_id: str, token: str = Depends(require_print_token)):
    """Data for the headless print page (PDF export). Authorised by a one-time token."""
    p = _or_404(svc.get, proposal_id)
    return {"proposal": p, "settings": repo.settings.get_all()}


@router.put("/{proposal_id}")
def update_proposal(proposal_id: str, body: ProposalUpdate, user: User = Depends(get_current_user)):
    return _or_404(svc.update, proposal_id, body.model_dump(exclude_none=True))


@router.delete("/{proposal_id}", status_code=204)
def delete_proposal(proposal_id: str, user: User = Depends(get_current_user)):
    _or_404(svc.get, proposal_id)
    repo.proposals.delete(proposal_id)
    return Response(status_code=204)


@router.post("/{proposal_id}/duplicate", status_code=201)
def duplicate(proposal_id: str, user: User = Depends(get_current_user)):
    return _or_404(svc.duplicate, proposal_id)


@router.get("/{proposal_id}/reuse")
def reuse(proposal_id: str, user: User = Depends(get_current_user)):
    return {"inputs": _or_404(svc.reuse_inputs, proposal_id)}


@router.post("/{proposal_id}/sections/{section_id}/regenerate")
def regenerate_section(proposal_id: str, section_id: str, body: RegenerateSection,
                       user: User = Depends(get_current_user)):
    try:
        return _or_404(svc.regenerate_section, proposal_id, section_id, body.tone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{proposal_id}/regenerate")
def regenerate_all(proposal_id: str, body: RegenerateAll, user: User = Depends(get_current_user)):
    return _or_404(svc.regenerate_all, proposal_id, body.inputs)


@router.post("/{proposal_id}/versions")
def new_version(proposal_id: str, body: VersionRequest, user: User = Depends(get_current_user)):
    return _or_404(svc.new_version, proposal_id, body.note)


@router.get("/{proposal_id}/revisions")
def revisions(proposal_id: str, user: User = Depends(get_current_user)):
    _or_404(svc.get, proposal_id)
    return {"items": repo.proposals.revisions(proposal_id)}


@router.post("/{proposal_id}/revisions/{revision_id}/restore")
def restore(proposal_id: str, revision_id: str, user: User = Depends(get_current_user)):
    return _or_404(svc.restore_revision, proposal_id, revision_id)


@router.post("/{proposal_id}/save-as-template", status_code=201)
def save_as_template(proposal_id: str, body: TemplateFromProposal, user: User = Depends(get_current_user)):
    return _or_404(svc.save_as_template, proposal_id, body.name, body.description)


@router.get("/{proposal_id}/export/pdf")
def export_pdf(proposal_id: str, user: User = Depends(get_current_user)):
    p = _or_404(svc.get, proposal_id)
    try:
        data = pdf_exporter.render_pdf(proposal_id)
    except pdf_exporter.PdfError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return _attachment(data, "application/pdf", _filename(p, "pdf"))


@router.get("/{proposal_id}/export/pptx")
def export_pptx(proposal_id: str, user: User = Depends(get_current_user)):
    p = _or_404(svc.get, proposal_id)
    data = pptx_export.build_pptx(p, repo.settings.get_all())
    return _attachment(data, "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                       _filename(p, "pptx"))
