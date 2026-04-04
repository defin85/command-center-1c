from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import patch

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.factual_scope_selection import FACTUAL_SCOPE_CONTRACT_VERSION
from apps.intercompany_pools.factual_sync_runtime import build_factual_sales_report_sync_scope
from apps.intercompany_pools.factual_workflow_runtime import start_pool_factual_sync_workflow
from apps.intercompany_pools.models import OrganizationPool, PoolFactualLane, PoolFactualSyncCheckpoint
from apps.intercompany_pools.factual_source_profile import (
    REQUIRED_FACTUAL_ACCOUNTING_REGISTER,
    REQUIRED_FACTUAL_DOCUMENTS,
    REQUIRED_FACTUAL_INFORMATION_REGISTER,
)
from apps.templates.workflow.models import WorkflowExecution
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-workflow-runtime-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-workflow-runtime-{suffix}.odata",
        username="admin",
        password="secret",
        server_address="srv-factual",
        server_port=1540,
    )


@pytest.mark.django_db
def test_start_pool_factual_sync_workflow_enqueues_read_lane_on_default_path() -> None:
    tenant = Tenant.objects.create(
        slug=f"factual-workflow-runtime-{uuid4().hex[:6]}",
        name="Factual Workflow Runtime",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-runtime-pool-{uuid4().hex[:6]}",
        name="Factual Runtime Pool",
    )
    database = _create_database(tenant=tenant, suffix="read")
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
    )

    with (
        patch("apps.intercompany_pools.factual_workflow_runtime.sync_pool_runtime_template_registry"),
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123999-0"

        result = start_pool_factual_sync_workflow(
            checkpoint=checkpoint,
            database=database,
            organization_ids=("org-a", "org-b"),
            account_codes=("62.01", "90.01"),
            movement_kinds=("credit", "debit"),
            correlation_id="corr-factual-read-001",
            origin_system="tests",
            origin_event_id="evt-factual-read-001",
            activity="active",
            freeze_quarter=False,
        )

    assert result.created_execution is True
    assert result.enqueue_success is True
    assert result.execution_id
    assert result.operation_id
    checkpoint.refresh_from_db()
    assert checkpoint.workflow_status == "running"
    assert checkpoint.last_error_code == ""
    assert checkpoint.last_error == ""
    assert checkpoint.workflow_execution_id == UUID(str(result.execution_id))
    assert checkpoint.operation_id == UUID(str(result.operation_id))
    execution = WorkflowExecution.objects.get(id=result.execution_id)
    assert execution.input_context["document_entities"] == ",".join(sorted(REQUIRED_FACTUAL_DOCUMENTS))
    assert execution.input_context["accounting_register_entity"] == REQUIRED_FACTUAL_ACCOUNTING_REGISTER
    assert execution.input_context["accounting_register_function"] == "Turnovers"
    assert execution.input_context["information_register_entity"] == REQUIRED_FACTUAL_INFORMATION_REGISTER
    assert execution.input_context["read_boundary_kind"] == "odata"
    assert execution.input_context["direct_db_access"] == "0"
    assert execution.input_context["read_boundary_service_name"] == ""

    message = mock_redis_client.enqueue_operation_stream.call_args.args[0]
    assert message["payload"]["data"]["role"] == "read"
    assert message["metadata"]["role"] == "read"
    mock_event_publisher.publish.assert_called_once()


@pytest.mark.django_db
def test_start_pool_factual_sync_workflow_preserves_source_scope_for_reconcile_lane() -> None:
    tenant = Tenant.objects.create(
        slug=f"factual-workflow-runtime-reconcile-{uuid4().hex[:6]}",
        name="Factual Workflow Runtime Reconcile",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-runtime-reconcile-pool-{uuid4().hex[:6]}",
        name="Factual Runtime Reconcile Pool",
    )
    database = _create_database(tenant=tenant, suffix="reconcile")
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.RECONCILE,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
    )

    with (
        patch("apps.intercompany_pools.factual_workflow_runtime.sync_pool_runtime_template_registry"),
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123999-1"

        result = start_pool_factual_sync_workflow(
            checkpoint=checkpoint,
            database=database,
            organization_ids=("org-a", "org-b"),
            account_codes=("62.01", "90.01"),
            movement_kinds=("credit", "debit"),
            correlation_id="corr-factual-reconcile-001",
            origin_system="tests",
            origin_event_id="evt-factual-reconcile-001",
            activity="cold",
            freeze_quarter=True,
        )

    assert result.created_execution is True
    assert result.enqueue_success is True
    execution = WorkflowExecution.objects.get(id=result.execution_id)
    assert execution.input_context["lane"] == PoolFactualLane.RECONCILE
    assert execution.input_context["document_entities"] == ",".join(sorted(REQUIRED_FACTUAL_DOCUMENTS))
    assert execution.input_context["accounting_register_entity"] == REQUIRED_FACTUAL_ACCOUNTING_REGISTER
    assert execution.input_context["accounting_register_function"] == "Turnovers"
    assert execution.input_context["information_register_entity"] == REQUIRED_FACTUAL_INFORMATION_REGISTER
    assert execution.input_context["read_boundary_kind"] == "odata"
    assert execution.input_context["direct_db_access"] == "0"
    assert execution.input_context["quarter_scope"] == "closed"
    assert execution.input_context["schedule_window"] == "nightly"
    assert execution.input_context["freeze_quarter"] is True

    message = mock_redis_client.enqueue_operation_stream.call_args.args[0]
    assert message["payload"]["data"]["role"] == "reconcile"
    assert message["metadata"]["role"] == "reconcile"
    mock_event_publisher.publish.assert_called_once()


@pytest.mark.django_db
def test_start_pool_factual_sync_workflow_uses_scope_fingerprint_in_enqueue_idempotency_key() -> None:
    tenant = Tenant.objects.create(
        slug=f"factual-workflow-runtime-lineage-{uuid4().hex[:6]}",
        name="Factual Workflow Runtime Lineage",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-runtime-lineage-pool-{uuid4().hex[:6]}",
        name="Factual Runtime Lineage Pool",
    )
    database = _create_database(tenant=tenant, suffix="lineage")
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
    )
    scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-a",),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
        selector_key=f"pool:{pool.id}:sales_report_v1:2026-01-01",
        gl_account_set_id=str(uuid4()),
        gl_account_set_revision_id="gl_account_set_rev_v1",
        effective_members=(
            {
                "canonical_id": "factual_sales_report_62_01",
                "code": "62.01",
                "name": "62.01",
                "chart_identity": "ChartOfAccounts_Хозрасчетный",
                "sort_order": 0,
            },
            {
                "canonical_id": "factual_sales_report_90_01",
                "code": "90.01",
                "name": "90.01",
                "chart_identity": "ChartOfAccounts_Хозрасчетный",
                "sort_order": 1,
            },
        ),
        resolved_bindings=(
            {
                "canonical_id": "factual_sales_report_62_01",
                "code": "62.01",
                "name": "62.01",
                "chart_identity": "ChartOfAccounts_Хозрасчетный",
                "target_ref_key": "account-62",
            },
            {
                "canonical_id": "factual_sales_report_90_01",
                "code": "90.01",
                "name": "90.01",
                "chart_identity": "ChartOfAccounts_Хозрасчетный",
                "target_ref_key": "account-90",
            },
        ),
        contract_version=FACTUAL_SCOPE_CONTRACT_VERSION,
    )

    with (
        patch("apps.intercompany_pools.factual_workflow_runtime.sync_pool_runtime_template_registry"),
        patch("apps.operations.services.operations_service.workflow.redis_client"),
        patch("apps.operations.services.operations_service.workflow.event_publisher"),
        patch(
            "apps.intercompany_pools.factual_workflow_runtime.OperationsService.enqueue_workflow_execution",
            return_value=SimpleNamespace(success=True, status="running", operation_id=str(uuid4())),
        ) as enqueue_workflow,
    ):
        result = start_pool_factual_sync_workflow(
            checkpoint=checkpoint,
            database=database,
            organization_ids=("org-a",),
            account_codes=("62.01", "90.01"),
            movement_kinds=("credit", "debit"),
            correlation_id="corr-factual-lineage-001",
            origin_system="tests",
            origin_event_id="evt-factual-lineage-001",
            activity="active",
            freeze_quarter=False,
            scope=scope,
        )

    assert result.enqueue_success is True
    workflow_config = enqueue_workflow.call_args.kwargs["workflow_config"]
    assert workflow_config["idempotency_key"].startswith(f"pool.factual.sync:{scope.scope_fingerprint}:")
