from __future__ import annotations

from collections import Counter
from datetime import datetime
import logging
from typing import Any, Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import (
    Organization,
    PoolBatch,
    PoolEdgeVersion,
    PoolFactualReviewItem,
    PoolFactualReviewReason,
    PoolFactualReviewStatus,
)


User = get_user_model()
logger = logging.getLogger(__name__)

POOL_FACTUAL_REVIEW_QUEUE_CONTRACT = "pool_factual_review_queue.v1"
POOL_FACTUAL_REVIEW_QUEUE_INVALID = "POOL_FACTUAL_REVIEW_QUEUE_INVALID"
POOL_FACTUAL_REVIEW_QUEUE_SUBSYSTEM = "reconcile_review"

FACTUAL_REVIEW_ACTION_ATTRIBUTE = "attribute"
FACTUAL_REVIEW_ACTION_RECONCILE = "reconcile"
FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE = "resolve_without_change"

_ALLOWED_PENDING_ACTIONS_BY_REASON = {
    PoolFactualReviewReason.UNATTRIBUTED: frozenset(
        {
            FACTUAL_REVIEW_ACTION_ATTRIBUTE,
            FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE,
        }
    ),
    PoolFactualReviewReason.LATE_CORRECTION: frozenset(
        {
            FACTUAL_REVIEW_ACTION_RECONCILE,
            FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE,
        }
    ),
}

_STATUS_BY_ACTION = {
    FACTUAL_REVIEW_ACTION_ATTRIBUTE: PoolFactualReviewStatus.ATTRIBUTED,
    FACTUAL_REVIEW_ACTION_RECONCILE: PoolFactualReviewStatus.RECONCILED,
    FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE: PoolFactualReviewStatus.RESOLVED_WITHOUT_CHANGE,
}


def _fail(detail: str) -> ValueError:
    return ValueError(f"{POOL_FACTUAL_REVIEW_QUEUE_INVALID}: {detail}")


