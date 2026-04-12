from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from .models import PoolMasterDataBootstrapCollectionMode

POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT = (
    "pool_master_data_bootstrap_collection_workflow.v1"
)
POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT_INVALID = (
    "POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT_INVALID"
)


def _fail(detail: str) -> ValueError:
    return ValueError(f"{POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT_INVALID}: {detail}")


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


def validate_pool_master_data_bootstrap_collection_workflow_input_context(
    *,
    input_context: Any,
) -> dict[str, Any]:
    if not isinstance(input_context, Mapping):
        raise _fail("input_context must be an object")

    payload = dict(input_context)
    contract_version = _require_token(payload, "contract_version")
    if contract_version != POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT:
        raise _fail(f"unsupported contract version '{contract_version}'")

    return {
        "contract_version": contract_version,
        "collection_id": _require_uuid(payload, "collection_id"),
        "tenant_id": _require_uuid(payload, "tenant_id"),
        "stage": _require_stage(payload, "stage"),
        "runner_token": _require_token(payload, "runner_token"),
        "correlation_id": _require_token(payload, "correlation_id"),
        "origin_system": _require_token(payload, "origin_system"),
        "origin_event_id": _require_token(payload, "origin_event_id"),
        "actor_username": str(payload.get("actor_username") or "").strip(),
    }


def build_pool_master_data_bootstrap_collection_workflow_input_context(
    *,
    collection_id: str,
    tenant_id: str,
    stage: str,
    runner_token: str,
    correlation_id: str,
    origin_system: str,
    origin_event_id: str,
    actor_username: str = "",
) -> dict[str, Any]:
    payload = {
        "contract_version": POOL_MASTER_DATA_BOOTSTRAP_COLLECTION_WORKFLOW_CONTRACT,
        "collection_id": str(collection_id),
        "tenant_id": str(tenant_id),
        "stage": str(stage or "").strip(),
        "runner_token": str(runner_token or "").strip(),
        "correlation_id": str(correlation_id or "").strip(),
        "origin_system": str(origin_system or "").strip(),
        "origin_event_id": str(origin_event_id or "").strip(),
        "actor_username": str(actor_username or "").strip(),
    }
    return validate_pool_master_data_bootstrap_collection_workflow_input_context(
        input_context=payload
    )


def _require_stage(payload: Mapping[str, Any], field_name: str) -> str:
    value = _require_token(payload, field_name)
    if value not in {
        PoolMasterDataBootstrapCollectionMode.DRY_RUN,
        PoolMasterDataBootstrapCollectionMode.EXECUTE,
    }:
        raise _fail(f"field '{field_name}' must be one of: dry_run, execute")
    return value
