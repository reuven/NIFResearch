import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.peopledatalabs import PeopleDataLabsSource


def test_metadata():
    assert PeopleDataLabsSource(api_key="k").id == "grey_pdl"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await PeopleDataLabsSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.get("https://api.peopledatalabs.com/v5/person/enrich").mock(
        return_value=httpx.Response(200, json={"data": {
            "job_title": "VP Eng", "job_company_name": "Acme",
            "location_name": "Haifa, Israel", "work_email": "a@b.co",
        }})
    )
    async with httpx.AsyncClient() as client:
        r = await PeopleDataLabsSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.EMPLOYER, FactType.ADDRESS, FactType.CONTACT} <= types
    assert all(f.confidence == 0.25 for f in r.facts)
    assert all(f.detail["caveat"] for f in r.facts)
    sent = respx.calls.last.request
    assert sent.headers.get("X-Api-Key") == "k"
    assert "key=" not in str(sent.url)
