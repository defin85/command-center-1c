from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from django.db import transaction
from django.utils import timezone

from apps.databases.models import Database, InfobaseUserMapping
from apps.databases.odata import ODataClient, resolve_database_odata_verify_tls
from apps.databases.odata.exceptions import (
    ODataConnectionError,
    ODataRequestError,
    ODataTimeoutError,
)

from .master_data_registry import normalize_pool_master_data_entity_type
from .master_data_sync_inbound_poller import (
    MasterDataSyncInboundChange,
    MasterDataSyncSelectChangesResult,
)
from .master_data_sync_outbox import build_master_data_mutation_payload_fingerprint
from .models import (
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterDataSourceRecord,
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncOutbox,
    PoolMasterParty,
)


MASTER_DATA_SYNC_ODATA_DATABASE_NOT_FOUND = "MASTER_DATA_SYNC_ODATA_DATABASE_NOT_FOUND"
MASTER_DATA_SYNC_ODATA_MAPPING_NOT_CONFIGURED = "MASTER_DATA_SYNC_ODATA_MAPPING_NOT_CONFIGURED"
MASTER_DATA_SYNC_ODATA_MAPPING_AMBIGUOUS = "MASTER_DATA_SYNC_ODATA_MAPPING_AMBIGUOUS"
MASTER_DATA_SYNC_ODATA_URL_MISSING = "MASTER_DATA_SYNC_ODATA_URL_MISSING"
MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED = "MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED"
MASTER_DATA_SYNC_ODATA_ITEM_KIND_MISSING = "MASTER_DATA_SYNC_ODATA_ITEM_KIND_MISSING"
MASTER_DATA_SYNC_ODATA_ITEM_APPLY_FAILED = "MASTER_DATA_SYNC_ODATA_ITEM_APPLY_FAILED"
MASTER_DATA_SYNC_ODATA_ITEM_REF_MISSING = "MASTER_DATA_SYNC_ODATA_ITEM_REF_MISSING"
MASTER_DATA_SYNC_ODATA_PARTY_APPLY_FAILED = "MASTER_DATA_SYNC_ODATA_PARTY_APPLY_FAILED"
MASTER_DATA_SYNC_ODATA_PARTY_REF_MISSING = "MASTER_DATA_SYNC_ODATA_PARTY_REF_MISSING"
MASTER_DATA_SYNC_ODATA_PARTY_ROLE_UNSUPPORTED = "MASTER_DATA_SYNC_ODATA_PARTY_ROLE_UNSUPPORTED"
MASTER_DATA_SYNC_ODATA_CONTRACT_APPLY_FAILED = "MASTER_DATA_SYNC_ODATA_CONTRACT_APPLY_FAILED"
MASTER_DATA_SYNC_ODATA_CONTRACT_REF_MISSING = "MASTER_DATA_SYNC_ODATA_CONTRACT_REF_MISSING"
MASTER_DATA_SYNC_ODATA_CONTRACT_OWNER_MISSING = "MASTER_DATA_SYNC_ODATA_CONTRACT_OWNER_MISSING"

_FULL_SCAN_COMMITTED_VERSIONS_KEY = "live_full_scan_committed_versions"
_FULL_SCAN_PENDING_VERSIONS_KEY = "live_full_scan_pending_versions"
_FULL_SCAN_TRANSPORT_KEY = "live_full_scan_transport"
_FULL_SCAN_LAST_SCAN_AT_KEY = "live_full_scan_last_scan_at"
_FULL_SCAN_LAST_COMMITTED_AT_KEY = "live_full_scan_last_committed_at"

_ITEM_ENTITY_NAME = "Catalog_Номенклатура"
_ITEM_KIND_ENTITY_NAME = "Catalog_ВидыНоменклатуры"
_PARTY_COUNTERPARTY_ENTITY_NAME = "Catalog_Контрагенты"
_PARTY_ORGANIZATION_ENTITY_NAME = "Catalog_Организации"
_CONTRACT_ENTITY_NAME = "Catalog_ДоговорыКонтрагентов"
_PAGE_SIZE = 500
_ZERO_GUID = "00000000-0000-0000-0000-000000000000"
_PARTY_KIND_COUNTERPARTY = "counterparty"
_PARTY_KIND_ORGANIZATION = "organization"


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


@dataclass(frozen=True)
class _VatProfile:
    canonical_id: str
    vat_code: str
    vat_rate: str
    vat_included: bool
    native_token: str
    aliases: tuple[str, ...]


_VAT_PROFILES = (
    _VatProfile(
        canonical_id="vat20",
        vat_code="VAT20",
        vat_rate="20.00",
        vat_included=True,
        native_token="НДС20",
        aliases=("НДС20", "VAT20"),
    ),
    _VatProfile(
        canonical_id="vat10",
        vat_code="VAT10",
        vat_rate="10.00",
        vat_included=True,
        native_token="НДС10",
        aliases=("НДС10", "VAT10"),
    ),
    _VatProfile(
        canonical_id="vat0",
        vat_code="VAT0",
        vat_rate="0.00",
        vat_included=True,
        native_token="НДС0",
        aliases=("НДС0", "VAT0"),
    ),
    _VatProfile(
        canonical_id="without_vat",
        vat_code="NO_VAT",
        vat_rate="0.00",
        vat_included=False,
        native_token="БезНДС",
        aliases=("БЕЗНДС", "NO_VAT", "NOVAT", "WITHOUTVAT"),
    ),
)
_VAT_PROFILE_BY_ALIAS = {
    str(alias).strip().upper().replace(" ", ""): profile
    for profile in _VAT_PROFILES
    for alias in profile.aliases
}
_VAT_PROFILE_BY_CODE = {
    str(profile.vat_code).strip().upper(): profile
    for profile in _VAT_PROFILES
}
_WRITE_PROBE_RECOVERY_ERRORS = (
    ODataConnectionError,
    ODataRequestError,
    ODataTimeoutError,
)


