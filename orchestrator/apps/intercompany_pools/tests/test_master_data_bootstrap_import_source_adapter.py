from __future__ import annotations

from uuid import uuid4

import pytest

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.master_data_bootstrap_import_source_adapter import (
    BOOTSTRAP_SOURCE_MODE_METADATA_ROWS,
    CHART_ROW_SOURCE_PROBE_FAILED,
    BOOTSTRAP_SOURCE_MAPPING_NOT_CONFIGURED,
    build_standard_chart_odata_row_source,
    fetch_pool_master_data_chart_row_source_rows,
    fetch_pool_master_data_bootstrap_source_rows,
    reset_pool_master_data_bootstrap_source_callbacks,
    run_pool_master_data_chart_row_source_preflight,
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


@pytest.mark.django_db
def test_source_fetch_rows_stamps_gl_account_chart_identity_from_chart_entity_name(monkeypatch) -> None:
    tenant = Tenant.objects.create(slug=f"bootstrap-source-chart-{uuid4().hex[:8]}", name="Bootstrap Source Chart")
    database = _create_database(
        tenant=tenant,
        name=f"bootstrap-source-chart-db-{uuid4().hex[:8]}",
        metadata={
            "bootstrap_import_source": {
                "page_size": 50,
                "entities": {
                    "gl_account": {
                        "entity_name": "ChartOfAccounts_Main",
                        "field_mapping": {
                            "canonical_id": "Ref_Key",
                            "code": "Code",
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

    class _FakeODataClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def health_check(self) -> bool:
            return True

        def get_entities(self, *_args, **kwargs):
            if int(kwargs.get("skip") or 0) > 0:
                return []
            return [
                {
                    "Ref_Key": "gl-10-01",
                    "Code": "10.01",
                    "Description": "Materials",
                }
            ]

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "apps.intercompany_pools.master_data_bootstrap_import_source_adapter.ODataClient",
        _FakeODataClient,
    )

    preflight = run_pool_master_data_bootstrap_source_preflight(
        tenant_id=str(tenant.id),
        database=database,
        entity_scope=["gl_account"],
        actor_id="",
    )
    assert preflight.ok is True

    rows = fetch_pool_master_data_bootstrap_source_rows(
        tenant_id=str(tenant.id),
        database=database,
        entity_type="gl_account",
        actor_id="",
    )

    assert rows == [
        {
            "canonical_id": "gl-10-01",
            "code": "10.01",
            "name": "Materials",
            "chart_identity": "ChartOfAccounts_Main",
        }
    ]


@pytest.mark.django_db
def test_chart_row_source_preflight_and_fetch_use_standard_chartofaccounts_mapping(monkeypatch) -> None:
    tenant = Tenant.objects.create(slug=f"chart-row-source-{uuid4().hex[:8]}", name="Chart Row Source")
    database = _create_database(tenant=tenant, name=f"chart-row-source-db-{uuid4().hex[:8]}")
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

        def get_entities(self, entity_name: str, **kwargs):
            calls.append({"entity_name": entity_name, **kwargs})
            if kwargs.get("top") == 1:
                return [{"Ref_Key": "gl-10-01", "Code": "10.01", "Description": "Materials"}]
            if int(kwargs.get("skip") or 0) == 0:
                return [
                    {"Ref_Key": "gl-10-01", "Code": "10.01", "Description": "Materials"},
                    {"Ref_Key": "gl-60-01", "Code": "60.01", "Description": "Suppliers"},
                ]
            return []

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "apps.intercompany_pools.master_data_bootstrap_import_source_adapter.ODataClient",
        _FakeODataClient,
    )

    row_source = build_standard_chart_odata_row_source(chart_identity="ChartOfAccounts_Main")
    row_source["row_source_page_size"] = 2
    preflight = run_pool_master_data_chart_row_source_preflight(
        tenant_id=str(tenant.id),
        database=database,
        row_source=row_source,
    )
    assert preflight.ok is True
    assert preflight.credential_strategy == "service"

    rows = fetch_pool_master_data_chart_row_source_rows(
        tenant_id=str(tenant.id),
        database=database,
        row_source=row_source,
    )
    assert rows == [
        {
            "canonical_id": "gl-10-01",
            "source_ref": "gl-10-01",
            "code": "10.01",
            "name": "Materials",
            "chart_identity": "ChartOfAccounts_Main",
        },
        {
            "canonical_id": "gl-60-01",
            "source_ref": "gl-60-01",
            "code": "60.01",
            "name": "Suppliers",
            "chart_identity": "ChartOfAccounts_Main",
        },
    ]
    assert calls[0]["select_fields"] == ["Ref_Key", "Code", "Description"]
    assert calls[0]["order_by"] == ["Ref_Key", "Code"]
    assert calls[1]["skip"] == 0
    assert calls[2]["skip"] == 2


@pytest.mark.django_db
def test_chart_row_source_probe_fails_when_required_fields_are_missing(monkeypatch) -> None:
    tenant = Tenant.objects.create(slug=f"chart-row-missing-{uuid4().hex[:8]}", name="Chart Row Missing")
    database = _create_database(tenant=tenant, name=f"chart-row-missing-db-{uuid4().hex[:8]}")
    InfobaseUserMapping.objects.create(
        database=database,
        ib_username="svc-user",
        ib_password="svc-pass",
        is_service=True,
    )

    class _FakeODataClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def health_check(self) -> bool:
            return True

        def get_entities(self, *_args, **_kwargs):
            return [{"Ref_Key": "gl-10-01", "Code": "10.01"}]

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "apps.intercompany_pools.master_data_bootstrap_import_source_adapter.ODataClient",
        _FakeODataClient,
    )

    preflight = run_pool_master_data_chart_row_source_preflight(
        tenant_id=str(tenant.id),
        database=database,
        row_source=build_standard_chart_odata_row_source(chart_identity="ChartOfAccounts_Main"),
    )

    assert preflight.ok is False
    assert preflight.errors[0]["code"] == CHART_ROW_SOURCE_PROBE_FAILED
    assert "Description" in preflight.errors[0]["detail"]
