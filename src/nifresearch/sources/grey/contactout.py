from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class ContactOutSource(GreySource):
    id = "grey_contactout"
    name = "ContactOut (grey-market enrichment)"
    url = "https://contactout.com/"
    env_var = "NIFRESEARCH_CONTACTOUT_API_KEY"
    required_inputs = {InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        if not subject.email:
            return []
        resp = await client.get(
            "https://api.contactout.com/v1/people/enrich",
            params={"email": subject.email},
            headers={"authorization": f"Basic {self._api_key}"}, timeout=20.0,
        )
        resp.raise_for_status()
        profile = (resp.json() or {}).get("profile") or {}
        facts: list[Fact] = []
        for em in profile.get("emails", []):
            facts.append(self._grey_fact(FactType.CONTACT, em, channel="email"))
        for ph in profile.get("phones", []):
            facts.append(self._grey_fact(FactType.CONTACT, ph, channel="phone"))
        company = profile.get("company") or {}
        if company.get("name"):
            facts.append(self._grey_fact(FactType.EMPLOYER, company["name"]))
        return facts
