from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.factual_scope_selection import FACTUAL_SCOPE_CONTRACT_VERSION
from apps.intercompany_pools.factual_sync_runtime import build_factual_sales_report_sync_scope
from apps.intercompany_pools.factual_workspace_runtime import (
    PoolFactualScope,
    _get_or_create_checkpoint_for_scope,
    _update_checkpoint_scope_contract,
    ensure_pool_factual_workspace_default_sync,
    resolve_pool_factual_sync_activity,
)
from apps.intercompany_pools.factual_workflow_runtime import PoolFactualSyncWorkflowStartResult
from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSettlement,
    PoolBatchSettlementStatus,
    PoolBatchSourceType,
    PoolFactualLane,
    PoolFactualSyncCheckpoint,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-workspace-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-workspace-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_pool(*, tenant: Tenant, suffix: str) -> OrganizationPool:
    return OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-workspace-pool-{suffix}-{uuid4().hex[:6]}",
        name=f"Factual Workspace Pool {suffix}",
    )


@pytest.mark.django_db
def test_get_or_create_checkpoint_for_scope_upgrades_legacy_checkpoint_and_backfills_scope_contract() -> None:
    tenant = Tenant.objects.create(
        slug=f"factual-workspace-upgrade-{uuid4().hex[:6]}",
        name="Factual Workspace Upgrade",
    )
    pool = _create_pool(tenant=tenant, suffix="upgrade")
    database = _create_database(tenant=tenant, suffix="upgrade")
    legacy_checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        scope_fingerprint="",
        metadata={},
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
                "binding_source": "binding_table",
            },
            {
                "canonical_id": "factual_sales_report_90_01",
                "code": "90.01",
                "name": "90.01",
                "chart_identity": "ChartOfAccounts_Хозрасчетный",
                "target_ref_key": "account-90",
                "binding_source": "binding_table",
            },
        ),
        contract_version=FACTUAL_SCOPE_CONTRACT_VERSION,
    )

    checkpoint, created = _get_or_create_checkpoint_for_scope(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        scope_fingerprint=scope.scope_fingerprint,
        default_entrypoint="pools_factual_workspace",
    )

    assert created is False
    assert checkpoint.id == legacy_checkpoint.id
    assert checkpoint.scope_fingerprint == scope.scope_fingerprint
    assert checkpoint.metadata["default_entrypoint"] == "pools_factual_workspace"

    checkpoint = _update_checkpoint_scope_contract(
        checkpoint=checkpoint,
        scope=scope,
        default_entrypoint="pools_factual_workspace",
    )
    checkpoint.refresh_from_db()

    assert checkpoint.metadata["source_scope"]["scope_fingerprint"] == scope.scope_fingerprint
    assert checkpoint.metadata["factual_scope_contract"]["contract_version"] == FACTUAL_SCOPE_CONTRACT_VERSION
    assert checkpoint.metadata["factual_scope_contract"]["selector_key"] == f"pool:{pool.id}:sales_report_v1:2026-01-01"
    assert checkpoint.metadata["factual_scope_contract"]["resolved_bindings"][0]["target_ref_key"] == "account-62"


@pytest.mark.django_db
def test_resolve_pool_factual_sync_activity_returns_warm_for_historical_open_context() -> None:
    tenant = Tenant.objects.create(
        slug=f"factual-workspace-activity-{uuid4().hex[:6]}",
        name="Factual Workspace Activity",
    )
    pool = _create_pool(tenant=tenant, suffix="activity")
    batch = PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.MANUAL,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        source_reference="receipt-q1-open",
    )
    PoolBatchSettlement.objects.create(
        tenant=tenant,
        batch=batch,
        status=PoolBatchSettlementStatus.PARTIALLY_CLOSED,
        incoming_amount="120.00",
        outgoing_amount="80.00",
        open_balance="40.00",
        summary={},
    )

    decision = resolve_pool_factual_sync_activity(
        pool=pool,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        now=datetime(2026, 4, 14, 10, 0, tzinfo=dt_timezone.utc),
    )

    assert decision.activity == "warm"
    assert decision.polling_tier == "warm"
    assert decision.poll_interval_seconds == 600
    assert decision.freshness_target_seconds == 600
    assert decision.reason == "open_context"


