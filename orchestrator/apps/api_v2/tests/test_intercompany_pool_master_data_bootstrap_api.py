from __future__ import annotations

from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Database
from apps.intercompany_pools.master_data_bootstrap_import_feature_flags import (
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY,
)
from apps.intercompany_pools.master_data_bootstrap_import_source_adapter import (
    PoolMasterDataBootstrapSourcePreflightResult,
    configure_pool_master_data_bootstrap_source_callbacks,
    reset_pool_master_data_bootstrap_source_callbacks,
)
from apps.intercompany_pools.models import PoolMasterParty
from apps.runtime_settings.models import RuntimeSetting
from apps.runtime_settings.models import TenantRuntimeSettingOverride
from apps.tenancy.models import Tenant, TenantMember


def _assert_problem_details_response(response, *, status_code: int, code: str) -> dict:
    assert response.status_code == status_code
    assert response.headers.get("Content-Type", "").startswith("application/problem+json")
    payload = response.json()
    assert payload.get("code") == code
    return payload


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
    user = User.objects.create_user(username=f"pool-bootstrap-admin-{uuid4().hex[:8]}", password="pass")
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
def member_user(default_tenant: Tenant) -> User:
    user = User.objects.create_user(username=f"pool-bootstrap-member-{uuid4().hex[:8]}", password="pass")
    TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=user,
        defaults={"role": TenantMember.ROLE_MEMBER},
    )
    return user


@pytest.fixture
def admin_client(admin_user: User, default_tenant: Tenant) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=admin_user)
    client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))
    return client


@pytest.fixture
def member_client(member_user: User, default_tenant: Tenant) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=member_user)
    client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))
    return client


@pytest.fixture(autouse=True)
def bootstrap_feature_flag_enabled(default_tenant: Tenant) -> None:
    RuntimeSetting.objects.update_or_create(
        key=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY,
        defaults={"value": True},
    )
    TenantRuntimeSettingOverride.objects.update_or_create(
        tenant=default_tenant,
        key=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY,
        defaults={
            "value": True,
            "status": TenantRuntimeSettingOverride.STATUS_PUBLISHED,
        },
    )


def _create_database(*, tenant: Tenant, name: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        odata_url="http://localhost/odata/bootstrap.odata",
        username="user",
        password="pass",
    )


def _configure_source_callbacks(
    *,
    rows_by_entity: dict[str, list[dict]],
) -> None:
    def _preflight(*, entity_scope: list[str], **_kwargs) -> PoolMasterDataBootstrapSourcePreflightResult:
        return PoolMasterDataBootstrapSourcePreflightResult(
            ok=True,
            source_kind="ib_odata",
            coverage={entity: True for entity in entity_scope},
            credential_strategy="service",
            errors=[],
            diagnostics={"source": "test"},
        )

    def _fetch_rows(*, entity_type: str, **_kwargs) -> list[dict]:
        return list(rows_by_entity.get(entity_type, []))

    configure_pool_master_data_bootstrap_source_callbacks(
        preflight=_preflight,
        fetch_rows=_fetch_rows,
    )


@pytest.mark.django_db
def test_bootstrap_preflight_requires_tenant_admin_or_staff(
    admin_client: APIClient,
    member_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"pool-bootstrap-preflight-{uuid4().hex[:8]}")
    _configure_source_callbacks(rows_by_entity={})

    ok_response = admin_client.post(
        "/api/v2/pools/master-data/bootstrap-import/preflight/",
        {
            "database_id": str(database.id),
            "entity_scope": ["party", "item"],
        },
        format="json",
    )
    assert ok_response.status_code == 200
    assert ok_response.json()["preflight"]["ok"] is True

    forbidden_response = member_client.post(
        "/api/v2/pools/master-data/bootstrap-import/preflight/",
        {
            "database_id": str(database.id),
            "entity_scope": ["party"],
        },
        format="json",
    )
    _assert_problem_details_response(forbidden_response, status_code=403, code="FORBIDDEN")


