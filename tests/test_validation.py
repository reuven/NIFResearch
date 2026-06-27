from nifresearch.validation import (
    is_valid_israeli_id, normalize_id, normalize_phone, looks_like_email,
)


def test_valid_israeli_ids():
    assert is_valid_israeli_id("123456782") is True
    assert is_valid_israeli_id("000000018") is True
    # short IDs are left-padded to 9 digits
    assert is_valid_israeli_id("18") is True


def test_invalid_israeli_ids():
    assert is_valid_israeli_id("123456789") is False
    assert is_valid_israeli_id("abc") is False
    assert is_valid_israeli_id("1234567890") is False  # too long


def test_normalize_id():
    assert normalize_id(" 123456782 ") == "123456782"
    assert normalize_id("18") == "000000018"
    assert normalize_id("123456789") is None


def test_normalize_phone():
    assert normalize_phone("054-123-4567") == "0541234567"
    assert normalize_phone("+972 54 123 4567") == "+972541234567"
    assert normalize_phone("123") is None


def test_looks_like_email():
    assert looks_like_email("a@b.co") is True
    assert looks_like_email("not-an-email") is False
