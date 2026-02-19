from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.models import (
    Organization,
    OrganizationStatus,
    OrganizationPool,
    PoolEdgeVersion,
    PoolNodeVersion,
    PoolPublicationAttempt,
    PoolPublicationAttemptStatus,
    PoolRun,
    PoolRunAuditEvent,
    PoolRunCommandLog,
    PoolRunCommandOutbox,
    PoolRunCommandType,
    PoolRunDirection,
    PoolRunMode,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
)
from apps.operations.services import EnqueueResult
from apps.runtime_settings.models import RuntimeSetting
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant, TenantMember


def _create_validated_run(*, tenant: Tenant, pool: OrganizationPool) -> PoolRun:
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save()
    run.confirm_publication()
    run.save(update_fields=["publication_confirmed_at", "publication_confirmed_by", "updated_at"])
    return run


def _attach_workflow_execution_to_run(
    *,
    run: PoolRun,
    status: str,
    input_context: dict[str, object] | None = None,
    link_run: bool = True,
) -> WorkflowExecution:
    template = WorkflowTemplate.objects.create(
        name=f"pool-run-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node 1",
                    "type": "operation",
                    "template_id": "tpl-test",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    execution = template.create_execution(
        input_context or {"pool_run_id": str(run.id)},
        tenant=run.tenant,
        execution_consumer="pools",
    )
    update_fields = ["workflow_execution_id", "workflow_status", "execution_backend", "workflow_template_name", "updated_at"]
    if status == WorkflowExecution.STATUS_RUNNING:
        execution.start()
        execution.save(update_fields=["status", "started_at"])
    elif status == WorkflowExecution.STATUS_COMPLETED:
        execution.start()
        execution.complete({"ok": True})
        execution.save(update_fields=["status", "started_at", "completed_at", "final_result"])
    elif status == WorkflowExecution.STATUS_FAILED:
        execution.start()
        execution.fail("failed")
        execution.save(
            update_fields=[
                "status",
                "started_at",
                "completed_at",
                "error_message",
                "error_node_id",
            ]
        )
    elif status == WorkflowExecution.STATUS_CANCELLED:
        execution.cancel()
        execution.save(update_fields=["status", "completed_at"])

    if link_run:
        run.workflow_execution_id = execution.id
        run.workflow_status = execution.status
        run.execution_backend = "workflow_core"
        run.workflow_template_name = template.name
        run.save(update_fields=update_fields)
    return execution


def _create_database(*, tenant: Tenant, name: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="admin",
        password="secret",
    )


def _attach_pool_target_database(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    period_start: date,
) -> Database:
    database = _create_database(tenant=tenant, name=f"pool-api-target-{uuid4().hex[:8]}")
    organization = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Org {uuid4().hex[:6]}",
        inn=f"73{uuid4().hex[:10]}",
        status=OrganizationStatus.ACTIVE,
    )
    PoolNodeVersion.objects.create(
        pool=pool,
        organization=organization,
        effective_from=period_start,
        is_root=True,
    )
    return database


def _create_run_with_execution_state(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    mode: str = PoolRunMode.SAFE,
    workflow_status: str = WorkflowExecution.STATUS_COMPLETED,
    approval_required: bool = True,
    approval_state: str = "awaiting_approval",
    approved_at: str | None = None,
    publication_step_state: str = "not_enqueued",
    terminal_reason: str | None = None,
) -> PoolRun:
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=mode,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])

    input_context: dict[str, object] = {
        "pool_run_id": str(run.id),
        "approval_required": approval_required,
        "approval_state": approval_state,
        "approved_at": approved_at,
        "publication_step_state": publication_step_state,
    }
    if terminal_reason:
        input_context["terminal_reason"] = terminal_reason

    _attach_workflow_execution_to_run(
        run=run,
        status=workflow_status,
        input_context=input_context,
    )
    return run


def _assert_safe_command_conflict_payload(
    payload: dict[str, object],
    *,
    run_id: UUID,
    expected_code: str,
    expected_reason: str,
    expected_retryable: bool,
) -> None:
    assert payload["success"] is False
    assert payload["error_code"] == expected_code
    assert isinstance(payload["error_message"], str)
    assert payload["error_message"]
    assert payload["conflict_reason"] == expected_reason
    assert payload["retryable"] is expected_retryable
    assert payload["run_id"] == str(run_id)


def _assert_problem_details_response(response, *, status_code: int, code: str) -> dict[str, object]:
    assert response.status_code == status_code
    assert response["Content-Type"].startswith("application/problem+json")
    payload = response.json()
    assert payload["status"] == status_code
    assert payload["code"] == code
    assert payload["type"] == "about:blank"
    assert isinstance(payload["title"], str) and payload["title"]
    assert isinstance(payload["detail"], str) and payload["detail"]
    return payload


def _build_document_policy_payload() -> dict[str, object]:
    return {
        "version": "document_policy.v1",
        "chains": [
            {
                "chain_id": "sale_chain",
                "documents": [
                    {
                        "document_id": "sale",
                        "entity_name": "Document_Sales",
                        "document_role": "sale",
                        "field_mapping": {"Amount": "allocation.amount"},
                        "table_parts_mapping": {},
                        "link_rules": {},
                        "invoice_mode": "required",
                    },
                    {
                        "document_id": "invoice",
                        "entity_name": "Document_Invoice",
                        "document_role": "invoice",
                        "field_mapping": {"BaseDocument": "sale.ref"},
                        "table_parts_mapping": {},
                        "link_rules": {"depends_on": "sale"},
                        "link_to": "sale",
                    },
                ],
            }
        ],
    }


@pytest.fixture
def default_tenant() -> Tenant:
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    return tenant


@pytest.fixture
def user(default_tenant: Tenant) -> User:
    user = User.objects.create_user(username="pool-api-user", password="pass")
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


@pytest.fixture
def pool(default_tenant: Tenant) -> OrganizationPool:
    return OrganizationPool.objects.create(
        tenant=default_tenant,
        code="pool-api",
        name="Pool API",
    )


@pytest.mark.django_db
def test_pool_run_endpoints_require_authentication(pool: OrganizationPool) -> None:
    client = APIClient()
    create_response = client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": []},
        },
        format="json",
    )
    assert create_response.status_code in [401, 403]


@pytest.mark.django_db
def test_list_organizations_endpoint_filters_by_status_and_query(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    db = _create_database(tenant=default_tenant, name="pool-org-list-db")
    Organization.objects.create(
        tenant=default_tenant,
        database=db,
        name="Alpha Org",
        full_name="Alpha Organization",
        inn="710000000001",
        status=OrganizationStatus.ACTIVE,
    )
    Organization.objects.create(
        tenant=default_tenant,
        name="Beta Org",
        full_name="Beta Organization",
        inn="710000000002",
        status=OrganizationStatus.INACTIVE,
    )

    response = authenticated_client.get("/api/v2/pools/organizations/?status=active&query=alpha")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["organizations"][0]["inn"] == "710000000001"
    assert payload["organizations"][0]["database_id"] == str(db.id)


@pytest.mark.django_db
def test_get_organization_returns_pool_bindings(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    organization = Organization.objects.create(
        tenant=default_tenant,
        name="Binding Org",
        inn="720000000001",
    )
    PoolNodeVersion.objects.create(
        pool=pool,
        organization=organization,
        effective_from=date(2026, 1, 1),
        is_root=False,
    )

    response = authenticated_client.get(f"/api/v2/pools/organizations/{organization.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["organization"]["id"] == str(organization.id)
    assert payload["organization"]["inn"] == "720000000001"
    assert len(payload["pool_bindings"]) == 1
    assert payload["pool_bindings"][0]["pool_id"] == str(pool.id)
    assert payload["pool_bindings"][0]["pool_code"] == pool.code


@pytest.mark.django_db
def test_upsert_organization_creates_updates_and_enforces_database_uniqueness(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    db1 = _create_database(tenant=default_tenant, name="pool-org-upsert-db-1")
    db2 = _create_database(tenant=default_tenant, name="pool-org-upsert-db-2")

    create_response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "inn": "730000000001",
            "name": "Create Org",
            "status": "active",
            "database_id": str(db1.id),
        },
        format="json",
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["created"] is True
    created_id = create_payload["organization"]["id"]

    update_response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "organization_id": created_id,
            "inn": "730000000001",
            "name": "Updated Org",
            "status": "inactive",
            "database_id": str(db1.id),
        },
        format="json",
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["created"] is False
    assert update_payload["organization"]["name"] == "Updated Org"
    assert update_payload["organization"]["status"] == "inactive"

    Organization.objects.create(
        tenant=default_tenant,
        database=db2,
        name="DB2 owner",
        inn="730000000002",
    )
    conflict_response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "inn": "730000000003",
            "name": "Conflict Org",
            "status": "active",
            "database_id": str(db2.id),
        },
        format="json",
    )
    _assert_problem_details_response(
        conflict_response,
        status_code=400,
        code="DATABASE_ALREADY_LINKED",
    )


