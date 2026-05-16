"""Shared fixtures.

We use SQLite (`aiosqlite`) for ergonomics + speed. To keep Postgres-only
column types portable, we monkey-patch the SQLAlchemy types **before**
importing the models:

- `JSONB` → `JSON`
- `ARRAY(String)` → JSON list
- `UUID` → 36-char string

This keeps production DDL (`Postgres`) untouched while letting tests run
fast and infrastructure-free. For real Postgres integration coverage, set
`TEST_DATABASE_URL=postgresql+asyncpg://...` and the fixture honours it.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"),
)
os.environ.setdefault("MUREKA_API_KEY", "mk_test_dummy")
os.environ.setdefault("JWT_SIGNING_KEY", "test-secret")
os.environ.setdefault("MODERATION_ENABLED", "false")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")


# --- monkeypatch postgres-only types for SQLite ---
def _patch_postgres_types_for_sqlite() -> None:
    if not os.environ["DATABASE_URL"].startswith("sqlite"):
        return

    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql as pg
    from sqlalchemy.dialects.postgresql import JSONB, UUID

    # JSONB → JSON
    class _SQLiteJSONB(sa.JSON):
        cache_ok = True

        def __init__(self, *a, **kw):
            kw.pop("astext_type", None)
            super().__init__()

    pg.JSONB = _SQLiteJSONB  # type: ignore[assignment]

    # ARRAY → JSON
    class _SQLiteARRAY(sa.JSON):
        cache_ok = True

        def __init__(self, item_type=None, *a, **kw):
            super().__init__()

    pg.ARRAY = _SQLiteARRAY  # type: ignore[assignment]

    # UUID → CHAR(36) string with bind/result converters
    class _StringUUID(sa.types.TypeDecorator):
        impl = sa.String(36)
        cache_ok = True

        def __init__(self, *a, as_uuid: bool = True, **kw):
            self.as_uuid = as_uuid
            super().__init__()

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            return str(value)

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            if self.as_uuid:
                return uuid.UUID(value)
            return value

    pg.UUID = _StringUUID  # type: ignore[assignment]
    # Some imports come from sqlalchemy.dialects.postgresql directly; rebind:
    JSONB.__init__ = _SQLiteJSONB.__init__  # type: ignore[assignment]


_patch_postgres_types_for_sqlite()


# Now safe to import app / models
from app import db as app_db  # noqa: E402
from app.deps import get_current_user  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, User  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    """Per-test in-memory engine — fully isolated."""
    from sqlalchemy.ext.asyncio import create_async_engine

    url = os.environ["DATABASE_URL"]
    eng = create_async_engine(url, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    return factory


@pytest_asyncio.fixture
async def db_session_obj(session_factory) -> AsyncIterator:
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def current_user(session_factory) -> User:
    async with session_factory() as s:
        user = User(
            id=uuid.uuid4(),
            email=f"user+{uuid.uuid4().hex[:8]}@example.com",
            name="Test User",
            credits=10,
            plan="pro",
        )
        s.add(user)
        # Seed grant in credit_ledger so balance = 10
        from app.models.credit_ledger import CreditLedger, CreditLedgerType

        s.add(
            CreditLedger(
                user_id=user.id,
                type=CreditLedgerType.grant.value,
                amount=10,
                reason="test_seed",
            )
        )
        await s.commit()
        await s.refresh(user)
        return user


@pytest_asyncio.fixture
async def app(session_factory, current_user):
    """FastAPI app with overridden DB + auth dependencies."""
    application = create_app()

    async def _override_session():
        async with session_factory() as s:
            yield s

    async def _override_current_user():
        # Re-attach to fresh session in this request
        async with session_factory() as s:
            from sqlalchemy import select

            return (
                await s.execute(select(User).where(User.id == current_user.id))
            ).scalar_one()

    from app.deps import db_session as _real_db_dep

    application.dependency_overrides[_real_db_dep] = _override_session
    application.dependency_overrides[get_current_user] = _override_current_user

    # Also patch global session factory so workers/services using it pick up the same DB
    app_db._session_factory = session_factory  # type: ignore[attr-defined]
    yield application


@pytest_asyncio.fixture
async def client(app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
