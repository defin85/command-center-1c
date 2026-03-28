from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Iterable, Mapping

from django.db import transaction
from django.utils import timezone

from apps.databases.models import Database

from .ccpool_traceability import parse_ccpool_traceability_marker
from .factual_carry_forward import materialize_factual_carry_forward
from .factual_review_models import PoolFactualReviewReason, PoolFactualReviewStatus
from .factual_review_queue import build_pool_factual_review_queue_snapshot
from .factual_sync_runtime import (
    build_factual_sales_report_sync_scope,
    mark_factual_sync_checkpoint_error,
    mark_factual_sync_checkpoint_success,
    resolve_factual_sync_source_state,
)
from .factual_workflow_contract import (
    POOL_FACTUAL_SYNC_WORKFLOW_CONTRACT,
    validate_pool_factual_sync_workflow_input_context,
)
from .models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSettlement,
    PoolBatchSettlementStatus,
    PoolEdgeVersion,
    PoolFactualBalanceSnapshot,
    PoolFactualLane,
    PoolFactualReviewItem,
    PoolFactualSyncCheckpoint,
)


FACTUAL_SYNC_RESULT_STEP = "factual_sync_source_slice"
MONEY_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class _FactualDocumentRecord:
    source_document_ref: str
    organization_id: str | None
    edge_id: str | None
    batch_id: str | None
    amount_with_vat: Decimal
    amount_without_vat: Decimal
    vat_amount: Decimal
    comment: str
    kind: str | None
    modified_at: datetime | None
    unattributed: bool


def is_pool_factual_sync_execution(*, execution) -> bool:
    input_context = execution.input_context if isinstance(execution.input_context, dict) else {}
    return str(input_context.get("contract_version") or "").strip() == POOL_FACTUAL_SYNC_WORKFLOW_CONTRACT


def sync_pool_factual_checkpoint_state_from_execution(*, execution) -> None:
    if not is_pool_factual_sync_execution(execution=execution):
        return

    input_context = validate_pool_factual_sync_workflow_input_context(
        input_context=execution.input_context or {}
    )
    checkpoint = PoolFactualSyncCheckpoint.objects.filter(id=input_context["checkpoint_id"]).first()
    if checkpoint is None:
        return

    next_status = str(execution.status or "").strip()
    update_fields: set[str] = set()
    if checkpoint.workflow_execution_id != execution.id:
        checkpoint.workflow_execution_id = execution.id
        update_fields.add("workflow_execution_id")
    if checkpoint.workflow_status != next_status:
        checkpoint.workflow_status = next_status
        update_fields.add("workflow_status")
    if next_status == "failed":
        next_error_code = str(getattr(execution, "error_code", "") or "").strip()
        next_error = str(getattr(execution, "error_message", "") or "").strip()
    else:
        next_error_code = ""
        next_error = ""
    if checkpoint.last_error_code != next_error_code:
        checkpoint.last_error_code = next_error_code
        update_fields.add("last_error_code")
    if checkpoint.last_error != next_error:
        checkpoint.last_error = next_error
        update_fields.add("last_error")
    if update_fields:
        update_fields.add("updated_at")
        checkpoint.save(update_fields=sorted(update_fields))


