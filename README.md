# Price Tracker

> Personal price tracker that monitors product prices and sends email alerts when prices drop.

⚠️ **Status:** Work in Progress (Phase 1 — Skeleton and Configuration complete).

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package and environment manager

## Installation

Clone the repository and install dependencies with `uv`:

```bash
uv sync
```

## Configuration

Copy the example environment configuration file and provide your own values:

```bash
cp .env.example .env
```

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string (e.g. Supabase connection pooler or direct connection).
- `SMTP_HOST`: Brevo SMTP server (`smtp-relay.brevo.com`).
- `SMTP_PORT`: SMTP port (`587`).
- `SMTP_USER`: Brevo SMTP login username.
- `SMTP_PASSWORD`: Brevo SMTP password / master key.
- `MAIL_FROM`: Sender email address (configured with SPF/DKIM).
- `MAIL_TO`: Recipient email address for price alerts.

Optional variables:
- `USER_AGENT`: Custom HTTP User-Agent header for price fetching.
- `FETCH_TIMEOUT`: HTTP request timeout in seconds (default: 15).
- `SANITY_DROP_THRESHOLD`: Price drop ratio threshold to flag suspicious drops (default: 0.30 for 30%).

## Usage

Display the command line help and available subcommands:

```bash
uv run python -m tracker --help
```

Available subcommands (to be implemented across project phases):
- `add`: Add a new product URL to track.
- `list`: List all currently tracked products.
- `remove`: Remove or deactivate a tracked product.
- `reactivate`: Reactivate a previously deactivated product.
- `set-target`: Set or clear target price for alerts.
- `check-url`: Test price extraction for a URL without saving.
- `run`: Run price check cycle for all active products.
- `send-test-email`: Verify SMTP configuration by sending a test email.
- `simulate`: Simulate a price change and test notifications.
- `status`: Show status overview of tracked products.

## Development

Run tests and linter:

```bash
uv run pytest
uv run ruff check src/ tests/
```
