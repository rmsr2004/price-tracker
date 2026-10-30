"""Unit tests for database URL handling."""

from tracker.db import normalize_db_url


def test_normalize_db_url_selects_project_postgres_driver():
    assert (
        normalize_db_url("postgres://user:pass@localhost/db")
        == "postgresql+psycopg2://user:pass@localhost/db"
    )
    assert (
        normalize_db_url("postgresql+psycopg://user:pass@localhost/db")
        == "postgresql+psycopg2://user:pass@localhost/db"
    )


def test_normalize_db_url_preserves_other_urls():
    assert normalize_db_url("sqlite:///tracker.db") == "sqlite:///tracker.db"
