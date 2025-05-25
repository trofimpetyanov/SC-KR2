import pytest_asyncio
import httpx
from typing import AsyncGenerator

from httpx import AsyncClient

from main import app 

@pytest_asyncio.fixture(scope="function")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testapigateway") as client:
        yield client