def select_changes_from_live_odata(
    *,
    checkpoint_token: str,
    tenant_id: str,
    database_id: str,
    entity_type: str,
) -> MasterDataSyncSelectChangesResult:
    database = _resolve_database(tenant_id=tenant_id, database_id=database_id)
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)

    if normalized_entity_type == PoolMasterDataEntityType.ITEM:
        return _select_changes_by_full_scan(
            checkpoint_token=checkpoint_token,
            tenant_id=tenant_id,
            database_id=database_id,
            entity_type=normalized_entity_type,
            database=database,
            fetch_rows=_fetch_live_item_rows,
            build_change=_build_item_inbound_change,
            row_key=_row_ref_key,
            build_version=_build_item_row_version_token,
        )

    if normalized_entity_type == PoolMasterDataEntityType.PARTY:
        return _select_changes_by_full_scan(
            checkpoint_token=checkpoint_token,
            tenant_id=tenant_id,
            database_id=database_id,
            entity_type=normalized_entity_type,
            database=database,
            fetch_rows=_fetch_live_counterparty_rows,
            build_change=_build_party_inbound_change,
            row_key=_row_ref_key,
            build_version=_build_party_row_version_token,
        )

    if normalized_entity_type == PoolMasterDataEntityType.CONTRACT:
        return _select_changes_by_full_scan(
            checkpoint_token=checkpoint_token,
            tenant_id=tenant_id,
            database_id=database_id,
            entity_type=normalized_entity_type,
            database=database,
            fetch_rows=_fetch_live_contract_rows,
            build_change=_build_contract_inbound_change,
            row_key=_row_ref_key,
            build_version=_build_contract_row_version_token,
        )

    if normalized_entity_type == PoolMasterDataEntityType.TAX_PROFILE:
        return _select_changes_by_full_scan(
            checkpoint_token=checkpoint_token,
            tenant_id=tenant_id,
            database_id=database_id,
            entity_type=normalized_entity_type,
            database=database,
            fetch_rows=_fetch_live_tax_profile_rows,
            build_change=_build_tax_profile_inbound_change,
            row_key=_row_ref_key,
            build_version=_build_tax_profile_row_version_token,
        )

    raise MasterDataSyncLiveODataError(
        code=MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED,
        detail=f"Live OData inbound transport does not support entity '{normalized_entity_type}'.",
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
    payload = dict(mutation.get("payload") or {})
    payload_metadata = _payload_metadata(payload=payload)
    canonical_id = str(payload.get("canonical_id") or mutation.get("canonical_id") or "").strip()

    if mutation_kind == "item_upsert":
        if str(outbox.entity_type) != PoolMasterDataEntityType.ITEM:
            raise MasterDataSyncLiveODataError(
                code=MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED,
                detail=(
                    "Live OData outbound transport expected item entity for item_upsert; "
                    f"got entity='{outbox.entity_type}'."
                ),
            )
        return _apply_item_outbox(
            database=database,
            payload=payload,
            payload_metadata=payload_metadata,
            canonical_id=canonical_id,
        )

    if mutation_kind == "party_upsert":
        if str(outbox.entity_type) != PoolMasterDataEntityType.PARTY:
            raise MasterDataSyncLiveODataError(
                code=MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED,
                detail=(
                    "Live OData outbound transport expected party entity for party_upsert; "
                    f"got entity='{outbox.entity_type}'."
                ),
            )
        return _apply_party_outbox(
            database=database,
            payload=payload,
            payload_metadata=payload_metadata,
            canonical_id=canonical_id,
        )

    if mutation_kind == "contract_upsert":
        if str(outbox.entity_type) != PoolMasterDataEntityType.CONTRACT:
            raise MasterDataSyncLiveODataError(
                code=MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED,
                detail=(
                    "Live OData outbound transport expected contract entity for contract_upsert; "
                    f"got entity='{outbox.entity_type}'."
                ),
            )
        return _apply_contract_outbox(
            database=database,
            payload=payload,
            payload_metadata=payload_metadata,
            canonical_id=canonical_id,
        )

    if mutation_kind == "tax_profile_upsert":
        if str(outbox.entity_type) != PoolMasterDataEntityType.TAX_PROFILE:
            raise MasterDataSyncLiveODataError(
                code=MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED,
                detail=(
                    "Live OData outbound transport expected tax_profile entity for tax_profile_upsert; "
                    f"got entity='{outbox.entity_type}'."
                ),
            )
        return _apply_tax_profile_outbox(
            database=database,
            payload=payload,
            payload_metadata=payload_metadata,
            canonical_id=canonical_id,
        )

    raise MasterDataSyncLiveODataError(
        code=MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED,
        detail=(
            "Live OData outbound transport does not support "
            f"entity='{outbox.entity_type}' mutation='{mutation_kind}'."
        ),
    )


def _select_changes_by_full_scan(
    *,
    checkpoint_token: str,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    database: Database,
    fetch_rows: Callable[..., list[dict[str, Any]]],
    build_change: Callable[..., MasterDataSyncInboundChange | None],
    row_key: Callable[[Mapping[str, Any]], str],
    build_version: Callable[[Mapping[str, Any]], str],
) -> MasterDataSyncSelectChangesResult:
    current_rows = fetch_rows(database=database)
    current_versions: dict[str, str] = {}
    committed_versions, has_committed_snapshot = _read_checkpoint_versions_state(
        tenant_id=tenant_id,
        database_id=database_id,
        entity_type=entity_type,
        metadata_key=_FULL_SCAN_COMMITTED_VERSIONS_KEY,
    )
    changes: list[MasterDataSyncInboundChange] = []
    for row in current_rows:
        ref_key = row_key(row)
        if not ref_key:
            continue
        current_version = build_version(row)
        current_versions[ref_key] = current_version
        if not has_committed_snapshot:
            continue
        if committed_versions.get(ref_key) == current_version:
            continue
        inbound_change = build_change(
            database=database,
            row=row,
            entity_type=entity_type,
        )
        if inbound_change is not None:
            changes.append(inbound_change)

    scan_token = f"full-scan:{entity_type}:{len(current_versions)}:{timezone.now().isoformat()}"
    _store_pending_versions(
        tenant_id=tenant_id,
        database_id=database_id,
        entity_type=entity_type,
        versions=current_versions,
        scan_token=scan_token,
    )
    return MasterDataSyncSelectChangesResult(
        changes=changes,
        source_checkpoint_token=str(checkpoint_token or ""),
        next_checkpoint_token=scan_token,
    )


def _resolve_database(*, tenant_id: str, database_id: str) -> Database:
    database = Database.objects.filter(
        id=str(database_id or "").strip(),
        tenant_id=str(tenant_id or "").strip(),
    ).first()
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


def _fetch_live_entity_rows(
    *,
    database: Database,
    entity_name: str,
    select_fields: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skip = 0
    with _build_odata_client(database=database) as client:
        while True:
            batch = client.get_entities(
                entity_name,
                select_fields=select_fields,
                top=_PAGE_SIZE,
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
            if len(batch) < _PAGE_SIZE:
                break
            skip += len(batch)
    return rows


def _fetch_live_item_rows(*, database: Database) -> list[dict[str, Any]]:
    return _fetch_live_entity_rows(
        database=database,
        entity_name=_ITEM_ENTITY_NAME,
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
    )


def _fetch_live_counterparty_rows(*, database: Database) -> list[dict[str, Any]]:
    return _fetch_live_entity_rows(
        database=database,
        entity_name=_PARTY_COUNTERPARTY_ENTITY_NAME,
        select_fields=[
            "Ref_Key",
            "DataVersion",
            "Code",
            "Description",
            "НаименованиеПолное",
            "ИНН",
            "КПП",
            "DeletionMark",
            "IsFolder",
        ],
    )


def _fetch_live_contract_rows(*, database: Database) -> list[dict[str, Any]]:
    return _fetch_live_entity_rows(
        database=database,
        entity_name=_CONTRACT_ENTITY_NAME,
        select_fields=[
            "Ref_Key",
            "DataVersion",
            "Description",
            "Owner_Key",
            "Номер",
            "Дата",
            "ВидДоговора",
            "СтавкаНДС",
            "СуммаВключаетНДС",
            "DeletionMark",
            "IsFolder",
        ],
    )


def _fetch_live_tax_profile_rows(*, database: Database) -> list[dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for row in _fetch_live_contract_rows(database=database):
        vat_profile = _resolve_vat_profile_from_token(row.get("СтавкаНДС"))
        if vat_profile is None:
            continue
        existing = profiles.get(vat_profile.canonical_id)
        if existing is None:
            profiles[vat_profile.canonical_id] = {
                "Ref_Key": vat_profile.canonical_id,
                "VatToken": vat_profile.native_token,
                "VatCode": vat_profile.vat_code,
                "VatRate": vat_profile.vat_rate,
                "VatIncluded": vat_profile.vat_included,
                "DataVersion": vat_profile.native_token,
            }
            continue
        if str(row.get("DataVersion") or "").strip():
            existing["DataVersion"] = build_master_data_mutation_payload_fingerprint(
                payload={
                    "canonical_id": vat_profile.canonical_id,
                    "tokens": sorted(
                        {
                            str(existing.get("DataVersion") or ""),
                            str(row.get("DataVersion") or ""),
                        }
                    ),
                }
            )
    return list(profiles.values())


def _read_checkpoint_versions_state(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    metadata_key: str,
) -> tuple[dict[str, str], bool]:
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
        return {}, False
    metadata = checkpoint.metadata if isinstance(checkpoint.metadata, Mapping) else {}
    has_snapshot = str(metadata_key) in metadata
    raw_versions = metadata.get(str(metadata_key))
    if not isinstance(raw_versions, Mapping):
        return {}, has_snapshot
    return (
        {
            str(key or "").strip(): str(value or "").strip()
            for key, value in raw_versions.items()
            if str(key or "").strip()
        },
        has_snapshot,
    )


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


def _build_party_inbound_change(
    *,
    database: Database,
    row: Mapping[str, Any],
    entity_type: str,
) -> MasterDataSyncInboundChange:
    ref_key = _row_ref_key(row)
    payload_metadata = {
        "source_database_id": str(database.id),
        "source_database_name": str(database.name or ""),
        "ib_ref_keys": {
            str(database.id): {
                _PARTY_KIND_COUNTERPARTY: ref_key,
            }
        },
        "party_catalog_kind": _PARTY_KIND_COUNTERPARTY,
        "code": str(row.get("Code") or "").strip(),
        "odata_data_version": str(row.get("DataVersion") or "").strip(),
    }
    payload = {
        "name": str(row.get("Description") or "").strip(),
        "full_name": str(row.get("НаименованиеПолное") or "").strip(),
        "inn": str(row.get("ИНН") or "").strip(),
        "kpp": str(row.get("КПП") or "").strip(),
        "is_our_organization": False,
        "is_counterparty": True,
        "source_ref": ref_key,
        "metadata": payload_metadata,
    }
    payload_fingerprint = build_master_data_mutation_payload_fingerprint(payload=payload)
    origin_event_id = (
        f"ib-party:{database.id}:{ref_key}:{payload_metadata['odata_data_version'] or payload_fingerprint}"
    )
    return MasterDataSyncInboundChange(
        origin_system="ib",
        origin_event_id=origin_event_id,
        canonical_id=f"party:{ref_key}",
        entity_type=entity_type,
        payload=payload,
        payload_fingerprint=payload_fingerprint,
    )


def _build_contract_inbound_change(
    *,
    database: Database,
    row: Mapping[str, Any],
    entity_type: str,
) -> MasterDataSyncInboundChange | None:
    ref_key = _row_ref_key(row)
    owner_ref = str(row.get("Owner_Key") or "").strip()
    owner_counterparty_canonical_id = _resolve_party_source_canonical_id(
        database=database,
        owner_ref=owner_ref,
    )
    if not owner_counterparty_canonical_id:
        return None
    vat_profile = _resolve_vat_profile_from_token(row.get("СтавкаНДС"))
    payload_metadata = {
        "source_database_id": str(database.id),
        "source_database_name": str(database.name or ""),
        "ib_ref_keys": {
            str(database.id): {
                owner_counterparty_canonical_id: ref_key,
            }
        },
        "contract_kind": str(row.get("ВидДоговора") or "").strip(),
        "vat_native_ref": vat_profile.native_token if vat_profile is not None else "",
        "vat_code": vat_profile.vat_code if vat_profile is not None else "",
        "vat_profile_canonical_id": vat_profile.canonical_id if vat_profile is not None else "",
        "vat_included": bool(row.get("СуммаВключаетНДС", True)),
        "odata_data_version": str(row.get("DataVersion") or "").strip(),
    }
    payload = {
        "name": str(row.get("Description") or "").strip(),
        "owner_counterparty_canonical_id": owner_counterparty_canonical_id,
        "number": str(row.get("Номер") or "").strip(),
        "date": _normalize_row_date(row.get("Дата")),
        "source_ref": ref_key,
        "metadata": payload_metadata,
    }
    payload_fingerprint = build_master_data_mutation_payload_fingerprint(payload=payload)
    origin_event_id = (
        f"ib-contract:{database.id}:{ref_key}:{payload_metadata['odata_data_version'] or payload_fingerprint}"
    )
    return MasterDataSyncInboundChange(
        origin_system="ib",
        origin_event_id=origin_event_id,
        canonical_id=f"contract:{ref_key}",
        entity_type=entity_type,
        payload=payload,
        payload_fingerprint=payload_fingerprint,
    )


def _build_tax_profile_inbound_change(
    *,
    database: Database,
    row: Mapping[str, Any],
    entity_type: str,
) -> MasterDataSyncInboundChange:
    ref_key = _row_ref_key(row)
    payload_metadata = {
        "source_database_id": str(database.id),
        "source_database_name": str(database.name or ""),
        "ib_ref_keys": {str(database.id): str(row.get("VatToken") or "").strip()},
        "vat_native_ref": str(row.get("VatToken") or "").strip(),
        "odata_data_version": str(row.get("DataVersion") or "").strip(),
    }
    payload = {
        "vat_rate": str(row.get("VatRate") or "0.00"),
        "vat_included": bool(row.get("VatIncluded", True)),
        "vat_code": str(row.get("VatCode") or "").strip(),
        "source_ref": str(row.get("VatToken") or "").strip(),
        "metadata": payload_metadata,
    }
    payload_fingerprint = build_master_data_mutation_payload_fingerprint(payload=payload)
    origin_event_id = (
        f"ib-tax-profile:{database.id}:{ref_key}:{payload_metadata['odata_data_version'] or payload_fingerprint}"
    )
    return MasterDataSyncInboundChange(
        origin_system="ib",
        origin_event_id=origin_event_id,
        canonical_id=ref_key,
        entity_type=entity_type,
        payload=payload,
        payload_fingerprint=payload_fingerprint,
    )


def _build_item_row_version_token(row: Mapping[str, Any]) -> str:
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


def _build_party_row_version_token(row: Mapping[str, Any]) -> str:
    data_version = str(row.get("DataVersion") or "").strip()
    if data_version:
        return data_version
    return build_master_data_mutation_payload_fingerprint(
        payload={
            "ref_key": _row_ref_key(row),
            "name": str(row.get("Description") or "").strip(),
            "full_name": str(row.get("НаименованиеПолное") or "").strip(),
            "inn": str(row.get("ИНН") or "").strip(),
            "kpp": str(row.get("КПП") or "").strip(),
        }
    )


def _build_contract_row_version_token(row: Mapping[str, Any]) -> str:
    data_version = str(row.get("DataVersion") or "").strip()
    if data_version:
        return data_version
    return build_master_data_mutation_payload_fingerprint(
        payload={
            "ref_key": _row_ref_key(row),
            "owner_ref": str(row.get("Owner_Key") or "").strip(),
            "number": str(row.get("Номер") or "").strip(),
            "date": _normalize_row_date(row.get("Дата")),
            "vat_native_ref": str(row.get("СтавкаНДС") or "").strip(),
        }
    )


def _build_tax_profile_row_version_token(row: Mapping[str, Any]) -> str:
    return build_master_data_mutation_payload_fingerprint(
        payload={
            "canonical_id": _row_ref_key(row),
            "vat_code": str(row.get("VatCode") or "").strip(),
            "vat_rate": str(row.get("VatRate") or "").strip(),
            "vat_included": bool(row.get("VatIncluded", True)),
            "vat_native_ref": str(row.get("VatToken") or "").strip(),
        }
    )


def _row_ref_key(row: Mapping[str, Any]) -> str:
    return str(row.get("Ref_Key") or "").strip()


def _payload_metadata(*, payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata")
    return dict(metadata) if isinstance(metadata, Mapping) else {}


def _apply_item_outbox(
    *,
    database: Database,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    canonical_id: str,
) -> dict[str, Any]:
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
    entity_payload = _build_item_entity_payload(
        database=database,
        canonical_id=canonical_id,
        payload=payload,
        payload_metadata=payload_metadata,
    )

    with _build_odata_client(database=database) as client:
        target_ref_key = _resolve_item_target_ref_key(
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


def _apply_party_outbox(
    *,
    database: Database,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    canonical_id: str,
) -> dict[str, Any]:
    if not canonical_id:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_PARTY_APPLY_FAILED,
            detail="Outbound party_upsert payload must include canonical_id.",
        )
    party_name = str(payload.get("name") or "").strip()
    if not party_name:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_PARTY_APPLY_FAILED,
            detail=f"Outbound party_upsert '{canonical_id}' must include non-empty name.",
        )

    catalog_kind = _resolve_party_catalog_kind(
        payload=payload,
        payload_metadata=payload_metadata,
        database=database,
        canonical_id=canonical_id,
    )
    if catalog_kind == _PARTY_KIND_COUNTERPARTY:
        entity_name = _PARTY_COUNTERPARTY_ENTITY_NAME
        entity_payload = _build_counterparty_entity_payload(payload=payload)
    elif catalog_kind == _PARTY_KIND_ORGANIZATION:
        entity_name = _PARTY_ORGANIZATION_ENTITY_NAME
        entity_payload = _build_organization_entity_payload(payload=payload)
    else:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_PARTY_ROLE_UNSUPPORTED,
            detail=(
                "Live OData outbound transport could not resolve a supported party catalog role; "
                f"got catalog_kind='{catalog_kind or 'unknown'}' for canonical_id='{canonical_id}'."
            ),
        )
    with _build_odata_client(database=database) as client:
        target_ref_key = _resolve_party_target_ref_key(
            database=database,
            canonical_id=canonical_id,
            client=client,
            payload=payload,
            payload_metadata=payload_metadata,
            database_id=str(database.id),
            catalog_kind=catalog_kind,
        )
        try:
            if target_ref_key:
                client.update_entity(
                    entity_name,
                    _guid_literal(target_ref_key),
                    entity_payload,
                )
                applied_ref_key = target_ref_key
                created = False
            else:
                created_payload = client.create_entity(entity_name, entity_payload)
                applied_ref_key = str(created_payload.get("Ref_Key") or "").strip()
                if not applied_ref_key:
                    raise MasterDataSyncLiveODataError(
                        code=MASTER_DATA_SYNC_ODATA_PARTY_REF_MISSING,
                        detail=(
                            f"OData create for canonical party '{canonical_id}' did not return Ref_Key "
                            f"for database '{database.id}'."
                        ),
                    )
                created = True
        except _WRITE_PROBE_RECOVERY_ERRORS as exc:
            recovered_ref = _recover_party_ref_after_write_error(
                database=database,
                canonical_id=canonical_id,
                client=client,
                payload=payload,
                payload_metadata=payload_metadata,
                database_id=str(database.id),
                catalog_kind=catalog_kind,
            )
            if not recovered_ref:
                raise MasterDataSyncLiveODataError(
                    code=MASTER_DATA_SYNC_ODATA_PARTY_APPLY_FAILED,
                    detail=(
                        f"Live OData party write failed for canonical_id='{canonical_id}' "
                        f"in database '{database.id}': {exc}"
                    ),
                ) from exc
            applied_ref_key = recovered_ref
            created = not bool(target_ref_key)

    return {
        "status": "applied",
        "created": created,
        "entity_name": entity_name,
        "canonical_id": canonical_id,
        "ib_ref_key": applied_ref_key,
        "ib_catalog_kind": catalog_kind,
    }


def _apply_contract_outbox(
    *,
    database: Database,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    canonical_id: str,
) -> dict[str, Any]:
    if not canonical_id:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_CONTRACT_APPLY_FAILED,
            detail="Outbound contract_upsert payload must include canonical_id.",
        )
    contract_name = str(payload.get("name") or "").strip()
    if not contract_name:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_CONTRACT_APPLY_FAILED,
            detail=f"Outbound contract_upsert '{canonical_id}' must include non-empty name.",
        )
    owner_counterparty_canonical_id = str(payload.get("owner_counterparty_canonical_id") or "").strip()
    if not owner_counterparty_canonical_id:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_CONTRACT_OWNER_MISSING,
            detail=f"Outbound contract_upsert '{canonical_id}' must include owner_counterparty_canonical_id.",
        )
    owner_target_ref = _resolve_target_party_binding_ref(
        database=database,
        canonical_id=owner_counterparty_canonical_id,
        catalog_kind=_PARTY_KIND_COUNTERPARTY,
    )
    if not owner_target_ref:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_CONTRACT_OWNER_MISSING,
            detail=(
                f"Counterparty binding for owner '{owner_counterparty_canonical_id}' "
                f"is missing in database '{database.id}'."
            ),
        )

    entity_payload = _build_contract_entity_payload(
        payload=payload,
        payload_metadata=payload_metadata,
        owner_target_ref=owner_target_ref,
        database_id=str(database.id),
    )
    with _build_odata_client(database=database) as client:
        target_ref_key = _resolve_contract_target_ref_key(
            client=client,
            payload=payload,
            payload_metadata=payload_metadata,
            database_id=str(database.id),
            owner_target_ref=owner_target_ref,
        )
        if target_ref_key:
            client.update_entity(
                _CONTRACT_ENTITY_NAME,
                _guid_literal(target_ref_key),
                entity_payload,
            )
            applied_ref_key = target_ref_key
            created = False
        else:
            created_payload = client.create_entity(_CONTRACT_ENTITY_NAME, entity_payload)
            applied_ref_key = str(created_payload.get("Ref_Key") or "").strip()
            if not applied_ref_key:
                raise MasterDataSyncLiveODataError(
                    code=MASTER_DATA_SYNC_ODATA_CONTRACT_REF_MISSING,
                    detail=(
                        f"OData create for canonical contract '{canonical_id}' did not return Ref_Key "
                        f"for database '{database.id}'."
                    ),
                )
            created = True

    return {
        "status": "applied",
        "created": created,
        "entity_name": _CONTRACT_ENTITY_NAME,
        "canonical_id": canonical_id,
        "ib_ref_key": applied_ref_key,
        "owner_counterparty_canonical_id": owner_counterparty_canonical_id,
    }


