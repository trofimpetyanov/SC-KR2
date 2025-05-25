from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

env_path = Path(__file__).parent / ".env"

class Settings(BaseSettings):
    API_GATEWAY_HOST: str = "0.0.0.0"
    API_GATEWAY_PORT: int = 8000
    FSS_URL: str = "http://files_storing_service:8000"
    FAS_URL: str = "http://file_analysis_service:8000"

    model_config = SettingsConfigDict(env_file=env_path, extra='ignore')

settings = Settings() 