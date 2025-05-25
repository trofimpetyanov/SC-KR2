from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import uuid

from pydantic import BaseModel, Field, HttpUrl, model_validator, ConfigDict
from pydantic_core.core_schema import ValidationInfo

class FileAnalysisBaseFields(BaseModel):
    original_file_id: uuid.UUID
    analysis_status: str = Field("PENDING", description="Status of the analysis: PENDING, PROCESSING, COMPLETED, FAILED")
    error_message: Optional[str] = None

class FileAnalysisRequest(BaseModel):
    file_id: uuid.UUID
    file_location: HttpUrl
    original_filename: str
    mime_type: str

class FileAnalysisResultCreate(FileAnalysisBaseFields):
    word_cloud_image_location: Optional[str] = None
    other_analysis_data: Optional[Dict[str, Any]] = None 

class FileAnalysisResultUpdate(BaseModel):
    analysis_status: Optional[str] = None
    word_cloud_image_location: Optional[str] = None
    other_analysis_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class FileAnalysisResultInDB(FileAnalysisResultCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FileAnalysisResultPublic(FileAnalysisBaseFields):
    id: uuid.UUID
    word_cloud_image_url: Optional[HttpUrl] = None
    analysis_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    word_cloud_image_location_internal: Optional[str] = Field(None, alias='word_cloud_image_location', exclude=True)
    other_analysis_data_internal: Optional[Dict[str, Any]] = Field(None, alias='other_analysis_data', exclude=True)

    @model_validator(mode='after')
    def populate_public_fields(self, info: ValidationInfo):
        actual_request_in_context = info.context.get("request") if info.context else None

        if self.other_analysis_data_internal:
            self.analysis_data = self.other_analysis_data_internal
        
        if actual_request_in_context is not None:
            if self.word_cloud_image_location_internal and self.analysis_status == "COMPLETED":
                if not hasattr(actual_request_in_context, 'base_url'):
                    self.word_cloud_image_url = None 
                else:
                    image_filename = Path(self.word_cloud_image_location_internal).name
                    try:
                        base_url_from_request = actual_request_in_context.base_url
                        url_path = f"/analysis/wordclouds/{self.id}/{image_filename}"
        
                        if hasattr(base_url_from_request, 'replace') and callable(base_url_from_request.replace) and not isinstance(base_url_from_request, str):
                            final_url_obj = base_url_from_request.replace(path=url_path)
                            self.word_cloud_image_url = HttpUrl(str(final_url_obj))
                        else: 
                            base_url_str = str(base_url_from_request).rstrip('/')
                            self.word_cloud_image_url = HttpUrl(f"{base_url_str}{url_path}")
                    except Exception:
                        self.word_cloud_image_url = None
            else:
                self.word_cloud_image_url = None

        return self

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)