def project_pool_factual_result_from_execution(*, execution, result_payload: Mapping[str, Any] | None = None) -> bool:
    if not is_pool_factual_sync_execution(execution=execution):
        return False

    payload = dict(result_payload or execution.final_result or {})
    step_payload = _extract_step_payload(payload)
    if step_payload is None:
        return False

    input_context = validate_pool_factual_sync_workflow_input_context(
        input_context=execution.input_context or {}
    )
    checkpoint = (
        PoolFactualSyncCheckpoint.objects.select_related("tenant", "pool", "database")
        .filter(id=input_context["checkpoint_id"])
        .first()
    )
    if checkpoint is None:
        return False

    database = Database.objects.filter(id=input_context["database_id"]).first()
    if database is None:
        return False

    scope = build_factual_sales_report_sync_scope(
        quarter_start=date.fromisoformat(input_context["quarter_start"]),
        quarter_end=date.fromisoformat(input_context["quarter_end"]),
        organization_ids=input_context["organization_ids"].split(","),
        account_codes=input_context["account_codes"].split(","),
        movement_kinds=input_context["movement_kinds"].split(","),
    )
    source_state = resolve_factual_sync_source_state(database=database)
    source_checkpoint_token = _resolve_source_checkpoint_token(step_payload=step_payload)
    if checkpoint.lane == PoolFactualLane.RECONCILE or _is_frozen_checkpoint(checkpoint=checkpoint):
        _project_late_corrections(
            checkpoint=checkpoint,
            step_payload=step_payload,
        )
        mark_factual_sync_checkpoint_success(
            checkpoint=checkpoint,
            scope=scope,
            source_state=source_state,
            source_checkpoint_token=source_checkpoint_token,
            synced_at=timezone.now(),
        )
        return True

    _materialize_factual_projection(
        checkpoint=checkpoint,
        step_payload=step_payload,
    )
    mark_factual_sync_checkpoint_success(
        checkpoint=checkpoint,
        scope=scope,
        source_state=source_state,
        source_checkpoint_token=source_checkpoint_token,
        synced_at=timezone.now(),
    )

    if bool(input_context.get("freeze_quarter")) and not _is_frozen_checkpoint(checkpoint=checkpoint):
        _freeze_factual_quarter(checkpoint=checkpoint)
    return True


def mark_pool_factual_execution_failed(*, execution) -> bool:
    if not is_pool_factual_sync_execution(execution=execution):
        return False

    input_context = validate_pool_factual_sync_workflow_input_context(
        input_context=execution.input_context or {}
    )
    checkpoint = (
        PoolFactualSyncCheckpoint.objects.select_related("database")
        .filter(id=input_context["checkpoint_id"])
        .first()
    )
    if checkpoint is None:
        return False
    database = Database.objects.filter(id=input_context["database_id"]).first()
    if database is None:
        return False
    scope = build_factual_sales_report_sync_scope(
        quarter_start=date.fromisoformat(input_context["quarter_start"]),
        quarter_end=date.fromisoformat(input_context["quarter_end"]),
        organization_ids=input_context["organization_ids"].split(","),
        account_codes=input_context["account_codes"].split(","),
        movement_kinds=input_context["movement_kinds"].split(","),
    )
    source_state = resolve_factual_sync_source_state(database=database)
    mark_factual_sync_checkpoint_error(
        checkpoint=checkpoint,
        scope=scope,
        source_state=source_state,
        error=f"{execution.error_code or 'POOL_FACTUAL_SYNC_FAILED'}: {execution.error_message or 'workflow failed'}",
        failed_at=timezone.now(),
    )
    return True


def _extract_step_payload(result_payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if str(result_payload.get("step") or "").strip() == FACTUAL_SYNC_RESULT_STEP:
        return dict(result_payload)
    node_results = result_payload.get("node_results")
    if not isinstance(node_results, Mapping):
        return None
    for node_payload in node_results.values():
        if isinstance(node_payload, Mapping) and str(node_payload.get("step") or "").strip() == FACTUAL_SYNC_RESULT_STEP:
            return dict(node_payload)
    return None


def _resolve_source_checkpoint_token(*, step_payload: Mapping[str, Any]) -> str:
    token = str(step_payload.get("source_checkpoint_token") or "").strip()
    if token:
        return token
    fingerprint_payload = {
        "documents": [
            str(item.get("source_document_ref") or "").strip()
            for item in step_payload.get("factual_documents") or []
            if isinstance(item, Mapping)
        ],
        "counts": dict(step_payload.get("boundary_reads") or {}),
    }
    return sha256(repr(fingerprint_payload).encode("utf-8")).hexdigest()


def _parse_decimal(raw_value: Any) -> Decimal:
    try:
        return Decimal(str(raw_value or "0")).quantize(MONEY_QUANT)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT)