@pytest.mark.django_db
def test_upsert_organization_validation_error_returns_problem_details_with_field_errors(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/organizations/upsert/",
        {
            "name": "Missing INN",
        },
        format="json",
    )
    payload = _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")
    assert isinstance(payload.get("errors"), dict)
    assert "inn" in payload["errors"]


@pytest.mark.django_db
def test_sync_organizations_catalog_endpoint_returns_stats(
    authenticated_client: APIClient,
) -> None:
    create_response = authenticated_client.post(
        "/api/v2/pools/organizations/sync/",
        {
            "rows": [
                {"inn": "740000000001", "name": "Sync Org A"},
                {"inn": "740000000002", "name": "Sync Org B", "status": "inactive"},
            ]
        },
        format="json",
    )
    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["stats"] == {"created": 2, "updated": 0, "skipped": 0}
    assert create_payload["total_rows"] == 2

    update_response = authenticated_client.post(
        "/api/v2/pools/organizations/sync/",
        {
            "rows": [
                {"inn": "740000000001", "name": "Sync Org A Updated"},
                {"inn": "740000000002", "name": "Sync Org B", "status": "inactive"},
            ]
        },
        format="json",
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["stats"] == {"created": 0, "updated": 1, "skipped": 1}


@pytest.mark.django_db
def test_upsert_pool_metadata_creates_updates_and_enforces_tenant_boundary(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    create_response = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "code": "pool-meta",
            "name": "Pool Metadata",
            "description": "Initial pool metadata",
            "is_active": True,
            "metadata": {"domain": "intercompany"},
        },
        format="json",
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["created"] is True
    pool_id = create_payload["pool"]["id"]

    update_response = authenticated_client.post(
        "/api/v2/pools/upsert/",
        {
            "pool_id": pool_id,
            "code": "pool-meta",
            "name": "Pool Metadata Updated",
            "description": "Updated pool metadata",
            "is_active": False,
            "metadata": {"domain": "intercompany", "version": 2},
        },
        format="json",
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["created"] is False
    assert update_payload["pool"]["name"] == "Pool Metadata Updated"
    assert update_payload["pool"]["description"] == "Updated pool metadata"
    assert update_payload["pool"]["is_active"] is False

    pools_response = authenticated_client.get("/api/v2/pools/")
    assert pools_response.status_code == 200
    pools_payload = pools_response.json()
    assert any(
        item["id"] == pool_id
        and item["description"] == "Updated pool metadata"
        for item in pools_payload["pools"]
    )

    another_tenant = Tenant.objects.create(slug="pool-meta-other", name="Pool Meta Other")
    another_user = User.objects.create_user(username="pool-meta-other-user", password="pass")
    TenantMember.objects.create(
        tenant=another_tenant,
        user=another_user,
        role=TenantMember.ROLE_ADMIN,
    )
    another_client = APIClient()
    another_client.force_authenticate(user=another_user)
    another_client.credentials(HTTP_X_CC1C_TENANT_ID=str(another_tenant.id))
    cross_tenant_response = another_client.post(
        "/api/v2/pools/upsert/",
        {
            "pool_id": pool_id,
            "code": "pool-meta",
            "name": "Cross tenant update",
        },
        format="json",
    )
    assert cross_tenant_response.status_code == 404
    assert cross_tenant_response.json()["code"] == "POOL_NOT_FOUND"


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_creates_graph_for_date(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Root Org", inn="741000000001")
    middle_org = Organization.objects.create(tenant=default_tenant, name="Middle Org", inn="741000000002")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Leaf Org", inn="741000000003")
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "effective_to": None,
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(middle_org.id), "is_root": False},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(middle_org.id),
                    "weight": "1.0",
                },
                {
                    "parent_organization_id": str(middle_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["pool_id"] == str(pool.id)
    assert payload["nodes_count"] == 3
    assert payload["edges_count"] == 2
    assert isinstance(payload["version"], str) and payload["version"]

    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert isinstance(graph_payload["version"], str) and graph_payload["version"]
    assert len(graph_payload["nodes"]) == 3
    assert len(graph_payload["edges"]) == 2
    assert any(node["is_root"] for node in graph_payload["nodes"])


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_accepts_valid_document_policy_metadata(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Policy Root", inn="741100000001")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Policy Leaf", inn="741100000002")
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                    "metadata": {
                        "document_policy": _build_document_policy_payload(),
                    },
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 200

    edge = (
        PoolEdgeVersion.objects.select_related("parent_node__organization", "child_node__organization")
        .filter(pool=pool, effective_from=date(2026, 1, 1))
        .get(
            parent_node__organization=root_org,
            child_node__organization=leaf_org,
        )
    )
    edge_metadata = edge.metadata if isinstance(edge.metadata, dict) else {}
    policy = edge_metadata.get("document_policy")
    assert isinstance(policy, dict)
    documents = policy["chains"][0]["documents"]
    assert documents[0]["invoice_mode"] == "required"
    assert documents[1]["invoice_mode"] == "optional"


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_rejects_invalid_document_policy_mapping(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Policy Invalid Root", inn="741100000011")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Policy Invalid Leaf", inn="741100000012")
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    invalid_policy = _build_document_policy_payload()
    invalid_policy["chains"][0]["documents"][0]["field_mapping"] = []

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                    "metadata": {
                        "document_policy": invalid_policy,
                    },
                },
            ],
        },
        format="json",
    )
    payload = _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")
    assert "POOL_DOCUMENT_POLICY_MAPPING_INVALID" in payload["detail"]


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_rejects_missing_required_invoice_in_policy(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Policy Missing Invoice Root", inn="741100000021")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Policy Missing Invoice Leaf", inn="741100000022")
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    invalid_policy = _build_document_policy_payload()
    invalid_policy["chains"][0]["documents"] = [
        {
            "document_id": "sale",
            "entity_name": "Document_Sales",
            "document_role": "sale",
            "field_mapping": {"Amount": "allocation.amount"},
            "table_parts_mapping": {},
            "link_rules": {},
            "invoice_mode": "required",
        }
    ]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                    "metadata": {
                        "document_policy": invalid_policy,
                    },
                },
            ],
        },
        format="json",
    )
    payload = _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")
    assert "POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE" in payload["detail"]


@pytest.mark.django_db
def test_get_pool_graph_returns_node_and_edge_metadata_including_document_policy(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Graph Metadata Root", inn="741100000031")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Graph Metadata Leaf", inn="741100000032")
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {
                    "organization_id": str(root_org.id),
                    "is_root": True,
                    "metadata": {"node_tag": "root-tag"},
                },
                {
                    "organization_id": str(leaf_org.id),
                    "is_root": False,
                    "metadata": {"node_tag": "leaf-tag"},
                },
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                    "metadata": {
                        "edge_tag": "edge-tag",
                        "document_policy": _build_document_policy_payload(),
                    },
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 200

    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_response.status_code == 200
    payload = graph_response.json()

    nodes_by_org = {item["organization_id"]: item for item in payload["nodes"]}
    assert nodes_by_org[str(root_org.id)]["metadata"] == {"node_tag": "root-tag"}
    assert nodes_by_org[str(leaf_org.id)]["metadata"] == {"node_tag": "leaf-tag"}

    assert len(payload["edges"]) == 1
    edge_metadata = payload["edges"][0]["metadata"]
    assert edge_metadata["edge_tag"] == "edge-tag"
    assert edge_metadata["document_policy"]["version"] == "document_policy.v1"
    documents = edge_metadata["document_policy"]["chains"][0]["documents"]
    assert documents[0]["invoice_mode"] == "required"
    assert documents[1]["invoice_mode"] == "optional"


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_rejects_invalid_cycle(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    left_org = Organization.objects.create(tenant=default_tenant, name="Cycle Left", inn="742000000001")
    right_org = Organization.objects.create(tenant=default_tenant, name="Cycle Right", inn="742000000002")
    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    current_version = graph_before.json()["version"]

    response = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": current_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(left_org.id), "is_root": True},
                {"organization_id": str(right_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(left_org.id),
                    "child_organization_id": str(right_org.id),
                    "weight": "1.0",
                },
                {
                    "parent_organization_id": str(right_org.id),
                    "child_organization_id": str(left_org.id),
                    "weight": "1.0",
                },
            ],
        },
        format="json",
    )
    _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")


