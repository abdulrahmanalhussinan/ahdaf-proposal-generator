"""End-to-end test of the browser edition (GitHub Pages build).

    python scripts/build_static.py
    (serve _site at http://127.0.0.1:8899/ahdaf-proposal-generator/)
    python tests/e2e_static_test.py http://127.0.0.1:8899/ahdaf-proposal-generator/ out_dir
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/ahdaf-proposal-generator/"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e-static-output")
OUT.mkdir(parents=True, exist_ok=True)
CLIENT = f"متاجر اختبار المتصفح {int(time.time()) % 10000}"
errors: list[str] = []
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))


def boot(page):
    page.wait_for_selector(".side nav", timeout=120_000)


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

    t0 = time.time()
    page.goto(BASE, wait_until="domcontentloaded")
    check("boot screen shows while loading", page.locator(".boot").count() == 1)
    boot(page)
    check("browser edition boots", True, f"{time.time() - t0:.1f}s first load")
    page.wait_for_selector(".table tbody tr")
    rows = page.locator(".table tbody tr").count()
    check("demo proposals seeded", rows == 4, f"{rows} rows")
    page.screenshot(path=str(OUT / "01-dashboard.png"))

    page.get_by_role("link", name="إنشاء عرض جديد").first.click()
    page.wait_for_selector("#c-name")
    check("hash routing", "#/new" in page.url, page.url)
    page.locator("#c-name").fill(CLIENT)
    page.locator("#c-sector").select_option("retail")
    page.get_by_role("button", name="التالي").click()
    page.locator("#p-name").fill("حملة الجمعة البيضاء")
    page.get_by_role("radio", name="حملة تسويقية متكاملة").click()
    page.get_by_placeholder("مثال: إدارة حساب الشركة على تيك توك").fill("حملة رقمية متكاملة لموسم الجمعة البيضاء على سناب شات وتيك توك.")
    for _ in range(4):
        page.get_by_role("button", name="التالي").click()
    page.get_by_placeholder("رفع الوعي بالعلامة في الرياض").fill("زيادة المبيعات خلال الموسم 25%")
    page.get_by_role("button", name="التالي").click()
    page.wait_for_selector(".analysis div")
    page.get_by_role("button", name="توليد العرض الفني").click()
    page.wait_for_url("**/edit", timeout=60_000)
    page.wait_for_selector(".ed-nav .sec-item")
    pid = page.url.split("#/proposals/")[1].split("/")[0]
    check("proposal generated in the browser", bool(pid), pid)
    page.screenshot(path=str(OUT / "02-editor.png"))

    page.locator(".ed-nav .sec-item", has_text="فهمنا للمشروع").click()
    page.locator(".title-in").fill("فهمنا لموسم الجمعة البيضاء")
    expect(page.locator(".save-state")).to_contain_text("تم الحفظ", timeout=10_000)
    before = page.locator(".blk-ed textarea").first.input_value()
    page.get_by_role("button", name="إعادة توليد القسم").click()
    page.get_by_role("menuitem", name="بأسلوب: تسويقي").click()
    page.wait_for_timeout(1500)
    check("regenerate section in the browser", page.locator(".blk-ed textarea").first.input_value() != before)

    # PDF: stub the print dialog and inspect what would be printed
    page.evaluate("window.__printed = 0; window.print = () => { window.__printed++; }")
    page.get_by_role("button", name="تصدير PDF").click()
    if page.get_by_role("button", name="تصدير على أي حال").count():
        page.get_by_role("button", name="تصدير على أي حال").click()
    page.wait_for_function("window.__printed > 0", timeout=60_000)
    pages = page.locator("#print-root .pg").count()
    check("PDF print layout prepared", pages >= 15, f"{pages} pages")
    page.emulate_media(media="print")
    pdf = page.pdf(prefer_css_page_size=True, print_background=True)
    (OUT / "browser-print.pdf").write_bytes(pdf)
    page.emulate_media(media="screen")
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    check("printed PDF has the proposal pages", pdf[:4] == b"%PDF", f"{len(pdf) // 1024} KB")

    # PowerPoint generated in the browser (installs python-pptx on first use)
    with page.expect_download(timeout=240_000) as dl:
        page.get_by_role("button", name="PowerPoint").click()
    target = OUT / "browser.pptx"
    dl.value.save_as(str(target))
    check("PowerPoint export in the browser", target.read_bytes()[:2] == b"PK", f"{target.stat().st_size // 1024} KB")

    # persistence across reloads (IndexedDB)
    page.wait_for_timeout(1200)
    page.goto(BASE + "#/proposals", wait_until="domcontentloaded")
    boot(page)
    page.wait_for_selector(".table tbody tr")
    page.get_by_placeholder("ابحث: اسم العميل").fill("اختبار المتصفح")
    page.wait_for_timeout(800)
    check("data persists after reload + search works", page.locator(".table tbody tr").count() == 1)
    page.goto(BASE + f"#/proposals/{pid}/edit")
    page.wait_for_selector(".ed-nav .sec-item")
    titles = page.locator(".ed-nav .sec-item .t").all_inner_texts()
    check("edited title persisted", "فهمنا لموسم الجمعة البيضاء" in titles)

    m = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    mp = m.new_page()
    mp.goto(BASE, wait_until="domcontentloaded")
    boot(mp)
    mp.wait_for_timeout(800)
    overflow = mp.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    check("mobile has no horizontal scroll", overflow <= 1, f"{overflow}px")
    mp.screenshot(path=str(OUT / "03-mobile.png"))
    browser.close()

real_errors = [e for e in errors if "favicon" not in e]
check("no console errors", not real_errors, "; ".join(real_errors[:4]))
failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
(OUT / "results.json").write_text(json.dumps({"results": results, "console": errors}, ensure_ascii=False, indent=1), encoding="utf-8")
sys.exit(1 if failed else 0)
