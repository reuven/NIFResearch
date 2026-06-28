from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class ApolloSource(GreySource):
    id = "grey_apollo"
    name = "Apollo.io (grey-market enrichment)"
    url = "https://www.apollo.io/"
    env_var = "NIFRESEARCH_APOLLO_API_KEY"
    required_inputs = {InputField.NAME, InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        payload: dict[str, str] = {}
        if subject.email:
            payload["email"] = subject.email
        name = subject.name_he or subject.name_en
        if name:
            payload["name"] = name
        resp = await client.post(
            "https://api.apollo.io/v1/people/match",
            json=payload, headers={"X-Api-Key": self._api_key}, timeout=20.0,
        )
        resp.raise_for_status()
        person = (resp.json() or {}).get("person") or {}
        facts: list[Fact] = []
        if person.get("title"):
            facts.append(self._grey_fact(FactType.ROLE, person["title"]))
        org = person.get("organization") or {}
        if org.get("name"):
            facts.append(self._grey_fact(FactType.EMPLOYER, org["name"]))
        if person.get("email"):
            facts.append(self._grey_fact(FactType.CONTACT, person["email"], channel="email"))
        for ph in person.get("phone_numbers", []):
            if ph.get("raw_number"):
                facts.append(self._grey_fact(FactType.CONTACT, ph["raw_number"], channel="phone"))
        return facts
