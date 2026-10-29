"""JSON-LD schema.org/Product price extractor."""

import json
from typing import Any

from bs4 import BeautifulSoup

from tracker.extractors.base import (
    BaseExtractor,
    ExtractionResult,
    detect_currency,
    normalize_price,
)


class JsonLdExtractor(BaseExtractor):
    """Extracts product price information from JSON-LD schema.org metadata."""

    def extract(self, html: str, url: str, **kwargs: Any) -> ExtractionResult | None:
        """Extract product details from application/ld+json script tags."""
        soup = BeautifulSoup(html, "lxml")
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            content = script.string or script.get_text()
            if not content:
                continue

            try:
                data = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                continue

            product = self._find_product(data)
            if product is None:
                continue

            result = self._extract_from_product(product)
            if result is not None and result.price is not None:
                return result

        return None

    def _find_product(self, data: Any) -> dict[str, Any] | None:
        """Find a schema.org/Product object in JSON-LD structure."""
        if isinstance(data, list):
            for item in data:
                found = self._find_product(item)
                if found is not None:
                    return found
            return None

        if not isinstance(data, dict):
            return None

        # Check @graph array
        if "@graph" in data and isinstance(data["@graph"], list):
            for item in data["@graph"]:
                found = self._find_product(item)
                if found is not None:
                    return found

        type_val = data.get("@type")
        if isinstance(type_val, str) and type_val.lower() == "product":
            return data
        if isinstance(type_val, list) and any(
            isinstance(t, str) and t.lower() == "product" for t in type_val
        ):
            return data

        return None

    def _extract_from_product(self, product: dict[str, Any]) -> ExtractionResult | None:
        """Extract price, currency, name, and stock status from Product dict."""
        name = product.get("name")
        if not isinstance(name, str):
            name = None

        raw_offers = product.get("offers")
        if raw_offers is None:
            return None

        offers: list[dict[str, Any]] = []
        if isinstance(raw_offers, dict):
            offers = [raw_offers]
        elif isinstance(raw_offers, list):
            offers = [o for o in raw_offers if isinstance(o, dict)]

        if not offers:
            return None

        best_price: float | None = None
        best_currency: str = "EUR"
        best_in_stock: bool | None = None

        for offer in offers:
            # Price can be in 'price' or 'lowPrice'
            raw_price = offer.get("price")
            if raw_price is None:
                raw_price = offer.get("lowPrice")

            norm_price = normalize_price(raw_price)
            if norm_price is None:
                continue

            # Pick the lowest price among valid offers
            if best_price is None or norm_price < best_price:
                best_price = norm_price

                # Currency
                curr = offer.get("priceCurrency")
                if isinstance(curr, str) and curr.strip():
                    best_currency = detect_currency(curr.strip())
                elif isinstance(raw_price, str):
                    best_currency = detect_currency(raw_price)

                # Stock availability
                avail = offer.get("availability")
                if isinstance(avail, str):
                    avail_lower = avail.lower()
                    if "instock" in avail_lower or "preorder" in avail_lower:
                        best_in_stock = True
                    elif (
                        "outofstock" in avail_lower
                        or "soldout" in avail_lower
                        or "discontinued" in avail_lower
                    ):
                        best_in_stock = False

        if best_price is None:
            return None

        return ExtractionResult(
            price=best_price,
            currency=best_currency,
            name=name,
            in_stock=best_in_stock,
            method="json-ld",
        )
