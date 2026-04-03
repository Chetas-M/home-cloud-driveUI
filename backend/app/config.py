"""
Home Cloud Drive - Configuration Settings
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # Security
    # Security - no default! App will refuse to start without a real key.
    secret_key: str

    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v):
        """Block insecure placeholder keys at startup"""
        blocked = ['dev-secret', 'change-in-production', 'your-secret', 'super-secret', 'example', 'changeme', 'change_me', 'placeholder']
        v_lower = v.lower()
        for word in blocked:
            if word in v_lower:
                raise ValueError(
                    f"SECRET_KEY contains '{word}' - set a real key in .env "
                    f"(generate one with: openssl rand -hex 32)"
                )
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: openssl rand -hex 32"
            )
        return v
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    password_reset_expire_minutes: int = 30
    two_factor_temp_token_expire_minutes: int = 10

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/homecloud.db"

    # Storage (local filesystem)
    storage_path: str = "./storage"
    max_storage_bytes: int = 107374182400  # 100 GB default per user
    max_file_size_bytes: int = 1073741824  # 1 GB max per file
    trash_auto_delete_days: int = 30  # Auto-delete trashed files after N days

    # CORS - allowed origins for frontend (comma-separated string)
    # Accepts both CORS_ORIGINS and CORS_ORIGINS_STR env var names
    cors_origins_str: str = "http://localhost:5173,http://localhost:3000,http://localhost"

    @field_validator('cors_origins_str', mode='before')
    @classmethod
    def parse_cors(cls, v):
        """Accept CORS_ORIGINS env var (pydantic-settings maps it here via alias)"""
        if isinstance(v, list):
            return ','.join(v)
        return v

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins_str.split(',') if origin.strip()]

    # Session last-seen throttle - only write last_seen_at if older than this many seconds.
    # Reduces write amplification on busy deployments (set to 0 to always update).
    session_last_seen_update_interval_seconds: int = 60
    trust_proxy_headers: bool = False

    # Registration control - default OFF for secure-by-default; enable explicitly via env
    allow_registration: bool = False

    # Resend email API / password reset email
    resend_api_key: str | None = None
    resend_from_email: str | None = None
    resend_from_name: str = "Home Cloud"
    resend_api_url: str = "https://api.resend.com/emails"
    resend_timeout_seconds: int = 15
    password_reset_url: str | None = None

    @property
    def email_delivery_config_error(self) -> str | None:
        """Return a generic setup issue string when email delivery is not ready."""
        if not self.resend_api_key:
            return "Resend API key is missing"
        if not self.resend_from_email:
            return "Resend sender email is missing"
        return None

    @property
    def password_reset_enabled(self) -> bool:
        """Password reset requires a delivery channel for reset links."""
        return self.email_delivery_config_error is None

    @property
    def email_delivery_enabled(self) -> bool:
        """Resend is configured well enough to send transactional emails."""
        return self.email_delivery_config_error is None

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()

