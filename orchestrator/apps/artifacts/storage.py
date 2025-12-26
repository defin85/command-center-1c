import logging
from typing import IO, Optional

from django.conf import settings
from minio import Minio
from minio.error import S3Error


logger = logging.getLogger(__name__)


class ArtifactStorageError(RuntimeError):
    pass


class ArtifactStorageClient:
    def __init__(self) -> None:
        endpoint = getattr(settings, "MINIO_ENDPOINT", "localhost:9000")
        access_key = getattr(settings, "MINIO_ACCESS_KEY", "minioadmin")
        secret_key = getattr(settings, "MINIO_SECRET_KEY", "minioadmin")
        secure = bool(getattr(settings, "MINIO_SECURE", False))
        self.bucket = getattr(settings, "MINIO_BUCKET", "cc1c-artifacts")
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    def ensure_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as exc:
            raise ArtifactStorageError(str(exc)) from exc

    def upload_object(
        self,
        storage_key: str,
        data: IO[bytes],
        size: int,
        content_type: Optional[str] = None,
    ) -> None:
        try:
            self.ensure_bucket()
            self.client.put_object(
                self.bucket,
                storage_key,
                data,
                length=size,
                content_type=content_type or "application/octet-stream",
            )
        except S3Error as exc:
            raise ArtifactStorageError(str(exc)) from exc

    def get_object(self, storage_key: str):
        try:
            self.ensure_bucket()
            return self.client.get_object(self.bucket, storage_key)
        except S3Error as exc:
            raise ArtifactStorageError(str(exc)) from exc

    def delete_object(self, storage_key: str) -> None:
        try:
            self.ensure_bucket()
            self.client.remove_object(self.bucket, storage_key)
        except S3Error as exc:
            raise ArtifactStorageError(str(exc)) from exc