def _apply_tax_profile_outbox(
    *,
    database: Database,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    canonical_id: str,
) -> dict[str, Any]:
    if not canonical_id:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED,
            detail="Outbound tax_profile_upsert payload must include canonical_id.",
        )
    native_token = _resolve_tax_profile_native_token(
        payload=payload,
        payload_metadata=payload_metadata,
        database_id=str(database.id),
    )
    if not native_token:
        raise MasterDataSyncLiveODataError(
            code=MASTER_DATA_SYNC_ODATA_ENTITY_UNSUPPORTED,
            detail=(
                f"Cannot resolve target VAT token for canonical tax profile '{canonical_id}' "
                f"in database '{database.id}'."
            ),
        )
    return {
        "status": "applied",
        "created": False,
        "entity_name": "StaticVATToken",
        "canonical_id": canonical_id,
        "ib_ref_key": native_token,
    }


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


def _build_counterparty_entity_payload(*, payload: Mapping[str, Any]) -> dict[str, Any]:
    entity_payload = {
        "Description": str(payload.get("name") or "").strip(),
        "НаименованиеПолное": str(payload.get("full_name") or "").strip() or str(payload.get("name") or "").strip(),
        "Parent_Key": _ZERO_GUID,
        "IsFolder": False,
        "DeletionMark": False,
        "ЮридическоеФизическоеЛицо": "ЮридическоеЛицо",
    }
    inn = str(payload.get("inn") or "").strip()
    if inn:
        entity_payload["ИНН"] = inn
    kpp = str(payload.get("kpp") or "").strip()
    if kpp:
        entity_payload["КПП"] = kpp
    return entity_payload


