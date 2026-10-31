"""Unit tests for the orchestration runner."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from tracker.exceptions import FetchError
from tracker.runner import (
    count_consecutive_failures,
    process_product,
    run,
)


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    """Provide the tuning value without requiring SMTP configuration."""
    monkeypatch.setattr(
        "tracker.runner.get_settings",
        lambda: SimpleNamespace(sanity_drop_threshold=0.30),
    )


def _product(product_id=1, url="https://store.example/item"):
    return SimpleNamespace(
        id=product_id,
        name="Item",
        store="store.example",
        url=url,
        css_selector=None,
        target_price=None,
        currency="EUR",
    )


def _extraction(price):
    return SimpleNamespace(price=price, in_stock=True, currency="EUR")


def test_count_consecutive_failures():
    assert count_consecutive_failures([]) == 0
    assert (
        count_consecutive_failures(
            [SimpleNamespace(status="ok"), SimpleNamespace(status="parse_error")]
        )
        == 0
    )
    assert (
        count_consecutive_failures(
            [
                SimpleNamespace(status="fetch_error"),
                SimpleNamespace(status="ok"),
            ]
        )
        == 1
    )
    assert (
        count_consecutive_failures(
            [
                SimpleNamespace(status="fetch_error"),
                SimpleNamespace(status="parse_error"),
                SimpleNamespace(status="ok"),
            ]
        )
        == 2
    )
    assert (
        count_consecutive_failures(
            [
                SimpleNamespace(status="fetch_error"),
                SimpleNamespace(status="parse_error"),
                SimpleNamespace(status="fetch_error"),
            ]
        )
        == 3
    )


def test_process_product_success_records_price(monkeypatch):
    session = SimpleNamespace()
    product = _product()
    monkeypatch.setattr("tracker.runner.fetch", lambda url: "<html>")
    monkeypatch.setattr(
        "tracker.runner.extract_price", lambda *args, **kwargs: _extraction(199)
    )
    monkeypatch.setattr(
        "tracker.runner.get_latest_price",
        lambda *args, **kwargs: SimpleNamespace(price=199),
    )
    monkeypatch.setattr("tracker.runner.get_alerts_in_last_hours", lambda *args: [])
    monkeypatch.setattr("tracker.runner.get_last_n_prices", lambda *args: [])
    monkeypatch.setattr("tracker.runner.add_price_record", lambda *args: None)
    record = []
    monkeypatch.setattr(
        "tracker.runner.add_price_record", lambda *args: record.append(args)
    )
    monkeypatch.setattr("tracker.runner.send_alert_email", pytest.fail)

    result = process_product(session, product)

    assert result.status == "ok"
    assert result.price == 199
    assert result.alerts_sent == []
    assert record[0][1:] == (1, 199, True, "ok")


def test_process_product_price_drop_sends_and_records_alert(monkeypatch):
    session = SimpleNamespace()
    product = _product()
    monkeypatch.setattr("tracker.runner.fetch", lambda url: "<html>")
    monkeypatch.setattr(
        "tracker.runner.extract_price", lambda *args, **kwargs: _extraction(179)
    )
    monkeypatch.setattr(
        "tracker.runner.get_latest_price",
        lambda *args, **kwargs: SimpleNamespace(price=199),
    )
    monkeypatch.setattr("tracker.runner.get_alerts_in_last_hours", lambda *args: [])
    monkeypatch.setattr("tracker.runner.get_last_n_prices", lambda *args: [])
    monkeypatch.setattr("tracker.runner.add_price_record", lambda *args: None)
    sent = []
    alerts = []
    monkeypatch.setattr(
        "tracker.runner.send_alert_email", lambda **kwargs: sent.append(kwargs)
    )
    monkeypatch.setattr("tracker.runner.add_alert", lambda *args: alerts.append(args))

    result = process_product(session, product)

    assert result.alerts_sent == ["price_drop"]
    assert sent[0]["current_price"] == 179
    assert alerts[0][1:] == (1, 179, "price_drop")


def test_process_product_fetch_error_records_failure(monkeypatch):
    session = SimpleNamespace()
    product = _product()
    monkeypatch.setattr(
        "tracker.runner.fetch",
        lambda url: (_ for _ in ()).throw(FetchError(url, "timeout")),
    )
    records = []
    monkeypatch.setattr(
        "tracker.runner.add_price_record", lambda *args: records.append(args)
    )
    monkeypatch.setattr("tracker.runner.get_last_n_prices", lambda *args: [])
    monkeypatch.setattr("tracker.runner.send_failure_alert_email", pytest.fail)

    result = process_product(session, product)

    assert result.status == "fetch_error"
    assert records[0][1:] == (1, None, None, "fetch_error")


def test_process_product_dry_run_does_not_write_or_send(monkeypatch):
    session = SimpleNamespace()
    product = _product()
    monkeypatch.setattr("tracker.runner.fetch", lambda url: "<html>")
    monkeypatch.setattr(
        "tracker.runner.extract_price", lambda *args, **kwargs: _extraction(179)
    )
    monkeypatch.setattr(
        "tracker.runner.get_latest_price",
        lambda *args, **kwargs: SimpleNamespace(price=199),
    )
    monkeypatch.setattr("tracker.runner.get_alerts_in_last_hours", lambda *args: [])
    monkeypatch.setattr("tracker.runner.get_last_n_prices", lambda *args: [])
    monkeypatch.setattr("tracker.runner.add_price_record", pytest.fail)
    monkeypatch.setattr("tracker.runner.send_alert_email", pytest.fail)

    result = process_product(session, product, dry_run=True)

    assert result.alerts_sent == ["price_drop"]


def test_run_throttles_requests_to_same_domain(monkeypatch):
    products = [_product(1), _product(2, "https://store.example/other")]
    session = SimpleNamespace()

    @contextmanager
    def fake_session():
        yield session

    monkeypatch.setattr("tracker.db.get_session", fake_session)
    monkeypatch.setattr("tracker.runner.get_active_products", lambda session: products)
    monkeypatch.setattr(
        "tracker.runner.process_product",
        lambda session, product, dry_run: SimpleNamespace(
            status="ok",
            alerts_sent=[],
            product_name=product.name,
            store=product.store,
            price=199,
            previous_price=None,
            error=None,
        ),
    )
    times = iter([0.0, 0.1, 0.2, 0.3])
    monkeypatch.setattr("tracker.runner.time.time", lambda: next(times))
    sleeps = []
    monkeypatch.setattr("tracker.runner.time.sleep", sleeps.append)

    result = run()

    assert result.total_products == 2
    assert sleeps == [1.9]
