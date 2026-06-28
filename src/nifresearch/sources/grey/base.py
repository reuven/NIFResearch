from __future__ import annotations

import os

import httpx

from nifresearch.models import (
    Classification, Fact, FactType, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source

GREY_CAVEAT = "grey-market source — verify legal basis before use"


class GreySource(Source):
    classification = Classification.GREY_MARKET
    confidence: float = 0.25
    env_var: str = ""
    url: str = ""

    def __init__(
        self, client: httpx.AsyncClient | None = None, api_key: str | None = None
    ) -> None:
        self._client = client
        self._api_key = api_key if api_key is not None else os.getenv(self.env_var)

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _grey_fact(self, type: FactType, value: str, **detail) -> Fact:
        return Fact(
            type=type,
            value=value,
            source_id=self.id,
            confidence=self.confidence,
            url=self.url,
            detail={**detail, "caveat": GREY_CAVEAT},
        )

    async def query(self, subject: Subject) -> SourceResult:
        if not self.is_configured():
            return SourceResult(
                source_id=self.id, status=SourceStatus.SKIPPED,
                error=f"not configured: set {self.env_var}",
            )
        try:
            if self._client is not None:
                facts = await self._fetch(subject, self._client)
            else:
                async with httpx.AsyncClient() as client:
                    facts = await self._fetch(subject, client)
        except Exception as exc:  # noqa: BLE001 — record any source failure
            return SourceResult(source_id=self.id, status=SourceStatus.ERROR, error=str(exc))
        if not facts:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        raise NotImplementedError