def _build_organization_entity_payload(*, payload: Mapping[str, Any]) -> dict[str, Any]:
    entity_payload = {
        "Description": str(payload.get("name") or "").strip(),
        "НаименованиеПолное": str(payload.get("full_name") or "").strip() or str(payload.get("name") or "").strip(),
        "НаименованиеСокращенное": str(payload.get("name") or "").strip(),
        "Parent_Key": _ZERO_GUID,
        "IsFolder": False,
        "DeletionMark": False,
        "ОбособленноеПодразделение": False,
        "ЮридическоеФизическоеЛицо": "ЮридическоеЛицо",
    }
    inn = str(payload.get("inn") or "").strip()
    if inn:
        entity_payload["ИНН"] = inn
    kpp = str(payload.get("kpp") or "").strip()
    if kpp:
        entity_payload["КПП"] = kpp
    return entity_payload


def _build_contract_entity_payload(
    *,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    owner_target_ref: str,
    database_id: str,
) -> dict[str, Any]:
    entity_payload = {
        "Description": str(payload.get("name") or "").strip(),
        "Owner_Key": owner_target_ref,
        "Parent_Key": _ZERO_GUID,
        "IsFolder": False,
        "DeletionMark": False,
        "ВидДоговора": str(payload_metadata.get("contract_kind") or "").strip() or "СПокупателем",
        "СуммаВключаетНДС": bool(payload_metadata.get("vat_included", True)),
    }
    number = str(payload.get("number") or "").strip()
    if number:
        entity_payload["Номер"] = number
    date_token = _normalize_row_date(payload.get("date"))
    if date_token:
        entity_payload["Дата"] = f"{date_token}T00:00:00"
    vat_token = _resolve_tax_profile_native_token(
        payload=payload,
        payload_metadata=payload_metadata,
        database_id=database_id,
    )
    if vat_token:
        entity_payload["СтавкаНДС"] = vat_token
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


