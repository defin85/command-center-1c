from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import redis
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.databases.models import Database, DatabaseExtensionsSnapshot, InfobaseUserMapping

from .models import (
    PoolODataMetadataCatalogSnapshot,
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


def resolve_metadata_catalog_scope(*, tenant_id: str, database: Database) -> MetadataCatalogScope:
    config_name = str(
        database.base_name
        or database.infobase_name
        or database.name
        or database.id
        or ""
    ).strip()
    config_version = str(database.version or "").strip()

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


def read_metadata_catalog_snapshot(
    *,
    tenant_id: str,
    database: Database,
    requested_by_username: str,
    allow_cold_bootstrap: bool = True,
) -> tuple[PoolODataMetadataCatalogSnapshot, str]:
    # Metadata catalog path is mapping-only for both read and refresh requests.
    # Validate auth configuration before serving cached/snapshotted data.
    _resolve_metadata_mapping_credentials(
        database=database,
        requested_by_username=requested_by_username,
    )
    scope = resolve_metadata_catalog_scope(tenant_id=tenant_id, database=database)
    cached_snapshot = _read_snapshot_from_cache(scope=scope)
    if cached_snapshot is not None:
        return cached_snapshot, SOURCE_REDIS

    current_snapshot = _get_current_snapshot(scope=scope)
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

            scope_filters = _scope_filters(scope=scope)
            current_qs = PoolODataMetadataCatalogSnapshot.objects.select_for_update().filter(
                **scope_filters,
                is_current=True,
            )
            existing_version = (
                PoolODataMetadataCatalogSnapshot.objects.select_for_update()
                .filter(**scope_filters, catalog_version=catalog_version)
                .first()
            )

            if existing_version is not None:
                current_qs.exclude(id=existing_version.id).update(is_current=False, updated_at=now)
                existing_version.metadata_hash = metadata_hash
                existing_version.payload = catalog_payload
                existing_version.source = source
                existing_version.fetched_at = now
                existing_version.is_current = True
                existing_version.save(
                    update_fields=[
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
                current_qs.update(is_current=False, updated_at=now)
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
    except MetadataCatalogError:
        raise

    _write_snapshot_to_cache(scope=scope, snapshot=snapshot)
    return snapshot


def get_current_snapshot_for_database_scope(
    *,
    tenant_id: str,
    database: Database,
) -> PoolODataMetadataCatalogSnapshot | None:
    scope = resolve_metadata_catalog_scope(tenant_id=tenant_id, database=database)
    return _get_current_snapshot(scope=scope)


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

    payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
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
        return {"documents": []}

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

    normalized_documents.sort(key=lambda item: str(item.get("entity_name") or ""))
    return {"documents": normalized_documents}


def _scope_filters(scope: MetadataCatalogScope) -> dict[str, str]:
    return {
        "tenant_id": scope.tenant_id,
        "database_id": scope.database_id,
        "config_name": scope.config_name,
        "config_version": scope.config_version,
        "extensions_fingerprint": scope.extensions_fingerprint,
    }


def _get_current_snapshot(*, scope: MetadataCatalogScope) -> PoolODataMetadataCatalogSnapshot | None:
    return (
        PoolODataMetadataCatalogSnapshot.objects.filter(**_scope_filters(scope), is_current=True)
        .order_by("-fetched_at", "-created_at")
        .first()
    )


def _build_catalog_version(*, scope: MetadataCatalogScope, metadata_hash: str) -> str:
    fingerprint = "|".join(
        [
            "v1",
            scope.tenant_id,
            scope.database_id,
            scope.config_name,
            scope.config_version,
            scope.extensions_fingerprint,
            metadata_hash,
        ]
    )
    return f"v1:{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()[:16]}"


def _resolve_metadata_mapping_credentials(
    *,
    database: Database,
    requested_by_username: str,
) -> tuple[str, str]:
    user_model = get_user_model()
    requested_by = user_model.objects.filter(username=str(requested_by_username or "").strip()).only("id").first()

    actor_queryset = InfobaseUserMapping.objects.filter(database=database, user=requested_by) if requested_by else None
    if actor_queryset is not None:
        actor_mappings = list(actor_queryset.only("ib_username", "ib_password", "id"))
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

    service_mappings = list(
        InfobaseUserMapping.objects.filter(
            database=database,
            is_service=True,
            user__isnull=True,
        ).only("ib_username", "ib_password", "id")
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
    metadata_url = f"{str(database.odata_url or '').rstrip('/')}/$metadata"
    if not metadata_url.startswith("http"):
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_FETCH_FAILED,
            title="Metadata Catalog Fetch Failed",
            detail="Database OData URL is not configured.",
            status_code=400,
        )

    try:
        username.encode("latin-1")
        password.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise MetadataCatalogError(
            code=ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
            title="Metadata Catalog Auth Configuration Error",
            detail=(
                "Infobase mapping credentials contain characters unsupported by HTTP Basic auth "
                "(latin-1). Configure mapping in /rbac."
            ),
            status_code=400,
        ) from exc

    try:
        response = requests.get(
            metadata_url,
            headers={"Accept": "application/xml"},
            auth=(username, password),
            timeout=(5, 30),
        )
    except requests.RequestException as exc:
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_FETCH_FAILED,
            title="Metadata Catalog Fetch Failed",
            detail=f"Unable to fetch OData $metadata: {exc}",
            status_code=502,
        ) from exc

    if response.status_code in {401, 403}:
        raise MetadataCatalogError(
            code=ERROR_CODE_ODATA_MAPPING_NOT_CONFIGURED,
            title="Metadata Catalog Auth Configuration Error",
            detail="Infobase mapping credentials were rejected by OData endpoint.",
            status_code=400,
        )
    if response.status_code >= 400:
        upstream_detail = _extract_odata_error_detail(
            response_text=response.text,
            content_type=str(response.headers.get("Content-Type") or ""),
        )
        detail = f"OData endpoint returned HTTP {response.status_code} for $metadata."
        errors: list[dict[str, Any]] = []
        if upstream_detail:
            detail = f"{detail} Upstream error: {upstream_detail}"
            errors.append(
                {
                    "code": ERROR_CODE_POOL_METADATA_FETCH_FAILED,
                    "path": "$metadata",
                    "detail": upstream_detail,
                }
            )
        raise MetadataCatalogError(
            code=ERROR_CODE_POOL_METADATA_FETCH_FAILED,
            title="Metadata Catalog Fetch Failed",
            detail=detail,
            status_code=502,
            errors=errors,
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

    documents: list[dict[str, Any]] = []
    for entity_name, document_model in entity_models.items():
        if not entity_name.startswith("Document_") or entity_name.endswith("_RowType"):
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
    return {"documents": documents}


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


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _build_cache_key(*, scope: MetadataCatalogScope) -> str:
    scope_hash = hashlib.sha256(
        "|".join(
            [
                scope.config_name,
                scope.config_version,
                scope.extensions_fingerprint,
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
    snapshot_raw = parsed.get("snapshot")
    if not isinstance(snapshot_raw, Mapping):
        return None

    if str(snapshot_raw.get("tenant_id") or "") != scope.tenant_id:
        return None
    if str(snapshot_raw.get("database_id") or "") != scope.database_id:
        return None
    if str(snapshot_raw.get("config_name") or "") != scope.config_name:
        return None
    if str(snapshot_raw.get("config_version") or "") != scope.config_version:
        return None
    if str(snapshot_raw.get("extensions_fingerprint") or "") != scope.extensions_fingerprint:
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
        database_id=scope.database_id,
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
