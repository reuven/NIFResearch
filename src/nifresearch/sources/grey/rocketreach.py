from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class RocketReachSource(GreySource):
    id = "grey_rocketreach"
    name = "RocketReach (grey-market enrichment)"
    url = "https://rocketreach.co/"
    env_var = "NIFRESEARCH_ROCKETREACH_API_KEY"
    required_inputs = {InputField.NAME, InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        params: dict[str, str] = {}
        if subject.email:
            params["email"] = subject.email
        name = subject.name_he or subject.name_en
        if name:
            params["name"] = name
        resp = await client.get(
            "https://api.rocketreach.co/v2/api/lookupProfile",
            params=params, headers={"Api-Key": self._api_key}, timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        facts: list[Fact] = []
        for em in data.get("emails", []):
            if em.get("email"):
                facts.append(self._grey_fact(FactType.CONTACT, em["email"], channel="email"))
        for ph in data.get("phones", []):
            if ph.get("number"):
                facts.append(self._grey_fact(FactType.CONTACT, ph["number"], channel="phone"))
        if data.get("current_employer"):
            facts.append(self._grey_fact(FactType.EMPLOYER, data["current_employer"]))
        if data.get("current_title"):
            facts.append(self._grey_fact(FactType.ROLE, data["current_title"]))
        return facts
