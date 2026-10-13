"""PDF export.

The proposal is laid out by the same page renderer the editor preview uses (web/js/document),
so the PDF matches what the user reviewed. A headless Chromium-based browser (Microsoft Edge on
Windows, or Playwright's bundled Chromium) opens the print page with a one-time token, waits until
fonts are loaded and pagination is finished, then prints vector pages with selectable Arabic text.
"""
from __future__ import annotations

import logging
import threading

from app import config
from app.core.security import issue_print_token

log = logging.getLogger("ahdaf.pdf")
_lock = threading.Lock()


class PdfError(Exception):
    pass


def _base_url() -> str:
    host = "127.0.0.1" if config.HOST in ("0.0.0.0", "") else config.HOST
    return f"http://{host}:{config.PORT}"


def render_pdf(proposal_id: str, base_url: str | None = None, timeout_ms: int = 45_000) -> bytes:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise PdfError("مكتبة Playwright غير مثبتة على الخادم") from exc

    token = issue_print_token(proposal_id)
    url = f"{base_url or _base_url()}/print.html?id={proposal_id}&token={token}"
    with _lock, sync_playwright() as pw:
        browser = None
        try:
            try:
                browser = pw.chromium.launch(channel=config.PDF_BROWSER_CHANNEL, headless=True)
            except Exception:
                browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_function("window.__PRINT_READY__ === true || !!window.__PRINT_ERROR__", timeout=timeout_ms)
            failure = page.evaluate("window.__PRINT_ERROR__ || null")
            if failure:
                raise PdfError(f"تعذر تجهيز صفحة الطباعة: {failure}")
            pdf = page.pdf(prefer_css_page_size=True, print_background=True,
                           margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
            if errors:
                log.warning("print page reported errors: %s", errors)
            return pdf
        except PdfError:
            raise
        except Exception as exc:
            log.exception("PDF rendering failed")
            raise PdfError("تعذر إنشاء ملف PDF. تأكد من تثبيت متصفح Edge أو Chromium على الخادم.") from exc
        finally:
            if browser:
                browser.close()
