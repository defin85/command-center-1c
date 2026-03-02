from __future__ import annotations

from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_workflow_contract import (
    POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT,
    POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT_INVALID,
    build_master_data_sync_workflow_input_context,
    validate_master_data_sync_workflow_input_context,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncDirection,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncPolicy,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-wf-contract-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_build_sync_workflow_input_context_contains_scope_policy_and_correlation() -> None:
    tenant = Tenant.objects.create(slug="sync-wf-contract-build", name="Sync WF Contract Build")
    database = _create_database(tenant=tenant, suffix="build")
    job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        direction=PoolMasterDataSyncDirection.OUTBOUND,
        status=PoolMasterDataSyncJobStatus.PENDING,
    )

    context = build_master_data_sync_workflow_input_context(
        sync_job=job,
        correlation_id="corr-sync-001",
        origin_system="cc",
        origin_event_id="evt-sync-001",
    )

    assert context["contract_version"] == POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT
    assert context["sync_job_id"] == str(job.id)
    assert context["tenant_id"] == str(tenant.id)
    assert context["database_id"] == str(database.id)
    assert context["entity_type"] == PoolMasterDataEntityType.ITEM
    assert context["sync_policy"] == PoolMasterDataSyncPolicy.BIDIRECTIONAL
    assert context["sync_direction"] == PoolMasterDataSyncDirection.OUTBOUND
    assert context["correlation_id"] == "corr-sync-001"
    assert context["origin_system"] == "cc"
    assert context["origin_event_id"] == "evt-sync-001"


@pytest.mark.django_db
def test_validate_sync_workflow_input_context_accepts_valid_payload() -> None:
    payload = {
        "contract_version": POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT,
        "sync_job_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "database_id": str(uuid4()),
        "entity_type": PoolMasterDataEntityType.CONTRACT,
        "sync_policy": PoolMasterDataSyncPolicy.IB_MASTER,
        "sync_direction": PoolMasterDataSyncDirection.INBOUND,
        "correlation_id": "corr-001",
        "origin_system": "ib",
        "origin_event_id": "evt-001",
    }

    validated = validate_master_data_sync_workflow_input_context(input_context=payload)
    assert validated["entity_type"] == PoolMasterDataEntityType.CONTRACT
    assert validated["sync_policy"] == PoolMasterDataSyncPolicy.IB_MASTER
    assert validated["sync_direction"] == PoolMasterDataSyncDirection.INBOUND


@pytest.mark.django_db
def test_validate_sync_workflow_input_context_fails_closed_when_correlation_missing() -> None:
    payload = {
        "contract_version": POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT,
        "sync_job_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "database_id": str(uuid4()),
        "entity_type": PoolMasterDataEntityType.PARTY,
        "sync_policy": PoolMasterDataSyncPolicy.CC_MASTER,
        "sync_direction": PoolMasterDataSyncDirection.BIDIRECTIONAL,
        "correlation_id": "",
        "origin_system": "cc",
        "origin_event_id": "evt-001",
    }

    with pytest.raises(
        ValueError,
        match=POOL_MASTER_DATA_SYNC_WORKFLOW_CONTRACT_INVALID,
    ):
        validate_master_data_sync_workflow_input_context(input_context=payload)