def _resolve_item_target_ref_key(
    *,
    client: ODataClient,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    database_id: str,
) -> str:
    direct_ref = _read_ib_ref_key_from_metadata(
        payload_metadata=payload_metadata,
        database_id=database_id,
    )
    if direct_ref:
        return direct_ref
    code = str(payload_metadata.get("code") or "").strip()
    if not code:
        return ""
    return _find_unique_ref_by_field(
        client=client,
        entity_name=_ITEM_ENTITY_NAME,
        field_name="Code",
        field_value=code,
    )


def _resolve_party_target_ref_key(
    *,
    database: Database,
    canonical_id: str,
    client: ODataClient,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    database_id: str,
    catalog_kind: str,
) -> str:
    direct_ref = _read_ib_ref_key_from_metadata(
        payload_metadata=payload_metadata,
        database_id=database_id,
        qualifier=catalog_kind,
    )
    if direct_ref:
        return direct_ref
    existing_ref = _resolve_target_party_binding_ref(
        database=database,
        canonical_id=canonical_id,
        catalog_kind=catalog_kind,
    )
    if existing_ref:
        return existing_ref
    inn = str(payload.get("inn") or "").strip()
    kpp = str(payload.get("kpp") or "").strip()
    entity_name = (
        _PARTY_ORGANIZATION_ENTITY_NAME
        if catalog_kind == _PARTY_KIND_ORGANIZATION
        else _PARTY_COUNTERPARTY_ENTITY_NAME
    )
    if inn:
        matched_ref = _find_unique_party_by_inn_kpp(
            client=client,
            entity_name=entity_name,
            inn=inn,
            kpp=kpp,
        )
        if matched_ref:
            return matched_ref
    party_name = str(payload.get("name") or "").strip()
    if not party_name:
        return ""
    return _find_unique_ref_by_field(
        client=client,
        entity_name=entity_name,
        field_name="Description",
        field_value=party_name,
        include_is_folder=catalog_kind != _PARTY_KIND_ORGANIZATION,
    )


