from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from django.db import transaction

from apps.operations.services import OperationsService

from .master_data_bootstrap_collection_service import (
    _COLLECTION_OPERATION_ID,
    _COLLECTION_STAGE_RUNNER,
    _COLLECTION_WORKFLOW_EXECUTION_ID,
)
from .master_data_bootstrap_collection_workflow_contract import (
    build_pool_master_data_bootstrap_collection_workflow_input_context,
)
from .master_data_bootstrap_collection_workflow_template import (
    ensure_pool_master_data_bootstrap_collection_workflow_template,
)
from .master_data_sync_redaction import sanitize_master_data_sync_text, sanitize_master_data_sync_value
from .models import (
    PoolMasterDataBootstrapCollectionMode,
    PoolMasterDataBootstrapCollectionRequest,
    PoolMasterDataBootstrapCollectionStatus,
)
from .runtime_template_registry import sync_pool_runtime_template_registry


@dataclass
class PoolMasterDataBootstrapCollectionWorkflowStartResult:
    collection: PoolMasterDataBootstrapCollectionRequest
    stage: str
    runner_token: str
    execution_id: str | None
    operation_id: str | None
    enqueue_success: bool
    enqueue_status: str
    enqueue_error: str | None
    created_execution: bool


def start_pool_master_data_bootstrap_collection_stage_workflow(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    stage: str,
    correlation_id: str,
    origin_system: str,
    origin_event_id: str,
    actor_username: str = "",
) -> PoolMasterDataBootstrapCollectionWorkflowStartResult:
    normalized_stage = _normalize_stage(stage)
    runner_token = f"{normalized_stage}:{uuid4()}"
    execution_id: str | None = None
    created_execution = False

    with transaction.atomic():
        locked = PoolMasterDataBootstrapCollectionRequest.objects.select_for_update().get(id=collection.id)
        metadata = dict(locked.metadata if isinstance(locked.metadata, dict) else {})
        metadata[_COLLECTION_STAGE_RUNNER] = {
            "stage": normalized_stage,
            "token": runner_token,
        }
        sync_pool_runtime_template_registry()
        workflow_template = ensure_pool_master_data_bootstrap_collection_workflow_template()
        input_context = build_pool_master_data_bootstrap_collection_workflow_input_context(
            collection_id=str(locked.id),
            tenant_id=str(locked.tenant_id),
            stage=normalized_stage,
            runner_token=runner_token,
            correlation_id=correlation_id,
            origin_system=origin_system,
            origin_event_id=origin_event_id,
            actor_username=actor_username,
        )
        execution = workflow_template.create_execution(
            input_context,
            tenant=locked.tenant,
            execution_consumer="pools",
        )
        metadata[_COLLECTION_WORKFLOW_EXECUTION_ID] = str(execution.id)
        locked.metadata = sanitize_master_data_sync_value(metadata)
        locked.status = _running_status_for_stage(normalized_stage)
        locked.last_error_code = ""
        locked.last_error = ""
        locked.save(update_fields=["metadata", "status", "last_error_code", "last_error", "updated_at"])
        execution_id = str(execution.id)
        created_execution = True

    if transaction.get_connection().in_atomic_block:
        deferred = PoolMasterDataBootstrapCollectionWorkflowStartResult(
            collection=PoolMasterDataBootstrapCollectionRequest.objects.get(id=collection.id),
            stage=normalized_stage,
            runner_token=runner_token,
            execution_id=execution_id,
            operation_id=None,
            enqueue_success=True,
            enqueue_status="deferred",
            enqueue_error=None,
            created_execution=created_execution,
        )

        def _enqueue_after_commit() -> None:
            final = _enqueue_pool_master_data_bootstrap_collection_workflow(
                collection_id=str(collection.id),
                stage=normalized_stage,
                runner_token=runner_token,
                execution_id=execution_id,
                created_execution=created_execution,
                correlation_id=correlation_id,
                actor_username=actor_username,
            )
            _copy_start_result(target=deferred, source=final)

        transaction.on_commit(_enqueue_after_commit)
        return deferred

    return _enqueue_pool_master_data_bootstrap_collection_workflow(
        collection_id=str(collection.id),
        stage=normalized_stage,
        runner_token=runner_token,
        execution_id=execution_id,
        created_execution=created_execution,
        correlation_id=correlation_id,
        actor_username=actor_username,
    )


def start_pool_master_data_bootstrap_collection_execute_workflow(
    *,
    collection: PoolMasterDataBootstrapCollectionRequest,
    correlation_id: str,
    origin_system: str,
    origin_event_id: str,
    actor_username: str = "",
) -> PoolMasterDataBootstrapCollectionWorkflowStartResult:
    return start_pool_master_data_bootstrap_collection_stage_workflow(
        collection=collection,
        stage=PoolMasterDataBootstrapCollectionMode.EXECUTE,
        correlation_id=correlation_id,
        origin_system=origin_system,
        origin_event_id=origin_event_id,
        actor_username=actor_username,
    )


