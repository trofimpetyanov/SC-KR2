import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_ping_fas(async_client_fas: AsyncClient):
    response = await async_client_fas.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"message": "File Analysis Service is alive!"}

@pytest.mark.asyncio
async def test_root_fas(async_client_fas: AsyncClient):
    response = await async_client_fas.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the File Analysis Service!"} 