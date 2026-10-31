"""Email notification module via Brevo SMTP."""

import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime, make_msgid
from html import escape

from tracker.config import get_settings


def _send_message(message: MIMEMultipart) -> None:
    """Send a prepared message using the configured Brevo SMTP connection."""
    settings = get_settings()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        server.send_message(message)


def _new_message(subject: str) -> MIMEMultipart:
    """Create a multipart message with the standard sender headers."""
    settings = get_settings()
    message = MIMEMultipart("alternative")
    message["From"] = settings.mail_from
    message["To"] = settings.mail_to
    message["Subject"] = subject
    message["Date"] = format_datetime(datetime.now(UTC))
    message["Message-ID"] = make_msgid()
    return message


def send_alert_email(
    product_name: str,
    store: str,
    previous_price: float,
    current_price: float,
    currency: str,
    product_url: str,
    target_price: float | None,
    reasons: list[str],
    is_suspicious: bool,
    is_test: bool = False,
    checked_at: datetime | None = None,
) -> None:
    """Send a price alert email via Brevo SMTP."""
    difference = previous_price - current_price
    percentage = (difference / previous_price * 100) if previous_price else 0
    checked_at = checked_at or datetime.now(UTC)

    if "below_target" in reasons:
        subject = f"🎯 Target Reached: {product_name} — {current_price:.2f} {currency}"
    else:
        subject = f"Price Drop: {product_name} — {current_price:.2f} {currency}"
    if is_suspicious:
        subject = f"⚠️ [VERIFY] {subject}"
    if is_test:
        subject = f"[TEST] {subject}"

    target_text = (
        f"{target_price:.2f} {currency}" if target_price is not None else "Not set"
    )
    checked_text = format_datetime(checked_at)
    warning = (
        "WARNING: This price drop is unusually large (>70% off). "
        "Please verify the price manually — it may be a parsing error."
        if is_suspicious
        else ""
    )
    plain_body = (
        f"Product:        {product_name}\n"
        f"Store:          {store}\n"
        f"Previous Price: {previous_price:.2f} {currency}\n"
        f"Current Price:  {current_price:.2f} {currency}\n"
        f"Difference:     -{difference:.2f} {currency} (-{percentage:.2f}%)\n"
        f"Target Price:   {target_text}\n"
        f"Link:           {product_url}\n"
        f"Checked At:     {checked_text}\n\n"
        f"{warning}"
    )
    html_body = (
        f"<p><strong>Product:</strong> {escape(product_name)}<br>"
        f"<strong>Store:</strong> {escape(store)}<br>"
        f"<strong>Previous Price:</strong> {previous_price:.2f} {escape(currency)}<br>"
        f"<strong>Current Price:</strong> {current_price:.2f} {escape(currency)}<br>"
        f"<strong>Difference:</strong> -{difference:.2f} {escape(currency)} "
        f"(-{percentage:.2f}%)<br>"
        f"<strong>Target Price:</strong> {escape(target_text)}<br>"
        f'<strong>Link:</strong> <a href="{escape(product_url)}">{escape(product_url)}</a><br>'
        f"<strong>Checked At:</strong> {escape(checked_text)}</p>"
        f"{f'<p><strong>WARNING:</strong> {escape(warning)}</p>' if warning else ''}"
    )
    message = _new_message(subject)
    message.attach(MIMEText(plain_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))
    _send_message(message)


def send_test_email() -> None:
    """Send a simple email to verify SMTP configuration."""
    timestamp = format_datetime(datetime.now(UTC))
    message = _new_message("[TEST] Price Tracker — Email Configuration Test")
    body = (
        "This is a test email from your Price Tracker.\n"
        "If you received this, your email configuration is working correctly.\n\n"
        f"Sent at: {timestamp}"
    )
    message.attach(MIMEText(body, "plain", "utf-8"))
    message.attach(
        MIMEText(f"<p>{escape(body).replace(chr(10), '<br>')}</p>", "html", "utf-8")
    )
    _send_message(message)


def send_failure_alert_email(
    product_name: str,
    store: str,
    product_url: str,
    consecutive_failures: int,
) -> None:
    """Send an email warning about repeated extraction failures."""
    message = _new_message(f"Extraction Failure: {product_name}")
    body = (
        f"Product: {product_name}\nStore: {store}\nURL: {product_url}\n"
        f"Consecutive extraction failures: {consecutive_failures}\n"
    )
    message.attach(MIMEText(body, "plain", "utf-8"))
    message.attach(
        MIMEText(f"<p>{escape(body).replace(chr(10), '<br>')}</p>", "html", "utf-8")
    )
    _send_message(message)
