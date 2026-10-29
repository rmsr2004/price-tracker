"""CLI entry point for price tracker."""

import typer
from pydantic import ValidationError

from tracker.config import Settings, get_missing_settings_fields, get_settings

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
    # If no subcommand was invoked and help was not requested,
    # validate settings and display help.
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
    typer.echo(f"Command 'add' is not implemented yet. URL: {url}")


@app.command(name="list")
def list_products(
    all_products: bool = typer.Option(
        False, "--all", "-a", help="Include inactive products"
    ),
) -> None:
    """List tracked products."""
    ensure_settings()
    typer.echo("Command 'list' is not implemented yet.")


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
    typer.echo(f"Command 'remove' is not implemented yet. Identifier: {identifier}")


@app.command(name="reactivate")
def reactivate_product(
    product_id: int = typer.Argument(..., help="Product ID to reactivate"),
) -> None:
    """Reactivate a previously deactivated product."""
    ensure_settings()
    typer.echo(f"Command 'reactivate' is not implemented yet. ID: {product_id}")


@app.command(name="set-target")
def set_target(
    product_id: int = typer.Argument(..., help="Product ID"),
    target_price: str = typer.Argument(
        ..., help="Target price (e.g. 199.99 or 'none')"
    ),
) -> None:
    """Set or remove target price for a product."""
    ensure_settings()
    typer.echo(
        f"Command 'set-target' is not implemented yet. ID: {product_id}, target: {target_price}"
    )


@app.command(name="check-url")
def check_url(
    url: str = typer.Argument(..., help="Product URL to test"),
    css_selector: str | None = typer.Option(
        None, "--css-selector", help="Optional CSS selector"
    ),
) -> None:
    """Check price extraction for a URL without saving to database."""
    ensure_settings()
    typer.echo(f"Command 'check-url' is not implemented yet. URL: {url}")


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
