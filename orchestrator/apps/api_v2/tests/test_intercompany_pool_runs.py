from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Database
from apps.databases.odata import ODataRequestError
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolNodeVersion,
    PoolPublicationAttempt,
    PoolPublicationAttemptStatus,
    PoolRun,
    PoolRunDirection,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
)
from apps.intercompany_pools.publication import publish_run_documents
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
    first = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")
    assert first.status_code == 201
    first_payload = first.json()
    assert first_payload["created"] is True
    assert first_payload["run"]["status"] == PoolRun.STATUS_DRAFT

    second = authenticated_client.post("/api/v2/pools/runs/", payload, format="json")
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["created"] is False
    assert second_payload["run"]["id"] == first_payload["run"]["id"]

    run = PoolRun.objects.get(id=first_payload["run"]["id"])
    assert run.idempotency_key


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
