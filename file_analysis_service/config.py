from pydantic import HttpUrl, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path
from typing import Optional, Any

class Settings(BaseSettings):
    DATABASE_URL: str
    FAS_HOST: str = "0.0.0.0"
    FAS_PORT: int = 8002
    FAS_URL: Optional[HttpUrl] = None
    FSS_URL: HttpUrl
    WORDCLOUD_API_URL: HttpUrl = HttpUrl("https://quickchart.io/wordcloud")
    MAX_FILE_SIZE_MB: int = 10
    STORAGE_BASE_PATH_FAS: str = "wordclouds_fas"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8', 
        extra='ignore'
    )

    @field_validator('FAS_URL', mode='before')
    @classmethod
    def assemble_fas_url(cls, v: Optional[str], info: ValidationInfo) -> Any:
        if isinstance(v, str) and v:
            return v
        
        host = info.data.get('FAS_HOST', "0.0.0.0") 
        port = info.data.get('FAS_PORT', 8002)
        return f"http://{host}:{port}"

settings = Settings() 