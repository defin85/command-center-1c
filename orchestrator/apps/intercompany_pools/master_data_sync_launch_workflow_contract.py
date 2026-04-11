from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from .models import PoolMasterDataSyncLaunchMode, PoolMasterDataSyncLaunchRequest, PoolMasterDataSyncLaunchTargetMode


POOL_MASTER_DATA_SYNC_LAUNCH_WORKFLOW_CONTRACT = "pool_master_data_sync_launch_workflow.v1"
POOL_MASTER_DATA_SYNC_LAUNCH_WORKFLOW_CONTRACT_INVALID = "POOL_MASTER_DATA_SYNC_LAUNCH_WORKFLOW_CONTRACT_INVALID"


def _fail(detail: str) -> ValueError:
    return ValueError(f"{POOL_MASTER_DATA_SYNC_LAUNCH_WORKFLOW_CONTRACT_INVALID}: {detail}")


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


def validate_master_data_sync_launch_workflow_input_context(
    *,
    input_context: Any,
) -> dict[str, Any]:
    if not isinstance(input_context, Mapping):
        raise _fail("input_context must be an object")

    payload = dict(input_context)
    contract_version = _require_token(payload, "contract_version")
    if contract_version != POOL_MASTER_DATA_SYNC_LAUNCH_WORKFLOW_CONTRACT:
        raise _fail(f"unsupported contract version '{contract_version}'")

    normalized = {
        "contract_version": contract_version,
        "launch_request_id": _require_uuid(payload, "launch_request_id"),
        "tenant_id": _require_uuid(payload, "tenant_id"),
        "mode": _require_token(payload, "mode"),
        "target_mode": _require_token(payload, "target_mode"),
        "correlation_id": _require_token(payload, "correlation_id"),
        "origin_system": _require_token(payload, "origin_system"),
        "origin_event_id": _require_token(payload, "origin_event_id"),
        "actor_username": str(payload.get("actor_username") or "").strip(),
    }
    if normalized["mode"] not in set(PoolMasterDataSyncLaunchMode.values):
        raise _fail(f"unsupported mode '{normalized['mode']}'")
    if normalized["target_mode"] not in set(PoolMasterDataSyncLaunchTargetMode.values):
        raise _fail(f"unsupported target_mode '{normalized['target_mode']}'")
    return normalized


def build_master_data_sync_launch_workflow_input_context(
    *,
    launch_request: PoolMasterDataSyncLaunchRequest,
    correlation_id: str,
    origin_system: str,
    origin_event_id: str,
    actor_username: str = "",
) -> dict[str, Any]:
    payload = {
        "contract_version": POOL_MASTER_DATA_SYNC_LAUNCH_WORKFLOW_CONTRACT,
        "launch_request_id": str(launch_request.id),
        "tenant_id": str(launch_request.tenant_id),
        "mode": str(launch_request.mode or "").strip(),
        "target_mode": str(launch_request.target_mode or "").strip(),
        "correlation_id": str(correlation_id or "").strip(),
        "origin_system": str(origin_system or "").strip(),
        "origin_event_id": str(origin_event_id or "").strip(),
        "actor_username": str(actor_username or "").strip(),
    }
    return validate_master_data_sync_launch_workflow_input_context(input_context=payload)
