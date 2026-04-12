from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from django.db import transaction
from django.utils import timezone

from apps.databases.models import Database, InfobaseUserMapping
from apps.databases.odata import ODataClient, resolve_database_odata_verify_tls

from .master_data_sync_inbound_poller import (
    MasterDataSyncInboundChange,
    MasterDataSyncSelectChangesResult,
)
from .master_data_sync_outbox import build_master_data_mutation_payload_fingerprint
from .master_data_registry import normalize_pool_master_data_entity_type
from .models import PoolMasterDataEntityType, PoolMasterDataSyncCheckpoint, PoolMasterDataSyncOutbox


MASTER_DATA_SYNC_ODATA_DATABASE_NOT_FOUND = "MASTER_DATA_SYNC_ODATA_DATABASE_NOT_FOUND"
MASTER_DATA_SYNC_ODATA_MAPPING_NOT_CONFIGURED = "MASTER_DATA_SYNC_ODATA_MAPPING_NOT_CONFIGURED"
MASTER_DATA_SYNC_ODATA_MAPPING_AMBIGUOUS = "MASTER_DATA_SYNC_ODATA_MAPPING_AMBIGUOUS"
MASTER_DATA_SYNC_ODATA_URL_MISSING = "MASTER_DATA_SYNC_ODATA_URL_MISSING"
MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED = "MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED"
MASTER_DATA_SYNC_ODATA_ITEM_KIND_MISSING = "MASTER_DATA_SYNC_ODATA_ITEM_KIND_MISSING"
MASTER_DATA_SYNC_ODATA_ITEM_APPLY_FAILED = "MASTER_DATA_SYNC_ODATA_ITEM_APPLY_FAILED"
MASTER_DATA_SYNC_ODATA_ITEM_REF_MISSING = "MASTER_DATA_SYNC_ODATA_ITEM_REF_MISSING"

_FULL_SCAN_COMMITTED_VERSIONS_KEY = "live_full_scan_committed_versions"
_FULL_SCAN_PENDING_VERSIONS_KEY = "live_full_scan_pending_versions"
_FULL_SCAN_TRANSPORT_KEY = "live_full_scan_transport"
_FULL_SCAN_LAST_SCAN_AT_KEY = "live_full_scan_last_scan_at"
_FULL_SCAN_LAST_COMMITTED_AT_KEY = "live_full_scan_last_committed_at"

_ITEM_ENTITY_NAME = "Catalog_Номенклатура"
_ITEM_KIND_ENTITY_NAME = "Catalog_ВидыНоменклатуры"
_ITEM_PAGE_SIZE = 500
_ZERO_GUID = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True)
class MasterDataSyncLiveODataError(RuntimeError):
    code: str
    detail: str

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, f"{self.code}: {self.detail}")


@dataclass(frozen=True)
class _ResolvedServiceCredentials:
    username: str
    password: str


def select_changes_from_live_odata(
    *,
    checkpoint_token: str,
    tenant_id: str,
    database_id: str,
    entity_type: str,
) -> MasterDataSyncSelectChangesResult:
    database = _resolve_database(tenant_id=tenant_id, database_id=database_id)
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    if normalized_entity_type != PoolMasterDataEntityType.ITEM:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED,
            detail=f"Live OData inbound transport does not support entity '{normalized_entity_type}'.",
        )

    current_rows = _fetch_live_item_rows(database=database)
    current_versions = {
        _row_ref_key(row): _build_row_version_token(row)
        for row in current_rows
        if _row_ref_key(row)
    }
    committed_versions = _read_checkpoint_versions(
        tenant_id=tenant_id,
        database_id=database_id,
        entity_type=normalized_entity_type,
        metadata_key=_FULL_SCAN_COMMITTED_VERSIONS_KEY,
    )
    changes: list[MasterDataSyncInboundChange] = []
    if committed_versions:
        for row in current_rows:
            ref_key = _row_ref_key(row)
            if not ref_key:
                continue
            current_version = current_versions.get(ref_key, "")
            if committed_versions.get(ref_key) == current_version:
                continue
            changes.append(
                _build_item_inbound_change(
                    database=database,
                    row=row,
                    entity_type=normalized_entity_type,
                )
            )

    scan_token = f"full-scan:{len(current_versions)}:{timezone.now().isoformat()}"
    _store_pending_versions(
        tenant_id=tenant_id,
        database_id=database_id,
        entity_type=normalized_entity_type,
        versions=current_versions,
        scan_token=scan_token,
    )
    return MasterDataSyncSelectChangesResult(
        changes=changes,
        source_checkpoint_token=str(checkpoint_token or ""),
        next_checkpoint_token=scan_token,
    )


