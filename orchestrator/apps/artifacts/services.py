import hashlib
import json
from typing import Optional, Tuple

from django.db import transaction

from .models import Artifact, ArtifactAlias, ArtifactVersion
from apps.files.services import FileStorageService
from .storage import ArtifactStorageClient


class ArtifactService:
    @staticmethod
    def calculate_checksum(file_obj) -> str:
        sha256 = hashlib.sha256()
        file_obj.seek(0)
        for chunk in file_obj.chunks(chunk_size=8192):
            sha256.update(chunk)
        file_obj.seek(0)
        return sha256.hexdigest()

    @staticmethod
    def generate_version(artifact: Artifact) -> str:
        count = artifact.versions.count()
        return f"v{count + 1}"

    @classmethod
    def resolve_version(
        cls,
        artifact: Artifact,
        version: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> ArtifactVersion:
        if version:
            return artifact.versions.get(version=version)
        if alias:
            alias_record = ArtifactAlias.objects.select_related("version").get(
                artifact=artifact,
                alias=alias,
            )
            return alias_record.version
        raise ValueError("version or alias is required")

    @classmethod
    def create_version(
        cls,
        artifact: Artifact,
        file_obj,
        filename: str,
        version: Optional[str] = None,
        metadata: Optional[dict] = None,
        content_type: Optional[str] = None,
        created_by=None,
    ) -> ArtifactVersion:
        storage = ArtifactStorageClient()
        checksum = cls.calculate_checksum(file_obj)
        metadata = metadata or {}
        filename = FileStorageService.sanitize_filename(filename)

        with transaction.atomic():
            if not artifact.is_versioned:
                if artifact.versions.exists():
                    raise ValueError("artifact is not versioned")
                if not version:
                    version = "current"

            version_value = version or cls.generate_version(artifact)
            if artifact.versions.filter(version=version_value).exists():
                raise ValueError("version already exists")

            storage_key = f"artifacts/{artifact.id}/{version_value}/{filename}"
            storage.upload_object(storage_key, file_obj, file_obj.size, content_type=content_type)

            return ArtifactVersion.objects.create(
                artifact=artifact,
                version=version_value,
                filename=filename,
                storage_key=storage_key,
                size=file_obj.size,
                checksum=checksum,
                content_type=content_type or "",
                metadata=metadata,
                created_by=created_by,
            )

    @staticmethod
    def parse_metadata(value) -> dict:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}
