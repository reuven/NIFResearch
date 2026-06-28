import httpx
import respx
from fastapi.testclient import TestClient

from nifresearch.web.app import app


def test_form_renders():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'name="name_he"' in resp.text


@respx.mock
def test_research_renders_report_with_facts_and_provenance():
    # All live CKAN calls return empty; the mock source still produces facts.
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    respx.get("https://www.odata.org.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    client = TestClient(app)
    resp = client.post("/research", data={"name_he": "דוד כהן"})
    assert resp.status_code == 200
    # mock_board fact appears, tagged with its source
    assert "חבר ועד" in resp.text
    assert "mock_board" in resp.text
    # report is RTL
    assert 'dir="rtl"' in resp.text


@respx.mock
def test_research_warns_on_invalid_id():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    respx.get("https://www.odata.org.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    client = TestClient(app)
    resp = client.post("/research", data={"name_he": "דוד", "id_number": "123456789"})
    assert resp.status_code == 200
    assert "123456789" in resp.text  # surfaced as a warning
