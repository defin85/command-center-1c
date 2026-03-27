from __future__ import annotations

import hashlib
import ipaddress
import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import redis
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.databases.odata import (
    ODataMetadataAdapter,
    ODataMetadataTransportError,
    resolve_database_odata_verify_tls,
)
from apps.databases.models import Database, DatabaseExtensionsSnapshot, InfobaseUserMapping
from apps.intercompany_pools.business_configuration_operations import (
    ensure_business_configuration_profile_runtime,
)
from apps.intercompany_pools.business_configuration_profile import (
    get_business_configuration_profile,
    mark_business_configuration_publication_state,
    persist_business_configuration_profile,
)

from .models import (
    PoolODataMetadataCatalogSnapshot,
    PoolODataMetadataCatalogScopeResolution,
    PoolODataMetadataCatalogSnapshotSource,
)
from .publication_auth_mapping import (
    ERROR_CODE_ODATA_MAPPING_AMBIGUOUS,
    ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
)


ERROR_CODE_POOL_METADATA_REFERENCE_INVALID = "POOL_METADATA_REFERENCE_INVALID"
ERROR_CODE_POOL_METADATA_SNAPSHOT_UNAVAILABLE = "POOL_METADATA_SNAPSHOT_UNAVAILABLE"
ERROR_CODE_POOL_METADATA_REFRESH_IN_PROGRESS = "POOL_METADATA_REFRESH_IN_PROGRESS"
ERROR_CODE_POOL_METADATA_FETCH_FAILED = "POOL_METADATA_FETCH_FAILED"
ERROR_CODE_POOL_METADATA_PARSE_FAILED = "POOL_METADATA_PARSE_FAILED"
ERROR_CODE_POOL_METADATA_PROFILE_UNAVAILABLE = "POOL_METADATA_PROFILE_UNAVAILABLE"

SOURCE_REDIS = "redis"
SOURCE_DB = "db"
SOURCE_LIVE_REFRESH = "live_refresh"

DEFAULT_CACHE_KEY_PREFIX = "cc1c:pools:odata-metadata:catalog"
DEFAULT_CACHE_TTL_SECONDS = 300
MAX_UPSTREAM_ERROR_DETAIL_LENGTH = 500
MAX_UPSTREAM_ERROR_MESSAGES = 3

@dataclass(frozen=True)
class MetadataCatalogScope:
    tenant_id: str
    database_id: str
    config_name: str
    config_version: str
    extensions_fingerprint: str


@dataclass(frozen=True)
class MetadataCatalogSnapshotResolution:
    resolution_mode: str
    is_shared_snapshot: bool
    provenance_database_id: str
    provenance_confirmed_at: datetime | None


@dataclass(frozen=True)
class DatabaseMetadataCatalogState:
    profile: dict[str, Any] | None
    snapshot: PoolODataMetadataCatalogSnapshot | None
    resolution: MetadataCatalogSnapshotResolution | None


RESOLUTION_MODE_DATABASE_SCOPE = "database_scope"
RESOLUTION_MODE_SHARED_SCOPE = "shared_scope"


class MetadataCatalogError(Exception):
    def __init__(
        self,
        *,
        code: str,
        title: str,
        detail: str,
        status_code: int = 400,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.title = title
        self.detail = detail
        self.status_code = status_code
        self.errors = errors or []


def _build_metadata_catalog_scope_from_profile(
    *,
    tenant_id: str,
    database: Database,
    profile: dict[str, Any],
) -> MetadataCatalogScope:
    config_name = str(profile.get("config_name") or "").strip()
    config_version = str(profile.get("config_version") or "").strip()

    extensions_fingerprint = ""
    snapshot: DatabaseExtensionsSnapshot | None = getattr(database, "extensions_snapshot", None)
    if snapshot and isinstance(snapshot.snapshot, dict):
        extensions_fingerprint = hashlib.sha256(_canonical_json_bytes(snapshot.snapshot)).hexdigest()

    return MetadataCatalogScope(
        tenant_id=str(tenant_id),
        database_id=str(database.id),
        config_name=config_name,
        config_version=config_version,
        extensions_fingerprint=extensions_fingerprint,
    )


def resolve_metadata_catalog_scope(*, tenant_id: str, database: Database) -> MetadataCatalogScope:
    profile = _resolve_business_configuration_profile(database=database)
    if profile is None:
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_PROFILE_UNAVAILABLE,
            title="Metadata Business Profile Unavailable",
            detail="Business configuration profile is unavailable for selected database.",
            status_code=400,
            errors=[
                {
                    "code": ERROR_CODE_POOL_METADATA_PROFILE_UNAVAILABLE,
                    "path": "database_id",
                    "detail": "Business configuration profile is unavailable for selected database.",
                }
            ],
        )
    return _build_metadata_catalog_scope_from_profile(
        tenant_id=tenant_id,
        database=database,
        profile=profile,
    )


def read_metadata_catalog_snapshot(
    *,
    tenant_id: str,
    database: Database,
    requested_by_username: str,
    allow_cold_bootstrap: bool = True,
) -> tuple[PoolODataMetadataCatalogSnapshot, str]:
    ensure_business_configuration_profile_runtime(database=database)
    scope = resolve_metadata_catalog_scope(tenant_id=tenant_id, database=database)
    # Metadata catalog path is mapping-only for both read and refresh requests.
    # Validate auth configuration before serving cached/snapshotted data.
    _resolve_metadata_mapping_credentials(
        database=database,
        requested_by_username=requested_by_username,
    )
    cached_snapshot = _read_snapshot_from_cache(scope=scope)
    if cached_snapshot is not None:
        current_resolution = _get_scope_resolution(scope=scope)
        if current_resolution is not None:
            current_snapshot = current_resolution.snapshot
            if current_snapshot.id == cached_snapshot.id:
                return cached_snapshot, SOURCE_REDIS
            _write_snapshot_to_cache(scope=scope, snapshot=current_snapshot)
            return current_snapshot, SOURCE_DB

        resolved_cached_snapshot = _get_current_snapshot(scope=scope, database=database)
        if resolved_cached_snapshot is not None:
            if resolved_cached_snapshot.id != cached_snapshot.id:
                _write_snapshot_to_cache(scope=scope, snapshot=resolved_cached_snapshot)
            return resolved_cached_snapshot, SOURCE_DB

    current_snapshot = _get_current_snapshot(scope=scope, database=database)
    if current_snapshot is not None:
        _write_snapshot_to_cache(scope=scope, snapshot=current_snapshot)
        return current_snapshot, SOURCE_DB

    if not allow_cold_bootstrap:
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_SNAPSHOT_UNAVAILABLE,
            title="Metadata Snapshot Unavailable",
            detail="Current metadata snapshot is missing for selected database scope.",
            status_code=400,
            errors=[
                {
                    "code": ERROR_CODE_POOL_METADATA_SNAPSHOT_UNAVAILABLE,
                    "path": "document_policy",
                    "detail": "Current metadata snapshot is missing for selected database scope.",
                }
            ],
        )

    refreshed = refresh_metadata_catalog_snapshot(
        tenant_id=tenant_id,
        database=database,
        requested_by_username=requested_by_username,
        source=PoolODataMetadataCatalogSnapshotSource.COLD_BOOTSTRAP,
    )
    return refreshed, SOURCE_LIVE_REFRESH


