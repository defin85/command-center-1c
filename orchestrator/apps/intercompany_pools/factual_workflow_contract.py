from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping
from uuid import UUID

from .factual_read_lane import build_factual_read_lane_execution_context
from .factual_scheduling import build_factual_closed_quarter_reconcile_contract
from .models import PoolFactualLane


POOL_FACTUAL_SYNC_WORKFLOW_CONTRACT = "pool_factual_sync_workflow.v1"
POOL_FACTUAL_SYNC_WORKFLOW_CONTRACT_INVALID = "POOL_FACTUAL_SYNC_WORKFLOW_CONTRACT_INVALID"


def _fail(detail: str) -> ValueError:
    return ValueError(f"{POOL_FACTUAL_SYNC_WORKFLOW_CONTRACT_INVALID}: {detail}")


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


def _require_date(payload: Mapping[str, Any], field_name: str) -> str:
    value = _require_token(payload, field_name)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise _fail(f"field '{field_name}' must be an ISO date") from exc
    return parsed.isoformat()


def _require_csv_tokens(payload: Mapping[str, Any], field_name: str) -> str:
    return ",".join(_normalize_csv_tokens(payload.get(field_name), field_name=field_name))


def _require_positive_int_token(payload: Mapping[str, Any], field_name: str) -> str:
    raw_value = _require_token(payload, field_name)
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise _fail(f"field '{field_name}' must be a positive integer") from exc
    if parsed <= 0:
        raise _fail(f"field '{field_name}' must be a positive integer")
    return str(parsed)


def _require_bool_like_token(payload: Mapping[str, Any], field_name: str) -> str:
    raw_value = payload.get(field_name)
    if isinstance(raw_value, bool):
        return "1" if raw_value else "0"
    value = _require_token(payload, field_name)
    if value not in {"0", "1", "true", "false"}:
        raise _fail(f"field '{field_name}' must be one of '0', '1', 'true', or 'false'")
    return value


def _normalize_csv_tokens(raw_value: Any, *, field_name: str) -> tuple[str, ...]:
    if isinstance(raw_value, str):
        values = [part.strip() for part in raw_value.split(",")]
    elif isinstance(raw_value, Iterable):
        values = [str(part or "").strip() for part in raw_value]
    else:
        values = []
    normalized = tuple(sorted({value for value in values if value}))
    if not normalized:
        raise _fail(f"field '{field_name}' must contain at least one token")
    return normalized


def _normalize_shared_source_scope_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    boundary_kind = _require_token(payload, "read_boundary_kind")
    normalized = {
        "document_entities": _require_csv_tokens(payload, "document_entities"),
        "accounting_register_entity": _require_token(payload, "accounting_register_entity"),
        "accounting_register_function": _require_token(payload, "accounting_register_function"),
        "information_register_entity": _require_token(payload, "information_register_entity"),
        "source_profile": _require_token(payload, "source_profile"),
        "freshness_target_seconds": _require_positive_int_token(payload, "freshness_target_seconds"),
        "scope_fingerprint": _require_token(payload, "scope_fingerprint"),
        "subsystem": _require_token(payload, "subsystem"),
        "read_boundary_kind": boundary_kind,
        "direct_db_access": _require_bool_like_token(payload, "direct_db_access"),
        "factual_use_case": _require_token(payload, "factual_use_case"),
        "priority": _require_token(payload, "priority"),
        "role": _require_token(payload, "role"),
        "deadline_at": _require_token(payload, "deadline_at"),
        "server_affinity": _require_token(payload, "server_affinity"),
        "server_affinity_source": _require_token(payload, "server_affinity_source"),
    }
    if boundary_kind == "odata":
        normalized.update(
            {
                "read_boundary_entity_allowlist": _require_csv_tokens(payload, "read_boundary_entity_allowlist"),
                "read_boundary_function_allowlist": _require_csv_tokens(payload, "read_boundary_function_allowlist"),
                "read_boundary_service_name": str(payload.get("read_boundary_service_name") or "").strip(),
                "read_boundary_endpoint_path": str(payload.get("read_boundary_endpoint_path") or "").strip(),
                "read_boundary_operation_name": str(payload.get("read_boundary_operation_name") or "").strip(),
            }
        )
    else:
        normalized.update(
            {
                "read_boundary_entity_allowlist": str(payload.get("read_boundary_entity_allowlist") or "").strip(),
                "read_boundary_function_allowlist": str(payload.get("read_boundary_function_allowlist") or "").strip(),
                "read_boundary_service_name": _require_token(payload, "read_boundary_service_name"),
                "read_boundary_endpoint_path": _require_token(payload, "read_boundary_endpoint_path"),
                "read_boundary_operation_name": _require_token(payload, "read_boundary_operation_name"),
            }
        )
    return normalized


