from __future__ import annotations

import asyncio

from nifresearch.compliance import is_allowed
from nifresearch.models import ComplianceMode, SourceResult, SourceStatus, Subject
from nifresearch.sources.base import Source


async def _run_one(source: Source, subject: Subject, mode: ComplianceMode, timeout: float) -> SourceResult:
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
    try:
        return await asyncio.wait_for(source.query(subject), timeout)
    except (TimeoutError, asyncio.TimeoutError):
        return SourceResult(source_id=source.id, status=SourceStatus.ERROR, error="timed out")
    except Exception as exc:  # noqa: BLE001 — record any source failure
        return SourceResult(source_id=source.id, status=SourceStatus.ERROR, error=str(exc))


async def run(
    subject: Subject,
    sources: list[Source],
    mode: ComplianceMode,
    timeout: float = 10.0,
) -> list[SourceResult]:
    return await asyncio.gather(*(_run_one(s, subject, mode, timeout) for s in sources))
