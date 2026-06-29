import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus, Classification
from nifresearch.sources.grey.twilio_lookup import TwilioLookupSource


def test_metadata_and_classification():
    s = TwilioLookupSource(auth=("sid", "tok"))
    assert s.id == "grey_twilio"
    assert s.classification == Classification.GREY_MARKET


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await TwilioLookupSource(auth=("", "")).query(Subject(phone="+972500000000"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_caller_name():
    respx.get("https://lookups.twilio.com/v2/PhoneNumbers/+972500000000").mock(
        return_value=httpx.Response(200, json={"caller_name": {"caller_name": "David Cohen"}})
    )
    async with httpx.AsyncClient() as client:
        r = await TwilioLookupSource(client=client, auth=("SID", "SEKRET")).query(
            Subject(phone="+972500000000")
        )
    assert r.status == SourceStatus.OK
    assert r.facts[0].type == FactType.CONTACT
    assert r.facts[0].value == "David Cohen"
    req = respx.calls.last.request
    assert req.headers.get("Authorization", "").startswith("Basic ")
    assert "SEKRET" not in str(req.url)
