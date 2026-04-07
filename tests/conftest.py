import os

import pytest_asyncio

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/exchange-game-pytest.db"

from app.db import Base, engine  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def reset_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
