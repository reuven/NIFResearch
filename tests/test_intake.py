from nifresearch.intake import build_subject


def test_valid_inputs_pass_through():
    subject, warnings = build_subject("דוד כהן", None, "d@e.co", "054-123-4567", "123456782")
    assert subject.name_he == "דוד כהן"
    assert subject.email == "d@e.co"
    assert subject.phone == "0541234567"
    assert subject.id_number == "123456782"
    assert warnings == []


def test_invalid_id_dropped_with_warning():
    subject, warnings = build_subject(None, "David", None, None, "123456789")
    assert subject.id_number is None
    assert any("ID" in w or "ת\"ז" in w for w in warnings)


def test_invalid_email_warns():
    subject, warnings = build_subject("דוד", None, "bad-email", None, None)
    assert subject.email is None
    assert any("email" in w.lower() for w in warnings)


def test_invalid_phone_dropped_with_warning():
    subject, warnings = build_subject("דוד", None, None, "123", None)
    assert subject.phone is None
    assert any("phone" in w.lower() for w in warnings)


def test_empty_strings_become_none_without_warning():
    subject, warnings = build_subject("דוד", "", "", "   ", None)
    assert subject.name_en is None
    assert subject.email is None
    assert subject.phone is None
    assert subject.id_number is None
    assert warnings == []