def _parse_datetime(raw_value: Any) -> datetime | None:
    if isinstance(raw_value, datetime):
        return raw_value
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_factual_document_records(*, step_payload: Mapping[str, Any], pool_id: str) -> tuple[_FactualDocumentRecord, ...]:
    rows = []
    for raw_row in step_payload.get("factual_documents") or []:
        if not isinstance(raw_row, Mapping):
            continue
        comment = str(raw_row.get("comment") or "").strip()
        marker = parse_ccpool_traceability_marker(comment)
        unattributed = marker is None or marker.get("pool_id") != pool_id
        organization_id = str(
            raw_row.get("organization_id")
            or (marker or {}).get("organization_id")
            or ""
        ).strip() or None
        batch_id = str(
            raw_row.get("batch_id")
            or (marker or {}).get("batch_id")
            or ""
        ).strip() or None
        edge_id = str(raw_row.get("edge_id") or "").strip() or None
        kind = str(raw_row.get("kind") or (marker or {}).get("kind") or "").strip().lower() or None
        rows.append(
            _FactualDocumentRecord(
                source_document_ref=str(raw_row.get("source_document_ref") or "").strip(),
                organization_id=organization_id,
                edge_id=edge_id,
                batch_id=batch_id,
                amount_with_vat=_parse_decimal(raw_row.get("amount_with_vat")),
                amount_without_vat=_parse_decimal(raw_row.get("amount_without_vat")),
                vat_amount=_parse_decimal(raw_row.get("vat_amount")),
                comment=comment,
                kind=kind,
                modified_at=_parse_datetime(raw_row.get("modified_at")),
                unattributed=unattributed,
            )
        )
    return tuple(rows)


def _materialize_factual_projection(*, checkpoint: PoolFactualSyncCheckpoint, step_payload: Mapping[str, Any]) -> None:
    rows = _normalize_factual_document_records(
        step_payload=step_payload,
        pool_id=str(checkpoint.pool_id),
    )
    timestamp = timezone.now()

    with transaction.atomic():
        PoolFactualBalanceSnapshot.objects.filter(
            tenant=checkpoint.tenant,
            pool=checkpoint.pool,
            quarter_start=checkpoint.quarter_start,
            quarter_end=checkpoint.quarter_end,
            metadata__database_id=str(checkpoint.database_id),
        ).delete()
        PoolFactualReviewItem.objects.filter(
            tenant=checkpoint.tenant,
            pool=checkpoint.pool,
            quarter_start=checkpoint.quarter_start,
            quarter_end=checkpoint.quarter_end,
            reason=PoolFactualReviewReason.UNATTRIBUTED,
            metadata__database_id=str(checkpoint.database_id),
            status=PoolFactualReviewStatus.PENDING,
        ).delete()

        aggregates: dict[tuple[str | None, str, str | None], dict[str, Decimal]] = {}
        for row in rows:
            if row.unattributed:
                _create_review_item(
                    checkpoint=checkpoint,
                    reason=PoolFactualReviewReason.UNATTRIBUTED,
                    row=row,
                )

            if not row.organization_id:
                continue

            key = (row.batch_id, row.organization_id, row.edge_id)
            aggregate = aggregates.setdefault(
                key,
                {
                    "incoming_amount": Decimal("0.00"),
                    "outgoing_amount": Decimal("0.00"),
                    "amount_with_vat": Decimal("0.00"),
                    "amount_without_vat": Decimal("0.00"),
                    "vat_amount": Decimal("0.00"),
                },
            )
            sign = Decimal("1.00")
            if row.kind in {"sale", "manual"}:
                aggregate["outgoing_amount"] += row.amount_with_vat.copy_abs()
                sign = Decimal("-1.00")
            else:
                aggregate["incoming_amount"] += row.amount_with_vat.copy_abs()
            aggregate["amount_with_vat"] = _money(aggregate["amount_with_vat"] + (row.amount_with_vat * sign))
            aggregate["amount_without_vat"] = _money(
                aggregate["amount_without_vat"] + (row.amount_without_vat * sign)
            )
            aggregate["vat_amount"] = _money(aggregate["vat_amount"] + (row.vat_amount * sign))

        organizations = {
            str(organization.id): organization
            for organization in Organization.objects.filter(
                id__in={organization_id for _, organization_id, _ in aggregates.keys()}
            )
        }
        edges = {
            str(edge.id): edge
            for edge in PoolEdgeVersion.objects.filter(
                id__in={edge_id for _, _, edge_id in aggregates.keys() if edge_id}
            )
        }
        batches = {
            str(batch.id): batch
            for batch in PoolBatch.objects.filter(
                id__in={batch_id for batch_id, _, _ in aggregates.keys() if batch_id}
            )
        }

        for (batch_id, organization_id, edge_id), aggregate in aggregates.items():
            organization = organizations.get(organization_id)
            if organization is None:
                continue
            PoolFactualBalanceSnapshot.objects.create(
                tenant=checkpoint.tenant,
                pool=checkpoint.pool,
                batch=batches.get(batch_id) if batch_id else None,
                organization=organization,
                edge=edges.get(edge_id) if edge_id else None,
                quarter_start=checkpoint.quarter_start,
                quarter_end=checkpoint.quarter_end,
                amount_with_vat=_money(aggregate["amount_with_vat"]),
                amount_without_vat=_money(aggregate["amount_without_vat"]),
                vat_amount=_money(aggregate["vat_amount"]),
                incoming_amount=_money(aggregate["incoming_amount"]),
                outgoing_amount=_money(aggregate["outgoing_amount"]),
                open_balance=_money(aggregate["incoming_amount"] - aggregate["outgoing_amount"]),
                freshness_at=timestamp,
                metadata={
                    "database_id": str(checkpoint.database_id),
                    "lane": checkpoint.lane,
                    "source_contract": FACTUAL_SYNC_RESULT_STEP,
                },
            )

        _refresh_batch_settlement_snapshots(
            checkpoint=checkpoint,
            refreshed_at=timestamp,
        )


