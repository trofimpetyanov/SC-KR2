import pytest
import httpx
import json
from httpx import AsyncClient, Response, Request, ConnectError, TimeoutException, HTTPStatusError
from fastapi import Request as FastAPIRequest, HTTPException
from unittest.mock import patch, MagicMock

from http_client import forward_request_to_service, lifespan_manager, client_store
from config import settings

@pytest.mark.asyncio
async def test_forward_request_to_service_get(httpx_mock):
    base_url = "http://testservice"
    path = "/items/123"
    query_params = "param1=value1"
    full_url_with_query = f"{base_url}{path}?{query_params}"
    
    mock_response_content = {"key": "value"}
    mock_status_code = 200
    mock_headers = {"X-Test-Header": "TestValue"}

    httpx_mock.add_response(
        method="GET",
        url=full_url_with_query,
        json=mock_response_content,
        status_code=mock_status_code,
        headers=mock_headers
    )

    scope = {
        "type": "http",
        "method": "GET",
        "headers": [],
        "path": "/api/v1/files" + path, 
        "query_string": query_params.encode('utf-8'),
        "asgi": {"version": "3.0"}
    }
    fastapi_request = FastAPIRequest(scope)
    
    async with AsyncClient() as client: 
        response = await forward_request_to_service(fastapi_request, base_url, path, client)

    assert response.status_code == mock_status_code
    assert json.loads(response.body) == mock_response_content
    
    assert response.headers["content-type"] == "application/json"
    assert response.headers["x-test-header"] == "TestValue"

@pytest.mark.asyncio
async def test_forward_request_to_service_post_with_body(httpx_mock):
    base_url = "http://testservice"
    path = "/items"
    full_url = f"{base_url}{path}"
    
    request_body_dict = {"name": "test_item"}
    request_body_bytes = json.dumps(request_body_dict).encode("utf-8")
    mock_response_content = {"id": "1", "name": "test_item"}
    mock_status_code = 201
    mock_response_headers = {"content-type": "application/json"}

    httpx_mock.add_response(
        method="POST",
        url=full_url,
        json=mock_response_content,
        status_code=mock_status_code,
        headers=mock_response_headers
    )

    async def receive():
        return {"type": "http.request", "body": request_body_bytes, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(request_body_bytes)).encode())],
        "path": "/api/v1/files" + path,
        "query_string": b"",
        "asgi": {"version": "3.0"}
    }
    fastapi_request = FastAPIRequest(scope, receive=receive)
    
    async with AsyncClient() as client:
        response = await forward_request_to_service(fastapi_request, base_url, path, client)

    assert response.status_code == mock_status_code
    assert json.loads(response.body) == mock_response_content
    assert response.headers["content-type"] == "application/json"
    
    http_request: Request = httpx_mock.get_requests()[0]
    assert http_request.method == "POST"
    assert http_request.url == full_url
    assert http_request.read() == request_body_bytes
    assert http_request.headers["content-type"] == "application/json"

@pytest.mark.asyncio
async def test_lifespan_manager():
    app_mock = MagicMock()
    async with lifespan_manager(app_mock):
        assert "client" in client_store
        assert isinstance(client_store["client"], httpx.AsyncClient)
        assert not client_store["client"].is_closed
    
    assert "client" not in client_store 

@pytest.mark.asyncio
async def test_forward_request_to_service_connect_error(httpx_mock):
    base_url = "http://testservice_unavailable"
    path = "/items"
    full_url = f"{base_url}{path}"

    httpx_mock.add_exception(ConnectError("Connection failed"), url=full_url)

    scope = {"type": "http", "method": "GET", "headers": [], "path": path, "query_string": b"", "asgi": {"version": "3.0"}}
    fastapi_request = FastAPIRequest(scope)
    
    with pytest.raises(HTTPException) as exc_info:
        async with AsyncClient() as client:
            await forward_request_to_service(fastapi_request, base_url, path, client)
    assert exc_info.value.status_code == 503
    assert "Service unavailable" in exc_info.value.detail

@pytest.mark.asyncio
async def test_forward_request_to_service_timeout_error(httpx_mock):
    base_url = "http://testservice_timeout"
    path = "/items"
    full_url = f"{base_url}{path}"

    httpx_mock.add_exception(TimeoutException("Request timed out"), url=full_url)

    scope = {"type": "http", "method": "GET", "headers": [], "path": path, "query_string": b"", "asgi": {"version": "3.0"}}
    fastapi_request = FastAPIRequest(scope)
    
    with pytest.raises(HTTPException) as exc_info:
        async with AsyncClient() as client:
            await forward_request_to_service(fastapi_request, base_url, path, client)
    assert exc_info.value.status_code == 504
    assert "Gateway timeout" in exc_info.value.detail

@pytest.mark.asyncio
async def test_forward_request_to_service_http_status_error(httpx_mock):
    base_url = "http://testservice_status_error"
    path = "/items"
    full_url = f"{base_url}{path}"
    error_content = b"Internal Server Error"
    error_status = 500

    mock_httpx_request = httpx.Request(method="GET", url=full_url)
    mock_httpx_response = httpx.Response(status_code=error_status, content=error_content, request=mock_httpx_request)

    httpx_mock.add_exception(HTTPStatusError("Server error", request=mock_httpx_request, response=mock_httpx_response), url=full_url)

    scope = {"type": "http", "method": "GET", "headers": [], "path": path, "query_string": b"", "asgi": {"version": "3.0"}}
    fastapi_request = FastAPIRequest(scope)
    
    async with AsyncClient() as client:
        response = await forward_request_to_service(fastapi_request, base_url, path, client)
    
    assert response.status_code == error_status
    assert response.body == error_content

@pytest.mark.asyncio
async def test_forward_request_to_service_generic_exception(httpx_mock):
    base_url = "http://testservice_generic_error"
    path = "/items"
    full_url = f"{base_url}{path}"

    httpx_mock.add_exception(Exception("Some generic error"), url=full_url)

    scope = {"type": "http", "method": "GET", "headers": [], "path": path, "query_string": b"", "asgi": {"version": "3.0"}}
    fastapi_request = FastAPIRequest(scope)
    
    with pytest.raises(HTTPException) as exc_info:
        async with AsyncClient() as client:
            await forward_request_to_service(fastapi_request, base_url, path, client)
    assert exc_info.value.status_code == 500
    assert "An unexpected error occurred" in exc_info.value.detail 