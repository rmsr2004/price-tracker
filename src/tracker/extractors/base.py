"""Base price extractor interface and normalization utilities."""

import re
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    """Standardized result of a price extraction attempt."""

    price: float | None
    currency: str
    name: str | None
    in_stock: bool | None
    method: str


class BaseExtractor:
    """Base class for price extractors."""

    def extract(self, html: str, url: str, **kwargs) -> ExtractionResult | None:
        """Try to extract price information from the HTML.

        Args:
            html: Raw HTML content of the page.
            url: The source URL of the page.
            **kwargs: Additional parameters (e.g. css_selector).

        Returns:
            ExtractionResult if extraction succeeds, None otherwise.
        """
        raise NotImplementedError


def detect_currency(raw: str, default: str = "EUR") -> str:
    """Detect currency code from raw text, symbols, or ISO codes."""
    if not raw:
        return default

    upper = raw.upper()
    if "€" in raw or "EUR" in upper:
        return "EUR"
    if "$" in raw or "USD" in upper:
        return "USD"
    if "£" in raw or "GBP" in upper:
        return "GBP"

    # Match any 3-letter currency code (e.g. BRL, CAD, etc.)
    match = re.search(r"\b([A-Z]{3})\b", upper)
    if match:
        return match.group(1)

    return default


def normalize_price(raw: str | float | None) -> float | None:
    """Parse a raw price string or numeric value into a normalized float.

    Handles PT and EN price formats, including thousands separators (space, dot, comma)
    and decimal separators (comma, dot).

    Args:
        raw: Raw price representation (e.g. "1.299,00 €", "€199.00", 199.99).

    Returns:
        float with up to 2 decimal places, or None if parsing fails.
    """
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        return round(float(raw), 2)

    text = str(raw).strip().replace("\xa0", " ")
    if not text:
        return None

    # Check for presence of any digits
    if not re.search(r"\d", text):
        return None

    # Extract the numeric candidate portion (digits, dots, commas, spaces, minus)
    # Remove currency symbols and other non-numeric characters
    cleaned = re.sub(r"[^\d.,\s-]", "", text).strip()
    if not cleaned or not re.search(r"\d", cleaned):
        return None

    has_dot = "." in cleaned
    has_comma = "," in cleaned

    try:
        if has_dot and has_comma:
            last_dot = cleaned.rfind(".")
            last_comma = cleaned.rfind(",")
            if last_comma > last_dot:
                # Comma is the decimal separator (PT/EU format: 1.299,00)
                sanitized = cleaned.replace(".", "").replace(" ", "").replace(",", ".")
            else:
                # Dot is the decimal separator (EN format: 1,299.00)
                sanitized = cleaned.replace(",", "").replace(" ", "")
        elif has_comma:
            # Only comma is present
            parts = cleaned.split(",")
            last_part = parts[-1].strip()
            if len(last_part) == 2:
                # Decimal comma (e.g. 199,00 or 1 299,00)
                prefix = "".join(parts[:-1]).replace(" ", "")
                sanitized = f"{prefix}.{last_part}"
            else:
                # Thousands comma (e.g. 1,299 or 1,299,000)
                sanitized = cleaned.replace(",", "").replace(" ", "")
        elif has_dot:
            # Only dot is present
            parts = cleaned.split(".")
            last_part = parts[-1].strip()
            if len(last_part) == 2:
                # Decimal dot (e.g. 199.00 or 1 299.00)
                prefix = "".join(parts[:-1]).replace(" ", "")
                sanitized = f"{prefix}.{last_part}"
            else:
                # Thousands dot (e.g. 1.299 or 1.299.000)
                sanitized = cleaned.replace(".", "").replace(" ", "")
        else:
            # Integer without separators (e.g. 199)
            sanitized = cleaned.replace(" ", "")

        return round(float(sanitized), 2)
    except (ValueError, IndexError):
        return None