def refresh_metadata_catalog_snapshot(
    *,
    tenant_id: str,
    database: Database,
    requested_by_username: str,
    source: str = PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH,
) -> PoolODataMetadataCatalogSnapshot:
    ensure_business_configuration_profile_runtime(database=database)
    scope = resolve_metadata_catalog_scope(tenant_id=tenant_id, database=database)

    try:
        with transaction.atomic():
            try:
                Database.objects.select_for_update(nowait=True).only("id").get(id=database.id)
            except DatabaseError as exc:
                raise MetadataCatalogError(
                    code=ERROR_CODE_POOL_METADATA_REFRESH_IN_PROGRESS,
                    title="Metadata Refresh In Progress",
                    detail="Metadata refresh already in progress for selected database.",
                    status_code=409,
                ) from exc

            catalog_payload = _fetch_live_catalog_payload(
                database=database,
                requested_by_username=requested_by_username,
            )
            metadata_hash = hashlib.sha256(_canonical_json_bytes(catalog_payload)).hexdigest()
            catalog_version = _build_catalog_version(scope=scope, metadata_hash=metadata_hash)
            now = timezone.now()
            previous_resolution = _get_scope_resolution(scope=scope, for_update=True)
            previous_snapshot = previous_resolution.snapshot if previous_resolution is not None else None
            current_shared_snapshot = _get_shared_current_snapshot(scope=scope, for_update=True)

            if current_shared_snapshot is not None and current_shared_snapshot.metadata_hash != metadata_hash:
                should_reuse_current_snapshot = (
                    str(current_shared_snapshot.database_id) != str(database.id)
                    or _shared_snapshot_has_peer_resolution(
                        snapshot=current_shared_snapshot,
                        database=database,
                    )
                )
                if should_reuse_current_snapshot:
                    snapshot = current_shared_snapshot
                    _upsert_scope_resolution(
                        scope=scope,
                        database=database,
                        snapshot=snapshot,
                        confirmed_at=snapshot.fetched_at,
                        existing=previous_resolution,
                    )
                    _sync_snapshot_current_marker(snapshot=snapshot)
                    mark_business_configuration_publication_state(
                        database=database,
                        observed_metadata_hash=metadata_hash,
                        fetched_at=now,
                        canonical_metadata_hash=snapshot.metadata_hash,
                    )
                    if previous_snapshot is not None and previous_snapshot.id != snapshot.id:
                        _sync_snapshot_current_marker(snapshot=previous_snapshot)
                    _write_snapshot_to_cache(scope=scope, snapshot=snapshot)
                    return snapshot

            existing_version = None
            if current_shared_snapshot is None or current_shared_snapshot.metadata_hash == metadata_hash:
                existing_version = (
                    PoolODataMetadataCatalogSnapshot.objects.select_for_update()
                    .filter(**_shared_scope_filters(scope), catalog_version=catalog_version)
                    .first()
                )

            if existing_version is not None:
                existing_version.database = database
                existing_version.extensions_fingerprint = scope.extensions_fingerprint
                existing_version.metadata_hash = metadata_hash
                existing_version.payload = catalog_payload
                existing_version.source = source
                existing_version.fetched_at = now
                existing_version.is_current = True
                existing_version.save(
                    update_fields=[
                        "database",
                        "extensions_fingerprint",
                        "metadata_hash",
                        "payload",
                        "source",
                        "fetched_at",
                        "is_current",
                        "updated_at",
                    ]
                )
                snapshot = existing_version
            else:
                snapshot = PoolODataMetadataCatalogSnapshot.objects.create(
                    tenant_id=scope.tenant_id,
                    database=database,
                    config_name=scope.config_name,
                    config_version=scope.config_version,
                    extensions_fingerprint=scope.extensions_fingerprint,
                    metadata_hash=metadata_hash,
                    catalog_version=catalog_version,
                    payload=catalog_payload,
                    source=source,
                    fetched_at=now,
                    is_current=True,
                )
            _upsert_scope_resolution(
                scope=scope,
                database=database,
                snapshot=snapshot,
                confirmed_at=now,
                existing=previous_resolution,
            )
            _sync_snapshot_current_marker(snapshot=snapshot)
            if previous_snapshot is not None and previous_snapshot.id != snapshot.id:
                _sync_snapshot_current_marker(snapshot=previous_snapshot)
            mark_business_configuration_publication_state(
                database=database,
                observed_metadata_hash=metadata_hash,
                fetched_at=now,
                canonical_metadata_hash=snapshot.metadata_hash,
            )
    except MetadataCatalogError:
        raise

    _write_snapshot_to_cache(scope=scope, snapshot=snapshot)
    return snapshot


def get_current_snapshot_for_database_scope(
    *,
    tenant_id: str,
    database: Database,
) -> PoolODataMetadataCatalogSnapshot | None:
    ensure_business_configuration_profile_runtime(database=database)
    scope = resolve_metadata_catalog_scope(tenant_id=tenant_id, database=database)
    return _get_current_snapshot(scope=scope, database=database)


def read_existing_metadata_catalog_snapshot(
    *,
    tenant_id: str,
    database: Database,
    requested_by_username: str,
) -> tuple[PoolODataMetadataCatalogSnapshot, str, MetadataCatalogSnapshotResolution, dict[str, Any]]:
    profile = _resolve_business_configuration_profile(
        database=database,
        materialize_legacy=False,
        include_legacy_snapshot_profile=True,
    )
    if profile is None:
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_PROFILE_UNAVAILABLE,
            title="Metadata Business Profile Unavailable",
            detail="Business configuration profile is unavailable for selected database.",
            status_code=400,
            errors=[
                {
                    "code": ERROR_CODE_POOL_METADATA_PROFILE_UNAVAILABLE,
                    "path": "database_id",
                    "detail": "Business configuration profile is unavailable for selected database.",
                }
            ],
        )

    scope = _build_metadata_catalog_scope_from_profile(
        tenant_id=tenant_id,
        database=database,
        profile=profile,
    )
    _resolve_metadata_mapping_credentials(
        database=database,
        requested_by_username=requested_by_username,
    )
    snapshot = _get_current_snapshot(scope=scope, database=None)
    if snapshot is None:
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_SNAPSHOT_UNAVAILABLE,
            title="Metadata Snapshot Unavailable",
            detail="Current metadata snapshot is missing for selected database scope.",
            status_code=400,
            errors=[
                {
                    "code": ERROR_CODE_POOL_METADATA_SNAPSHOT_UNAVAILABLE,
                    "path": "database_id",
                    "detail": "Current metadata snapshot is missing for selected database scope.",
                }
            ],
        )

    resolution = describe_metadata_catalog_snapshot_resolution(
        tenant_id=tenant_id,
        database=database,
        snapshot=snapshot,
    )
    return snapshot, SOURCE_DB, resolution, profile


def get_database_metadata_catalog_state(
    *,
    tenant_id: str,
    database: Database,
) -> DatabaseMetadataCatalogState:
    profile = _resolve_business_configuration_profile(
        database=database,
        materialize_legacy=False,
        include_legacy_snapshot_profile=True,
    )
    if profile is None:
        return DatabaseMetadataCatalogState(
            profile=None,
            snapshot=None,
            resolution=None,
        )

    scope = _build_metadata_catalog_scope_from_profile(
        tenant_id=tenant_id,
        database=database,
        profile=profile,
    )
    snapshot = _get_current_snapshot(scope=scope, database=None)
    if snapshot is None:
        return DatabaseMetadataCatalogState(
            profile=profile,
            snapshot=None,
            resolution=None,
        )

    resolution = describe_metadata_catalog_snapshot_resolution(
        tenant_id=tenant_id,
        database=database,
        snapshot=snapshot,
    )
    return DatabaseMetadataCatalogState(
        profile=profile,
        snapshot=snapshot,
        resolution=resolution,
    )


