from __future__ import annotations

import re


def is_valid_israeli_id(raw: str) -> bool:
    digits = (raw or "").strip()
    if not digits.isdigit() or len(digits) > 9:
        return False
    digits = digits.zfill(9)
    total = 0
    for i, ch in enumerate(digits):
        n = int(ch) * (1 if i % 2 == 0 else 2)
        total += n if n < 10 else n - 9
    return total % 10 == 0


def normalize_id(raw: str) -> str | None:
    digits = (raw or "").strip()
    if not is_valid_israeli_id(digits):
        return None
    return digits.zfill(9)


def normalize_phone(raw: str) -> str | None:
    raw = (raw or "").strip()
    plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 9:
        return None
    return ("+" + digits) if plus else digits


def looks_like_email(raw: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (raw or "").strip()))
