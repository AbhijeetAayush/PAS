from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
        populate_by_name=True,
    )

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_db_url: str = ""
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    qstash_token: str = ""
    qstash_current_signing_key: str = ""
    qstash_next_signing_key: str = ""
    qstash_url: str = "https://qstash-us-east-1.upstash.io"
    vertex_model: str = "gemini-3.5-flash"
    vertex_location: str = "global"
    gcp_project_id: str = ""
    bigquery_dataset: str = "voter_rolls"
    bigquery_location: str = "US"
    gcp_service_account_json_b64: str = ""
    gcp_service_account_secret: str = ""
    pdf_bucket: str = ""
    worker_base_url: str = ""
    cors_origin: str = Field(default="http://localhost:5173")
    log_level: str = "INFO"

    def cors_origins(self) -> list[str]:
        if self.cors_origin.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origin.split(",") if item.strip()]

    def require(self, *names: str) -> None:
        missing = [name for name in names if not str(getattr(self, name)).strip()]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing settings: {joined}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
