from nifresearch.models import ComplianceMode
from nifresearch.web.params import parse_compliance_mode, build_request_context


def test_parse_compliance_mode():
    assert parse_compliance_mode("standard") == ComplianceMode.STANDARD
    assert parse_compliance_mode("PERMISSIVE") == ComplianceMode.PERMISSIVE
    assert parse_compliance_mode("strict") == ComplianceMode.STRICT
    assert parse_compliance_mode(None) == ComplianceMode.STRICT
    assert parse_compliance_mode("garbage") == ComplianceMode.STRICT


def test_build_request_context():
    subject, warnings, mode = build_request_context(
        "דוד כהן", None, "d@e.co", None, "123456789", "standard"
    )
    assert subject.name_he == "דוד כהן"
    assert subject.email == "d@e.co"
    assert subject.id_number is None        # invalid ID dropped
    assert any("ID" in w or "ת\"ז" in w for w in warnings)
    assert mode == ComplianceMode.STANDARD
