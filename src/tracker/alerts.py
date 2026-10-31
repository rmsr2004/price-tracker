"""Pure alert evaluation rules."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class AlertDecision:
    """The reasons an alert should be sent and any safety warning."""

    reasons: list[str]
    is_suspicious: bool
    message: str | None


def _alert_value(alert: dict[str, Any] | object, name: str) -> Any:
    """Read alert fields from either a mapping or an ORM-like object."""
    if isinstance(alert, dict):
        return alert.get(name)
    return getattr(alert, name, None)


def _as_aware(value: datetime) -> datetime:
    """Treat naive timestamps as UTC for predictable comparisons."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def evaluate_alerts(
    current_price: float | None,
    previous_price: float | None,
    target_price: float | None,
    recent_alerts: list[dict],
    consecutive_failures: int,
    sanity_threshold: float = 0.30,
    anti_spam_hours: int = 24,
    now: datetime | None = None,
) -> AlertDecision:
    """Evaluate price, target, anti-spam, failure, and sanity alert rules."""
    if current_price is None:
        reasons = ["extraction_failing"] if consecutive_failures >= 3 else []
        message = "Price extraction has failed repeatedly." if reasons else None
        return AlertDecision(reasons, False, message)

    reasons: list[str] = []
    if previous_price is not None and current_price < previous_price:
        reasons.append("price_drop")
    if target_price is not None and current_price <= target_price:
        reasons.append("below_target")

    current_time = _as_aware(now or datetime.now(UTC))
    cutoff = current_time - timedelta(hours=anti_spam_hours)
    for alert in recent_alerts:
        sent_at = _alert_value(alert, "sent_at")
        alert_price = _alert_value(alert, "price")
        if sent_at is None or alert_price is None:
            continue
        if _as_aware(sent_at) >= cutoff and float(alert_price) <= current_price:
            return AlertDecision([], False, "An alert was already sent recently.")

    is_suspicious = previous_price is not None and current_price < previous_price * (
        1 - sanity_threshold
    )
    if not reasons:
        return AlertDecision([], is_suspicious, None)

    message = "Price alert: " + ", ".join(reasons)
    if is_suspicious:
        message += ". Please verify this unusually large price drop."
    return AlertDecision(reasons, is_suspicious, message)
