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
def test_research_renders_report_no_findings():
    # All data.gov.il sources return no records -> no_match for all three.
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    client = TestClient(app)
    resp = client.post("/research", data={"name_he": "דוד כהן"})
    assert resp.status_code == 200
    assert 'dir="rtl"' in resp.text
    # The three real sources appear in the status table
    assert "datagov_amutot" in resp.text or "Non-profits" in resp.text
    assert "Doctors" in resp.text or "datagov_doctors" in resp.text
