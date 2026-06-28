from __future__ import annotations

import httpx

from nifresearch.models import (
    Classification, Fact, FactType, InputField, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source
from nifresearch.sources.ckan import CkanClient

BASE_URL = "https://data.gov.il"
RESOURCE_ID = "f004176c-b85f-4542-8901-7b3176f9a054"


class CompaniesSource(Source):
    id = "datagov_companies"
    name = "data.gov.il — Companies Registrar"
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._ckan = CkanClient(BASE_URL, client=client)

    async def query(self, subject: Subject) -> SourceResult:
        name = subject.name_he or subject.name_en
        if not name:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        records = await self._ckan.datastore_search(RESOURCE_ID, q=name, limit=10)
        facts = [
            Fact(
                type=FactType.ORG_AFFILIATION,
                value=rec.get("שם חברה", "").strip(),
                source_id=self.id,
                confidence=0.3,
                url="https://data.gov.il/api/3/action/package_show?id=ica_companies",
                detail={
                    "company_number": str(rec.get("מספר חברה", "")),
                    "status": rec.get("סטטוס חברה", ""),
                    "registrar": "https://ica.justice.gov.il/",
                },
            )
            for rec in records
            if rec.get("שם חברה")
        ]
        if not facts:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)
