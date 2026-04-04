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
from .factual_sale_attribution import (
    apply_leaf_sale_attribution_plan,
    build_leaf_sale_attribution_plan,
)
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


def _build_scope_kwargs_from_input_context(*, input_context: Mapping[str, Any]) -> dict[str, Any]:
    factual_scope_contract = (
        dict(input_context.get("factual_scope_contract") or {})
        if isinstance(input_context.get("factual_scope_contract"), Mapping)
        else {}
    )
    return {
        "quarter_start": date.fromisoformat(str(input_context["quarter_start"])),
        "quarter_end": date.fromisoformat(str(input_context["quarter_end"])),
        "organization_ids": str(input_context["organization_ids"]).split(","),
        "account_codes": str(input_context["account_codes"]).split(","),
        "movement_kinds": str(input_context["movement_kinds"]).split(","),
        "selector_key": str(factual_scope_contract.get("selector_key") or ""),
        "gl_account_set_id": str(factual_scope_contract.get("gl_account_set_id") or ""),
        "gl_account_set_revision_id": str(factual_scope_contract.get("gl_account_set_revision_id") or ""),
        "effective_members": tuple(factual_scope_contract.get("effective_members") or ()),
        "resolved_bindings": tuple(factual_scope_contract.get("resolved_bindings") or ()),
        "contract_version": str(factual_scope_contract.get("contract_version") or ""),
    }


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


def _load_resolved_review_items(*, checkpoint: PoolFactualSyncCheckpoint) -> dict[str, PoolFactualReviewItem]:
    resolved_items = (
        PoolFactualReviewItem.objects.filter(
            tenant=checkpoint.tenant,
            pool=checkpoint.pool,
            quarter_start=checkpoint.quarter_start,
            quarter_end=checkpoint.quarter_end,
            reason=PoolFactualReviewReason.UNATTRIBUTED,
        )
        .exclude(status=PoolFactualReviewStatus.PENDING)
        .order_by("created_at", "id")
    )
    return {
        str(item.source_document_ref): item
        for item in resolved_items
        if str(item.source_document_ref or "").strip()
    }


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
    review_resolutions = _load_resolved_review_items(checkpoint=checkpoint)
    rows = _normalize_factual_document_records(
        step_payload=step_payload,
        pool_id=str(checkpoint.pool_id),
        review_resolutions=review_resolutions,
    )

    scope = build_factual_sales_report_sync_scope(
        **_build_scope_kwargs_from_input_context(input_context=input_context),
    )
    source_state = resolve_factual_sync_source_state(database=database)
    source_checkpoint_token = _resolve_source_checkpoint_token(step_payload=step_payload)
    if checkpoint.lane == PoolFactualLane.RECONCILE or _is_frozen_checkpoint(checkpoint=checkpoint):
        _project_late_corrections(
            checkpoint=checkpoint,
            rows=rows,
        )
        _remember_checkpoint_source_documents(checkpoint=checkpoint, rows=rows)
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
        rows=rows,
    )
    _remember_checkpoint_source_documents(checkpoint=checkpoint, rows=rows)
    mark_factual_sync_checkpoint_success(
        checkpoint=checkpoint,
        scope=scope,
        source_state=source_state,
        source_checkpoint_token=source_checkpoint_token,
        synced_at=timezone.now(),
    )

    if bool(input_context.get("freeze_quarter")) and not _is_frozen_checkpoint(checkpoint=checkpoint):
        _freeze_factual_quarter(checkpoint=checkpoint, rows=rows)
    return True


def apply_pool_factual_review_resolution_to_projection(
    *,
    review_item: PoolFactualReviewItem,
    action: str,
    original_batch_id: str | None = None,
    original_edge_id: str | None = None,
    original_organization_id: str | None = None,
    applied_at: datetime | None = None,
) -> bool:
    normalized_action = str(action or "").strip()
    timestamp = applied_at or timezone.now()
    changed = False
    if (
        normalized_action == "attribute"
        and review_item.reason == PoolFactualReviewReason.UNATTRIBUTED
    ):
        changed = _move_unattributed_review_item_to_resolved_target(
            review_item=review_item,
            original_batch_id=original_batch_id,
            original_edge_id=original_edge_id,
            original_organization_id=original_organization_id,
            applied_at=timestamp,
        )

    refresh_pool_factual_batch_settlement_snapshots(
        tenant=review_item.tenant,
        pool=review_item.pool,
        quarter_start=review_item.quarter_start,
        quarter_end=review_item.quarter_end,
        refreshed_at=timestamp,
    )
    return changed


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
        **_build_scope_kwargs_from_input_context(input_context=input_context),
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


