"""Client profiles uploaded in the wizard: the file is kept, and its text is what Claude reads."""
from __future__ import annotations

import uuid

from app import config
from app.data import repositories as repo
from app.services import files


def store(filename: str, data: bytes, keep_file: bool = True) -> dict:
    """Read and save an uploaded profile. Raises files.FileError with a message for the user."""
    info = files.extract_document(filename, data)
    if not info["text"]:
        raise files.FileError("الملف لا يحتوي على نص يمكن قراءته (قد يكون صورًا فقط). ارفع نسخة PDF نصية أو Word.")
    stored = None
    if keep_file:
        stored = f"{uuid.uuid4().hex}{files.ext_of(filename)}"
        (config.UPLOAD_DIR / stored).write_bytes(data)
    doc = repo.documents.create(filename, info["mime"], len(data), stored, info["pages"], info["text"])
    return public(doc, scanned=info["scanned"])


def public(doc: dict, scanned: bool = False) -> dict:
    """What the browser keeps in the proposal inputs (never the full text)."""
    text = doc.get("text") or ""
    return {"id": doc["id"], "filename": doc["filename"], "pages": doc.get("pages"), "chars": len(text),
            "preview": text[:280], "scanned": scanned}
