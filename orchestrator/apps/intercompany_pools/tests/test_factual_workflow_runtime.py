from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4
from unittest.mock import patch

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.factual_workflow_runtime import start_pool_factual_sync_workflow
from apps.intercompany_pools.models import OrganizationPool, PoolFactualLane, PoolFactualSyncCheckpoint
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

    message = mock_redis_client.enqueue_operation_stream.call_args.args[0]
    assert message["payload"]["data"]["role"] == "read"
    assert message["metadata"]["role"] == "read"
    mock_event_publisher.publish.assert_called_once()
