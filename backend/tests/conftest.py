import asyncio
import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor_test"
)

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import src.db as db_module
from src.db import Base, get_db
from src.main import app
from src.routers.resources import get_ingestion_trigger

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


async def _reset_schema() -> None:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    # A plain sync fixture using its own short-lived event loop (asyncio.run),
    # so it never conflicts with pytest-asyncio's per-test event loop below.
    asyncio.run(_reset_schema())


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_engine_pool():
    """Some services (e.g. study_plan.build_outline_entries, the ingestion
    pipeline) open their own session via the app's module-level `src.db.engine`
    instead of the per-test `db_session` fixture below. That engine's pool is a
    process-wide singleton, but pytest-asyncio gives each test its own event
    loop -- a pooled connection checked out in one test's loop breaks when reused
    in the next test's loop ("Event loop is closed"). Disposing the pool after
    every test forces a fresh connection (and thus a fresh loop binding) next time.
    """
    yield
    await db_module.engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        yield session

    # Clean up between tests without re-creating the schema each time.
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    # Never let a test's HTTP request trigger real ingestion (network calls, and a
    # separate DB engine/event loop from the one `db_session` above uses).
    app.dependency_overrides[get_ingestion_trigger] = lambda: (lambda *a, **kw: None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
