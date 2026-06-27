from nifresearch.models import (
    Classification, InputField, Subject, SourceResult, SourceStatus,
)
from nifresearch.sources.base import Source, SourceRegistry


class DummySource(Source):
    id = "dummy"
    name = "Dummy"
    classification = Classification.OFFICIAL_PUBLIC
    required_inputs = {InputField.NAME}

    async def query(self, subject):
        return SourceResult(source_id=self.id, status=SourceStatus.OK)


def test_can_run_requires_any_input():
    src = DummySource()
    assert src.can_run(Subject(name_he="דוד")) is True
    assert src.can_run(Subject(email="a@b.co")) is False


def test_registry_register_and_lookup():
    reg = SourceRegistry()
    src = DummySource()
    reg.register(src)
    assert reg.all() == [src]
    assert reg.get("dummy") is src
    assert reg.get("missing") is None
