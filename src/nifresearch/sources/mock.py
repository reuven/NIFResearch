from __future__ import annotations

from nifresearch.models import (
    Classification, Fact, FactType, InputField, SourceResult, SourceStatus, Subject,
)
from nifresearch.sources.base import Source


class MockBoardSource(Source):
    id = "mock_board"
    name = "Mock Board Memberships (sample data)"
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    async def query(self, subject: Subject) -> SourceResult:
        name = subject.name_he or subject.name_en
        if not name:
            return SourceResult(source_id=self.id, status=SourceStatus.NO_MATCH)
        facts = [
            Fact(
                type=FactType.BOARD_MEMBERSHIP,
                value="עמותת דוגמה לחינוך",
                source_id=self.id,
                confidence=0.4,
                detail={"note": "sample data, not a real record"},
            ),
            Fact(
                type=FactType.ROLE,
                value="חבר ועד",
                source_id=self.id,
                confidence=0.4,
            ),
        ]
        return SourceResult(source_id=self.id, status=SourceStatus.OK, facts=facts)