def _recover_party_ref_after_write_error(
    *,
    database: Database,
    canonical_id: str,
    client: ODataClient,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    database_id: str,
    catalog_kind: str,
) -> str:
    return _resolve_party_target_ref_key(
        database=database,
        canonical_id=canonical_id,
        client=client,
        payload=payload,
        payload_metadata=payload_metadata,
        database_id=database_id,
        catalog_kind=catalog_kind,
    )


def _resolve_contract_target_ref_key(
    *,
    client: ODataClient,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    database_id: str,
    owner_target_ref: str,
) -> str:
    owner_counterparty_canonical_id = str(payload.get("owner_counterparty_canonical_id") or "").strip()
    direct_ref = _read_ib_ref_key_from_metadata(
        payload_metadata=payload_metadata,
        database_id=database_id,
        qualifier=owner_counterparty_canonical_id,
    )
    if direct_ref:
        return direct_ref
    number = str(payload.get("number") or "").strip()
    if not number:
        return ""
    rows = _load_entity_rows_for_lookup(
        client=client,
        entity_name=_CONTRACT_ENTITY_NAME,
        select_fields=["Ref_Key", "Owner_Key", "Номер", "DeletionMark", "IsFolder"],
    )
    matches = [
        row
        for row in rows
        if str(row.get("Owner_Key") or "").strip() == owner_target_ref
        and str(row.get("Номер") or "").strip() == number
    ]
    if len(matches) != 1:
        return ""
    return str(matches[0].get("Ref_Key") or "").strip()


