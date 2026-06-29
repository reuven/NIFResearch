import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.contactout import ContactOutSource


def test_metadata():
    assert ContactOutSource(api_key="k").id == "grey_contactout"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await ContactOutSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://api.contactout.com/v1/people/enrich").mock(return_value=httpx.Response(200, json={
        "profile": {
            "full_name": "David Cohen",
            "emails": ["a@b.co"], "phones": ["+972500000000"],
            "company": {"name": "Acme"},
        }
    }))
    async with httpx.AsyncClient() as client:
        r = await ContactOutSource(client=client, api_key="SEKRET").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.CONTACT, FactType.EMPLOYER} <= types
    req = respx.calls.last.request
    assert "SEKRET" in req.headers.get("authorization", "")
    assert "SEKRET" not in str(req.url)
