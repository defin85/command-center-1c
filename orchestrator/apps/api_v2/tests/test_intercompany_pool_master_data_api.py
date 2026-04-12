from __future__ import annotations

from uuid import uuid4
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Database
from apps.intercompany_pools.master_data_dedupe import ingest_pool_master_data_source_record
from apps.intercompany_pools.models import (
    PoolMasterDataBinding,
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


def _create_pending_dedupe_review(*, tenant: Tenant) -> tuple[Database, Database, str]:
    database_a = _create_database(tenant=tenant, name=f"mdm-dedupe-db-a-{uuid4().hex[:8]}")
    database_b = _create_database(tenant=tenant, name=f"mdm-dedupe-db-b-{uuid4().hex[:8]}")
    ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.PARTY,
        source_database=database_a,
        source_ref="party-a",
        source_canonical_id="party-a",
        canonical_payload={
            "name": "ООО Спорная",
            "full_name": "ООО Спорная",
            "inn": "7703003003",
            "kpp": "770301001",
            "is_counterparty": True,
            "is_our_organization": False,
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-a",
        origin_event_id="evt-party-a",
    )
    blocked = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.PARTY,
        source_database=database_b,
        source_ref="party-b",
        source_canonical_id="party-b",
        canonical_payload={
            "name": "ООО Спорная Компания",
            "full_name": "ООО Спорная Компания",
            "inn": "7703003003",
            "kpp": "770301001",
            "is_counterparty": True,
            "is_our_organization": False,
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-b",
        origin_event_id="evt-party-b",
    )
    return database_a, database_b, str(blocked.review_item.id)


def _create_pending_gl_account_dedupe_review(*, tenant: Tenant) -> tuple[Database, Database, str]:
    database_a = _create_database(tenant=tenant, name=f"mdm-dedupe-gl-db-a-{uuid4().hex[:8]}")
    database_b = _create_database(tenant=tenant, name=f"mdm-dedupe-gl-db-b-{uuid4().hex[:8]}")
    ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
        source_database=database_a,
        source_ref="gl-a",
        source_canonical_id="gl-a",
        canonical_payload={
            "code": "10.01",
            "name": "Материалы",
            "chart_identity": "ChartOfAccounts_Main",
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-gl-a",
        origin_event_id="evt-gl-a",
    )
    blocked = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
        source_database=database_b,
        source_ref="gl-b",
        source_canonical_id="gl-b",
        canonical_payload={
            "code": "10.01",
            "name": "Материалы Основные",
            "chart_identity": "ChartOfAccounts_Main",
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-gl-b",
        origin_event_id="evt-gl-b",
    )
    return database_a, database_b, str(blocked.review_item.id)


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
    assert payload["count"] == 7
    assert len(payload["entries"]) == 7
    binding_entry = next(item for item in payload["entries"] if item["entity_type"] == "binding")
    assert binding_entry["kind"] == "bootstrap_helper"
    assert binding_entry["capabilities"]["bootstrap_import"] is True
    assert binding_entry["capabilities"]["outbox_fanout"] is False
    gl_account_entry = next(item for item in payload["entries"] if item["entity_type"] == "gl_account")
    assert gl_account_entry["binding_scope_fields"] == ["canonical_id", "database_id", "chart_identity"]
    gl_account_set_entry = next(item for item in payload["entries"] if item["entity_type"] == "gl_account_set")
    assert gl_account_set_entry["capabilities"]["direct_binding"] is False


@pytest.mark.django_db
def test_master_data_dedupe_review_list_get_and_action_roundtrip(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    _, _, review_item_id = _create_pending_dedupe_review(tenant=default_tenant)

    list_response = authenticated_client.get("/api/v2/pools/master-data/dedupe-review/?status=pending_review")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 1
    assert list_payload["items"][0]["id"] == review_item_id
    assert list_payload["items"][0]["status"] == "pending_review"

    get_response = authenticated_client.get(f"/api/v2/pools/master-data/dedupe-review/{review_item_id}/")
    assert get_response.status_code == 200
    assert get_response.json()["review_item"]["id"] == review_item_id

    action_response = authenticated_client.post(
        f"/api/v2/pools/master-data/dedupe-review/{review_item_id}/actions/",
        {
            "action": "choose_survivor",
            "note": "operator approved survivor",
        },
        format="json",
    )
    assert action_response.status_code == 200
    action_payload = action_response.json()
    assert action_payload["review_item"]["status"] == "resolved_manual"
    assert action_payload["review_item"]["cluster"]["status"] == "resolved_manual"

    second_action_response = authenticated_client.post(
        f"/api/v2/pools/master-data/dedupe-review/{review_item_id}/actions/",
        {
            "action": "mark_distinct",
            "note": "should fail because item is already resolved",
        },
        format="json",
    )
    _assert_problem_details_response(
        second_action_response,
        status_code=400,
        code="MASTER_DATA_DEDUPE_REVIEW_NOT_PENDING",
    )


@pytest.mark.django_db
def test_master_data_dedupe_review_detail_includes_affected_bindings_and_runtime_blockers(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    database_a, _, review_item_id = _create_pending_dedupe_review(tenant=default_tenant)
    review_item = authenticated_client.get(
        f"/api/v2/pools/master-data/dedupe-review/{review_item_id}/"
    ).json()["review_item"]
    PoolMasterDataBinding.objects.create(
        tenant=default_tenant,
        entity_type=PoolMasterDataEntityType.PARTY,
        canonical_id=review_item["cluster"]["canonical_id"],
        database=database_a,
        ib_ref_key="ref-party-001",
        ib_catalog_kind="counterparty",
    )

    response = authenticated_client.get(f"/api/v2/pools/master-data/dedupe-review/{review_item_id}/")
    assert response.status_code == 200
    payload = response.json()["review_item"]
    assert payload["affected_bindings"][0]["database_id"] == str(database_a.id)
    assert payload["affected_bindings"][0]["ib_ref_key"] == "ref-party-001"
    blocker_codes = {item["code"] for item in payload["runtime_blockers"]}
    assert blocker_codes == {"publication", "manual_sync_launch", "outbound_outbox"}


@pytest.mark.django_db
def test_master_data_dedupe_review_detail_omits_runtime_blockers_without_runtime_capability(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    _, _, review_item_id = _create_pending_gl_account_dedupe_review(tenant=default_tenant)

    response = authenticated_client.get(f"/api/v2/pools/master-data/dedupe-review/{review_item_id}/")
    assert response.status_code == 200
    payload = response.json()["review_item"]
    blocker_codes = {item["code"] for item in payload["runtime_blockers"]}
    assert blocker_codes == {"publication"}


@pytest.mark.django_db
def test_master_data_dedupe_review_action_validates_unknown_action(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    _, _, review_item_id = _create_pending_dedupe_review(tenant=default_tenant)

    response = authenticated_client.post(
        f"/api/v2/pools/master-data/dedupe-review/{review_item_id}/actions/",
        {"action": "bad_action"},
        format="json",
    )

    _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")


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


@pytest.mark.django_db
def test_master_data_gl_accounts_upsert_list_get_roundtrip(authenticated_client: APIClient) -> None:
    create_response = authenticated_client.post(
        "/api/v2/pools/master-data/gl-accounts/upsert/",
        {
            "canonical_id": "gl-account-001",
            "code": "10.01",
            "name": "Основной счет",
            "chart_identity": "ChartOfAccounts_Main",
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
        },
        format="json",
    )
    assert create_response.status_code == 201
    gl_account_id = create_response.json()["gl_account"]["id"]

    list_response = authenticated_client.get(
        "/api/v2/pools/master-data/gl-accounts/?code=10.01&chart_identity=ChartOfAccounts_Main"
    )
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

    get_response = authenticated_client.get(f"/api/v2/pools/master-data/gl-accounts/{gl_account_id}/")
    assert get_response.status_code == 200
    assert get_response.json()["gl_account"]["canonical_id"] == "gl-account-001"


@pytest.mark.django_db
def test_master_data_gl_account_sets_upsert_publish_and_get_detail(authenticated_client: APIClient) -> None:
    first_gl_account = authenticated_client.post(
        "/api/v2/pools/master-data/gl-accounts/upsert/",
        {
            "canonical_id": "gl-account-100",
            "code": "10.01",
            "name": "Основной счет",
            "chart_identity": "ChartOfAccounts_Main",
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
        },
        format="json",
    )
    second_gl_account = authenticated_client.post(
        "/api/v2/pools/master-data/gl-accounts/upsert/",
        {
            "canonical_id": "gl-account-200",
            "code": "60.01",
            "name": "Расчеты с поставщиками",
            "chart_identity": "ChartOfAccounts_Main",
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
        },
        format="json",
    )
    assert first_gl_account.status_code == 201
    assert second_gl_account.status_code == 201

    upsert_response = authenticated_client.post(
        "/api/v2/pools/master-data/gl-account-sets/upsert/",
        {
            "canonical_id": "gl-set-001",
            "name": "Основной набор счетов",
            "description": "Черновик для публикации",
            "chart_identity": "ChartOfAccounts_Main",
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
            "members": [
                {"canonical_id": "gl-account-100"},
                {"canonical_id": "gl-account-200"},
            ],
        },
        format="json",
    )
    assert upsert_response.status_code == 201
    payload = upsert_response.json()["gl_account_set"]
    gl_account_set_id = payload["gl_account_set_id"]
    assert payload["draft_members_count"] == 2
    assert payload["published_revision"] is None

    publish_response = authenticated_client.post(
        f"/api/v2/pools/master-data/gl-account-sets/{gl_account_set_id}/publish/",
        {},
        format="json",
    )
    assert publish_response.status_code == 200
    published = publish_response.json()["gl_account_set"]
    assert published["published_revision"]["revision_number"] == 1
    assert len(published["published_revision"]["members"]) == 2

    detail_response = authenticated_client.get(
        f"/api/v2/pools/master-data/gl-account-sets/{gl_account_set_id}/"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()["gl_account_set"]
    assert detail["published_revision_number"] == 1
    assert [item["canonical_id"] for item in detail["draft_members"]] == [
        "gl-account-100",
        "gl-account-200",
    ]


@pytest.mark.django_db
def test_master_data_gl_account_set_upsert_updates_draft_without_mutating_published_revision(
    authenticated_client: APIClient,
) -> None:
    for canonical_id, code, name in (
        ("gl-account-100", "10.01", "Основной счет"),
        ("gl-account-200", "60.01", "Расчеты с поставщиками"),
        ("gl-account-300", "62.01", "Расчеты с покупателями"),
    ):
        response = authenticated_client.post(
            "/api/v2/pools/master-data/gl-accounts/upsert/",
            {
                "canonical_id": canonical_id,
                "code": code,
                "name": name,
                "chart_identity": "ChartOfAccounts_Main",
                "config_name": "Accounting Enterprise",
                "config_version": "3.0.1",
            },
            format="json",
        )
        assert response.status_code == 201

    create_response = authenticated_client.post(
        "/api/v2/pools/master-data/gl-account-sets/upsert/",
        {
            "canonical_id": "gl-set-immutable-001",
            "name": "Набор счетов v1",
            "description": "Черновик до первой публикации",
            "chart_identity": "ChartOfAccounts_Main",
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
            "members": [
                {"canonical_id": "gl-account-100"},
                {"canonical_id": "gl-account-200"},
            ],
        },
        format="json",
    )
    assert create_response.status_code == 201
    gl_account_set_id = create_response.json()["gl_account_set"]["gl_account_set_id"]

    publish_response = authenticated_client.post(
        f"/api/v2/pools/master-data/gl-account-sets/{gl_account_set_id}/publish/",
        {},
        format="json",
    )
    assert publish_response.status_code == 200
    published_revision = publish_response.json()["gl_account_set"]["published_revision"]
    assert published_revision is not None
    published_revision_id = published_revision["gl_account_set_revision_id"]
    assert published_revision["revision_number"] == 1
    assert published_revision["name"] == "Набор счетов v1"
    assert published_revision["description"] == "Черновик до первой публикации"
    assert [item["canonical_id"] for item in published_revision["members"]] == [
        "gl-account-100",
        "gl-account-200",
    ]

    update_response = authenticated_client.post(
        "/api/v2/pools/master-data/gl-account-sets/upsert/",
        {
            "gl_account_set_id": gl_account_set_id,
            "canonical_id": "gl-set-immutable-001",
            "name": "Набор счетов v2 draft",
            "description": "Черновик после публикации",
            "chart_identity": "ChartOfAccounts_Main",
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
            "members": [
                {"canonical_id": "gl-account-100"},
                {"canonical_id": "gl-account-300"},
            ],
        },
        format="json",
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["created"] is False
    updated = update_payload["gl_account_set"]
    assert updated["name"] == "Набор счетов v2 draft"
    assert updated["description"] == "Черновик после публикации"
    assert updated["draft_members_count"] == 2
    assert [item["canonical_id"] for item in updated["draft_members"]] == [
        "gl-account-100",
        "gl-account-300",
    ]
    assert updated["published_revision_number"] == 1
    assert updated["published_revision_id"] == published_revision_id
    assert updated["published_revision"] is not None
    assert updated["published_revision"]["gl_account_set_revision_id"] == published_revision_id
    assert updated["published_revision"]["revision_number"] == 1
    assert updated["published_revision"]["name"] == "Набор счетов v1"
    assert updated["published_revision"]["description"] == "Черновик до первой публикации"
    assert [item["canonical_id"] for item in updated["published_revision"]["members"]] == [
        "gl-account-100",
        "gl-account-200",
    ]
    assert len(updated["revisions"]) == 1
    assert updated["revisions"][0]["gl_account_set_revision_id"] == published_revision_id

    detail_response = authenticated_client.get(
        f"/api/v2/pools/master-data/gl-account-sets/{gl_account_set_id}/"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()["gl_account_set"]
    assert detail["name"] == "Набор счетов v2 draft"
    assert detail["description"] == "Черновик после публикации"
    assert [item["canonical_id"] for item in detail["draft_members"]] == [
        "gl-account-100",
        "gl-account-300",
    ]
    assert detail["published_revision_number"] == 1
    assert detail["published_revision_id"] == published_revision_id
    assert detail["published_revision"] is not None
    assert detail["published_revision"]["gl_account_set_revision_id"] == published_revision_id
    assert detail["published_revision"]["revision_number"] == 1
    assert detail["published_revision"]["name"] == "Набор счетов v1"
    assert detail["published_revision"]["description"] == "Черновик до первой публикации"
    assert [item["canonical_id"] for item in detail["published_revision"]["members"]] == [
        "gl-account-100",
        "gl-account-200",
    ]
    assert len(detail["revisions"]) == 1
    assert detail["revisions"][0]["gl_account_set_revision_id"] == published_revision_id
