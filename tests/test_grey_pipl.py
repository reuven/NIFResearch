import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.grey.pipl import PiplSource


def test_metadata():
    s = PiplSource(api_key="k")
    assert s.id == "grey_pipl"
    assert s.classification == Classification.GREY_MARKET
    assert InputField.EMAIL in s.required_inputs


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await PiplSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://api.pipl.com/search/").mock(return_value=httpx.Response(200, json={
        "person": {
            "addresses": [{"display": "Tel Aviv, Israel"}],
            "jobs": [{"display": "CEO at Acme"}],
            "emails": [{"address": "a@b.co"}],
        }
    }))
    async with httpx.AsyncClient() as client:
        r = await PiplSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.ADDRESS, FactType.EMPLOYER, FactType.CONTACT} <= types
    assert all(f.confidence == 0.25 for f in r.facts)
    assert all(f.detail["caveat"] for f in r.facts)
    sent = respx.calls.last.request
    assert sent.headers.get("X-Access-Key") == "k"
    assert "key=" not in str(sent.url)