@pytest.mark.django_db
def test_ensure_pool_factual_workspace_default_sync_force_refresh_uses_active_metadata() -> None:
    tenant = Tenant.objects.create(
        slug=f"factual-workspace-force-{uuid4().hex[:6]}",
        name="Factual Workspace Force Refresh",
    )
    pool = _create_pool(tenant=tenant, suffix="force")
    database = _create_database(tenant=tenant, suffix="force")
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 4, 1),
        quarter_end=date(2026, 6, 30),
        last_synced_at=datetime(2026, 4, 14, 9, 59, tzinfo=dt_timezone.utc),
        workflow_status="completed",
        metadata={
            "freshness_state": "fresh",
            "freshness_target_seconds": 600,
        },
    )
    fixed_now = datetime(2026, 4, 14, 10, 0, tzinfo=dt_timezone.utc)
    factual_scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 4, 1),
        quarter_end=date(2026, 6, 30),
        organization_ids=("org-a",),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
    )

    with patch(
        "apps.intercompany_pools.factual_workspace_runtime.resolve_pool_factual_scope",
        return_value=PoolFactualScope(
            organization_ids=("org-a",),
            databases=(database,),
            quarter_end=date(2026, 6, 30),
            freeze_quarter=False,
        ),
    ), patch(
        "apps.intercompany_pools.factual_workspace_runtime.resolve_pool_factual_sync_scope_for_database",
        return_value=factual_scope,
    ), patch(
        "apps.intercompany_pools.factual_workspace_runtime.start_pool_factual_sync_workflow",
    ) as start_workflow:
        def _fake_start(**kwargs):
            refreshed = kwargs["checkpoint"]
            refreshed.workflow_status = "running"
            refreshed.save(update_fields=["workflow_status", "updated_at"])
            return PoolFactualSyncWorkflowStartResult(
                checkpoint=refreshed,
                execution_id="11111111-1111-1111-1111-111111111111",
                operation_id="22222222-2222-2222-2222-222222222222",
                enqueue_success=True,
                enqueue_status="running",
                enqueue_error=None,
                created_execution=True,
            )

        start_workflow.side_effect = _fake_start

        checkpoints = ensure_pool_factual_workspace_default_sync(
            pool=pool,
            quarter_start=date(2026, 4, 1),
            now=fixed_now,
            requested_activity="active",
            force_sync=True,
        )

    checkpoint.refresh_from_db()
    assert len(checkpoints) == 1
    assert checkpoint.id == checkpoints[0].id
    assert checkpoint.metadata["activity"] == "active"
    assert checkpoint.metadata["polling_tier"] == "active"
    assert checkpoint.metadata["poll_interval_seconds"] == 120
    assert checkpoint.metadata["freshness_target_seconds"] == 120
    start_workflow.assert_called_once()
    assert start_workflow.call_args.kwargs["activity"] == "active"


