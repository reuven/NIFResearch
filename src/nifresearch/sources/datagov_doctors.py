from __future__ import annotations

import httpx

from nifresearch.models import (
    Classification, Fact, FactType, InputField, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source
from nifresearch.sources.ckan import CkanClient

BASE_URL = "https://data.gov.il"
RESOURCE_ID = "9c64c522-bbc2-48fe-96fb-3b2a8626f59e"
DATASET_URL = "https://data.gov.il/api/3/action/package_show?id=database-of-doctors-licenses-moh"


class DoctorsSource(Source):
    id = "datagov_doctors"
    name = "data.gov.il — Doctors registry (MoH)"
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._ckan = CkanClient(BASE_URL, client=client)

    async def query(self, subject: Subject) -> SourceResult:
        name = subject.name_he or subject.name_en
        if not name:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        records = await self._ckan.datastore_search(RESOURCE_ID, q=name, limit=10)
        if not records:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        facts: list[Fact] = []
        for rec in records:
            full_name = f"{rec.get('שם פרטי', '')} {rec.get('שם משפחה', '')}".strip()
            detail = {
                "license_number": str(rec.get("מספר רישיון רופא", "")),
                "specialty": rec.get("שם התמחות", ""),
                "full_name": full_name,
            }
            facts.append(Fact(
                type=FactType.PROFESSION, value="רופא/ה",
                source_id=self.id, confidence=0.4, url=DATASET_URL, detail=dict(detail),
            ))
            facts.append(Fact(
                type=FactType.LICENSE,
                value=f"רישיון רופא {detail['license_number']}".strip(),
                source_id=self.id, confidence=0.4, url=DATASET_URL, detail=dict(detail),
            ))
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)
