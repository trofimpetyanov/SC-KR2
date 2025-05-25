import shutil
import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import FileResponse
import httpx
import aiofiles

import crud, schemas
from database import get_db
from config import settings as global_app_settings, Settings 
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    tags=["files"],
)

if not global_app_settings.STORAGE_BASE_PATH.exists():
    logger.info(f"Creating file storage directory at {global_app_settings.STORAGE_BASE_PATH}")
    global_app_settings.STORAGE_BASE_PATH.mkdir(parents=True, exist_ok=True)
else:
    logger.info(f"File storage directory already exists at {global_app_settings.STORAGE_BASE_PATH}")

def calculate_sha256(file_content: bytes) -> str:
    sha256_hash = hashlib.sha256()
    sha256_hash.update(file_content)
    return sha256_hash.hexdigest()

def get_settings():
    return global_app_settings

async def notify_fas_of_new_file(
    file_id: uuid.UUID,
    file_download_url: str,
    original_filename: str,
    mime_type: str,
    fas_url: str
):
    fas_trigger_url = f"{fas_url.rstrip('/')}/analysis/"
    payload = {
        "file_id": str(file_id),
        "file_location": file_download_url,
        "original_filename": original_filename,
        "mime_type": mime_type
    }
    logger.info(f"Notifying FAS at {fas_trigger_url} for file_id: {file_id}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(fas_trigger_url, json=payload)
            response.raise_for_status()
            logger.info(f"Successfully notified FAS for file_id: {file_id}. Response: {response.json()}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Error notifying FAS for file_id: {file_id}. Status: {e.response.status_code}, Response: {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"Error notifying FAS for file_id: {file_id}. Request failed: {str(e)}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while notifying FAS for file_id: {file_id}")

@router.post("/upload", response_model=schemas.FileMetadataInDB)
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_settings: Settings = Depends(get_settings)
):
    logger.info(f"Upload request for filename: '{file.filename}', content_type: '{file.content_type}'")
    content = await file.read()
    await file.seek(0)
    file_hash = hashlib.sha256(content).hexdigest()
    logger.debug(f"Calculated hash for '{file.filename}': {file_hash}")

    existing_file_meta = await crud.get_file_metadata_by_hash(db, file_hash=file_hash)
    if existing_file_meta:
        logger.info(f"File with hash {file_hash} (original: '{existing_file_meta.original_filename}') already exists. Returning existing metadata.")
        return existing_file_meta

    hash_prefix = file_hash[:2]
    storage_dir = current_settings.STORAGE_BASE_PATH / hash_prefix
    storage_dir.mkdir(parents=True, exist_ok=True)
    local_file_path = storage_dir / file_hash 

    logger.info(f"Saving new file '{file.filename}' to {local_file_path} (base: {current_settings.STORAGE_BASE_PATH})")
    try:
        async with aiofiles.open(local_file_path, 'wb') as out_file:
            while chunk := await file.read(1024*1024):
                await out_file.write(chunk)
    except Exception as e:
        logger.exception(f"Error saving file '{file.filename}' to {local_file_path}")
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")
    finally:
        await file.close()

    file_meta_create = schemas.FileMetadataCreate(
        original_filename=file.filename,
        file_hash=file_hash,
        mime_type=file.content_type,
        size_bytes=file.size if file.size else len(content)
    )
    relative_file_path = local_file_path.relative_to(current_settings.STORAGE_BASE_PATH)
    db_file_meta = await crud.create_file_metadata(db, file_meta=file_meta_create, file_location=str(relative_file_path))
    logger.info(f"Saved '{db_file_meta.original_filename}' (ID: {db_file_meta.id}) metadata to DB.")

    file_download_url = str(request.base_url.replace(path=f"/{db_file_meta.id}/download"))
    
    background_tasks.add_task(
        notify_fas_of_new_file,
        db_file_meta.id,
        file_download_url,
        db_file_meta.original_filename,
        db_file_meta.mime_type,
        current_settings.FAS_URL
    )
    logger.info(f"Background task added to notify FAS for file '{db_file_meta.original_filename}' (ID: {db_file_meta.id}).")

    return db_file_meta

@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_settings: Settings = Depends(get_settings)
):
    logger.info(f"Download request for file_id: {file_id}")
    file_meta = await crud.get_file_metadata_by_id(db, file_id=file_id)
    if not file_meta:
        logger.warning(f"File not found for download: ID {file_id}")
        raise HTTPException(status_code=404, detail="File not found")

    file_path_on_disk = current_settings.STORAGE_BASE_PATH / file_meta.file_location
    logger.debug(f"Serving file from path: {file_path_on_disk} for file_id: {file_id}")

    if not file_path_on_disk.exists() or not file_path_on_disk.is_file():
        logger.error(f"File for ID {file_id} found in DB (location: {file_meta.file_location}) but not in storage at {file_path_on_disk}. Inconsistency!")
        raise HTTPException(status_code=500, detail="File found in DB but not in storage. Inconsistency.")

    return FileResponse(
        path=file_path_on_disk,
        filename=file_meta.original_filename,
        media_type=file_meta.mime_type
    )

@router.get("/{file_id}/metadata", response_model=schemas.FileMetadataInDB)
async def get_file_metadata_endpoint(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    file_meta = await crud.get_file_metadata_by_id(db, file_id=file_id)
    if not file_meta:
        raise HTTPException(status_code=404, detail="File metadata not found")
    return file_meta 