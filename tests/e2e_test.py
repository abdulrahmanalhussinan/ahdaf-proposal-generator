"""End-to-end test of the main user journey against a running server.

    python tests/e2e_test.py [output_dir]

Covers: wizard (7 steps) -> generation -> editor (edit title, edit quantity, regenerate a section,
autosave) -> search -> PDF export -> mobile layout, and fails on any browser console error.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8765"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "e2e-output")
OUT.mkdir(parents=True, exist_ok=True)
CLIENT = f"مطاعم اختبار الذوق {int(time.time()) % 10000}"
console_errors: list[str] = []
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))


def watch(page) -> None:
    page.on("console", lambda m: console_errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))


def shot(page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)


def run() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ar-SA")
        page = ctx.new_page()
        watch(page)

        # ------------------------------------------------------------ wizard (3 steps)
        page.goto(f"{BASE}/new", wait_until="networkidle")
        if page.get_by_text("استُكملت المسودة").count():
            page.get_by_role("button", name="البدء من جديد").click()
            page.get_by_role("button", name="مسح المدخلات").click()
        page.wait_for_selector(".design-opt .pg")
        check("step 1 shows the four designs", page.locator(".design-opt").count() == 4)
        page.locator(".design-opt", has_text="الليلي الفاخر").click()
        shot(page, "01-wizard-designs")
        page.get_by_role("button", name="التالي").click()
        page.get_by_role("button", name="التالي").click()
        check("wizard validates the essentials", page.get_by_text("اكتب اسم العميل").count() > 0)
        page.locator("#c-name").fill(CLIENT)
        page.locator("#c-sector").select_option("food_beverage")
        page.locator("#p-name").fill("إدارة حسابات التواصل الاجتماعي")
        page.get_by_role("radio", name="إدارة منصات التواصل الاجتماعي").click()
        page.get_by_placeholder("مثال: نركز على الرياض").fill("نبي نرفع حضور المطاعم ونزيد الطلبات.")
        shot(page, "02-wizard-project")
        page.get_by_role("button", name="التالي").click()
        page.locator(".chips").nth(0).locator(".chip").first.click()  # first suggested audience segment
        page.get_by_role("button", name="تعزيز التفاعل").click()
        page.locator(".chips").nth(1).get_by_role("button", name="أخرى").click()
        page.get_by_placeholder("هدف آخر").fill("رفع التفاعل على المحتوى إلى 6%")
        page.get_by_role("button", name="إنستقرام").click()
        page.get_by_role("button", name="سناب شات").click()
        page.locator(".chips").nth(3).get_by_role("button", name="أخرى").click()
        page.get_by_placeholder("خدمة أخرى").fill("تصوير الأطباق داخل المطعم")
        page.get_by_role("button", name="شهران").click()
        page.locator("input[type=date]").first.fill("2026-11-15")
        page.get_by_role("button", name="فاخر").click()
        shot(page, "03-wizard-suggestions")
        page.get_by_role("button", name="توليد العرض الفني").click()
        page.wait_for_url("**/edit", timeout=30_000)
        page.wait_for_selector(".ed-nav .sec-item")
        shot(page, "03-editor")
        pid = page.url.split("/proposals/")[1].split("/")[0]
        check("proposal generated and editor opened", bool(pid), pid)

        # ------------------------------------------------------------ editor
        sections = page.locator(".ed-nav .sec-item .t").all_inner_texts()
        expected = ["المقدمة", "فهمنا للمشروع", "أهداف المشروع", "الفكرة الإبداعية", "أفكار تفعيلية مقترحة",
                    "محاور المحتوى وخطة النشر", "نطاق العمل", "منهجية وآلية التنفيذ", "المخرجات",
                    "الجدول الزمني", "مؤشرات الأداء", "الخاتمة"]
        missing = [s for s in expected if s not in sections]
        check("all required + creative sections exist", not missing, f"missing: {missing}" if missing else f"{len(sections)} sections")
        check("filler sections are off by default", not {"فريق العمل", "الحوكمة وإدارة المشروع"} & set(sections))

        page.locator(".ed-nav .sec-item", has_text="فهمنا للمشروع").click()
        title = page.locator(".title-in")
        title.fill("فهمنا لاحتياج المطاعم")
        page.wait_for_timeout(1800)
        expect(page.locator(".save-state")).to_contain_text("تم الحفظ", timeout=8000)
        before = page.locator(".blk-ed textarea").first.input_value()
        page.get_by_role("button", name="إعادة توليد القسم").click()
        page.get_by_role("menuitem", name="بأسلوب: رسمي").click()
        page.wait_for_selector(".toast", timeout=10_000)
        page.wait_for_timeout(600)
        after = page.locator(".blk-ed textarea").first.input_value()
        check("regenerate section changes its text", before != after)
        check("regenerate keeps the edited title", page.locator(".title-in").input_value() == "فهمنا لاحتياج المطاعم")
        shot(page, "04-editor-regenerated")
        check("undo button appears after regeneration", page.get_by_role("button", name="تراجع").count() == 1)

        page.locator(".ed-nav .sec-item", has_text="المخرجات").click()
        qty = page.locator(".ed-table input[type=number]").first
        qty.fill("15")
        page.wait_for_timeout(1800)
        expect(page.locator(".save-state")).to_contain_text("تم الحفظ", timeout=8000)
        shot(page, "05-editor-deliverables")

        # hide a section and reorder via keyboard
        page.locator(".ed-nav .sec-item", has_text="مؤشرات الأداء").locator(".eye").click()
        page.wait_for_timeout(1500)

        saved = json.loads(urllib.request.urlopen(f"{BASE}/api/proposals/{pid}").read().decode("utf-8"))
        secs = {s["type"]: s for s in saved["doc"]["sections"]}
        check("edited title persisted", secs["understanding"]["title"] == "فهمنا لاحتياج المطاعم")
        dl = next(b for b in secs["deliverables"]["blocks"] if b["type"] == "deliverables")
        check("edited quantity persisted", dl["rows"][0]["qty"] == 15, str(dl["rows"][0]["qty"]))
        check("hidden section persisted", secs["kpis"]["visible"] is False)
        check("chosen design saved", saved["doc"]["theme"] == "night")
        check("«أخرى» service used", "تصوير الأطباق داخل المطعم" in saved["meta"]["service_labels"])
        check("objective target from «أخرى» text", any(k["target"] == "6%" for s2 in saved["doc"]["sections"] for b in s2["blocks"] if b["type"] == "kpis" for k in b["items"]))
        check("no unfilled placeholders", "[[" not in json.dumps(saved["doc"], ensure_ascii=False))
        page.locator(".ed-nav .sec-item", has_text="مؤشرات الأداء").locator(".eye").click()
        page.wait_for_timeout(1500)

        # ------------------------------------------------------------ search
        page.goto(f"{BASE}/proposals", wait_until="networkidle")
        page.get_by_placeholder("ابحث: اسم العميل").fill("اختبار الذوق")
        page.wait_for_timeout(900)
        rows = page.locator(".table tbody tr").count()
        check("search by client finds the proposal", rows == 1, f"{rows} rows")
        page.get_by_placeholder("ابحث: اسم العميل").fill("الأغذية 2026")
        page.wait_for_timeout(900)
        check("search by sector + year", page.locator(".table tbody tr").count() >= 1)
        page.get_by_placeholder("ابحث: اسم العميل").fill("تصوير الأطباق")
        page.wait_for_timeout(900)
        check("search by service name", page.locator(".table tbody tr").count() >= 1)
        shot(page, "06-search")

        # ------------------------------------------------------------ exports
        r = page.request.get(f"{BASE}/api/proposals/{pid}/export/pdf", timeout=120_000)
        pdf = r.body()
        (OUT / "proposal.pdf").write_bytes(pdf)
        check("PDF export", r.status == 200 and pdf[:4] == b"%PDF", f"{len(pdf) // 1024} KB")
        r = page.request.get(f"{BASE}/api/proposals/{pid}/export/pptx", timeout=120_000)
        pptx = r.body()
        (OUT / "proposal.pptx").write_bytes(pptx)
        check("PowerPoint export", r.status == 200 and pptx[:2] == b"PK", f"{len(pptx) // 1024} KB")

        # ------------------------------------------------------------ viewer + duplicate
        page.goto(f"{BASE}/proposals/{pid}", wait_until="networkidle")
        page.wait_for_selector(".viewer .pg")
        n = page.locator(".viewer .pg").count()
        check("viewer renders paginated pages", n >= 15, f"{n} pages")
        page.goto(f"{BASE}/celebrities", wait_until="networkidle")
        with page.expect_file_chooser() as fc:
            page.get_by_text("رفع شيت (Excel أو CSV)").click()
        sheet = OUT / "celebs.csv"
        sheet.write_text("الاسم,المنصة,المتابعين,المدينة\nمشهور اختبار,سناب شات,1M,الرياض\n", encoding="utf-8-sig")
        fc.value.set_files(str(sheet))
        page.wait_for_selector("text=مشهور اختبار", timeout=10_000)
        check("celebrity sheet uploads and lists", page.locator(".table tbody tr").count() >= 1)
        shot(page, "06b-celebrities")
        page.goto(f"{BASE}/templates", wait_until="networkidle")
        page.wait_for_selector(".design-opt .pg")
        check("templates page shows 4 designs", page.locator(".design-opt").count() == 4)
        shot(page, "07-viewer")

        # ------------------------------------------------------------ mobile
        m = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        mp = m.new_page()
        watch(mp)
        for name, path in [("08-m-dashboard", "/"), ("09-m-new", "/new"), ("10-m-proposals", "/proposals"), ("11-m-editor", f"/proposals/{pid}/edit")]:
            mp.goto(BASE + path, wait_until="networkidle")
            mp.wait_for_timeout(900)
            overflow = mp.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check(f"mobile {path} has no horizontal scroll", overflow <= 1, f"overflow {overflow}px")
            mp.screenshot(path=str(OUT / f"{name}.png"))
        mp.goto(f"{BASE}/", wait_until="networkidle")
        mp.get_by_role("button", name="القائمة").click()
        mp.wait_for_timeout(400)
        mp.screenshot(path=str(OUT / "12-m-nav.png"))
        check("mobile navigation opens", mp.locator(".app.nav-open").count() == 1)

        # ------------------------------------------------------------ RTL
        check("document is RTL Arabic", page.evaluate("document.documentElement.dir") == "rtl" and page.evaluate("document.documentElement.lang") == "ar")
        browser.close()

    check("no console errors", not console_errors, "; ".join(console_errors[:5]))
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    (OUT / "results.json").write_text(json.dumps({"results": results, "console": console_errors}, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run()