def describe_metadata_catalog_snapshot_resolution(
    *,
    tenant_id: str,
    database: Database,
    snapshot: PoolODataMetadataCatalogSnapshot,
) -> MetadataCatalogSnapshotResolution:
    provenance_database_id = str(snapshot.database_id)
    provenance_confirmed_at = snapshot.fetched_at
    is_shared_snapshot = (
        provenance_database_id != str(database.id)
        or PoolODataMetadataCatalogScopeResolution.objects.filter(snapshot_id=snapshot.id)
        .exclude(database_id=database.id)
        .exists()
    )
    resolution_mode = (
        RESOLUTION_MODE_SHARED_SCOPE if is_shared_snapshot else RESOLUTION_MODE_DATABASE_SCOPE
    )
    return MetadataCatalogSnapshotResolution(
        resolution_mode=resolution_mode,
        is_shared_snapshot=is_shared_snapshot,
        provenance_database_id=provenance_database_id,
        provenance_confirmed_at=provenance_confirmed_at,
    )


def build_metadata_catalog_api_payload(
    *,
    database: Database,
    snapshot: PoolODataMetadataCatalogSnapshot,
    source: str,
    resolution: MetadataCatalogSnapshotResolution,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = normalize_catalog_payload(
        payload=snapshot.payload if isinstance(snapshot.payload, dict) else {}
    )
    effective_profile = profile if profile is not None else (get_business_configuration_profile(database=database) or {})
    config_name = str(effective_profile.get("config_name") or snapshot.config_name or "")
    config_version = str(effective_profile.get("config_version") or snapshot.config_version or "")
    documents = payload.get("documents") if isinstance(payload.get("documents"), list) else []
    return {
        "database_id": str(database.id),
        "snapshot_id": str(snapshot.id),
        "source": str(source or snapshot.source or ""),
        "fetched_at": snapshot.fetched_at,
        "catalog_version": snapshot.catalog_version,
        "config_name": config_name,
        "config_version": config_version,
        "extensions_fingerprint": snapshot.extensions_fingerprint,
        "metadata_hash": snapshot.metadata_hash,
        "config_generation_id": str(effective_profile.get("config_generation_id") or ""),
        "publication_drift": bool(effective_profile.get("publication_drift")),
        "observed_metadata_hash": str(effective_profile.get("observed_metadata_hash") or ""),
        "resolution_mode": resolution.resolution_mode,
        "is_shared_snapshot": resolution.is_shared_snapshot,
        "provenance_database_id": resolution.provenance_database_id,
        "provenance_confirmed_at": resolution.provenance_confirmed_at,
        "documents": documents,
    }


def validate_document_policy_references(
    *,
    policy: dict[str, Any],
    snapshot: PoolODataMetadataCatalogSnapshot | None,
    path_prefix: str = "document_policy",
) -> list[dict[str, str]]:
    if snapshot is None:
        return [
            {
                "code": ERROR_CODE_POOL_METADATA_SNAPSHOT_UNAVAILABLE,
                "path": path_prefix,
                "detail": "Current metadata snapshot is missing for selected database scope.",
            }
        ]

    payload = normalize_catalog_payload(
        payload=snapshot.payload if isinstance(snapshot.payload, dict) else {}
    )
    documents_raw = payload.get("documents")
    if not isinstance(documents_raw, list):
        return [
            {
                "code": ERROR_CODE_POOL_METADATA_SNAPSHOT_UNAVAILABLE,
                "path": path_prefix,
                "detail": "Metadata snapshot payload is invalid or empty.",
            }
        ]

    documents_index: dict[str, dict[str, Any]] = {}
    for raw_document in documents_raw:
        if not isinstance(raw_document, Mapping):
            continue
        entity_name = str(raw_document.get("entity_name") or "").strip()
        if entity_name:
            documents_index[entity_name] = dict(raw_document)

    errors: list[dict[str, str]] = []
    chains = policy.get("chains")
    if not isinstance(chains, list):
        return errors

    for chain_index, raw_chain in enumerate(chains):
        if not isinstance(raw_chain, Mapping):
            continue
        chain_documents = raw_chain.get("documents")
        if not isinstance(chain_documents, list):
            continue

        document_ids = {
            str(item.get("document_id") or "").strip()
            for item in chain_documents
            if isinstance(item, Mapping)
        }
        document_ids.discard("")

        for document_index, raw_document in enumerate(chain_documents):
            if not isinstance(raw_document, Mapping):
                continue
            document_path = f"{path_prefix}.chains[{chain_index}].documents[{document_index}]"
            entity_name = str(raw_document.get("entity_name") or "").strip()
            if not entity_name:
                continue

            catalog_document = documents_index.get(entity_name)
            if catalog_document is None:
                errors.append(
                    {
                        "code": ERROR_CODE_POOL_METADATA_REFERENCE_INVALID,
                        "path": f"{document_path}.entity_name",
                        "detail": f"Entity '{entity_name}' is not available in current metadata catalog.",
                    }
                )
                continue

            allowed_fields = {
                str(item.get("name") or "").strip()
                for item in (catalog_document.get("fields") or [])
                if isinstance(item, Mapping)
            }
            allowed_fields.discard("")

            field_mapping = raw_document.get("field_mapping")
            if isinstance(field_mapping, Mapping):
                for field_name in field_mapping.keys():
                    mapped_field = str(field_name or "").strip()
                    if mapped_field and mapped_field not in allowed_fields:
                        errors.append(
                            {
                                "code": ERROR_CODE_POOL_METADATA_REFERENCE_INVALID,
                                "path": f"{document_path}.field_mapping.{mapped_field}",
                                "detail": (
                                    f"Field '{mapped_field}' is not available for entity '{entity_name}'."
                                ),
                            }
                        )

            table_parts_index: dict[str, set[str]] = {}
            for table_part in (catalog_document.get("table_parts") or []):
                if not isinstance(table_part, Mapping):
                    continue
                table_part_name = str(table_part.get("name") or "").strip()
                if not table_part_name:
                    continue
                row_fields = {
                    str(row_field.get("name") or "").strip()
                    for row_field in (table_part.get("row_fields") or [])
                    if isinstance(row_field, Mapping)
                }
                row_fields.discard("")
                table_parts_index[table_part_name] = row_fields

            table_parts_mapping = raw_document.get("table_parts_mapping")
            if isinstance(table_parts_mapping, Mapping):
                for table_part_name, row_mapping in table_parts_mapping.items():
                    normalized_table_part_name = str(table_part_name or "").strip()
                    if not normalized_table_part_name:
                        continue
                    row_fields = table_parts_index.get(normalized_table_part_name)
                    if row_fields is None:
                        errors.append(
                            {
                                "code": ERROR_CODE_POOL_METADATA_REFERENCE_INVALID,
                                "path": f"{document_path}.table_parts_mapping.{normalized_table_part_name}",
                                "detail": (
                                    f"Table part '{normalized_table_part_name}' is not available for "
                                    f"entity '{entity_name}'."
                                ),
                            }
                        )
                        continue

                    if isinstance(row_mapping, Mapping):
                        for row_field_name in row_mapping.keys():
                            normalized_row_field = str(row_field_name or "").strip()
                            if normalized_row_field and normalized_row_field not in row_fields:
                                errors.append(
                                    {
                                        "code": ERROR_CODE_POOL_METADATA_REFERENCE_INVALID,
                                        "path": (
                                            f"{document_path}.table_parts_mapping."
                                            f"{normalized_table_part_name}.{normalized_row_field}"
                                        ),
                                        "detail": (
                                            f"Row field '{normalized_row_field}' is not available for "
                                            f"table part '{normalized_table_part_name}' of entity '{entity_name}'."
                                        ),
                                    }
                                )

            link_to = str(raw_document.get("link_to") or "").strip()
            if link_to and link_to not in document_ids:
                errors.append(
                    {
                        "code": ERROR_CODE_POOL_METADATA_REFERENCE_INVALID,
                        "path": f"{document_path}.link_to",
                        "detail": f"link_to='{link_to}' does not reference an existing document_id in chain.",
                    }
                )
            link_rules = raw_document.get("link_rules")
            if isinstance(link_rules, Mapping):
                depends_on = str(link_rules.get("depends_on") or "").strip()
                if depends_on and depends_on not in document_ids:
                    errors.append(
                        {
                            "code": ERROR_CODE_POOL_METADATA_REFERENCE_INVALID,
                            "path": f"{document_path}.link_rules.depends_on",
                            "detail": (
                                f"link_rules.depends_on='{depends_on}' does not reference an existing "
                                "document_id in chain."
                            ),
                        }
                    )
    return errors


def normalize_catalog_payload(*, payload: dict[str, Any]) -> dict[str, Any]:
    documents_raw = payload.get("documents")
    if not isinstance(documents_raw, list):
        documents_raw = []

    normalized_documents: list[dict[str, Any]] = []
    for raw_document in documents_raw:
        if not isinstance(raw_document, Mapping):
            continue
        entity_name = str(raw_document.get("entity_name") or "").strip()
        if not entity_name:
            continue
        normalized_document: dict[str, Any] = {
            "entity_name": entity_name,
            "display_name": str(raw_document.get("display_name") or entity_name).strip() or entity_name,
            "fields": _normalize_field_items(raw_document.get("fields")),
            "table_parts": _normalize_table_parts(raw_document.get("table_parts")),
        }
        normalized_documents.append(normalized_document)

    documents_by_entity_name = {
        str(item.get("entity_name") or ""): item for item in normalized_documents
    }
    for document in normalized_documents:
        document_entity_name = str(document.get("entity_name") or "").strip()
        table_parts = document.get("table_parts")
        if not document_entity_name or not isinstance(table_parts, list):
            continue
        for table_part in table_parts:
            if not isinstance(table_part, Mapping):
                continue
            row_fields = table_part.get("row_fields")
            if isinstance(row_fields, list) and len(row_fields) > 0:
                continue

            table_part_name = str(table_part.get("name") or "").strip()
            if not table_part_name:
                continue
            companion_entity_name = f"{document_entity_name}_{table_part_name}"
            companion_document = documents_by_entity_name.get(companion_entity_name)
            if not isinstance(companion_document, Mapping):
                continue

            companion_fields = _normalize_field_items(companion_document.get("fields"))
            if companion_fields:
                table_part["row_fields"] = companion_fields

    normalized_documents.sort(key=lambda item: str(item.get("entity_name") or ""))
    return {
        "documents": normalized_documents,
        "information_registers": _normalize_catalog_entities(payload.get("information_registers")),
        "accounting_registers": _normalize_register_entities(payload.get("accounting_registers")),
    }


def _shared_scope_filters(scope: MetadataCatalogScope) -> dict[str, str]:
    return {
        "tenant_id": scope.tenant_id,
        "config_name": scope.config_name,
        "config_version": scope.config_version,
    }


def _resolution_filters(scope: MetadataCatalogScope) -> dict[str, str]:
    return {
        "tenant_id": scope.tenant_id,
        "database_id": scope.database_id,
        "config_name": scope.config_name,
        "config_version": scope.config_version,
    }


def _get_current_snapshot(
    *,
    scope: MetadataCatalogScope,
    database: Database | None = None,
) -> PoolODataMetadataCatalogSnapshot | None:
    resolution = _get_scope_resolution(scope=scope)
    if resolution is not None:
        return resolution.snapshot

    shared_candidates = list(_get_shared_current_snapshot_candidates(scope=scope)[:2])
    if len(shared_candidates) == 0:
        return None

    snapshot = shared_candidates[0]
    if database is None:
        return snapshot
    return _adopt_scope_resolution_for_snapshot(
        scope=scope,
        database=database,
        snapshot=snapshot,
    )


def _adopt_scope_resolution_for_snapshot(
    *,
    scope: MetadataCatalogScope,
    database: Database,
    snapshot: PoolODataMetadataCatalogSnapshot,
) -> PoolODataMetadataCatalogSnapshot:
    with transaction.atomic():
        existing = _get_scope_resolution(scope=scope, for_update=True)
        if existing is not None:
            return existing.snapshot
        _upsert_scope_resolution(
            scope=scope,
            database=database,
            snapshot=snapshot,
            confirmed_at=snapshot.fetched_at,
            existing=None,
        )
        _sync_snapshot_current_marker(snapshot=snapshot)
    return snapshot


def _build_catalog_version(*, scope: MetadataCatalogScope, metadata_hash: str) -> str:
    fingerprint = "|".join(
        [
            "v1",
            scope.tenant_id,
            scope.config_name,
            scope.config_version,
            metadata_hash,
        ]
    )
    return f"v1:{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()[:16]}"


def _get_scope_resolution(
    *,
    scope: MetadataCatalogScope,
    for_update: bool = False,
) -> PoolODataMetadataCatalogScopeResolution | None:
    queryset = PoolODataMetadataCatalogScopeResolution.objects.select_related("snapshot")
    if for_update:
        queryset = queryset.select_for_update()
    return queryset.filter(**_resolution_filters(scope)).first()


def _upsert_scope_resolution(
    *,
    scope: MetadataCatalogScope,
    database: Database,
    snapshot: PoolODataMetadataCatalogSnapshot,
    confirmed_at: datetime,
    existing: PoolODataMetadataCatalogScopeResolution | None,
) -> PoolODataMetadataCatalogScopeResolution:
    if existing is None:
        return PoolODataMetadataCatalogScopeResolution.objects.create(
            tenant_id=scope.tenant_id,
            database=database,
            snapshot=snapshot,
            config_name=scope.config_name,
            config_version=scope.config_version,
            extensions_fingerprint=scope.extensions_fingerprint,
            confirmed_at=confirmed_at,
        )

    existing.database = database
    existing.snapshot = snapshot
    existing.config_name = scope.config_name
    existing.config_version = scope.config_version
    existing.extensions_fingerprint = scope.extensions_fingerprint
    existing.confirmed_at = confirmed_at
    existing.save(
        update_fields=[
            "database",
            "snapshot",
            "config_name",
            "config_version",
            "extensions_fingerprint",
            "confirmed_at",
            "updated_at",
        ]
    )
    return existing


def _sync_snapshot_current_marker(*, snapshot: PoolODataMetadataCatalogSnapshot) -> None:
    should_be_current = PoolODataMetadataCatalogScopeResolution.objects.filter(snapshot=snapshot).exists()
    if snapshot.is_current == should_be_current:
        return
    snapshot.is_current = should_be_current
    snapshot.save(update_fields=["is_current", "updated_at"])


def _resolve_metadata_mapping_credentials(
    *,
    database: Database,
    requested_by_username: str,
) -> tuple[str, str]:
    # Metadata catalog is a shared builder resource, so service mapping must be
    # used when configured. Actor mapping is fallback only.
    service_mappings = list(
        InfobaseUserMapping.objects.filter(
            database=database,
            is_service=True,
            user__isnull=True,
        ).only("ib_username", "ib_password", "id")[:2]
    )
    if len(service_mappings) > 1:
        raise MetadataCatalogError(
            code=ERROR_CODE_ODATA_MAPPING_AMBIGUOUS,
            title="Metadata Catalog Auth Configuration Error",
            detail="Ambiguous service infobase mapping. Configure mapping in /rbac.",
            status_code=400,
        )
    if len(service_mappings) == 1:
        mapping = service_mappings[0]
        username = str(mapping.ib_username or "").strip()
        password = str(mapping.ib_password or "").strip()
        if username and password:
            return username, password
        raise MetadataCatalogError(
            code=ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
            title="Metadata Catalog Auth Configuration Error",
            detail="Service infobase mapping credentials are incomplete. Configure mapping in /rbac.",
            status_code=400,
        )

    user_model = get_user_model()
    requested_by = user_model.objects.filter(username=str(requested_by_username or "").strip()).only("id").first()
    actor_queryset = InfobaseUserMapping.objects.filter(database=database, user=requested_by) if requested_by else None
    if actor_queryset is not None:
        actor_mappings = list(actor_queryset.only("ib_username", "ib_password", "id")[:2])
        if len(actor_mappings) > 1:
            raise MetadataCatalogError(
                code=ERROR_CODE_ODATA_MAPPING_AMBIGUOUS,
                title="Metadata Catalog Auth Configuration Error",
                detail="Ambiguous infobase mapping for actor credentials. Configure mapping in /rbac.",
                status_code=400,
            )
        if len(actor_mappings) == 1:
            mapping = actor_mappings[0]
            username = str(mapping.ib_username or "").strip()
            password = str(mapping.ib_password or "").strip()
            if username and password:
                return username, password
            raise MetadataCatalogError(
                code=ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
                title="Metadata Catalog Auth Configuration Error",
                detail="Infobase mapping credentials are incomplete. Configure mapping in /rbac.",
                status_code=400,
            )

    raise MetadataCatalogError(
        code=ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
        title="Metadata Catalog Auth Configuration Error",
        detail="Infobase mapping is not configured for metadata catalog path. Configure mapping in /rbac.",
        status_code=400,
    )


def _fetch_live_catalog_payload(*, database: Database, requested_by_username: str) -> dict[str, Any]:
    username, password = _resolve_metadata_mapping_credentials(
        database=database,
        requested_by_username=requested_by_username,
    )
    odata_base_url = str(database.odata_url or "").strip()
    parsed_url = urlparse(odata_base_url)
    if parsed_url.scheme not in {"http", "https"} or not str(parsed_url.netloc or "").strip():
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_FETCH_FAILED,
            title="Metadata Catalog Fetch Failed",
            detail="Database OData URL is not configured.",
            status_code=400,
        )
    if parsed_url.scheme == "http" and not _is_loopback_odata_host(parsed_url.hostname):
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_FETCH_FAILED,
            title="Metadata Catalog Fetch Failed",
            detail="Database OData URL must use HTTPS for non-local endpoints.",
            status_code=400,
            errors=[
                {
                    "code": ERROR_CODE_POOL_METADATA_FETCH_FAILED,
                    "path": "database.odata_url",
                    "detail": "Plain HTTP is allowed only for localhost/loopback endpoints.",
                }
            ],
        )

    try:
        with ODataMetadataAdapter(
            base_url=str(database.odata_url or ""),
            username=username,
            password=password,
            timeout=database.connection_timeout,
            verify_tls=resolve_database_odata_verify_tls(database=database),
        ) as metadata_adapter:
            response = metadata_adapter.fetch_metadata()
    except ODataMetadataTransportError as exc:
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_FETCH_FAILED,
            title="Metadata Catalog Fetch Failed",
            detail=f"Unable to fetch OData $metadata: {exc}",
            status_code=502,
            errors=[
                {
                    "code": ERROR_CODE_POOL_METADATA_FETCH_FAILED,
                    "path": "$metadata",
                    "detail": str(exc),
                }
            ],
        ) from exc

    if response.status_code in {401, 403}:
        upstream_detail = _extract_odata_error_detail(
            response_text=response.text,
            content_type=str(response.headers.get("Content-Type") or ""),
        )
        detail = "Infobase mapping credentials were rejected by OData endpoint."
        if upstream_detail:
            detail = f"{detail} Upstream error: {upstream_detail}"
        raise MetadataCatalogError(
            code=ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
            title="Metadata Catalog Auth Configuration Error",
            detail=detail,
            status_code=400,
            errors=[
                {
                    "code": ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
                    "path": "$metadata",
                    "detail": upstream_detail or "Infobase mapping credentials were rejected by OData endpoint.",
                }
            ],
        )
    if response.status_code >= 400:
        upstream_detail = _extract_odata_error_detail(
            response_text=response.text,
            content_type=str(response.headers.get("Content-Type") or ""),
        )
        detail = f"OData endpoint returned HTTP {response.status_code} for $metadata."
        error_detail = f"HTTP {response.status_code}"
        if upstream_detail:
            detail = f"{detail} Upstream error: {upstream_detail}"
            error_detail = upstream_detail
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_FETCH_FAILED,
            title="Metadata Catalog Fetch Failed",
            detail=detail,
            status_code=502,
            errors=[
                {
                    "code": ERROR_CODE_POOL_METADATA_FETCH_FAILED,
                    "path": "$metadata",
                    "detail": error_detail,
                }
            ],
        )

    try:
        raw_payload = _parse_csdl_metadata(response.text)
    except MetadataCatalogError:
        raise
    except Exception as exc:
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_PARSE_FAILED,
            title="Metadata Catalog Parse Failed",
            detail=f"Unable to parse OData $metadata payload: {exc}",
            status_code=502,
            errors=[
                {
                    "code": ERROR_CODE_POOL_METADATA_PARSE_FAILED,
                    "path": "$metadata",
                    "detail": str(exc),
                }
            ],
        ) from exc
    return normalize_catalog_payload(payload=raw_payload)