def notify_changes_received_from_live_odata(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    checkpoint_token: str,
    next_checkpoint_token: str,
) -> dict[str, Any]:
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    with transaction.atomic():
        checkpoint = (
            PoolMasterDataSyncCheckpoint.objects.select_for_update()
            .filter(
                tenant_id=str(tenant_id or "").strip(),
                database_id=str(database_id or "").strip(),
                entity_type=normalized_entity_type,
            )
            .first()
        )
        if checkpoint is None:
            raise MasterDataSyncLiveODataError(
                code=MASTER_DATA_SYNC_ODATA_DATABASE_NOT_FOUND,
                detail=(
                    "Checkpoint scope is missing while acknowledging live OData inbound transport "
                    f"for database '{database_id}'."
                ),
            )
        metadata = dict(checkpoint.metadata or {})
        pending_versions = metadata.pop(_FULL_SCAN_PENDING_VERSIONS_KEY, None)
        if isinstance(pending_versions, Mapping):
            metadata[_FULL_SCAN_COMMITTED_VERSIONS_KEY] = {
                str(key or "").strip(): str(value or "").strip()
                for key, value in pending_versions.items()
                if str(key or "").strip()
            }
        metadata[_FULL_SCAN_LAST_COMMITTED_AT_KEY] = timezone.now().isoformat()
        checkpoint.metadata = metadata
        checkpoint.save(update_fields=["metadata", "updated_at"])
    return {
        "status": "acknowledged",
        "transport": "odata_catalog_full_scan",
        "checkpoint_token": str(checkpoint_token or ""),
        "next_checkpoint_token": str(next_checkpoint_token or ""),
    }


def apply_outbox_to_live_odata(
    *,
    outbox: PoolMasterDataSyncOutbox,
) -> dict[str, Any]:
    database = outbox.database
    mutation = dict(outbox.payload or {})
    mutation_kind = str(mutation.get("mutation_kind") or "").strip()
    if str(outbox.entity_type) != PoolMasterDataEntityType.ITEM or mutation_kind != "item_upsert":
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED,
            detail=(
                "Live OData outbound transport currently supports only "
                f"item_upsert; got entity='{outbox.entity_type}' mutation='{mutation_kind}'."
            ),
        )

    payload = dict(mutation.get("payload") or {})
    canonical_id = str(payload.get("canonical_id") or mutation.get("canonical_id") or "").strip()
    if not canonical_id:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_ITEM_APPLY_FAILED,
            detail="Outbound item_upsert payload must include canonical_id.",
        )
    item_name = str(payload.get("name") or "").strip()
    if not item_name:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_ITEM_APPLY_FAILED,
            detail=f"Outbound item_upsert '{canonical_id}' must include non-empty name.",
        )

    metadata = payload.get("metadata")
    payload_metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
    entity_payload = _build_item_entity_payload(
        database=database,
        canonical_id=canonical_id,
        payload=payload,
        payload_metadata=payload_metadata,
    )

    with _build_odata_client(database=database) as client:
        target_ref_key = _resolve_target_ref_key(
            client=client,
            payload=payload,
            payload_metadata=payload_metadata,
            database_id=str(database.id),
        )
        if target_ref_key:
            client.update_entity(
                _ITEM_ENTITY_NAME,
                _guid_literal(target_ref_key),
                entity_payload,
            )
            applied_ref_key = target_ref_key
            created = False
        else:
            created_payload = client.create_entity(_ITEM_ENTITY_NAME, entity_payload)
            applied_ref_key = str(created_payload.get("Ref_Key") or "").strip()
            if not applied_ref_key:
                raise MasterDataSyncLiveODataError(
                    code=MASTER_DATA_SYNC_ODATA_ITEM_REF_MISSING,
                    detail=(
                        f"OData create for canonical item '{canonical_id}' did not return Ref_Key "
                        f"for database '{database.id}'."
                    ),
                )
            created = True

    return {
        "status": "applied",
        "created": created,
        "entity_name": _ITEM_ENTITY_NAME,
        "canonical_id": canonical_id,
        "ib_ref_key": applied_ref_key,
    }


