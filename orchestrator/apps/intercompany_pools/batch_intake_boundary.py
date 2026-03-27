from __future__ import annotations

from typing import Any, Iterable, Mapping
from uuid import UUID

from .models import PoolBatchKind, PoolBatchSourceType


POOL_BATCH_INTAKE_BOUNDARY_CONTRACT = "pool_batch_intake_boundary.v1"
BATCH_INTAKE_CONTRACT_INVALID = "POOL_BATCH_INTAKE_CONTRACT_INVALID"
BATCH_INTAKE_SUBSYSTEM = "batch_intake"
BATCH_INTAKE_ALLOWED_ACTIONS = frozenset(
    {
        "normalize_batch_payload",
        "persist_batch_provenance",
        "kickoff_receipt_run",
        "build_sale_closing_contract",
    }
)
BATCH_INTAKE_DISALLOWED_ACTIONS = frozenset(
    {
        "materialize_factual_projection",
        "refresh_batch_settlement",
        "enqueue_manual_review",
        "attribute",
        "reconcile",
        "resolve_without_change",
    }
)
BATCH_INTAKE_PERSISTENCE_TARGETS = (
    "pool_batches",
    "pool_runs",
    "pool_run_audit_events",
)
BATCH_INTAKE_FORBIDDEN_PERSISTENCE_TARGETS = frozenset(
    {
        "pool_batch_settlements",
        "pool_factual_balance_snapshots",
        "pool_factual_sync_checkpoints",
        "pool_factual_review_items",
    }
)


def _fail(detail: str) -> ValueError:
    return ValueError(f"{BATCH_INTAKE_CONTRACT_INVALID}: {detail}")


def build_batch_intake_execution_context(
    *,
    tenant_id: str,
    pool_id: str,
    batch_kind: str,
    source_type: str,
    actions: Iterable[str],
    persistence_targets: Iterable[str] = BATCH_INTAKE_PERSISTENCE_TARGETS,
) -> dict[str, Any]:
    payload = {
        "contract_version": POOL_BATCH_INTAKE_BOUNDARY_CONTRACT,
        "tenant_id": str(tenant_id or "").strip(),
        "pool_id": str(pool_id or "").strip(),
        "subsystem": BATCH_INTAKE_SUBSYSTEM,
        "batch_kind": str(batch_kind or "").strip(),
        "source_type": str(source_type or "").strip(),
        "actions": sorted(_normalize_actions(actions)),
        "persistence_targets": list(_normalize_persistence_targets(persistence_targets)),
    }
    return validate_batch_intake_execution_context(input_context=payload)


def validate_batch_intake_execution_context(*, input_context: Any) -> dict[str, Any]:
    if not isinstance(input_context, Mapping):
        raise _fail("input_context must be an object")

    payload = dict(input_context)
    contract_version = _require_token(payload, "contract_version")
    if contract_version != POOL_BATCH_INTAKE_BOUNDARY_CONTRACT:
        raise _fail(f"unsupported contract version '{contract_version}'")

    subsystem = _require_token(payload, "subsystem")
    if subsystem != BATCH_INTAKE_SUBSYSTEM:
        raise _fail(f"subsystem must be '{BATCH_INTAKE_SUBSYSTEM}', got '{subsystem}'")

    batch_kind = _require_token(payload, "batch_kind")
    if batch_kind not in set(PoolBatchKind.values):
        raise _fail(f"unsupported batch_kind '{batch_kind}'")

    source_type = _require_token(payload, "source_type")
    if source_type not in set(PoolBatchSourceType.values):
        raise _fail(f"unsupported source_type '{source_type}'")

    actions = _normalize_actions(payload.get("actions") or ())
    persistence_targets = _normalize_persistence_targets(payload.get("persistence_targets") or ())

    return {
        "contract_version": contract_version,
        "tenant_id": _require_uuid(payload, "tenant_id"),
        "pool_id": _require_uuid(payload, "pool_id"),
        "subsystem": subsystem,
        "batch_kind": batch_kind,
        "source_type": source_type,
        "actions": sorted(actions),
        "persistence_targets": list(persistence_targets),
    }


def _normalize_actions(actions: Iterable[str]) -> frozenset[str]:
    normalized = frozenset(
        str(action or "").strip()
        for action in actions
        if str(action or "").strip()
    )
    if not normalized:
        raise _fail("actions must contain at least one intake action")
    disallowed = normalized.intersection(BATCH_INTAKE_DISALLOWED_ACTIONS)
    if disallowed:
        blocked = ",".join(sorted(disallowed))
        raise _fail(f"actions contain disallowed commands: {blocked}")
    unsupported = normalized.difference(BATCH_INTAKE_ALLOWED_ACTIONS)
    if unsupported:
        blocked = ",".join(sorted(unsupported))
        raise _fail(f"actions contain unsupported commands: {blocked}")
    return normalized


def _normalize_persistence_targets(raw_targets: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(
        sorted(
            {
                str(target or "").strip()
                for target in raw_targets
                if str(target or "").strip()
            }
        )
    )
    if not normalized:
        raise _fail("persistence_targets must contain at least one allowed write target")
    forbidden = set(normalized).intersection(BATCH_INTAKE_FORBIDDEN_PERSISTENCE_TARGETS)
    if forbidden:
        blocked = ",".join(sorted(forbidden))
        raise _fail(f"persistence_targets contain forbidden factual ownership targets: {blocked}")
    unsupported = set(normalized).difference(BATCH_INTAKE_PERSISTENCE_TARGETS)
    if unsupported:
        blocked = ",".join(sorted(unsupported))
        raise _fail(f"persistence_targets contain unsupported write targets: {blocked}")
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
    "BATCH_INTAKE_ALLOWED_ACTIONS",
    "BATCH_INTAKE_CONTRACT_INVALID",
    "BATCH_INTAKE_DISALLOWED_ACTIONS",
    "BATCH_INTAKE_FORBIDDEN_PERSISTENCE_TARGETS",
    "BATCH_INTAKE_PERSISTENCE_TARGETS",
    "BATCH_INTAKE_SUBSYSTEM",
    "POOL_BATCH_INTAKE_BOUNDARY_CONTRACT",
    "build_batch_intake_execution_context",
    "validate_batch_intake_execution_context",
]
