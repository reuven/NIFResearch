from __future__ import annotations

from nifresearch.models import Classification, ComplianceMode

_ALLOWED: dict[ComplianceMode, set[Classification]] = {
    ComplianceMode.STRICT: {Classification.OFFICIAL_PUBLIC},
    ComplianceMode.STANDARD: {Classification.OFFICIAL_PUBLIC, Classification.LICENSED},
    ComplianceMode.PERMISSIVE: {
        Classification.OFFICIAL_PUBLIC,
        Classification.LICENSED,
        Classification.GREY_MARKET,
    },
}


def allowed_classifications(mode: ComplianceMode) -> set[Classification]:
    return set(_ALLOWED[mode])


def is_allowed(classification: Classification, mode: ComplianceMode) -> bool:
    return classification in _ALLOWED[mode]
