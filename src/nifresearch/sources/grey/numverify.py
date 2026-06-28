from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class NumVerifySource(GreySource):
    id = "grey_numverify"
    name = "NumVerify (grey-market phone validation)"
    url = "https://numverify.com/"
    env_var = "NIFRESEARCH_NUMVERIFY_KEY"
    required_inputs = {InputField.PHONE}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        if not subject.phone:
            return []
        resp = await client.get(
            "https://apilayer.net/api/validate",
            params={"number": subject.phone},
            headers={"apikey": self._api_key}, timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json() or {}
        if not data.get("valid"):
            return []
        facts: list[Fact] = []
        carrier = data.get("carrier")
        line = data.get("line_type")
        if carrier or line:
            facts.append(self._grey_fact(
                FactType.CONTACT, " / ".join(p for p in [carrier, line] if p),
                channel="phone",
            ))
        loc = data.get("location") or data.get("country_name")
        if loc:
            facts.append(self._grey_fact(FactType.ADDRESS, loc))
        return facts