def _resolve_database(*, tenant_id: str, database_id: str) -> Database:
    database = Database.objects.filter(id=str(database_id or "").strip(), tenant_id=str(tenant_id or "").strip()).first()
    if database is None:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_DATABASE_NOT_FOUND,
            detail=f"Database '{database_id}' is not available in tenant '{tenant_id}'.",
        )
    if not str(database.odata_url or "").strip():
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_URL_MISSING,
            detail=f"Database '{database.id}' is missing OData URL.",
        )
    return database


def _resolve_service_credentials(*, database: Database) -> _ResolvedServiceCredentials:
    mappings = list(
        InfobaseUserMapping.objects.filter(
            database=database,
            is_service=True,
            user__isnull=True,
        )
        .only("ib_username", "ib_password")
        .order_by("created_at", "id")[:2]
    )
    if len(mappings) > 1:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_MAPPING_AMBIGUOUS,
            detail=f"Multiple service InfobaseUserMapping rows found for database '{database.id}'.",
        )
    if len(mappings) != 1:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_MAPPING_NOT_CONFIGURED,
            detail=f"Service InfobaseUserMapping is not configured for database '{database.id}'.",
        )
    mapping = mappings[0]
    username = str(mapping.ib_username or "").strip()
    password = str(mapping.ib_password or "").strip()
    if not username or not password:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_MAPPING_NOT_CONFIGURED,
            detail=f"Service InfobaseUserMapping for database '{database.id}' is incomplete.",
        )
    return _ResolvedServiceCredentials(username=username, password=password)


def _build_odata_client(*, database: Database) -> ODataClient:
    credentials = _resolve_service_credentials(database=database)
    return ODataClient(
        base_url=str(database.odata_url or ""),
        username=credentials.username,
        password=credentials.password,
        timeout=database.connection_timeout,
        verify_tls=resolve_database_odata_verify_tls(database=database),
    )


def _fetch_live_item_rows(*, database: Database) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skip = 0
    with _build_odata_client(database=database) as client:
        while True:
            batch = client.get_entities(
                _ITEM_ENTITY_NAME,
                select_fields=[
                    "Ref_Key",
                    "DataVersion",
                    "Code",
                    "Description",
                    "Артикул",
                    "ВидНоменклатуры_Key",
                    "ЕдиницаИзмерения_Key",
                    "НаименованиеПолное",
                    "Комментарий",
                    "Услуга",
                    "DeletionMark",
                    "IsFolder",
                ],
                top=_ITEM_PAGE_SIZE,
                skip=skip,
            )
            normalized_batch = [
                dict(row)
                for row in batch
                if isinstance(row, Mapping)
                and not bool(row.get("DeletionMark"))
                and not bool(row.get("IsFolder"))
            ]
            rows.extend(normalized_batch)
            if len(batch) < _ITEM_PAGE_SIZE:
                break
            skip += len(batch)
    return rows


def _read_checkpoint_versions(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    metadata_key: str,
) -> dict[str, str]:
    checkpoint = (
        PoolMasterDataSyncCheckpoint.objects.filter(
            tenant_id=str(tenant_id or "").strip(),
            database_id=str(database_id or "").strip(),
            entity_type=str(entity_type or "").strip(),
        )
        .only("metadata")
        .first()
    )
    if checkpoint is None:
        return {}
    metadata = checkpoint.metadata if isinstance(checkpoint.metadata, Mapping) else {}
    raw_versions = metadata.get(str(metadata_key))
    if not isinstance(raw_versions, Mapping):
        return {}
    return {
        str(key or "").strip(): str(value or "").strip()
        for key, value in raw_versions.items()
        if str(key or "").strip()
    }


