from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Classification(str, Enum):
    OFFICIAL_PUBLIC = "official_public"
    LICENSED = "licensed"
    GREY_MARKET = "grey_market"


class ComplianceMode(str, Enum):
    STRICT = "strict"
    STANDARD = "standard"
    PERMISSIVE = "permissive"


class InputField(str, Enum):
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    ID_NUMBER = "id_number"


class FactType(str, Enum):
    ADDRESS = "address"
    EMPLOYER = "employer"
    ROLE = "role"
    BOARD_MEMBERSHIP = "board_membership"
    PROFESSION = "profession"
    LICENSE = "license"
    CONTACT = "contact"
    ORG_AFFILIATION = "org_affiliation"
    DONATION = "donation"
    INCOME_ESTIMATE = "income_estimate"
    OTHER = "other"


class SourceStatus(str, Enum):
    OK = "ok"
    NO_MATCH = "no_match"
    ERROR = "error"
    SKIPPED = "skipped"


class Subject(BaseModel):
    name_he: str | None = None
    name_en: str | None = None
    email: str | None = None
    phone: str | None = None
    id_number: str | None = None

    def available_inputs(self) -> set[InputField]:
        present: set[InputField] = set()
        if self.name_he or self.name_en:
            present.add(InputField.NAME)
        if self.email:
            present.add(InputField.EMAIL)
        if self.phone:
            present.add(InputField.PHONE)
        if self.id_number:
            present.add(InputField.ID_NUMBER)
        return present


class Fact(BaseModel):
    type: FactType
    value: str
    source_id: str
    confidence: float = 0.5
    url: str | None = None
    retrieved_at: str | None = None
    detail: dict = Field(default_factory=dict)


class SourceResult(BaseModel):
    source_id: str
    status: SourceStatus
    facts: list[Fact] = Field(default_factory=list)
    latency_ms: float | None = None
    error: str | None = None


class Profile(BaseModel):
    subject: Subject
    facts: list[Fact] = Field(default_factory=list)
    results: list[SourceResult] = Field(default_factory=list)

    def by_type(self) -> dict[FactType, list[Fact]]:
        grouped: dict[FactType, list[Fact]] = {}
        for fact in self.facts:
            grouped.setdefault(fact.type, []).append(fact)
        return grouped
