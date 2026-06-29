"""Application configuration (env-driven via pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PSRU AI Virtual Photo Booth API"
    env: str = "dev"

    database_url: str = "sqlite+aiosqlite:///./data/photobooth.db"
    public_base_url: str = "http://localhost:8000"

    # Storage: "local" filesystem (dev/single-instance) or "s3" (S3 / Cloudflare R2 / MinIO)
    storage_backend: str = "local"
    storage_dir: str = "./data/storage"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""        # set for R2/MinIO; leave empty for AWS S3
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_public_base_url: str = ""     # public-read bucket/CDN base; empty → presigned URLs
    s3_signed_url_ttl: int = 1800    # seconds

    # Dev auth (HS256) — used when OIDC is not configured, and for /auth/dev-token
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_alg: str = "HS256"
    auth_dev_mode: bool = True  # enable /auth/dev-token + accept HS256 dev tokens

    # Production auth (OIDC / Keycloak). Set oidc_issuer to enable JWKS validation.
    #   e.g. http://localhost:8080/realms/psru
    oidc_issuer: str = ""
    oidc_audience: str = "account"
    oidc_role_priority: list[str] = ["admin", "operator", "executive", "user"]

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.oidc_issuer)

    @property
    def oidc_jwks_url(self) -> str:
        return f"{self.oidc_issuer.rstrip('/')}/protocol/openid-connect/certs"

    pipeline_mock: bool = True
    pipeline_stage_delay_ms: int = 400

    capture_ttl_hours: int = 24
    output_ttl_days: int = 30
    policy_version: str = "2026.1"

    # CORS — restrict to PSRU origins in prod
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
