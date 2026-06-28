from __future__ import annotations

from nifresearch.models import Subject
from nifresearch.validation import looks_like_email, normalize_id, normalize_phone


def build_subject(
    name_he: str | None,
    name_en: str | None,
    email: str | None,
    phone: str | None,
    id_number: str | None,
) -> tuple[Subject, list[str]]:
    warnings: list[str] = []

    clean_email = (email or "").strip() or None
    if clean_email and not looks_like_email(clean_email):
        warnings.append(f"Ignored invalid email: {clean_email}")
        clean_email = None

    clean_phone = None
    if phone and phone.strip():
        clean_phone = normalize_phone(phone)
        if clean_phone is None:
            warnings.append(f"Ignored unparseable phone: {phone.strip()}")

    clean_id = None
    if id_number and id_number.strip():
        clean_id = normalize_id(id_number)
        if clean_id is None:
            warnings.append(f'Ignored invalid Israeli ID (ת"ז): {id_number.strip()}')

    subject = Subject(
        name_he=(name_he or "").strip() or None,
        name_en=(name_en or "").strip() or None,
        email=clean_email,
        phone=clean_phone,
        id_number=clean_id,
    )
    return subject, warnings
