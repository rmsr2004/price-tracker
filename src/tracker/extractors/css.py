"""CSS selector price extractor."""

from typing import Any

from bs4 import BeautifulSoup
from soupsieve import SelectorSyntaxError

from tracker.extractors.base import (
    BaseExtractor,
    ExtractionResult,
    detect_currency,
    normalize_price,
)


class CssExtractor(BaseExtractor):
    """Extracts product price using a custom user-provided CSS selector."""

    def extract(self, html: str, url: str, **kwargs: Any) -> ExtractionResult | None:
        """Extract price element text matching css_selector."""
        css_selector: str | None = kwargs.get("css_selector")
        if not css_selector or not css_selector.strip():
            return None

        soup = BeautifulSoup(html, "lxml")
        try:
            matches = soup.select(css_selector.strip())
        except (SelectorSyntaxError, ValueError, TypeError):
            return None

        if not matches:
            return None

        first_match = matches[0]
        raw_text = first_match.get_text(strip=True)
        if not raw_text:
            return None

        price = normalize_price(raw_text)
        if price is None:
            return None

        currency = detect_currency(raw_text)

        # Name extraction (og:title -> title tag)
        name: str | None = None
        og_title = soup.find("meta", property="og:title") or soup.find(
            "meta", attrs={"name": "og:title"}
        )
        if og_title and og_title.get("content"):
            name = og_title["content"].strip()
        elif soup.title and soup.title.string:
            name = soup.title.string.strip()

        return ExtractionResult(
            price=price,
            currency=currency,
            name=name,
            in_stock=None,
            method="css",
        )
