"""Reading the files the team uploads: client profiles (PDF / Word / PowerPoint / text) and
celebrity sheets (Excel / CSV). Pure Python so the same code runs on the server and in the browser
edition (Pyodide)."""
from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from datetime import date, datetime

from app.core.arabic import normalize

MAX_DOC_BYTES = 25 * 1024 * 1024
MAX_SHEET_BYTES = 15 * 1024 * 1024
MAX_TEXT_CHARS = 150_000

DOC_TYPES = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
             ".txt": "text/plain", ".md": "text/markdown"}
SHEET_TYPES = (".xlsx", ".xlsm", ".csv")


class FileError(Exception):
    """A file the user uploaded cannot be read; the message is shown to them as is."""


def ext_of(filename: str) -> str:
    m = re.search(r"\.[A-Za-z0-9]+$", filename or "")
    return m.group(0).lower() if m else ""


# =============================================================================== documents
def _clean(text: str) -> str:
    # NFKC turns Arabic presentation forms (common in PDFs) back into normal letters
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace(" ", " ").replace("‏", "").replace("‎", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def _xml_text(xml: str, para_tag: str, text_tag: str) -> str:
    out = []
    for para in re.findall(rf"<{para_tag}[ >].*?</{para_tag}>", xml, flags=re.S):
        runs = re.findall(rf"<{text_tag}(?: [^>]*)?>([^<]*)</{text_tag}>", para)
        line = "".join(runs).strip()
        if line:
            out.append(line)
    text = "\n".join(out)
    for ent, ch in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'")):
        text = text.replace(ent, ch)
    return text


def _pdf(data: bytes) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - pypdf is in requirements
        raise FileError("قراءة ملفات PDF غير متاحة على هذا الجهاز") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages[:120]]
    except Exception as exc:
        raise FileError("تعذر قراءة ملف PDF. تأكد أنه غير محمي بكلمة مرور.") from exc
    return "\n\n".join(pages), len(reader.pages)


def _docx(data: bytes) -> tuple[str, int | None]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    return _xml_text(xml, "w:p", "w:t"), None


def _pptx(data: bytes) -> tuple[str, int]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                        key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        parts = [_xml_text(z.read(n).decode("utf-8", "ignore"), "a:p", "a:t") for n in slides]
    return "\n\n".join(p for p in parts if p), len(slides)


def _plain(data: bytes) -> tuple[str, None]:
    for enc in ("utf-8-sig", "cp1256"):
        try:
            return data.decode(enc), None
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore"), None


def extract_document(filename: str, data: bytes) -> dict:
    """Text of an uploaded profile. Raises FileError with a user-facing message."""
    ext = ext_of(filename)
    if ext not in DOC_TYPES:
        raise FileError("الصيغ المسموحة للملف التعريفي: PDF، Word ‏(docx)، PowerPoint ‏(pptx)، أو نص")
    if len(data) > MAX_DOC_BYTES:
        raise FileError("الحد الأقصى لحجم الملف التعريفي 25 ميجابايت")
    try:
        reader = {".pdf": _pdf, ".docx": _docx, ".pptx": _pptx}.get(ext, _plain)
        text, pages = reader(data)
    except FileError:
        raise
    except (zipfile.BadZipFile, KeyError) as exc:
        raise FileError("تعذر فتح الملف. تأكد أنه ملف سليم وغير محمي.") from exc
    text = _clean(text)[:MAX_TEXT_CHARS]
    return {"text": text, "pages": pages, "mime": DOC_TYPES[ext], "chars": len(text),
            # a PDF made of images (scanned / exported as pictures) has almost no extractable text
            "scanned": ext == ".pdf" and len(text) < 80 * min(pages or 1, 5)}


# =============================================================================== celebrity sheets
# Header synonyms, compared after normalize() (hamza/ta-marbuta/diacritics folded, lower-case).
HEADERS = {
    "name": ["الاسم", "اسم المشهور", "المشهور", "المشاهير", "اسم المؤثر", "المؤثر", "المؤثرين", "اسم المشاهير", "الاسم الكامل",
             "اسم الحساب", "name", "full name", "influencer", "celebrity", "creator", "اسم"],
    "handle": ["الحساب", "اليوزر", "المعرف", "اسم المستخدم", "الرابط", "رابط الحساب", "الروابط", "username", "user name", "handle",
               "account", "link", "url", "profile"],
    "platforms": ["المنصه", "المنصات", "منصه", "platform", "platforms", "channel"],
    "followers": ["المتابعين", "عدد المتابعين", "المتابعون", "متابعين", "followers", "follower", "audience size", "reach", "الوصول"],
    "category": ["التصنيف", "المجال", "الفئه", "النوع", "نوع المحتوى", "المحتوى", "التخصص", "category", "niche", "field", "type", "genre"],
    "city": ["المدينه", "المنطقه", "مكان الاقامه", "الموقع", "city", "region", "location", "الدوله", "country"],
    "gender": ["الجنس", "gender", "sex"],
    "notes": ["ملاحظات", "ملاحظه", "notes", "note", "comments", "تعليق"],
}
PLATFORM_HEADERS = {
    "إنستقرام": ["انستقرام", "انستغرام", "انستا", "instagram", "insta", "ig"],
    "تيك توك": ["تيك توك", "تيكتوك", "tiktok", "tik tok"],
    "سناب شات": ["سناب", "سناب شات", "سنابشات", "snapchat", "snap"],
    "إكس": ["تويتر", "اكس", "x", "twitter"],
    "يوتيوب": ["يوتيوب", "youtube"],
}
_HEADER_LOOKUP = {normalize(s): field for field, syns in HEADERS.items() for s in syns}
_PLATFORM_LOOKUP = {normalize(s): label for label, syns in PLATFORM_HEADERS.items() for s in syns}


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    return re.sub(r"\s+", " ", str(v)).strip()


