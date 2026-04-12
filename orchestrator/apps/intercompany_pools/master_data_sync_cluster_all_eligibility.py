from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from apps.databases.models import Database, InfobaseUserMapping

from .master_data_sync_runtime_settings import get_pool_master_data_sync_runtime_settings


POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_ELIGIBLE = "eligible"
POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_EXCLUDED = "excluded"
POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_UNCONFIGURED = "unconfigured"
POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_VALUES = {
    POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_ELIGIBLE,
    POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_EXCLUDED,
    POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_UNCONFIGURED,
}

_DATABASE_METADATA_NAMESPACE = "pool_master_data_sync"
_CLUSTER_ALL_ELIGIBILITY_KEY = "cluster_all_eligibility"


def normalize_pool_master_data_sync_cluster_all_eligibility_state(value: object | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_VALUES:
        return normalized
    return POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_UNCONFIGURED


def get_pool_master_data_sync_cluster_all_eligibility_state(*, database: Database) -> str:
    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    namespace = metadata.get(_DATABASE_METADATA_NAMESPACE)
    if not isinstance(namespace, dict):
        return POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_UNCONFIGURED
    return normalize_pool_master_data_sync_cluster_all_eligibility_state(
        namespace.get(_CLUSTER_ALL_ELIGIBILITY_KEY)
    )


def set_pool_master_data_sync_cluster_all_eligibility_state(
    *,
    database: Database,
    state: str,
) -> dict[str, Any]:
    normalized = normalize_pool_master_data_sync_cluster_all_eligibility_state(state)
    metadata = dict(database.metadata) if isinstance(database.metadata, dict) else {}
    namespace = dict(metadata.get(_DATABASE_METADATA_NAMESPACE) or {})
    namespace[_CLUSTER_ALL_ELIGIBILITY_KEY] = normalized
    metadata[_DATABASE_METADATA_NAMESPACE] = namespace
    return metadata


def serialize_pool_master_data_sync_cluster_all_database_entry(*, database: Database) -> dict[str, Any]:
    return {
        "database_id": str(database.id),
        "database_name": str(database.name),
        "cluster_id": str(database.cluster_id) if database.cluster_id else None,
        "cluster_all_eligibility_state": get_pool_master_data_sync_cluster_all_eligibility_state(
            database=database
        ),
    }


def summarize_pool_master_data_sync_cluster_all_eligibility(
    *,
    databases: Iterable[Database],
) -> dict[str, Any]:
    eligible_entries: list[dict[str, Any]] = []
    excluded_entries: list[dict[str, Any]] = []
    unconfigured_entries: list[dict[str, Any]] = []
    for database in databases:
        entry = serialize_pool_master_data_sync_cluster_all_database_entry(database=database)
        state = entry["cluster_all_eligibility_state"]
        if state == POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_ELIGIBLE:
            eligible_entries.append(entry)
            continue
        if state == POOL_MASTER_DATA_SYNC_CLUSTER_ALL_ELIGIBILITY_EXCLUDED:
            excluded_entries.append(entry)
            continue
        unconfigured_entries.append(entry)
    return {
        "eligible_count": len(eligible_entries),
        "excluded_count": len(excluded_entries),
        "unconfigured_count": len(unconfigured_entries),
        "eligible_database_ids": [entry["database_id"] for entry in eligible_entries],
        "excluded_databases": excluded_entries,
        "unconfigured_databases": unconfigured_entries,
    }


def build_pool_master_data_sync_readiness_summary(*, database: Database) -> dict[str, Any]:
    runtime_settings = get_pool_master_data_sync_runtime_settings(tenant_id=str(database.tenant_id))
    service_mappings = list(
        InfobaseUserMapping.objects.filter(database=database, is_service=True).only(
            "id", "ib_username", "ib_password"
        )[:2]
    )
    if not service_mappings:
        service_mapping_status = "missing"
    elif len(service_mappings) > 1:
        service_mapping_status = "ambiguous"
    else:
        mapping = service_mappings[0]
        service_mapping_status = (
            "configured"
            if str(mapping.ib_username or "").strip() and bool(mapping.ib_password)
            else "incomplete"
        )
    metadata = database.metadata if isinstance(database.metadata, dict) else {}
    return {
        "cluster_attached": bool(database.cluster_id),
        "odata_configured": bool(str(database.odata_url or "").strip()),
        "credentials_configured": bool(str(database.username or "").strip() and bool(database.password)),
        "ibcmd_profile_configured": isinstance(metadata.get("ibcmd_connection"), dict),
        "service_mapping_status": service_mapping_status,
        "service_mapping_count": len(service_mappings),
        "runtime_enabled": bool(runtime_settings.enabled),
        "inbound_enabled": bool(runtime_settings.inbound_enabled),
        "outbound_enabled": bool(runtime_settings.outbound_enabled),
        "default_policy": str(runtime_settings.default_policy),
        "health_status": str(database.last_check_status or ""),
    }
