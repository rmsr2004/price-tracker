"""Unit tests for shared utilities."""

from tracker.utils import normalize_url


def test_normalize_url_removes_tracking_data_and_fragment():
    assert (
        normalize_url(
            "HTTPS://WWW.Example.test/product/?utm_source=mail&color=red"
            "&fbclid=tracking#details"
        )
        == "https://example.test/product?color=red"
    )


def test_normalize_url_preserves_meaningful_query_parameters():
    assert normalize_url("https://example.test/item?b=2&a=1") == (
        "https://example.test/item?a=1&b=2"
    )
