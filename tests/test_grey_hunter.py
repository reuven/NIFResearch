import httpx
import pytest
import respx

from nifresearch.models import FactType, InputField, Subject, SourceStatus
from nifresearch.sources.grey.hunter import HunterSource


def test_metadata():
    s = HunterSource(api_key="k")
    assert s.id == "grey_hunter"
    assert s.required_inputs == {InputField.EMAIL}


@pytest.mark.asyncio
async def test_not_configured_skips():
    r = await HunterSource(api_key=None).query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.SKIPPED


@pytest.mark.asyncio
@respx.mock
async def test_match_maps_contact():
    respx.get("https://api.hunter.io/v2/email-verifier").mock(return_value=httpx.Response(200, json={
        "data": {"status": "valid", "score": 96, "email": "a@b.co"}
    }))
    async with httpx.AsyncClient() as client:
        r = await HunterSource(client=client, api_key="k").query(Subject(email="a@b.co"))
    assert r.status == SourceStatus.OK
    f = r.facts[0]
    assert f.type == FactType.CONTACT
    assert f.detail["status"] == "valid"