def _refresh_batch_settlement_snapshots(*, checkpoint: PoolFactualSyncCheckpoint, refreshed_at: datetime) -> None:
    for batch in PoolBatch.objects.filter(
        tenant=checkpoint.tenant,
        pool=checkpoint.pool,
        period_start=checkpoint.quarter_start,
    ).select_related("settlement"):
        settlement = getattr(batch, "settlement", None)
        if settlement is None:
            continue
        snapshots = list(
            PoolFactualBalanceSnapshot.objects.filter(
                tenant=checkpoint.tenant,
                batch=batch,
                quarter_start=checkpoint.quarter_start,
                quarter_end=checkpoint.quarter_end,
            )
        )
        incoming_amount = sum((snapshot.incoming_amount for snapshot in snapshots), Decimal("0.00"))
        outgoing_amount = sum((snapshot.outgoing_amount for snapshot in snapshots), Decimal("0.00"))
        open_balance = sum((snapshot.open_balance for snapshot in snapshots), Decimal("0.00"))
        pending_review_exists = PoolFactualReviewItem.objects.filter(
            tenant=checkpoint.tenant,
            pool=checkpoint.pool,
            batch=batch,
            quarter_start=checkpoint.quarter_start,
            quarter_end=checkpoint.quarter_end,
            status=PoolFactualReviewStatus.PENDING,
        ).exists()
        if pending_review_exists:
            next_status = PoolBatchSettlementStatus.ATTENTION_REQUIRED
        elif open_balance == Decimal("0.00") and outgoing_amount > Decimal("0.00"):
            next_status = PoolBatchSettlementStatus.CLOSED
        elif outgoing_amount > Decimal("0.00"):
            next_status = PoolBatchSettlementStatus.PARTIALLY_CLOSED
        elif incoming_amount > Decimal("0.00"):
            next_status = PoolBatchSettlementStatus.DISTRIBUTED
        else:
            next_status = settlement.status or PoolBatchSettlementStatus.INGESTED

        settlement.incoming_amount = incoming_amount
        settlement.outgoing_amount = outgoing_amount
        settlement.open_balance = open_balance
        settlement.status = next_status
        settlement.freshness_at = refreshed_at
        settlement.summary = {
            **dict(settlement.summary or {}),
            "review_queue": build_pool_factual_review_queue_snapshot(
                review_items=PoolFactualReviewItem.objects.filter(
                    tenant=checkpoint.tenant,
                    pool=checkpoint.pool,
                    batch=batch,
                    quarter_start=checkpoint.quarter_start,
                    quarter_end=checkpoint.quarter_end,
                )
            ),
        }
        settlement.save(
            update_fields=[
                "incoming_amount",
                "outgoing_amount",
                "open_balance",
                "status",
                "freshness_at",
                "summary",
                "updated_at",
            ]
        )


