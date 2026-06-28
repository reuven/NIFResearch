import httpx
import pytest
import respx

from nifresearch.sources.ckan import CkanClient


@pytest.mark.asyncio
@respx.mock
async def test_datastore_search_returns_records():
    route = respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "result": {"records": [{"x": 1}, {"x": 2}]}},
        )
    )
    async with httpx.AsyncClient() as client:
        ckan = CkanClient("https://data.gov.il", client=client)
        records = await ckan.datastore_search("res-id", q="דוד", limit=10)
    assert records == [{"x": 1}, {"x": 2}]
    assert route.calls.last.request.url.params["resource_id"] == "res-id"
    assert route.calls.last.request.url.params["q"] == "דוד"


@pytest.mark.asyncio
@respx.mock
async def test_datastore_search_handles_failure():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": False})
    )
    async with httpx.AsyncClient() as client:
        records = await CkanClient("https://data.gov.il", client=client).datastore_search("r")
    assert records == []
