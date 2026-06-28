import asyncio
import pytest

from nifresearch.models import (
    Classification, ComplianceMode, InputField, Subject, SourceResult, SourceStatus,
)
from nifresearch.sources.base import Source
from nifresearch.orchestrator import run


class OkSource(Source):
    id = "ok"
    name = "ok"
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    async def query(self, subject):
        return SourceResult(source_id=self.id, status=SourceStatus.OK)


class LicensedSource(OkSource):
    id = "lic"
    classification = Classification.LICENSED


class BoomSource(OkSource):
    id = "boom"

    async def query(self, subject):
        raise RuntimeError("kaboom")


class SlowSource(OkSource):
    id = "slow"

    async def query(self, subject):
        await asyncio.sleep(5)
        return SourceResult(source_id=self.id, status=SourceStatus.OK)


@pytest.mark.asyncio
async def test_skips_blocked_and_missing_inputs():
    subject = Subject(name_he="דוד")
    results = await run(subject, [OkSource(), LicensedSource()], ComplianceMode.STRICT)
    by_id = {r.source_id: r for r in results}
    assert by_id["ok"].status == SourceStatus.OK
    assert by_id["lic"].status == SourceStatus.SKIPPED
    assert "compliance" in by_id["lic"].error


@pytest.mark.asyncio
async def test_skips_when_inputs_missing():
    results = await run(Subject(email="a@b.co"), [OkSource()], ComplianceMode.STRICT)
    assert results[0].status == SourceStatus.SKIPPED
    assert "inputs" in results[0].error


@pytest.mark.asyncio
async def test_query_exception_becomes_error():
    results = await run(Subject(name_he="דוד"), [BoomSource()], ComplianceMode.STRICT)
    assert results[0].status == SourceStatus.ERROR
    assert "kaboom" in results[0].error


@pytest.mark.asyncio
async def test_timeout_becomes_error():
    results = await run(Subject(name_he="דוד"), [SlowSource()], ComplianceMode.STRICT, timeout=0.05)
    assert results[0].status == SourceStatus.ERROR
