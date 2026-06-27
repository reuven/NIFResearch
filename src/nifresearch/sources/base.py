from __future__ import annotations

from abc import ABC, abstractmethod

from nifresearch.models import Classification, InputField, SourceResult, Subject


class Source(ABC):
    id: str
    name: str
    classification: Classification
    required_inputs: set[InputField]

    def can_run(self, subject: Subject) -> bool:
        return bool(self.required_inputs & subject.available_inputs())

    @abstractmethod
    async def query(self, subject: Subject) -> SourceResult:
        ...


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: list[Source] = []

    def register(self, source: Source) -> None:
        self._sources.append(source)

    def all(self) -> list[Source]:
        return list(self._sources)

    def get(self, source_id: str) -> Source | None:
        for s in self._sources:
            if s.id == source_id:
                return s
        return None