@pytest.mark.django_db
def test_upsert_pool_topology_snapshot_rejects_stale_version_with_problem_details(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Version Root", inn="742000000011")
    leaf_org = Organization.objects.create(tenant=default_tenant, name="Version Leaf", inn="742000000012")

    graph_before = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-01")
    assert graph_before.status_code == 200
    stale_version = graph_before.json()["version"]

    first_save = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": stale_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "1.0",
                },
            ],
        },
        format="json",
    )
    assert first_save.status_code == 200

    conflict = authenticated_client.post(
        f"/api/v2/pools/{pool.id}/topology-snapshot/upsert/",
        {
            "version": stale_version,
            "effective_from": "2026-01-01",
            "nodes": [
                {"organization_id": str(root_org.id), "is_root": True},
                {"organization_id": str(leaf_org.id), "is_root": False},
            ],
            "edges": [
                {
                    "parent_organization_id": str(root_org.id),
                    "child_organization_id": str(leaf_org.id),
                    "weight": "0.8",
                },
            ],
        },
        format="json",
    )
    payload = _assert_problem_details_response(
        conflict,
        status_code=409,
        code="TOPOLOGY_VERSION_CONFLICT",
    )
    assert "latest version token" in payload["detail"]


@pytest.mark.django_db
def test_create_pool_run_rejects_top_down_without_starting_amount(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "direction": PoolRunDirection.TOP_DOWN,
            "period_start": "2026-01-01",
            "run_input": {},
            "mode": "safe",
        },
        format="json",
    )
    payload = _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")
    assert "run_input" in payload["detail"]


@pytest.mark.django_db
def test_create_pool_run_rejects_bottom_up_without_source_input(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {},
            "mode": "safe",
        },
        format="json",
    )
    payload = _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")
    assert "run_input" in payload["detail"]


@pytest.mark.django_db
def test_create_pool_run_rejects_legacy_source_hash_field_as_problem_details(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/runs/",
        {
            "pool_id": str(pool.id),
            "direction": PoolRunDirection.BOTTOM_UP,
            "period_start": "2026-01-01",
            "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
            "source_hash": "legacy-hash",
            "mode": "safe",
        },
        format="json",
    )
    payload = _assert_problem_details_response(response, status_code=400, code="VALIDATION_ERROR")
    assert "source_hash" in payload["detail"]


@pytest.mark.django_db
def test_create_pool_run_endpoint_creates_and_reuses_idempotency_key(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    payload = {
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "100.00"}]},
        "mode": "safe",
        "validation_summary": {"rows": 3},
        "diagnostics": [],
    }
    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-1", status="queued"),
    ) as enqueue:
        first = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")
        second = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    assert first.status_code == 201
    first_payload = first.json()
    assert first_payload["created"] is True
    assert first_payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert first_payload["run"]["workflow_execution_id"] is not None
    assert first_payload["run"]["workflow_status"] == "pending"
    assert first_payload["run"]["approval_state"] == "preparing"
    assert first_payload["run"]["publication_step_state"] == "not_enqueued"
    assert first_payload["run"]["execution_backend"] == "workflow_core"

    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["created"] is False
    assert second_payload["run"]["id"] == first_payload["run"]["id"]
    assert second_payload["run"]["workflow_execution_id"] == first_payload["run"]["workflow_execution_id"]
    enqueue.assert_called_once()

    run = PoolRun.objects.get(id=first_payload["run"]["id"])
    assert run.idempotency_key
    assert run.workflow_execution_id is not None
    assert run.publication_confirmed_at is None
    workflow_execution = WorkflowExecution.objects.get(id=run.workflow_execution_id)
    assert workflow_execution.execution_consumer == "pools"
    assert workflow_execution.tenant_id == run.tenant_id
    assert workflow_execution.input_context.get("approved_at") is None
    assert workflow_execution.input_context.get("approval_state") == "preparing"
    assert workflow_execution.input_context.get("publication_step_state") == "not_enqueued"
    assert workflow_execution.input_context.get("run_input") == payload["run_input"]
    assert workflow_execution.input_context.get("pool_run_idempotency_key") == run.idempotency_key
    assert workflow_execution.input_context.get("workflow_run_id") == str(workflow_execution.id)
    assert workflow_execution.input_context.get("root_workflow_run_id") == str(workflow_execution.id)
    assert workflow_execution.input_context.get("parent_workflow_run_id") is None
    assert workflow_execution.input_context.get("attempt_number") == 1
    assert workflow_execution.input_context.get("attempt_kind") == "initial"


@pytest.mark.django_db
def test_create_pool_run_endpoint_keeps_workflow_link_when_enqueue_fails(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    payload = {
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
        "mode": "safe",
    }
    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(
            success=False,
            operation_id="",
            status="error",
            error="redis down",
            error_code="REDIS_UNAVAILABLE",
        ),
    ):
        response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    assert response.status_code == 201
    data = response.json()
    assert data["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert data["run"]["workflow_execution_id"] is not None
    assert data["run"]["workflow_status"] == "pending"

    run = PoolRun.objects.get(id=data["run"]["id"])
    assert run.workflow_status == "pending"
    assert run.workflow_execution_id is not None
    assert PoolRunAuditEvent.objects.filter(run=run, event_type="run.workflow_execution_enqueue_failed").exists()


@pytest.mark.django_db
def test_create_pool_run_returns_problem_details_for_pool_runtime_fail_closed_error(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    payload = {
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
        "mode": "safe",
    }

    with patch(
        "apps.api_v2.views.intercompany_pools.start_pool_run_workflow_execution",
        side_effect=ValueError(
            "POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED: alias 'pool.prepare_input' is not configured"
        ),
    ):
        response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED",
    )
    assert problem["title"] == "Pool Runtime Configuration Error"
    assert "pool.prepare_input" in problem["detail"]


@pytest.mark.django_db
def test_create_pool_run_returns_problem_details_for_missing_actor_mapping(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    _attach_pool_target_database(
        tenant=default_tenant,
        pool=pool,
        period_start=date(2026, 1, 1),
    )
    payload = {
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
        "mode": "safe",
    }

    response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="ODATA_MAPPING_NOT_CONFIGURED",
    )
    assert problem["title"] == "Pool Runtime Configuration Error"
    assert "/rbac" in problem["detail"]


@pytest.mark.django_db
def test_create_pool_run_returns_problem_details_for_ambiguous_actor_mapping(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    database = _attach_pool_target_database(
        tenant=default_tenant,
        pool=pool,
        period_start=date(2026, 1, 1),
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=user,
        ib_username="actor-1",
        ib_password="pass-1",
        is_service=False,
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=user,
        ib_username="actor-2",
        ib_password="pass-2",
        is_service=False,
    )
    payload = {
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
        "mode": "safe",
    }

    response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    problem = _assert_problem_details_response(
        response,
        status_code=400,
        code="ODATA_MAPPING_AMBIGUOUS",
    )
    assert problem["title"] == "Pool Runtime Configuration Error"
    assert "/rbac" in problem["detail"]


@pytest.mark.django_db
def test_create_pool_run_succeeds_when_actor_mapping_configured(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    database = _attach_pool_target_database(
        tenant=default_tenant,
        pool=pool,
        period_start=date(2026, 1, 1),
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=user,
        ib_username="actor-ok",
        ib_password="actor-pass",
        is_service=False,
    )
    payload = {
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "50.00"}]},
        "mode": "safe",
    }

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-with-mapping", status="queued"),
    ):
        response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    assert response.status_code == 201
    assert response.json()["run"]["workflow_execution_id"] is not None


