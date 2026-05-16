"""Storage abstraction — S3/MinIO via boto3.

Sync API is sufficient — used inside Celery workers, which run sync.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import boto3
import structlog
from botocore.client import Config as BotoConfig

from app.config import get_settings

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PutResult:
    bucket: str
    key: str
    url: str


def _client() -> Any:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint or None,
        region_name=settings.storage_region,
        aws_access_key_id=settings.storage_access_key.get_secret_value(),
        aws_secret_access_key=settings.storage_secret_key.get_secret_value(),
        config=BotoConfig(signature_version="s3v4"),
        use_ssl=settings.storage_use_ssl,
    )


def put_bytes(key: str, body: bytes, *, content_type: str = "audio/mpeg") -> PutResult:
    """Upload bytes to the configured bucket and return a CDN URL."""
    settings = get_settings()
    client = _client()
    # Ensure bucket exists in dev
    try:
        client.head_bucket(Bucket=settings.storage_bucket)
    except Exception:  # noqa: BLE001
        try:
            client.create_bucket(Bucket=settings.storage_bucket)
        except Exception as exc:  # noqa: BLE001
            log.warning("storage.create_bucket_failed", error=str(exc))

    client.put_object(
        Bucket=settings.storage_bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    url = f"{settings.cdn_base_url.rstrip('/')}/{key}"
    return PutResult(bucket=settings.storage_bucket, key=key, url=url)


def presign(key: str, expires_in: int = 300) -> str:
    settings = get_settings()
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.storage_bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def delete(key: str) -> None:
    settings = get_settings()
    try:
        _client().delete_object(Bucket=settings.storage_bucket, Key=key)
    except Exception as exc:  # noqa: BLE001
        log.warning("storage.delete_failed", key=key, error=str(exc))


def storage_key_for_song(generation_id: str, variant: str, ext: str = "mp3") -> str:
    return os.path.join("songs", str(generation_id), f"{variant}.{ext}")
