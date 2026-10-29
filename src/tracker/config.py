"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and/or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        ...,
        description="PostgreSQL connection string (Supabase)",
    )

    # Email (Brevo SMTP)
    smtp_host: str = Field(
        ...,
        description="Brevo SMTP host server",
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP port (defaults to 587 for STARTTLS)",
    )
    smtp_user: str = Field(
        ...,
        description="SMTP username / API key",
    )
    smtp_password: SecretStr = Field(
        ...,
        description="SMTP password / secret key",
    )
    mail_from: str = Field(
        ...,
        description="Sender email address",
    )
    mail_to: str = Field(
        ...,
        description="Recipient email address",
    )

    # Scraper & Alert Tuning
    user_agent: str = Field(
        default="PriceTracker/1.0 (+https://github.com/<user>/price-tracker)",
        description="HTTP User-Agent header for fetching pages",
    )
    fetch_timeout: int = Field(
        default=15,
        description="HTTP request timeout in seconds",
    )
    sanity_drop_threshold: float = Field(
        default=0.30,
        description="Price drop threshold fraction to flag suspicious drops (e.g. 0.30 for 30%)",
    )


def get_missing_settings_fields(error: ValidationError) -> list[str]:
    """Extract human-readable environment variable names for missing required settings.

    Args:
        error: The ValidationError raised by Pydantic.

    Returns:
        A sorted list of missing environment variable names in uppercase.
    """
    missing_fields: set[str] = set()
    for err in error.errors():
        if err.get("type") == "missing":
            loc = err.get("loc", ())
            if loc:
                missing_fields.add(str(loc[0]).upper())
    return sorted(missing_fields)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings.

    Raises:
        ValidationError: When required environment variables or configuration values are missing.
    """
    return Settings()
