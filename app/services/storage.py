"""File storage behind one interface: local folder (dev), S3-compatible (production), or disabled.

Nothing is written to the application's own disk in production (Render's filesystem is
ephemeral); `STORAGE_BACKEND=disabled` is forced while DEMO_MODE=true.
"""

import uuid
from pathlib import Path
from typing import Any, Protocol

from app.settings import get_settings

ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_BYTES = 5 * 1024 * 1024


class StorageDisabled(Exception):
    """Uploads are switched off (always the case in demo mode)."""


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> tuple[bytes, str] | None: ...


class DisabledStorage:
    def put(self, key: str, data: bytes, content_type: str) -> None:
        raise StorageDisabled

    def get(self, key: str) -> tuple[bytes, str] | None:
        raise StorageDisabled


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise ValueError("invalid storage key")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.with_name(path.name + ".type").write_text(content_type)

    def get(self, key: str) -> tuple[bytes, str] | None:
        path = self._path(key)
        if not path.is_file():
            return None
        content_type = path.with_name(path.name + ".type").read_text()
        return path.read_bytes(), content_type


class S3Storage:
    """S3-compatible object storage. boto3 is imported lazily so it stays optional."""

    def __init__(self, bucket: str, client: Any | None = None) -> None:
        self._bucket = bucket
        if client is None:
            import boto3  # type: ignore[import-not-found,unused-ignore]

            settings = get_settings()
            client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url or None,
                region_name=settings.s3_region or None,
            )
        self._client = client

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> tuple[bytes, str] | None:
        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception:  # noqa: BLE001 - missing key or transient error: treat as absent
            return None
        return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")


_override: Storage | None = None


def set_storage_for_tests(storage: Storage | None) -> None:
    global _override
    _override = storage


def get_storage() -> Storage:
    if _override is not None:
        return _override
    settings = get_settings()
    backend = settings.effective_storage_backend
    if backend == "local":
        return LocalStorage(Path(settings.storage_dir))
    if backend == "s3":
        return S3Storage(settings.s3_bucket)
    return DisabledStorage()


def new_photo_key(case_id: uuid.UUID, content_type: str) -> str:
    return f"wound/{case_id}/{uuid.uuid4()}{ALLOWED_TYPES[content_type]}"
