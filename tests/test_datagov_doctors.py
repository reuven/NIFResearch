import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.datagov_doctors import DoctorsSource


def test_metadata():
    src = DoctorsSource()
    assert src.id == "datagov_doctors"
    assert src.classification == Classification.OFFICIAL_PUBLIC
    assert src.required_inputs == {InputField.NAME}


@pytest.mark.asyncio
@respx.mock
async def test_query_maps_record_to_profession_and_license():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": [
            {"שם פרטי": "דוד", "שם משפחה": "כהן",
             "מספר רישיון רופא": 12345, "שם התמחות": "קרדיולוגיה"},
        ]}})
    )
    async with httpx.AsyncClient() as client:
        result = await DoctorsSource(client=client).query(Subject(name_he="דוד כהן"))
    assert result.status == SourceStatus.OK
    types = {f.type for f in result.facts}
    assert FactType.PROFESSION in types
    assert FactType.LICENSE in types
    prof = next(f for f in result.facts if f.type == FactType.PROFESSION)
    assert prof.value == "רופא/ה"
    assert prof.confidence == 0.4
    assert prof.url == "https://data.gov.il/dataset/database-of-doctors-licenses-moh"
    assert prof.detail["specialty"] == "קרדיולוגיה"
    assert prof.detail["license_number"] == "12345"
    assert prof.detail["full_name"] == "דוד כהן"


@pytest.mark.asyncio
@respx.mock
async def test_query_no_records_is_no_match():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    async with httpx.AsyncClient() as client:
        result = await DoctorsSource(client=client).query(Subject(name_he="איןכזה"))
    assert result.status == SourceStatus.NO_MATCH
