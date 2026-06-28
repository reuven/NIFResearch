import asyncio
import time
import httpx
import pytest
import respx

from nifresearch.models import (
    Classification, ComplianceMode, InputField, Subject, SourceResult, SourceStatus,
)
from nifresearch.sources.base import Source
from nifresearch.orchestrator import run, run_streaming
from nifresearch.sources.grey.pipl import PiplSource


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


class SlowOkSource(Source):
    """Eligible source that sleeps for a configurable duration, used to test concurrency."""
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    def __init__(self, source_id: str, delay: float) -> None:
        self.id = source_id
        self.name = source_id
        self._delay = delay

    async def query(self, subject):
        await asyncio.sleep(self._delay)
        return SourceResult(source_id=self.id, status=SourceStatus.OK)


@pytest.mark.asyncio
async def test_skips_blocked_and_missing_inputs():
    subject = Subject(name_he="דוד")
    sources = [OkSource(), LicensedSource()]
    results = await run(subject, sources, ComplianceMode.STRICT)
    # Order must match input order
    assert results[0].source_id == sources[0].id
    assert results[1].source_id == sources[1].id
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


@pytest.mark.asyncio
async def test_eligible_sources_run_concurrently():
    """Two sources each sleeping D seconds must complete in much less than 2*D total."""
    D = 0.3
    subject = Subject(name_he="דוד")
    sources = [SlowOkSource("slow_a", D), SlowOkSource("slow_b", D)]

    t0 = time.perf_counter()
    results = await run(subject, sources, ComplianceMode.STRICT)
    elapsed = time.perf_counter() - t0

    assert results[0].source_id == "slow_a"
    assert results[1].source_id == "slow_b"
    assert results[0].status == SourceStatus.OK
    assert results[1].status == SourceStatus.OK
    # If sources ran sequentially, elapsed ≥ 2*D ≈ 0.6s; concurrent execution should be < 1.5*D
    assert elapsed < 1.5 * D, (
        f"Sources appear to have run sequentially: elapsed={elapsed:.3f}s >= 1.5*D={1.5*D:.3f}s"
    )


@pytest.mark.asyncio
async def test_run_streaming_yields_one_result_per_source_including_skipped():
    subject = Subject(name_he="דוד")
    sources = [OkSource(), LicensedSource(), BoomSource()]
    results = [r async for r in run_streaming(subject, sources, ComplianceMode.STRICT)]
    by_id = {r.source_id: r for r in results}
    assert set(by_id) == {"ok", "lic", "boom"}
    assert by_id["ok"].status == SourceStatus.OK
    assert by_id["lic"].status == SourceStatus.SKIPPED      # licensed blocked under STRICT
    assert by_id["boom"].status == SourceStatus.ERROR       # raises


@pytest.mark.asyncio
async def test_grey_source_blocked_under_strict():
    src = PiplSource(api_key="k")
    results = await run(Subject(email="a@b.co"), [src], ComplianceMode.STRICT)
    assert results[0].status == SourceStatus.SKIPPED
    assert "compliance" in results[0].error


@pytest.mark.asyncio
@respx.mock
async def test_grey_source_runs_under_permissive():
    respx.get("https://api.pipl.com/search/").mock(return_value=httpx.Response(200, json={
        "person": {"emails": [{"address": "a@b.co"}]}
    }))
    async with httpx.AsyncClient() as client:
        src = PiplSource(client=client, api_key="k")
        results = await run(Subject(email="a@b.co"), [src], ComplianceMode.PERMISSIVE)
    assert results[0].status == SourceStatus.OK
