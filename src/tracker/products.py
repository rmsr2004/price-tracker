"""Business logic for managing tracked products."""

from decimal import Decimal
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from tracker import repository
from tracker.exceptions import (
    DuplicateProductError,
    NoPriceFoundError,
    ProductNotFoundError,
)
from tracker.extractors import ExtractionResult, extract_price
from tracker.fetcher import fetch
from tracker.models import Product
from tracker.utils import derive_store_name, normalize_url


def _find_product(session: Session, identifier: str | int) -> Product | None:
    """Find a product by numeric ID or normalized URL."""
    if isinstance(identifier, int) or (
        isinstance(identifier, str) and identifier.isdecimal()
    ):
        return repository.get_product_by_id(session, int(identifier))
    return repository.get_product_by_url(session, normalize_url(str(identifier)))


def _fallback_name(url: str) -> str:
    """Build a readable name when the page does not provide one."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").split("/")
    snippet = next((part for part in reversed(path) if part), "")
    return (
        f"{derive_store_name(url)} / {snippet}" if snippet else derive_store_name(url)
    )


def add_product(
    session: Session,
    url: str,
    target_price: float | Decimal | None = None,
    css_selector: str | None = None,
    name_override: str | None = None,
) -> tuple[Product, ExtractionResult]:
    """Fetch, extract, and persist a product with its first price record."""
    normalized_url = normalize_url(url)
    if repository.get_product_by_url(session, normalized_url) is not None:
        raise DuplicateProductError(
            f"This URL is already being tracked: {normalized_url}"
        )

    html = fetch(normalized_url)
    result = extract_price(html, normalized_url, css_selector=css_selector)
    if result is None or result.price is None:
        raise NoPriceFoundError(
            f"Could not extract a price from {normalized_url}. "
            "Try providing a custom CSS selector using --css-selector."
        )

    product = repository.create_product(
        session,
        name=name_override or result.name or _fallback_name(normalized_url),
        store=derive_store_name(normalized_url),
        url=normalized_url,
        css_selector=css_selector,
        target_price=target_price,
        currency=result.currency,
    )
    repository.add_price_record(
        session,
        product.id,
        price=result.price,
        in_stock=result.in_stock,
        status="ok",
    )
    return product, result


def list_products(
    session: Session, include_inactive: bool = False
) -> list[dict[str, object]]:
    """Return products and their latest prices and health status."""
    products = (
        repository.get_all_products(session)
        if include_inactive
        else repository.get_active_products(session)
    )
    listed: list[dict[str, object]] = []
    for product in products:
        latest = repository.get_latest_price(session, product.id)
        latest_ok = repository.get_latest_price(
            session, product.id, status_ok_only=True
        )
        recent = repository.get_last_n_prices(session, product.id, 50)
        failures = 0
        for record in recent:
            if record.status == "ok":
                break
            failures += 1

        status = "inactive" if not product.active else "active"
        if product.active and failures:
            status = f"failing ({failures})"
        listed.append(
            {
                "id": product.id,
                "name": product.name,
                "store": product.store,
                "url": product.url,
                "price": latest_ok.price if latest_ok else None,
                "target_price": product.target_price,
                "last_checked": latest.checked_at if latest else None,
                "status": status,
            }
        )
    return listed


def remove_product(session: Session, identifier: str | int) -> dict[str, object]:
    """Delete a product and return the counts of related records removed."""
    product = _find_product(session, identifier)
    if product is None:
        raise ProductNotFoundError("Product not found")

    result = {
        "id": product.id,
        "name": product.name,
        "store": product.store,
        "price_history_count": len(product.price_history),
        "alerts_count": len(product.alerts_sent),
    }
    repository.delete_product(session, product.id)
    return result


def preview_remove_product(
    session: Session, identifier: str | int
) -> dict[str, object]:
    """Return the product and related-record counts before deletion."""
    product = _find_product(session, identifier)
    if product is None:
        raise ProductNotFoundError("Product not found")
    return {
        "id": product.id,
        "name": product.name,
        "store": product.store,
        "price_history_count": len(product.price_history),
        "alerts_count": len(product.alerts_sent),
    }


def deactivate_product(session: Session, identifier: str | int) -> Product:
    """Deactivate a product while preserving all historical records."""
    product = _find_product(session, identifier)
    if product is None:
        raise ProductNotFoundError("Product not found")
    return repository.deactivate_product(session, product.id)


def reactivate_product(session: Session, identifier: str | int) -> Product:
    """Reactivate a product."""
    product = _find_product(session, identifier)
    if product is None:
        raise ProductNotFoundError("Product not found")
    return repository.reactivate_product(session, product.id)


def set_target_price(
    session: Session, product_id: int, price: float | Decimal | None
) -> Product:
    """Set or clear a product's target price."""
    product = repository.get_product_by_id(session, product_id)
    if product is None:
        raise ProductNotFoundError("Product not found")
    return repository.update_product(session, product_id, target_price=price)
