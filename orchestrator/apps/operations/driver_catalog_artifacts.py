from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from apps.artifacts.models import Artifact, ArtifactAlias, ArtifactKind, ArtifactVersion
from apps.artifacts.services import ArtifactService


CATALOG_ARTIFACT_KIND = ArtifactKind.DRIVER_CATALOG

CATALOG_BASE_SUFFIX = "base"
CATALOG_OVERRIDES_SUFFIX = "overrides"

CATALOG_ALIAS_LATEST = "latest"
CATALOG_ALIAS_APPROVED = "approved"
CATALOG_ALIAS_ACTIVE = "active"


@dataclass(frozen=True)
class CatalogArtifacts:
    base: Artifact
    overrides: Artifact


def get_catalog_artifacts(driver: str) -> CatalogArtifacts | None:
    driver = _normalize_driver(driver)
    base_name = f"driver_catalog.{driver}.{CATALOG_BASE_SUFFIX}"
    overrides_name = f"driver_catalog.{driver}.{CATALOG_OVERRIDES_SUFFIX}"

    base = Artifact.objects.filter(name=base_name, kind=CATALOG_ARTIFACT_KIND, is_deleted=False).first()
    if not base:
        return None
    overrides = Artifact.objects.filter(name=overrides_name, kind=CATALOG_ARTIFACT_KIND, is_deleted=False).first()
    if not overrides:
        return None
    return CatalogArtifacts(base=base, overrides=overrides)


def get_or_create_catalog_artifacts(driver: str, *, created_by=None) -> CatalogArtifacts:
    driver = _normalize_driver(driver)
    base_name = f"driver_catalog.{driver}.{CATALOG_BASE_SUFFIX}"
    overrides_name = f"driver_catalog.{driver}.{CATALOG_OVERRIDES_SUFFIX}"

    base = _get_or_create_artifact(
        name=base_name,
        tags=["driver_catalog", driver, CATALOG_BASE_SUFFIX],
        created_by=created_by,
    )
    overrides = _get_or_create_artifact(
        name=overrides_name,
        tags=["driver_catalog", driver, CATALOG_OVERRIDES_SUFFIX],
        created_by=created_by,
    )

    _ensure_overrides_active_alias(overrides, driver, created_by=created_by)

    return CatalogArtifacts(base=base, overrides=overrides)


def upload_base_catalog_version(
    driver: str,
    catalog: dict[str, Any],
    *,
    created_by=None,
    metadata_extra: dict[str, Any] | None = None,
) -> ArtifactVersion:
    driver = _normalize_driver(driver)
    artifacts = get_or_create_catalog_artifacts(driver, created_by=created_by)

    version_value = build_catalog_version_string(catalog)
    existing = artifacts.base.versions.filter(version=version_value).first()
    if existing:
        _upsert_alias(artifacts.base, CATALOG_ALIAS_LATEST, existing)
        return existing

    filename = _build_unique_filename(artifacts.base.name, version_value)
    file_obj = SimpleUploadedFile(
        name=filename,
        content=_encode_json(catalog),
        content_type="application/json",
    )

    metadata = _build_catalog_metadata(catalog)
    if metadata_extra:
        metadata = dict(metadata)
        metadata.update(metadata_extra)

    version_obj = ArtifactService.create_version(
        artifact=artifacts.base,
        file_obj=file_obj,
        filename=filename,
        version=version_value,
        metadata=metadata,
        content_type="application/json",
        created_by=created_by,
    )

    _upsert_alias(artifacts.base, CATALOG_ALIAS_LATEST, version_obj)

    return version_obj


def upload_overrides_catalog_version(
    driver: str,
    catalog: dict[str, Any],
    *,
    created_by=None,
    metadata_extra: dict[str, Any] | None = None,
) -> ArtifactVersion:
    driver = _normalize_driver(driver)
    artifacts = get_or_create_catalog_artifacts(driver, created_by=created_by)

    version_value = build_overrides_version_string(catalog)
    existing = artifacts.overrides.versions.filter(version=version_value).first()
    if existing:
        _upsert_alias(artifacts.overrides, CATALOG_ALIAS_ACTIVE, existing)
        return existing

    filename = _build_unique_filename(artifacts.overrides.name, version_value)
    file_obj = SimpleUploadedFile(
        name=filename,
        content=_encode_json(catalog),
        content_type="application/json",
    )

    metadata = {"catalog_version": 2, "driver": driver, "type": "overrides"}
    if metadata_extra:
        metadata = dict(metadata)
        metadata.update(metadata_extra)

    version_obj = ArtifactService.create_version(
        artifact=artifacts.overrides,
        file_obj=file_obj,
        filename=filename,
        version=version_value,
        metadata=metadata,
        content_type="application/json",
        created_by=created_by,
    )

    _upsert_alias(artifacts.overrides, CATALOG_ALIAS_ACTIVE, version_obj)
    return version_obj


