from __future__ import annotations

from uuid import uuid4

import pytest

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.master_data_bootstrap_import_source_adapter import (
    BOOTSTRAP_SOURCE_MODE_METADATA_ROWS,
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
def test_source_fetch_rows_reads_rows_from_database_metadata_only_in_explicit_metadata_mode() -> None:
    tenant = Tenant.objects.create(slug=f"bootstrap-source-md-{uuid4().hex[:8]}", name="Bootstrap Source Metadata")
    database = _create_database(
        tenant=tenant,
        name=f"bootstrap-source-md-db-{uuid4().hex[:8]}",
        metadata={
            "bootstrap_import_source_mode": BOOTSTRAP_SOURCE_MODE_METADATA_ROWS,
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


@pytest.mark.django_db
def test_source_fetch_rows_supports_gl_account_rows_in_metadata_mode() -> None:
    tenant = Tenant.objects.create(slug=f"bootstrap-source-gl-{uuid4().hex[:8]}", name="Bootstrap Source GL")
    database = _create_database(
        tenant=tenant,
        name=f"bootstrap-source-gl-db-{uuid4().hex[:8]}",
        metadata={
            "bootstrap_import_source_mode": BOOTSTRAP_SOURCE_MODE_METADATA_ROWS,
            "bootstrap_import_rows": {
                "gl_account": [
                    {
                        "canonical_id": "gl-001",
                        "code": "10.01",
                        "name": "Основной счет",
                        "chart_identity": "ChartOfAccounts_Main",
                    }
                ]
            },
        },
    )

    rows = fetch_pool_master_data_bootstrap_source_rows(
        tenant_id=str(tenant.id),
        database=database,
        entity_type="gl_account",
        actor_id="",
    )

    assert rows == [
        {
            "canonical_id": "gl-001",
            "code": "10.01",
            "name": "Основной счет",
            "chart_identity": "ChartOfAccounts_Main",
        }
    ]


@pytest.mark.django_db
def test_source_fetch_rows_reads_full_odata_pages_with_mapping(monkeypatch) -> None:
    tenant = Tenant.objects.create(slug=f"bootstrap-source-odata-{uuid4().hex[:8]}", name="Bootstrap Source OData")
    database = _create_database(
        tenant=tenant,
        name=f"bootstrap-source-odata-db-{uuid4().hex[:8]}",
        metadata={
            "bootstrap_import_source": {
                "page_size": 2,
                "entities": {
                    "party": {
                        "entity_name": "Catalog_Контрагенты",
                        "field_mapping": {
                            "canonical_id": "Ref_Key",
                            "name": "Description",
                        },
                    }
                },
            }
        },
    )
    InfobaseUserMapping.objects.create(
        database=database,
        ib_username="svc-user",
        ib_password="svc-pass",
        is_service=True,
    )

    calls: list[dict[str, object]] = []

    class _FakeODataClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def health_check(self) -> bool:
            return True

        def get_entities(
            self,
            entity_name: str,
            filter_query=None,
            select_fields=None,
            top=None,
            skip=None,
        ):
            calls.append(
                {
                    "entity_name": entity_name,
                    "filter_query": filter_query,
                    "select_fields": list(select_fields or []),
                    "top": top,
                    "skip": skip,
                }
            )
            if int(skip or 0) == 0:
                return [
                    {"Ref_Key": "party-001", "Description": "Party 001"},
                    {"Ref_Key": "party-002", "Description": "Party 002"},
                ]
            return []

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "apps.intercompany_pools.master_data_bootstrap_import_source_adapter.ODataClient",
        _FakeODataClient,
    )

    preflight = run_pool_master_data_bootstrap_source_preflight(
        tenant_id=str(tenant.id),
        database=database,
        entity_scope=["party"],
        actor_id="",
    )
    assert preflight.ok is True
    assert preflight.coverage == {"party": True}

    rows = fetch_pool_master_data_bootstrap_source_rows(
        tenant_id=str(tenant.id),
        database=database,
        entity_type="party",
        actor_id="",
    )
    assert rows == [
        {"canonical_id": "party-001", "name": "Party 001"},
        {"canonical_id": "party-002", "name": "Party 002"},
    ]

    fetch_calls = [call for call in calls if call.get("entity_name") == "Catalog_Контрагенты"]
    assert len(fetch_calls) == 3
    assert fetch_calls[1]["skip"] == 0
    assert fetch_calls[2]["skip"] == 2
