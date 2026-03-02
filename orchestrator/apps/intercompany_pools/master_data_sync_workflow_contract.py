from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from .models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncPolicy,
)


POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT = "pool_master_data_sync_workflow.v1"
POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT_INVALID = "POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT_INVALID"


def _fail(detail: str) -> ValueError:
    return ValueError(f"{POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT_INVALID}: {detail}")


def _require_token(payload: Mapping[str, Any], field_name: str) -> str:
    value = str(payload.get(field_name) or "").strip()
    if not value:
        raise _fail(f"field '{field_name}' must be a non-empty string")
    return value


def _require_uuid(payload: Mapping[str, Any], field_name: str) -> str:
    value = _require_token(payload, field_name)
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise _fail(f"field '{field_name}' must be a valid UUID") from exc


def validate_master_data_sync_workflow_input_context(
    *,
    input_context: Any,
) -> dict[str, Any]:
    if not isinstance(input_context, Mapping):
        raise _fail("input_context must be an object")

    payload = dict(input_context)
    contract_version = _require_token(payload, "contract_version")
    if contract_version != POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT:
        raise _fail(f"unsupported contract version '{contract_version}'")

    normalized = {
        "contract_version": contract_version,
        "sync_job_id": _require_uuid(payload, "sync_job_id"),
        "tenant_id": _require_uuid(payload, "tenant_id"),
        "database_id": _require_uuid(payload, "database_id"),
        "entity_type": _require_token(payload, "entity_type"),
        "sync_policy": _require_token(payload, "sync_policy"),
        "sync_direction": _require_token(payload, "sync_direction"),
        "correlation_id": _require_token(payload, "correlation_id"),
        "origin_system": _require_token(payload, "origin_system"),
        "origin_event_id": _require_token(payload, "origin_event_id"),
    }

    if normalized["entity_type"] not in set(PoolMasterDataEntityType.values):
        raise _fail(f"unsupported entity_type '{normalized['entity_type']}'")
    if normalized["sync_policy"] not in set(PoolMasterDataSyncPolicy.values):
        raise _fail(f"unsupported sync_policy '{normalized['sync_policy']}'")
    if normalized["sync_direction"] not in set(PoolMasterDataSyncDirection.values):
        raise _fail(f"unsupported sync_direction '{normalized['sync_direction']}'")

    return normalized


def build_master_data_sync_workflow_input_context(
    *,
    sync_job: PoolMasterDataSyncJob,
    correlation_id: str,
    origin_system: str,
    origin_event_id: str,
) -> dict[str, Any]:
    payload = {
        "contract_version": POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT,
        "sync_job_id": str(sync_job.id),
        "tenant_id": str(sync_job.tenant_id),
        "database_id": str(sync_job.database_id),
        "entity_type": str(sync_job.entity_type or "").strip(),
        "sync_policy": str(sync_job.policy or "").strip(),
        "sync_direction": str(sync_job.direction or "").strip(),
        "correlation_id": str(correlation_id or "").strip(),
        "origin_system": str(origin_system or "").strip(),
        "origin_event_id": str(origin_event_id or "").strip(),
    }
    return validate_master_data_sync_workflow_input_context(input_context=payload)
