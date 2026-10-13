"""Dev helper: render a PDF's pages into contact sheets (6 per image)."""
import sys, pathlib, pymupdf
from PIL import Image
src, out, scale = sys.argv[1], pathlib.Path(sys.argv[2]), float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
out.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(src)
th = []
for pg in doc:
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
    th.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
w, h = th[0].size
for s in range(0, len(th), 6):
    ch = th[s:s + 6]; rows = (len(ch) + 1) // 2
    im = Image.new("RGB", (2 * w + 24, rows * h + (rows + 1) * 8), (200, 200, 210))
    for i, t in enumerate(ch):
        im.paste(t, (8 + (i % 2) * (w + 8), 8 + (i // 2) * (h + 8)))
    im.save(out / f"sheet_{s // 6 + 1}.jpg", quality=85)
print(len(th), "pages")