def promote_base_alias(driver: str, *, version: str, alias: str = CATALOG_ALIAS_APPROVED) -> ArtifactAlias:
    driver = _normalize_driver(driver)
    artifacts = get_or_create_catalog_artifacts(driver)
    version_obj = artifacts.base.versions.get(version=version)
    return _upsert_alias(artifacts.base, alias, version_obj)


def build_catalog_version_string(catalog: dict[str, Any]) -> str:
    platform_version = str(catalog.get("platform_version") or "").strip() or "unknown"
    source = catalog.get("source") or {}
    doc_id = str(source.get("doc_id") or "").strip()
    fingerprint = _fingerprint(catalog)

    prefix_parts = [platform_version]
    if doc_id:
        prefix_parts.append(doc_id)

    prefix = "-".join(_sanitize_version_part(p) for p in prefix_parts if p)
    prefix = prefix.strip("_-")

    if not prefix:
        return fingerprint

    max_len = 64
    sep = "-"
    budget = max_len - len(sep) - len(fingerprint)
    if budget <= 0:
        return fingerprint

    if len(prefix) > budget:
        prefix = prefix[:budget].rstrip("_-")
        if not prefix:
            return fingerprint

    return f"{prefix}{sep}{fingerprint}"


def build_overrides_version_string(catalog: dict[str, Any]) -> str:
    fingerprint = _fingerprint(catalog)
    return f"ovr-{fingerprint}"


def build_empty_overrides_catalog(driver: str) -> dict[str, Any]:
    driver = _normalize_driver(driver)
    return {
        "catalog_version": 2,
        "driver": driver,
        "overrides": {
            "commands_by_id": {},
            "driver_schema": {},
        },
    }


def _ensure_overrides_active_alias(overrides: Artifact, driver: str, *, created_by=None) -> None:
    if ArtifactAlias.objects.filter(artifact=overrides, alias=CATALOG_ALIAS_ACTIVE).exists():
        return

    if overrides.versions.exists():
        latest = overrides.versions.order_by("-created_at").first()
        if latest:
            _upsert_alias(overrides, CATALOG_ALIAS_ACTIVE, latest)
            return

    empty_catalog = build_empty_overrides_catalog(driver)
    filename = _build_unique_filename(overrides.name, "v1")
    file_obj = SimpleUploadedFile(
        name=filename,
        content=_encode_json(empty_catalog),
        content_type="application/json",
    )
    try:
        version_obj = ArtifactService.create_version(
            artifact=overrides,
            file_obj=file_obj,
            filename=filename,
            version="v1",
            metadata={"catalog_version": 2, "driver": driver, "type": "overrides"},
            content_type="application/json",
            created_by=created_by,
        )
    except (ValueError, IntegrityError):
        version_obj = overrides.versions.get(version="v1")
    _upsert_alias(overrides, CATALOG_ALIAS_ACTIVE, version_obj)


def _upsert_alias(artifact: Artifact, alias: str, version: ArtifactVersion) -> ArtifactAlias:
    alias_obj, _ = ArtifactAlias.objects.update_or_create(
        artifact=artifact,
        alias=alias,
        defaults={"version": version},
    )
    return alias_obj


def _encode_json(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def _fingerprint(data: Any) -> str:
    payload = json.dumps(
        data,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _sanitize_version_part(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value.strip("_")


def _build_unique_filename(name: str, version: str) -> str:
    base = _sanitize_version_part(name)
    ver = _sanitize_version_part(version)
    suffix = f"__{ver}.json"
    max_len = 255
    if len(base) + len(suffix) <= max_len:
        return f"{base}{suffix}"
    budget = max_len - len(suffix)
    trimmed = base[:budget].rstrip("_-")
    if not trimmed:
        trimmed = "artifact"
    return f"{trimmed}{suffix}"


def _normalize_driver(driver: str) -> str:
    return str(driver or "").strip().lower()


def _build_catalog_metadata(catalog: dict[str, Any]) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "catalog_version": catalog.get("catalog_version"),
        "driver": catalog.get("driver"),
        "platform_version": catalog.get("platform_version"),
        "generated_at": catalog.get("generated_at"),
    }
    source = catalog.get("source")
    if isinstance(source, dict):
        for key in ("type", "doc_id", "doc_url", "section_prefix"):
            if key in source:
                meta[f"source_{key}"] = source.get(key)
    return meta


def _get_or_create_artifact(*, name: str, tags: list[str], created_by=None) -> Artifact:
    try:
        artifact, _ = Artifact.objects.get_or_create(
            name=name,
            kind=CATALOG_ARTIFACT_KIND,
            defaults={
                "is_versioned": True,
                "tags": tags,
                "created_by": created_by,
            },
        )
        return artifact
    except IntegrityError:
        return Artifact.objects.get(name=name, kind=CATALOG_ARTIFACT_KIND)
