from urllib.parse import quote, quote as _quote

import httpx
import respx
from fastapi.testclient import TestClient

from nifresearch.web.app import app


def test_form_renders_with_dropdown():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'name="name_he"' in resp.text
    assert 'name="compliance_mode"' in resp.text
    assert "strict" in resp.text and "standard" in resp.text and "permissive" in resp.text


def test_research_returns_progress_page():
    client = TestClient(app)
    resp = client.post("/research", data={"name_he": "דוד כהן"})
    assert resp.status_code == 200
    # progress page lists the real sources and wires up the SSE stream
    assert "/research/stream" in resp.text
    assert "Doctors" in resp.text or "datagov_doctors" in resp.text
    assert 'dir="rtl"' in resp.text


@respx.mock
def test_stream_emits_progress_and_done_with_fact():
    def responder(request):
        rid = request.url.params.get("resource_id")
        if rid == "9c64c522-bbc2-48fe-96fb-3b2a8626f59e":  # doctors
            return httpx.Response(200, json={"success": True, "result": {"records": [
                {"שם פרטי": "דוד", "שם משפחה": "כהן",
                 "מספר רישיון רופא": 123, "שם התמחות": "קרדיולוגיה"},
            ]}})
        return httpx.Response(200, json={"success": True, "result": {"records": []}})

    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(side_effect=responder)
    client = TestClient(app)
    resp = client.get("/research/stream?name_he=" + quote("דוד כהן"))
    assert resp.status_code == 200
    body = resp.text
    assert "event: progress" in body
    assert "event: done" in body
    assert "datagov_doctors" in body
    assert "רופא/ה" in body  # the doctor profession fact is in the done fragment


def test_progress_page_warns_on_invalid_id():
    client = TestClient(app)
    resp = client.post("/research", data={"name_he": "דוד", "id_number": "123456789"})
    assert resp.status_code == 200
    assert "123456789" in resp.text   # invalid ID surfaced as a warning


@respx.mock
def test_grey_banner_absent_under_strict():
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    client = TestClient(app)
    resp = client.get("/research/stream?name_he=" + _quote("דוד"))
    assert 'grey-banner' not in resp.text


@respx.mock
def test_grey_banner_present_when_grey_ran(monkeypatch):
    monkeypatch.setenv("NIFRESEARCH_PIPL_API_KEY", "k")
    respx.get("https://data.gov.il/api/3/action/datastore_search").mock(
        return_value=httpx.Response(200, json={"success": True, "result": {"records": []}})
    )
    respx.get("https://api.pipl.com/search/").mock(return_value=httpx.Response(200, json={
        "person": {"emails": [{"address": "a@b.co"}]}
    }))
    client = TestClient(app)
    resp = client.get(
        "/research/stream?compliance_mode=permissive&email=" + _quote("a@b.co")
    )
    assert 'grey-banner' in resp.text
