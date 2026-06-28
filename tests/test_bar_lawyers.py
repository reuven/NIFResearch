import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.bar_lawyers import BarLawyersSource


def test_metadata():
    src = BarLawyersSource()
    assert src.id == "bar_lawyers"
    assert src.classification == Classification.OFFICIAL_PUBLIC
    assert src.required_inputs == {InputField.NAME}


@pytest.mark.asyncio
@respx.mock
async def test_query_maps_records_to_profession_and_license():
    respx.get("https://www.odata.org.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": [
            {"שם מלא": "דוד כהן", "מספר חבר": "12345", "עיר": "תל אביב"},
        ]}})
    )
    async with httpx.AsyncClient() as client:
        result = await BarLawyersSource(client=client).query(Subject(name_he="דוד כהן"))
    assert result.status == SourceStatus.OK
    types = {f.type for f in result.facts}
    assert FactType.PROFESSION in types
    assert FactType.LICENSE in types
    license_fact = next(f for f in result.facts if f.type == FactType.LICENSE)
    assert license_fact.detail["member_number"] == "12345"
    assert license_fact.detail["city"] == "תל אביב"
    # Provenance must point to the actual retrieval source (odata.org.il)
    assert license_fact.url == "https://www.odata.org.il/dataset/israelbarmembers"
    # Bar's human-facing site in detail, not as url
    assert license_fact.detail.get("bar") == "https://www.israelbar.org.il/"
    # Confidence check
    assert any(f.confidence == 0.4 for f in result.facts)


@pytest.mark.asyncio
@respx.mock
async def test_query_no_records_is_no_match():
    respx.get("https://www.odata.org.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    async with httpx.AsyncClient() as client:
        result = await BarLawyersSource(client=client).query(Subject(name_he="איןכזה"))
    assert result.status == SourceStatus.NO_MATCH
