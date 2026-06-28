import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.datagov_amutot import AmutotSource


def test_metadata():
    src = AmutotSource()
    assert src.id == "datagov_amutot"
    assert src.classification == Classification.OFFICIAL_PUBLIC
    assert src.required_inputs == {InputField.NAME}


@pytest.mark.asyncio
@respx.mock
async def test_query_maps_records_to_facts():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": [
            {"שם עמותה": "עמותת אור", "מספר עמותה": "580001", "סטטוס עמותה": "רשומה"},
        ]}})
    )
    async with httpx.AsyncClient() as client:
        result = await AmutotSource(client=client).query(Subject(name_he="אור"))
    assert result.status == SourceStatus.OK
    assert result.facts[0].type == FactType.ORG_AFFILIATION
    assert result.facts[0].value == "עמותת אור"
    assert result.facts[0].detail["amuta_number"] == "580001"
    assert result.facts[0].source_id == "datagov_amutot"


@pytest.mark.asyncio
@respx.mock
async def test_query_no_records_is_no_match():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    async with httpx.AsyncClient() as client:
        result = await AmutotSource(client=client).query(Subject(name_he="איןכזה"))
    assert result.status == SourceStatus.NO_MATCH
