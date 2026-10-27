"""Async SQLAlchemy engine and session factory."""

import os
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def get_current_database_url() -> str:
    """Returns test database URL if testing mode is active, otherwise default dev database URL."""
    if settings.testing or os.getenv("TESTING", "").lower() in ("true", "1"):
        return settings.test_database_url
    return settings.database_url


engine = create_async_engine(get_current_database_url(), echo=settings.debug)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


from sqlalchemy.pool import NullPool


def set_database_url(url: Optional[str] = None):
    """Dynamically rebinds engine and async_session factory (for test isolation)."""
    global engine
    target_url = url or get_current_database_url()
    pool_kwargs = {"poolclass": NullPool} if (settings.testing or os.getenv("TESTING", "").lower() in ("true", "1")) else {}
    engine = create_async_engine(target_url, echo=settings.debug, **pool_kwargs)
    async_session.configure(bind=engine)
    return engine


async def get_db():
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        yield session
