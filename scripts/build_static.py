"""Build the browser edition (GitHub Pages) into a folder.

    python scripts/build_static.py [out_dir]      (default: _site)

The output is a static site: the web app + the Python package zipped as py/app.zip, which the page
runs in the browser with Pyodide. No server, no secrets: data stays in each visitor's browser.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "web", out, ignore=shutil.ignore_patterns("print.html", "print.js"))

    py_dir = out / "py"
    py_dir.mkdir()
    with zipfile.ZipFile(py_dir / "app.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((ROOT / "app").rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                z.write(f, f.relative_to(ROOT).as_posix())

    try:
        build_id = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        build_id = "dev"

    index = out / "index.html"
    html = index.read_text(encoding="utf-8")
    html = html.replace('  <base href="/">\n', "")
    html = html.replace('  <meta name="robots" content="noindex">\n', "")
    html = html.replace(
        "  <title>",
        '  <meta name="description" content="مولّد العروض الفنية لأهداف للخدمات التسويقية: يكتب عرضًا فنيًا كاملًا بالعربية من معلومات المشروع، مع التعديل والتصدير PDF وPowerPoint.">\n'
        '  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>\n'
        "  <title>",
        1,
    )
    html = html.replace(
        '  <script type="module" src="js/main.js"></script>',
        f'  <script>window.AHDAF_STATIC = true; window.AHDAF_BUILD = "{build_id}";</script>\n'
        '  <script type="module" src="js/main.js"></script>',
    )
    index.write_text(html, encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
    print("built", build(target.resolve()))