def _enqueue_pool_master_data_bootstrap_collection_workflow(
    *,
    collection_id: str,
    stage: str,
    runner_token: str,
    execution_id: str | None,
    created_execution: bool,
    correlation_id: str,
    actor_username: str,
) -> PoolMasterDataBootstrapCollectionWorkflowStartResult:
    refreshed = PoolMasterDataBootstrapCollectionRequest.objects.get(id=collection_id)
    metadata = dict(refreshed.metadata if isinstance(refreshed.metadata, dict) else {})
    linked_execution_id = str(metadata.get(_COLLECTION_WORKFLOW_EXECUTION_ID) or execution_id or "").strip()
    if not linked_execution_id:
        raise ValueError("Bootstrap collection request is not linked to workflow execution.")

    enqueue_result = OperationsService.enqueue_workflow_execution(
        execution_id=linked_execution_id,
        workflow_config={
            "collection_id": str(refreshed.id),
            "stage": str(stage),
            "runner_token": str(runner_token),
            "execution_consumer": "pools",
            "idempotency_key": f"pool.master_data.bootstrap.collection:{refreshed.id}:{stage}:{runner_token}",
            "trace_id": str(correlation_id or "").strip(),
            "requested_by": str(actor_username or "").strip(),
        },
    )
    if enqueue_result.success:
        normalized_operation_id = _normalize_operation_id(enqueue_result.operation_id or linked_execution_id)
        metadata[_COLLECTION_OPERATION_ID] = normalized_operation_id or ""
        refreshed.metadata = sanitize_master_data_sync_value(metadata)
        refreshed.status = _running_status_for_stage(stage)
        refreshed.last_error_code = ""
        refreshed.last_error = ""
        refreshed.save(update_fields=["metadata", "status", "last_error_code", "last_error", "updated_at"])
        return PoolMasterDataBootstrapCollectionWorkflowStartResult(
            collection=refreshed,
            stage=stage,
            runner_token=runner_token,
            execution_id=linked_execution_id,
            operation_id=normalized_operation_id,
            enqueue_success=True,
            enqueue_status=enqueue_result.status,
            enqueue_error=None,
            created_execution=created_execution,
        )

    refreshed.status = PoolMasterDataBootstrapCollectionStatus.FAILED
    refreshed.last_error_code = str(enqueue_result.error_code or "ENQUEUE_FAILED").strip() or "ENQUEUE_FAILED"
    refreshed.last_error = sanitize_master_data_sync_text(
        str(enqueue_result.error or "Failed to enqueue workflow execution")
    )
    refreshed.save(update_fields=["status", "last_error_code", "last_error", "updated_at"])
    return PoolMasterDataBootstrapCollectionWorkflowStartResult(
        collection=refreshed,
        stage=stage,
        runner_token=runner_token,
        execution_id=linked_execution_id,
        operation_id=None,
        enqueue_success=False,
        enqueue_status=enqueue_result.status,
        enqueue_error=refreshed.last_error or None,
        created_execution=created_execution,
    )


def _copy_start_result(
    *,
    target: PoolMasterDataBootstrapCollectionWorkflowStartResult,
    source: PoolMasterDataBootstrapCollectionWorkflowStartResult,
) -> None:
    target.collection = source.collection
    target.stage = source.stage
    target.runner_token = source.runner_token
    target.execution_id = source.execution_id
    target.operation_id = source.operation_id
    target.enqueue_success = source.enqueue_success
    target.enqueue_status = source.enqueue_status
    target.enqueue_error = source.enqueue_error
    target.created_execution = source.created_execution


def _normalize_operation_id(raw_value: str | None) -> str | None:
    token = str(raw_value or "").strip()
    if not token:
        return None
    try:
        return str(UUID(token))
    except ValueError:
        return None


def _normalize_stage(stage: str) -> str:
    normalized = str(stage or "").strip().lower()
    if normalized not in {
        PoolMasterDataBootstrapCollectionMode.DRY_RUN,
        PoolMasterDataBootstrapCollectionMode.EXECUTE,
    }:
        raise ValueError(f"Unsupported bootstrap collection stage '{stage}'")
    return normalized


def _running_status_for_stage(stage: str) -> str:
    if stage == PoolMasterDataBootstrapCollectionMode.DRY_RUN:
        return PoolMasterDataBootstrapCollectionStatus.DRY_RUN_RUNNING
    return PoolMasterDataBootstrapCollectionStatus.EXECUTE_RUNNING