def _store_pending_versions(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    versions: Mapping[str, str],
    scan_token: str,
) -> None:
    with transaction.atomic():
        checkpoint = (
            PoolMasterDataSyncCheckpoint.objects.select_for_update()
            .filter(
                tenant_id=str(tenant_id or "").strip(),
                database_id=str(database_id or "").strip(),
                entity_type=str(entity_type or "").strip(),
            )
            .first()
        )
        if checkpoint is None:
            return
        metadata = dict(checkpoint.metadata or {})
        metadata[_FULL_SCAN_PENDING_VERSIONS_KEY] = {
            str(key or "").strip(): str(value or "").strip()
            for key, value in versions.items()
            if str(key or "").strip()
        }
        metadata[_FULL_SCAN_TRANSPORT_KEY] = "odata_catalog_full_scan"
        metadata[_FULL_SCAN_LAST_SCAN_AT_KEY] = timezone.now().isoformat()
        metadata["live_full_scan_pending_token"] = str(scan_token or "")
        checkpoint.metadata = metadata
        checkpoint.save(update_fields=["metadata", "updated_at"])


def _build_item_inbound_change(
    *,
    database: Database,
    row: Mapping[str, Any],
    entity_type: str,
) -> MasterDataSyncInboundChange:
    ref_key = _row_ref_key(row)
    payload_metadata: dict[str, Any] = {
        "source_database_id": str(database.id),
        "source_database_name": str(database.name or ""),
        "ib_ref_keys": {str(database.id): ref_key},
        "code": str(row.get("Code") or "").strip(),
        "item_kind_ref": str(row.get("ВидНоменклатуры_Key") or "").strip(),
        "unit_ref": str(row.get("ЕдиницаИзмерения_Key") or "").strip(),
        "full_name": str(row.get("НаименованиеПолное") or "").strip(),
        "comment": str(row.get("Комментарий") or "").strip(),
        "is_service": bool(row.get("Услуга")),
        "odata_data_version": str(row.get("DataVersion") or "").strip(),
    }
    payload = {
        "name": str(row.get("Description") or "").strip(),
        "sku": str(row.get("Артикул") or "").strip(),
        "unit": "",
        "source_ref": ref_key,
        "metadata": payload_metadata,
    }
    payload_fingerprint = build_master_data_mutation_payload_fingerprint(payload=payload)
    origin_event_id = (
        f"ib-item:{database.id}:{ref_key}:{payload_metadata['odata_data_version'] or payload_fingerprint}"
    )
    return MasterDataSyncInboundChange(
        origin_system="ib",
        origin_event_id=origin_event_id,
        canonical_id=f"item:{ref_key}",
        entity_type=entity_type,
        payload=payload,
        payload_fingerprint=payload_fingerprint,
    )


def _build_row_version_token(row: Mapping[str, Any]) -> str:
    data_version = str(row.get("DataVersion") or "").strip()
    if data_version:
        return data_version
    fingerprint_payload = {
        "ref_key": _row_ref_key(row),
        "code": str(row.get("Code") or "").strip(),
        "name": str(row.get("Description") or "").strip(),
        "sku": str(row.get("Артикул") or "").strip(),
        "item_kind_ref": str(row.get("ВидНоменклатуры_Key") or "").strip(),
        "unit_ref": str(row.get("ЕдиницаИзмерения_Key") or "").strip(),
        "is_service": bool(row.get("Услуга")),
    }
    return build_master_data_mutation_payload_fingerprint(payload=fingerprint_payload)


def _row_ref_key(row: Mapping[str, Any]) -> str:
    return str(row.get("Ref_Key") or "").strip()


