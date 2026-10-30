"""URL normalization tests used by product management."""

import pytest

from tracker.utils import normalize_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "https://www.example.com/product?utm_source=google&ref=123",
            "https://example.com/product",
        ),
        ("https://EXAMPLE.COM/Product/", "https://example.com/Product"),
        ("https://example.com/page#section", "https://example.com/page"),
        (
            "https://www.example.com/product?id=123&utm_medium=cpc",
            "https://example.com/product?id=123",
        ),
    ],
)
def test_normalize_url_cases(raw, expected):
    assert normalize_url(raw) == expected
