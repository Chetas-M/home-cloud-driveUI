"""
Home Cloud Drive - Configuration Settings
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/homecloud.db"

    # Storage (local filesystem)
    storage_path: str = "./storage"
    max_storage_bytes: int = 107374182400  # 100 GB default per user

    # CORS - allowed origins for frontend (comma-separated string)
    cors_origins_str: str = "http://localhost:5173,http://localhost:3000,http://localhost"

    # Registration control - set to false to disable new user registration
    allow_registration: bool = True

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins_str.split(',') if origin.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
