from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Mapping
from uuid import UUID

from .factual_sync_runtime import build_factual_sales_report_sync_contract


POOL_FACTUAL_READ_LANE_CONTRACT = "pool_factual_read_lane.v1"
FACTUAL_READ_LANE_CONTRACT_INVALID = "POOL_FACTUAL_READ_LANE_CONTRACT_INVALID"

FACTUAL_READ_LANE_SUBSYSTEM = "factual_read_projection"
FACTUAL_READ_LANE_ALLOWED_ACTIONS = frozenset(
    {
        "sync_source_slice",
        "update_checkpoint",
        "refresh_batch_settlement",
        "materialize_carry_forward",
        "attribute_leaf_sale",
    }
)
FACTUAL_READ_LANE_DISALLOWED_ACTIONS = frozenset(
    {
        "create_run",
        "start_run",
        "confirm_publication",
        "retry_publication",
        "attribute",
        "reconcile",
        "resolve_without_change",
    }
)
FACTUAL_READ_LANE_MATERIALIZATION_TARGETS = (
    "pool_batch_settlements",
    "pool_factual_balance_snapshots",
    "pool_factual_sync_checkpoints",
)


def _fail(detail: str) -> ValueError:
    return ValueError(f"{FACTUAL_READ_LANE_CONTRACT_INVALID}: {detail}")


def build_factual_read_lane_execution_context(
    *,
    tenant_id: str,
    pool_id: str,
    database: Any,
    quarter_start: date,
    quarter_end: date,
    organization_ids: Iterable[str],
    account_codes: Iterable[str],
    movement_kinds: Iterable[str],
    actions: Iterable[str],
    activity: str = "active",
    now: datetime | None = None,
) -> dict[str, Any]:
    sync_contract = build_factual_sales_report_sync_contract(
        database=database,
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        organization_ids=organization_ids,
        account_codes=account_codes,
        movement_kinds=movement_kinds,
        activity=activity,
        now=now,
    )
    payload = {
        **sync_contract,
        "contract_version": POOL_FACTUAL_READ_LANE_CONTRACT,
        "tenant_id": str(tenant_id or "").strip(),
        "pool_id": str(pool_id or "").strip(),
        "database_id": str(getattr(database, "id", "") or "").strip(),
        "subsystem": FACTUAL_READ_LANE_SUBSYSTEM,
        "lane": "read",
        "actions": sorted(_normalize_actions(actions=actions)),
        "materialization_targets": list(FACTUAL_READ_LANE_MATERIALIZATION_TARGETS),
    }
    normalized = validate_factual_read_lane_execution_context(input_context=payload)
    normalized["actions"] = ",".join(normalized["actions"])
    normalized["materialization_targets"] = ",".join(normalized["materialization_targets"])
    normalized.update(sync_contract)
    return normalized


def validate_factual_read_lane_execution_context(*, input_context: Any) -> dict[str, Any]:
    if not isinstance(input_context, Mapping):
        raise _fail("input_context must be an object")

    payload = dict(input_context)
    contract_version = _require_token(payload, "contract_version")
    if contract_version != POOL_FACTUAL_READ_LANE_CONTRACT:
        raise _fail(f"unsupported contract version '{contract_version}'")

    lane = _require_token(payload, "lane")
    if lane != "read":
        raise _fail(f"lane must be 'read', got '{lane}'")

    subsystem = _require_token(payload, "subsystem")
    if subsystem != FACTUAL_READ_LANE_SUBSYSTEM:
        raise _fail(f"subsystem must be '{FACTUAL_READ_LANE_SUBSYSTEM}', got '{subsystem}'")

    actions = _normalize_actions(actions=payload.get("actions") or ())
    materialization_targets = _normalize_materialization_targets(payload.get("materialization_targets") or ())

    return {
        "contract_version": contract_version,
        "tenant_id": _require_uuid(payload, "tenant_id"),
        "pool_id": _require_uuid(payload, "pool_id"),
        "database_id": _require_token(payload, "database_id"),
        "lane": lane,
        "subsystem": subsystem,
        "actions": sorted(actions),
        "materialization_targets": list(materialization_targets),
    }


def _normalize_actions(*, actions: Iterable[str]) -> frozenset[str]:
    normalized = frozenset(
        str(action or "").strip()
        for action in actions
        if str(action or "").strip()
    )
    if not normalized:
        raise _fail("actions must contain at least one read-lane materialization action")
    disallowed = normalized.intersection(FACTUAL_READ_LANE_DISALLOWED_ACTIONS)
    if disallowed:
        blocked = ",".join(sorted(disallowed))
        raise _fail(f"actions contain disallowed commands: {blocked}")
    unsupported = normalized.difference(FACTUAL_READ_LANE_ALLOWED_ACTIONS)
    if unsupported:
        blocked = ",".join(sorted(unsupported))
        raise _fail(f"actions contain unsupported commands: {blocked}")
    return normalized


def _normalize_materialization_targets(raw_targets: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(
        sorted(
            {
                str(target or "").strip()
                for target in raw_targets
                if str(target or "").strip()
            }
        )
    )
    if normalized != FACTUAL_READ_LANE_MATERIALIZATION_TARGETS:
        expected = ",".join(FACTUAL_READ_LANE_MATERIALIZATION_TARGETS)
        actual = ",".join(normalized)
        raise _fail(
            "materialization_targets must be exactly "
            f"'{expected}', got '{actual or '<empty>'}'"
        )
    return normalized


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


__all__ = [
    "FACTUAL_READ_LANE_ALLOWED_ACTIONS",
    "FACTUAL_READ_LANE_CONTRACT_INVALID",
    "FACTUAL_READ_LANE_DISALLOWED_ACTIONS",
    "FACTUAL_READ_LANE_MATERIALIZATION_TARGETS",
    "FACTUAL_READ_LANE_SUBSYSTEM",
    "POOL_FACTUAL_READ_LANE_CONTRACT",
    "build_factual_read_lane_execution_context",
    "validate_factual_read_lane_execution_context",
]