def _extract_odata_error_detail(*, response_text: str, content_type: str) -> str:
    raw_text = str(response_text or "").lstrip("\ufeff").strip()
    if not raw_text:
        return ""

    candidates: list[str] = []
    lower_content_type = str(content_type or "").lower()
    if "json" in lower_content_type or raw_text.startswith("{") or raw_text.startswith("["):
        try:
            parsed = json.loads(raw_text)
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None:
            candidates.extend(_collect_upstream_error_messages(parsed))

    if not candidates:
        fallback = _normalize_error_text(raw_text)
        if fallback:
            candidates.append(fallback)

    normalized: list[str] = []
    for item in candidates:
        text = _normalize_error_text(item)
        if not text:
            continue
        if text not in normalized:
            normalized.append(text)
        if len(normalized) >= MAX_UPSTREAM_ERROR_MESSAGES:
            break

    if not normalized:
        return ""

    merged = " | ".join(normalized)
    if len(merged) > MAX_UPSTREAM_ERROR_DETAIL_LENGTH:
        return f"{merged[:MAX_UPSTREAM_ERROR_DETAIL_LENGTH - 3]}..."
    return merged


def _collect_upstream_error_messages(node: Any, *, depth: int = 0) -> list[str]:
    if depth > 5:
        return []

    messages: list[str] = []
    if isinstance(node, Mapping):
        for raw_key, value in node.items():
            key = str(raw_key or "").strip().lower().lstrip("#")
            if not key:
                continue
            if key in {"data", "debug", "trace", "stack", "stacktrace"}:
                continue
            if key in {"message", "detail", "descr", "description", "title"} and isinstance(
                value, (str, int, float, bool)
            ):
                text = str(value).strip()
                if text:
                    messages.append(text)
            if isinstance(value, Mapping | list):
                messages.extend(_collect_upstream_error_messages(value, depth=depth + 1))
    elif isinstance(node, list):
        for item in node[:20]:
            messages.extend(_collect_upstream_error_messages(item, depth=depth + 1))
    return messages


