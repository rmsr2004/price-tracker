"""Tests for SMTP notification formatting."""

from email import message_from_bytes
from email.header import decode_header, make_header
from unittest.mock import MagicMock

import pytest

from tracker.notifier import (
    send_alert_email,
    send_failure_alert_email,
    send_test_email,
)


@pytest.fixture
def smtp(monkeypatch):
    server = MagicMock()
    context = server.__enter__.return_value
    monkeypatch.setattr("tracker.notifier.smtplib.SMTP", MagicMock(return_value=server))
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "password")
    monkeypatch.setenv("MAIL_FROM", "from@example.com")
    monkeypatch.setenv("MAIL_TO", "to@example.com")
    from tracker.config import get_settings

    get_settings.cache_clear()
    yield context
    get_settings.cache_clear()


def _message(server):
    return message_from_bytes(server.send_message.call_args.args[0].as_bytes())


def _subject(message):
    return str(make_header(decode_header(message["Subject"])))


def test_send_alert_email_contains_price_details(smtp):
    send_alert_email(
        "Headphones",
        "Example",
        200,
        150,
        "EUR",
        "https://example.test/item",
        None,
        ["price_drop"],
        False,
    )
    message = _message(smtp)
    assert "Price Drop" in _subject(message)
    body = message.get_payload(0).get_payload(decode=True).decode()
    assert "200.00 EUR" in body
    assert "150.00 EUR" in body
    assert "-50.00 EUR" in body
    assert "https://example.test/item" in body
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("user", "password")
    assert message["From"] == "from@example.com"
    assert message["To"] == "to@example.com"


def test_send_alert_email_subject_variants(smtp):
    send_alert_email(
        "Item", "Store", 100, 50, "EUR", "https://x", 60, ["below_target"], False
    )
    assert "Target Reached" in _subject(_message(smtp))

    send_alert_email(
        "Item", "Store", 100, 20, "EUR", "https://x", None, ["price_drop"], True
    )
    assert "[VERIFY]" in _subject(_message(smtp))

    send_alert_email(
        "Item", "Store", 100, 50, "EUR", "https://x", None, ["price_drop"], False, True
    )
    assert "[TEST]" in _subject(_message(smtp))


def test_other_notification_types(smtp):
    send_test_email()
    assert "Email Configuration Test" in _subject(_message(smtp))

    send_failure_alert_email("Item", "Store", "https://x", 3)
    message = _message(smtp)
    assert "Extraction Failure" in _subject(message)
    body = message.get_payload(0).get_payload(decode=True).decode()
    assert "Item" in body
    assert "3" in body
