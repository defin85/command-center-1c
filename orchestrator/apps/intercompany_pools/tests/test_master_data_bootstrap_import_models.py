from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    PoolMasterDataBootstrapImportEntityType,
    PoolMasterDataBootstrapImportChunk,
    PoolMasterDataBootstrapImportChunkStatus,
    PoolMasterDataBootstrapImportJob,
    PoolMasterDataBootstrapImportJobStatus,
    PoolMasterDataBootstrapImportReport,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"bootstrap-model-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/bootstrap-{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_bootstrap_job_persists_entity_scope_and_status() -> None:
    tenant = Tenant.objects.create(slug="bootstrap-job-status", name="Bootstrap Job Status")
    database = _create_database(tenant=tenant, suffix="job")

    job = PoolMasterDataBootstrapImportJob.objects.create(
        tenant=tenant,
        database=database,
        entity_scope=[
            PoolMasterDataBootstrapImportEntityType.PARTY,
            PoolMasterDataBootstrapImportEntityType.ITEM,
        ],
        status=PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_PENDING,
    )

    assert job.status == PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_PENDING
    assert job.entity_scope == [
        PoolMasterDataBootstrapImportEntityType.PARTY,
        PoolMasterDataBootstrapImportEntityType.ITEM,
    ]


@pytest.mark.django_db
def test_bootstrap_job_rejects_unknown_entity_scope_value() -> None:
    tenant = Tenant.objects.create(slug="bootstrap-job-invalid", name="Bootstrap Job Invalid")
    database = _create_database(tenant=tenant, suffix="invalid")

    with pytest.raises(ValidationError):
        PoolMasterDataBootstrapImportJob.objects.create(
            tenant=tenant,
            database=database,
            entity_scope=[PoolMasterDataBootstrapImportEntityType.PARTY, "unknown"],
            status=PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_PENDING,
        )


@pytest.mark.django_db
def test_bootstrap_chunk_is_unique_per_job_entity_and_chunk_index() -> None:
    tenant = Tenant.objects.create(slug="bootstrap-chunk-uniq", name="Bootstrap Chunk Uniq")
    database = _create_database(tenant=tenant, suffix="chunk")
    job = PoolMasterDataBootstrapImportJob.objects.create(
        tenant=tenant,
        database=database,
        entity_scope=[PoolMasterDataBootstrapImportEntityType.ITEM],
        status=PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING,
    )
    PoolMasterDataBootstrapImportChunk.objects.create(
        job=job,
        entity_type=PoolMasterDataBootstrapImportEntityType.ITEM,
        chunk_index=0,
        status=PoolMasterDataBootstrapImportChunkStatus.PENDING,
        records_total=100,
    )

    with pytest.raises(ValidationError):
        PoolMasterDataBootstrapImportChunk.objects.create(
            job=job,
            entity_type=PoolMasterDataBootstrapImportEntityType.ITEM,
            chunk_index=0,
            status=PoolMasterDataBootstrapImportChunkStatus.PENDING,
            records_total=100,
        )


@pytest.mark.django_db
def test_bootstrap_report_is_unique_per_job() -> None:
    tenant = Tenant.objects.create(slug="bootstrap-report-uniq", name="Bootstrap Report Uniq")
    database = _create_database(tenant=tenant, suffix="report")
    job = PoolMasterDataBootstrapImportJob.objects.create(
        tenant=tenant,
        database=database,
        entity_scope=[PoolMasterDataBootstrapImportEntityType.CONTRACT],
        status=PoolMasterDataBootstrapImportJobStatus.FINALIZED,
    )
    PoolMasterDataBootstrapImportReport.objects.create(
        job=job,
        created_count=1,
        updated_count=2,
        skipped_count=0,
        failed_count=1,
    )

    with pytest.raises(ValidationError):
        PoolMasterDataBootstrapImportReport.objects.create(
            job=job,
            created_count=0,
            updated_count=0,
            skipped_count=0,
            failed_count=0,
        )


@pytest.mark.django_db
def test_bootstrap_job_rejects_cross_tenant_database_scope() -> None:
    tenant = Tenant.objects.create(slug="bootstrap-tenant-a", name="Bootstrap Tenant A")
    foreign_tenant = Tenant.objects.create(slug="bootstrap-tenant-b", name="Bootstrap Tenant B")
    foreign_database = _create_database(tenant=foreign_tenant, suffix="foreign")

    with pytest.raises(ValidationError):
        PoolMasterDataBootstrapImportJob.objects.create(
            tenant=tenant,
            database=foreign_database,
            entity_scope=[PoolMasterDataBootstrapImportEntityType.PARTY],
            status=PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_PENDING,
        )