def _normalize_error_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _is_loopback_odata_host(hostname: str | None) -> bool:
    normalized = str(hostname or "").strip().lower()
    if not normalized:
        return False
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _parse_csdl_metadata(xml_payload: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(xml_payload)
    except ET.ParseError as exc:
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_PARSE_FAILED,
            title="Metadata Catalog Parse Failed",
            detail=f"OData $metadata XML is invalid: {exc}",
            status_code=502,
        ) from exc

    entity_models: dict[str, dict[str, Any]] = {}
    row_types: dict[str, list[dict[str, Any]]] = {}
    document_table_parts: dict[str, dict[str, str]] = {}
    entity_definitions: dict[str, dict[str, Any]] = {}
    published_entity_sets: dict[str, str] = {}
    bound_functions_by_entity: dict[str, list[dict[str, Any]]] = {}

    # Accept both OData v4 and legacy v3 CSDL namespaces.
    for entity_type in root.findall(".//{*}EntityType"):
        entity_name = str(entity_type.get("Name") or "").strip()
        if not entity_name:
            continue

        declared_members: list[dict[str, Any]] = []
        for tag_name in ("Property", "NavigationProperty"):
            for prop in entity_type.findall(f"{{*}}{tag_name}"):
                prop_name = str(prop.get("Name") or "").strip()
                if not prop_name:
                    continue
                declared_members.append(
                    {
                        "name": prop_name,
                        "type": str(prop.get("Type") or "").strip(),
                        "nullable": str(prop.get("Nullable", "true")).strip().lower() != "false",
                    }
                )

        entity_definitions[entity_name] = {
            "base_type": _extract_entity_name_from_type(str(entity_type.get("BaseType") or "").strip()),
            "members": declared_members,
        }

    for entity_name in entity_definitions.keys():
        resolved_members = _resolve_entity_members(
            entity_name=entity_name,
            entity_definitions=entity_definitions,
        )
        fields: list[dict[str, Any]] = []
        table_parts: dict[str, str] = {}
        for member in resolved_members:
            prop_name = str(member.get("name") or "").strip()
            if not prop_name:
                continue
            prop_type = str(member.get("type") or "").strip()
            nullable = bool(member.get("nullable", True))

            if prop_type.startswith("Collection("):
                row_entity_name = _extract_entity_name_from_type(prop_type)
                if row_entity_name and row_entity_name.endswith("_RowType"):
                    table_part_name = _derive_table_part_name(
                        document_entity_name=entity_name,
                        row_entity_name=row_entity_name,
                        fallback=prop_name,
                    )
                    table_parts[table_part_name] = row_entity_name
                continue

            fields.append(
                {
                    "name": prop_name,
                    "type": prop_type,
                    "nullable": nullable,
                }
            )

        normalized_fields = _normalize_field_items(fields)
        entity_models[entity_name] = {
            "entity_name": entity_name,
            "display_name": entity_name,
            "fields": normalized_fields,
        }
        if entity_name.endswith("_RowType"):
            row_types[entity_name] = normalized_fields
        elif entity_name.startswith("Document_"):
            document_table_parts[entity_name] = table_parts

    for entity_set in root.findall(".//{*}EntitySet"):
        entity_set_name = str(entity_set.get("Name") or "").strip()
        entity_type_name = _extract_entity_name_from_type(str(entity_set.get("EntityType") or "").strip())
        if entity_set_name and entity_type_name:
            published_entity_sets[entity_set_name] = entity_type_name

    for function_import in root.findall(".//{*}FunctionImport"):
        function_name = str(function_import.get("Name") or "").strip()
        if not function_name:
            continue
        parameters: list[dict[str, str]] = []
        binding_entity_name = ""
        for parameter in function_import.findall("{*}Parameter"):
            parameter_name = str(parameter.get("Name") or "").strip()
            parameter_type = str(parameter.get("Type") or "").strip()
            if not parameter_name or not parameter_type:
                continue
            if parameter_name == "bindingParameter":
                binding_entity_name = _extract_entity_name_from_type(parameter_type)
                continue
            parameters.append(
                {
                    "name": parameter_name,
                    "type": parameter_type,
                }
            )
        if not binding_entity_name:
            continue
        bound_functions_by_entity.setdefault(binding_entity_name, []).append(
            {
                "name": function_name,
                "return_type": str(function_import.get("ReturnType") or "").strip(),
                "parameters": parameters,
            }
        )

    documents: list[dict[str, Any]] = []
    for entity_name in _resolve_catalog_entity_names(
        entity_models=entity_models,
        published_entity_sets=published_entity_sets,
        prefix="Document_",
    ):
        document_model = entity_models.get(entity_name)
        if not isinstance(document_model, Mapping):
            continue
        table_parts: list[dict[str, Any]] = []

        explicit_table_parts = document_table_parts.get(entity_name, {})
        for table_part_name, row_entity_name in explicit_table_parts.items():
            table_parts.append(
                {
                    "name": table_part_name,
                    "row_fields": row_types.get(row_entity_name, []),
                }
            )

        inferred_row_types = [
            row_entity_name
            for row_entity_name in row_types.keys()
            if row_entity_name.startswith(f"{entity_name}_")
        ]
        for row_entity_name in inferred_row_types:
            inferred_table_part_name = _derive_table_part_name(
                document_entity_name=entity_name,
                row_entity_name=row_entity_name,
                fallback=row_entity_name,
            )
            if any(str(item.get("name") or "") == inferred_table_part_name for item in table_parts):
                continue
            table_parts.append(
                {
                    "name": inferred_table_part_name,
                    "row_fields": row_types.get(row_entity_name, []),
                }
            )

        documents.append(
            {
                "entity_name": entity_name,
                "display_name": str(document_model.get("display_name") or entity_name),
                "fields": document_model.get("fields") or [],
                "table_parts": _normalize_table_parts(table_parts),
            }
        )

    documents.sort(key=lambda item: str(item.get("entity_name") or ""))
    information_registers = _build_catalog_entities(
        entity_models=entity_models,
        published_entity_sets=published_entity_sets,
        prefix="InformationRegister_",
    )
    accounting_registers = _build_register_entities(
        entity_models=entity_models,
        published_entity_sets=published_entity_sets,
        prefix="AccountingRegister_",
        functions_by_entity=bound_functions_by_entity,
    )
    return {
        "documents": documents,
        "information_registers": information_registers,
        "accounting_registers": accounting_registers,
    }


