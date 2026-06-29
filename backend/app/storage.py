"""Storage abstraction — pluggable backend behind one API.

Backends (config `STORAGE_BACKEND`):
- ``local`` (default): local filesystem, served via the API's `/files` mount.
  Good for dev and single-instance deployments.
- ``s3``: S3 / Cloudflare R2 / MinIO (any S3-compatible). Required when running
  multiple API instances or for durable object storage. `url_for` returns a
  public CDN URL (if `S3_PUBLIC_BASE_URL` set) or a time-limited presigned URL.

The same functions (`save_bytes` / `read_bytes` / `exists` / `url_for`) are used
by the rest of the app regardless of backend.
"""
from __future__ import annotations

import os
from pathlib import Path

from .config import get_settings

settings = get_settings()
_BACKEND = settings.storage_backend.lower()

# ---- local backend ----
_ROOT = Path(settings.storage_dir)


def _path(key: str) -> Path:
    p = _ROOT / key
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---- s3 backend (lazy client) ----
_s3 = None


def _client():
    global _s3
    if _s3 is None:
        import boto3  # lazy: only needed when STORAGE_BACKEND=s3

        _s3 = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region or None,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )
    return _s3


# ---- public API ----
def save_bytes(key: str, data: bytes) -> str:
    if _BACKEND == "s3":
        _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data)
    else:
        _path(key).write_bytes(data)
    return key


def read_bytes(key: str) -> bytes:
    if _BACKEND == "s3":
        return _client().get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()
    return _path(key).read_bytes()


def exists(key: str) -> bool:
    if _BACKEND == "s3":
        from botocore.exceptions import ClientError

        try:
            _client().head_object(Bucket=settings.s3_bucket, Key=key)
            return True
        except ClientError:
            return False
    return (_ROOT / key).exists()


def url_for(key: str | None) -> str | None:
    """Public URL for a stored object."""
    if not key:
        return None
    if _BACKEND == "s3":
        if settings.s3_public_base_url:
            return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=settings.s3_signed_url_ttl,
        )
    return f"{settings.public_base_url.rstrip('/')}/files/{key}"


def is_local() -> bool:
    return _BACKEND != "s3"


def storage_root() -> str:
    """Local FS root (used by the `/files` static mount). Local backend only."""
    os.makedirs(_ROOT, exist_ok=True)
    return str(_ROOT)
