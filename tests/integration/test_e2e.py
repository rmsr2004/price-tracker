"""End-to-end orchestration tests."""

from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from tracker.products import add_product, deactivate_product
from tracker.repository import (
    add_price_record,
    create_product,
    get_active_products,
    get_alerts_in_last_hours,
    get_price_history,
)
from tracker.runner import run

pytest_plugins = ("tests.integration.test_repository",)

FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "html" / "product_jsonld.html"
).read_text(encoding="utf-8")


@pytest.fixture
def runner_session(monkeypatch: pytest.MonkeyPatch, db_session: Session):
    """Make the process runner use the isolated integration-test session."""

    @contextmanager
    def session_context():
        yield db_session

    monkeypatch.setattr("tracker.db.get_session", session_context)
    monkeypatch.setattr(
        "tracker.runner.get_settings",
        lambda: type("Settings", (), {"sanity_drop_threshold": 0.30})(),
    )
    return db_session


def test_full_flow(runner_session, httpserver, monkeypatch):
    """Add a product, detect a price drop, then remove the product."""
    httpserver.expect_request("/item").respond_with_data(FIXTURE)
    url = httpserver.url_for("/item")
    product, _ = add_product(runner_session, url)
    runner_session.commit()

    first = run()
    assert first.successful == 1
    assert first.alerts_sent == 0

    changed = FIXTURE.replace("199,00", "179,00")
    httpserver.clear()
    httpserver.expect_request("/item").respond_with_data(changed)
    monkeypatch.setattr("tracker.runner.send_alert_email", lambda **kwargs: None)

    second = run()
    assert second.alerts_sent == 1
    assert len(get_price_history(runner_session, product.id)) == 3
    assert len(get_alerts_in_last_hours(runner_session, product.id)) == 1

    runner_session.delete(product)
    runner_session.commit()
    assert run().total_products == 0


def test_deactivated_product_is_skipped(runner_session, httpserver):
    """Inactive products are excluded from orchestration."""
    httpserver.expect_request("/item").respond_with_data(FIXTURE)
    product, _ = add_product(runner_session, httpserver.url_for("/item"))
    runner_session.commit()
    deactivate_product(runner_session, product.id)
    runner_session.commit()

    result = run()

    assert result.total_products == 0
    assert get_active_products(runner_session) == []


def test_three_failures_send_warning(runner_session, httpserver, monkeypatch):
    """Three consecutive failed checks send one extraction warning."""
    product = create_product(
        runner_session,
        "Item",
        "store",
        httpserver.url_for("/item"),
    )
    add_price_record(runner_session, product.id, 199, True, "ok")
    runner_session.commit()
    httpserver.expect_request("/item").respond_with_data("unavailable", status=503)
    warnings = []
    monkeypatch.setattr(
        "tracker.runner.send_failure_alert_email",
        lambda *args: warnings.append(args),
    )

    for _ in range(3):
        run()

    assert len(warnings) == 1
    assert warnings[0][0] == product.name