@pytest.mark.django_db
def test_bootstrap_jobs_dry_run_execute_list_and_get(
    admin_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"pool-bootstrap-jobs-{uuid4().hex[:8]}")
    _configure_source_callbacks(
        rows_by_entity={
            "party": [
                {
                    "canonical_id": "party-001",
                    "name": "Party 001",
                    "is_counterparty": True,
                }
            ],
            "item": [
                {
                    "canonical_id": "item-001",
                    "name": "Item 001",
                    "sku": "SKU-001",
                }
            ],
        }
    )

    dry_run_response = admin_client.post(
        "/api/v2/pools/master-data/bootstrap-import/jobs/",
        {
            "database_id": str(database.id),
            "entity_scope": ["party", "item"],
            "mode": "dry_run",
        },
        format="json",
    )
    assert dry_run_response.status_code == 201
    dry_run_payload = dry_run_response.json()["job"]
    assert dry_run_payload["status"] == "execute_pending"
    assert dry_run_payload["dry_run_summary"]["rows_total"] == 2

    execute_response = admin_client.post(
        "/api/v2/pools/master-data/bootstrap-import/jobs/",
        {
            "database_id": str(database.id),
            "entity_scope": ["party", "item"],
            "mode": "execute",
        },
        format="json",
    )
    assert execute_response.status_code == 201
    execute_job = execute_response.json()["job"]
    assert execute_job["status"] == "finalized"

    list_response = admin_client.get("/api/v2/pools/master-data/bootstrap-import/jobs/?limit=20&offset=0")
    assert list_response.status_code == 200
    assert list_response.json()["count"] >= 2

    get_response = admin_client.get(f"/api/v2/pools/master-data/bootstrap-import/jobs/{execute_job['id']}/")
    assert get_response.status_code == 200
    detail_payload = get_response.json()["job"]
    assert detail_payload["status"] == "finalized"
    assert detail_payload["report"]["created_count"] >= 2
    assert detail_payload["chunks"]
    assert PoolMasterParty.objects.filter(tenant=default_tenant, canonical_id="party-001").exists()


@pytest.mark.django_db
def test_bootstrap_execute_marks_inbound_origin_and_keeps_partial_diagnostics(
    admin_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"pool-bootstrap-origin-{uuid4().hex[:8]}")
    valid_party_id = f"party-origin-{uuid4().hex[:8]}"
    _configure_source_callbacks(
        rows_by_entity={
            "party": [
                {
                    "canonical_id": valid_party_id,
                    "name": "Inbound Party",
                    "metadata": {"source": "ib"},
                },
                {
                    "canonical_id": f"party-origin-invalid-{uuid4().hex[:8]}",
                },
            ]
        }
    )

    execute_response = admin_client.post(
        "/api/v2/pools/master-data/bootstrap-import/jobs/",
        {
            "database_id": str(database.id),
            "entity_scope": ["party"],
            "mode": "execute",
        },
        format="json",
    )
    assert execute_response.status_code == 201
    job_id = execute_response.json()["job"]["id"]

    detail_response = admin_client.get(f"/api/v2/pools/master-data/bootstrap-import/jobs/{job_id}/")
    assert detail_response.status_code == 200
    payload = detail_response.json()["job"]

    assert payload["report"]["created_count"] >= 1
    assert payload["report"]["failed_count"] >= 1
    diagnostics = payload["report"]["diagnostics"]
    errors = diagnostics.get("errors", []) if isinstance(diagnostics, dict) else []
    assert any(str(item.get("code")) == "BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD" for item in errors)

    created_party = PoolMasterParty.objects.get(tenant=default_tenant, canonical_id=valid_party_id)
    metadata = created_party.metadata if isinstance(created_party.metadata, dict) else {}
    sync_origin = metadata.get("sync_origin")
    assert isinstance(sync_origin, dict)
    assert sync_origin.get("origin_system") == "ib"
    assert str(sync_origin.get("origin_event_id", "")).startswith("bootstrap:")
    bootstrap_meta = metadata.get("bootstrap_import")
    assert isinstance(bootstrap_meta, dict)
    assert str(bootstrap_meta.get("job_id")) == str(job_id)


