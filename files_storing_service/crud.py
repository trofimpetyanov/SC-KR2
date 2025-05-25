import uuid as py_uuid
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

import models, schemas

async def get_file_metadata_by_id(db: AsyncSession, file_id: py_uuid.UUID) -> Optional[models.FileMetadata]:
    result = await db.execute(select(models.FileMetadata).filter(models.FileMetadata.id == file_id))
    return result.scalars().first()

async def get_file_metadata_by_hash(db: AsyncSession, file_hash: str) -> Optional[models.FileMetadata]:
    result = await db.execute(select(models.FileMetadata).filter(models.FileMetadata.file_hash == file_hash))
    return result.scalars().first()

async def create_file_metadata(db: AsyncSession, file_meta: schemas.FileMetadataCreate, file_location: str) -> models.FileMetadata:
    db_file_meta = models.FileMetadata(
        original_filename=file_meta.original_filename,
        file_hash=file_meta.file_hash,
        mime_type=file_meta.mime_type,
        size_bytes=file_meta.size_bytes,
        file_location=file_location
    )
    db.add(db_file_meta)
    await db.commit()
    await db.refresh(db_file_meta)
    return db_file_meta

async def get_file_content_location(db: AsyncSession, file_id: py_uuid.UUID) -> Optional[str]:
    file_meta = await get_file_metadata_by_id(db, file_id)
    if file_meta:
        return file_meta.file_location
    return None