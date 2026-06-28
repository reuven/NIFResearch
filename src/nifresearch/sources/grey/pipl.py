from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class PiplSource(GreySource):
    id = "grey_pipl"
    name = "Pipl (grey-market people search)"
    url = "https://pipl.com/"
    env_var = "NIFRESEARCH_PIPL_API_KEY"
    required_inputs = {InputField.NAME, InputField.EMAIL, InputField.PHONE}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        params: dict[str, str] = {}
        if subject.email:
            params["email"] = subject.email
        if subject.phone:
            params["phone"] = subject.phone
        name = subject.name_he or subject.name_en
        if name:
            params["raw_name"] = name
        resp = await client.get(
            "https://api.pipl.com/search/",
            params=params,
            headers={"X-Access-Key": self._api_key},
            timeout=20.0,
        )
        resp.raise_for_status()
        person = (resp.json() or {}).get("person") or {}
        facts: list[Fact] = []
        for addr in person.get("addresses", []):
            if addr.get("display"):
                facts.append(self._grey_fact(FactType.ADDRESS, addr["display"]))
        for job in person.get("jobs", []):
            if job.get("display"):
                facts.append(self._grey_fact(FactType.EMPLOYER, job["display"]))
        for em in person.get("emails", []):
            if em.get("address"):
                facts.append(self._grey_fact(FactType.CONTACT, em["address"], channel="email"))
        return facts
