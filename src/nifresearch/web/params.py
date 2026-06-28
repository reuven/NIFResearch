from __future__ import annotations

from nifresearch.intake import build_subject
from nifresearch.models import ComplianceMode, Subject


def parse_compliance_mode(raw: str | None) -> ComplianceMode:
    if raw:
        try:
            return ComplianceMode(raw.strip().lower())
        except ValueError:
            pass
    return ComplianceMode.STRICT


def build_request_context(
    name_he: str | None,
    name_en: str | None,
    email: str | None,
    phone: str | None,
    id_number: str | None,
    compliance_mode: str | None,
) -> tuple[Subject, list[str], ComplianceMode]:
    subject, warnings = build_subject(name_he, name_en, email, phone, id_number)
    return subject, warnings, parse_compliance_mode(compliance_mode)
