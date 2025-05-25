import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from database import engine
from models import Base
from routers import files as files_router
from logging_config import get_logger
from config import settings

logger = get_logger(__name__)

async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created or already exist.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Files Storing Service starting up...")
    await create_db_and_tables()
    logger.info(f"File storage path configured at: {settings.STORAGE_BASE_PATH}")
    logger.info(f"FAS URL for notifications: {settings.FAS_URL}")
    yield
    logger.info("Files Storing Service shutting down...")

app = FastAPI(
    title="Files Storing Service",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(files_router.router)

@app.get("/ping")
async def ping():
    return {"ping": "pong! from FSS"}

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Files Storing Service API"}

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting FSS on {settings.FSS_HOST}:{settings.FSS_PORT}")
    uvicorn.run("main:app", host=settings.FSS_HOST, port=settings.FSS_PORT, reload=True) 