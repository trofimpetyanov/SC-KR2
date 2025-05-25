import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

class FileMetadataBase(BaseModel):
    original_filename: str
    file_hash: str
    mime_type: Optional[str] = None
    size_bytes: int

class FileMetadataCreate(FileMetadataBase):
    pass

class FileMetadataInDB(FileMetadataBase):
    id: uuid.UUID
    file_location: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)