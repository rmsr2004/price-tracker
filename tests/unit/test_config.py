"""Unit tests for configuration module."""

import pytest
from pydantic import ValidationError

from tracker.config import Settings, get_missing_settings_fields, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear LRU cache of get_settings before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch):
    """Test that Settings loads all required and optional fields from environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "smtp_user_test")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp_secret_token")
    monkeypatch.setenv("MAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("MAIL_TO", "recipient@example.com")
    monkeypatch.setenv("USER_AGENT", "CustomTracker/2.0")
    monkeypatch.setenv("FETCH_TIMEOUT", "25")
    monkeypatch.setenv("SANITY_DROP_THRESHOLD", "0.45")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://user:pass@localhost:5432/testdb"
    assert settings.smtp_host == "smtp-relay.brevo.com"
    assert settings.smtp_port == 587
    assert settings.smtp_user == "smtp_user_test"
    assert settings.smtp_password.get_secret_value() == "smtp_secret_token"
    assert settings.mail_from == "alerts@example.com"
    assert settings.mail_to == "recipient@example.com"
    assert settings.user_agent == "CustomTracker/2.0"
    assert settings.fetch_timeout == 25
    assert settings.sanity_drop_threshold == 0.45


def test_settings_default_values(monkeypatch: pytest.MonkeyPatch):
    """Test that default values are properly populated when optional variables are omitted."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setenv("SMTP_USER", "smtp_user_test")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp_secret_token")
    monkeypatch.setenv("MAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("MAIL_TO", "recipient@example.com")

    # Remove optional env vars if present
    monkeypatch.delenv("SMTP_PORT", raising=False)
    monkeypatch.delenv("USER_AGENT", raising=False)
    monkeypatch.delenv("FETCH_TIMEOUT", raising=False)
    monkeypatch.delenv("SANITY_DROP_THRESHOLD", raising=False)

    settings = Settings(_env_file=None)

    assert settings.smtp_port == 587
    assert "PriceTracker/1.0" in settings.user_agent
    assert settings.fetch_timeout == 15
    assert settings.sanity_drop_threshold == 0.30


def test_missing_required_env_vars_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that omitting required environment variables raises ValidationError."""
    # Ensure environment is clean
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

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    error = exc_info.value
    missing_fields = get_missing_settings_fields(error)

    assert "DATABASE_URL" in missing_fields
    assert "SMTP_HOST" in missing_fields
    assert "SMTP_USER" in missing_fields
    assert "SMTP_PASSWORD" in missing_fields
    assert "MAIL_FROM" in missing_fields
    assert "MAIL_TO" in missing_fields


def test_get_settings_caches_result(monkeypatch: pytest.MonkeyPatch):
    """Test that get_settings caches the returned Settings instance."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setenv("SMTP_USER", "smtp_user_test")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp_secret_token")
    monkeypatch.setenv("MAIL_FROM", "alerts@example.com")
    monkeypatch.setenv("MAIL_TO", "recipient@example.com")

    settings_1 = get_settings()
    settings_2 = get_settings()

    assert settings_1 is settings_2
