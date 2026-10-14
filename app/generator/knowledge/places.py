"""Saudi cities the team may name in a brief ("نركز على الرياض")."""
from __future__ import annotations

from app.core.arabic import normalize

CITIES = ["الرياض", "جدة", "مكة", "المدينة المنورة", "الدمام", "الخبر", "الظهران", "الأحساء", "الطائف", "أبها", "خميس مشيط",
          "تبوك", "بريدة", "القصيم", "حائل", "جازان", "نجران", "الباحة", "الجوف", "ينبع", "العلا", "الجبيل", "عنيزة"]


def mentioned_cities(text: str) -> list[str]:
    n = normalize(text)
    return [c for c in CITIES if normalize(c) in n]
