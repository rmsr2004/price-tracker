"""SQLAlchemy 2.x data models for price tracker."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    desc,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy models."""


class Product(Base):
    """Tracked product definition."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    store: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    css_selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), default="EUR", server_default="EUR", nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships with cascade delete
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    alerts_sent: Mapped[list["AlertSent"]] = relationship(
        "AlertSent",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Product(id={self.id}, name={self.name!r}, store={self.store!r}, "
            f"active={self.active})>"
        )


class PriceHistory(Base):
    """Historical price checks for a product."""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    product: Mapped["Product"] = relationship("Product", back_populates="price_history")

    __table_args__ = (
        CheckConstraint(
            "status IN ('ok', 'fetch_error', 'parse_error')",
            name="ck_price_history_status",
        ),
        Index(
            "ix_price_history_product_id_checked_at_desc",
            "product_id",
            desc("checked_at"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PriceHistory(id={self.id}, product_id={self.product_id}, "
            f"price={self.price}, status={self.status!r}, checked_at={self.checked_at})>"
        )


class AlertSent(Base):
    """Log of alerts dispatched for products."""

    __tablename__ = "alerts_sent"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    product: Mapped["Product"] = relationship("Product", back_populates="alerts_sent")

    __table_args__ = (
        CheckConstraint(
            "reason IN ('price_drop', 'below_target', 'test')",
            name="ck_alerts_sent_reason",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AlertSent(id={self.id}, product_id={self.product_id}, "
            f"price={self.price}, reason={self.reason!r}, sent_at={self.sent_at})>"
        )
