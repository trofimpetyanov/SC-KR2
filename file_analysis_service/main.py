from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pathlib import Path
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from config import settings 
from database import get_db
from logging_config import get_logger
from routers import analysis as analysis_router 

logger = get_logger(__name__)

app = FastAPI(
    title="File Analysis Service",
    version="0.1.0"
)

@app.get("/ping", tags=["Health"])
async def ping():
    logger.debug("Ping endpoint was called")
    return {"message": "File Analysis Service is alive!"}

@app.get("/", tags=["Root"])
async def read_root():
    logger.info("Root endpoint was called")
    return {"message": "Welcome to the File Analysis Service!"}

app.include_router(analysis_router.router, prefix="/analysis")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting File Analysis Service on {settings.FAS_HOST}:{settings.FAS_PORT}")
    uvicorn.run(app, host=settings.FAS_HOST, port=settings.FAS_PORT) 