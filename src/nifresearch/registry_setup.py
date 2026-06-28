from __future__ import annotations

import httpx

from nifresearch.sources.base import SourceRegistry
from nifresearch.sources.datagov_amutot import AmutotSource
from nifresearch.sources.datagov_companies import CompaniesSource
from nifresearch.sources.datagov_doctors import DoctorsSource


def build_default_registry(client: httpx.AsyncClient | None = None) -> SourceRegistry:
    registry = SourceRegistry()
    registry.register(AmutotSource(client))
    registry.register(CompaniesSource(client))
    registry.register(DoctorsSource(client))
    return registry
