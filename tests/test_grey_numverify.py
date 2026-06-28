import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.numverify import NumVerifySource


def test_metadata():
    assert NumVerifySource(api_key="k").id == "grey_numverify"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await NumVerifySource(api_key=None).query(Subject(phone="+972500000000"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://apilayer.net/api/validate").mock(return_value=httpx.Response(200, json={
        "valid": True, "carrier": "Pelephone", "line_type": "mobile",
        "location": "Israel", "country_name": "Israel",
    }))
    async with httpx.AsyncClient() as client:
        r = await NumVerifySource(client=client, api_key="k").query(Subject(phone="+972500000000"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert FactType.CONTACT in types
