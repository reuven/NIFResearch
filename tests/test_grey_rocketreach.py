import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.rocketreach import RocketReachSource


def test_metadata():
    assert RocketReachSource(api_key="k").id == "grey_rocketreach"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await RocketReachSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://api.rocketreach.co/v2/api/lookupProfile").mock(
        return_value=httpx.Response(200, json={
            "emails": [{"email": "a@b.co"}], "phones": [{"number": "+972500000000"}],
            "current_employer": "Acme", "current_title": "Partner",
        })
    )
    async with httpx.AsyncClient() as client:
        r = await RocketReachSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.CONTACT, FactType.EMPLOYER, FactType.ROLE} <= types
