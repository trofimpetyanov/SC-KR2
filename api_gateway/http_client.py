from fastapi import HTTPException, Request, Response, FastAPI
import httpx
from contextlib import asynccontextmanager
from logging_config import get_logger

logger = get_logger(__name__)

client_store = {}

@asynccontextmanager
async def lifespan_manager(app: FastAPI):
    logger.info("API Gateway: Initializing HTTP client")
    client_store["client"] = httpx.AsyncClient()
    yield
    logger.info("API Gateway: Closing HTTP client")
    if "client" in client_store:
        await client_store["client"].aclose()
        client_store.pop("client", None) 

async def forward_request_to_service(
    request: Request, 
    target_url: str,
    target_path: str,
    client: httpx.AsyncClient
):
    full_target_url = f"{target_url.rstrip('/')}{target_path}"
    if request.url.query:
        full_target_url += f"?{request.url.query}"
    
    headers = [(k, v) for k, v in request.headers.items() if k.lower() not in ("host", "connection", "user-agent")]
    
    content = None
    if request.method in ["POST", "PUT", "PATCH"]:
        content = await request.body()

    logger.info(f"Forwarding {request.method} request to {full_target_url}")
    try:
        rp = await client.request(
            method=request.method,
            url=full_target_url,
            headers=headers,
            content=content,
        )
        response_headers = dict(rp.headers)
        response_headers.pop("transfer-encoding", None)
        return Response(content=rp.content, status_code=rp.status_code, headers=response_headers)
    except httpx.ConnectError as e:
        logger.error(f"Service unavailable: {full_target_url} - {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {target_url}{target_path} - {str(e)}")
    except httpx.TimeoutException as e:
        logger.error(f"Gateway timeout: {full_target_url} - {str(e)}")
        raise HTTPException(status_code=504, detail=f"Gateway timeout: {target_url}{target_path} - {str(e)}")
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error from {full_target_url}: {e.response.status_code} - {e.response.text}")
        response_headers = dict(e.response.headers)
        response_headers.pop("transfer-encoding", None)
        return Response(content=e.response.content, status_code=e.response.status_code, headers=response_headers)
    except Exception as e:
        logger.exception(f"An unexpected error occurred while forwarding request to {full_target_url}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while forwarding request to {target_url}{target_path}: {str(e)}")