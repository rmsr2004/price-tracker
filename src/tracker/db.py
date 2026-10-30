"""Database engine and session management."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from tracker.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def normalize_db_url(url: str) -> str:
    """Normalize database connection URL for SQLAlchemy.

    Replaces legacy ``postgres://`` and psycopg3 URLs with the
    psycopg2 dialect declared by this project.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    return url


def get_engine(database_url: str | None = None, **kwargs: Any) -> Engine:
    """Get or create the global SQLAlchemy Engine.

    Args:
        database_url: Optional connection string override.
        **kwargs: Additional parameters passed to create_engine.

    Returns:
        SQLAlchemy Engine instance.
    """
    global _engine
    if database_url is not None:
        normalized_url = normalize_db_url(database_url)
        return create_engine(normalized_url, **kwargs)

    if _engine is None:
        settings = get_settings()
        normalized_url = normalize_db_url(settings.database_url)
        _engine = create_engine(
            normalized_url,
            pool_pre_ping=True,
            **kwargs,
        )
    return _engine


def get_session_factory(
    engine: Engine | None = None,
) -> sessionmaker[Session]:
    """Get or create the global sessionmaker factory."""
    global _session_factory
    if engine is not None:
        return sessionmaker(bind=engine, autoflush=False, autocommit=False)

    if _session_factory is None:
        active_engine = get_engine()
        _session_factory = sessionmaker(
            bind=active_engine,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


@contextmanager
def get_session(
    factory: sessionmaker[Session] | None = None,
) -> Generator[Session, None, None]:
    """Context manager providing a transactional SQLAlchemy Session.

    Commits automatically on normal exit, rolls back on exception,
    and always closes the session.

    Yields:
        Active SQLAlchemy Session.
    """
    session_maker = factory or get_session_factory()
    session: Session = session_maker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_db_connections() -> None:
    """Reset global engine and session factory (primarily for testing)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
