from fastapi import FastAPI, Request, Depends
from contextlib import asynccontextmanager
import httpx

from config import Settings, settings
from http_client import lifespan_manager, forward_request_to_service, client_store
from logging_config import get_logger

logger = get_logger(__name__)

app = FastAPI(lifespan=lifespan_manager)

@app.get("/ping", tags=["Health"])
async def ping():
    logger.debug("Ping endpoint was called")
    return {"message": "API Gateway is alive!"}

@app.get("/", tags=["Root"])
async def read_root(current_settings: Settings = Depends(lambda: settings)):
    logger.info("Root endpoint was called")
    return {
        "message": "Welcome to the API Gateway!",
        "fss_url": current_settings.FSS_URL,
        "fas_url": current_settings.FAS_URL
    }

async def get_http_client():
    return client_store["client"]

@app.api_route("/api/v1/files/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_to_fss(request: Request, path: str, client: httpx.AsyncClient = Depends(get_http_client), current_settings: Settings = Depends(lambda: settings)):
    logger.info(f"Proxying request for /api/v1/files/{path} to FSS ({current_settings.FSS_URL})")
    return await forward_request_to_service(request, current_settings.FSS_URL, f"/{path}", client)

@app.api_route("/api/v1/analysis/{full_path:path}", methods=["GET", "POST"])
async def proxy_to_fas(
    full_path: str,
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    current_settings: Settings = Depends(lambda: settings)
):
    logger.info(f"Proxying request for /api/v1/analysis/{full_path} to FAS ({current_settings.FAS_URL})")
    return await forward_request_to_service(request, current_settings.FAS_URL, "/analysis/" + full_path, client)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_GATEWAY_HOST, port=settings.API_GATEWAY_PORT) 