def _resolve_party_catalog_kind(
    *,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    database: Database,
    canonical_id: str,
) -> str:
    explicit_kind = str(payload_metadata.get("party_catalog_kind") or "").strip().lower()
    if explicit_kind in {_PARTY_KIND_COUNTERPARTY, _PARTY_KIND_ORGANIZATION}:
        return explicit_kind

    database_ref_entry = _read_database_ref_entry(
        payload_metadata=payload_metadata,
        database_id=str(database.id),
    )
    if isinstance(database_ref_entry, Mapping):
        for kind in (_PARTY_KIND_ORGANIZATION, _PARTY_KIND_COUNTERPARTY):
            if str(database_ref_entry.get(kind) or "").strip():
                return kind

    binding_kind = _resolve_existing_party_catalog_kind(
        database=database,
        canonical_id=canonical_id,
    )
    if binding_kind:
        return binding_kind

    is_our_organization = bool(payload.get("is_our_organization"))
    is_counterparty = bool(payload.get("is_counterparty", True))
    if is_our_organization:
        return _PARTY_KIND_ORGANIZATION
    if is_counterparty:
        return _PARTY_KIND_COUNTERPARTY
    return ""


def _resolve_existing_party_catalog_kind(
    *,
    database: Database,
    canonical_id: str,
) -> str:
    if not canonical_id:
        return ""
    binding = (
        PoolMasterDataBinding.objects.filter(
            tenant_id=str(database.tenant_id),
            entity_type=PoolMasterDataEntityType.PARTY,
            canonical_id=str(canonical_id),
            database=database,
            ib_catalog_kind__in=[_PARTY_KIND_COUNTERPARTY, _PARTY_KIND_ORGANIZATION],
        )
        .exclude(ib_ref_key="")
        .order_by("-updated_at", "-created_at")
        .only("ib_catalog_kind")
        .first()
    )
    if binding is not None:
        return str(binding.ib_catalog_kind or "").strip().lower()

    party = (
        PoolMasterParty.objects.filter(
            tenant_id=str(database.tenant_id),
            canonical_id=str(canonical_id),
        )
        .only("metadata")
        .first()
    )
    if party is None:
        return ""
    metadata = dict(party.metadata or {})
    database_entry = _read_database_ref_entry(
        payload_metadata=metadata,
        database_id=str(database.id),
    )
    if not isinstance(database_entry, Mapping):
        return ""
    for kind in (_PARTY_KIND_ORGANIZATION, _PARTY_KIND_COUNTERPARTY):
        if str(database_entry.get(kind) or "").strip():
            return kind
    return ""


def _resolve_tax_profile_native_token(
    *,
    payload: Mapping[str, Any],
    payload_metadata: Mapping[str, Any],
    database_id: str,
) -> str:
    direct_ref = _read_ib_ref_key_from_metadata(
        payload_metadata=payload_metadata,
        database_id=database_id,
    )
    if direct_ref:
        return direct_ref

    native_token = str(payload_metadata.get("vat_native_ref") or "").strip()
    if native_token:
        profile = _resolve_vat_profile_from_token(native_token)
        if profile is not None:
            return profile.native_token
        return native_token

    vat_code = str(payload.get("vat_code") or payload_metadata.get("vat_code") or "").strip().upper()
    if vat_code:
        profile = _VAT_PROFILE_BY_CODE.get(vat_code)
        if profile is not None:
            return profile.native_token
        return vat_code

    vat_rate = str(payload.get("vat_rate") or payload_metadata.get("vat_rate") or "").strip()
    vat_included = bool(payload.get("vat_included", payload_metadata.get("vat_included", True)))
    for profile in _VAT_PROFILES:
        if profile.vat_rate == vat_rate and profile.vat_included is vat_included:
            return profile.native_token
    return ""


