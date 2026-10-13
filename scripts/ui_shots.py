"""Dev helper: open pages in headless Edge, capture screenshots and console errors."""
import sys, json, pathlib
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:8765"
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
pages = sys.argv[2].split(",")
width = int(sys.argv[3]) if len(sys.argv) > 3 else 1440
height = int(sys.argv[4]) if len(sys.argv) > 4 else 900
errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge")
    ctx = b.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
    pg = ctx.new_page()
    pg.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
    for i, path in enumerate(pages):
        pg.goto(BASE + path, wait_until="networkidle")
        pg.wait_for_timeout(1200)
        pg.screenshot(path=str(out / f"{i:02d}.png"), full_page=False)
    b.close()
print("errors:", json.dumps(errors, ensure_ascii=False, indent=1))
