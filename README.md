# Price Tracker

Personal price tracker that monitors product prices and sends email alerts when
prices drop. It runs automatically every three hours through GitHub Actions.

## Features

- Extracts prices from JSON-LD, meta tags, or custom CSS selectors.
- Sends alerts for price drops and reached target prices.
- Prevents duplicate alerts for the same or lower price within 24 hours.
- Flags unusually large price changes for manual verification.
- Warns about repeated extraction failures.
- Runs without a dedicated server: each scheduled job checks prices and exits.

## Architecture

- **Execution:** GitHub Actions, scheduled every three hours.
- **Database:** Supabase PostgreSQL.
- **Email:** Brevo SMTP.
- **Application:** Python 3.12, SQLAlchemy, Alembic, and `uv`.

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A [Supabase](https://supabase.com/) PostgreSQL project
- A [Brevo](https://www.brevo.com/) SMTP account with a verified sender

### Local installation

```bash
git clone https://github.com/rmsr2004/price-tracker.git
cd price-tracker
uv sync
cp .env.example .env
```

Set the required values in `.env`, then apply the database schema:

```bash
uv run alembic upgrade head
```

### Configuration

| Variable | Required | Description |
|---|---:|---|
| `DATABASE_URL` | Yes | Supabase PostgreSQL connection string |
| `SMTP_HOST` | Yes | Brevo SMTP host, usually `smtp-relay.brevo.com` |
| `SMTP_PORT` | Yes | SMTP port, usually `587` |
| `SMTP_USER` | Yes | Brevo SMTP username |
| `SMTP_PASSWORD` | Yes | Brevo SMTP password or API key |
| `MAIL_FROM` | Yes | Verified sender address |
| `MAIL_TO` | Yes | Alert recipient address |
| `USER_AGENT` | No | HTTP user agent |
| `FETCH_TIMEOUT` | No | Fetch timeout in seconds, default `15` |
| `SANITY_DROP_THRESHOLD` | No | Suspicious-drop threshold, default `0.30` |

For Supabase, use the direct connection or pooler connection supported by your
network. The pooler commonly uses port `6543`; the direct connection commonly
uses port `5432`.

## Managing products

```bash
# Add a product
uv run python -m tracker add "https://example.com/product"

# Add a target price or custom CSS selector
uv run python -m tracker add "https://example.com/product" --target 250.00
uv run python -m tracker add "https://example.com/product" --css-selector ".price"

# List, update, deactivate, reactivate, or remove products
uv run python -m tracker list
uv run python -m tracker set-target 1 250.00
uv run python -m tracker set-target 1 none
uv run python -m tracker remove 1 --deactivate
uv run python -m tracker reactivate 1
uv run python -m tracker remove 1
```

## Checking and notifications

```bash
# Test extraction without saving anything
uv run python -m tracker check-url "https://example.com/product"

# Verify SMTP configuration
uv run python -m tracker send-test-email

# Send a real test-mode alert for a simulated price
uv run python -m tracker simulate --product-id 1 --price 150.00

# Run checks without database writes or emails
uv run python -m tracker run --dry-run

# Run a normal price check cycle or inspect current state
uv run python -m tracker run
uv run python -m tracker status
```

## GitHub Actions deployment

The repository includes three workflows:

- `CI` runs linting and unit/integration tests on pushes to `main` and pull
  requests.
- `Track Prices` runs every three hours at `0 */3 * * *` and supports manual
  dry runs.
- `Keepalive` updates `.keepalive` monthly so public-repository scheduled
  workflows continue receiving repository activity.

Add these seven repository secrets under **Settings → Secrets and variables →
Actions → Repository secrets**:

| Secret | Description |
|---|---|
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `SMTP_HOST` | Brevo SMTP server |
| `SMTP_PORT` | Brevo SMTP port |
| `SMTP_USER` | Brevo SMTP username |
| `SMTP_PASSWORD` | Brevo SMTP password or API key |
| `MAIL_FROM` | Verified sender address |
| `MAIL_TO` | Alert recipient address |

After adding the secrets:

1. Run `CI` from a pull request or push.
2. Add the first product locally or through a controlled environment.
3. Use **Actions → Track Prices → Run workflow** with `dry_run=true`.
4. Run without dry-run and verify price history and email delivery.

Never commit `.env`, credentials, or secret values.

## Development

```bash
uv run ruff check src/ tests/
uv run pytest tests/ -v
uv run pytest tests/unit/test_runner.py -v
```

## License

MIT
