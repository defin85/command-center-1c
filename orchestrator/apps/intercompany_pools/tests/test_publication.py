from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError

from apps.databases.models import Database
from apps.databases.odata import ODataRequestError
from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolPublicationAttempt,
    PoolPublicationAttemptStatus,
    PoolRun,
    PoolRunAuditEvent,
    PoolRunDirection,
)
from apps.intercompany_pools.publication import (
    MAX_PUBLICATION_ATTEMPTS,
    MAX_RETRY_INTERVAL_SECONDS,
    publish_run_documents,
    retry_failed_run_documents,
)
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


@pytest.fixture
def publication_context() -> dict[str, object]:
    tenant = Tenant.objects.create(slug="pool-publication", name="Pool Publication")
    pool = OrganizationPool.objects.create(tenant=tenant, code="pool-publication", name="Pool Publication")
    database = Database.objects.create(
        tenant=tenant,
        name="pool-publication-db",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="admin",
        password="secret",
    )
    return {
        "tenant": tenant,
        "pool": pool,
        "database": database,
    }


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


def _attach_workflow_execution_to_run(*, run: PoolRun) -> None:
    template = WorkflowTemplate.objects.create(
        name=f"pool-publication-{run.id.hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "publication_odata",
                    "name": "Publication OData",
                    "type": "operation",
                    "template_id": "pool.publication_odata",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    execution = template.create_execution(
        {
            "pool_run_id": str(run.id),
            "approval_required": run.mode == "safe",
            "approval_state": "approved",
            "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
            "publication_step_state": "queued",
        },
        tenant=run.tenant,
        execution_consumer="pools",
    )
    run.workflow_execution_id = execution.id
    run.workflow_status = execution.status
    run.execution_backend = "workflow_core"
    run.workflow_template_name = template.name
    run.save(
        update_fields=[
            "workflow_execution_id",
            "workflow_status",
            "execution_backend",
            "workflow_template_name",
            "updated_at",
        ]
    )


@pytest.mark.django_db
def test_publish_run_documents_success_with_posting(publication_context: dict[str, object]) -> None:
    tenant = publication_context["tenant"]
    pool = publication_context["pool"]
    database = publication_context["database"]
    run = _create_validated_run(tenant=tenant, pool=pool)
    _attach_workflow_execution_to_run(run=run)
    entity_name = "Document_IntercompanyPoolDistribution"
    client = MagicMock()
    client.get_entities.return_value = []
    client.create_entity.return_value = {"Ref_Key": "550e8400-e29b-41d4-a716-446655440000"}

    with patch("apps.intercompany_pools.publication.session_manager.get_client", return_value=client):
        summary = publish_run_documents(
            run=run,
            entity_name=entity_name,
            documents_by_database={str(database.id): [{"Amount": "100.00"}]},
        )

    assert summary.total_targets == 1
    assert summary.succeeded_targets == 1
    assert summary.failed_targets == 0

    run_state = PoolRun.objects.filter(id=run.id).values("status", "publication_summary").get()
    assert run_state["status"] == PoolRun.STATUS_PUBLISHED
    assert run_state["publication_summary"]["succeeded_targets"] == 1
    assert run_state["publication_summary"]["failed_targets"] == 0

    create_payload = client.create_entity.call_args.args[1]
    assert create_payload["Amount"] == "100.00"
    assert create_payload["ExternalRunKey"].startswith("runkey-")
    assert len(create_payload["ExternalRunKey"]) == len("runkey-") + 32
    client.update_entity.assert_called_once_with(
        entity_name,
        "guid'550e8400-e29b-41d4-a716-446655440000'",
        {"Posted": True},
    )

    attempt = PoolPublicationAttempt.objects.get(run=run, target_database=database)
    assert attempt.status == PoolPublicationAttemptStatus.SUCCESS
    assert attempt.posted is True
    assert attempt.external_document_identity == "550e8400-e29b-41d4-a716-446655440000"
    assert attempt.identity_strategy == "guid_from_odata"

    event_types = list(PoolRunAuditEvent.objects.filter(run=run).values_list("event_type", flat=True))
    assert "run.publication_attempt_success" in event_types
    assert "run.published" in event_types

    workflow_execution = WorkflowExecution.objects.get(id=run.workflow_execution_id)
    assert workflow_execution.input_context.get("publication_step_state") == "completed"


@pytest.mark.django_db
def test_publish_run_documents_failed_with_retries(publication_context: dict[str, object]) -> None:
    tenant = publication_context["tenant"]
    pool = publication_context["pool"]
    database = publication_context["database"]
    run = _create_validated_run(tenant=tenant, pool=pool)
    client = MagicMock()
    client.get_entities.side_effect = ODataRequestError("temporary OData error", status_code=503)

    with patch("apps.intercompany_pools.publication.session_manager.get_client", return_value=client):
        summary = publish_run_documents(
            run=run,
            entity_name="Document_IntercompanyPoolDistribution",
            documents_by_database={str(database.id): [{"Amount": "100.00"}]},
            max_attempts=3,
            retry_interval_seconds=0,
        )

    assert summary.succeeded_targets == 0
    assert summary.failed_targets == 1

    run_state = PoolRun.objects.filter(id=run.id).values("status", "last_error").get()
    assert run_state["status"] == PoolRun.STATUS_FAILED
    assert run_state["last_error"] == "publication_failed_all_targets"

    attempts = list(
        PoolPublicationAttempt.objects.filter(run=run, target_database=database).order_by("attempt_number")
    )
    assert len(attempts) == 3
    assert [attempt.attempt_number for attempt in attempts] == [1, 2, 3]
    assert all(attempt.status == PoolPublicationAttemptStatus.FAILED for attempt in attempts)
    assert attempts[0].http_status == 503
    assert attempts[-1].error_code == "ODataRequestError"

    failed_events = list(
        PoolRunAuditEvent.objects.filter(run=run, event_type="run.publication_attempt_failed")
    )
    assert len(failed_events) == 3


@pytest.mark.django_db
def test_publish_run_documents_marks_partial_success_for_mixed_targets(
    publication_context: dict[str, object],
) -> None:
    tenant = publication_context["tenant"]
    pool = publication_context["pool"]
    db_success = publication_context["database"]
    db_failed = Database.objects.create(
        tenant=tenant,
        name="pool-publication-db-failed",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="admin",
        password="secret",
    )
    run = _create_validated_run(tenant=tenant, pool=pool)

    success_client = MagicMock()
    success_client.get_entities.return_value = []
    success_client.create_entity.return_value = {"Ref_Key": "11111111-1111-1111-1111-111111111111"}

    failed_client = MagicMock()
    failed_client.get_entities.side_effect = ODataRequestError("target down", status_code=502)

    def _get_client(*, base_id: str, **kwargs):  # noqa: ARG001
        if base_id == str(db_success.id):
            return success_client
        if base_id == str(db_failed.id):
            return failed_client
        raise AssertionError(f"Unexpected base_id: {base_id}")

    with patch("apps.intercompany_pools.publication.session_manager.get_client", side_effect=_get_client):
        summary = publish_run_documents(
            run=run,
            entity_name="Document_IntercompanyPoolDistribution",
            documents_by_database={
                str(db_success.id): [{"Amount": "60.00"}],
                str(db_failed.id): [{"Amount": "40.00"}],
            },
            max_attempts=1,
        )

    assert summary.total_targets == 2
    assert summary.succeeded_targets == 1
    assert summary.failed_targets == 1

    run_state = PoolRun.objects.filter(id=run.id).values("status", "publication_summary").get()
    assert run_state["status"] == PoolRun.STATUS_PARTIAL_SUCCESS
    assert run_state["publication_summary"]["succeeded_targets"] == 1
    assert run_state["publication_summary"]["failed_targets"] == 1

    assert PoolPublicationAttempt.objects.filter(
        run=run,
        target_database=db_success,
        status=PoolPublicationAttemptStatus.SUCCESS,
    ).exists()
    assert PoolPublicationAttempt.objects.filter(
        run=run,
        target_database=db_failed,
        status=PoolPublicationAttemptStatus.FAILED,
    ).exists()


@pytest.mark.django_db
def test_retry_failed_run_documents_retries_only_failed_targets(
    publication_context: dict[str, object],
) -> None:
    tenant = publication_context["tenant"]
    pool = publication_context["pool"]
    db_success = publication_context["database"]
    db_failed = Database.objects.create(
        tenant=tenant,
        name="pool-publication-db-failed-retry",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="admin",
        password="secret",
    )
    run = _create_validated_run(tenant=tenant, pool=pool)
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
    first_state = PoolRun.objects.filter(id=run.id).values("status").get()
    assert first_state["status"] == PoolRun.STATUS_PARTIAL_SUCCESS

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
        retry_summary = retry_failed_run_documents(
            run=run,
            entity_name=entity_name,
            documents_by_database={
                str(db_success.id): [{"Amount": "999.00"}],
                str(db_failed.id): [{"Amount": "40.00"}],
            },
            max_attempts=1,
        )

    assert retry_summary.total_targets == 1
    assert retry_summary.succeeded_targets == 1
    assert retry_summary.failed_targets == 0

    final_state = PoolRun.objects.filter(id=run.id).values("status").get()
    assert final_state["status"] == PoolRun.STATUS_PUBLISHED
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
def test_publish_run_documents_default_policy_retries_up_to_max_attempts(
    publication_context: dict[str, object],
) -> None:
    tenant = publication_context["tenant"]
    pool = publication_context["pool"]
    database = publication_context["database"]
    run = _create_validated_run(tenant=tenant, pool=pool)
    client = MagicMock()
    client.get_entities.side_effect = ODataRequestError("temporary OData error", status_code=503)

    with patch("apps.intercompany_pools.publication.session_manager.get_client", return_value=client):
        summary = publish_run_documents(
            run=run,
            entity_name="Document_IntercompanyPoolDistribution",
            documents_by_database={str(database.id): [{"Amount": "100.00"}]},
        )

    assert summary.max_attempts == MAX_PUBLICATION_ATTEMPTS
    assert summary.failed_targets == 1
    attempts = list(
        PoolPublicationAttempt.objects.filter(run=run, target_database=database).order_by("attempt_number")
    )
    assert len(attempts) == MAX_PUBLICATION_ATTEMPTS
    assert attempts[-1].attempt_number == MAX_PUBLICATION_ATTEMPTS
    assert all(attempt.status == PoolPublicationAttemptStatus.FAILED for attempt in attempts)


@pytest.mark.django_db
def test_publish_run_documents_retry_interval_sleeps_between_attempts(
    publication_context: dict[str, object],
) -> None:
    tenant = publication_context["tenant"]
    pool = publication_context["pool"]
    database = publication_context["database"]
    run = _create_validated_run(tenant=tenant, pool=pool)
    client = MagicMock()
    client.get_entities.side_effect = [
        ODataRequestError("temporary-1", status_code=503),
        ODataRequestError("temporary-2", status_code=503),
        [],
    ]
    client.create_entity.return_value = {"Ref_Key": "33333333-3333-3333-3333-333333333333"}

    with patch("apps.intercompany_pools.publication.session_manager.get_client", return_value=client):
        with patch("apps.intercompany_pools.publication.time.sleep") as sleep_mock:
            summary = publish_run_documents(
                run=run,
                entity_name="Document_IntercompanyPoolDistribution",
                documents_by_database={str(database.id): [{"Amount": "100.00"}]},
                max_attempts=3,
                retry_interval_seconds=7,
            )

    assert summary.succeeded_targets == 1
    assert summary.failed_targets == 0
    sleep_mock.assert_called_with(7)
    assert sleep_mock.call_count == 2
    attempts = list(
        PoolPublicationAttempt.objects.filter(run=run, target_database=database).order_by("attempt_number")
    )
    assert [attempt.status for attempt in attempts] == [
        PoolPublicationAttemptStatus.FAILED,
        PoolPublicationAttemptStatus.FAILED,
        PoolPublicationAttemptStatus.SUCCESS,
    ]


@pytest.mark.django_db
def test_publish_run_documents_validates_retry_policy_bounds(
    publication_context: dict[str, object],
) -> None:
    tenant = publication_context["tenant"]
    pool = publication_context["pool"]
    database = publication_context["database"]
    run = _create_validated_run(tenant=tenant, pool=pool)

    with pytest.raises(ValueError, match="max_attempts must be in range"):
        publish_run_documents(
            run=run,
            entity_name="Document_IntercompanyPoolDistribution",
            documents_by_database={str(database.id): [{"Amount": "100.00"}]},
            max_attempts=MAX_PUBLICATION_ATTEMPTS + 1,
        )

    with pytest.raises(ValueError, match="retry_interval_seconds must be <="):
        publish_run_documents(
            run=run,
            entity_name="Document_IntercompanyPoolDistribution",
            documents_by_database={str(database.id): [{"Amount": "100.00"}]},
            retry_interval_seconds=MAX_RETRY_INTERVAL_SECONDS + 1,
        )


@pytest.mark.django_db
def test_publish_run_documents_requires_validated_status(publication_context: dict[str, object]) -> None:
    tenant = publication_context["tenant"]
    pool = publication_context["pool"]
    database = publication_context["database"]
    draft_run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
    )

    with pytest.raises(ValidationError, match="Run must be in"):
        publish_run_documents(
            run=draft_run,
            entity_name="Document_IntercompanyPoolDistribution",
            documents_by_database={str(database.id): [{"Amount": "100.00"}]},
        )
