"""Application configuration.

All secrets (AI keys, future DB credentials) are read from the environment or
from a local `.env` file on the server. Nothing here is ever sent to the browser.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE per line) so we avoid an extra dependency."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("AHDAF_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "ahdaf.db"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
WEB_DIR = BASE_DIR / "web"

HOST = os.getenv("AHDAF_HOST", "127.0.0.1")
PORT = int(os.getenv("AHDAF_PORT", "8765"))

# AI writing provider: "rules" (built-in engine, default), "claude", or "auto"
# (use Claude when a key is configured, otherwise the built-in engine).
AI_PROVIDER = os.getenv("AI_PROVIDER", "auto").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")

# Uploads
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/svg+xml": ".svg"}

# Browser used for PDF rendering (Playwright channel). Edge ships with Windows.
PDF_BROWSER_CHANNEL = os.getenv("PDF_BROWSER_CHANNEL", "msedge")

for _d in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