@pytest.mark.django_db
def test_create_pool_run_enqueues_to_workflow_stream_with_normal_priority(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    payload = {
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "run_input": {"source_payload": [{"inn": "730000000001", "amount": "30.00"}]},
        "mode": "safe",
    }
    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        mock_redis_client.STREAM_WORKFLOWS = "commands:worker:workflows"
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123456-0"

        response = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")

    assert response.status_code == 201
    run_payload = response.json()["run"]
    assert run_payload["workflow_execution_id"] is not None

    mock_redis_client.enqueue_operation_stream.assert_called_once()
    call_args = mock_redis_client.enqueue_operation_stream.call_args
    message = call_args.args[0]
    assert call_args.kwargs["stream_name"] == "commands:worker:workflows"
    assert message["execution_config"]["priority"] == "normal"
    assert message["execution_config"]["idempotency_key"] == run_payload["idempotency_key"]
    assert message["payload"]["data"]["pool_run_idempotency_key"] == run_payload["idempotency_key"]
    assert message["operation_type"] == "execute_workflow"
    mock_event_publisher.publish.assert_called_once()


@pytest.mark.django_db
def test_get_pool_run_returns_details(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    database = _create_database(tenant=default_tenant, name="pool-api-details-db")
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=database,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=False,
        error_code="network",
        error_message="temporary error",
    )
    run.add_audit_event(
        event_type="run.test_event",
        status_before=run.status,
        status_after=run.status,
        payload={"test": True},
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["id"] == str(run.id)
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["terminal_reason"] is None
    assert payload["run"]["provenance"]["workflow_run_id"] is None
    assert payload["run"]["provenance"]["workflow_status"] is None
    assert payload["run"]["provenance"]["execution_backend"] == "legacy_pool_runtime"
    assert payload["run"]["provenance"]["retry_chain"] == []
    assert len(payload["publication_attempts"]) == 1
    attempt_payload = payload["publication_attempts"][0]
    assert attempt_payload["target_database_id"] == str(database.id)
    assert attempt_payload["attempt_timestamp"] is not None
    assert attempt_payload["payload_summary"] == {
        "documents_count": 1,
        "entity_name": "Document_IntercompanyPoolDistribution",
    }
    assert attempt_payload["http_error"] is None
    assert attempt_payload["transport_error"] == {
        "code": "network",
        "message": "temporary error",
    }
    assert attempt_payload["domain_error_code"] == "network"
    assert attempt_payload["domain_error_message"] == "temporary error"
    assert attempt_payload["publication_identity_strategy"] == ""
    assert any(event["event_type"] == "run.test_event" for event in payload["audit_events"])


@pytest.mark.django_db
def test_historical_run_read_contract_returns_nullable_run_input_and_legacy_contract_version(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    historical_run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2025, 12, 1),
        run_input={},
        source_hash="legacy-source-hash",
    )

    list_response = authenticated_client.get(f"/api/v2/pools/runs/?pool_id={pool.id}&limit=10")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    historical_row = next(item for item in list_payload["runs"] if item["id"] == str(historical_run.id))
    assert historical_row["run_input"] is None
    assert historical_row["input_contract_version"] == "legacy_pre_run_input"
    assert "source_hash" not in historical_row

    details_response = authenticated_client.get(f"/api/v2/pools/runs/{historical_run.id}/")
    assert details_response.status_code == 200
    details_payload = details_response.json()
    assert details_payload["run"]["run_input"] is None
    assert details_payload["run"]["input_contract_version"] == "legacy_pre_run_input"
    assert "source_hash" not in details_payload["run"]


@pytest.mark.django_db
def test_get_pool_run_serializes_http_error_in_canonical_diagnostics(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    database = _create_database(tenant=default_tenant, name="pool-api-http-error-db")
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=database,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=2,
        posted=False,
        http_status=503,
        error_code="ODataRequestError",
        error_message="gateway timeout",
        request_summary={"documents_count": 2},
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    attempt_payload = payload["publication_attempts"][0]
    assert attempt_payload["payload_summary"] == {
        "documents_count": 2,
        "entity_name": "Document_IntercompanyPoolDistribution",
        "requested_documents_count": 2,
    }
    assert attempt_payload["http_error"] == {
        "status": 503,
        "code": "ODataRequestError",
        "message": "gateway timeout",
    }
    assert attempt_payload["transport_error"] is None
    assert attempt_payload["domain_error_code"] == "ODataRequestError"
    assert attempt_payload["domain_error_message"] == "gateway timeout"
    assert attempt_payload["error_code"] == "ODataRequestError"
    assert attempt_payload["error_message"] == "gateway timeout"


@pytest.mark.django_db
def test_get_pool_run_redacts_traceback_and_sensitive_diagnostics(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    database = _create_database(tenant=default_tenant, name="pool-api-redaction-db")
    sensitive_error = (
        f"Traceback (most recent call last): File \"worker.py\", line 42, "
        f"password=super-secret token=abc123 tenant={default_tenant.id}"
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=database,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=False,
        error_code="ODataRequestError",
        error_message=sensitive_error,
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    attempt_payload = payload["publication_attempts"][0]
    assert attempt_payload["domain_error_message"] == "internal_error"
    assert attempt_payload["transport_error"] == {
        "code": "ODataRequestError",
        "message": "internal_error",
    }
    assert str(default_tenant.id) not in attempt_payload["domain_error_message"]
    assert "super-secret" not in attempt_payload["domain_error_message"]
    assert "abc123" not in attempt_payload["domain_error_message"]


@pytest.mark.django_db
def test_get_pool_run_resolves_transition_workflow_link_without_persisted_relation(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    run.add_audit_event(
        event_type="run.transition_only_event",
        status_before=run.status,
        status_after=run.status,
        payload={"source": "transition"},
    )
    execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_RUNNING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "publication_step_state": "started",
        },
        link_run=False,
    )
    run_state = PoolRun.objects.get(id=run.id)
    assert run_state.workflow_execution_id is None
    assert run_state.execution_backend == "legacy_pool_runtime"

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["workflow_execution_id"] == str(execution.id)
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING
    assert payload["run"]["execution_backend"] == "workflow_core"
    assert payload["run"]["provenance"]["workflow_run_id"] == str(execution.id)
    assert payload["run"]["provenance"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING
    assert payload["run"]["provenance"]["retry_chain"] == [
        {
            "workflow_run_id": str(execution.id),
            "parent_workflow_run_id": None,
            "attempt_number": 1,
            "attempt_kind": "initial",
            "status": WorkflowExecution.STATUS_RUNNING,
        }
    ]
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHING
    assert any(event["event_type"] == "run.transition_only_event" for event in payload["audit_events"])


@pytest.mark.django_db
def test_get_pool_run_builds_deterministic_lineage_for_multiple_workflow_attempts(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    initial_execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "publication_step_state": "completed",
        },
        link_run=False,
    )
    initial_execution.input_context = {
        **(initial_execution.input_context or {}),
        "workflow_run_id": str(initial_execution.id),
        "root_workflow_run_id": str(initial_execution.id),
        "parent_workflow_run_id": None,
        "attempt_number": 1,
        "attempt_kind": "initial",
    }
    initial_execution.save(update_fields=["input_context"])

    retry_execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_RUNNING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "publication_step_state": "started",
        },
        link_run=False,
    )
    retry_execution.input_context = {
        **(retry_execution.input_context or {}),
        "workflow_run_id": str(retry_execution.id),
        "root_workflow_run_id": str(initial_execution.id),
        "parent_workflow_run_id": str(initial_execution.id),
        "attempt_number": 2,
        "attempt_kind": "retry",
    }
    retry_execution.save(update_fields=["input_context"])

    run_state = PoolRun.objects.get(id=run.id)
    assert run_state.workflow_execution_id is None

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["workflow_execution_id"] == str(retry_execution.id)
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING
    assert payload["run"]["provenance"]["workflow_run_id"] == str(initial_execution.id)
    assert payload["run"]["provenance"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING
    assert payload["run"]["provenance"]["retry_chain"] == [
        {
            "workflow_run_id": str(initial_execution.id),
            "parent_workflow_run_id": None,
            "attempt_number": 1,
            "attempt_kind": "initial",
            "status": WorkflowExecution.STATUS_COMPLETED,
        },
        {
            "workflow_run_id": str(retry_execution.id),
            "parent_workflow_run_id": str(initial_execution.id),
            "attempt_number": 2,
            "attempt_kind": "retry",
            "status": WorkflowExecution.STATUS_RUNNING,
        },
    ]


@pytest.mark.django_db
def test_list_runs_resolves_transition_workflow_link_without_persisted_relation(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_PENDING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "publication_step_state": "not_enqueued",
        },
        link_run=False,
    )
    assert PoolRun.objects.get(id=run.id).workflow_execution_id is None

    response = authenticated_client.get(f"/api/v2/pools/runs/?pool_id={pool.id}&limit=10")
    assert response.status_code == 200
    payload = response.json()
    run_payload = next(item for item in payload["runs"] if item["id"] == str(run.id))
    assert run_payload["workflow_execution_id"] == str(execution.id)
    assert run_payload["workflow_status"] == WorkflowExecution.STATUS_PENDING
    assert run_payload["execution_backend"] == "workflow_core"
    assert run_payload["provenance"]["workflow_run_id"] == str(execution.id)
    assert run_payload["provenance"]["workflow_status"] == WorkflowExecution.STATUS_PENDING
    assert run_payload["provenance"]["retry_chain"] == [
        {
            "workflow_run_id": str(execution.id),
            "parent_workflow_run_id": None,
            "attempt_number": 1,
            "attempt_kind": "initial",
            "status": WorkflowExecution.STATUS_PENDING,
        }
    ]


@pytest.mark.django_db
def test_get_pool_run_projects_safe_pending_workflow_to_validated_preparing(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save()
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_PENDING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "preparing",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["status_reason"] == "preparing"
    assert payload["run"]["approval_state"] == "preparing"
    assert payload["run"]["publication_step_state"] == "not_enqueued"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_PENDING
    assert payload["run"]["provenance"]["workflow_run_id"] == str(run.workflow_execution_id)
    assert payload["run"]["provenance"]["workflow_status"] == WorkflowExecution.STATUS_PENDING
    assert payload["run"]["provenance"]["execution_backend"] == "workflow_core"
    assert payload["run"]["provenance"]["retry_chain"] == [
        {
            "workflow_run_id": str(run.workflow_execution_id),
            "parent_workflow_run_id": None,
            "attempt_number": 1,
            "attempt_kind": "initial",
            "status": WorkflowExecution.STATUS_PENDING,
        }
    ]


@pytest.mark.django_db
def test_get_pool_run_projects_completed_workflow_with_failed_targets_to_partial_success(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    run.publication_summary = {"failed_targets": 2}
    run.save(update_fields=["publication_summary", "updated_at"])
    _attach_workflow_execution_to_run(run=run, status=WorkflowExecution.STATUS_COMPLETED)

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_PARTIAL_SUCCESS
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED


@pytest.mark.django_db
def test_get_pool_run_projects_completed_workflow_with_completed_publication_step_to_published(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
            "publication_step_state": "completed",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHED
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["publication_step_state"] == "completed"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED


@pytest.mark.django_db
def test_get_pool_run_projects_completed_workflow_with_non_completed_publication_step_to_failed(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
            "publication_step_state": "queued",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_FAILED
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["publication_step_state"] == "queued"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED
    diagnostics = payload["run"]["diagnostics"]
    assert any(
        item.get("code") == "POOL_PUBLICATION_STEP_INCOMPLETE"
        for item in diagnostics
        if isinstance(item, dict)
    )


@pytest.mark.django_db
def test_get_pool_run_returns_stable_publication_incomplete_problem_code_with_existing_diagnostics(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    run.diagnostics = [
        {
            "type": "about:blank",
            "title": "Validation Error",
            "status": 400,
            "detail": "legacy diagnostics should not replace publication code",
            "code": "VALIDATION_ERROR",
        }
    ]
    run.save(update_fields=["diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
            "publication_step_state": "queued",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    diagnostics = [item for item in payload["run"]["diagnostics"] if isinstance(item, dict)]
    publication_diagnostics = [
        item
        for item in diagnostics
        if item.get("code") == "POOL_PUBLICATION_STEP_INCOMPLETE"
    ]
    assert len(publication_diagnostics) == 1
    publication_problem = publication_diagnostics[0]
    assert publication_problem.get("type") == "about:blank"
    assert publication_problem.get("title") == "Publication Step Incomplete"
    assert publication_problem.get("status") == 409
    assert publication_problem.get("code") == "POOL_PUBLICATION_STEP_INCOMPLETE"
    assert "publication-step completion" in str(publication_problem.get("detail"))
    assert any(item.get("code") == "VALIDATION_ERROR" for item in diagnostics)


@pytest.mark.django_db
def test_get_pool_run_projects_workflow_core_historical_completed_without_publication_state_uses_legacy_projection(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
        },
    )

    historical_started_at = datetime(2025, 12, 31, 23, 59, tzinfo=dt_timezone.utc)
    WorkflowExecution.objects.filter(id=run.workflow_execution_id).update(started_at=historical_started_at)

    RuntimeSetting.objects.update_or_create(
        key="pools.projection.publication_hardening_cutoff_utc",
        defaults={"value": "2026-01-01T00:00:00Z"},
    )
    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHED
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["publication_step_state"] is None
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED
    diagnostics = payload["run"]["diagnostics"]
    assert not any(
        item.get("code") == "POOL_PUBLICATION_STEP_INCOMPLETE"
        for item in diagnostics
        if isinstance(item, dict)
    )


@pytest.mark.django_db
def test_get_pool_run_projects_workflow_core_new_completed_without_publication_state_is_failed_after_cutoff(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
        },
    )

    started_after_cutoff = datetime(2026, 1, 1, 0, 1, tzinfo=dt_timezone.utc)
    WorkflowExecution.objects.filter(id=run.workflow_execution_id).update(started_at=started_after_cutoff)

    RuntimeSetting.objects.update_or_create(
        key="pools.projection.publication_hardening_cutoff_utc",
        defaults={"value": "2026-01-01T00:00:00Z"},
    )
    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_FAILED
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["publication_step_state"] is None
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED


@pytest.mark.django_db
def test_get_pool_run_projects_workflow_core_completed_without_publication_state_ignores_non_utc_cutoff(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": False,
            "approval_state": "not_required",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
        },
    )

    started_after_cutoff = datetime(2026, 1, 1, 0, 1, tzinfo=dt_timezone.utc)
    WorkflowExecution.objects.filter(id=run.workflow_execution_id).update(started_at=started_after_cutoff)

    RuntimeSetting.objects.update_or_create(
        key="pools.projection.publication_hardening_cutoff_utc",
        defaults={"value": "2026-01-01T00:00:00+03:00"},
    )
    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHED
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["publication_step_state"] is None
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED


@pytest.mark.django_db
def test_get_pool_run_projects_safe_completed_unapproved_workflow_to_validated_awaiting_approval(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save()
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "preparing",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["status_reason"] == "awaiting_approval"
    assert payload["run"]["approval_state"] == "awaiting_approval"
    assert payload["run"]["publication_step_state"] == "not_enqueued"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_COMPLETED


@pytest.mark.django_db
def test_get_pool_run_projects_running_approved_with_queued_publication_state_to_validated_queued(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.confirm_publication()
    run.save(
        update_fields=[
            "status",
            "validated_at",
            "validation_summary",
            "diagnostics",
            "publication_confirmed_at",
            "publication_confirmed_by",
            "updated_at",
        ]
    )
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_RUNNING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat(),
            "publication_step_state": "queued",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["status_reason"] == "queued"
    assert payload["run"]["approval_state"] == "approved"
    assert payload["run"]["publication_step_state"] == "queued"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING


@pytest.mark.django_db
def test_get_pool_run_projects_running_approved_with_started_publication_state_to_publishing(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.confirm_publication()
    run.save(
        update_fields=[
            "status",
            "validated_at",
            "validation_summary",
            "diagnostics",
            "publication_confirmed_at",
            "publication_confirmed_by",
            "updated_at",
        ]
    )
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_RUNNING,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat(),
            "publication_step_state": "started",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHING
    assert payload["run"]["status_reason"] is None
    assert payload["run"]["approval_state"] == "approved"
    assert payload["run"]["publication_step_state"] == "started"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_RUNNING


@pytest.mark.django_db
def test_get_pool_run_returns_terminal_reason_from_workflow_input_context(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_CANCELLED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "approved",
            "approved_at": timezone.now().isoformat(),
            "publication_step_state": "queued",
            "terminal_reason": "aborted_by_operator",
        },
    )

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_FAILED
    assert payload["run"]["terminal_reason"] == "aborted_by_operator"


@pytest.mark.django_db
def test_confirm_publication_requires_idempotency_key_header(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


@pytest.mark.django_db
def test_abort_publication_requires_idempotency_key_header(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="awaiting_approval",
        publication_step_state="not_enqueued",
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


@pytest.mark.django_db
def test_confirm_publication_returns_noop_200_for_already_approved_run(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="approved",
        approved_at=timezone.now().isoformat(),
        publication_step_state="queued",
        workflow_status=WorkflowExecution.STATUS_RUNNING,
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-noop-1",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"] == "noop"
    assert payload["replayed"] is False
    assert payload["run"]["approval_state"] == "approved"
    assert payload["run"]["status_reason"] == "queued"
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0


@pytest.mark.django_db
def test_abort_publication_returns_noop_200_for_aborted_terminal_replay(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="approved",
        approved_at=timezone.now().isoformat(),
        publication_step_state="queued",
        workflow_status=WorkflowExecution.STATUS_CANCELLED,
        terminal_reason="aborted_by_operator",
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="abort-noop-1",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"] == "noop"
    assert payload["replayed"] is False
    assert payload["run"]["terminal_reason"] == "aborted_by_operator"
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0


@pytest.mark.django_db
def test_confirm_publication_from_preparing_returns_retryable_conflict_payload(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="preparing",
        publication_step_state="not_enqueued",
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-preparing-1",
    )
    assert response.status_code == 409
    _assert_safe_command_conflict_payload(
        response.json(),
        run_id=run.id,
        expected_code="AWAITING_PRE_PUBLISH",
        expected_reason="awaiting_pre_publish",
        expected_retryable=True,
    )


@pytest.mark.django_db
def test_confirm_publication_for_unsafe_run_returns_not_safe_conflict_payload(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        mode=PoolRunMode.UNSAFE,
        approval_required=False,
        approval_state="not_required",
        approved_at=timezone.now().isoformat(),
        publication_step_state="queued",
        workflow_status=WorkflowExecution.STATUS_RUNNING,
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-unsafe-1",
    )
    assert response.status_code == 409
    _assert_safe_command_conflict_payload(
        response.json(),
        run_id=run.id,
        expected_code="NOT_SAFE_RUN",
        expected_reason="not_safe_run",
        expected_retryable=False,
    )


@pytest.mark.django_db
def test_abort_publication_after_started_step_returns_publication_started_conflict_payload(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="approved",
        approved_at=timezone.now().isoformat(),
        publication_step_state="started",
        workflow_status=WorkflowExecution.STATUS_RUNNING,
    )

    response = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="abort-started-1",
    )
    assert response.status_code == 409
    _assert_safe_command_conflict_payload(
        response.json(),
        run_id=run.id,
        expected_code="PUBLICATION_STARTED",
        expected_reason="publication_started",
        expected_retryable=False,
    )


@pytest.mark.django_db
def test_confirm_publication_returns_accepted_and_deterministic_replay(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    first = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-key-1",
    )
    replay = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-key-1",
    )

    assert first.status_code == 202
    first_payload = first.json()
    assert first_payload["result"] == "accepted"
    assert first_payload["replayed"] is False

    assert replay.status_code == 202
    replay_payload = replay.json()
    assert replay_payload["result"] == "accepted"
    assert replay_payload["replayed"] is True

    execution = WorkflowExecution.objects.get(id=run.workflow_execution_id)
    assert execution.input_context.get("publication_auth") == {
        "strategy": "actor",
        "actor_username": user.username,
        "source": "confirm_publication",
    }
    assert PoolRunCommandLog.objects.filter(run=run).count() == 1
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 1


@pytest.mark.django_db
def test_abort_publication_returns_accepted_and_deterministic_replay(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="awaiting_approval",
        publication_step_state="not_enqueued",
    )

    first = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="abort-key-replay-1",
    )
    replay = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="abort-key-replay-1",
    )

    assert first.status_code == 202
    first_payload = first.json()
    assert first_payload["result"] == "accepted"
    assert first_payload["replayed"] is False

    assert replay.status_code == 202
    replay_payload = replay.json()
    assert replay_payload["result"] == "accepted"
    assert replay_payload["replayed"] is True

    assert PoolRunCommandLog.objects.filter(run=run).count() == 1
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 1


@pytest.mark.django_db
def test_abort_publication_after_confirm_pending_outbox_returns_single_winner_conflict(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    confirm = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="confirm-key-2",
    )
    abort = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="abort-key-2",
    )

    assert confirm.status_code == 202
    assert abort.status_code == 409
    _assert_safe_command_conflict_payload(
        abort.json(),
        run_id=run.id,
        expected_code="TERMINAL_STATE",
        expected_reason="terminal_state",
        expected_retryable=False,
    )

    outbox_entries = list(PoolRunCommandOutbox.objects.filter(run=run))
    assert len(outbox_entries) == 1


@pytest.mark.django_db
def test_confirm_publication_with_reused_key_from_other_command_returns_idempotency_conflict(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = PoolRun.objects.create(
        tenant=default_tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
        mode=PoolRunMode.SAFE,
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
    )

    abort = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/abort-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="shared-key",
    )
    confirm = authenticated_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="shared-key",
    )

    assert abort.status_code == 202
    assert confirm.status_code == 409
    _assert_safe_command_conflict_payload(
        confirm.json(),
        run_id=run.id,
        expected_code="IDEMPOTENCY_KEY_REUSED",
        expected_reason="idempotency_key_reused",
        expected_retryable=False,
    )


@pytest.mark.django_db
def test_get_pool_run_cross_tenant_and_unknown_run_are_indistinguishable(
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)

    another_tenant = Tenant.objects.create(slug=f"tenant-alt-{uuid4().hex[:6]}", name="Tenant Alt")
    TenantMember.objects.create(
        tenant=another_tenant,
        user=user,
        role=TenantMember.ROLE_ADMIN,
    )
    another_client = APIClient()
    another_client.force_authenticate(user=user)
    another_client.credentials(HTTP_X_CC1C_TENANT_ID=str(another_tenant.id))

    cross_tenant_response = another_client.get(f"/api/v2/pools/runs/{run.id}/")
    unknown_response = another_client.get(f"/api/v2/pools/runs/{uuid4()}/")

    assert cross_tenant_response.status_code == 404
    assert unknown_response.status_code == 404
    assert cross_tenant_response.json() == unknown_response.json()
    assert cross_tenant_response.json()["error"]["code"] == "RUN_NOT_FOUND"


@pytest.mark.django_db
def test_confirm_publication_cross_tenant_and_unknown_run_are_indistinguishable(
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_run_with_execution_state(
        tenant=default_tenant,
        pool=pool,
        approval_required=True,
        approval_state="awaiting_approval",
        publication_step_state="not_enqueued",
    )

    another_tenant = Tenant.objects.create(slug=f"tenant-alt-safe-{uuid4().hex[:6]}", name="Tenant Alt Safe")
    TenantMember.objects.create(
        tenant=another_tenant,
        user=user,
        role=TenantMember.ROLE_ADMIN,
    )
    another_client = APIClient()
    another_client.force_authenticate(user=user)
    another_client.credentials(HTTP_X_CC1C_TENANT_ID=str(another_tenant.id))

    cross_tenant_response = another_client.post(
        f"/api/v2/pools/runs/{run.id}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="tenant-cross-check",
    )
    unknown_response = another_client.post(
        f"/api/v2/pools/runs/{uuid4()}/confirm-publication/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="tenant-cross-check-unknown",
    )

    assert cross_tenant_response.status_code == 404
    assert unknown_response.status_code == 404
    assert cross_tenant_response.json() == unknown_response.json()
    assert cross_tenant_response.json()["error"]["code"] == "RUN_NOT_FOUND"


@pytest.mark.django_db
def test_retry_pool_run_failed_endpoint_returns_accepted_workflow_reference_and_avoids_direct_publication(
    authenticated_client: APIClient,
    user: User,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    db_one = _create_database(tenant=default_tenant, name="pool-api-retry-db-one")
    db_two = _create_database(tenant=default_tenant, name="pool-api-retry-db-two")
    initial_execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={"pool_run_id": str(run.id)},
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=db_one,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.SUCCESS,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=True,
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=db_two,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=False,
        error_code="network",
        error_message="temporary network error",
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="retry-op-1", status="queued"),
    ) as enqueue:
        response = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(db_one.id): [{"Amount": "100.00"}, {"Amount": "110.00"}],
                    str(db_two.id): [{"Amount": "90.00"}],
                },
                "use_retry_subset_payload": True,
                "max_attempts": 1,
            },
            format="json",
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["operation_id"] == "retry-op-1"
    assert payload["retry_target_summary"] == {
        "requested_targets": 2,
        "requested_documents": 3,
        "failed_targets": 1,
        "enqueued_targets": 1,
        "skipped_successful_targets": 1,
    }
    assert payload["workflow_execution_id"] != str(initial_execution.id)
    enqueue.assert_called_once()

    run_reloaded = PoolRun.objects.get(id=run.id)
    assert str(run_reloaded.workflow_execution_id) == payload["workflow_execution_id"]
    assert run_reloaded.workflow_status == "queued"
    retry_execution = WorkflowExecution.objects.get(id=run_reloaded.workflow_execution_id)
    assert retry_execution.input_context.get("attempt_kind") == "retry"
    assert retry_execution.input_context.get("attempt_number") == 2
    assert retry_execution.input_context.get("parent_workflow_run_id") == str(initial_execution.id)
    retry_request = retry_execution.input_context.get("retry_request")
    assert isinstance(retry_request, dict)
    assert retry_request.get("requested_target_ids") == [str(db_two.id)]
    assert retry_request.get("requested_targets_count") == 1
    assert retry_request.get("requested_documents_count") == 1
    assert retry_request.get("use_retry_subset_payload") is True
    assert retry_execution.input_context.get("pool_runtime_retry_settings") == {
        "use_retry_subset_payload": True,
    }
    publication_payload = retry_execution.input_context.get("pool_runtime_publication_payload")
    assert isinstance(publication_payload, dict)
    pool_runtime_payload = publication_payload.get("pool_runtime")
    assert isinstance(pool_runtime_payload, dict)
    assert pool_runtime_payload.get("entity_name") == "Document_IntercompanyPoolDistribution"
    assert pool_runtime_payload.get("documents_by_database") == {
        str(db_two.id): [{"Amount": "90.00"}],
    }
    assert retry_execution.input_context.get("publication_auth") == {
        "strategy": "actor",
        "actor_username": user.username,
        "source": "retry_publication",
    }


@pytest.mark.django_db
def test_retry_pool_run_failed_endpoint_builds_subset_from_persisted_document_plan_artifact(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    db_success = _create_database(tenant=default_tenant, name="pool-api-retry-success-db")
    db_failed = _create_database(tenant=default_tenant, name="pool-api-retry-failed-db")
    initial_execution = _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={
            "pool_run_id": str(run.id),
            "pool_runtime_document_plan_artifact": {
                "version": "document_plan_artifact.v1",
                "run_id": str(run.id),
                "distribution_artifact_ref": {
                    "version": "distribution_artifact.v1",
                    "topology_version_ref": "topology-v1",
                },
                "topology_version_ref": "topology-v1",
                "policy_refs": [
                    {
                        "edge_ref": {"parent_node_id": "node-parent", "child_node_id": "node-child"},
                        "policy_version": "document_policy.v1",
                        "source": "edge.metadata.document_policy",
                    }
                ],
                "targets": [
                    {
                        "database_id": str(db_success.id),
                        "chains": [
                            {
                                "chain_id": "chain-success",
                                "edge_ref": {"parent_node_id": "node-parent", "child_node_id": "node-success"},
                                "policy_source": "edge.metadata.document_policy",
                                "policy_version": "document_policy.v1",
                                "allocation": {"amount": "80.00"},
                                "documents": [
                                    {
                                        "document_id": "doc-success",
                                        "entity_name": "Document_Sales",
                                        "document_role": "base",
                                        "field_mapping": {},
                                        "table_parts_mapping": {},
                                        "link_rules": {},
                                        "invoice_mode": "optional",
                                        "idempotency_key": "doc-success-key",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "database_id": str(db_failed.id),
                        "chains": [
                            {
                                "chain_id": "chain-failed",
                                "edge_ref": {"parent_node_id": "node-parent", "child_node_id": "node-failed"},
                                "policy_source": "edge.metadata.document_policy",
                                "policy_version": "document_policy.v1",
                                "allocation": {"amount": "20.00"},
                                "documents": [
                                    {
                                        "document_id": "doc-sale",
                                        "entity_name": "Document_Sales",
                                        "document_role": "base",
                                        "field_mapping": {},
                                        "table_parts_mapping": {},
                                        "link_rules": {},
                                        "invoice_mode": "optional",
                                        "idempotency_key": "doc-sale-key",
                                    },
                                    {
                                        "document_id": "doc-invoice",
                                        "entity_name": "Document_Invoice",
                                        "document_role": "invoice",
                                        "field_mapping": {},
                                        "table_parts_mapping": {},
                                        "link_rules": {},
                                        "invoice_mode": "required",
                                        "idempotency_key": "doc-invoice-key",
                                        "link_to": "doc-sale",
                                    },
                                ],
                            }
                        ],
                    },
                ],
                "compile_summary": {
                    "compiled_edges": 1,
                    "targets_count": 2,
                    "chains_count": 2,
                    "documents_count": 3,
                    "compiled_at": "2026-01-01T00:00:00+00:00",
                },
            },
        },
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=db_success,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.SUCCESS,
        entity_name="Document_Sales",
        documents_count=1,
        posted=True,
        request_summary={
            "documents_count": 1,
            "document_idempotency_keys": ["doc-success-key"],
        },
        response_summary={
            "posted": True,
            "successful_document_idempotency_keys": ["doc-success-key"],
        },
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=db_failed,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_Sales",
        documents_count=2,
        posted=False,
        error_code="network",
        error_message="temporary network error",
        request_summary={
            "documents_count": 2,
            "document_idempotency_keys": ["doc-sale-key", "doc-invoice-key"],
        },
        response_summary={
            "posted": False,
            "successful_document_idempotency_keys": ["doc-sale-key"],
            "failed_document_idempotency_key": "doc-invoice-key",
        },
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="retry-op-artifact", status="queued"),
    ) as enqueue:
        response = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "target_database_ids": [str(db_failed.id)],
                "use_retry_subset_payload": True,
                "max_attempts": 1,
            },
            format="json",
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["operation_id"] == "retry-op-artifact"
    assert payload["retry_target_summary"] == {
        "requested_targets": 1,
        "requested_documents": 0,
        "failed_targets": 1,
        "enqueued_targets": 1,
        "skipped_successful_targets": 0,
    }
    assert payload["workflow_execution_id"] != str(initial_execution.id)
    enqueue.assert_called_once()

    run_reloaded = PoolRun.objects.get(id=run.id)
    retry_execution = WorkflowExecution.objects.get(id=run_reloaded.workflow_execution_id)
    retry_request = retry_execution.input_context.get("retry_request")
    assert isinstance(retry_request, dict)
    assert retry_request.get("requested_target_ids") == [str(db_failed.id)]
    assert retry_request.get("requested_targets_count") == 1
    assert retry_request.get("requested_documents_count") == 0
    publication_payload = retry_execution.input_context.get("pool_runtime_publication_payload")
    assert isinstance(publication_payload, dict)
    pool_runtime_payload = publication_payload.get("pool_runtime")
    assert isinstance(pool_runtime_payload, dict)
    assert pool_runtime_payload.get("documents_by_database") == {
        str(db_failed.id): [{"Amount": "20.00"}]
    }
    assert pool_runtime_payload.get("document_chains_by_database") == {
        str(db_failed.id): [
            {
                "chain_id": "chain-failed",
                "edge_ref": {"parent_node_id": "node-parent", "child_node_id": "node-failed"},
                "policy_source": "edge.metadata.document_policy",
                "policy_version": "document_policy.v1",
                "allocation": {"amount": "20.00"},
                "documents": [
                    {
                        "document_id": "doc-invoice",
                        "entity_name": "Document_Invoice",
                        "document_role": "invoice",
                        "idempotency_key": "doc-invoice-key",
                        "invoice_mode": "required",
                        "payload": {"Amount": "20.00"},
                        "link_to": "doc-sale",
                    }
                ],
            }
        ]
    }


@pytest.mark.django_db
def test_retry_pool_run_failed_endpoint_replays_idempotency_key_without_duplicate_enqueue(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    failed_db = _create_database(tenant=default_tenant, name="pool-api-retry-replay-failed-db")
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={"pool_run_id": str(run.id)},
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=failed_db,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=False,
        error_code="network",
        error_message="temporary network error",
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="retry-op-replay", status="queued"),
    ) as enqueue:
        first = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(failed_db.id): [{"Amount": "100.00"}],
                },
                "max_attempts": 1,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="retry-replay-key-1",
        )
        replay = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(failed_db.id): [{"Amount": "100.00"}],
                },
                "max_attempts": 1,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="retry-replay-key-1",
        )

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json() == first.json()
    enqueue.assert_called_once()
    logs = list(
        PoolRunCommandLog.objects.filter(
            run=run,
            command_type=PoolRunCommandType.RETRY_PUBLICATION,
        )
    )
    assert len(logs) == 1
    assert logs[0].replay_count == 1


