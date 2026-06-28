from __future__ import annotations

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class HunterSource(GreySource):
    id = "grey_hunter"
    name = "Hunter.io (grey-market email verification)"
    url = "https://hunter.io/"
    env_var = "NIFRESEARCH_HUNTER_API_KEY"
    required_inputs = {InputField.EMAIL}

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        if not subject.email:
            return []
        resp = await client.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": subject.email},
            headers={"Authorization": f"Bearer {self._api_key}"}, timeout=20.0,
        )
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or {}
        if not data.get("email"):
            return []
        return [self._grey_fact(
            FactType.CONTACT, data["email"],
            channel="email", status=data.get("status", ""), score=data.get("score"),
        )]
