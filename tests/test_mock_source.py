import pytest

from nifresearch.models import FactType, InputField, Subject, SourceStatus, Classification
from nifresearch.sources.mock import MockBoardSource


def test_metadata():
    src = MockBoardSource()
    assert src.id == "mock_board"
    assert src.classification == Classification.OFFICIAL_PUBLIC
    assert src.required_inputs == {InputField.NAME}


@pytest.mark.asyncio
async def test_query_returns_deterministic_facts():
    src = MockBoardSource()
    result = await src.query(Subject(name_he="דוד כהן"))
    assert result.status == SourceStatus.OK
    assert result.source_id == "mock_board"
    types = {f.type for f in result.facts}
    assert FactType.BOARD_MEMBERSHIP in types
    assert FactType.ROLE in types
    assert all(f.source_id == "mock_board" for f in result.facts)


@pytest.mark.asyncio
async def test_query_no_name_is_no_match():
    result = await MockBoardSource().query(Subject(email="a@b.co"))
    assert result.status == SourceStatus.NO_MATCH
    assert result.facts == []
