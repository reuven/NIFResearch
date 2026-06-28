from __future__ import annotations

import httpx

from nifresearch.models import (
    Classification, Fact, FactType, InputField, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source
from nifresearch.sources.ckan import CkanClient

BASE_URL = "https://data.gov.il"
RESOURCE_ID = "be5b7935-3922-45d4-9638-08871b17ec95"


class AmutotSource(Source):
    id = "datagov_amutot"
    name = "data.gov.il — Non-profits (Amutot)"
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
        facts = [
            Fact(
                type=FactType.ORG_AFFILIATION,
                value=rec.get("שם עמותה", "").strip(),
                source_id=self.id,
                confidence=0.3,
                url="https://www.guidestar.org.il/",
                detail={
                    "amuta_number": str(rec.get("מספר עמותה", "")),
                    "status": rec.get("סטטוס עמותה", ""),
                },
            )
            for rec in records
            if rec.get("שם עמותה")
        ]
        if not facts:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)