def _build_item_entity_payload(
    *,
    database: Database,
    canonical_id: str,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    item_kind_ref = str(payload_metadata.get("item_kind_ref") or "").strip()
    if not item_kind_ref:
        item_kind_ref = _resolve_default_item_kind_ref(database=database)
    if not item_kind_ref:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_ITEM_KIND_MISSING,
            detail=(
                f"Cannot resolve ВидНоменклатуры_Key for outbound canonical item '{canonical_id}' "
                f"to database '{database.id}'."
            ),
        )
    entity_payload = {
        "Description": str(payload.get("name") or "").strip(),
        "НаименованиеПолное": (
            str(payload_metadata.get("full_name") or "").strip()
            or str(payload.get("name") or "").strip()
        ),
        "ВидНоменклатуры_Key": item_kind_ref,
        "Parent_Key": _ZERO_GUID,
        "IsFolder": False,
        "DeletionMark": False,
        "Услуга": bool(payload_metadata.get("is_service")),
    }
    code = str(payload_metadata.get("code") or "").strip()
    if code:
        entity_payload["Code"] = code
    sku = str(payload.get("sku") or "").strip()
    if sku:
        entity_payload["Артикул"] = sku
    unit_ref = str(payload_metadata.get("unit_ref") or "").strip()
    if unit_ref:
        entity_payload["ЕдиницаИзмерения_Key"] = unit_ref
    return entity_payload


def _resolve_default_item_kind_ref(*, database: Database) -> str:
    with _build_odata_client(database=database) as client:
        rows = client.get_entities(
            _ITEM_KIND_ENTITY_NAME,
            top=1,
        )
    if not rows:
        return ""
    first_row = rows[0] if isinstance(rows[0], Mapping) else {}
    return str(first_row.get("Ref_Key") or "").strip()


def _resolve_target_ref_key(
    *,
    client: ODataClient,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    database_id: str,
) -> str:
    metadata_ib_ref_keys = payload_metadata.get("ib_ref_keys")
    if isinstance(metadata_ib_ref_keys, Mapping):
        direct_ref = metadata_ib_ref_keys.get(database_id)
        if isinstance(direct_ref, str) and direct_ref.strip():
            return direct_ref.strip()
        if isinstance(direct_ref, Mapping):
            nested_ref = str(direct_ref.get("ref") or direct_ref.get("value") or "").strip()
            if nested_ref:
                return nested_ref

    code = str(payload_metadata.get("code") or "").strip()
    if not code:
        return ""
    skip = 0
    matches: list[Mapping[str, Any]] = []
    while True:
        batch = client.get_entities(
            _ITEM_ENTITY_NAME,
            select_fields=["Ref_Key", "Code", "DeletionMark", "IsFolder"],
            top=_ITEM_PAGE_SIZE,
            skip=skip,
        )
        normalized_batch = [row for row in batch if isinstance(row, Mapping)]
        for row in normalized_batch:
            if bool(row.get("DeletionMark")) or bool(row.get("IsFolder")):
                continue
            if str(row.get("Code") or "").strip() == code:
                matches.append(row)
        if len(normalized_batch) < _ITEM_PAGE_SIZE or len(matches) > 1:
            break
        skip += len(normalized_batch)
    if len(matches) != 1:
        return ""
    return str(matches[0].get("Ref_Key") or "").strip()


def _guid_literal(raw_ref: str) -> str:
    normalized_ref = str(raw_ref or "").strip()
    if normalized_ref.startswith("guid'") and normalized_ref.endswith("'"):
        return normalized_ref
    return f"guid'{normalized_ref}'"


__all__ = [
    "MASTER_DATA_SYNC_ODATA_DATABASE_NOT_FOUND",
    "MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED",
    "MASTER_DATA_SYNC_ODATA_ITEM_APPLY_FAILED",
    "MASTER_DATA_SYNC_ODATA_ITEM_KIND_MISSING",
    "MASTER_DATA_SYNC_ODATA_ITEM_REF_MISSING",
    "MASTER_DATA_SYNC_ODATA_MAPPING_AMBIGUOUS",
    "MASTER_DATA_SYNC_ODATA_MAPPING_NOT_CONFIGURED",
    "MASTER_DATA_SYNC_ODATA_URL_MISSING",
    "MasterDataSyncLiveODataError",
    "apply_outbox_to_live_odata",
    "notify_changes_received_from_live_odata",
    "select_changes_from_live_odata",
]