def _resolve_entity_members(
    *,
    entity_name: str,
    entity_definitions: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    lineage: list[Mapping[str, Any]] = []
    visited: set[str] = set()
    current_name = entity_name

    while current_name and current_name not in visited:
        visited.add(current_name)
        definition = entity_definitions.get(current_name)
        if not isinstance(definition, Mapping):
            break
        lineage.append(definition)
        base_type = _extract_entity_name_from_type(str(definition.get("base_type") or "").strip())
        if not base_type or base_type == current_name:
            break
        current_name = base_type

    merged_by_name: dict[str, dict[str, Any]] = {}
    for definition in reversed(lineage):
        members = definition.get("members")
        if not isinstance(members, list):
            continue
        for member in members:
            if not isinstance(member, Mapping):
                continue
            name = str(member.get("name") or "").strip()
            if not name:
                continue
            merged_by_name[name] = {
                "name": name,
                "type": str(member.get("type") or "").strip(),
                "nullable": bool(member.get("nullable", True)),
            }
    return list(merged_by_name.values())


def _extract_entity_name_from_type(type_token: str) -> str:
    token = str(type_token or "").strip()
    if not token:
        return ""
    if token.startswith("Collection(") and token.endswith(")"):
        token = token[len("Collection("):-1].strip()
    if "." in token:
        token = token.split(".")[-1]
    return token.strip()


def _derive_table_part_name(
    *,
    document_entity_name: str,
    row_entity_name: str,
    fallback: str,
) -> str:
    prefix = f"{document_entity_name}_"
    suffix = "_RowType"
    if row_entity_name.startswith(prefix) and row_entity_name.endswith(suffix):
        table_part_name = row_entity_name[len(prefix):-len(suffix)].strip("_")
        if table_part_name:
            return table_part_name
    return str(fallback or row_entity_name).strip() or row_entity_name


def _normalize_field_items(raw_fields: object) -> list[dict[str, Any]]:
    if not isinstance(raw_fields, list):
        return []
    normalized_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in raw_fields:
        if not isinstance(raw_item, Mapping):
            continue
        name = str(raw_item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized_items.append(
            {
                "name": name,
                "type": str(raw_item.get("type") or "").strip(),
                "nullable": bool(raw_item.get("nullable", True)),
            }
        )
    normalized_items.sort(key=lambda item: item["name"])
    return normalized_items


def _normalize_table_parts(raw_table_parts: object) -> list[dict[str, Any]]:
    if not isinstance(raw_table_parts, list):
        return []
    normalized_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in raw_table_parts:
        if not isinstance(raw_item, Mapping):
            continue
        name = str(raw_item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized_items.append(
            {
                "name": name,
                "row_fields": _normalize_field_items(raw_item.get("row_fields")),
            }
        )
    normalized_items.sort(key=lambda item: item["name"])
    return normalized_items


def _normalize_catalog_entities(raw_entities: object) -> list[dict[str, Any]]:
    if not isinstance(raw_entities, list):
        return []
    normalized_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in raw_entities:
        if not isinstance(raw_item, Mapping):
            continue
        entity_name = str(raw_item.get("entity_name") or "").strip()
        if not entity_name or entity_name in seen:
            continue
        seen.add(entity_name)
        normalized_items.append(
            {
                "entity_name": entity_name,
                "display_name": str(raw_item.get("display_name") or entity_name).strip() or entity_name,
                "fields": _normalize_field_items(raw_item.get("fields")),
            }
        )
    normalized_items.sort(key=lambda item: item["entity_name"])
    return normalized_items


def _normalize_register_entities(raw_entities: object) -> list[dict[str, Any]]:
    if not isinstance(raw_entities, list):
        return []
    normalized_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in raw_entities:
        if not isinstance(raw_item, Mapping):
            continue
        entity_name = str(raw_item.get("entity_name") or "").strip()
        if not entity_name or entity_name in seen:
            continue
        seen.add(entity_name)
        normalized_items.append(
            {
                "entity_name": entity_name,
                "display_name": str(raw_item.get("display_name") or entity_name).strip() or entity_name,
                "fields": _normalize_field_items(raw_item.get("fields")),
                "functions": _normalize_function_items(raw_item.get("functions")),
            }
        )
    normalized_items.sort(key=lambda item: item["entity_name"])
    return normalized_items


def _normalize_function_items(raw_functions: object) -> list[dict[str, Any]]:
    if not isinstance(raw_functions, list):
        return []
    normalized_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in raw_functions:
        if not isinstance(raw_item, Mapping):
            continue
        name = str(raw_item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized_items.append(
            {
                "name": name,
                "return_type": str(raw_item.get("return_type") or "").strip(),
                "parameters": _normalize_function_parameters(raw_item.get("parameters")),
            }
        )
    normalized_items.sort(key=lambda item: item["name"])
    return normalized_items


def _normalize_function_parameters(raw_parameters: object) -> list[dict[str, str]]:
    if not isinstance(raw_parameters, list):
        return []
    normalized_items: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_item in raw_parameters:
        if not isinstance(raw_item, Mapping):
            continue
        name = str(raw_item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized_items.append(
            {
                "name": name,
                "type": str(raw_item.get("type") or "").strip(),
            }
        )
    normalized_items.sort(key=lambda item: item["name"])
    return normalized_items


def _build_catalog_entities(
    *,
    entity_models: Mapping[str, Mapping[str, Any]],
    published_entity_sets: Mapping[str, str],
    prefix: str,
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for entity_name in _resolve_catalog_entity_names(
        entity_models=entity_models,
        published_entity_sets=published_entity_sets,
        prefix=prefix,
    ):
        entity_model = entity_models.get(entity_name)
        if not isinstance(entity_model, Mapping):
            continue
        entities.append(
            {
                "entity_name": entity_name,
                "display_name": str(entity_model.get("display_name") or entity_name),
                "fields": entity_model.get("fields") or [],
            }
        )
    entities.sort(key=lambda item: str(item.get("entity_name") or ""))
    return entities


def _build_register_entities(
    *,
    entity_models: Mapping[str, Mapping[str, Any]],
    published_entity_sets: Mapping[str, str],
    prefix: str,
    functions_by_entity: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for entity_name in _resolve_catalog_entity_names(
        entity_models=entity_models,
        published_entity_sets=published_entity_sets,
        prefix=prefix,
    ):
        entity_model = entity_models.get(entity_name)
        if not isinstance(entity_model, Mapping):
            continue
        entities.append(
            {
                "entity_name": entity_name,
                "display_name": str(entity_model.get("display_name") or entity_name),
                "fields": entity_model.get("fields") or [],
                "functions": functions_by_entity.get(entity_name) or [],
            }
        )
    entities.sort(key=lambda item: str(item.get("entity_name") or ""))
    return entities


def _resolve_catalog_entity_names(
    *,
    entity_models: Mapping[str, Mapping[str, Any]],
    published_entity_sets: Mapping[str, str],
    prefix: str,
) -> list[str]:
    resolved_names = sorted(
        entity_name
        for entity_name in published_entity_sets.values()
        if entity_name.startswith(prefix)
    )
    if resolved_names:
        return resolved_names
    return sorted(
        entity_name
        for entity_name in entity_models.keys()
        if entity_name.startswith(prefix) and not _is_derived_catalog_entity_name(entity_name=entity_name)
    )


def _is_derived_catalog_entity_name(*, entity_name: str) -> bool:
    return entity_name.endswith(
        (
            "_RowType",
            "_Balance",
            "_Turnover",
            "_BalanceAndTurnover",
            "_ExtDimensions",
            "_RecordsWithExtDimensions",
            "_DrCrTurnover",
        )
    )


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _build_cache_key(*, scope: MetadataCatalogScope) -> str:
    scope_hash = hashlib.sha256(
        "|".join(
            [
                scope.config_name,
                scope.config_version,
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"{DEFAULT_CACHE_KEY_PREFIX}:{scope.tenant_id}:{scope.database_id}:{scope_hash}"


def _get_cache_ttl_seconds() -> int:
    try:
        return max(int(getattr(settings, "POOL_ODATA_METADATA_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS)), 1)
    except (TypeError, ValueError):
        return DEFAULT_CACHE_TTL_SECONDS


def _get_redis_client() -> redis.Redis:
    redis_password = getattr(settings, "REDIS_PASSWORD", None)
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=int(settings.REDIS_PORT),
        db=int(settings.REDIS_DB),
        password=redis_password if redis_password else None,
        decode_responses=True,
        socket_timeout=2,
    )


def _write_snapshot_to_cache(*, scope: MetadataCatalogScope, snapshot: PoolODataMetadataCatalogSnapshot) -> None:
    cache_payload = {
        "scope": {
            "tenant_id": scope.tenant_id,
            "database_id": scope.database_id,
            "config_name": scope.config_name,
            "config_version": scope.config_version,
            "extensions_fingerprint": scope.extensions_fingerprint,
        },
        "snapshot": {
            "id": str(snapshot.id),
            "tenant_id": str(snapshot.tenant_id),
            "database_id": str(snapshot.database_id),
            "config_name": snapshot.config_name,
            "config_version": snapshot.config_version,
            "extensions_fingerprint": snapshot.extensions_fingerprint,
            "metadata_hash": snapshot.metadata_hash,
            "catalog_version": snapshot.catalog_version,
            "payload": snapshot.payload if isinstance(snapshot.payload, dict) else {},
            "source": snapshot.source,
            "fetched_at": snapshot.fetched_at.isoformat(),
            "is_current": bool(snapshot.is_current),
        },
    }
    key = _build_cache_key(scope=scope)
    client: redis.Redis | None = None
    try:
        client = _get_redis_client()
        client.setex(key, _get_cache_ttl_seconds(), json.dumps(cache_payload, ensure_ascii=False))
    except Exception:
        return
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _read_snapshot_from_cache(*, scope: MetadataCatalogScope) -> PoolODataMetadataCatalogSnapshot | None:
    key = _build_cache_key(scope=scope)
    client: redis.Redis | None = None
    try:
        client = _get_redis_client()
        raw_value = client.get(key)
    except Exception:
        return None
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    if not raw_value:
        return None
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, Mapping):
        return None
    cached_scope_raw = parsed.get("scope")
    if not isinstance(cached_scope_raw, Mapping):
        return None
    snapshot_raw = parsed.get("snapshot")
    if not isinstance(snapshot_raw, Mapping):
        return None

    if str(cached_scope_raw.get("tenant_id") or "") != scope.tenant_id:
        return None
    if str(cached_scope_raw.get("database_id") or "") != scope.database_id:
        return None
    if str(cached_scope_raw.get("config_name") or "") != scope.config_name:
        return None
    if str(cached_scope_raw.get("config_version") or "") != scope.config_version:
        return None
    if str(snapshot_raw.get("tenant_id") or "") != scope.tenant_id:
        return None

    snapshot_id = str(snapshot_raw.get("id") or "").strip()
    if not snapshot_id:
        return None
    try:
        snapshot_uuid = UUID(snapshot_id)
    except (TypeError, ValueError):
        return None
    return PoolODataMetadataCatalogSnapshot(
        id=snapshot_uuid,
        tenant_id=scope.tenant_id,
        database_id=str(snapshot_raw.get("database_id") or "").strip() or scope.database_id,
        config_name=scope.config_name,
        config_version=scope.config_version,
        extensions_fingerprint=scope.extensions_fingerprint,
        metadata_hash=str(snapshot_raw.get("metadata_hash") or "").strip(),
        catalog_version=str(snapshot_raw.get("catalog_version") or "").strip(),
        payload=snapshot_raw.get("payload") if isinstance(snapshot_raw.get("payload"), dict) else {},
        source=str(snapshot_raw.get("source") or PoolODataMetadataCatalogSnapshotSource.LIVE_REFRESH),
        fetched_at=_parse_iso_datetime(snapshot_raw.get("fetched_at")) or timezone.now(),
        is_current=bool(snapshot_raw.get("is_current", True)),
    )


def _parse_iso_datetime(raw: object) -> datetime | None:
    token = str(raw or "").strip()
    if not token:
        return None
    normalized = token[:-1] + "+00:00" if token.endswith("Z") else token
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _resolve_business_configuration_profile(
    *,
    database: Database,
    materialize_legacy: bool = True,
    include_legacy_snapshot_profile: bool = True,
) -> dict[str, Any] | None:
    profile = get_business_configuration_profile(database=database)
    if profile is not None:
        return profile
    legacy_profile = _build_business_configuration_profile_from_existing_snapshot(database=database)
    if legacy_profile is None:
        return None
    if materialize_legacy:
        return persist_business_configuration_profile(
            database=database,
            profile=legacy_profile,
        )
    if include_legacy_snapshot_profile:
        return legacy_profile
    return None


def _build_business_configuration_profile_from_existing_snapshot(
    *,
    database: Database,
) -> dict[str, Any] | None:
    resolution = (
        PoolODataMetadataCatalogScopeResolution.objects.select_related("snapshot")
        .filter(database=database)
        .order_by("-confirmed_at", "-updated_at", "-created_at")
        .first()
    )
    snapshot = resolution.snapshot if resolution is not None else None
    if snapshot is None:
        snapshot = (
            PoolODataMetadataCatalogSnapshot.objects.filter(database=database, is_current=True)
            .order_by("-fetched_at", "-created_at")
            .first()
        )
    if snapshot is None:
        return None

    config_name = str(snapshot.config_name or "").strip()
    config_version = str(snapshot.config_version or "").strip()
    if not config_name or not config_version:
        return None

    return {
        "config_name": config_name,
        "config_root_name": config_name,
        "config_version": config_version,
        "config_name_source": "legacy_snapshot",
        "verification_status": "migrated_legacy",
        "verified_at": snapshot.fetched_at,
        "observed_metadata_hash": snapshot.metadata_hash,
        "canonical_metadata_hash": snapshot.metadata_hash,
        "publication_drift": False,
        "observed_metadata_fetched_at": snapshot.fetched_at,
    }


def _backfill_business_configuration_profile_from_existing_snapshot(
    *,
    database: Database,
) -> dict[str, Any] | None:
    profile = _build_business_configuration_profile_from_existing_snapshot(database=database)
    if profile is None:
        return None
    return persist_business_configuration_profile(database=database, profile=profile)


def _get_shared_current_snapshot_candidates(*, scope: MetadataCatalogScope):
    return (
        PoolODataMetadataCatalogSnapshot.objects.filter(
            **_shared_scope_filters(scope),
            is_current=True,
        )
        .order_by("-fetched_at", "-created_at")
    )


def _get_shared_current_snapshot(
    *,
    scope: MetadataCatalogScope,
    for_update: bool = False,
) -> PoolODataMetadataCatalogSnapshot | None:
    queryset = _get_shared_current_snapshot_candidates(scope=scope)
    if for_update:
        queryset = queryset.select_for_update()
    return queryset.first()


def _shared_snapshot_has_peer_resolution(
    *,
    snapshot: PoolODataMetadataCatalogSnapshot,
    database: Database,
) -> bool:
    return (
        PoolODataMetadataCatalogScopeResolution.objects.filter(snapshot=snapshot)
        .exclude(database_id=database.id)
        .exists()
    )
