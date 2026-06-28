from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class LushaSource(GreySource):
    id = "grey_lusha"
    name = "Lusha (grey-market B2B enrichment)"
    url = "https://www.lusha.com/"
    env_var = "NIFRESEARCH_LUSHA_API_KEY"
    required_inputs = {InputField.NAME, InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        params: dict[str, str] = {}
        if subject.email:
            params["email"] = subject.email
        name = subject.name_he or subject.name_en
        if name:
            params["name"] = name
        resp = await client.get(
            "https://api.lusha.com/v2/person",
            params=params, headers={"api_key": self._api_key}, timeout=20.0,
        )
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or {}
        facts: list[Fact] = []
        if data.get("jobTitle"):
            facts.append(self._grey_fact(FactType.ROLE, data["jobTitle"]))
        if data.get("companyName"):
            facts.append(self._grey_fact(FactType.EMPLOYER, data["companyName"]))
        for em in data.get("emailAddresses", []):
            if em.get("email"):
                facts.append(self._grey_fact(FactType.CONTACT, em["email"], channel="email"))
        for ph in data.get("phoneNumbers", []):
            if ph.get("number"):
                facts.append(self._grey_fact(FactType.CONTACT, ph["number"], channel="phone"))
        return facts
