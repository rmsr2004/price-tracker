"""Unit tests for CLI commands and entry point."""

import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tracker.__main__ import app, main
from tracker.config import get_settings
from tracker.exceptions import FetchError

runner = CliRunner()
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "html"


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear LRU cache before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_valid_env(monkeypatch: pytest.MonkeyPatch):
    """Set valid environment variables for CLI commands."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setenv("SMTP_USER", "smtp_user_test")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp_secret_token")
    monkeypatch.setenv("MAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("MAIL_TO", "recipient@example.com")


def test_cli_help_displays_app_name_and_subcommands():
    """Test that tracker --help displays app name and all subcommands with exit code 0."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Price Tracker" in result.output

    expected_commands = [
        "add",
        "list",
        "remove",
        "reactivate",
        "set-target",
        "check-url",
        "run",
        "send-test-email",
        "simulate",
        "status",
    ]
    for cmd in expected_commands:
        assert cmd in result.output, f"Command '{cmd}' not found in help output"


def test_cli_subcommand_help_works():
    """Test that tracker <subcommand> --help works for stub commands without requiring env vars."""
    result = runner.invoke(app, ["add", "--help"])
    assert result.exit_code == 0
    assert "Add a new product to track" in result.output


def test_cli_missing_env_vars_prints_clear_error(monkeypatch: pytest.MonkeyPatch):
    """Test that running without required env vars prints clear error and exits with code 1."""
    for key in [
        "DATABASE_URL",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "MAIL_FROM",
        "MAIL_TO",
    ]:
        monkeypatch.delenv(key, raising=False)

    result = runner.invoke(app, ["run"])
    assert result.exit_code == 1
    assert (
        "Configuration error: Missing required environment variable(s):"
        in result.output
    )
    assert "DATABASE_URL" in result.output
    assert "SMTP_HOST" in result.output
    assert "SMTP_USER" in result.output
    assert "SMTP_PASSWORD" in result.output
    assert "MAIL_FROM" in result.output
    assert "MAIL_TO" in result.output


def test_cli_invalid_config_type_error(monkeypatch: pytest.MonkeyPatch, mock_valid_env):
    """Test that configuration type error (non-missing) prints validation error message."""
    monkeypatch.setenv("SMTP_PORT", "invalid_non_integer")

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 1
    assert "Configuration error:" in result.output
    assert "SMTP_PORT" in result.output or "smtp_port" in result.output


def test_cli_no_args_without_env_vars_prints_clear_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that running tracker with no arguments without env vars exits with code 1 and error."""
    for key in [
        "DATABASE_URL",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "MAIL_FROM",
        "MAIL_TO",
    ]:
        monkeypatch.delenv(key, raising=False)

    result = runner.invoke(app, [])
    assert result.exit_code == 1
    assert (
        "Configuration error: Missing required environment variable(s):"
        in result.output
    )


def test_cli_no_args_with_valid_env_shows_help(mock_valid_env):
    """Test that running tracker with no arguments and valid env displays help."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Price Tracker" in result.output


def test_cli_check_url_success_jsonld(monkeypatch: pytest.MonkeyPatch):
    """Test check-url prints extracted info and exits 0 on success."""
    html_content = (FIXTURES_DIR / "product_jsonld.html").read_text(encoding="utf-8")
    monkeypatch.setattr("tracker.__main__.fetch", lambda url: html_content)

    result = runner.invoke(app, ["check-url", "https://example.com/headphones"])
    assert result.exit_code == 0
    assert "Sony WH-1000XM5" in result.output
    assert "199.00 EUR" in result.output
    assert "In Stock:  Yes" in result.output
    assert "Method:    json-ld" in result.output


def test_cli_check_url_success_with_css_selector(monkeypatch: pytest.MonkeyPatch):
    """Test check-url with custom CSS selector succeeds."""
    html_content = (FIXTURES_DIR / "product_css.html").read_text(encoding="utf-8")
    monkeypatch.setattr("tracker.__main__.fetch", lambda url: html_content)

    result = runner.invoke(
        app,
        ["check-url", "https://example.com/phone", "--css-selector", ".price"],
    )
    assert result.exit_code == 0
    assert "1299.00 EUR" in result.output
    assert "Method:    css" in result.output


def test_cli_check_url_no_price_suggests_css_selector(monkeypatch: pytest.MonkeyPatch):
    """Test check-url prints clear error and suggests --css-selector when no price found."""
    html_content = (FIXTURES_DIR / "product_no_price.html").read_text(encoding="utf-8")
    monkeypatch.setattr("tracker.__main__.fetch", lambda url: html_content)

    result = runner.invoke(app, ["check-url", "https://example.com/blog"])
    assert result.exit_code == 1
    assert "Could not extract price" in result.output
    assert "--css-selector" in result.output


def test_cli_check_url_fetch_error(monkeypatch: pytest.MonkeyPatch):
    """Test check-url handles FetchError cleanly."""

    def fail_fetch(url: str):
        raise FetchError(url=url, message="404 Not Found", status_code=404)

    monkeypatch.setattr("tracker.__main__.fetch", fail_fetch)

    result = runner.invoke(app, ["check-url", "https://example.com/notfound"])
    assert result.exit_code == 1
    assert "Fetch error:" in result.output


def test_main_function_entry_point(mock_valid_env):
    """Test main() executes without error."""
    original_argv = sys.argv
    try:
        sys.argv = ["tracker", "--help"]
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    finally:
        sys.argv = original_argv


def test_module_execution_via_python_m_tracker():
    """Test executing python -m tracker --help as a separate process."""
    result = subprocess.run(
        [sys.executable, "-m", "tracker", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Price Tracker" in result.stdout
