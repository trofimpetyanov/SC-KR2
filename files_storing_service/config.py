from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

env_path = Path(__file__).parent / ".env"

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/db"
    FSS_HOST: str = "0.0.0.0"
    FSS_PORT: int = 8001
    FAS_URL: str = "http://localhost:8002"
    STORAGE_BASE_PATH: Path = Path("filestorage_fss")

    model_config = SettingsConfigDict(env_file=env_path, extra='ignore')

settings = Settings() 