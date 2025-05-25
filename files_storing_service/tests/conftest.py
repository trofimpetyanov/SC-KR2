import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
import httpx
from httpx._client import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from models import Base
from database import get_db
from config import settings

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_fss.db"

@pytest_asyncio.fixture(scope="function") 
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False) 
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession
    )
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testfss") as client:
        yield client
    
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def mock_fss_settings(tmp_path, monkeypatch):
    mock_storage_path = tmp_path / "filestorage_fss_test"
    mock_storage_path.mkdir()
    monkeypatch.setattr(settings, 'STORAGE_BASE_PATH', mock_storage_path)
    monkeypatch.setattr(settings, 'FAS_URL', 'http://mockfas:8000')
    return settings