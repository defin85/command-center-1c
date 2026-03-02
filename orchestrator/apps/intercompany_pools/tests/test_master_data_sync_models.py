from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncConflict,
    PoolMasterDataSyncConflictStatus,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-model-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_sync_job_persists_machine_readable_status() -> None:
    tenant = Tenant.objects.create(slug="sync-job-status", name="Sync Job Status")
    database = _create_database(tenant=tenant, suffix="job")

    job = PoolMasterDataSyncJob.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncJobStatus.PENDING,
    )

    assert job.status == "pending"


@pytest.mark.django_db
def test_sync_checkpoint_is_unique_per_tenant_database_entity_scope() -> None:
    tenant = Tenant.objects.create(slug="sync-checkpoint-uniq", name="Sync Checkpoint Uniq")
    database = _create_database(tenant=tenant, suffix="checkpoint")
    PoolMasterDataSyncCheckpoint.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status="active",
        checkpoint_token="cp-1",
    )

    with pytest.raises(ValidationError):
        PoolMasterDataSyncCheckpoint.objects.create(
            tenant=tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.PARTY,
            status="active",
            checkpoint_token="cp-2",
        )


@pytest.mark.django_db
def test_sync_outbox_uses_scope_and_dedupe_key_uniqueness() -> None:
    tenant = Tenant.objects.create(slug="sync-outbox-dedupe", name="Sync Outbox Dedupe")
    database = _create_database(tenant=tenant, suffix="outbox")
    PoolMasterDataSyncOutbox.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.CONTRACT,
        status=PoolMasterDataSyncOutboxStatus.PENDING,
        dedupe_key="dedupe-001",
        payload={"canonical_id": "contract-001"},
    )

    with pytest.raises(ValidationError):
        PoolMasterDataSyncOutbox.objects.create(
            tenant=tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.CONTRACT,
            status=PoolMasterDataSyncOutboxStatus.PENDING,
            dedupe_key="dedupe-001",
            payload={"canonical_id": "contract-001"},
        )


@pytest.mark.django_db
def test_sync_conflict_persists_machine_readable_status() -> None:
    tenant = Tenant.objects.create(slug="sync-conflict-status", name="Sync Conflict Status")
    database = _create_database(tenant=tenant, suffix="conflict")

    conflict = PoolMasterDataSyncConflict.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.TAX_PROFILE,
        status=PoolMasterDataSyncConflictStatus.PENDING,
        conflict_code="POLICY_VIOLATION",
        canonical_id="tax-001",
    )

    assert conflict.status == "pending"


@pytest.mark.django_db
def test_sync_models_reject_cross_tenant_database_scope() -> None:
    tenant = Tenant.objects.create(slug="sync-model-tenant-a", name="Sync Model Tenant A")
    foreign_tenant = Tenant.objects.create(slug="sync-model-tenant-b", name="Sync Model Tenant B")
    foreign_database = _create_database(tenant=foreign_tenant, suffix="foreign")

    with pytest.raises(ValidationError):
        PoolMasterDataSyncJob.objects.create(
            tenant=tenant,
            database=foreign_database,
            entity_type=PoolMasterDataEntityType.ITEM,
            status=PoolMasterDataSyncJobStatus.PENDING,
        )
