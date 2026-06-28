from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from nifresearch.compliance import is_allowed
from nifresearch.models import ComplianceMode, SourceResult, SourceStatus, Subject
from nifresearch.sources.base import Source


def _gate(source: Source, subject: Subject, mode: ComplianceMode) -> SourceResult | None:
    """Return a SKIPPED result if the source must not run, else None."""
    if not is_allowed(source.classification, mode):
        return SourceResult(
            source_id=source.id, status=SourceStatus.SKIPPED,
            error="blocked by compliance mode",
        )
    if not source.can_run(subject):
        return SourceResult(
            source_id=source.id, status=SourceStatus.SKIPPED,
            error="missing required inputs",
        )
    return None


async def _execute(source: Source, subject: Subject, timeout: float) -> SourceResult:
    try:
        return await asyncio.wait_for(source.query(subject), timeout)
    except (TimeoutError, asyncio.TimeoutError):
        return SourceResult(source_id=source.id, status=SourceStatus.ERROR, error="timed out")
    except Exception as exc:  # noqa: BLE001 — record any source failure
        return SourceResult(source_id=source.id, status=SourceStatus.ERROR, error=str(exc))


async def _run_one(source: Source, subject: Subject, mode: ComplianceMode, timeout: float) -> SourceResult:
    skipped = _gate(source, subject, mode)
    if skipped is not None:
        return skipped
    return await _execute(source, subject, timeout)


async def run(
    subject: Subject,
    sources: list[Source],
    mode: ComplianceMode,
    timeout: float = 25.0,
) -> list[SourceResult]:
    return await asyncio.gather(*(_run_one(s, subject, mode, timeout) for s in sources))


async def run_streaming(
    subject: Subject,
    sources: list[Source],
    mode: ComplianceMode,
    timeout: float = 25.0,
) -> AsyncIterator[SourceResult]:
    pending: list[asyncio.Task[SourceResult]] = []
    for source in sources:
        skipped = _gate(source, subject, mode)
        if skipped is not None:
            yield skipped
        else:
            pending.append(asyncio.ensure_future(_execute(source, subject, timeout)))
    for fut in asyncio.as_completed(pending):
        yield await fut
