from __future__ import annotations

import httpx

from nifresearch.sources.base import SourceRegistry
from nifresearch.sources.datagov_amutot import AmutotSource
from nifresearch.sources.datagov_companies import CompaniesSource
from nifresearch.sources.datagov_doctors import DoctorsSource
from nifresearch.sources.grey.apollo import ApolloSource
from nifresearch.sources.grey.clearbit import ClearbitSource
from nifresearch.sources.grey.contactout import ContactOutSource
from nifresearch.sources.grey.hunter import HunterSource
from nifresearch.sources.grey.lusha import LushaSource
from nifresearch.sources.grey.numverify import NumVerifySource
from nifresearch.sources.grey.peopledatalabs import PeopleDataLabsSource
from nifresearch.sources.grey.pipl import PiplSource
from nifresearch.sources.grey.rocketreach import RocketReachSource
from nifresearch.sources.grey.twilio_lookup import TwilioLookupSource


def build_default_registry(client: httpx.AsyncClient | None = None) -> SourceRegistry:
    registry = SourceRegistry()
    registry.register(AmutotSource(client))
    registry.register(CompaniesSource(client))
    registry.register(DoctorsSource(client))
    registry.register(PiplSource(client))
    registry.register(LushaSource(client))
    registry.register(HunterSource(client))
    registry.register(NumVerifySource(client))
    registry.register(TwilioLookupSource(client))
    registry.register(ApolloSource(client))
    registry.register(RocketReachSource(client))
    registry.register(ContactOutSource(client))
    registry.register(ClearbitSource(client))
    registry.register(PeopleDataLabsSource(client))
    return registry
