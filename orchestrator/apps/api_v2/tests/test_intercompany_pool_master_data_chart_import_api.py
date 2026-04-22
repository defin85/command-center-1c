from __future__ import annotations

from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Database
from apps.intercompany_pools.business_configuration_profile import persist_business_configuration_profile
from apps.intercompany_pools.master_data_bindings import upsert_pool_master_data_binding
from apps.intercompany_pools.master_data_bootstrap_import_source_adapter import (
    PoolMasterDataBootstrapSourcePreflightResult,
    configure_pool_master_data_bootstrap_source_callbacks,
    reset_pool_master_data_bootstrap_source_callbacks,
)
from apps.intercompany_pools.models import PoolMasterBindingSyncStatus
from apps.intercompany_pools.models import PoolMasterDataBinding
from apps.intercompany_pools.models import PoolMasterGLAccount
from apps.tenancy.models import Tenant, TenantMember


CHART_IDENTITY = "ChartOfAccounts_Main"


@pytest.fixture(autouse=True)
def _reset_bootstrap_callbacks() -> None:
    reset_pool_master_data_bootstrap_source_callbacks()
    yield
    reset_pool_master_data_bootstrap_source_callbacks()


@pytest.fixture
def default_tenant() -> Tenant:
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    return tenant


@pytest.fixture
def admin_user(default_tenant: Tenant) -> User:
    user = User.objects.create_user(username=f"pool-chart-admin-{uuid4().hex[:8]}", password="pass")
    membership, _ = TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=user,
        defaults={"role": TenantMember.ROLE_ADMIN},
    )
    if membership.role != TenantMember.ROLE_ADMIN:
        membership.role = TenantMember.ROLE_ADMIN
        membership.save(update_fields=["role"])
    return user


@pytest.fixture
def admin_client(admin_user: User, default_tenant: Tenant) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=admin_user)
    client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))
    return client


def _create_database(*, tenant: Tenant, name: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        odata_url="http://localhost/odata/chart-import.odata",
        username="user",
        password="pass",
    )


def _set_business_configuration_profile(
    *,
    database: Database,
    config_name: str = "Accounting Enterprise",
    config_version: str = "3.0.1",
) -> None:
    persist_business_configuration_profile(
        database=database,
        profile={
            "config_name": config_name,
            "config_root_name": "AccountingEnterprise",
            "config_version": config_version,
            "config_vendor": '1C',
            "config_generation_id": uuid4().hex,
            "config_name_source": "synonym_ru",
            "verification_status": "verified",
            "verified_at": "2026-04-22T00:00:00+00:00",
        },
    )


def _configure_source_callbacks(*, rows_by_database: dict[str, dict[str, list[dict]]]) -> None:
    def _preflight(*, database: Database, entity_scope: list[str], **_kwargs) -> PoolMasterDataBootstrapSourcePreflightResult:
        return PoolMasterDataBootstrapSourcePreflightResult(
            ok=True,
            source_kind="ib_odata",
            coverage={entity: True for entity in entity_scope},
            credential_strategy="service",
            errors=[],
            diagnostics={"database_id": str(database.id), "source": "test"},
        )

    def _fetch_rows(*, database: Database, entity_type: str, **_kwargs) -> list[dict]:
        return list((rows_by_database.get(str(database.id)) or {}).get(entity_type, []))

    configure_pool_master_data_bootstrap_source_callbacks(
        preflight=_preflight,
        fetch_rows=_fetch_rows,
    )


def _upsert_chart_source(*, client: APIClient, database_id: str, chart_identity: str = CHART_IDENTITY) -> dict:
    response = client.post(
        "/api/v2/pools/master-data/chart-import/sources/upsert/",
        {
            "database_id": database_id,
            "chart_identity": chart_identity,
        },
        format="json",
    )
    assert response.status_code == 200
    return response.json()["source"]