def _read_ib_ref_key_from_metadata(
    *,
    payload_metadata: Mapping[str, Any],
    database_id: str,
    qualifier: str = "",
) -> str:
    database_entry = _read_database_ref_entry(
        payload_metadata=payload_metadata,
        database_id=database_id,
    )
    if database_entry is None:
        return ""
    if qualifier:
        if isinstance(database_entry, Mapping):
            return str(database_entry.get(qualifier) or "").strip()
        return ""
    if isinstance(database_entry, str):
        return database_entry.strip()
    if isinstance(database_entry, Mapping):
        return str(database_entry.get("ref") or database_entry.get("value") or "").strip()
    return ""


def _read_database_ref_entry(
    *,
    payload_metadata: Mapping[str, Any],
    database_id: str,
) -> Any:
    metadata_ib_ref_keys = payload_metadata.get("ib_ref_keys")
    if not isinstance(metadata_ib_ref_keys, Mapping):
        return None
    return metadata_ib_ref_keys.get(database_id)


def _resolve_target_party_binding_ref(
    *,
    database: Database,
    canonical_id: str,
    catalog_kind: str,
) -> str:
    binding = (
        PoolMasterDataBinding.objects.filter(
            tenant_id=str(database.tenant_id),
            entity_type=PoolMasterDataEntityType.PARTY,
            canonical_id=str(canonical_id or "").strip(),
            database=database,
            ib_catalog_kind=str(catalog_kind or "").strip(),
        )
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if binding is not None and str(binding.ib_ref_key or "").strip():
        return str(binding.ib_ref_key or "").strip()
    party = PoolMasterParty.objects.filter(
        tenant_id=str(database.tenant_id),
        canonical_id=str(canonical_id or "").strip(),
    ).only("metadata").first()
    if party is None:
        return ""
    metadata = dict(party.metadata or {})
    ib_ref_keys = metadata.get("ib_ref_keys")
    if not isinstance(ib_ref_keys, Mapping):
        return ""
    database_entry = ib_ref_keys.get(str(database.id))
    if not isinstance(database_entry, Mapping):
        return ""
    return str(database_entry.get(catalog_kind) or "").strip()


def _resolve_party_source_canonical_id(
    *,
    database: Database,
    owner_ref: str,
) -> str:
    if not owner_ref:
        return ""
    source_record = (
        PoolMasterDataSourceRecord.objects.filter(
            tenant_id=str(database.tenant_id),
            entity_type=PoolMasterDataEntityType.PARTY,
            source_database=database,
            source_ref=owner_ref,
        )
        .exclude(canonical_id="")
        .order_by("-updated_at", "-created_at")
        .only("canonical_id")
        .first()
    )
    if source_record is None:
        for party in PoolMasterParty.objects.filter(tenant_id=str(database.tenant_id)).only("canonical_id", "metadata"):
            metadata = dict(party.metadata or {})
            ib_ref_keys = metadata.get("ib_ref_keys")
            if not isinstance(ib_ref_keys, Mapping):
                continue
            database_entry = ib_ref_keys.get(str(database.id))
            if not isinstance(database_entry, Mapping):
                continue
            if str(database_entry.get(_PARTY_KIND_COUNTERPARTY) or "").strip() == owner_ref:
                return str(party.canonical_id or "").strip()
        return ""
    return str(source_record.canonical_id or "").strip()


def _find_unique_ref_by_field(
    *,
    client: ODataClient,
    entity_name: str,
    field_name: str,
    field_value: str,
    include_is_folder: bool = True,
) -> str:
    select_fields = ["Ref_Key", field_name, "DeletionMark"]
    if include_is_folder:
        select_fields.append("IsFolder")
    rows = _load_entity_rows_for_lookup(
        client=client,
        entity_name=entity_name,
        select_fields=select_fields,
    )
    matches = [
        row
        for row in rows
        if str(row.get(field_name) or "").strip() == str(field_value or "").strip()
    ]
    if len(matches) != 1:
        return ""
    return str(matches[0].get("Ref_Key") or "").strip()


def _find_unique_party_by_inn_kpp(
    *,
    client: ODataClient,
    entity_name: str,
    inn: str,
    kpp: str,
) -> str:
    select_fields = ["Ref_Key", "ИНН", "КПП", "DeletionMark"]
    if entity_name != _PARTY_ORGANIZATION_ENTITY_NAME:
        select_fields.append("IsFolder")
    rows = _load_entity_rows_for_lookup(
        client=client,
        entity_name=entity_name,
        select_fields=select_fields,
    )
    inn_matches = [
        row
        for row in rows
        if str(row.get("ИНН") or "").strip() == str(inn or "").strip()
    ]
    if not inn_matches:
        return ""
    if kpp:
        exact_matches = [
            row
            for row in inn_matches
            if str(row.get("КПП") or "").strip() == str(kpp or "").strip()
        ]
        if len(exact_matches) == 1:
            return str(exact_matches[0].get("Ref_Key") or "").strip()
        if exact_matches:
            return ""
    if len(inn_matches) != 1:
        return ""
    return str(inn_matches[0].get("Ref_Key") or "").strip()


def _load_entity_rows_for_lookup(
    *,
    client: ODataClient,
    entity_name: str,
    select_fields: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skip = 0
    while True:
        batch = client.get_entities(
            entity_name,
            select_fields=select_fields,
            top=_PAGE_SIZE,
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
        if len(batch) < _PAGE_SIZE:
            break
        skip += len(batch)
    return rows


def _normalize_row_date(raw_value: Any) -> str:
    if raw_value in (None, ""):
        return ""
    value = str(raw_value).strip()
    if not value:
        return ""
    if "T" in value:
        value = value.split("T", 1)[0]
    return value[:10]


def _resolve_vat_profile_from_token(raw_token: Any) -> _VatProfile | None:
    normalized = str(raw_token or "").strip().upper().replace(" ", "")
    if not normalized:
        return None
    return _VAT_PROFILE_BY_ALIAS.get(normalized)


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
