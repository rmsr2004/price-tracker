"""Unit tests for price normalization and currency detection."""

import pytest

from tracker.extractors.base import detect_currency, normalize_price


@pytest.mark.parametrize(
    ("raw_input", "expected_price"),
    [
        ("199,00 €", 199.00),
        ("€199.00", 199.00),
        ("1.299,00 €", 1299.00),
        ("1,299.00", 1299.00),
        ("1 299,00€", 1299.00),
        ("$1,299.00", 1299.00),
        ("199", 199.00),
        ("free", None),
        ("", None),
        ("€0.00", 0.00),
        (None, None),
        (299, 299.00),
        (299.95, 299.95),
        ("R$ 1.500,50", 1500.50),
        ("Price unavailable", None),
    ],
)
def test_normalize_price(raw_input, expected_price):
    """Test price normalization handles various PT/EN formats correctly."""
    assert normalize_price(raw_input) == expected_price


@pytest.mark.parametrize(
    ("raw_input", "expected_currency"),
    [
        ("199,00 €", "EUR"),
        ("€199.00", "EUR"),
        ("EUR 250.00", "EUR"),
        ("$1,299.00", "USD"),
        ("USD 1299", "USD"),
        ("£49.99", "GBP"),
        ("GBP 49.99", "GBP"),
        ("BRL 100", "BRL"),
        ("Unknown price", "EUR"),  # Default fallback
    ],
)
def test_detect_currency(raw_input, expected_currency):
    """Test currency detection from symbols and ISO codes."""
    assert detect_currency(raw_input) == expected_currency
