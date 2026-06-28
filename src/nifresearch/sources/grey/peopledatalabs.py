from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class PeopleDataLabsSource(GreySource):
    id = "grey_pdl"
    name = "People Data Labs (grey-market enrichment)"
    url = "https://www.peopledatalabs.com/"
    env_var = "NIFRESEARCH_PDL_API_KEY"
    required_inputs = {InputField.NAME, InputField.EMAIL, InputField.PHONE}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        params: dict[str, str] = {}
        if subject.email:
            params["email"] = subject.email
        if subject.phone:
            params["phone"] = subject.phone
        name = subject.name_he or subject.name_en
        if name:
            params["name"] = name
        resp = await client.get(
            "https://api.peopledatalabs.com/v5/person/enrich",
            params=params, headers={"X-Api-Key": self._api_key}, timeout=20.0,
        )
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or {}
        facts: list[Fact] = []
        title, company = data.get("job_title"), data.get("job_company_name")
        if title or company:
            facts.append(self._grey_fact(FactType.EMPLOYER, " @ ".join(p for p in [title, company] if p)))
        if data.get("location_name"):
            facts.append(self._grey_fact(FactType.ADDRESS, data["location_name"]))
        if data.get("work_email"):
            facts.append(self._grey_fact(FactType.CONTACT, data["work_email"], channel="email"))
        return facts