def _create_review_item(*, checkpoint: PoolFactualSyncCheckpoint, reason: str, row: _FactualDocumentRecord) -> None:
    organization = Organization.objects.filter(id=row.organization_id).first() if row.organization_id else None
    batch = PoolBatch.objects.filter(id=row.batch_id).first() if row.batch_id else None
    edge = PoolEdgeVersion.objects.filter(id=row.edge_id).first() if row.edge_id else None
    PoolFactualReviewItem.objects.update_or_create(
        tenant=checkpoint.tenant,
        pool=checkpoint.pool,
        quarter_start=checkpoint.quarter_start,
        quarter_end=checkpoint.quarter_end,
        reason=reason,
        source_document_ref=row.source_document_ref,
        defaults={
            "batch": batch,
            "organization": organization,
            "edge": edge,
            "status": PoolFactualReviewStatus.PENDING,
            "delta_payload": {
                "amount_with_vat": f"{row.amount_with_vat:.2f}",
                "amount_without_vat": f"{row.amount_without_vat:.2f}",
                "vat_amount": f"{row.vat_amount:.2f}",
                "comment": row.comment,
            },
            "metadata": {
                "database_id": str(checkpoint.database_id),
                "lane": checkpoint.lane,
                "modified_at": row.modified_at.isoformat() if row.modified_at else "",
                "raw_organization_id": row.organization_id or "",
            },
            "resolved_by": None,
            "resolved_at": None,
        },
    )


def _freeze_factual_quarter(*, checkpoint: PoolFactualSyncCheckpoint) -> None:
    snapshots = list(
        PoolFactualBalanceSnapshot.objects.filter(
            tenant=checkpoint.tenant,
            pool=checkpoint.pool,
            quarter_start=checkpoint.quarter_start,
            quarter_end=checkpoint.quarter_end,
        )
    )
    for snapshot in snapshots:
        materialize_factual_carry_forward(source_snapshot=snapshot, applied_at=timezone.now())
    metadata = dict(checkpoint.metadata or {})
    metadata["frozen_at"] = timezone.now().isoformat()
    checkpoint.metadata = metadata
    checkpoint.save(update_fields=["metadata", "updated_at"])


def _is_frozen_checkpoint(*, checkpoint: PoolFactualSyncCheckpoint) -> bool:
    metadata = checkpoint.metadata if isinstance(checkpoint.metadata, dict) else {}
    return bool(str(metadata.get("frozen_at") or "").strip())


def _project_late_corrections(*, checkpoint: PoolFactualSyncCheckpoint, step_payload: Mapping[str, Any]) -> None:
    rows = _normalize_factual_document_records(
        step_payload=step_payload,
        pool_id=str(checkpoint.pool_id),
    )
    for row in rows:
        _create_review_item(
            checkpoint=checkpoint,
            reason=PoolFactualReviewReason.LATE_CORRECTION,
            row=row,
        )


__all__ = [
    "FACTUAL_SYNC_RESULT_STEP",
    "is_pool_factual_sync_execution",
    "mark_pool_factual_execution_failed",
    "project_pool_factual_result_from_execution",
    "sync_pool_factual_checkpoint_state_from_execution",
]