def validate_pool_factual_sync_workflow_input_context(*, input_context: Any) -> dict[str, Any]:
    if not isinstance(input_context, Mapping):
        raise _fail("input_context must be an object")

    payload = dict(input_context)
    contract_version = _require_token(payload, "contract_version")
    if contract_version != POOL_FACTUAL_SYNC_WORKFLOW_CONTRACT:
        raise _fail(f"unsupported contract version '{contract_version}'")

    lane = _require_token(payload, "lane")
    if lane not in set(PoolFactualLane.values):
        raise _fail(f"unsupported lane '{lane}'")

    quarter_start = _require_date(payload, "quarter_start")
    quarter_end = _require_date(payload, "quarter_end")
    if quarter_end < quarter_start:
        raise _fail("quarter_end must be greater than or equal to quarter_start")

    normalized = {
        "contract_version": contract_version,
        "tenant_id": _require_uuid(payload, "tenant_id"),
        "pool_id": _require_uuid(payload, "pool_id"),
        "database_id": _require_uuid(payload, "database_id"),
        "checkpoint_id": _require_uuid(payload, "checkpoint_id"),
        "lane": lane,
        "quarter_start": quarter_start,
        "quarter_end": quarter_end,
        "organization_ids": _require_csv_tokens(payload, "organization_ids"),
        "account_codes": _require_csv_tokens(payload, "account_codes"),
        "movement_kinds": _require_csv_tokens(payload, "movement_kinds"),
        "activity": _require_token(payload, "activity"),
        "freeze_quarter": bool(payload.get("freeze_quarter")),
        "correlation_id": _require_token(payload, "correlation_id"),
        "origin_system": _require_token(payload, "origin_system"),
        "origin_event_id": _require_token(payload, "origin_event_id"),
    }
    normalized.update(_normalize_shared_source_scope_fields(payload))
    if lane == PoolFactualLane.READ:
        normalized.update(
            {
                "actions": _require_csv_tokens(payload, "actions"),
                "materialization_targets": _require_csv_tokens(payload, "materialization_targets"),
                "per_database_cap": _require_positive_int_token(payload, "per_database_cap"),
                "per_cluster_cap": _require_positive_int_token(payload, "per_cluster_cap"),
                "global_cap": _require_positive_int_token(payload, "global_cap"),
                "polling_tier": _require_token(payload, "polling_tier"),
                "poll_interval_seconds": _require_positive_int_token(payload, "poll_interval_seconds"),
            }
        )
    elif lane == PoolFactualLane.RECONCILE:
        normalized.update(
            {
                "quarter_scope": _require_token(payload, "quarter_scope"),
                "schedule_window": _require_token(payload, "schedule_window"),
            }
        )
    return normalized


def build_pool_factual_sync_workflow_input_context(
    *,
    checkpoint_id: str,
    tenant_id: str,
    pool_id: str,
    database: Any,
    quarter_start: date,
    quarter_end: date,
    organization_ids: Iterable[str],
    account_codes: Iterable[str],
    movement_kinds: Iterable[str],
    lane: str,
    correlation_id: str,
    origin_system: str,
    origin_event_id: str,
    activity: str = "active",
    freeze_quarter: bool = False,
    now=None,
) -> dict[str, Any]:
    normalized_lane = str(lane or "").strip().lower()
    if normalized_lane == PoolFactualLane.READ:
        read_context = build_factual_read_lane_execution_context(
            tenant_id=tenant_id,
            pool_id=pool_id,
            database=database,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            organization_ids=organization_ids,
            account_codes=account_codes,
            movement_kinds=movement_kinds,
            actions=("sync_source_slice", "update_checkpoint", "refresh_batch_settlement", "materialize_carry_forward"),
            activity=activity,
            now=now,
        )
        payload = dict(read_context)
        payload["activity"] = str(activity or "").strip().lower() or "active"
    elif normalized_lane == PoolFactualLane.RECONCILE:
        read_context = build_factual_read_lane_execution_context(
            tenant_id=tenant_id,
            pool_id=pool_id,
            database=database,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            organization_ids=organization_ids,
            account_codes=account_codes,
            movement_kinds=movement_kinds,
            actions=("sync_source_slice", "update_checkpoint", "refresh_batch_settlement", "materialize_carry_forward"),
            activity=activity,
            now=now,
        )
        reconcile_contract = build_factual_closed_quarter_reconcile_contract(
            database=database,
            now=now,
        )
        payload = {
            **read_context,
            **reconcile_contract,
            "tenant_id": str(tenant_id or "").strip(),
            "pool_id": str(pool_id or "").strip(),
            "database_id": str(getattr(database, "id", "") or "").strip(),
            "lane": PoolFactualLane.RECONCILE,
            "quarter_start": quarter_start.isoformat(),
            "quarter_end": quarter_end.isoformat(),
            "activity": str(activity or "").strip().lower() or "active",
            "freeze_quarter": bool(freeze_quarter),
        }
    else:
        raise _fail(f"unsupported lane '{lane}'")

    payload.update(
        {
            "contract_version": POOL_FACTUAL_SYNC_WORKFLOW_CONTRACT,
            "checkpoint_id": str(checkpoint_id or "").strip(),
            "correlation_id": str(correlation_id or "").strip(),
            "origin_system": str(origin_system or "").strip(),
            "origin_event_id": str(origin_event_id or "").strip(),
            "freeze_quarter": bool(freeze_quarter),
        }
    )
    return validate_pool_factual_sync_workflow_input_context(input_context=payload)


__all__ = [
    "POOL_FACTUAL_SYNC_WORKFLOW_CONTRACT",
    "POOL_FACTUAL_SYNC_WORKFLOW_CONTRACT_INVALID",
    "build_pool_factual_sync_workflow_input_context",
    "validate_pool_factual_sync_workflow_input_context",
]
