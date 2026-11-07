"""GSTIN format, checksum, buyer-match, and state-code validation."""

import re


GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)
GSTIN_BODY_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z$")
BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def validate_gstin_format(gstin: str) -> bool:
    """Validate the 15-character GSTIN structure, including the default 'Z'."""
    return bool(gstin and GSTIN_PATTERN.fullmatch(gstin.upper()))


def calculate_gstin_checksum(gstin_without_checksum: str) -> str:
    """Calculate the GSTIN check character using the alternating base-36 algorithm."""
    gstin_body = gstin_without_checksum.upper()
    if not GSTIN_BODY_PATTERN.fullmatch(gstin_body):
        raise ValueError("GSTIN checksum input must be a valid 14-character GSTIN body")

    total = 0
    factor = 2
    for character in reversed(gstin_body):
        product = BASE36.index(character) * factor
        total += product // 36 + product % 36
        factor = 1 if factor == 2 else 2

    return BASE36[(36 - total % 36) % 36]


def validate_gstin_checksum(gstin: str) -> bool:
    """Return whether a structurally valid GSTIN has a matching check character."""
    if not validate_gstin_format(gstin):
        return False

    normalized = gstin.upper()
    return calculate_gstin_checksum(normalized[:14]) == normalized[14]


def validate_gstin_matches_buyer(record_gstin: str, invoice_gstin: str) -> bool:
    """Compare an invoice GSTIN to the buyer's recorded GSTIN, case-insensitively."""
    return bool(record_gstin and invoice_gstin and record_gstin.upper() == invoice_gstin.upper())


def validate_state_code(gstin: str, expected_state_code: str) -> bool:
    """Check that the GSTIN's two-character state prefix matches the record."""
    return bool(
        validate_gstin_format(gstin)
        and expected_state_code
        and gstin[:2] == expected_state_code
    )
