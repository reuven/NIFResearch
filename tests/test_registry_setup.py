from nifresearch.registry_setup import build_default_registry


def test_default_registry_contains_expected_sources():
    reg = build_default_registry()
    ids = [s.id for s in reg.all()]
    assert ids == [
        "datagov_amutot", "datagov_companies", "datagov_doctors",
        "grey_pipl", "grey_lusha", "grey_hunter", "grey_numverify", "grey_twilio",
        "grey_apollo", "grey_rocketreach", "grey_contactout", "grey_clearbit", "grey_pdl",
    ]
