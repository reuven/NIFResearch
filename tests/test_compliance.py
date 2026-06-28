from nifresearch.models import Classification, ComplianceMode
from nifresearch.compliance import allowed_classifications, is_allowed


def test_strict_allows_only_official():
    assert allowed_classifications(ComplianceMode.STRICT) == {Classification.OFFICIAL_PUBLIC}
    assert is_allowed(Classification.OFFICIAL_PUBLIC, ComplianceMode.STRICT) is True
    assert is_allowed(Classification.LICENSED, ComplianceMode.STRICT) is False
    assert is_allowed(Classification.GREY_MARKET, ComplianceMode.STRICT) is False


def test_standard_adds_licensed():
    assert is_allowed(Classification.LICENSED, ComplianceMode.STANDARD) is True
    assert is_allowed(Classification.GREY_MARKET, ComplianceMode.STANDARD) is False
    assert allowed_classifications(ComplianceMode.STANDARD) == {Classification.OFFICIAL_PUBLIC, Classification.LICENSED}


def test_permissive_allows_all():
    assert is_allowed(Classification.GREY_MARKET, ComplianceMode.PERMISSIVE) is True
    assert allowed_classifications(ComplianceMode.PERMISSIVE) == {Classification.OFFICIAL_PUBLIC, Classification.LICENSED, Classification.GREY_MARKET}
