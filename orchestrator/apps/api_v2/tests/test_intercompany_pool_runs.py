from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Database
from apps.databases.odata import ODataRequestError
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
    PoolRunDirection,
    PoolRunMode,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
)
from apps.intercompany_pools.publication import publish_run_documents
from apps.operations.services import EnqueueResult
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


def _attach_workflow_execution_to_run(*, run: PoolRun, status: str) -> WorkflowExecution:
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
        {"pool_run_id": str(run.id)},
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
            "source_hash": "file-1",
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
    assert conflict_response.status_code == 400
    assert conflict_response.json()["error"]["code"] == "DATABASE_ALREADY_LINKED"


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
def test_create_pool_run_endpoint_creates_and_reuses_idempotency_key(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    payload = {
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "source_hash": "same-file",
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
    workflow_execution = WorkflowExecution.objects.get(id=run.workflow_execution_id)
    assert workflow_execution.execution_consumer == "pools"
    assert workflow_execution.tenant_id == run.tenant_id


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
        "source_hash": "enqueue-error",
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
def test_create_pool_run_enqueues_to_workflow_stream_with_normal_priority(
    authenticated_client: APIClient,
    pool: OrganizationPool,
) -> None:
    payload = {
        "pool_id": str(pool.id),
        "direction": PoolRunDirection.BOTTOM_UP,
        "period_start": "2026-01-01",
        "source_hash": "queue-contract",
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
    assert len(payload["publication_attempts"]) == 1
    assert payload["publication_attempts"][0]["target_database_id"] == str(database.id)
    assert any(event["event_type"] == "run.test_event" for event in payload["audit_events"])


@pytest.mark.django_db
def test_get_pool_run_projects_safe_pending_workflow_to_validated_awaiting_approval(
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
    _attach_workflow_execution_to_run(run=run, status=WorkflowExecution.STATUS_PENDING)

    response = authenticated_client.get(f"/api/v2/pools/runs/{run.id}/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == PoolRun.STATUS_VALIDATED
    assert payload["run"]["status_reason"] == "awaiting_approval"
    assert payload["run"]["workflow_status"] == WorkflowExecution.STATUS_PENDING


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
def test_retry_pool_run_failed_endpoint_retries_only_failed_targets(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    pool: OrganizationPool,
) -> None:
    run = _create_validated_run(tenant=default_tenant, pool=pool)
    db_success = _create_database(tenant=default_tenant, name="pool-api-retry-db-success")
    db_failed = _create_database(tenant=default_tenant, name="pool-api-retry-db-failed")
    entity_name = "Document_IntercompanyPoolDistribution"

    success_client = MagicMock()
    success_client.get_entities.return_value = []
    success_client.create_entity.return_value = {"Ref_Key": "11111111-1111-1111-1111-111111111111"}

    failed_client = MagicMock()
    failed_client.get_entities.side_effect = ODataRequestError("target down", status_code=502)

    def _get_initial_client(*, base_id: str, **kwargs):  # noqa: ARG001
        if base_id == str(db_success.id):
            return success_client
        if base_id == str(db_failed.id):
            return failed_client
        raise AssertionError(f"Unexpected base_id: {base_id}")

    with patch("apps.intercompany_pools.publication.session_manager.get_client", side_effect=_get_initial_client):
        first_summary = publish_run_documents(
            run=run,
            entity_name=entity_name,
            documents_by_database={
                str(db_success.id): [{"Amount": "60.00"}],
                str(db_failed.id): [{"Amount": "40.00"}],
            },
            max_attempts=1,
        )

    assert first_summary.succeeded_targets == 1
    assert first_summary.failed_targets == 1

    recovered_client = MagicMock()
    recovered_client.get_entities.return_value = []
    recovered_client.create_entity.return_value = {"Ref_Key": "22222222-2222-2222-2222-222222222222"}

    def _get_retry_client(*, base_id: str, **kwargs):  # noqa: ARG001
        if base_id == str(db_success.id):
            raise AssertionError("Successful target should not be retried")
        if base_id == str(db_failed.id):
            return recovered_client
        raise AssertionError(f"Unexpected base_id: {base_id}")

    with patch("apps.intercompany_pools.publication.session_manager.get_client", side_effect=_get_retry_client):
        response = authenticated_client.post(
            f"/api/v2/pools/runs/{run.id}/retry/",
            {
                "entity_name": entity_name,
                "documents_by_database": {
                    str(db_success.id): [{"Amount": "999.00"}],
                    str(db_failed.id): [{"Amount": "40.00"}],
                },
                "max_attempts": 1,
            },
            format="json",
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_targets"] == 1
    assert payload["summary"]["succeeded_targets"] == 1
    assert payload["summary"]["failed_targets"] == 0
    assert payload["run"]["status"] == PoolRun.STATUS_PUBLISHED

    assert PoolPublicationAttempt.objects.filter(
        run=run,
        target_database=db_success,
        status=PoolPublicationAttemptStatus.SUCCESS,
    ).count() == 1
    failed_attempts = list(
        PoolPublicationAttempt.objects.filter(run=run, target_database=db_failed).order_by("attempt_number")
    )
    assert [attempt.status for attempt in failed_attempts] == [
        PoolPublicationAttemptStatus.FAILED,
        PoolPublicationAttemptStatus.SUCCESS,
    ]


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
                "source_hash": "facade-template-hash",
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
    assert payload["run"]["execution_backend"] == "workflow_core"
    workflow_execution = WorkflowExecution.objects.get(id=payload["run"]["workflow_execution_id"])
    assert workflow_execution.execution_consumer == "pools"
    assert workflow_execution.tenant_id == default_tenant.id


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
