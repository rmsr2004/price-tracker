"""Integration tests for the PostgreSQL repository."""

from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from docker.errors import DockerException
from sqlalchemy import create_engine, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.community.postgres import PostgresContainer

from alembic import command
from tracker.models import AlertSent, PriceHistory, Product
from tracker.repository import (
    add_alert,
    add_price_record,
    create_product,
    deactivate_product,
    delete_product,
    get_active_products,
    get_alerts_in_last_hours,
    get_last_n_prices,
    get_latest_price,
    reactivate_product,
)


@pytest.fixture(scope="module")
def session_factory():
    """Start PostgreSQL and apply all migrations for this test module."""
    postgres = PostgresContainer("postgres:16-alpine")
    try:
        postgres.start()
    except DockerException as error:
        pytest.skip(f"PostgreSQL container unavailable: {error}")

    database_url = postgres.get_connection_url()
    engine = create_engine(database_url)
    alembic_config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)
    try:
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()
        postgres.stop()


@pytest.fixture
def db_session(session_factory):
    """Provide an isolated session for each integration test."""
    with session_factory() as session:
        session.execute(delete(AlertSent))
        session.execute(delete(PriceHistory))
        session.execute(delete(Product))
        session.commit()
        yield session


def test_create_product_stores_all_fields(db_session: Session):
    product = create_product(
        db_session,
        "Keyboard",
        "Example Store",
        "https://example.test/keyboard",
        css_selector=".price",
        target_price=Decimal("49.99"),
        currency="EUR",
    )
    db_session.commit()

    loaded = db_session.get(Product, product.id)
    assert loaded is not None
    assert loaded.name == "Keyboard"
    assert loaded.css_selector == ".price"
    assert loaded.target_price == Decimal("49.99")
    assert loaded.currency == "EUR"
    assert loaded.active is True
    assert loaded.created_at is not None


def test_duplicate_url_is_rejected(db_session: Session):
    create_product(db_session, "First", "Store", "https://example.test/item")
    db_session.commit()
    with pytest.raises(IntegrityError):
        create_product(db_session, "Second", "Store", "https://example.test/item")


def test_price_history_queries_return_newest_records(db_session: Session):
    product = create_product(
        db_session, "Keyboard", "Store", "https://example.test/item"
    )
    db_session.commit()
    first = add_price_record(db_session, product.id, 100, True, "ok")
    second = add_price_record(db_session, product.id, 90, True, "ok")
    third = add_price_record(db_session, product.id, None, None, "parse_error")
    db_session.commit()

    assert get_latest_price(db_session, product.id) == third
    assert get_latest_price(db_session, product.id, status_ok_only=True) == second
    assert get_last_n_prices(db_session, product.id, 2) == [third, second]
    assert first.price == Decimal("100.00")


def test_delete_product_cascades_related_rows(db_session: Session):
    product = create_product(
        db_session, "Keyboard", "Store", "https://example.test/item"
    )
    db_session.commit()
    add_price_record(db_session, product.id, 100, True, "ok")
    add_alert(db_session, product.id, 90, "price_drop")
    db_session.commit()

    assert delete_product(db_session, product.id) is True
    db_session.commit()
    assert db_session.query(PriceHistory).count() == 0
    assert db_session.query(AlertSent).count() == 0


def test_deactivate_and_reactivate_product(db_session: Session):
    product = create_product(
        db_session, "Keyboard", "Store", "https://example.test/item"
    )
    db_session.commit()

    deactivate_product(db_session, product.id)
    db_session.commit()
    assert get_active_products(db_session) == []

    reactivate_product(db_session, product.id)
    db_session.commit()
    assert get_active_products(db_session) == [product]


def test_alert_queries_return_recent_alerts(db_session: Session):
    product = create_product(
        db_session, "Keyboard", "Store", "https://example.test/item"
    )
    db_session.commit()
    alert = add_alert(db_session, product.id, 90, "test")
    db_session.commit()

    assert get_alerts_in_last_hours(db_session, product.id) == [alert]