@pytest.mark.django_db
def test_retry_pool_run_failed_endpoint_reused_key_with_different_payload_returns_conflict(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    failed_db = _create_database(tenant=default_tenant, name="pool-api-retry-reuse-failed-db")
    _attach_workflow_execution_to_run(
        run=run,
        status=WorkflowExecution.STATUS_COMPLETED,
        input_context={"pool_run_id": str(run.id)},
    )
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=failed_db,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.FAILED,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=False,
        error_code="network",
        error_message="temporary network error",
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="retry-op-reuse", status="queued"),
    ) as enqueue:
        first = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(failed_db.id): [{"Amount": "100.00"}],
                },
                "max_attempts": 1,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="retry-reuse-key-1",
        )
        reused = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": "Document_IntercompanyPoolDistribution",
                "documents_by_database": {
                    str(failed_db.id): [{"Amount": "100.00"}],
                },
                "max_attempts": 2,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="retry-reuse-key-1",
        )

    assert first.status_code == 202
    assert reused.status_code == 409
    _assert_safe_command_conflict_payload(
        reused.json(),
        run_id=run.id,
        expected_code="IDEMPOTENCY_KEY_REUSED",
        expected_reason="idempotency_key_reused",
        expected_retryable=False,
    )
    enqueue.assert_called_once()


