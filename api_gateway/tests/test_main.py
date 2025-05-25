import pytest
import httpx
from httpx import AsyncClient, Response
import json

from config import settings
from main import app, get_http_client, client_store

@pytest.mark.asyncio
async def test_ping(async_client: AsyncClient):
    response = await async_client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"message": "API Gateway is alive!"}

@pytest.mark.asyncio
async def test_root(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["message"] == "Welcome to the API Gateway!"
    assert "fss_url" in json_response
    assert "fas_url" in json_response

@pytest.mark.asyncio
async def test_proxy_to_fss_get(async_client: AsyncClient, httpx_mock):
    path = "/some/file/path"
    query_params = "v=1"
    fss_target_url = f"{settings.FSS_URL}{path}?{query_params}"
    mock_content = {"detail": "FSS File Found"}
    
    httpx_mock.add_response(method="GET", url=fss_target_url, json=mock_content, status_code=200)
    
    actual_outgoing_client = httpx.AsyncClient()
    client_store["client"] = actual_outgoing_client

    response = await async_client.get(f"/api/v1/files{path}?{query_params}")
    assert response.status_code == 200
    assert response.json() == mock_content

    await actual_outgoing_client.aclose()
    client_store.pop("client", None)

@pytest.mark.asyncio
async def test_proxy_to_fas_post(async_client: AsyncClient, httpx_mock):
    path = "/initiate"
    query_params = "source=test"
    fas_target_url = f"{str(settings.FAS_URL).rstrip('/')}/analysis{path}?{query_params}"
    request_payload = {"file_id": "some-uuid"}
    mock_response_content = {"analysis_id": "new-analysis-uuid", "status": "PENDING"}
    
    httpx_mock.add_response(
        method="POST", 
        url=fas_target_url, 
        json=mock_response_content, 
        status_code=202
    )
    
    actual_outgoing_client = httpx.AsyncClient()
    client_store["client"] = actual_outgoing_client

    response = await async_client.post(f"/api/v1/analysis{path}?{query_params}", json=request_payload)
    assert response.status_code == 202
    assert response.json() == mock_response_content

    mock_request = httpx_mock.get_requests()[0]
    assert mock_request.method == "POST"
    assert str(mock_request.url) == fas_target_url
    assert json.loads(mock_request.content) == request_payload

    await actual_outgoing_client.aclose()
    client_store.pop("client", None) 