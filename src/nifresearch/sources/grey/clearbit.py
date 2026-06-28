from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class ClearbitSource(GreySource):
    id = "grey_clearbit"
    name = "Clearbit/Breeze (grey-market enrichment)"
    url = "https://clearbit.com/"
    env_var = "NIFRESEARCH_CLEARBIT_API_KEY"
    required_inputs = {InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        if not subject.email:
            return []
        resp = await client.get(
            "https://person.clearbit.com/v2/people/find",
            params={"email": subject.email},
            headers={"Authorization": f"Bearer {self._api_key}"}, timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        facts: list[Fact] = []
        employment = data.get("employment") or {}
        if employment.get("name"):
            facts.append(self._grey_fact(FactType.EMPLOYER, employment["name"]))
        if employment.get("title"):
            facts.append(self._grey_fact(FactType.ROLE, employment["title"]))
        if data.get("email"):
            facts.append(self._grey_fact(FactType.CONTACT, data["email"], channel="email"))
        return facts