@pytest.mark.django_db
def test_bootstrap_retry_failed_chunks_keeps_idempotent_effects(
    admin_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"pool-bootstrap-retry-{uuid4().hex[:8]}")
    party_canonical_id = f"party-retry-{uuid4().hex[:8]}"
    rows_by_entity = {
        "party": [
            {
                "canonical_id": party_canonical_id,
            }
        ]
    }
    _configure_source_callbacks(rows_by_entity=rows_by_entity)

    execute_response = admin_client.post(
        "/api/v2/pools/master-data/bootstrap-import/jobs/",
        {
            "database_id": str(database.id),
            "entity_scope": ["party"],
            "mode": "execute",
        },
        format="json",
    )
    assert execute_response.status_code == 201
    job_id = execute_response.json()["job"]["id"]

    first_detail = admin_client.get(f"/api/v2/pools/master-data/bootstrap-import/jobs/{job_id}/")
    assert first_detail.status_code == 200
    assert first_detail.json()["job"]["report"]["failed_count"] >= 1
    assert PoolMasterParty.objects.filter(tenant=default_tenant, canonical_id=party_canonical_id).count() == 0

    retry_response = admin_client.post(
        f"/api/v2/pools/master-data/bootstrap-import/jobs/{job_id}/retry-failed-chunks/",
        {},
        format="json",
    )
    assert retry_response.status_code == 200
    assert retry_response.json()["job"]["status"] == "finalized"
    assert retry_response.json()["job"]["chunks"][0]["attempt_count"] == 2
    assert PoolMasterParty.objects.filter(tenant=default_tenant, canonical_id=party_canonical_id).count() == 0

    second_retry_response = admin_client.post(
        f"/api/v2/pools/master-data/bootstrap-import/jobs/{job_id}/retry-failed-chunks/",
        {},
        format="json",
    )
    assert second_retry_response.status_code == 200
    assert second_retry_response.json()["job"]["chunks"][0]["attempt_count"] == 3
    assert PoolMasterParty.objects.filter(tenant=default_tenant, canonical_id=party_canonical_id).count() == 0


@pytest.mark.django_db
def test_bootstrap_cancel_job_in_execute_pending_state(
    admin_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"pool-bootstrap-cancel-{uuid4().hex[:8]}")
    _configure_source_callbacks(rows_by_entity={})

    dry_run_response = admin_client.post(
        "/api/v2/pools/master-data/bootstrap-import/jobs/",
        {
            "database_id": str(database.id),
            "entity_scope": ["party"],
            "mode": "dry_run",
        },
        format="json",
    )
    assert dry_run_response.status_code == 201
    job_id = dry_run_response.json()["job"]["id"]

    cancel_response = admin_client.post(
        f"/api/v2/pools/master-data/bootstrap-import/jobs/{job_id}/cancel/",
        {},
        format="json",
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["job"]["status"] == "canceled"


@pytest.mark.django_db
def test_bootstrap_mutating_actions_require_tenant_admin_or_staff(
    admin_client: APIClient,
    member_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"pool-bootstrap-rbac-{uuid4().hex[:8]}")
    _configure_source_callbacks(
        rows_by_entity={
            "party": [
                {
                    "canonical_id": "party-rbac-001",
                    "name": "Party RBAC 001",
                    "is_counterparty": True,
                }
            ]
        }
    )

    forbidden_create = member_client.post(
        "/api/v2/pools/master-data/bootstrap-import/jobs/",
        {
            "database_id": str(database.id),
            "entity_scope": ["party"],
            "mode": "dry_run",
        },
        format="json",
    )
    _assert_problem_details_response(forbidden_create, status_code=403, code="FORBIDDEN")

    dry_run_response = admin_client.post(
        "/api/v2/pools/master-data/bootstrap-import/jobs/",
        {
            "database_id": str(database.id),
            "entity_scope": ["party"],
            "mode": "dry_run",
        },
        format="json",
    )
    assert dry_run_response.status_code == 201
    job_id = dry_run_response.json()["job"]["id"]

    forbidden_cancel = member_client.post(
        f"/api/v2/pools/master-data/bootstrap-import/jobs/{job_id}/cancel/",
        {},
        format="json",
    )
    _assert_problem_details_response(forbidden_cancel, status_code=403, code="FORBIDDEN")

    forbidden_retry = member_client.post(
        f"/api/v2/pools/master-data/bootstrap-import/jobs/{job_id}/retry-failed-chunks/",
        {},
        format="json",
    )
    _assert_problem_details_response(forbidden_retry, status_code=403, code="FORBIDDEN")
