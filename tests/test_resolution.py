from nifresearch.models import (
    Fact, FactType, Profile, SourceResult, SourceStatus, Subject,
)
from nifresearch.resolution import build_profile


def test_collects_only_ok_facts():
    ok = SourceResult(
        source_id="a", status=SourceStatus.OK,
        facts=[Fact(type=FactType.ROLE, value="חבר ועד", source_id="a")],
    )
    skipped = SourceResult(source_id="b", status=SourceStatus.SKIPPED)
    profile = build_profile(Subject(), [ok, skipped])
    assert len(profile.facts) == 1
    assert profile.results == [ok, skipped]


def test_dedupes_same_type_value_keeping_highest_confidence():
    f_low = Fact(type=FactType.ROLE, value="חבר ועד", source_id="a", confidence=0.3)
    f_high = Fact(type=FactType.ROLE, value="חבר ועד", source_id="b", confidence=0.9)
    r = [
        SourceResult(source_id="a", status=SourceStatus.OK, facts=[f_low]),
        SourceResult(source_id="b", status=SourceStatus.OK, facts=[f_high]),
    ]
    profile = build_profile(Subject(), r)
    assert len(profile.facts) == 1
    kept = profile.facts[0]
    assert kept.confidence == 0.9
    assert set(kept.detail["also_from"]) == {"a", "b"}
