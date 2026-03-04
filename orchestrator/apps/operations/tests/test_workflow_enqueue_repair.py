from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import transaction
from django.utils import timezone

from apps.operations.models import BatchOperation, WorkflowEnqueueOutbox
from apps.operations.services import OperationsService
from apps.operations.workflow_enqueue_repair import run_workflow_enqueue_detect_repair
from apps.templates.workflow.models import WorkflowTemplate, WorkflowType


def _create_pending_workflow_outbox_entry(*, execution_id: str) -> WorkflowEnqueueOutbox:
    message = OperationsService._build_execution_envelope(
        operation_id=execution_id,
        operation_type="execute_workflow",
        entity="Workflow",
        target_databases=[],
        payload_data={"execution_id": execution_id},
        execution_config={"idempotency_key": execution_id},
        metadata={"created_by": "repair-test"},
    )
    with transaction.atomic():
        OperationsService._upsert_workflow_root_operation(
            execution_id=execution_id,
            message_payload=message,
        )
        outbox_entry, _created = OperationsService._enqueue_workflow_outbox_intent(
            operation_id=execution_id,
            message_payload=message,
            stream_name="commands:worker:workflows",
        )

    outbox_entry.dispatch_attempts = 5
    outbox_entry.next_retry_at = timezone.now() - timedelta(minutes=1)
    outbox_entry.save(update_fields=["dispatch_attempts", "next_retry_at", "updated_at"])
    return outbox_entry


def _create_workflow_execution_without_root_projection() -> str:
    template = WorkflowTemplate.objects.create(
        name=f"repair-workflow-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node 1",
                    "type": "operation",
                    "template_id": "tpl-repair",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    execution = template.create_execution(
        {"executed_by": "repair-user"},
        execution_consumer="workflows",
    )
    execution_id = str(execution.id)
    assert BatchOperation.objects.filter(id=execution_id).count() == 0
    return execution_id


@pytest.mark.django_db
def test_run_workflow_enqueue_detect_repair_relays_stuck_outbox_and_backfills_missing_root():
    relay_execution_id = str(uuid4())
    outbox_entry = _create_pending_workflow_outbox_entry(execution_id=relay_execution_id)
    missing_root_execution_id = _create_workflow_execution_without_root_projection()

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher"),
        patch("apps.operations.workflow_enqueue_repair.event_publisher") as mock_repair_event_publisher,
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123999-0"

        report = run_workflow_enqueue_detect_repair(
            relay_batch_size=50,
            stuck_age_seconds=30,
            retry_saturation_attempts=5,
            root_backfill_sla_seconds=3600,
            root_backfill_chunk_size=200,
            diagnostic_sample_limit=10,
        )

    assert report.status == "ok"
    assert report.stuck_outbox_candidates_before >= 1
    assert report.relay_claimed >= 1
    assert report.relay_dispatched >= 1
    assert report.relay_failed == 0
    assert report.terminal_failed == 0
    assert report.diagnostic_events_published == 0
    assert report.stuck_outbox_candidates_after == 0
    assert report.root_missing_before >= 1
    assert report.root_repaired >= 1
    assert report.root_repair_failed == 0
    mock_repair_event_publisher.publish.assert_not_called()

    outbox_entry.refresh_from_db()
    assert outbox_entry.status == WorkflowEnqueueOutbox.STATUS_DISPATCHED
    assert outbox_entry.stream_message_id == "1702389123999-0"
    assert BatchOperation.objects.get(id=relay_execution_id).status == BatchOperation.STATUS_QUEUED
    assert BatchOperation.objects.filter(id=missing_root_execution_id).exists()

    payload = report.to_dict()
    assert payload["schema_version"] == "workflow_enqueue_repair.v1"
    assert "stuck_outbox_before" in payload["diagnostics"]
    assert "root_backfill" in payload["diagnostics"]
    assert payload["terminal_failed"]["count"] == 0
    assert payload["terminal_failed"]["diagnostic_events_published"] == 0


@pytest.mark.django_db
def test_run_workflow_enqueue_detect_repair_marks_follow_up_when_stuck_outbox_remains():
    outbox_entry = _create_pending_workflow_outbox_entry(execution_id=str(uuid4()))

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher"),
        patch("apps.operations.workflow_enqueue_repair.event_publisher") as mock_repair_event_publisher,
    ):
        mock_redis_client.enqueue_operation_stream.side_effect = RuntimeError("redis down")

        report = run_workflow_enqueue_detect_repair(
            relay_batch_size=10,
            stuck_age_seconds=30,
            retry_saturation_attempts=1,
            root_backfill_sla_seconds=3600,
            root_backfill_chunk_size=100,
            diagnostic_sample_limit=5,
        )

    assert report.status == "needs_follow_up"
    assert report.stuck_outbox_candidates_before >= 1
    assert report.relay_failed >= 1
    assert report.terminal_failed >= 1
    assert report.diagnostic_events_published >= 1
    outbox_entry.refresh_from_db()
    assert outbox_entry.status == WorkflowEnqueueOutbox.STATUS_FAILED
    assert outbox_entry.last_error_code == "WORKFLOW_ENQUEUE_STUCK_OUTBOX_FAILED"
    assert report.diagnostics["terminal_failed_outbox"]
    mock_repair_event_publisher.publish.assert_called()