def _create_chart_job(
    *,
    client: APIClient,
    chart_source_id: str,
    mode: str,
    database_ids: list[str] | None = None,
) -> dict:
    response = client.post(
        "/api/v2/pools/master-data/chart-import/jobs/",
        {
            "chart_source_id": chart_source_id,
            "mode": mode,
            "database_ids": list(database_ids or []),
        },
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()["job"]
    assert payload["status"] == "succeeded"
    return payload


@pytest.mark.django_db
def test_chart_import_requires_preflight_before_dry_run_and_dry_run_before_materialize(
    admin_client: APIClient,
    default_tenant: Tenant,
) -> None:
    source_database = _create_database(tenant=default_tenant, name=f"chart-source-{uuid4().hex[:8]}")
    _set_business_configuration_profile(database=source_database)
    _configure_source_callbacks(
        rows_by_database={
            str(source_database.id): {
                "gl_account": [
                    {
                        "canonical_id": "legacy-10-01",
                        "source_ref": "src-10-01-v1",
                        "code": "10.01",
                        "name": "Materials",
                        "chart_identity": CHART_IDENTITY,
                        "config_name": "Accounting Enterprise",
                        "config_version": "3.0.1",
                    }
                ]
            }
        }
    )

    source = _upsert_chart_source(client=admin_client, database_id=str(source_database.id))

    dry_run_without_preflight = admin_client.post(
        "/api/v2/pools/master-data/chart-import/jobs/",
        {
            "chart_source_id": source["id"],
            "mode": "dry_run",
        },
        format="json",
    )
    assert dry_run_without_preflight.status_code == 409
    assert dry_run_without_preflight.json()["code"] == "CHART_JOB_PREREQUISITE_MISSING"
    assert "preflight" in dry_run_without_preflight.json()["detail"]

    _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="preflight")

    materialize_without_dry_run = admin_client.post(
        "/api/v2/pools/master-data/chart-import/jobs/",
        {
            "chart_source_id": source["id"],
            "mode": "materialize",
        },
        format="json",
    )
    assert materialize_without_dry_run.status_code == 409
    assert materialize_without_dry_run.json()["code"] == "CHART_JOB_PREREQUISITE_MISSING"
    assert "dry_run" in materialize_without_dry_run.json()["detail"]

    _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="dry_run")
    materialize_job = _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="materialize")
    assert materialize_job["snapshot"]["materialized_count"] == 1


@pytest.mark.django_db
def test_chart_import_materialization_keeps_deterministic_ids_and_soft_retires(
    admin_client: APIClient,
    default_tenant: Tenant,
) -> None:
    source_database = _create_database(tenant=default_tenant, name=f"chart-source-{uuid4().hex[:8]}")
    follower_database = _create_database(tenant=default_tenant, name=f"chart-follower-{uuid4().hex[:8]}")
    _set_business_configuration_profile(database=source_database)
    _set_business_configuration_profile(database=follower_database)

    rows_by_database = {
        str(source_database.id): {
            "gl_account": [
                {
                    "canonical_id": "legacy-10-01",
                    "source_ref": "src-10-01-v1",
                    "code": "10.01",
                    "name": "Materials",
                    "chart_identity": CHART_IDENTITY,
                    "config_name": "Accounting Enterprise",
                    "config_version": "3.0.1",
                },
                {
                    "canonical_id": "legacy-60-01",
                    "source_ref": "src-60-01-v1",
                    "code": "60.01",
                    "name": "Suppliers",
                    "chart_identity": CHART_IDENTITY,
                    "config_name": "Accounting Enterprise",
                    "config_version": "3.0.1",
                },
            ]
        }
    }
    _configure_source_callbacks(rows_by_database=rows_by_database)

    source = _upsert_chart_source(client=admin_client, database_id=str(source_database.id))
    assert source["config_name"] == "Accounting Enterprise"
    assert source["config_version"] == "3.0.1"
    assert {item["database_id"] for item in source["candidate_databases"]} == {str(follower_database.id)}

    list_response = admin_client.get("/api/v2/pools/master-data/chart-import/sources/")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 1
    assert list_payload["sources"][0]["id"] == source["id"]

    preflight_job = _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="preflight")
    assert preflight_job["counters"]["source_ok"] is True
    assert preflight_job["diagnostics"]["candidate_follower_count"] == 1

    dry_run_job = _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="dry_run")
    assert dry_run_job["counters"]["created_count"] == 2
    assert dry_run_job["counters"]["retired_count"] == 0

    materialize_job = _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="materialize")
    assert materialize_job["snapshot"]["materialized_count"] == 2
    assert materialize_job["snapshot"]["retired_count"] == 0

    first_run_accounts = {
        account.code: account
        for account in PoolMasterGLAccount.objects.filter(tenant=default_tenant, chart_identity=CHART_IDENTITY)
    }
    assert set(first_run_accounts) == {"10.01", "60.01"}
    assert first_run_accounts["10.01"].canonical_id != "legacy-10-01"
    stable_canonical_id = first_run_accounts["60.01"].canonical_id

    rows_by_database[str(source_database.id)] = {
        "gl_account": [
            {
                "canonical_id": "legacy-60-01-v2",
                "source_ref": "src-60-01-v2",
                "code": "60.01",
                "name": "Suppliers and Contractors",
                "chart_identity": CHART_IDENTITY,
                "config_name": "Accounting Enterprise",
                "config_version": "3.0.1",
            }
        ]
    }
    _configure_source_callbacks(rows_by_database=rows_by_database)

    _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="preflight")
    _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="dry_run")
    second_job = _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="materialize")
    assert second_job["snapshot"]["materialized_count"] == 0
    assert second_job["snapshot"]["updated_count"] == 1
    assert second_job["snapshot"]["retired_count"] == 1

    retired_account = PoolMasterGLAccount.objects.get(tenant=default_tenant, canonical_id=first_run_accounts["10.01"].canonical_id)
    assert retired_account.is_retired is True
    assert retired_account.retired_at is not None
    assert retired_account.metadata["chart_materialization"]["retired"] is True

    refreshed_account = PoolMasterGLAccount.objects.get(tenant=default_tenant, code="60.01")
    assert refreshed_account.canonical_id == stable_canonical_id
    assert refreshed_account.name == "Suppliers and Contractors"
    assert refreshed_account.metadata["chart_materialization"]["source_ref"] == "src-60-01-v2"
    assert refreshed_account.metadata["chart_materialization"]["source_canonical_id"] == "legacy-60-01-v2"

    jobs_response = admin_client.get(
        "/api/v2/pools/master-data/chart-import/jobs/",
        {"chart_source_id": source["id"], "mode": "materialize"},
    )
    assert jobs_response.status_code == 200
    jobs_payload = jobs_response.json()
    assert jobs_payload["count"] == 2

    detail_response = admin_client.get(f"/api/v2/pools/master-data/chart-import/jobs/{second_job['id']}/")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["job"]
    assert detail_payload["snapshot"]["retired_count"] == 1
    assert detail_payload["chart_source"]["latest_snapshot"]["fingerprint"] == detail_payload["snapshot"]["fingerprint"]


