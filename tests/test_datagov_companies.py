import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.datagov_companies import CompaniesSource


def test_metadata():
    src = CompaniesSource()
    assert src.id == "datagov_companies"
    assert src.classification == Classification.OFFICIAL_PUBLIC
    assert src.required_inputs == {InputField.NAME}


@pytest.mark.asyncio
@respx.mock
async def test_query_maps_records_to_facts():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": [
            {"שם חברה": 'אור בע"מ', "מספר חברה": "510001", "סטטוס חברה": "פעילה"},
        ]}})
    )
    async with httpx.AsyncClient() as client:
        result = await CompaniesSource(client=client).query(Subject(name_he="אור"))
    assert result.status == SourceStatus.OK
    assert result.facts[0].type == FactType.ORG_AFFILIATION
    assert result.facts[0].value == 'אור בע"מ'
    assert result.facts[0].detail["company_number"] == "510001"
    assert result.facts[0].source_id == "datagov_companies"
    assert result.facts[0].confidence == 0.3
    assert result.facts[0].detail["status"] == "פעילה"
    assert result.facts[0].url == "https://data.gov.il/dataset/ica_companies"
    assert result.facts[0].detail["registrar"] == "https://ica.justice.gov.il/"


@pytest.mark.asyncio
@respx.mock
async def test_query_no_records_is_no_match():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    async with httpx.AsyncClient() as client:
        result = await CompaniesSource(client=client).query(Subject(name_he="איןכזה"))
    assert result.status == SourceStatus.NO_MATCH


@pytest.mark.asyncio
@respx.mock
async def test_records_missing_company_name_is_no_match():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": [
            {"מספר חברה": "510001", "סטטוס חברה": "פעילה"},
        ]}})
    )
    async with httpx.AsyncClient() as client:
        result = await CompaniesSource(client=client).query(Subject(name_he="אור"))
    assert result.status == SourceStatus.NO_MATCH
