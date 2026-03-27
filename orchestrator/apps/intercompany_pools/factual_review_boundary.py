from __future__ import annotations

from typing import Any, Iterable, Mapping
from uuid import UUID


POOL_FACTUAL_REVIEW_BOUNDARY_CONTRACT = "pool_factual_review_boundary.v1"
FACTUAL_REVIEW_BOUNDARY_INVALID = "POOL_FACTUAL_REVIEW_BOUNDARY_INVALID"
FACTUAL_REVIEW_SUBSYSTEM = "reconcile_review"
FACTUAL_REVIEW_LANE = "review"

FACTUAL_REVIEW_ALLOWED_ACTIONS = frozenset(
    {
        "enqueue_manual_review",
        "attribute",
        "reconcile",
        "resolve_without_change",
    }
)
FACTUAL_REVIEW_DISALLOWED_ACTIONS = frozenset(
    {
        "normalize_batch_payload",
        "persist_batch_provenance",
        "kickoff_receipt_run",
        "build_sale_closing_contract",
        "create_run",
        "start_run",
        "confirm_publication",
        "retry_publication",
        "sync_source_slice",
        "refresh_batch_settlement",
        "materialize_carry_forward",
    }
)
FACTUAL_REVIEW_PERSISTENCE_TARGETS = ("pool_factual_review_items",)
FACTUAL_REVIEW_FORBIDDEN_PERSISTENCE_TARGETS = frozenset(
    {
        "pool_batches",
        "pool_runs",
        "pool_run_audit_events",
        "pool_batch_settlements",
        "pool_factual_balance_snapshots",
        "pool_factual_sync_checkpoints",
    }
)
FACTUAL_REVIEW_PROTECTED_CONTRACTS = (
    "batch_intake_contract",
    "pool_run_status",
)


def _fail(detail: str) -> ValueError:
    return ValueError(f"{FACTUAL_REVIEW_BOUNDARY_INVALID}: {detail}")


def build_factual_review_execution_context(
    *,
    tenant_id: str,
    pool_id: str,
    actions: Iterable[str],
    persistence_targets: Iterable[str] = FACTUAL_REVIEW_PERSISTENCE_TARGETS,
) -> dict[str, Any]:
    payload = {
        "contract_version": POOL_FACTUAL_REVIEW_BOUNDARY_CONTRACT,
        "tenant_id": str(tenant_id or "").strip(),
        "pool_id": str(pool_id or "").strip(),
        "subsystem": FACTUAL_REVIEW_SUBSYSTEM,
        "lane": FACTUAL_REVIEW_LANE,
        "actions": sorted(_normalize_actions(actions)),
        "persistence_targets": list(_normalize_persistence_targets(persistence_targets)),
        "protected_contracts": list(FACTUAL_REVIEW_PROTECTED_CONTRACTS),
    }
    return validate_factual_review_execution_context(input_context=payload)


def validate_factual_review_execution_context(*, input_context: Any) -> dict[str, Any]:
    if not isinstance(input_context, Mapping):
        raise _fail("input_context must be an object")

    payload = dict(input_context)
    contract_version = _require_token(payload, "contract_version")
    if contract_version != POOL_FACTUAL_REVIEW_BOUNDARY_CONTRACT:
        raise _fail(f"unsupported contract version '{contract_version}'")

    subsystem = _require_token(payload, "subsystem")
    if subsystem != FACTUAL_REVIEW_SUBSYSTEM:
        raise _fail(f"subsystem must be '{FACTUAL_REVIEW_SUBSYSTEM}', got '{subsystem}'")

    lane = _require_token(payload, "lane")
    if lane != FACTUAL_REVIEW_LANE:
        raise _fail(f"lane must be '{FACTUAL_REVIEW_LANE}', got '{lane}'")

    actions = _normalize_actions(payload.get("actions") or ())
    persistence_targets = _normalize_persistence_targets(payload.get("persistence_targets") or ())
    protected_contracts = tuple(
        sorted(
            {
                str(contract or "").strip()
                for contract in (payload.get("protected_contracts") or ())
                if str(contract or "").strip()
            }
        )
    )
    if protected_contracts != FACTUAL_REVIEW_PROTECTED_CONTRACTS:
        expected = ",".join(FACTUAL_REVIEW_PROTECTED_CONTRACTS)
        actual = ",".join(protected_contracts)
        raise _fail(
            "protected_contracts must be exactly "
            f"'{expected}', got '{actual or '<empty>'}'"
        )

    return {
        "contract_version": contract_version,
        "tenant_id": _require_uuid(payload, "tenant_id"),
        "pool_id": _require_uuid(payload, "pool_id"),
        "subsystem": subsystem,
        "lane": lane,
        "actions": sorted(actions),
        "persistence_targets": list(persistence_targets),
        "protected_contracts": list(protected_contracts),
    }


def _normalize_actions(actions: Iterable[str]) -> frozenset[str]:
    normalized = frozenset(
        str(action or "").strip()
        for action in actions
        if str(action or "").strip()
    )
    if not normalized:
        raise _fail("actions must contain at least one review action")
    disallowed = normalized.intersection(FACTUAL_REVIEW_DISALLOWED_ACTIONS)
    if disallowed:
        blocked = ",".join(sorted(disallowed))
        raise _fail(f"actions contain disallowed commands: {blocked}")
    unsupported = normalized.difference(FACTUAL_REVIEW_ALLOWED_ACTIONS)
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
    if normalized != FACTUAL_REVIEW_PERSISTENCE_TARGETS:
        forbidden = set(normalized).intersection(FACTUAL_REVIEW_FORBIDDEN_PERSISTENCE_TARGETS)
        if forbidden:
            blocked = ",".join(sorted(forbidden))
            raise _fail(f"persistence_targets contain forbidden ownership targets: {blocked}")
        expected = ",".join(FACTUAL_REVIEW_PERSISTENCE_TARGETS)
        actual = ",".join(normalized)
        raise _fail(
            "persistence_targets must be exactly "
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
    "FACTUAL_REVIEW_ALLOWED_ACTIONS",
    "FACTUAL_REVIEW_BOUNDARY_INVALID",
    "FACTUAL_REVIEW_DISALLOWED_ACTIONS",
    "FACTUAL_REVIEW_FORBIDDEN_PERSISTENCE_TARGETS",
    "FACTUAL_REVIEW_LANE",
    "FACTUAL_REVIEW_PERSISTENCE_TARGETS",
    "FACTUAL_REVIEW_PROTECTED_CONTRACTS",
    "FACTUAL_REVIEW_SUBSYSTEM",
    "POOL_FACTUAL_REVIEW_BOUNDARY_CONTRACT",
    "build_factual_review_execution_context",
    "validate_factual_review_execution_context",
]