@pytest.mark.django_db
def test_chart_import_backfill_is_fail_closed_for_ambiguous_and_stale_followers(
    admin_client: APIClient,
    default_tenant: Tenant,
) -> None:
    source_database = _create_database(tenant=default_tenant, name=f"chart-source-{uuid4().hex[:8]}")
    backfill_database = _create_database(tenant=default_tenant, name=f"chart-backfill-{uuid4().hex[:8]}")
    stale_database = _create_database(tenant=default_tenant, name=f"chart-stale-{uuid4().hex[:8]}")
    ambiguous_database = _create_database(tenant=default_tenant, name=f"chart-ambiguous-{uuid4().hex[:8]}")
    for database in (source_database, backfill_database, stale_database, ambiguous_database):
        _set_business_configuration_profile(database=database)

    source_rows = [
        {
            "canonical_id": "legacy-10-01",
            "source_ref": "src-10-01",
            "code": "10.01",
            "name": "Materials",
            "chart_identity": CHART_IDENTITY,
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
        },
        {
            "canonical_id": "legacy-60-01",
            "source_ref": "src-60-01",
            "code": "60.01",
            "name": "Suppliers",
            "chart_identity": CHART_IDENTITY,
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
        },
    ]
    _configure_source_callbacks(
        rows_by_database={
            str(source_database.id): {"gl_account": source_rows},
            str(backfill_database.id): {
                "gl_account": [
                    {
                        "source_ref": "bf-10-01",
                        "code": "10.01",
                        "name": "Materials",
                        "chart_identity": CHART_IDENTITY,
                    },
                    {
                        "source_ref": "bf-60-01",
                        "code": "60.01",
                        "name": "Suppliers",
                        "chart_identity": CHART_IDENTITY,
                    },
                ]
            },
            str(stale_database.id): {
                "gl_account": [
                    {
                        "source_ref": "st-10-01-live",
                        "code": "10.01",
                        "name": "Materials",
                        "chart_identity": CHART_IDENTITY,
                    },
                    {
                        "source_ref": "st-60-01-live",
                        "code": "60.01",
                        "name": "Suppliers",
                        "chart_identity": CHART_IDENTITY,
                    },
                ]
            },
            str(ambiguous_database.id): {
                "gl_account": [
                    {
                        "source_ref": "amb-10-01-a",
                        "code": "10.01",
                        "name": "Materials",
                        "chart_identity": CHART_IDENTITY,
                    },
                    {
                        "source_ref": "amb-10-01-b",
                        "code": "10.01",
                        "name": "Materials duplicate",
                        "chart_identity": CHART_IDENTITY,
                    },
                    {
                        "source_ref": "amb-60-01",
                        "code": "60.01",
                        "name": "Suppliers",
                        "chart_identity": CHART_IDENTITY,
                    },
                ]
            },
        }
    )

    source = _upsert_chart_source(client=admin_client, database_id=str(source_database.id))
    _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="preflight")
    _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="dry_run")
    materialize_job = _create_chart_job(client=admin_client, chart_source_id=source["id"], mode="materialize")
    account_by_code = {
        account.code: account
        for account in PoolMasterGLAccount.objects.filter(tenant=default_tenant, chart_identity=CHART_IDENTITY)
    }
    snapshot_id = materialize_job["snapshot"]["id"]

    upsert_pool_master_data_binding(
        tenant=default_tenant,
        entity_type="gl_account",
        canonical_id=account_by_code["10.01"].canonical_id,
        database=stale_database,
        ib_ref_key="st-10-01-old",
        chart_identity=CHART_IDENTITY,
        sync_status=PoolMasterBindingSyncStatus.RESOLVED,
        fingerprint="stale-old",
        metadata={},
        origin_system="cc",
    )
    upsert_pool_master_data_binding(
        tenant=default_tenant,
        entity_type="gl_account",
        canonical_id=account_by_code["60.01"].canonical_id,
        database=stale_database,
        ib_ref_key="st-60-01-live",
        chart_identity=CHART_IDENTITY,
        sync_status=PoolMasterBindingSyncStatus.RESOLVED,
        fingerprint="stale-good",
        metadata={},
        origin_system="cc",
    )
    upsert_pool_master_data_binding(
        tenant=default_tenant,
        entity_type="gl_account",
        canonical_id=account_by_code["60.01"].canonical_id,
        database=ambiguous_database,
        ib_ref_key="amb-60-01",
        chart_identity=CHART_IDENTITY,
        sync_status=PoolMasterBindingSyncStatus.RESOLVED,
        fingerprint="amb-good",
        metadata={},
        origin_system="cc",
    )

    backfill_job = _create_chart_job(
        client=admin_client,
        chart_source_id=source["id"],
        mode="backfill_bindings",
        database_ids=[str(backfill_database.id), str(stale_database.id), str(ambiguous_database.id)],
    )
    assert backfill_job["snapshot"]["id"] == snapshot_id
    assert backfill_job["counters"]["database_count"] == 3
    assert backfill_job["counters"]["backfilled_count"] == 1
    assert backfill_job["counters"]["stale_count"] == 1
    assert backfill_job["counters"]["ambiguous_count"] == 1

    statuses = {
        row["database_id"]: row
        for row in backfill_job["follower_statuses"]
    }
    assert statuses[str(backfill_database.id)]["verdict"] == "backfilled"
    assert statuses[str(backfill_database.id)]["backfilled_accounts"] == 2
    assert statuses[str(stale_database.id)]["verdict"] == "stale"
    assert statuses[str(stale_database.id)]["stale_bindings"] == 1
    assert str(stale_database.id) in str(statuses[str(stale_database.id)]["bindings_remediation_href"])
    assert account_by_code["10.01"].canonical_id in statuses[str(stale_database.id)]["bindings_remediation_href"]
    assert statuses[str(ambiguous_database.id)]["verdict"] == "ambiguous"
    assert statuses[str(ambiguous_database.id)]["ambiguous_accounts"] == 1

    backfilled_bindings = list(
        PoolMasterDataBinding.objects.filter(
            tenant=default_tenant,
            database=backfill_database,
            entity_type="gl_account",
        ).order_by("canonical_id")
    )
    assert len(backfilled_bindings) == 2
    assert {binding.ib_ref_key for binding in backfilled_bindings} == {"bf-10-01", "bf-60-01"}
    assert all(binding.chart_identity == CHART_IDENTITY for binding in backfilled_bindings)

    stale_binding = PoolMasterDataBinding.objects.get(
        tenant=default_tenant,
        database=stale_database,
        canonical_id=account_by_code["10.01"].canonical_id,
    )
    assert stale_binding.ib_ref_key == "st-10-01-old"

    detail_response = admin_client.get(f"/api/v2/pools/master-data/chart-import/jobs/{backfill_job['id']}/")
    assert detail_response.status_code == 200
    assert len(detail_response.json()["job"]["follower_statuses"]) == 3

    registry_response = admin_client.get("/api/v2/pools/master-data/registry/")
    assert registry_response.status_code == 200
    gl_account_entry = next(
        item for item in registry_response.json()["entries"] if item["entity_type"] == "gl_account"
    )
    assert gl_account_entry["capabilities"]["sync_outbound"] is False
    assert gl_account_entry["capabilities"]["sync_inbound"] is False
    assert gl_account_entry["capabilities"]["outbox_fanout"] is False
