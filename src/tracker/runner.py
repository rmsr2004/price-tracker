"""Orchestration runner for a price tracking cycle."""

import time
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from tracker.alerts import evaluate_alerts
from tracker.config import get_settings
from tracker.exceptions import FetchError
from tracker.extractors import extract_price
from tracker.fetcher import fetch
from tracker.models import PriceHistory, Product
from tracker.notifier import send_alert_email, send_failure_alert_email
from tracker.repository import (
    add_alert,
    add_price_record,
    get_active_products,
    get_alerts_in_last_hours,
    get_last_n_prices,
    get_latest_price,
)


@dataclass
class ProductRunResult:
    """Outcome of checking one product."""

    product_id: int
    product_name: str
    store: str
    status: str
    price: float | None = None
    previous_price: float | None = None
    alerts_sent: list[str] | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Use an independent list for each result."""
        if self.alerts_sent is None:
            self.alerts_sent = []


@dataclass
class RunResult:
    """Summary of a complete tracking cycle."""

    total_products: int
    successful: int
    failed: int
    alerts_sent: int
    results: list[ProductRunResult]


def count_consecutive_failures(recent_records: list[PriceHistory]) -> int:
    """Count non-``ok`` records from a list ordered newest first."""
    failures = 0
    for record in recent_records:
        if record.status == "ok":
            break
        failures += 1
    return failures


def _result(
    product: Product,
    status: str,
    *,
    price: float | None = None,
    previous_price: float | None = None,
    alerts: list[str] | None = None,
    error: str | None = None,
) -> ProductRunResult:
    """Build a consistently shaped product result."""
    return ProductRunResult(
        product_id=product.id,
        product_name=product.name,
        store=product.store,
        status=status,
        price=price,
        previous_price=previous_price,
        alerts_sent=alerts or [],
        error=error,
    )


def _record_failure(
    session: Session,
    product: Product,
    status: str,
    error: str | None,
    dry_run: bool,
) -> ProductRunResult:
    """Record a failed check and warn once three failures are consecutive."""
    if not dry_run:
        add_price_record(session, product.id, None, None, status)
    failures = count_consecutive_failures(get_last_n_prices(session, product.id, 50))
    if dry_run:
        failures += 1
    if not dry_run and failures >= 3 and failures == 3:
        send_failure_alert_email(
            product.name,
            product.store,
            product.url,
            failures,
        )
    warning_sent = failures == 3
    return _result(
        product,
        status,
        alerts=["extraction_failing"] if warning_sent else [],
        error=error,
    )


def process_product(
    session: Session,
    product: Product,
    dry_run: bool = False,
) -> ProductRunResult:
    """Fetch, extract, persist, and evaluate one active product."""
    try:
        html = fetch(product.url)
    except FetchError as error:
        return _record_failure(session, product, "fetch_error", str(error), dry_run)

    extracted = extract_price(html, product.url, css_selector=product.css_selector)
    if extracted is None or extracted.price is None:
        return _record_failure(
            session,
            product,
            "parse_error",
            "Could not extract a price.",
            dry_run,
        )

    previous_record = get_latest_price(session, product.id, status_ok_only=True)
    previous_price = (
        float(previous_record.price)
        if previous_record and previous_record.price is not None
        else None
    )
    recent_alerts = get_alerts_in_last_hours(session, product.id)
    consecutive_failures = count_consecutive_failures(
        get_last_n_prices(session, product.id, 50)
    )
    decision = evaluate_alerts(
        current_price=extracted.price,
        previous_price=previous_price,
        target_price=(
            float(product.target_price) if product.target_price is not None else None
        ),
        recent_alerts=recent_alerts,
        consecutive_failures=consecutive_failures,
        sanity_threshold=get_settings().sanity_drop_threshold,
    )

    if not dry_run:
        add_price_record(
            session,
            product.id,
            extracted.price,
            extracted.in_stock,
            "ok",
        )

    if decision.reasons and not dry_run:
        send_alert_email(
            product_name=product.name,
            store=product.store,
            previous_price=previous_price or extracted.price,
            current_price=extracted.price,
            currency=product.currency,
            product_url=product.url,
            target_price=(
                float(product.target_price)
                if product.target_price is not None
                else None
            ),
            reasons=decision.reasons,
            is_suspicious=decision.is_suspicious,
        )
        for reason in decision.reasons:
            add_alert(session, product.id, extracted.price, reason)

    return _result(
        product,
        "ok",
        price=extracted.price,
        previous_price=previous_price,
        alerts=decision.reasons,
    )


def _print_result(
    result: ProductRunResult,
    index: int,
    total: int,
    dry_run: bool,
) -> None:
    """Print concise progress for one product."""
    print(f"[{index}/{total}] {result.product_name} ({result.store})")
    if result.status != "ok":
        print(f"      ✗ {result.status}: {result.error or 'unknown error'}")
        if dry_run:
            print(f"      [DRY RUN] Would record {result.status}.")
        return

    currency = "EUR"
    if result.price is not None:
        if result.previous_price is None:
            detail = "first price"
        elif result.price == result.previous_price:
            detail = "no change"
        else:
            difference = result.price - result.previous_price
            percentage = (
                difference / result.previous_price * 100 if result.previous_price else 0
            )
            detail = (
                f"was {result.previous_price:.2f} ({difference:+.2f} / "
                f"{percentage:+.1f}%)"
            )
        print(f"      Price: {result.price:.2f} {currency} ({detail})")
    if dry_run:
        action = "record price"
        if result.alerts_sent:
            action += f" and send alert: {', '.join(result.alerts_sent)}"
        print(f"      [DRY RUN] Would {action}.")
    elif result.alerts_sent:
        print(f"      Alert sent: {', '.join(result.alerts_sent)}")


def run(dry_run: bool = False) -> RunResult:
    """Process all active products, respecting same-domain rate limits."""
    from tracker.db import get_session

    with get_session() as session:
        products = get_active_products(session)
        if dry_run:
            print("DRY RUN — no changes will be saved, no emails sent.\n")
        print(f"Processing {len(products)} active products...\n")

        last_request_time: defaultdict[str, float] = defaultdict(float)
        results: list[ProductRunResult] = []
        for index, product in enumerate(products, start=1):
            domain = urlparse(product.url).netloc
            elapsed = time.time() - last_request_time[domain]
            if last_request_time[domain] and elapsed < 2.0:
                time.sleep(2.0 - elapsed)
            result = process_product(session, product, dry_run)
            last_request_time[domain] = time.time()
            results.append(result)
            _print_result(result, index, len(products), dry_run)

    successful = sum(result.status == "ok" for result in results)
    alerts = sum(len(result.alerts_sent or []) for result in results)
    label = "Alerts would be sent" if dry_run else "Alerts sent"
    print(
        f"\nDone. Checked: {len(results)} | OK: {successful} | "
        f"Failed: {len(results) - successful} | {label}: {alerts}"
    )
    return RunResult(
        total_products=len(results),
        successful=successful,
        failed=len(results) - successful,
        alerts_sent=alerts,
        results=results,
    )
