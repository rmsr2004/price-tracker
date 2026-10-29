"""Price extraction module orchestrating JSON-LD, meta, and CSS extractors."""

from tracker.extractors.base import (
    BaseExtractor,
    ExtractionResult,
    detect_currency,
    normalize_price,
)
from tracker.extractors.css import CssExtractor
from tracker.extractors.jsonld import JsonLdExtractor
from tracker.extractors.meta import MetaExtractor

__all__ = [
    "BaseExtractor",
    "CssExtractor",
    "ExtractionResult",
    "JsonLdExtractor",
    "MetaExtractor",
    "detect_currency",
    "extract_price",
    "normalize_price",
]


def extract_price(
    html: str,
    url: str,
    css_selector: str | None = None,
) -> ExtractionResult | None:
    """Try all price extraction methods in sequence: JSON-LD -> Meta tags -> CSS selector.

    Args:
        html: Raw HTML content of the page.
        url: The source URL of the page.
        css_selector: Optional CSS selector to use if JSON-LD and meta tags fail.

    Returns:
        ExtractionResult for the first successful extraction method, or None if all fail.
    """
    # 1. JSON-LD (highest priority)
    jsonld_result = JsonLdExtractor().extract(html, url)
    if jsonld_result is not None and jsonld_result.price is not None:
        return jsonld_result

    # 2. Open Graph / HTML meta tags
    meta_result = MetaExtractor().extract(html, url)
    if meta_result is not None and meta_result.price is not None:
        return meta_result

    # 3. User-provided CSS selector (fallback)
    if css_selector:
        css_result = CssExtractor().extract(html, url, css_selector=css_selector)
        if css_result is not None and css_result.price is not None:
            return css_result

    return None
