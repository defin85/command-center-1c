from __future__ import annotations

from uuid import uuid4
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncJob,
    PoolMasterDataSyncJobStatus,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
    PoolMasterDataSyncPolicy,
    PoolMasterDataSyncScope,
    PoolMasterParty,
)
from apps.operations.services import EnqueueResult
from apps.runtime_settings.models import RuntimeSetting
from apps.tenancy.models import Tenant, TenantMember


def _assert_problem_details_response(response, *, status_code: int, code: str) -> dict:
    assert response.status_code == status_code
    assert response.headers.get("Content-Type", "").startswith("application/problem+json")
    payload = response.json()
    assert payload.get("code") == code
    return payload


@pytest.fixture
def default_tenant() -> Tenant:
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    return tenant


@pytest.fixture
def user(default_tenant: Tenant) -> User:
    user = User.objects.create_user(username=f"pool-mdm-user-{uuid4().hex[:8]}", password="pass")
    TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=user,
        defaults={"role": TenantMember.ROLE_ADMIN},
    )
    return user


@pytest.fixture
def authenticated_client(user: User, default_tenant: Tenant) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))
    return client


def _create_database(*, tenant: Tenant, name: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="user",
        password="pass",
    )


@pytest.mark.django_db
def test_master_data_parties_upsert_list_get_roundtrip(authenticated_client: APIClient) -> None:
    create_response = authenticated_client.post(
        "/api/v2/pools/master-data/parties/upsert/",
        {
            "canonical_id": "party-001",
            "name": "Party 001",
            "is_counterparty": True,
            "is_our_organization": False,
        },
        format="json",
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    party_id = create_payload["party"]["id"]

    list_response = authenticated_client.get(
        "/api/v2/pools/master-data/parties/?canonical_id=party-001&limit=10&offset=0"
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 1
    assert list_payload["parties"][0]["id"] == party_id

    get_response = authenticated_client.get(f"/api/v2/pools/master-data/parties/{party_id}/")
    assert get_response.status_code == 200
    assert get_response.json()["party"]["canonical_id"] == "party-001"


@pytest.mark.django_db
def test_master_data_parties_fail_when_no_role_is_set(authenticated_client: APIClient) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/master-data/parties/upsert/",
        {
            "canonical_id": "party-invalid-role",
            "name": "Party Invalid Role",
            "is_counterparty": False,
            "is_our_organization": False,
        },
        format="json",
    )
    _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")


@pytest.mark.django_db
def test_master_data_items_upsert_list_get_roundtrip(authenticated_client: APIClient) -> None:
    create_response = authenticated_client.post(
        "/api/v2/pools/master-data/items/upsert/",
        {
            "canonical_id": "item-001",
            "name": "Item 001",
            "sku": "SKU-001",
            "unit": "pcs",
        },
        format="json",
    )
    assert create_response.status_code == 201
    item_id = create_response.json()["item"]["id"]

    list_response = authenticated_client.get("/api/v2/pools/master-data/items/?sku=SKU-001")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

    get_response = authenticated_client.get(f"/api/v2/pools/master-data/items/{item_id}/")
    assert get_response.status_code == 200
    assert get_response.json()["item"]["canonical_id"] == "item-001"


@pytest.mark.django_db
def test_master_data_registry_inspect_returns_shared_capability_contract(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.get("/api/v2/pools/master-data/registry/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "pool_master_data_registry.v1"
    assert payload["count"] == 5
    assert len(payload["entries"]) == 5
    binding_entry = next(item for item in payload["entries"] if item["entity_type"] == "binding")
    assert binding_entry["kind"] == "bootstrap_helper"
    assert binding_entry["capabilities"]["bootstrap_import"] is True
    assert binding_entry["capabilities"]["outbox_fanout"] is False


@pytest.mark.django_db
def test_master_data_party_upsert_creates_outbox_intents_for_tenant_databases(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database_a = _create_database(tenant=default_tenant, name=f"mdm-sync-db-a-{uuid4().hex[:8]}")
    database_b = _create_database(tenant=default_tenant, name=f"mdm-sync-db-b-{uuid4().hex[:8]}")

    response = authenticated_client.post(
        "/api/v2/pools/master-data/parties/upsert/",
        {
            "canonical_id": "party-sync-001",
            "name": "Party Sync 001",
            "is_counterparty": True,
            "is_our_organization": False,
        },
        format="json",
    )
    assert response.status_code == 201

    rows = list(
        PoolMasterDataSyncOutbox.objects.filter(
            tenant=default_tenant,
            entity_type=PoolMasterDataEntityType.PARTY,
        )
    )
    assert len(rows) == 2
    database_ids = {str(row.database_id) for row in rows}
    assert database_ids == {str(database_a.id), str(database_b.id)}
    assert all(row.status == PoolMasterDataSyncOutboxStatus.PENDING for row in rows)
    assert all(row.payload["mutation_kind"] == "party_upsert" for row in rows)


@pytest.mark.django_db
def test_master_data_party_upsert_triggers_sync_job_workflow_when_runtime_enabled(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    django_capture_on_commit_callbacks,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"mdm-sync-job-db-{uuid4().hex[:8]}")
    PoolMasterDataSyncScope.objects.create(
        tenant=default_tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )
    RuntimeSetting.objects.create(key="pools.master_data.sync.enabled", value=True)
    RuntimeSetting.objects.create(key="pools.master_data.sync.outbound.enabled", value=True)
    RuntimeSetting.objects.create(key="pools.master_data.sync.default_policy", value="cc_master")

    def _enqueue(execution_id: str, workflow_config: dict | None = None) -> EnqueueResult:
        return EnqueueResult(
            success=True,
            operation_id=execution_id,
            status="queued",
            error=None,
            error_code=None,
        )

    with patch(
        "apps.intercompany_pools.master_data_sync_workflow_runtime.OperationsService.enqueue_workflow_execution",
        side_effect=_enqueue,
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = authenticated_client.post(
                "/api/v2/pools/master-data/parties/upsert/",
                {
                    "canonical_id": "party-sync-job-001",
                    "name": "Party Sync Job 001",
                    "is_counterparty": True,
                    "is_our_organization": False,
                },
                format="json",
            )
    assert response.status_code == 201

    jobs = list(
        PoolMasterDataSyncJob.objects.filter(
            tenant=default_tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.PARTY,
        )
    )
    assert len(jobs) == 1
    assert jobs[0].status == PoolMasterDataSyncJobStatus.RUNNING
    assert jobs[0].workflow_execution_id is not None
    assert jobs[0].operation_id is not None


@pytest.mark.django_db
def test_master_data_contracts_require_counterparty_owner(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    org_only_party = PoolMasterParty.objects.create(
        tenant=default_tenant,
        canonical_id="party-org-only",
        name="Party Org Only",
        is_our_organization=True,
        is_counterparty=False,
    )

    invalid_owner_response = authenticated_client.post(
        "/api/v2/pools/master-data/contracts/upsert/",
        {
            "canonical_id": "contract-001",
            "name": "Contract 001",
            "owner_counterparty_id": str(org_only_party.id),
        },
        format="json",
    )
    _assert_problem_details_response(
        invalid_owner_response,
        status_code=400,
        code="MASTER_DATA_OWNER_COUNTERPARTY_ROLE_INVALID",
    )


@pytest.mark.django_db
def test_master_data_tax_profiles_validate_vat_range(authenticated_client: APIClient) -> None:
    invalid_response = authenticated_client.post(
        "/api/v2/pools/master-data/tax-profiles/upsert/",
        {
            "canonical_id": "vat-120",
            "vat_rate": "120.00",
            "vat_included": True,
            "vat_code": "VAT120",
        },
        format="json",
    )
    _assert_problem_details_response(invalid_response, status_code=400, code="VALIDATION_ERROR")


@pytest.mark.django_db
def test_master_data_bindings_validate_party_catalog_kind_and_list_filters(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database = _create_database(tenant=default_tenant, name=f"mdm-bindings-db-{uuid4().hex[:8]}")

    invalid_binding_response = authenticated_client.post(
        "/api/v2/pools/master-data/bindings/upsert/",
        {
            "entity_type": "party",
            "canonical_id": "party-001",
            "database_id": str(database.id),
            "ib_ref_key": "ref-party-001",
            "ib_catalog_kind": "",
        },
        format="json",
    )
    _assert_problem_details_response(invalid_binding_response, status_code=400, code="VALIDATION_ERROR")

    create_binding_response = authenticated_client.post(
        "/api/v2/pools/master-data/bindings/upsert/",
        {
            "entity_type": "party",
            "canonical_id": "party-001",
            "database_id": str(database.id),
            "ib_ref_key": "ref-party-001",
            "ib_catalog_kind": "organization",
        },
        format="json",
    )
    assert create_binding_response.status_code == 201
    binding_id = create_binding_response.json()["binding"]["id"]

    list_response = authenticated_client.get("/api/v2/pools/master-data/bindings/?entity_type=party")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    assert list_response.json()["bindings"][0]["id"] == binding_id
