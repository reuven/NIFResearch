from __future__ import annotations

import os

import httpx

from nifresearch.models import Fact, FactType, InputField, Subject
from nifresearch.sources.grey.base import GreySource


class TwilioLookupSource(GreySource):
    id = "grey_twilio"
    name = "Twilio Lookup (grey-market caller ID)"
    url = "https://www.twilio.com/lookup"
    env_var = "NIFRESEARCH_TWILIO_SID"  # informational; auth uses two vars
    required_inputs = {InputField.PHONE}

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        auth: tuple[str, str] | None = None,
    ) -> None:
        self._client = client
        if auth is not None:
            self._sid, self._token = auth
        else:
            self._sid = os.getenv("NIFRESEARCH_TWILIO_SID") or ""
            self._token = os.getenv("NIFRESEARCH_TWILIO_TOKEN") or ""

    def is_configured(self) -> bool:
        return bool(self._sid and self._token)

    async def _fetch(self, subject: Subject, client: httpx.AsyncClient) -> list[Fact]:
        if not subject.phone:
            return []
        resp = await client.get(
            f"https://lookups.twilio.com/v2/PhoneNumbers/{subject.phone}",
            params={"Fields": "caller_name"},
            auth=(self._sid, self._token), timeout=20.0,
        )
        resp.raise_for_status()
        caller = (resp.json() or {}).get("caller_name") or {}
        name = caller.get("caller_name")
        return [self._grey_fact(FactType.CONTACT, name, channel="caller_id")] if name else []