@pytest.mark.django_db
def test_list_schema_templates_returns_public_by_default(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    public_template = PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-public",
        name="JSON Public",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )
    PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-private",
        name="JSON Private",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=False,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )

    response = authenticated_client.get("/api/v2/pools/schema-templates/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["templates"][0]["id"] == str(public_template.id)


@pytest.mark.django_db
def test_list_schema_templates_supports_format_and_visibility_filters(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    json_public_active = PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-public-active",
        name="JSON Public Active",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        is_active=True,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )
    PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-public-inactive",
        name="JSON Public Inactive",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        is_active=False,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )
    xlsx_private_active = PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="xlsx-private-active",
        name="XLSX Private Active",
        format=PoolSchemaTemplateFormat.XLSX,
        is_public=False,
        is_active=True,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )

    filtered = authenticated_client.get(
        "/api/v2/pools/schema-templates/?format=json&is_public=true&is_active=true"
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["count"] == 1
    assert filtered_payload["templates"][0]["id"] == str(json_public_active.id)

    private_only = authenticated_client.get("/api/v2/pools/schema-templates/?is_public=false")
    assert private_only.status_code == 200
    private_payload = private_only.json()
    assert private_payload["count"] == 1
    assert private_payload["templates"][0]["id"] == str(xlsx_private_active.id)


@pytest.mark.django_db
def test_create_schema_template_with_optional_workflow_binding(
    authenticated_client: APIClient,
) -> None:
    response = authenticated_client.post(
        "/api/v2/pools/schema-templates/",
        {
            "code": "xlsx-import-v1",
            "name": "XLSX Import V1",
            "format": PoolSchemaTemplateFormat.XLSX,
            "schema": {"sheet_name": "Sheet1", "columns": {"inn": "inn", "amount": "amount"}},
            "workflow_template_id": "11111111-1111-1111-1111-111111111111",
        },
        format="json",
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["template"]["code"] == "xlsx-import-v1"
    assert payload["template"]["workflow_template_id"] == "11111111-1111-1111-1111-111111111111"

    duplicate = authenticated_client.post(
        "/api/v2/pools/schema-templates/",
        {
            "code": "xlsx-import-v1",
            "name": "Duplicate",
            "format": PoolSchemaTemplateFormat.XLSX,
        },
        format="json",
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "DUPLICATE_TEMPLATE_CODE"


@pytest.mark.django_db
def test_graph_endpoint_filters_versions_by_requested_date(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Root Date", inn="750000000001")
    jan_org = Organization.objects.create(tenant=default_tenant, name="Jan Child", inn="750000000002")
    feb_org = Organization.objects.create(tenant=default_tenant, name="Feb Child", inn="750000000003")
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    jan_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=jan_org,
        effective_from=date(2026, 1, 1),
    )
    feb_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=feb_org,
        effective_from=date(2026, 2, 1),
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=jan_node,
        effective_from=date(2026, 1, 1),
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=feb_node,
        effective_from=date(2026, 2, 1),
    )

    january_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert january_response.status_code == 200
    january_payload = january_response.json()
    assert len(january_payload["nodes"]) == 2
    assert len(january_payload["edges"]) == 1

    february_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-02-15")
    assert february_response.status_code == 200
    february_payload = february_response.json()
    assert len(february_payload["nodes"]) == 3
    assert len(february_payload["edges"]) == 2


@pytest.mark.django_db
def test_list_pools_and_graph_endpoint(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    root_org = Organization.objects.create(tenant=default_tenant, name="Root", inn="700000000001")
    child_org = Organization.objects.create(tenant=default_tenant, name="Child", inn="700000000002")
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    child_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=child_org,
        effective_from=date(2026, 1, 1),
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=child_node,
        effective_from=date(2026, 1, 1),
    )

    pools_response = authenticated_client.get("/api/v2/pools/")
    assert pools_response.status_code == 200
    pools_payload = pools_response.json()
    assert pools_payload["count"] >= 1
    assert any(item["id"] == str(pool.id) for item in pools_payload["pools"])

    graph_response = authenticated_client.get(f"/api/v2/pools/{pool.id}/graph/?date=2026-01-15")
    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert graph_payload["pool_id"] == str(pool.id)
    assert len(graph_payload["nodes"]) == 2
    assert len(graph_payload["edges"]) == 1
    assert any(node["is_root"] for node in graph_payload["nodes"])


@pytest.mark.django_db
def test_create_pool_run_with_schema_template_uses_workflow_runtime(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    template = PoolSchemaTemplate.objects.create(
        tenant=default_tenant,
        code="json-run-template",
        name="JSON Run Template",
        format=PoolSchemaTemplateFormat.JSON,
        is_public=True,
        schema={"columns": {"inn": "inn", "amount": "amount"}},
    )

    with patch(
        "apps.intercompany_pools.workflow_runtime.OperationsService.enqueue_workflow_execution",
        return_value=EnqueueResult(success=True, operation_id="op-2", status="queued"),
    ):
        response = authenticated_client.post(
            "/api/v2/pools/runs/",
            {
                "pool_id": str(pool.id),
                "direction": PoolRunDirection.BOTTOM_UP,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "run_input": {"source_artifact_id": "artifact://pool-run-input"},
                "mode": "unsafe",
                "schema_template_id": str(template.id),
                "seed": 42,
            },
            format="json",
        )
    assert response.status_code == 201
    payload = response.json()
    assert payload["created"] is True
    assert payload["run"]["schema_template_id"] == str(template.id)
    assert payload["run"]["seed"] == 42
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["workflow_execution_id"] is not None
    assert payload["run"]["approval_state"] == "not_required"
    assert payload["run"]["publication_step_state"] == "queued"
    assert payload["run"]["execution_backend"] == "workflow_core"
    workflow_execution = WorkflowExecution.objects.get(id=payload["run"]["workflow_execution_id"])
    assert workflow_execution.execution_consumer == "pools"
    assert workflow_execution.tenant_id == default_tenant.id
    run = PoolRun.objects.get(id=payload["run"]["id"])
    assert run.publication_confirmed_at is not None
    assert workflow_execution.input_context.get("approved_at") is not None
    assert workflow_execution.input_context.get("approval_state") == "not_required"
    assert workflow_execution.input_context.get("publication_step_state") == "queued"


@pytest.mark.django_db
def test_list_runs_and_report_endpoint(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    database = _create_database(tenant=default_tenant, name="pool-api-report-db")
    PoolPublicationAttempt.objects.create(
        run=run,
        tenant=default_tenant,
        target_database=database,
        attempt_number=1,
        status=PoolPublicationAttemptStatus.SUCCESS,
        entity_name="Document_IntercompanyPoolDistribution",
        documents_count=1,
        posted=True,
    )

    runs_response = authenticated_client.get(f"/api/v2/pools/runs/?pool_id={pool.id}&limit=10")
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["count"] >= 1
    assert any(item["id"] == str(run.id) for item in runs_payload["runs"])

    report_response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/report/")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["run"]["id"] == str(run.id)
    assert report_payload["validation_summary"]["rows"] == 1
    assert report_payload["attempts_by_status"]["success"] == 1
    assert len(report_payload["publication_attempts"]) == 1