@pytest.mark.django_db
def test_ensure_pool_factual_workspace_default_sync_reconciles_stale_running_checkpoint_with_legacy_execution_contract_before_retry() -> None:
    tenant = Tenant.objects.create(
        slug=f"factual-workspace-reconcile-{uuid4().hex[:6]}",
        name="Factual Workspace Reconcile",
    )
    pool = _create_pool(tenant=tenant, suffix="reconcile")
    database = _create_database(tenant=tenant, suffix="reconcile")
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 4, 1),
        quarter_end=date(2026, 6, 30),
        workflow_status="running",
        workflow_execution_id=UUID("11111111-1111-1111-1111-111111111111"),
        operation_id=UUID("11111111-1111-1111-1111-111111111111"),
        metadata={
            "freshness_state": "stale",
            "freshness_target_seconds": 120,
        },
    )
    fixed_now = datetime(2026, 4, 14, 10, 0, tzinfo=dt_timezone.utc)
    factual_scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 4, 1),
        quarter_end=date(2026, 6, 30),
        organization_ids=("org-a",),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
    )
    failed_execution = SimpleNamespace(
        id=checkpoint.workflow_execution_id,
        status="failed",
        error_code="POOL_FACTUAL_SYNC_FAILED",
        error_message="source unavailable",
        input_context={
            "contract_version": "pool_factual_sync_workflow.v1",
            "checkpoint_id": str(checkpoint.id),
            "tenant_id": str(tenant.id),
            "pool_id": str(pool.id),
            "database_id": str(database.id),
            "quarter_start": "2026-04-01",
            "quarter_end": "2026-06-30",
            "organization_ids": "org-a",
            "account_codes": "62.01,90.01",
            "movement_kinds": "credit,debit",
            "lane": PoolFactualLane.READ,
            # Legacy executions in the contour can miss newer source-boundary fields.
            "correlation_id": "corr-factual-workspace-reconcile",
            "origin_system": "tests",
            "origin_event_id": "evt-factual-workspace-reconcile",
            "activity": "active",
        },
    )

    with patch(
        "apps.intercompany_pools.factual_workspace_runtime.resolve_pool_factual_scope",
        return_value=PoolFactualScope(
            organization_ids=("org-a",),
            databases=(database,),
            quarter_end=date(2026, 6, 30),
            freeze_quarter=False,
        ),
    ), patch(
        "apps.intercompany_pools.factual_workspace_runtime.resolve_pool_factual_sync_scope_for_database",
        return_value=factual_scope,
    ), patch(
        "apps.intercompany_pools.factual_workspace_runtime.WorkflowExecution.objects.filter",
    ) as workflow_filter, patch(
        "apps.intercompany_pools.factual_workspace_runtime.start_pool_factual_sync_workflow",
    ) as start_workflow:
        workflow_filter.return_value.first.return_value = failed_execution

        def _fake_start(**kwargs):
            refreshed = kwargs["checkpoint"]
            assert refreshed.workflow_status == "failed"
            assert refreshed.last_error_code == "POOL_FACTUAL_SYNC_FAILED"
            refreshed.workflow_status = "running"
            refreshed.workflow_execution_id = UUID("22222222-2222-2222-2222-222222222222")
            refreshed.operation_id = UUID("22222222-2222-2222-2222-222222222222")
            refreshed.last_error_code = ""
            refreshed.last_error = ""
            refreshed.save(
                update_fields=[
                    "workflow_status",
                    "workflow_execution_id",
                    "operation_id",
                    "last_error_code",
                    "last_error",
                    "updated_at",
                ]
            )
            return PoolFactualSyncWorkflowStartResult(
                checkpoint=refreshed,
                execution_id="22222222-2222-2222-2222-222222222222",
                operation_id="22222222-2222-2222-2222-222222222222",
                enqueue_success=True,
                enqueue_status="running",
                enqueue_error=None,
                created_execution=False,
            )

        start_workflow.side_effect = _fake_start

        checkpoints = ensure_pool_factual_workspace_default_sync(
            pool=pool,
            quarter_start=date(2026, 4, 1),
            now=fixed_now,
            requested_activity="active",
            force_sync=False,
        )

    checkpoint.refresh_from_db()
    assert len(checkpoints) == 1
    assert checkpoints[0].id == checkpoint.id
    assert checkpoint.workflow_status == "running"
    assert checkpoint.workflow_execution_id == UUID("22222222-2222-2222-2222-222222222222")
    workflow_filter.assert_called_once()
    start_workflow.assert_called_once()