def _header_field(h: str) -> tuple[str, str] | None:
    n = normalize(re.sub(r"[()\[\]:*#_\-]+", " ", h)).strip()
    if not n:
        return None
    if n in _PLATFORM_LOOKUP:
        return "platform_col", _PLATFORM_LOOKUP[n]
    if n in _HEADER_LOOKUP:
        return _HEADER_LOOKUP[n], ""
    for key, field in _HEADER_LOOKUP.items():  # «عدد متابعين انستقرام», «اسم المشهور/ة»…
        if len(key) >= 4 and key in n:
            for pk, label in _PLATFORM_LOOKUP.items():
                if len(pk) >= 4 and pk in n and field in ("followers", "handle"):
                    return "platform_col", label
            return field, ""
    for pk, label in _PLATFORM_LOOKUP.items():
        if len(pk) >= 4 and pk in n:
            return "platform_col", label
    return None


def _find_header(rows: list[list[str]]) -> int | None:
    best, best_score = None, 0
    for i, row in enumerate(rows[:15]):
        fields = [_header_field(c) for c in row if c]
        score = sum(1 for f in fields if f)
        if any(f and f[0] == "name" for f in fields) and score > best_score:
            best, best_score = i, score
    return best


def _rows_to_people(rows: list[list[str]], sheet_title: str, multi_sheet: bool) -> list[dict]:
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return []
    h = _find_header(rows)
    if h is None:
        # no recognisable header: first column is the name, the rest is kept as is
        header, body = [f"عمود {i + 1}" for i in range(max(len(r) for r in rows))], rows
        mapping = {0: ("name", "")}
    else:
        header, body = rows[h], rows[h + 1:]
        mapping = {}
        for i, c in enumerate(header):
            f = _header_field(c) if c else None
            if f and not (f[0] in {m[0] for m in mapping.values()} and f[0] != "platform_col"):
                mapping[i] = f
    people = []
    for r in body:
        p = {"extra": {}}
        platform_vals = []
        for i, val in enumerate(r):
            if not val:
                continue
            field, label = mapping.get(i, (None, ""))
            if field == "platform_col":
                platform_vals.append((label, val))
            elif field:
                p[field] = val
            elif i < len(header) and header[i]:
                p["extra"][header[i]] = val
        name = (p.get("name") or "").strip()
        if not name or normalize(name) in _HEADER_LOOKUP or len(name) > 120:
            continue
        if platform_vals:
            labels = [lb for lb, _ in platform_vals]
            if not p.get("platforms"):
                p["platforms"] = "، ".join(dict.fromkeys(labels))
            for lb, val in platform_vals:
                if not p.get("handle") and (val.startswith("@") or "http" in val or "www." in val):
                    p["handle"] = val
                else:
                    p["extra"][lb] = val
            if not p.get("followers"):
                nums = [f"{lb}: {v}" for lb, v in platform_vals if re.fullmatch(r"[\d,.]+\s*[KkMmألفمليون]*", v)]
                if nums:
                    p["followers"] = "، ".join(nums)
        if multi_sheet and not p.get("category") and sheet_title:
            p["category"] = sheet_title
        people.append(p)
    return people


def parse_celebrity_sheet(filename: str, data: bytes) -> list[dict]:
    ext = ext_of(filename)
    if ext == ".xls":
        raise FileError("صيغة xls القديمة غير مدعومة. افتح الملف واحفظه بصيغة xlsx ثم ارفعه.")
    if ext not in SHEET_TYPES:
        raise FileError("ارفع الشيت بصيغة Excel ‏(xlsx) أو CSV")
    if len(data) > MAX_SHEET_BYTES:
        raise FileError("الحد الأقصى لحجم الشيت 15 ميجابايت")
    sheets: list[tuple[str, list[list[str]]]] = []
    if ext == ".csv":
        text = _plain(data)[0]
        try:
            dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        sheets.append(("", [[_cell(c) for c in row] for row in csv.reader(io.StringIO(text), dialect)]))
    else:
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover
            raise FileError("قراءة ملفات Excel غير متاحة على هذا الجهاز") from exc
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as exc:
            raise FileError("تعذر فتح ملف Excel. تأكد أنه غير محمي بكلمة مرور.") from exc
        for ws in wb.worksheets:
            rows = [[_cell(c) for c in row] for row in ws.iter_rows(values_only=True, max_row=5000)]
            sheets.append((ws.title, rows))
        wb.close()
    multi = sum(1 for _, rows in sheets if any(any(c for c in r) for r in rows)) > 1
    people = []
    for title, rows in sheets:
        people += _rows_to_people(rows, title, multi)
    if not people:
        raise FileError("ما لقيت أسماء في الشيت. تأكد أن فيه عمودًا للاسم (مثل: الاسم، اسم المشهور، Name).")
    return people
