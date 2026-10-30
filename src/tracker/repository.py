"""Data access repository for products, price history, and alerts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tracker.models import AlertSent, PriceHistory, Product

# ============================================================================
# Product Data Access
# ============================================================================


def create_product(
    session: Session,
    name: str,
    store: str,
    url: str,
    css_selector: str | None = None,
    target_price: float | Decimal | None = None,
    currency: str = "EUR",
    active: bool = True,
) -> Product:
    """Create and persist a new Product.

    Args:
        session: Active database session.
        name: Product name.
        store: Store domain identifier.
        url: Unique product URL.
        css_selector: Optional custom CSS selector for price extraction.
        target_price: Optional target price threshold for alerts.
        currency: 3-character currency ISO code (default: EUR).
        active: Initial active status.

    Returns:
        The newly created and persisted Product.
    """
    target_dec = Decimal(str(target_price)) if target_price is not None else None
    product = Product(
        name=name,
        store=store,
        url=url,
        css_selector=css_selector,
        target_price=target_dec,
        currency=currency,
        active=active,
    )
    session.add(product)
    session.flush()
    return product


def get_product_by_id(session: Session, product_id: int) -> Product | None:
    """Retrieve a Product by its primary key ID."""
    stmt = select(Product).where(Product.id == product_id)
    return session.scalar(stmt)


def get_product_by_url(session: Session, url: str) -> Product | None:
    """Retrieve a Product by its unique URL."""
    stmt = select(Product).where(Product.url == url)
    return session.scalar(stmt)


def get_active_products(session: Session) -> list[Product]:
    """Retrieve all active Products ordered by ID."""
    stmt = select(Product).where(Product.active.is_(True)).order_by(Product.id)
    return list(session.scalars(stmt).all())


def get_all_products(session: Session) -> list[Product]:
    """Retrieve all Products including inactive ones ordered by ID."""
    stmt = select(Product).order_by(Product.id)
    return list(session.scalars(stmt).all())


def update_product(
    session: Session,
    product_id: int,
    **kwargs: Any,
) -> Product:
    """Update fields on an existing Product.

    Args:
        session: Active database session.
        product_id: Primary key of product to update.
        **kwargs: Attributes to update.

    Returns:
        The updated Product instance.

    Raises:
        ValueError: If the product does not exist.
    """
    product = get_product_by_id(session, product_id)
    if product is None:
        raise ValueError(f"Product with ID {product_id} not found.")

    writable_fields = {
        "name",
        "store",
        "url",
        "css_selector",
        "target_price",
        "currency",
        "active",
    }
    unknown_fields = set(kwargs) - writable_fields
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise ValueError(f"Unknown product field(s): {fields}")

    for key, value in kwargs.items():
        if key == "target_price" and value is not None:
            value = Decimal(str(value))
        setattr(product, key, value)

    session.flush()
    return product


def delete_product(session: Session, product_id: int) -> bool:
    """Delete a Product and cascade-delete its history and alerts.

    Returns:
        True if deleted, False if product was not found.
    """
    product = get_product_by_id(session, product_id)
    if product is None:
        return False
    session.delete(product)
    session.flush()
    return True


def deactivate_product(session: Session, product_id: int) -> Product:
    """Set active status to False for a Product."""
    return update_product(session, product_id, active=False)


def reactivate_product(session: Session, product_id: int) -> Product:
    """Set active status to True for a Product."""
    return update_product(session, product_id, active=True)


# ============================================================================
# Price History Data Access
# ============================================================================


def add_price_record(
    session: Session,
    product_id: int,
    price: float | Decimal | None,
    in_stock: bool | None,
    status: str,
) -> PriceHistory:
    """Record a price check result for a Product.

    Args:
        session: Active database session.
        product_id: Associated Product ID.
        price: Extracted price (or None if fetch/parse error).
        in_stock: Stock availability boolean (or None if unknown).
        status: Check outcome ('ok', 'fetch_error', 'parse_error').

    Returns:
        The created PriceHistory entry.
    """
    price_dec = Decimal(str(price)) if price is not None else None
    record = PriceHistory(
        product_id=product_id,
        price=price_dec,
        in_stock=in_stock,
        status=status,
    )
    session.add(record)
    session.flush()
    return record


def get_latest_price(
    session: Session,
    product_id: int,
    status_ok_only: bool = False,
) -> PriceHistory | None:
    """Get the most recent price record for a product.

    Args:
        session: Active database session.
        product_id: Product ID.
        status_ok_only: If True, only considers records where status == 'ok'.

    Returns:
        Latest PriceHistory entry, or None if none exist.
    """
    stmt = select(PriceHistory).where(PriceHistory.product_id == product_id)
    if status_ok_only:
        stmt = stmt.where(PriceHistory.status == "ok")

    stmt = stmt.order_by(PriceHistory.checked_at.desc(), PriceHistory.id.desc()).limit(
        1
    )
    return session.scalar(stmt)


def get_last_n_prices(
    session: Session,
    product_id: int,
    n: int,
) -> list[PriceHistory]:
    """Get the N most recent price check records for a product (newest first)."""
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.checked_at.desc(), PriceHistory.id.desc())
        .limit(n)
    )
    return list(session.scalars(stmt).all())


def get_price_history(
    session: Session,
    product_id: int,
    limit: int = 50,
) -> list[PriceHistory]:
    """Get historical price records for a product up to limit (newest first)."""
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.checked_at.desc(), PriceHistory.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


# ============================================================================
# Alerts Data Access
# ============================================================================


def add_alert(
    session: Session,
    product_id: int,
    price: float | Decimal,
    reason: str,
) -> AlertSent:
    """Record an alert sent for a product.

    Args:
        session: Active database session.
        product_id: Target product ID.
        price: Price at the time the alert was triggered.
        reason: Alert reason ('price_drop', 'below_target', 'test').

    Returns:
        The created AlertSent record.
    """
    price_dec = Decimal(str(price)) if not isinstance(price, Decimal) else price
    alert = AlertSent(
        product_id=product_id,
        price=price_dec,
        reason=reason,
    )
    session.add(alert)
    session.flush()
    return alert


def get_last_alert(session: Session, product_id: int) -> AlertSent | None:
    """Get the most recent alert sent for a product."""
    stmt = (
        select(AlertSent)
        .where(AlertSent.product_id == product_id)
        .order_by(AlertSent.sent_at.desc(), AlertSent.id.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def get_alerts_in_last_hours(
    session: Session,
    product_id: int,
    hours: int = 24,
) -> list[AlertSent]:
    """Get all alerts dispatched for a product within the last N hours."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    stmt = (
        select(AlertSent)
        .where(
            AlertSent.product_id == product_id,
            AlertSent.sent_at >= since,
        )
        .order_by(AlertSent.sent_at.desc(), AlertSent.id.desc())
    )
    return list(session.scalars(stmt).all())
