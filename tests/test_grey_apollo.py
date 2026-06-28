import httpx
import pytest
import respx

from nifresearch.models import FactType, Subject, SourceStatus
from nifresearch.sources.grey.apollo import ApolloSource


def test_metadata():
    assert ApolloSource(api_key="k").id == "grey_apollo"


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await ApolloSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_facts():
    respx.post("https://api.apollo.io/v1/people/match").mock(return_value=httpx.Response(200, json={
        "person": {
            "title": "Director", "organization": {"name": "Acme"},
            "email": "a@b.co", "phone_numbers": [{"raw_number": "+972500000000"}],
        }
    }))
    async with httpx.AsyncClient() as client:
        r = await ApolloSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    types = {f.type for f in r.facts}
    assert {FactType.ROLE, FactType.EMPLOYER, FactType.CONTACT} <= types
