"""Ahdaf Proposal Generator — application entry point.

Run:  python -m app            (or start.bat on Windows)
"""
from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.api import proposals, resources
from app.data.seed import ensure_seeded

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(_app):
    ensure_seeded(with_demo=True)
    yield


app = FastAPI(title="Ahdaf Proposal Generator", version="1.0.0", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)
app.include_router(proposals.router)
app.include_router(resources.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    logging.getLogger("ahdaf").exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "حدث خطأ غير متوقع في الخادم"})


_SAFE_FILE = re.compile(r"^[a-f0-9]{32}\.(png|jpg|webp|svg)$")


@app.get("/files/{name}")
def files(name: str):
    if not _SAFE_FILE.match(name):
        raise HTTPException(status_code=404)
    path = config.UPLOAD_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404)
    headers = {"Content-Security-Policy": "script-src 'none'"} if name.endswith(".svg") else {}
    return FileResponse(path, headers=headers)


@app.get("/print.html")
def print_page():
    return FileResponse(config.WEB_DIR / "print.html")


app.mount("/assets", StaticFiles(directory=config.WEB_DIR / "assets"), name="assets")
app.mount("/css", StaticFiles(directory=config.WEB_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=config.WEB_DIR / "js"), name="js")


@app.get("/")
@app.get("/{path:path}")
def spa(path: str = ""):
    if path.startswith("api/"):
        raise HTTPException(status_code=404)
    return FileResponse(config.WEB_DIR / "index.html")