def _normalize_factual_document_records(
    *,
    step_payload: Mapping[str, Any],
    pool_id: str,
    review_resolutions: Mapping[str, PoolFactualReviewItem] | None = None,
) -> tuple[_FactualDocumentRecord, ...]:
    rows = []
    resolved_items = dict(review_resolutions or {})
    for raw_row in step_payload.get("factual_documents") or []:
        if not isinstance(raw_row, Mapping):
            continue
        source_document_ref = str(raw_row.get("source_document_ref") or "").strip()
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
        resolution = resolved_items.get(source_document_ref)
        if resolution is not None and resolution.reason == PoolFactualReviewReason.UNATTRIBUTED:
            unattributed = False
            if resolution.status == PoolFactualReviewStatus.ATTRIBUTED:
                organization_id = str(resolution.organization_id or organization_id or "").strip() or None
                batch_id = str(resolution.batch_id or batch_id or "").strip() or None
                edge_id = str(resolution.edge_id or edge_id or "").strip() or None
        rows.append(
            _FactualDocumentRecord(
                source_document_ref=source_document_ref,
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


def _materialize_factual_projection(*, checkpoint: PoolFactualSyncCheckpoint, rows: Iterable[_FactualDocumentRecord]) -> None:
    timestamp = timezone.now()
    leaf_sale_rows: list[_FactualDocumentRecord] = []

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

            if row.kind == "sale" and not row.unattributed and not row.edge_id:
                leaf_sale_rows.append(row)
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

        _apply_leaf_sale_attribution_rows(
            checkpoint=checkpoint,
            rows=leaf_sale_rows,
            applied_at=timestamp,
        )

        refresh_pool_factual_batch_settlement_snapshots(
            tenant=checkpoint.tenant,
            pool=checkpoint.pool,
            quarter_start=checkpoint.quarter_start,
            quarter_end=checkpoint.quarter_end,
            refreshed_at=timestamp,
        )


def refresh_pool_factual_batch_settlement_snapshots(
    *,
    tenant,
    pool,
    quarter_start: date,
    quarter_end: date,
    refreshed_at: datetime,
) -> None:
    for batch in PoolBatch.objects.filter(
        tenant=tenant,
        pool=pool,
        period_start__gte=quarter_start,
        period_start__lte=quarter_end,
    ).select_related("settlement"):
        settlement = getattr(batch, "settlement", None)
        if settlement is None:
            continue
        snapshots = list(
            PoolFactualBalanceSnapshot.objects.filter(
                tenant=tenant,
                batch=batch,
                quarter_start=quarter_start,
                quarter_end=quarter_end,
            )
        )
        incoming_amount = sum((snapshot.incoming_amount for snapshot in snapshots), Decimal("0.00"))
        outgoing_amount = sum((snapshot.outgoing_amount for snapshot in snapshots), Decimal("0.00"))
        open_balance = sum((snapshot.open_balance for snapshot in snapshots), Decimal("0.00"))
        pending_review_exists = PoolFactualReviewItem.objects.filter(
            tenant=tenant,
            pool=pool,
            batch=batch,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            status=PoolFactualReviewStatus.PENDING,
        ).exists()
        carry_forward_summary = dict(settlement.summary or {}).get("carry_forward")
        if pending_review_exists:
            next_status = PoolBatchSettlementStatus.ATTENTION_REQUIRED
        elif isinstance(carry_forward_summary, dict) and carry_forward_summary:
            next_status = PoolBatchSettlementStatus.CARRIED_FORWARD
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
                    tenant=tenant,
                    pool=pool,
                    batch=batch,
                    quarter_start=quarter_start,
                    quarter_end=quarter_end,
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


def _apply_leaf_sale_attribution_rows(
    *,
    checkpoint: PoolFactualSyncCheckpoint,
    rows: Iterable[_FactualDocumentRecord],
    applied_at: datetime,
) -> None:
    leaf_sale_rows = [row for row in rows if row.organization_id and row.amount_with_vat.copy_abs() > Decimal("0.00")]
    if not leaf_sale_rows:
        return

    organizations = {
        str(organization.id): organization
        for organization in Organization.objects.filter(
            id__in={row.organization_id for row in leaf_sale_rows if row.organization_id}
        )
    }
    for row in leaf_sale_rows:
        organization = organizations.get(str(row.organization_id))
        if organization is None:
            continue
        candidate_snapshots = list(
            PoolFactualBalanceSnapshot.objects.filter(
                tenant=checkpoint.tenant,
                pool=checkpoint.pool,
                organization=organization,
                quarter_start=checkpoint.quarter_start,
                quarter_end=checkpoint.quarter_end,
                open_balance__gt=Decimal("0.00"),
            ).order_by("quarter_start", "created_at", "batch_id", "edge_id", "id")
        )
        plan = build_leaf_sale_attribution_plan(
            organization=organization,
            snapshots=candidate_snapshots,
            sale_amount=row.amount_with_vat.copy_abs(),
        )
        if plan.allocations:
            apply_leaf_sale_attribution_plan(plan=plan, applied_at=applied_at)
        if plan.unattributed_amount > Decimal("0.00"):
            _apply_leaf_sale_remainder_to_org_snapshot(
                checkpoint=checkpoint,
                row=row,
                remainder_with_vat=plan.unattributed_amount,
                applied_at=applied_at,
            )


def _create_review_item(*, checkpoint: PoolFactualSyncCheckpoint, reason: str, row: _FactualDocumentRecord) -> None:
    organization = Organization.objects.filter(id=row.organization_id).first() if row.organization_id else None
    batch = PoolBatch.objects.filter(id=row.batch_id).first() if row.batch_id else None
    edge = PoolEdgeVersion.objects.filter(id=row.edge_id).first() if row.edge_id else None
    metadata_payload = {
        "database_id": str(checkpoint.database_id),
        "lane": checkpoint.lane,
        "modified_at": row.modified_at.isoformat() if row.modified_at else "",
        "raw_organization_id": row.organization_id or "",
        "raw_batch_id": row.batch_id or "",
        "raw_edge_id": row.edge_id or "",
        "source_signature": _build_review_item_signature(row=row),
        "kind": row.kind or "",
    }
    delta_payload = {
        "amount_with_vat": f"{row.amount_with_vat:.2f}",
        "amount_without_vat": f"{row.amount_without_vat:.2f}",
        "vat_amount": f"{row.vat_amount:.2f}",
        "comment": row.comment,
        "kind": row.kind or "",
    }
    existing = PoolFactualReviewItem.objects.filter(
        tenant=checkpoint.tenant,
        pool=checkpoint.pool,
        quarter_start=checkpoint.quarter_start,
        quarter_end=checkpoint.quarter_end,
        reason=reason,
        source_document_ref=row.source_document_ref,
    ).first()
    if existing is not None:
        preserved_metadata = dict(existing.metadata or {})
        preserved_metadata.update(metadata_payload)
        existing.delta_payload = delta_payload
        existing.metadata = preserved_metadata
        if existing.status == PoolFactualReviewStatus.PENDING:
            existing.batch = batch
            existing.organization = organization
            existing.edge = edge
            existing.resolved_by = None
            existing.resolved_at = None
        existing.save()
        return

    PoolFactualReviewItem.objects.create(
        tenant=checkpoint.tenant,
        pool=checkpoint.pool,
        batch=batch,
        organization=organization,
        edge=edge,
        quarter_start=checkpoint.quarter_start,
        quarter_end=checkpoint.quarter_end,
        reason=reason,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref=row.source_document_ref,
        delta_payload=delta_payload,
        metadata=metadata_payload,
    )


def _freeze_factual_quarter(*, checkpoint: PoolFactualSyncCheckpoint, rows: Iterable[_FactualDocumentRecord]) -> None:
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
    metadata["frozen_source_documents"] = _build_source_document_snapshot(rows)
    checkpoint.metadata = metadata
    checkpoint.save(update_fields=["metadata", "updated_at"])


def _is_frozen_checkpoint(*, checkpoint: PoolFactualSyncCheckpoint) -> bool:
    metadata = checkpoint.metadata if isinstance(checkpoint.metadata, dict) else {}
    return bool(str(metadata.get("frozen_at") or "").strip())


def _project_late_corrections(*, checkpoint: PoolFactualSyncCheckpoint, rows: Iterable[_FactualDocumentRecord]) -> None:
    current_documents = _build_source_document_snapshot(rows)
    baseline_documents = _resolve_late_correction_baseline(checkpoint=checkpoint)
    if not baseline_documents:
        return
    for source_document_ref in sorted(set(current_documents) | set(baseline_documents)):
        current_payload = current_documents.get(source_document_ref)
        baseline_payload = baseline_documents.get(source_document_ref)
        if current_payload == baseline_payload:
            continue
        row = _deserialize_source_document_snapshot(current_payload or baseline_payload)
        _upsert_late_correction_review_item(
            checkpoint=checkpoint,
            row=row,
            source_signature=_build_late_correction_signature(
                baseline_payload=baseline_payload,
                current_payload=current_payload,
            ),
            change_type=_resolve_late_correction_change_type(
                baseline_payload=baseline_payload,
                current_payload=current_payload,
            ),
        )


def _upsert_late_correction_review_item(
    *,
    checkpoint: PoolFactualSyncCheckpoint,
    row: _FactualDocumentRecord,
    source_signature: str,
    change_type: str,
) -> PoolFactualReviewItem:
    organization = Organization.objects.filter(id=row.organization_id).first() if row.organization_id else None
    batch = PoolBatch.objects.filter(id=row.batch_id).first() if row.batch_id else None
    edge = PoolEdgeVersion.objects.filter(id=row.edge_id).first() if row.edge_id else None
    delta_payload = {
        "amount_with_vat": f"{row.amount_with_vat:.2f}",
        "amount_without_vat": f"{row.amount_without_vat:.2f}",
        "vat_amount": f"{row.vat_amount:.2f}",
        "comment": row.comment,
        "kind": row.kind or "",
    }
    metadata = {
        "database_id": str(checkpoint.database_id),
        "lane": checkpoint.lane,
        "modified_at": row.modified_at.isoformat() if row.modified_at else "",
        "raw_organization_id": row.organization_id or "",
        "raw_batch_id": row.batch_id or "",
        "raw_edge_id": row.edge_id or "",
        "source_signature": source_signature,
        "kind": row.kind or "",
        "change_type": change_type,
    }

    existing = PoolFactualReviewItem.objects.filter(
        tenant=checkpoint.tenant,
        pool=checkpoint.pool,
        quarter_start=checkpoint.quarter_start,
        quarter_end=checkpoint.quarter_end,
        reason=PoolFactualReviewReason.LATE_CORRECTION,
        source_document_ref=row.source_document_ref,
    ).first()
    if existing is not None:
        existing_signature = str((existing.metadata or {}).get("source_signature") or "").strip()
        if existing_signature == source_signature:
            return existing
        existing.batch = batch
        existing.organization = organization
        existing.edge = edge
        existing.status = PoolFactualReviewStatus.PENDING
        existing.delta_payload = delta_payload
        existing.metadata = metadata
        existing.resolved_by = None
        existing.resolved_at = None
        existing.save()
        return existing

    return PoolFactualReviewItem.objects.create(
        tenant=checkpoint.tenant,
        pool=checkpoint.pool,
        batch=batch,
        organization=organization,
        edge=edge,
        quarter_start=checkpoint.quarter_start,
        quarter_end=checkpoint.quarter_end,
        reason=PoolFactualReviewReason.LATE_CORRECTION,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref=row.source_document_ref,
        delta_payload=delta_payload,
        metadata=metadata,
    )


def _remember_checkpoint_source_documents(*, checkpoint: PoolFactualSyncCheckpoint, rows: Iterable[_FactualDocumentRecord]) -> None:
    metadata = dict(checkpoint.metadata or {})
    metadata["latest_source_documents"] = _build_source_document_snapshot(rows)
    checkpoint.metadata = metadata
    checkpoint.save(update_fields=["metadata", "updated_at"])


def _build_source_document_snapshot(rows: Iterable[_FactualDocumentRecord]) -> dict[str, dict[str, str]]:
    return {
        row.source_document_ref: {
            "source_document_ref": row.source_document_ref,
            "organization_id": row.organization_id or "",
            "batch_id": row.batch_id or "",
            "edge_id": row.edge_id or "",
            "amount_with_vat": f"{row.amount_with_vat:.2f}",
            "amount_without_vat": f"{row.amount_without_vat:.2f}",
            "vat_amount": f"{row.vat_amount:.2f}",
            "comment": row.comment,
            "kind": row.kind or "",
            "modified_at": row.modified_at.isoformat() if row.modified_at else "",
            "unattributed": "1" if row.unattributed else "0",
        }
        for row in rows
    }


def _deserialize_source_document_snapshot(payload: Mapping[str, Any] | None) -> _FactualDocumentRecord:
    document = dict(payload or {})
    return _FactualDocumentRecord(
        source_document_ref=str(document.get("source_document_ref") or "").strip(),
        organization_id=str(document.get("organization_id") or "").strip() or None,
        edge_id=str(document.get("edge_id") or "").strip() or None,
        batch_id=str(document.get("batch_id") or "").strip() or None,
        amount_with_vat=_parse_decimal(document.get("amount_with_vat")),
        amount_without_vat=_parse_decimal(document.get("amount_without_vat")),
        vat_amount=_parse_decimal(document.get("vat_amount")),
        comment=str(document.get("comment") or "").strip(),
        kind=str(document.get("kind") or "").strip().lower() or None,
        modified_at=_parse_datetime(document.get("modified_at")),
        unattributed=str(document.get("unattributed") or "").strip() == "1",
    )


def _resolve_late_correction_baseline(*, checkpoint: PoolFactualSyncCheckpoint) -> dict[str, dict[str, str]]:
    metadata = checkpoint.metadata if isinstance(checkpoint.metadata, dict) else {}
    baseline = metadata.get("frozen_source_documents") or metadata.get("latest_source_documents") or {}
    if not isinstance(baseline, dict):
        return {}
    return {str(key): dict(value) for key, value in baseline.items() if isinstance(value, Mapping)}


def _build_late_correction_signature(
    *,
    baseline_payload: Mapping[str, Any] | None,
    current_payload: Mapping[str, Any] | None,
) -> str:
    payload = {
        "baseline": dict(baseline_payload or {}),
        "current": dict(current_payload or {}),
    }
    return sha256(repr(payload).encode("utf-8")).hexdigest()


def _resolve_late_correction_change_type(
    *,
    baseline_payload: Mapping[str, Any] | None,
    current_payload: Mapping[str, Any] | None,
) -> str:
    if baseline_payload is None:
        return "added"
    if current_payload is None:
        return "removed"
    return "changed"


def _apply_leaf_sale_remainder_to_org_snapshot(
    *,
    checkpoint: PoolFactualSyncCheckpoint,
    row: _FactualDocumentRecord,
    remainder_with_vat: Decimal,
    applied_at: datetime,
) -> None:
    if not row.organization_id or remainder_with_vat <= Decimal("0.00"):
        return
    total_amount_with_vat = row.amount_with_vat.copy_abs()
    if total_amount_with_vat <= Decimal("0.00"):
        return
    proportion = remainder_with_vat / total_amount_with_vat
    remainder_without_vat = _money(row.amount_without_vat.copy_abs() * proportion)
    remainder_vat = _money(row.vat_amount.copy_abs() * proportion)
    organization = Organization.objects.filter(id=row.organization_id).first()
    batch = PoolBatch.objects.filter(id=row.batch_id).first() if row.batch_id else None
    if organization is None:
        return
    snapshot, _created = PoolFactualBalanceSnapshot.objects.get_or_create(
        tenant=checkpoint.tenant,
        pool=checkpoint.pool,
        batch=batch,
        organization=organization,
        edge=None,
        quarter_start=checkpoint.quarter_start,
        quarter_end=checkpoint.quarter_end,
        defaults={
            "amount_with_vat": Decimal("0.00"),
            "amount_without_vat": Decimal("0.00"),
            "vat_amount": Decimal("0.00"),
            "incoming_amount": Decimal("0.00"),
            "outgoing_amount": Decimal("0.00"),
            "open_balance": Decimal("0.00"),
            "freshness_at": applied_at,
            "metadata": {
                "database_id": str(checkpoint.database_id),
                "lane": checkpoint.lane,
                "source_contract": FACTUAL_SYNC_RESULT_STEP,
            },
        },
    )
    _apply_snapshot_document_delta(
        snapshot=snapshot,
        amount_with_vat=remainder_with_vat,
        amount_without_vat=remainder_without_vat,
        vat_amount=remainder_vat,
        kind=row.kind or "sale",
        reverse=False,
        applied_at=applied_at,
    )


def _move_unattributed_review_item_to_resolved_target(
    *,
    review_item: PoolFactualReviewItem,
    original_batch_id: str | None,
    original_edge_id: str | None,
    original_organization_id: str | None,
    applied_at: datetime,
) -> bool:
    delta_payload = review_item.delta_payload if isinstance(review_item.delta_payload, dict) else {}
    amount_with_vat = _parse_decimal(delta_payload.get("amount_with_vat"))
    amount_without_vat = _parse_decimal(delta_payload.get("amount_without_vat"))
    vat_amount = _parse_decimal(delta_payload.get("vat_amount"))
    if amount_with_vat == Decimal("0.00") and amount_without_vat == Decimal("0.00") and vat_amount == Decimal("0.00"):
        return False
    if review_item.organization is None:
        return False

    kind = str(
        delta_payload.get("kind")
        or (review_item.metadata or {}).get("kind")
        or "manual"
    ).strip().lower() or "manual"
    source_snapshot = _find_projection_snapshot(
        tenant=review_item.tenant,
        pool=review_item.pool,
        quarter_start=review_item.quarter_start,
        quarter_end=review_item.quarter_end,
        batch_id=original_batch_id,
        edge_id=original_edge_id,
        organization_id=original_organization_id,
    )
    target_snapshot = _get_or_create_projection_snapshot(
        review_item=review_item,
        applied_at=applied_at,
    )
    if source_snapshot is not None and source_snapshot.id != target_snapshot.id:
        _apply_snapshot_document_delta(
            snapshot=source_snapshot,
            amount_with_vat=amount_with_vat,
            amount_without_vat=amount_without_vat,
            vat_amount=vat_amount,
            kind=kind,
            reverse=True,
            applied_at=applied_at,
        )
        _delete_zero_projection_snapshot(snapshot=source_snapshot)
    if source_snapshot is None or source_snapshot.id != target_snapshot.id:
        _apply_snapshot_document_delta(
            snapshot=target_snapshot,
            amount_with_vat=amount_with_vat,
            amount_without_vat=amount_without_vat,
            vat_amount=vat_amount,
            kind=kind,
            reverse=False,
            applied_at=applied_at,
        )
    return True


def _find_projection_snapshot(
    *,
    tenant,
    pool,
    quarter_start: date,
    quarter_end: date,
    batch_id: str | None,
    edge_id: str | None,
    organization_id: str | None,
) -> PoolFactualBalanceSnapshot | None:
    if not organization_id:
        return None
    queryset = PoolFactualBalanceSnapshot.objects.filter(
        tenant=tenant,
        pool=pool,
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        organization_id=organization_id,
    )
    queryset = queryset.filter(batch_id=batch_id) if batch_id else queryset.filter(batch__isnull=True)
    queryset = queryset.filter(edge_id=edge_id) if edge_id else queryset.filter(edge__isnull=True)
    return queryset.first()


def _get_or_create_projection_snapshot(
    *,
    review_item: PoolFactualReviewItem,
    applied_at: datetime,
) -> PoolFactualBalanceSnapshot:
    metadata = review_item.metadata if isinstance(review_item.metadata, dict) else {}
    snapshot, _created = PoolFactualBalanceSnapshot.objects.get_or_create(
        tenant=review_item.tenant,
        pool=review_item.pool,
        batch=review_item.batch,
        organization=review_item.organization,
        edge=review_item.edge,
        quarter_start=review_item.quarter_start,
        quarter_end=review_item.quarter_end,
        defaults={
            "amount_with_vat": Decimal("0.00"),
            "amount_without_vat": Decimal("0.00"),
            "vat_amount": Decimal("0.00"),
            "incoming_amount": Decimal("0.00"),
            "outgoing_amount": Decimal("0.00"),
            "open_balance": Decimal("0.00"),
            "freshness_at": applied_at,
            "metadata": {
                "database_id": str(metadata.get("database_id") or ""),
                "lane": metadata.get("lane", ""),
                "source_contract": "review_resolution",
            },
        },
    )
    return snapshot


def _apply_snapshot_document_delta(
    *,
    snapshot: PoolFactualBalanceSnapshot,
    amount_with_vat: Decimal,
    amount_without_vat: Decimal,
    vat_amount: Decimal,
    kind: str,
    reverse: bool,
    applied_at: datetime,
) -> None:
    sale_like = kind in {"sale", "manual"}
    if sale_like:
        amount_sign = Decimal("1.00") if reverse else Decimal("-1.00")
        outgoing_sign = Decimal("-1.00") if reverse else Decimal("1.00")
        open_balance_sign = Decimal("1.00") if reverse else Decimal("-1.00")
        incoming_sign = Decimal("0.00")
    else:
        amount_sign = Decimal("-1.00") if reverse else Decimal("1.00")
        outgoing_sign = Decimal("0.00")
        open_balance_sign = Decimal("-1.00") if reverse else Decimal("1.00")
        incoming_sign = Decimal("-1.00") if reverse else Decimal("1.00")

    snapshot.amount_with_vat = _money(Decimal(str(snapshot.amount_with_vat or "0")) + (amount_with_vat * amount_sign))
    snapshot.amount_without_vat = _money(
        Decimal(str(snapshot.amount_without_vat or "0")) + (amount_without_vat * amount_sign)
    )
    snapshot.vat_amount = _money(Decimal(str(snapshot.vat_amount or "0")) + (vat_amount * amount_sign))
    snapshot.incoming_amount = _money(
        Decimal(str(snapshot.incoming_amount or "0")) + (amount_with_vat * incoming_sign)
    )
    snapshot.outgoing_amount = _money(
        Decimal(str(snapshot.outgoing_amount or "0")) + (amount_with_vat * outgoing_sign)
    )
    snapshot.open_balance = _money(
        Decimal(str(snapshot.open_balance or "0")) + (amount_with_vat * open_balance_sign)
    )
    snapshot.freshness_at = applied_at
    snapshot.save(
        update_fields=[
            "amount_with_vat",
            "amount_without_vat",
            "vat_amount",
            "incoming_amount",
            "outgoing_amount",
            "open_balance",
            "freshness_at",
            "updated_at",
        ]
    )


def _delete_zero_projection_snapshot(*, snapshot: PoolFactualBalanceSnapshot) -> None:
    if any(
        value != Decimal("0.00")
        for value in (
            snapshot.amount_with_vat,
            snapshot.amount_without_vat,
            snapshot.vat_amount,
            snapshot.incoming_amount,
            snapshot.outgoing_amount,
            snapshot.open_balance,
        )
    ):
        return
    snapshot.delete()


def _build_review_item_signature(*, row: _FactualDocumentRecord) -> str:
    payload = "|".join(
        [
            row.source_document_ref,
            row.organization_id or "",
            row.batch_id or "",
            row.edge_id or "",
            f"{row.amount_with_vat:.2f}",
            f"{row.amount_without_vat:.2f}",
            f"{row.vat_amount:.2f}",
            row.comment,
            row.kind or "",
            row.modified_at.isoformat() if row.modified_at else "",
        ]
    )
    return sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "FACTUAL_SYNC_RESULT_STEP",
    "apply_pool_factual_review_resolution_to_projection",
    "is_pool_factual_sync_execution",
    "mark_pool_factual_execution_failed",
    "project_pool_factual_result_from_execution",
    "refresh_pool_factual_batch_settlement_snapshots",
    "sync_pool_factual_checkpoint_state_from_execution",
]
