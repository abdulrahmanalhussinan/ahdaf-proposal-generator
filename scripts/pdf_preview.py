"""Dev helper: export a proposal to PDF through the running server and render pages to PNG sheets."""
import json, sys, urllib.request, pathlib
import pymupdf
from PIL import Image

BASE = "http://127.0.0.1:8765"
match, out_dir = sys.argv[1], pathlib.Path(sys.argv[2])
out_dir.mkdir(parents=True, exist_ok=True)
items = json.loads(urllib.request.urlopen(f"{BASE}/api/proposals").read().decode("utf-8"))["items"]
pid = next(p["id"] for p in items if match in p["project_name"])
pdf = urllib.request.urlopen(f"{BASE}/api/proposals/{pid}/export/pdf", timeout=120).read()
(out_dir / "out.pdf").write_bytes(pdf)
doc = pymupdf.open(stream=pdf, filetype="pdf")
print("pages", len(doc), "size", doc[0].rect, "bytes", len(pdf))
thumbs = []
for pg in doc:
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(float(sys.argv[3]) if len(sys.argv) > 3 else 0.6, float(sys.argv[3]) if len(sys.argv) > 3 else 0.6))
    thumbs.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
w, h = thumbs[0].size
per = 6
for s in range(0, len(thumbs), per):
    chunk = thumbs[s:s + per]
    rows = (len(chunk) + 1) // 2
    im = Image.new("RGB", (2 * w + 24, rows * h + (rows + 1) * 8), (200, 200, 210))
    for i, t in enumerate(chunk):
        im.paste(t, (8 + (i % 2) * (w + 8), 8 + (i // 2) * (h + 8)))
    im.save(out_dir / f"sheet_{s // per + 1}.jpg", quality=85)
print("sheets", (len(thumbs) + per - 1) // per)
