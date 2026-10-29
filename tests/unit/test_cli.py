"""Unit tests for CLI commands and entry point."""

import subprocess
import sys

import pytest
from typer.testing import CliRunner

from tracker.__main__ import app, main
from tracker.config import get_settings

runner = CliRunner()


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
    assert "Configuration error: Missing required environment variable(s):" in result.output
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


def test_cli_no_args_without_env_vars_prints_clear_error(monkeypatch: pytest.MonkeyPatch):
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
    assert "Configuration error: Missing required environment variable(s):" in result.output


def test_cli_no_args_with_valid_env_shows_help(mock_valid_env):
    """Test that running tracker with no arguments and valid env displays help."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Price Tracker" in result.output


@pytest.mark.parametrize(
    ("args", "expected_output"),
    [
        (["add", "https://example.com/p"], "Command 'add' is not implemented yet."),
        (["list"], "Command 'list' is not implemented yet."),
        (["remove", "1"], "Command 'remove' is not implemented yet."),
        (["reactivate", "1"], "Command 'reactivate' is not implemented yet."),
        (["set-target", "1", "100.0"], "Command 'set-target' is not implemented yet."),
        (["check-url", "https://example.com/p"], "Command 'check-url' is not implemented yet."),
        (["run", "--dry-run"], "Command 'run' is not implemented yet."),
        (["send-test-email"], "Command 'send-test-email' is not implemented yet."),
        (["simulate", "--product-id", "1", "--price", "99.99"], "Command 'simulate' is not implemented yet."),
        (["status"], "Command 'status' is not implemented yet."),
    ],
)
def test_all_subcommands_execute_stubs_with_valid_env(mock_valid_env, args, expected_output):
    """Test all stub commands execute and print placeholder messages."""
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    assert expected_output in result.output


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
