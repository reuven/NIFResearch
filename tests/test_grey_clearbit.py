import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.clearbit import ClearbitSource


def test_metadata():
    assert ClearbitSource(api_key="k").id == "grey_clearbit"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await ClearbitSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://person.clearbit.com/v2/people/find").mock(
        return_value=httpx.Response(200, json={
            "email": "a@b.co",
            "employment": {"name": "Acme", "title": "Chair"},
        })
    )
    async with httpx.AsyncClient() as client:
        r = await ClearbitSource(client=client, api_key="SEKRET").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.CONTACT, FactType.EMPLOYER, FactType.ROLE} <= types
    req = respx.calls.last.request
    assert "SEKRET" in req.headers.get("Authorization", "")
    assert "SEKRET" not in str(req.url)
