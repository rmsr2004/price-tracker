"""Utility functions for URL normalization and domain parsing."""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "ref",
    "ref_",
    "mc_cid",
    "mc_eid",
    "_ga",
    "_gl",
    "srsltid",
}


def normalize_url(url: str, strip_www: bool = True) -> str:
    """Normalize a product URL for consistent tracking and deduplication.

    - Strips fragment (#...).
    - Strips tracking query parameters (utm_*, fbclid, gclid, ref, etc.).
    - Lowercases scheme and host.
    - Strips 'www.' prefix from host when strip_www is True.
    - Removes trailing slashes from path (except single '/').
    - Sorts remaining query parameters.

    Args:
        url: Raw URL string.
        strip_www: Whether to strip leading 'www.' from hostname (default: True).

    Returns:
        Clean normalized URL string.
    """
    if not url:
        return ""

    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if strip_www and netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Filter query parameters
    filtered_query: list[tuple[str, str]] = []
    if parsed.query:
        for key, val in parse_qsl(parsed.query, keep_blank_values=True):
            lower_key = key.lower()
            if lower_key.startswith("utm_") or lower_key in TRACKING_PARAMS:
                continue
            filtered_query.append((key, val))

    # Sort remaining query parameters for canonical consistency
    filtered_query.sort(key=lambda item: item[0])
    query = urlencode(filtered_query)

    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def derive_store_name(url: str) -> str:
    """Derive a human-readable store name from a URL domain.

    Examples:
        "https://www.amazon.es/dp/123" -> "amazon.es"
        "https://store.example.com/p" -> "store.example.com"
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    host = host.removeprefix("www.")
    return host
