"""Arabic language helpers: normalisation for search, grammar for counted nouns,
list joining, prepositions and dates."""
from __future__ import annotations

import re
from datetime import date

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_ARABIC_LETTER = re.compile(r"[ء-ي]")

MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
          "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def normalize(text: str) -> str:
    """Normalise Arabic text so that search ignores hamza/ta-marbuta/diacritic variants."""
    if not text:
        return ""
    t = _TASHKEEL.sub("", str(text))
    t = re.sub("[إأآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    t = re.sub(r"[٠-٩]", lambda m: str(ord(m.group()) - 0x0660), t)
    return re.sub(r"\s+", " ", t).strip().lower()


def is_arabic(text: str) -> bool:
    return bool(text) and bool(_ARABIC_LETTER.match(text.strip()[:1] or ""))


def join(items: list[str], conj: str = "و") -> str:
    """['أ','ب','ج'] -> 'أ، وب، وج'"""
    items = [i.strip() for i in items if i and i.strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conj}{items[1]}"
    return items[0] + "".join(f"، {conj}{i}" for i in items[1:])


def join_or(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return "، ".join(items[:-1]) + f" أو {items[-1]}"


def li(name: str) -> str:
    """Attach the preposition لـ correctly: الشركة -> للشركة, شركة -> لشركة, Nike -> لـ Nike."""
    name = (name or "").strip()
    if not name:
        return ""
    if name.startswith("ال"):
        return "ل" + name[1:]
    if is_arabic(name):
        return "ل" + name
    return "لـ" + name


def bi(name: str) -> str:
    """Attach the preposition بـ."""
    name = (name or "").strip()
    if not name:
        return ""
    if is_arabic(name):
        return "ب" + name
    return "بـ" + name


_COUNTED = {
    # unit: (singular, dual, plural 3-10, accusative singular 11+)
    "day": ("يوم واحد", "يومان", "أيام", "يومًا"),
    "week": ("أسبوع واحد", "أسبوعان", "أسابيع", "أسبوعًا"),
    "month": ("شهر واحد", "شهران", "أشهر", "شهرًا"),
    "year": ("سنة واحدة", "سنتان", "سنوات", "سنة"),
    "item": ("عنصر واحد", "عنصران", "عناصر", "عنصرًا"),
    "member": ("عضو واحد", "عضوان", "أعضاء", "عضوًا"),
    "phase": ("مرحلة واحدة", "مرحلتان", "مراحل", "مرحلة"),
}


def count(n: int | float, unit: str) -> str:
    """Correct Arabic number-noun agreement: 1 شهر واحد، 2 شهران، 5 أشهر، 12 شهرًا."""
    one, two, few, many = _COUNTED[unit]
    n_int = int(round(n))
    if n_int == 1:
        return one
    if n_int == 2:
        return two
    if 3 <= n_int <= 10:
        return f"{n_int} {few}"
    return f"{n_int} {many}"


def count_gen(n: int, unit: str) -> str:
    """Genitive/accusative form used after prepositions: لمدة شهرين، خلال 3 أشهر."""
    if int(n) == 2:
        return {"day": "يومين", "week": "أسبوعين", "month": "شهرين", "year": "سنتين",
                "item": "عنصرين", "member": "عضوين", "phase": "مرحلتين"}[unit]
    return count(n, unit)


def fmt_date(d: date | None, with_day: bool = True) -> str:
    if not d:
        return ""
    if with_day:
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    return f"{MONTHS[d.month - 1]} {d.year}"


def fmt_short(d: date | None) -> str:
    if not d:
        return ""
    return f"{d.day} {MONTHS[d.month - 1]}"


def duration_phrase(days: int) -> str:
    """Human duration from a number of days, preferring months/weeks when exact enough."""
    if days <= 0:
        return ""
    if days >= 56 and abs(days / 30.4 - round(days / 30.4)) < 0.2:
        return count(round(days / 30.4), "month")
    if days >= 7 and days % 7 == 0:
        return count(days // 7, "week")
    return count(days, "day")


def duration_phrase_gen(days: int) -> str:
    if days <= 0:
        return ""
    if days >= 56 and abs(days / 30.4 - round(days / 30.4)) < 0.2:
        return count_gen(round(days / 30.4), "month")
    if days >= 7 and days % 7 == 0:
        return count_gen(days // 7, "week")
    return count_gen(days, "day")


def strip_end(text: str) -> str:
    return (text or "").strip().rstrip(".،,؛;:").strip()


def sentence(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    return t if t[-1] in ".!؟?:" else t + "."


def split_lines(text: str) -> list[str]:
    """Split user free text into items (newlines, bullets, Arabic/Latin commas when no newline)."""
    if not text:
        return []
    parts = re.split(r"[\n\r]+", text)
    if len(parts) == 1:
        parts = re.split(r"[؛;]|،\s*(?=\S)|,\s*(?=\S)", text) if len(text) < 400 else parts
    out = []
    for p in parts:
        p = re.sub(r"^\s*([-–•*·▪●]|\d+[\.\)\-]|[٠-٩]+[\.\)\-])\s*", "", p).strip()
        p = strip_end(p)
        if p:
            out.append(p)
    return out
