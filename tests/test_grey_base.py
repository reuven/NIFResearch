import pytest

from nifresearch.models import (
    Classification, FactType, InputField, Subject, SourceStatus,
)
from nifresearch.sources.grey.base import GreySource, GREY_CAVEAT


class FakeGrey(GreySource):
    id = "grey_fake"
    name = "Fake grey"
    url = "https://example.com/"
    env_var = "NIFRESEARCH_FAKE_KEY"
    required_inputs = {InputField.NAME}

    async def _fetch(self, subject, client):
        if subject.name_he == "boom":
            raise RuntimeError("kaboom")
        if subject.name_he == "empty":
            return []
        return [self._grey_fact(FactType.CONTACT, "a@b.co", channel="email")]


def test_classification_and_confidence():
    src = FakeGrey(api_key="k")
    assert src.classification == Classification.GREY_MARKET
    assert src.confidence == 0.25


@pytest.mark.asyncio
async def test_not_configured_is_skipped():
    result = await FakeGrey(api_key=None).query(Subject(name_he="x"))
    assert result.status == SourceStatus.SKIPPED
    assert "not configured" in result.error
    assert "NIFRESEARCH_FAKE_KEY" in result.error


@pytest.mark.asyncio
async def test_configured_match_is_ok_with_grey_fact():
    result = await FakeGrey(api_key="k").query(Subject(name_he="ok"))
    assert result.status == SourceStatus.OK
    f = result.facts[0]
    assert f.type == FactType.CONTACT
    assert f.source_id == "grey_fake"
    assert f.confidence == 0.25
    assert f.url == "https://example.com/"
    assert f.detail["caveat"] == GREY_CAVEAT
    assert f.detail["channel"] == "email"


@pytest.mark.asyncio
async def test_empty_is_no_match():
    result = await FakeGrey(api_key="k").query(Subject(name_he="empty"))
    assert result.status == SourceStatus.NO_MATCH


@pytest.mark.asyncio
async def test_exception_is_error():
    result = await FakeGrey(api_key="k").query(Subject(name_he="boom"))
    assert result.status == SourceStatus.ERROR
    assert "kaboom" in result.error
