"""Tests for pure alert evaluation."""

from datetime import UTC, datetime, timedelta

import pytest

from tracker.alerts import evaluate_alerts


@pytest.mark.parametrize(
    ("current", "previous", "target", "alerts", "failures", "reasons", "suspicious"),
    [
        (179, 199, None, [], 0, ["price_drop"], False),
        (199, 199, None, [], 0, [], False),
        (219, 199, None, [], 0, [], False),
        (179, 199, 180, [], 0, ["price_drop", "below_target"], False),
        (185, 199, 180, [], 0, ["price_drop"], False),
        (179, 199, None, [{"price": 179, "sent_at": "ignored"}], 0, [], False),
        (
            169,
            199,
            None,
            [{"price": 179, "sent_at": "ignored"}],
            0,
            ["price_drop"],
            False,
        ),
        (None, 199, None, [], 0, [], False),
        (None, 199, None, [], 3, ["extraction_failing"], False),
        (None, 199, None, [], 2, [], False),
        (50, 199, None, [], 0, ["price_drop"], True),
        (60, 199, None, [], 0, ["price_drop"], True),
        (140, 199, None, [], 0, ["price_drop"], False),
        (0, 199, None, [], 0, ["price_drop"], True),
    ],
)
def test_evaluate_alerts(
    current, previous, target, alerts, failures, reasons, suspicious
):
    """Evaluate the alert decision table."""
    now = datetime.now(UTC)
    if alerts:
        alerts[0]["sent_at"] = now - timedelta(hours=1)
    decision = evaluate_alerts(
        current,
        previous,
        target,
        alerts,
        failures,
        now=now,
    )
    assert decision.reasons == reasons
    assert decision.is_suspicious is suspicious


def test_alert_outside_anti_spam_window_is_not_suppressed():
    now = datetime.now(UTC)
    decision = evaluate_alerts(
        179,
        199,
        None,
        [{"price": 179, "sent_at": now - timedelta(hours=25)}],
        0,
        now=now,
    )
    assert decision.reasons == ["price_drop"]