@transaction.atomic
def apply_pool_factual_review_action(
    *,
    review_item_id: str,
    tenant_id: str,
    actor_id: str,
    action: str,
    batch_id: str | None = None,
    edge_id: str | None = None,
    organization_id: str | None = None,
    note: str = "",
    metadata: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> PoolFactualReviewItem:
    normalized_action = str(action or "").strip()
    if normalized_action not in _STATUS_BY_ACTION:
        raise _fail(f"unsupported factual review action '{normalized_action or '<empty>'}'")

    review_item = (
        PoolFactualReviewItem.objects.select_for_update()
        .get(id=review_item_id, tenant_id=tenant_id)
    )
    if review_item.status != PoolFactualReviewStatus.PENDING:
        raise _fail(f"review item '{review_item.id}' is already resolved with status '{review_item.status}'")

    allowed_actions = _allowed_actions(reason=review_item.reason, status=review_item.status)
    if normalized_action not in allowed_actions:
        raise _fail(
            f"action '{normalized_action}' is not allowed for reason '{review_item.reason}'"
        )

    actor = User.objects.get(id=actor_id)
    resolved_at = now or timezone.now()
    original_batch_id = str(review_item.batch_id) if review_item.batch_id else None
    original_edge_id = str(review_item.edge_id) if review_item.edge_id else None
    original_organization_id = str(review_item.organization_id) if review_item.organization_id else None

    batch = _load_batch(batch_id=batch_id, tenant_id=tenant_id)
    edge = _load_edge(edge_id=edge_id, pool_id=str(review_item.pool_id))
    organization = _load_organization(organization_id=organization_id, tenant_id=tenant_id)

    if normalized_action == FACTUAL_REVIEW_ACTION_ATTRIBUTE and not any((batch, edge, organization)):
        raise _fail("attribute action requires at least one attribution target")

    if batch is not None:
        review_item.batch = batch
    if edge is not None:
        review_item.edge = edge
    if organization is not None:
        review_item.organization = organization

    review_item.status = _STATUS_BY_ACTION[normalized_action]
    review_item.resolved_by = actor
    review_item.resolved_at = resolved_at
    review_item.metadata = _append_operator_action(
        current_metadata=review_item.metadata,
        action=normalized_action,
        actor_id=str(actor.id),
        resolved_at=resolved_at,
        note=note,
        metadata=metadata,
        batch_id=str(batch.id) if batch is not None else None,
        edge_id=str(edge.id) if edge is not None else None,
        organization_id=str(organization.id) if organization is not None else None,
    )
    review_item.save()
    from .factual_result_projection import apply_pool_factual_review_resolution_to_projection

    apply_pool_factual_review_resolution_to_projection(
        review_item=review_item,
        action=normalized_action,
        original_batch_id=original_batch_id,
        original_edge_id=original_edge_id,
        original_organization_id=original_organization_id,
        applied_at=resolved_at,
    )
    _refresh_factual_rollout_telemetry(timestamp=resolved_at)
    return review_item


def build_pool_factual_review_queue_snapshot(
    *,
    review_items: Iterable[PoolFactualReviewItem],
) -> dict[str, Any]:
    items = [
        _serialize_review_item(item=item)
        for item in sorted(review_items, key=lambda item: (item.created_at, str(item.id)), reverse=True)
    ]
    counts = Counter(item["reason"] for item in items if item["status"] == PoolFactualReviewStatus.PENDING)
    return {
        "contract_version": POOL_FACTUAL_REVIEW_QUEUE_CONTRACT,
        "subsystem": POOL_FACTUAL_REVIEW_QUEUE_SUBSYSTEM,
        "summary": {
            "pending_total": sum(1 for item in items if item["status"] == PoolFactualReviewStatus.PENDING),
            "unattributed_total": counts[PoolFactualReviewReason.UNATTRIBUTED],
            "late_correction_total": counts[PoolFactualReviewReason.LATE_CORRECTION],
            "attention_required_total": sum(1 for item in items if item["attention_required"]),
        },
        "items": items,
    }


def _serialize_review_item(*, item: PoolFactualReviewItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "pool_id": str(item.pool_id),
        "batch_id": str(item.batch_id) if item.batch_id else None,
        "organization_id": str(item.organization_id) if item.organization_id else None,
        "edge_id": str(item.edge_id) if item.edge_id else None,
        "reason": item.reason,
        "status": item.status,
        "quarter": _format_quarter(item.quarter_start),
        "source_document_ref": item.source_document_ref,
        "allowed_actions": sorted(_allowed_actions(reason=item.reason, status=item.status)),
        "attention_required": (
            item.reason == PoolFactualReviewReason.LATE_CORRECTION
            and item.status == PoolFactualReviewStatus.PENDING
        ),
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
    }


def _allowed_actions(*, reason: str, status: str) -> frozenset[str]:
    if status != PoolFactualReviewStatus.PENDING:
        return frozenset()
    return _ALLOWED_PENDING_ACTIONS_BY_REASON.get(reason, frozenset())


def _append_operator_action(
    *,
    current_metadata: Any,
    action: str,
    actor_id: str,
    resolved_at: datetime,
    note: str,
    metadata: dict[str, Any] | None,
    batch_id: str | None,
    edge_id: str | None,
    organization_id: str | None,
) -> dict[str, Any]:
    payload = dict(current_metadata or {})
    operator_actions = list(payload.get("operator_actions") or [])

    action_snapshot = {
        "action": action,
        "actor_id": actor_id,
        "at": resolved_at.isoformat(),
        "note": str(note or "").strip(),
        "metadata": dict(metadata or {}),
    }
    if batch_id is not None:
        action_snapshot["batch_id"] = batch_id
    if edge_id is not None:
        action_snapshot["edge_id"] = edge_id
    if organization_id is not None:
        action_snapshot["organization_id"] = organization_id

    operator_actions.append(action_snapshot)
    payload["operator_actions"] = operator_actions
    payload["last_resolution"] = action_snapshot
    return payload


def _format_quarter(quarter_start) -> str:
    quarter = ((quarter_start.month - 1) // 3) + 1
    return f"{quarter_start.year}Q{quarter}"


def _load_batch(*, batch_id: str | None, tenant_id: str) -> PoolBatch | None:
    if not batch_id:
        return None
    return PoolBatch.objects.get(id=batch_id, tenant_id=tenant_id)


def _load_edge(*, edge_id: str | None, pool_id: str) -> PoolEdgeVersion | None:
    if not edge_id:
        return None
    return PoolEdgeVersion.objects.get(id=edge_id, pool_id=pool_id)


def _load_organization(*, organization_id: str | None, tenant_id: str) -> Organization | None:
    if not organization_id:
        return None
    return Organization.objects.get(id=organization_id, tenant_id=tenant_id)


def _refresh_factual_rollout_telemetry(*, timestamp: datetime) -> None:
    try:
        from .factual_observability import record_pool_factual_rollout_telemetry

        record_pool_factual_rollout_telemetry(now=timestamp)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to record factual rollout telemetry: %s", exc)


__all__ = [
    "FACTUAL_REVIEW_ACTION_ATTRIBUTE",
    "FACTUAL_REVIEW_ACTION_RECONCILE",
    "FACTUAL_REVIEW_ACTION_RESOLVE_WITHOUT_CHANGE",
    "POOL_FACTUAL_REVIEW_QUEUE_CONTRACT",
    "POOL_FACTUAL_REVIEW_QUEUE_INVALID",
    "POOL_FACTUAL_REVIEW_QUEUE_SUBSYSTEM",
    "apply_pool_factual_review_action",
    "build_pool_factual_review_queue_snapshot",
]
