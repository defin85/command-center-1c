from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.operations.services import OperationsService

from .ccpool_traceability import build_ccpool_quarter_token, inject_ccpool_traceability_comment
from .models import PoolBatch
from .runtime_template_registry import sync_pool_runtime_template_registry
from .sale_batch_intake import SaleBatchClosingContract
from .sale_batch_workflow_template import ensure_pool_sale_batch_workflow_template


User = get_user_model()

SALE_BATCH_PUBLICATION_AUTH_SOURCE = "sale_batch_intake"
SALE_BATCH_PUBLICATION_DEFAULT_ENTITY = "Document_РеализацияТоваровУслуг"


@dataclass(frozen=True)
class PoolSaleBatchWorkflowStartResult:
    batch: PoolBatch
    execution_id: str | None
    operation_id: str | None
    enqueue_success: bool
    enqueue_status: str
    enqueue_error: str | None
    created_execution: bool


def start_pool_sale_batch_closing_workflow_execution(
    *,
    batch: PoolBatch,
    closing_contract: SaleBatchClosingContract,
    requested_by: User | None = None,
) -> PoolSaleBatchWorkflowStartResult:
    target_database_ids = sorted(
        {
            str(intent.database_id)
            for intent in closing_contract.closing_intents
        }
    )
    execution_id: str | None = None
    created_execution = False

    with transaction.atomic():
        locked_batch = PoolBatch.objects.select_for_update().get(id=batch.id)
        if locked_batch.workflow_execution_id and locked_batch.operation_id:
            existing_execution_id = str(locked_batch.workflow_execution_id)
            existing_operation_id = (
                str(locked_batch.operation_id)
                if locked_batch.operation_id is not None
                else None
            )
            return PoolSaleBatchWorkflowStartResult(
                batch=locked_batch,
                execution_id=existing_execution_id,
                operation_id=existing_operation_id,
                enqueue_success=True,
                enqueue_status=str(locked_batch.workflow_status or "").strip() or "pending",
                enqueue_error=None,
                created_execution=False,
            )

        if locked_batch.workflow_execution_id:
            execution_id = str(locked_batch.workflow_execution_id)
            created_execution = False
        else:
            sync_pool_runtime_template_registry()
            workflow_template = ensure_pool_sale_batch_workflow_template(created_by=requested_by)
            execution = workflow_template.create_execution(
                {
                    "tenant_id": str(locked_batch.tenant_id),
                    "pool_id": str(locked_batch.pool_id),
                    "pool_batch_id": str(locked_batch.id),
                    "batch_kind": locked_batch.batch_kind,
                    "period_start": locked_batch.period_start.isoformat(),
                    "period_end": locked_batch.period_end.isoformat() if locked_batch.period_end else None,
                    "target_database_ids": target_database_ids,
                    "approval_state": "not_required",
                    "publication_step_state": "queued",
                    "publication_auth": _build_publication_auth_context(requested_by=requested_by),
                    "pool_runtime_publication_payload": _build_sale_batch_publication_payload(
                        batch=locked_batch,
                        closing_contract=closing_contract,
                    ),
                },
                tenant=locked_batch.tenant,
                execution_consumer="pools",
            )
            locked_batch.workflow_execution_id = execution.id
            locked_batch.workflow_status = execution.status
            locked_batch.last_error_code = ""
            locked_batch.last_error = ""
            locked_batch.save(
                update_fields=[
                    "workflow_execution_id",
                    "workflow_status",
                    "last_error_code",
                    "last_error",
                    "updated_at",
                ]
            )
            execution_id = str(execution.id)
            created_execution = True

    enqueue_result = OperationsService.enqueue_workflow_execution(
        execution_id=execution_id or "",
        workflow_config={
            "pool_batch_id": str(batch.id),
            "execution_consumer": "pools",
            "idempotency_key": f"pool.sale_batch.closing:{batch.id}",
            "target_database_ids": target_database_ids,
        },
    )
    refreshed = PoolBatch.objects.get(id=batch.id)
    if enqueue_result.success:
        normalized_operation_id = _normalize_operation_id(enqueue_result.operation_id or (execution_id or ""))
        refreshed.operation_id = UUID(normalized_operation_id) if normalized_operation_id is not None else None
        refreshed.workflow_status = str(refreshed.workflow_status or "").strip() or "pending"
        refreshed.last_error_code = ""
        refreshed.last_error = ""
        refreshed.save(
            update_fields=[
                "operation_id",
                "workflow_status",
                "last_error_code",
                "last_error",
                "updated_at",
            ]
        )
        return PoolSaleBatchWorkflowStartResult(
            batch=refreshed,
            execution_id=execution_id,
            operation_id=normalized_operation_id,
            enqueue_success=True,
            enqueue_status=enqueue_result.status,
            enqueue_error=None,
            created_execution=created_execution,
        )

    refreshed.last_error_code = str(enqueue_result.error_code or "ENQUEUE_FAILED").strip() or "ENQUEUE_FAILED"
    refreshed.last_error = str(enqueue_result.error or "Failed to enqueue workflow execution").strip()
    refreshed.save(
        update_fields=[
            "last_error_code",
            "last_error",
            "updated_at",
        ]
    )
    return PoolSaleBatchWorkflowStartResult(
        batch=refreshed,
        execution_id=execution_id,
        operation_id=None,
        enqueue_success=False,
        enqueue_status=enqueue_result.status,
        enqueue_error=refreshed.last_error or None,
        created_execution=created_execution,
    )


def _normalize_operation_id(raw_value: str | None) -> str | None:
    token = str(raw_value or "").strip()
    if not token:
        return None
    try:
        return str(UUID(token))
    except ValueError:
        return None


def _build_publication_auth_context(*, requested_by: User | None) -> dict[str, str]:
    actor_username = str(getattr(requested_by, "username", "") or "").strip()
    if actor_username:
        return {
            "strategy": "actor",
            "actor_username": actor_username,
            "source": SALE_BATCH_PUBLICATION_AUTH_SOURCE,
        }
    return {
        "strategy": "service",
        "actor_username": "",
        "source": SALE_BATCH_PUBLICATION_AUTH_SOURCE,
    }


def _build_sale_batch_publication_payload(
    *,
    batch: PoolBatch,
    closing_contract: SaleBatchClosingContract,
) -> dict[str, Any]:
    documents_by_database: dict[str, list[dict[str, Any]]] = {}
    for intent in closing_contract.closing_intents:
        database_id = str(intent.database_id)
        document_payload = inject_ccpool_traceability_comment(
            payload={
                "Amount": _decimal_to_string(intent.amount_with_vat),
            },
            traceability={
                "pool_id": str(batch.pool_id),
                "run_id": "-",
                "batch_id": str(batch.id),
                "organization_id": str(intent.organization_id),
                "quarter": build_ccpool_quarter_token(period_start=batch.period_start),
                "kind": "sale",
            },
        )
        documents_by_database.setdefault(database_id, []).append(document_payload)
    return {
        "pool_runtime": {
            "entity_name": SALE_BATCH_PUBLICATION_DEFAULT_ENTITY,
            "documents_by_database": documents_by_database,
            "max_attempts": 1,
            "retry_interval_seconds": 0,
            "external_key_field": "ExternalRunKey",
        }
    }


def _decimal_to_string(value: Decimal) -> str:
    return format(value, "f")


__all__ = [
    "PoolSaleBatchWorkflowStartResult",
    "start_pool_sale_batch_closing_workflow_execution",
]
