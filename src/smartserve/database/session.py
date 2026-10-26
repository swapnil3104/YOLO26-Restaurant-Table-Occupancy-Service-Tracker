"""Database session management, connection pooling, and FastAPI dependency."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from smartserve.config import settings
from smartserve.database.base import Base


def get_sync_database_url(url: str | None = None) -> str:
    """Convert async db URL to sync driver URL for scripts and migrations."""
    db_url = url or settings.DATABASE_URL
    if db_url.startswith("sqlite+aiosqlite:///"):
        return db_url.replace("sqlite+aiosqlite:///", "sqlite:///")
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql://")
    return db_url


def create_app_async_engine(url: str | None = None) -> AsyncEngine:
    """Create async SQLAlchemy engine with connection tuning."""
    db_url = url or settings.DATABASE_URL
    kwargs: dict = {
        "echo": settings.DATABASE_ECHO,
        "future": True,
    }

    if "sqlite" in db_url:
        # SQLite specific configuration
        if ":memory:" in db_url:
            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_async_engine(db_url, **kwargs)

    # Enable SQLite foreign keys on connect
    if "sqlite" in db_url:

        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def create_app_sync_engine(url: str | None = None):
    """Create sync engine for Alembic and CLI commands."""
    db_url = get_sync_database_url(url)
    kwargs: dict = {
        "echo": settings.DATABASE_ECHO,
        "future": True,
    }
    if "sqlite" in db_url:
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in db_url:
            kwargs["poolclass"] = StaticPool

    engine = create_engine(db_url, **kwargs)

    if "sqlite" in db_url:

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


# Default global async engine and session factory
async_engine = create_app_async_engine()
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync session factory
sync_engine = create_app_sync_engine()
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session with automatic rollback on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for programmatic async session acquisition."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables in the configured database (useful for testing or initial dev)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """Drop all tables in the configured database."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
