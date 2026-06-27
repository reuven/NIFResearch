from nifresearch.models import (
    Classification, ComplianceMode, InputField, FactType, SourceStatus,
    Subject, Fact, SourceResult, Profile,
)


def test_enum_values():
    assert Classification.OFFICIAL_PUBLIC.value == "official_public"
    assert ComplianceMode.STRICT.value == "strict"
    assert InputField.ID_NUMBER.value == "id_number"
    assert FactType.BOARD_MEMBERSHIP.value == "board_membership"
    assert SourceStatus.OK.value == "ok"


def test_subject_available_inputs():
    s = Subject(name_he="דוד כהן", email="d@example.com")
    assert s.available_inputs() == {InputField.NAME, InputField.EMAIL}
    assert Subject(name_en="David Cohen").available_inputs() == {InputField.NAME}
    assert Subject().available_inputs() == set()


def test_profile_groups_facts_by_type():
    f1 = Fact(type=FactType.ROLE, value="יו\"ר", source_id="x")
    f2 = Fact(type=FactType.ROLE, value="חבר ועד", source_id="x")
    f3 = Fact(type=FactType.PROFESSION, value="עו\"ד", source_id="y")
    p = Profile(subject=Subject(), facts=[f1, f2, f3], results=[])
    grouped = p.by_type()
    assert grouped[FactType.ROLE] == [f1, f2]
    assert grouped[FactType.PROFESSION] == [f3]
