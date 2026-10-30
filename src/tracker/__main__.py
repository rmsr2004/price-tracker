"""CLI entry point for price tracker."""

import typer
from pydantic import ValidationError

from tracker.config import Settings, get_missing_settings_fields, get_settings
from tracker.db import get_session
from tracker.exceptions import (
    DuplicateProductError,
    FetchError,
    NoPriceFoundError,
    ProductNotFoundError,
)
from tracker.extractors import extract_price
from tracker.fetcher import fetch
from tracker.products import (
    add_product as add_product_logic,
)
from tracker.products import (
    deactivate_product as deactivate_product_logic,
)
from tracker.products import (
    list_products as list_products_logic,
)
from tracker.products import (
    preview_remove_product,
    set_target_price,
)
from tracker.products import (
    reactivate_product as reactivate_product_logic,
)
from tracker.products import (
    remove_product as remove_product_logic,
)

app = typer.Typer(
    name="tracker",
    help="Price Tracker — Personal price tracking and alert system.",
    no_args_is_help=False,
)


def ensure_settings() -> Settings:
    """Ensure that required configuration is present and valid.

    Returns:
        Settings: The validated application settings.

    Raises:
        typer.Exit: Exits with code 1 if configuration is missing or invalid.
    """
    try:
        return get_settings()
    except ValidationError as error:
        missing = get_missing_settings_fields(error)
        if missing:
            typer.echo(
                "Configuration error: Missing required environment variable(s):\n"
                + "\n".join(f"  - {var}" for var in missing),
                err=True,
            )
            typer.echo(
                "\nPlease set them in your environment or in a .env file (see .env.example).",
                err=True,
            )
        else:
            typer.echo(f"Configuration error:\n{error}", err=True)
        raise typer.Exit(code=1) from error


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Global callback for tracker CLI."""
    if ctx.invoked_subcommand is None:
        ensure_settings()
        typer.echo(ctx.get_help())


@app.command(name="add")
def add_product(
    url: str = typer.Argument(..., help="Product URL to track"),
    target: float | None = typer.Option(
        None, "--target", help="Target price for alert"
    ),
    css_selector: str | None = typer.Option(
        None, "--css-selector", help="Optional CSS selector for price"
    ),
    name: str | None = typer.Option(
        None, "--name", help="Custom product name override"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip interactive confirmation"
    ),
) -> None:
    """Add a new product to track."""
    ensure_settings()
    try:
        with get_session() as session:
            product, result = add_product_logic(
                session, url, target, css_selector, name
            )
            _print_extraction(result, product.name)
            if not yes and not typer.confirm("Add this product?", default=False):
                session.rollback()
                typer.echo("Cancelled.")
                return
            typer.echo(f"Product added (ID: {product.id})")
    except (DuplicateProductError, NoPriceFoundError, FetchError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error


@app.command(name="list")
def list_products(
    all_products: bool = typer.Option(
        False, "--all", "-a", help="Include inactive products"
    ),
) -> None:
    """List tracked products."""
    ensure_settings()
    with get_session() as session:
        products = list_products_logic(session, include_inactive=all_products)
    if not products:
        typer.echo("No products being tracked.")
        return
    typer.echo("ID  Name  Store  Price  Target  Last Check  Status")
    for product in products:
        typer.echo(
            f"{product['id']}  {product['name']}  {product['store']}  "
            f"{_format_price(product['price'])}  "
            f"{_format_price(product['target_price'])}  "
            f"{_format_datetime(product['last_checked'])}  {product['status']}"
        )


@app.command(name="remove")
def remove_product(
    identifier: str = typer.Argument(..., help="Product ID or URL to remove"),
    deactivate: bool = typer.Option(
        False, "--deactivate", help="Deactivate instead of deleting"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip interactive confirmation"
    ),
) -> None:
    """Remove or deactivate a tracked product."""
    ensure_settings()
    try:
        with get_session() as session:
            product = _get_product_for_cli(session, identifier)
            if deactivate:
                typer.echo(
                    f"Product: {product.name} ({product.store})\n"
                    "This will deactivate the product. History will be preserved."
                )
                if not yes and not typer.confirm("Proceed?", default=False):
                    typer.echo("Cancelled.")
                    return
                if not product.active:
                    typer.echo(f"Product already inactive (ID: {product.id})")
                else:
                    updated = deactivate_product_logic(session, identifier)
                    typer.echo(f"Product deactivated (ID: {updated.id})")
                return

            details = preview_remove_product(session, identifier)
            typer.echo(
                f"Product: {details['name']} ({details['store']})\n"
                "This will permanently delete the product and:\n"
                f"  - {details['price_history_count']} price history records\n"
                f"  - {details['alerts_count']} alert records"
            )
            if not yes and not typer.confirm("Proceed?", default=False):
                typer.echo("Cancelled.")
                return
            removed = remove_product_logic(session, identifier)
            typer.echo(f"Product removed (ID: {removed['id']})")
    except ProductNotFoundError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error


@app.command(name="reactivate")
def reactivate_product(
    product_id: int = typer.Argument(..., help="Product ID to reactivate"),
) -> None:
    """Reactivate a previously deactivated product."""
    ensure_settings()
    try:
        with get_session() as session:
            current = _get_product_for_cli(session, product_id)
            was_active = current.active
            product = reactivate_product_logic(session, product_id)
            if was_active:
                typer.echo(f"Product already active (ID: {product.id})")
            else:
                typer.echo(f"Product reactivated (ID: {product.id})")
    except ProductNotFoundError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error


@app.command(name="set-target")
def set_target(
    product_id: int = typer.Argument(..., help="Product ID"),
    target_price: str = typer.Argument(
        ..., help="Target price (e.g. 199.99 or 'none')"
    ),
) -> None:
    """Set or remove target price for a product."""
    ensure_settings()
    clear_values = {"none", "clear", "remove"}
    try:
        price = None if target_price.lower() in clear_values else float(target_price)
    except ValueError as error:
        typer.echo("Target price must be a number or 'none'.", err=True)
        raise typer.Exit(code=1) from error
    try:
        with get_session() as session:
            product = set_target_price(session, product_id, price)
            if price is None:
                typer.echo(f'Target price for "{product.name}" removed.')
            else:
                typer.echo(
                    f'Target price for "{product.name}" set to '
                    f"{price:.2f} {product.currency}."
                )
    except ProductNotFoundError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error


@app.command(name="check-url")
def check_url(
    url: str = typer.Argument(..., help="Product URL to test"),
    css_selector: str | None = typer.Option(
        None, "--css-selector", help="Optional CSS selector"
    ),
) -> None:
    """Check price extraction for a URL without saving to database."""
    try:
        html = fetch(url)
    except FetchError as err:
        typer.echo(f"Fetch error: {err}", err=True)
        raise typer.Exit(code=1) from err

    result = extract_price(html, url, css_selector=css_selector)
    if result is None or result.price is None:
        typer.echo(f"Could not extract price from URL: {url}", err=True)
        typer.echo(
            "The website does not expose price data via JSON-LD or meta tags.",
            err=True,
        )
        typer.echo(
            'Try providing a custom CSS selector using --css-selector (e.g. --css-selector ".price").',
            err=True,
        )
        raise typer.Exit(code=1)

    in_stock_str = "Unknown"
    if result.in_stock is True:
        in_stock_str = "Yes"
    elif result.in_stock is False:
        in_stock_str = "No"

    typer.echo(f"URL:       {url}")
    typer.echo(f"Name:      {result.name or 'Unknown'}")
    typer.echo(f"Price:     {result.price:.2f} {result.currency}")
    typer.echo(f"In Stock:  {in_stock_str}")
    typer.echo(f"Method:    {result.method}")


def _format_price(value: object) -> str:
    """Format optional monetary values for CLI output."""
    return "—" if value is None else f"{float(value):.2f}"


def _format_datetime(value: object) -> str:
    """Format optional timestamps for CLI output."""
    return "—" if value is None else value.strftime("%Y-%m-%d %H:%M")


def _print_extraction(result: object, product_name: str | None = None) -> None:
    """Display the extraction preview shown before add confirmation."""
    in_stock = getattr(result, "in_stock", None)
    stock_text = "Yes" if in_stock is True else "No" if in_stock is False else "Unknown"
    typer.echo(
        "Found product:\n"
        f"  Name:     {product_name or getattr(result, 'name', None) or 'Unknown'}\n"
        f"  Price:    {getattr(result, 'price', 0):.2f} "
        f"{getattr(result, 'currency', 'EUR')}\n"
        f"  In Stock: {stock_text}\n"
        f"  Method:   {getattr(result, 'method', 'unknown')}"
    )


def _get_product_for_cli(session, identifier: str):
    """Resolve a product for confirmation without changing business logic."""
    from tracker.products import _find_product

    product = _find_product(session, identifier)
    if product is None:
        raise ProductNotFoundError("Product not found")
    return product


@app.command(name="run")
def run_tracker(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Run checks without saving or sending emails"
    ),
) -> None:
    """Run price check cycle for all active products."""
    ensure_settings()
    typer.echo(f"Command 'run' is not implemented yet. Dry run: {dry_run}")


@app.command(name="send-test-email")
def send_test_email() -> None:
    """Send a test email via Brevo SMTP to verify email configuration."""
    ensure_settings()
    typer.echo("Command 'send-test-email' is not implemented yet.")


@app.command(name="simulate")
def simulate_price(
    product_id: int = typer.Option(..., "--product-id", help="Product ID to simulate"),
    price: float = typer.Option(..., "--price", help="Simulated price"),
) -> None:
    """Simulate a price change and trigger test notification."""
    ensure_settings()
    typer.echo(
        f"Command 'simulate' is not implemented yet. Product ID: {product_id}, Price: {price}"
    )


@app.command(name="status")
def status() -> None:
    """Show status of tracked products and recent checks."""
    ensure_settings()
    typer.echo("Command 'status' is not implemented yet.")


def main() -> None:
    """Main application entry point."""
    app()


if __name__ == "__main__":
    main()
