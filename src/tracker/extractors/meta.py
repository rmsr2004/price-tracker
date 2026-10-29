"""Meta tags and Open Graph price extractor."""

from typing import Any

from bs4 import BeautifulSoup

from tracker.extractors.base import (
    BaseExtractor,
    ExtractionResult,
    detect_currency,
    normalize_price,
)


class MetaExtractor(BaseExtractor):
    """Extracts product price information from HTML meta and Open Graph tags."""

    def extract(self, html: str, url: str, **kwargs: Any) -> ExtractionResult | None:
        """Extract product price from meta tags."""
        soup = BeautifulSoup(html, "lxml")

        # 1. Product price amount tags in priority order
        price_tag_candidates = [
            ("property", "product:price:amount"),
            ("name", "product:price:amount"),
            ("property", "og:price:amount"),
            ("name", "og:price:amount"),
        ]

        raw_price: str | None = None
        for attr, val in price_tag_candidates:
            tag = soup.find("meta", attrs={attr: val})
            if tag and tag.get("content"):
                raw_price = tag["content"]
                break

        if not raw_price:
            return None

        price = normalize_price(raw_price)
        if price is None:
            return None

        # 2. Currency
        currency_tag_candidates = [
            ("property", "product:price:currency"),
            ("name", "product:price:currency"),
            ("property", "og:price:currency"),
            ("name", "og:price:currency"),
        ]

        raw_currency: str | None = None
        for attr, val in currency_tag_candidates:
            tag = soup.find("meta", attrs={attr: val})
            if tag and tag.get("content"):
                raw_currency = tag["content"]
                break

        currency = detect_currency(raw_currency or raw_price)

        # 3. Product Name (og:title -> title tag)
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
            method="meta",
        )
