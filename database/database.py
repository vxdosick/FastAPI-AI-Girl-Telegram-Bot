# Async PostgreSQL engine (asyncpg) + session factory — tuned for pooled connections (e.g. Neon).
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.config import DATABASE_URL, DB_MAX_OVERFLOW, DB_POOL_SIZE


class Base(DeclarativeBase):
    pass


if not DATABASE_URL or not str(DATABASE_URL).strip():
    raise RuntimeError(
        "DATABASE_URL is required, e.g. postgresql+asyncpg://user:pass@host/dbname"
    )

_url = str(DATABASE_URL).strip()

engine = create_async_engine(
    _url,
    pool_pre_ping=True,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    echo=False,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db_schema() -> None:
    import database.models  # noqa: F401 — register ORM mappers

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "image_generating INTEGER NOT NULL DEFAULT 3"
            )
        )


async def dispose_engine() -> None:
    await engine.dispose()
