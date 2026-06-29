import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.lusha import LushaSource


def test_metadata():
    assert LushaSource(api_key="k").id == "grey_lusha"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await LushaSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://api.lusha.com/v2/person").mock(return_value=httpx.Response(200, json={
        "data": {
            "jobTitle": "CFO", "companyName": "Acme",
            "emailAddresses": [{"email": "a@b.co"}],
            "phoneNumbers": [{"number": "+972500000000"}],
        }
    }))
    async with httpx.AsyncClient() as client:
        r = await LushaSource(client=client, api_key="SEKRET").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.ROLE, FactType.EMPLOYER, FactType.CONTACT} <= types
    req = respx.calls.last.request
    assert req.headers.get("api_key") == "SEKRET"
    assert "SEKRET" not in str(req.url)
