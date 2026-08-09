from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import os


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    TELEGRAM_BOT_TOKEN: str
    SESSION_ENCRYPTION_KEY: str

    # Optional behaviour flags (safe defaults).
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    ALLOW_DEV_LOGIN: bool = False
    ENABLE_POLLER: bool = True
    POLL_INTERVAL_SECONDS: int = 45

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("SUPABASE_URL")
    @classmethod
    def normalize_supabase_url(cls, v: str) -> str:
        """Accept a bare project URL. Strip a trailing /rest/v1 that people
        paste from the dashboard — the supabase-py client appends it itself,
        and leaving it here produces /rest/v1/rest/v1 -> 401/404."""
        v = v.strip().rstrip("/")
        for suffix in ("/rest/v1", "/auth/v1"):
            if v.endswith(suffix):
                v = v[: -len(suffix)]
        return v.rstrip("/")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
