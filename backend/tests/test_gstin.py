import pytest

from munshi.checks.gstin import (
    calculate_gstin_checksum,
    validate_gstin_checksum,
    validate_gstin_format,
    validate_gstin_matches_buyer,
    validate_state_code,
)


def test_validate_gstin_format():
    assert validate_gstin_format("27AAPFU0939F1ZV")
    assert validate_gstin_format("27aapfu0939f1zv")
    assert not validate_gstin_format("27AAPFU0939F1XV")
    assert not validate_gstin_format("27AAPFU0939F0ZV")
    assert not validate_gstin_format("27AAPFU0939F1")


def test_checksum_matches_known_gstin_and_rejects_tampering():
    assert calculate_gstin_checksum("27AAPFU0939F1Z") == "V"
    assert validate_gstin_checksum("27AAPFU0939F1ZV")
    assert not validate_gstin_checksum("27AAPFU0939F1Z5")


def test_checksum_requires_valid_gstin_body():
    with pytest.raises(ValueError, match="14-character GSTIN body"):
        calculate_gstin_checksum("not-a-gstin")


def test_buyer_match_is_case_insensitive_and_requires_both_values():
    assert validate_gstin_matches_buyer("27AAPFU0939F1ZV", "27aapfu0939f1zv")
    assert not validate_gstin_matches_buyer("27AAPFU0939F1ZV", "29AAPFU0939F1ZV")
    assert not validate_gstin_matches_buyer("", "27AAPFU0939F1ZV")


def test_state_code_matches_gstin_prefix():
    assert validate_state_code("27AAPFU0939F1ZV", "27")
    assert not validate_state_code("27AAPFU0939F1ZV", "29")
    assert not validate_state_code("invalid", "27")
