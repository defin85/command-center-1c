from __future__ import annotations

from uuid import UUID, uuid4
from unittest.mock import patch

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_workflow_runtime import (
    start_pool_master_data_sync_job_workflow,
)
from apps.intercompany_pools.master_data_sync_workflow_template import (
    ensure_pool_master_data_sync_workflow_template,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncPolicy,
)
from apps.operations.services import EnqueueResult
from apps.templates.workflow.models import WorkflowExecution
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-wf-runtime-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_sync_job(*, suffix: str = "job") -> PoolMasterDataSyncJob:
    tenant = Tenant.objects.create(slug=f"sync-wf-runtime-{suffix}-{uuid4().hex[:6]}", name="Sync WF Runtime")
    database = _create_database(tenant=tenant, suffix=suffix)
    return PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.BIDIRECTIONAL,
        status=PoolMasterDataSyncJobStatus.PENDING,
    )


@pytest.mark.django_db
def test_start_sync_job_workflow_creates_execution_and_links_operation_ids() -> None:
    job = _create_sync_job(suffix="success")

    def _enqueue(execution_id: str, workflow_config: dict | None = None) -> EnqueueResult:
        return EnqueueResult(
            success=True,
            operation_id=execution_id,
            status="queued",
            error=None,
            error_code=None,
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_workflow_runtime.OperationsService.enqueue_workflow_execution",
        side_effect=_enqueue,
    ) as enqueue_mock:
        result = start_pool_master_data_sync_job_workflow(
            sync_job=job,
            correlation_id="corr-runtime-001",
            origin_system="cc",
            origin_event_id="evt-runtime-001",
        )

    assert result.created_execution is True
    assert result.enqueue_success is True
    assert result.execution_id
    assert result.operation_id == result.execution_id
    enqueue_mock.assert_called_once()

    refreshed = PoolMasterDataSyncJob.objects.get(id=job.id)
    assert str(refreshed.workflow_execution_id) == result.execution_id
    assert str(refreshed.operation_id) == result.operation_id
    assert refreshed.status == PoolMasterDataSyncJobStatus.RUNNING

    execution = WorkflowExecution.objects.get(id=result.execution_id)
    assert execution.execution_consumer == "pools"
    assert execution.input_context["sync_job_id"] == str(job.id)
    assert execution.input_context["correlation_id"] == "corr-runtime-001"


@pytest.mark.django_db
def test_start_sync_job_workflow_fails_closed_on_enqueue_error() -> None:
    job = _create_sync_job(suffix="error")

    with patch(
        "apps.intercompany_pools.master_data_sync_workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=False,
            operation_id="",
            status="error",
            error="redis unavailable",
            error_code="REDIS_ERROR",
        ),
    ):
        result = start_pool_master_data_sync_job_workflow(
            sync_job=job,
            correlation_id="corr-runtime-err",
            origin_system="cc",
            origin_event_id="evt-runtime-err",
        )

    assert result.enqueue_success is False
    refreshed = PoolMasterDataSyncJob.objects.get(id=job.id)
    assert refreshed.status == PoolMasterDataSyncJobStatus.FAILED
    assert refreshed.last_error_code == "REDIS_ERROR"
    assert "redis unavailable" in refreshed.last_error


@pytest.mark.django_db
def test_start_sync_job_workflow_is_idempotent_when_execution_already_linked() -> None:
    job = _create_sync_job(suffix="idempotent")
    template = ensure_pool_master_data_sync_workflow_template()
    execution = template.create_execution(
        {
            "sync_job_id": str(job.id),
            "tenant_id": str(job.tenant_id),
            "database_id": str(job.database_id),
        },
        tenant=job.tenant,
        execution_consumer="pools",
    )
    job.workflow_execution_id = execution.id
    job.operation_id = UUID(str(execution.id))
    job.save(update_fields=["workflow_execution_id", "operation_id", "updated_at"])

    with patch(
        "apps.intercompany_pools.master_data_sync_workflow_runtime.OperationsService.enqueue_workflow_execution",
    ) as enqueue_mock:
        result = start_pool_master_data_sync_job_workflow(
            sync_job=job,
            correlation_id="corr-runtime-reuse",
            origin_system="cc",
            origin_event_id="evt-runtime-reuse",
        )

    assert result.created_execution is False
    assert result.execution_id == str(execution.id)
    assert result.operation_id == str(execution.id)
    enqueue_mock.assert_not_called()
