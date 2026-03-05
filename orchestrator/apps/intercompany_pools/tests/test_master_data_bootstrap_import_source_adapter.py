from __future__ import annotations

from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.master_data_bootstrap_import_source_adapter import (
    BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED,
    fetch_pool_master_data_bootstrap_source_rows,
    reset_pool_master_data_bootstrap_source_callbacks,
    run_pool_master_data_bootstrap_source_preflight,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, name: str, metadata: dict | None = None) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        odata_url="http://localhost/odata/bootstrap-source.odata",
        username="legacy-user",
        password="legacy-pass",
        metadata=metadata or {},
    )


@pytest.fixture(autouse=True)
def _reset_callbacks() -> None:
    reset_pool_master_data_bootstrap_source_callbacks()
    yield
    reset_pool_master_data_bootstrap_source_callbacks()


@pytest.mark.django_db
def test_source_preflight_fails_when_mapping_is_missing() -> None:
    tenant = Tenant.objects.create(slug=f"bootstrap-source-{uuid4().hex[:8]}", name="Bootstrap Source Tenant")
    database = _create_database(tenant=tenant, name=f"bootstrap-source-db-{uuid4().hex[:8]}")

    result = run_pool_master_data_bootstrap_source_preflight(
        tenant_id=str(tenant.id),
        database=database,
        entity_scope=["party"],
        actor_id="",
    )

    assert result.ok is False
    assert result.errors
    assert result.errors[0]["code"] == BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED


@pytest.mark.django_db
def test_source_fetch_rows_reads_rows_from_database_metadata() -> None:
    tenant = Tenant.objects.create(slug=f"bootstrap-source-md-{uuid4().hex[:8]}", name="Bootstrap Source Metadata")
    database = _create_database(
        tenant=tenant,
        name=f"bootstrap-source-md-db-{uuid4().hex[:8]}",
        metadata={
            "bootstrap_import_rows": {
                "party": [
                    {"canonical_id": "party-001", "name": "Party 001"},
                    {"canonical_id": "party-002", "name": "Party 002"},
                ]
            }
        },
    )

    rows = fetch_pool_master_data_bootstrap_source_rows(
        tenant_id=str(tenant.id),
        database=database,
        entity_type="party",
        actor_id="",
    )

    assert len(rows) == 2
    assert rows[0]["canonical_id"] == "party-001"
