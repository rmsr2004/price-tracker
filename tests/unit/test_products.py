"""Unit tests for product-management business logic."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tracker.exceptions import (
    DuplicateProductError,
    NoPriceFoundError,
    ProductNotFoundError,
)
from tracker.extractors import ExtractionResult
from tracker.products import (
    add_product,
    list_products,
    remove_product,
    set_target_price,
)


def extraction_result(price=99.0):
    return ExtractionResult(price, "EUR", "Headphones", True, "json-ld")


def test_add_product_persists_product_and_first_price(monkeypatch):
    session = Mock()
    product = SimpleNamespace(id=1)
    monkeypatch.setattr("tracker.products.fetch", Mock(return_value="<html>"))
    monkeypatch.setattr(
        "tracker.products.extract_price", Mock(return_value=extraction_result())
    )
    repository = Mock()
    repository.get_product_by_url.return_value = None
    repository.create_product.return_value = product
    monkeypatch.setattr("tracker.products.repository", repository)

    saved, result = add_product(session, "HTTPS://WWW.Example.test/item?utm_source=x")

    assert saved is product
    assert result.price == 99.0
    assert repository.create_product.call_args.kwargs["url"] == (
        "https://example.test/item"
    )
    repository.add_price_record.assert_called_once_with(
        session, 1, price=99.0, in_stock=True, status="ok"
    )


def test_add_product_rejects_duplicate_and_missing_price(monkeypatch):
    session = Mock()
    repository = Mock()
    repository.get_product_by_url.return_value = SimpleNamespace(id=1)
    monkeypatch.setattr("tracker.products.repository", repository)
    with pytest.raises(DuplicateProductError):
        add_product(session, "https://example.test/item")

    repository.get_product_by_url.return_value = None
    monkeypatch.setattr("tracker.products.fetch", Mock(return_value="<html>"))
    monkeypatch.setattr("tracker.products.extract_price", Mock(return_value=None))
    with pytest.raises(NoPriceFoundError, match="--css-selector"):
        add_product(session, "https://example.test/item")


def test_list_products_reports_failures():
    session = Mock()
    product = SimpleNamespace(
        id=1,
        name="Headphones",
        store="example.test",
        url="https://example.test/item",
        target_price=None,
        active=True,
    )
    repository = Mock()
    repository.get_active_products.return_value = [product]
    repository.get_latest_price.side_effect = [
        SimpleNamespace(price=99, checked_at=None),
        SimpleNamespace(price=99),
    ]
    repository.get_last_n_prices.return_value = [
        SimpleNamespace(status="parse_error"),
        SimpleNamespace(status="fetch_error"),
    ]
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("tracker.products.repository", repository)
    try:
        listed = list_products(session)
    finally:
        monkeypatch.undo()
    assert listed[0]["status"] == "failing (2)"
    assert listed[0]["price"] == 99


def test_remove_and_set_target_raise_for_missing_products(monkeypatch):
    session = Mock()
    repository = Mock()
    repository.get_product_by_id.return_value = None
    monkeypatch.setattr("tracker.products.repository", repository)
    with pytest.raises(ProductNotFoundError):
        remove_product(session, 42)
    with pytest.raises(ProductNotFoundError):
        set_target_price(session, 42, 10)
