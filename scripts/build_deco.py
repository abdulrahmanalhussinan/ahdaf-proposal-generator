"""Render the proposal designs' artwork (web/js/document/art.js) to transparent PNGs for PowerPoint.

    python scripts/build_deco.py

Run it after changing art.js; the PNGs are committed in app/exporters/deco/.
"""
from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "exporters" / "deco"
DESIGNS = ["ahdaf", "night", "bold", "minimal"]
KINDS = ["cover", "content"]  # dividers and the closing slide reuse the cover art


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    src = (ROOT / "web" / "js" / "document" / "art.js").read_text(encoding="utf-8")
    src = re.sub(r"^import .*$", "const icon = () => '';", src, flags=re.M).replace("export ", "")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1.5)
        page.set_content("<html><body style='margin:0;background:transparent'><div id=a style='position:relative;width:1280px;height:720px'></div>"
                         "<style>.pg-art{position:absolute;inset:0;width:100%;height:100%}</style></body></html>")
        page.add_script_tag(content=src + "\nwindow.art = art;")
        for d in DESIGNS:
            for k in KINDS:
                page.evaluate("([d, k]) => { document.getElementById('a').innerHTML = window.art(d, k, { layout: 'landscape' }); }", [d, k])
                page.locator("#a").screenshot(path=str(OUT / f"{d}-{k}.png"), omit_background=True)
        browser.close()
    print("built", len(list(OUT.glob("*.png"))), "images in", OUT)


if __name__ == "__main__":
    main()
