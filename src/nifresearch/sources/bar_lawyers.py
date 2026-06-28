from __future__ import annotations

import httpx

from nifresearch.models import (
    Classification, Fact, FactType, InputField, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source
from nifresearch.sources.ckan import CkanClient

BASE_URL = "https://www.odata.org.il"
# TODO(build-time): confirm the live resource id from
# https://www.odata.org.il/dataset/israelbarmembers
RESOURCE_ID = "320c0980-3b41-4d3a-aa25-5f3f0a4a9b50"

_DATASET_URL = "https://www.odata.org.il/dataset/israelbarmembers"
_BAR_URL = "https://www.israelbar.org.il/"


class BarLawyersSource(Source):
    id = "bar_lawyers"
    name = "Israel Bar — Lawyers register"
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
            member = str(rec.get("מספר חבר", ""))
            city = rec.get("עיר", "")
            shared_detail = {"member_number": member, "city": city, "bar": _BAR_URL}
            facts.append(Fact(
                type=FactType.PROFESSION,
                value="עורך/ת דין",
                source_id=self.id,
                confidence=0.4,
                url=_DATASET_URL,
                detail=dict(shared_detail),
            ))
            facts.append(Fact(
                type=FactType.LICENSE,
                value=f"חבר/ת לשכה {member}".strip(),
                source_id=self.id,
                confidence=0.4,
                url=_DATASET_URL,
                detail=dict(shared_detail),
            ))
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)
