from nifresearch.registry_setup import build_default_registry


def test_default_registry_contains_expected_sources():
    reg = build_default_registry()
    ids = [s.id for s in reg.all()]
    assert ids == ["mock_board", "datagov_amutot", "datagov_companies", "bar_lawyers"]
