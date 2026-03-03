import pytest
from datetime import timedelta, timezone as dt_timezone
from unittest.mock import patch
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.operations.factory import BatchOperationFactory
from apps.operations.models import BatchOperation, WorkflowEnqueueOutbox
from apps.operations.services import OperationsService
from apps.templates.workflow.models import WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


def _create_workflow_execution_for_enqueue(
    *,
    input_context: dict,
    execution_consumer: str = "workflows",
) -> str:
    template = WorkflowTemplate.objects.create(
        name=f"workflow-enqueue-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node 1",
                    "type": "operation",
                    "template_id": "tpl-enqueue",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    tenant = None
    if execution_consumer == "pools":
        tenant = Tenant.objects.create(
            slug=f"tenant-enqueue-{uuid4().hex[:8]}",
            name="Tenant Enqueue",
        )
    execution = template.create_execution(
        input_context,
        tenant=tenant,
        execution_consumer=execution_consumer,
    )
    return str(execution.id)


@pytest.mark.django_db
def test_enqueue_operation_redis_failure_does_not_set_queued(operation_template, multiple_databases):
    operation = BatchOperationFactory.create(
        template=operation_template,
        rendered_data={"data": {}, "filters": {}, "options": {}},
        target_databases=[str(db.id) for db in multiple_databases],
        created_by="test",
    )
    assert operation.status == BatchOperation.STATUS_PENDING

    with (
        patch("apps.operations.services.operations_service.core.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.core.event_publisher") as mock_event_publisher,
        patch("apps.operations.services.operations_service.core.flow_publisher") as mock_flow_publisher,
    ):
        mock_redis_client.acquire_enqueue_lock.return_value = True
        mock_redis_client.enqueue_operation_stream.side_effect = Exception("redis down")

        result = OperationsService.enqueue_operation(str(operation.id))
        assert result.success is False

        operation.refresh_from_db()
        assert operation.status == BatchOperation.STATUS_PENDING

        mock_event_publisher.publish.assert_not_called()
        mock_flow_publisher.publish_flow.assert_not_called()
        mock_redis_client.release_enqueue_lock.assert_called_once()


@pytest.mark.django_db
def test_enqueue_operation_emits_default_qos_lane_metadata(operation_template, multiple_databases):
    operation = BatchOperationFactory.create(
        template=operation_template,
        rendered_data={"data": {}, "filters": {}, "options": {}},
        target_databases=[str(db.id) for db in multiple_databases],
        created_by="test",
    )

    with (
        patch("apps.operations.services.operations_service.core.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.core.event_publisher") as mock_event_publisher,
        patch("apps.operations.services.operations_service.core.flow_publisher") as mock_flow_publisher,
    ):
        mock_redis_client.acquire_enqueue_lock.return_value = True
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123222-0"

        result = OperationsService.enqueue_operation(str(operation.id))
        assert result.success is True

    publish_kwargs = mock_event_publisher.publish.call_args.kwargs
    assert publish_kwargs["root_operation_id"] == str(operation.id)
    assert publish_kwargs["execution_consumer"] == "operations"
    assert publish_kwargs["lane"] == "operations"

    flow_metadata = mock_flow_publisher.publish_flow.call_args.kwargs["metadata"]
    assert flow_metadata["root_operation_id"] == str(operation.id)
    assert flow_metadata["execution_consumer"] == "operations"
    assert flow_metadata["lane"] == "operations"


@pytest.mark.django_db
def test_enqueue_operation_preserves_explicit_lane_metadata(operation_template, multiple_databases):
    operation = BatchOperationFactory.create(
        template=operation_template,
        rendered_data={"data": {}, "filters": {}, "options": {}},
        target_databases=[str(db.id) for db in multiple_databases],
        created_by="test",
    )
    operation.metadata = {
        "workflow_execution_id": "wf-123",
        "node_id": "approval",
        "root_operation_id": "wf-123",
        "execution_consumer": "pools",
        "lane": "workflows",
        "trace_id": "trace-123",
    }
    operation.save(update_fields=["metadata", "updated_at"])

    with (
        patch("apps.operations.services.operations_service.core.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.core.event_publisher") as mock_event_publisher,
        patch("apps.operations.services.operations_service.core.flow_publisher") as mock_flow_publisher,
    ):
        mock_redis_client.acquire_enqueue_lock.return_value = True
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123333-0"

        result = OperationsService.enqueue_operation(str(operation.id))
        assert result.success is True

    publish_kwargs = mock_event_publisher.publish.call_args.kwargs
    assert publish_kwargs["workflow_execution_id"] == "wf-123"
    assert publish_kwargs["node_id"] == "approval"
    assert publish_kwargs["trace_id"] == "trace-123"
    assert publish_kwargs["root_operation_id"] == "wf-123"
    assert publish_kwargs["execution_consumer"] == "pools"
    assert publish_kwargs["lane"] == "workflows"

    flow_metadata = mock_flow_publisher.publish_flow.call_args.kwargs["metadata"]
    assert flow_metadata["workflow_execution_id"] == "wf-123"
    assert flow_metadata["node_id"] == "approval"
    assert flow_metadata["trace_id"] == "trace-123"
    assert flow_metadata["root_operation_id"] == "wf-123"
    assert flow_metadata["execution_consumer"] == "pools"
    assert flow_metadata["lane"] == "workflows"


@pytest.mark.django_db
def test_enqueue_workflow_execution_returns_error_on_redis_failure():
    execution_id = str(uuid4())

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        mock_redis_client.enqueue_operation_stream.side_effect = Exception("redis down")

        result = OperationsService.enqueue_workflow_execution(execution_id=execution_id)
        assert result.success is False
        assert result.status == "error"
        mock_redis_client.enqueue_operation_stream.assert_called_once()
        assert mock_redis_client.enqueue_operation_stream.call_args.kwargs == {
            "stream_name": str(mock_redis_client.STREAM_WORKFLOWS),
        }
        outbox = WorkflowEnqueueOutbox.objects.get(operation_id=execution_id)
        assert outbox.status == WorkflowEnqueueOutbox.STATUS_PENDING
        assert outbox.stream_message_id == ""
        root = BatchOperation.objects.get(id=execution_id)
        assert root.status == BatchOperation.STATUS_PENDING
        assert root.operation_type == "execute_workflow"
        assert root.metadata.get("workflow_execution_id") == execution_id
        assert root.metadata.get("root_operation_id") == execution_id

        mock_event_publisher.publish.assert_not_called()


@pytest.mark.django_db
def test_enqueue_workflow_execution_propagates_custom_idempotency_key():
    execution_id = str(uuid4())
    custom_key = "pool-run-idempotency-key"

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123456-0"

        result = OperationsService.enqueue_workflow_execution(
            execution_id=execution_id,
            workflow_config={"idempotency_key": custom_key},
        )

        assert result.success is True
        mock_redis_client.enqueue_operation_stream.assert_called_once()
        message = mock_redis_client.enqueue_operation_stream.call_args.args[0]
        assert message["execution_config"]["idempotency_key"] == custom_key
        assert message["metadata"]["workflow_execution_id"] == execution_id
        assert message["metadata"]["root_operation_id"] == execution_id
        assert message["metadata"]["execution_consumer"] == "workflows"
        assert message["metadata"]["lane"] == "workflows"
        outbox = WorkflowEnqueueOutbox.objects.get(operation_id=execution_id)
        assert outbox.status == WorkflowEnqueueOutbox.STATUS_DISPATCHED
        assert outbox.stream_message_id == "1702389123456-0"
        root = BatchOperation.objects.get(id=execution_id)
        assert root.status == BatchOperation.STATUS_QUEUED
        assert root.config.get("idempotency_key") == custom_key
        mock_event_publisher.publish.assert_called_once()


@pytest.mark.django_db
def test_enqueue_workflow_execution_preserves_consumer_and_correlation_metadata():
    execution_id = str(uuid4())

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123456-0"

        result = OperationsService.enqueue_workflow_execution(
            execution_id=execution_id,
            workflow_config={
                "execution_consumer": "pools",
                "node_id": "approval_gate",
                "trace_id": "trace-123",
            },
        )

        assert result.success is True
        message = mock_redis_client.enqueue_operation_stream.call_args.args[0]
        assert message["metadata"]["workflow_execution_id"] == execution_id
        assert message["metadata"]["node_id"] == "approval_gate"
        assert message["metadata"]["root_operation_id"] == execution_id
        assert message["metadata"]["execution_consumer"] == "pools"
        assert message["metadata"]["lane"] == "workflows"
        assert message["metadata"]["trace_id"] == "trace-123"
        root = BatchOperation.objects.get(id=execution_id)
        assert root.status == BatchOperation.STATUS_QUEUED
        assert root.metadata.get("execution_consumer") == "pools"
        assert root.metadata.get("node_id") == "approval_gate"
        assert root.metadata.get("trace_id") == "trace-123"
        mock_event_publisher.publish.assert_called_once()


@pytest.mark.django_db
def test_enqueue_workflow_execution_sync_contract_persists_scheduling_metadata():
    execution_id = str(uuid4())
    sync_job_id = str(uuid4())
    deadline_at = (
        timezone.now().astimezone(dt_timezone.utc) + timedelta(minutes=5)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123666-0"

        result = OperationsService.enqueue_workflow_execution(
            execution_id=execution_id,
            workflow_config={
                "sync_job_id": sync_job_id,
                "execution_consumer": "pools",
                "priority": "p2",
                "role": "inbound",
                "server_affinity": "srv-1c-a",
                "deadline_at": deadline_at,
            },
        )

        assert result.success is True
        message = mock_redis_client.enqueue_operation_stream.call_args.args[0]
        assert message["payload"]["data"]["priority"] == "p2"
        assert message["payload"]["data"]["role"] == "inbound"
        assert message["payload"]["data"]["server_affinity"] == "srv-1c-a"
        assert message["payload"]["data"]["deadline_at"] == deadline_at
        assert message["execution_config"]["priority"] == "p2"
        assert message["metadata"]["priority"] == "p2"
        assert message["metadata"]["role"] == "inbound"
        assert message["metadata"]["server_affinity"] == "srv-1c-a"
        assert message["metadata"]["deadline_at"] == deadline_at

        publish_kwargs = mock_event_publisher.publish.call_args.kwargs
        assert publish_kwargs["priority"] == "p2"
        assert publish_kwargs["role"] == "inbound"
        assert publish_kwargs["server_affinity"] == "srv-1c-a"
        assert publish_kwargs["deadline_at"] == deadline_at

    root = BatchOperation.objects.get(id=execution_id)
    assert root.status == BatchOperation.STATUS_QUEUED
    assert root.config.get("priority") == "p2"
    assert root.metadata.get("priority") == "p2"
    assert root.metadata.get("role") == "inbound"
    assert root.metadata.get("server_affinity") == "srv-1c-a"
    assert root.metadata.get("deadline_at") == deadline_at


@pytest.mark.django_db
def test_enqueue_workflow_execution_sync_contract_invalid_rejects_without_side_effects():
    execution_id = str(uuid4())
    sync_job_id = str(uuid4())
    deadline_at = (
        timezone.now().astimezone(dt_timezone.utc) + timedelta(minutes=5)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        result = OperationsService.enqueue_workflow_execution(
            execution_id=execution_id,
            workflow_config={
                "sync_job_id": sync_job_id,
                "execution_consumer": "pools",
                "priority": "p2",
                "role": "inbound",
                "deadline_at": deadline_at,
            },
        )

    assert result.success is False
    assert result.error_code == "SCHEDULING_CONTRACT_INVALID"
    mock_redis_client.enqueue_operation_stream.assert_not_called()
    mock_event_publisher.publish.assert_not_called()
    assert WorkflowEnqueueOutbox.objects.filter(operation_id=execution_id).count() == 0
    assert BatchOperation.objects.filter(id=execution_id).count() == 0


@pytest.mark.django_db
def test_enqueue_workflow_execution_sync_contract_past_deadline_rejects_without_side_effects():
    execution_id = str(uuid4())
    sync_job_id = str(uuid4())
    deadline_at = (
        timezone.now().astimezone(dt_timezone.utc) - timedelta(seconds=1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        result = OperationsService.enqueue_workflow_execution(
            execution_id=execution_id,
            workflow_config={
                "sync_job_id": sync_job_id,
                "execution_consumer": "pools",
                "priority": "p2",
                "role": "inbound",
                "server_affinity": "srv-1c-a",
                "deadline_at": deadline_at,
            },
        )

    assert result.success is False
    assert result.error_code == "SCHEDULING_DEADLINE_INVALID"
    mock_redis_client.enqueue_operation_stream.assert_not_called()
    mock_event_publisher.publish.assert_not_called()
    assert WorkflowEnqueueOutbox.objects.filter(operation_id=execution_id).count() == 0
    assert BatchOperation.objects.filter(id=execution_id).count() == 0


@pytest.mark.django_db
def test_enqueue_workflow_execution_uses_execution_actor_for_root_created_by():
    execution_id = _create_workflow_execution_for_enqueue(
        input_context={"executed_by": "workflow-owner"},
    )

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher"),
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123555-1"

        result = OperationsService.enqueue_workflow_execution(execution_id=execution_id)

        assert result.success is True
        message = mock_redis_client.enqueue_operation_stream.call_args.args[0]
        assert message["metadata"]["created_by"] == "workflow-owner"

    root = BatchOperation.objects.get(id=execution_id)
    assert root.created_by == "workflow-owner"
    assert root.metadata.get("created_by") == "workflow-owner"


@pytest.mark.django_db
def test_enqueue_workflow_execution_uses_publication_actor_for_root_created_by():
    execution_id = _create_workflow_execution_for_enqueue(
        input_context={
            "publication_auth": {
                "strategy": "actor",
                "actor_username": "pool-operator",
                "source": "run.create",
            }
        },
        execution_consumer="pools",
    )

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher"),
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123555-2"

        result = OperationsService.enqueue_workflow_execution(
            execution_id=execution_id,
            workflow_config={"execution_consumer": "pools"},
        )

        assert result.success is True
        message = mock_redis_client.enqueue_operation_stream.call_args.args[0]
        assert message["metadata"]["created_by"] == "pool-operator"

    root = BatchOperation.objects.get(id=execution_id)
    assert root.created_by == "pool-operator"
    assert root.metadata.get("created_by") == "pool-operator"


@pytest.mark.django_db
def test_enqueue_workflow_execution_reuses_existing_outbox_for_same_execution_id():
    execution_id = str(uuid4())

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123456-0"

        first = OperationsService.enqueue_workflow_execution(execution_id=execution_id)
        second = OperationsService.enqueue_workflow_execution(execution_id=execution_id)

        assert first.success is True
        assert second.success is True
        assert BatchOperation.objects.filter(id=execution_id).count() == 1
        assert BatchOperation.objects.get(id=execution_id).status == BatchOperation.STATUS_QUEUED
        assert WorkflowEnqueueOutbox.objects.filter(operation_id=execution_id).count() == 1
        assert mock_redis_client.enqueue_operation_stream.call_count == 1
        mock_event_publisher.publish.assert_called_once()


@pytest.mark.django_db
def test_workflow_enqueue_outbox_commit_dispatches_to_stream():
    execution_id = str(uuid4())
    message = OperationsService._build_execution_envelope(
        operation_id=execution_id,
        operation_type="execute_workflow",
        entity="Workflow",
        target_databases=[],
        payload_data={"execution_id": execution_id},
        execution_config={"idempotency_key": execution_id},
        metadata={"created_by": "test"},
    )

    with patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client:
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123555-0"

        with transaction.atomic():
            root, root_created = OperationsService._upsert_workflow_root_operation(
                execution_id=execution_id,
                message_payload=message,
            )
            assert root_created is True
            assert root.id == execution_id
            assert root.status == BatchOperation.STATUS_PENDING

            outbox_entry, created = OperationsService._enqueue_workflow_outbox_intent(
                operation_id=execution_id,
                message_payload=message,
                stream_name=mock_redis_client.STREAM_WORKFLOWS,
            )
            assert created is True

        dispatch = OperationsService._dispatch_workflow_outbox_entry(outbox_id=outbox_entry.id)
        if dispatch["success"]:
            OperationsService._mark_workflow_root_operation_queued(execution_id=execution_id)

    assert dispatch["success"] is True
    assert dispatch["dispatched_now"] is True
    assert dispatch["stream_message_id"] == "1702389123555-0"
    mock_redis_client.enqueue_operation_stream.assert_called_once()

    outbox = WorkflowEnqueueOutbox.objects.get(operation_id=execution_id)
    assert outbox.status == WorkflowEnqueueOutbox.STATUS_DISPATCHED
    assert outbox.stream_message_id == "1702389123555-0"
    root = BatchOperation.objects.get(id=execution_id)
    assert root.status == BatchOperation.STATUS_QUEUED
    assert root.metadata.get("workflow_execution_id") == execution_id


@pytest.mark.django_db
def test_dispatch_pending_workflow_enqueue_outbox_relays_after_inline_dispatch_failure():
    execution_id = str(uuid4())

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        mock_redis_client.enqueue_operation_stream.side_effect = [Exception("redis down"), "1702389123555-1"]

        enqueue_result = OperationsService.enqueue_workflow_execution(execution_id=execution_id)
        assert enqueue_result.success is False
        assert enqueue_result.error_code == "ENQUEUE_FAILED"

        outbox = WorkflowEnqueueOutbox.objects.get(operation_id=execution_id)
        assert outbox.status == WorkflowEnqueueOutbox.STATUS_PENDING
        outbox.next_retry_at = timezone.now() - timedelta(seconds=1)
        outbox.save(update_fields=["next_retry_at", "updated_at"])

        stats = OperationsService.dispatch_pending_workflow_enqueue_outbox(batch_size=10)

    assert stats["claimed"] == 1
    assert stats["dispatched"] == 1
    assert stats["failed"] == 0
    assert mock_redis_client.enqueue_operation_stream.call_count == 2
    assert mock_event_publisher.publish.call_count == 1

    outbox.refresh_from_db()
    assert outbox.status == WorkflowEnqueueOutbox.STATUS_DISPATCHED
    assert outbox.stream_message_id == "1702389123555-1"
    assert outbox.dispatch_attempts == 2

    root = BatchOperation.objects.get(id=execution_id)
    assert root.status == BatchOperation.STATUS_QUEUED


@pytest.mark.django_db
def test_dispatch_pending_workflow_enqueue_outbox_skips_not_due_entries():
    execution_id = str(uuid4())
    message = OperationsService._build_execution_envelope(
        operation_id=execution_id,
        operation_type="execute_workflow",
        entity="Workflow",
        target_databases=[],
        payload_data={"execution_id": execution_id},
        execution_config={"idempotency_key": execution_id},
        metadata={"created_by": "test"},
    )

    with transaction.atomic():
        OperationsService._upsert_workflow_root_operation(
            execution_id=execution_id,
            message_payload=message,
        )
        outbox_entry, created = OperationsService._enqueue_workflow_outbox_intent(
            operation_id=execution_id,
            message_payload=message,
            stream_name="commands:worker:workflows",
        )
        assert created is True

    outbox_entry.next_retry_at = timezone.now() + timedelta(minutes=1)
    outbox_entry.save(update_fields=["next_retry_at", "updated_at"])

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        stats = OperationsService.dispatch_pending_workflow_enqueue_outbox(
            batch_size=10,
            now=timezone.now(),
        )

    assert stats["claimed"] == 0
    assert stats["dispatched"] == 0
    assert stats["failed"] == 0
    mock_redis_client.enqueue_operation_stream.assert_not_called()
    mock_event_publisher.publish.assert_not_called()
    outbox_entry.refresh_from_db()
    assert outbox_entry.status == WorkflowEnqueueOutbox.STATUS_PENDING
    assert BatchOperation.objects.get(id=execution_id).status == BatchOperation.STATUS_PENDING


@pytest.mark.django_db
def test_dispatch_pending_workflow_enqueue_outbox_records_sync_backlog_by_scheduling_dimensions():
    execution_id = str(uuid4())
    message = OperationsService._build_execution_envelope(
        operation_id=execution_id,
        operation_type="execute_workflow",
        entity="Workflow",
        target_databases=[],
        payload_data={"execution_id": execution_id},
        execution_config={"idempotency_key": execution_id},
        metadata={
            "created_by": "test",
            "priority": "p1",
            "role": "reconcile",
            "server_affinity": "srv-a",
        },
    )

    with transaction.atomic():
        OperationsService._upsert_workflow_root_operation(
            execution_id=execution_id,
            message_payload=message,
        )
        outbox_entry, created = OperationsService._enqueue_workflow_outbox_intent(
            operation_id=execution_id,
            message_payload=message,
            stream_name="commands:worker:workflows",
        )
        assert created is True

    outbox_entry.dispatch_attempts = 2
    outbox_entry.next_retry_at = timezone.now() + timedelta(minutes=5)
    outbox_entry.save(update_fields=["dispatch_attempts", "next_retry_at", "updated_at"])

    with (
        patch(
            "apps.operations.services.operations_service.workflow.set_pool_master_data_sync_queue_backlog_by_scheduling"
        ) as metrics_mock,
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher") as mock_event_publisher,
    ):
        stats = OperationsService.dispatch_pending_workflow_enqueue_outbox(
            batch_size=10,
            now=timezone.now(),
        )

    assert stats["claimed"] == 0
    assert stats["dispatched"] == 0
    assert stats["failed"] == 0
    mock_redis_client.enqueue_operation_stream.assert_not_called()
    mock_event_publisher.publish.assert_not_called()

    metrics_mock.assert_called_once()
    metric_rows = metrics_mock.call_args.kwargs["rows"]
    assert len(metric_rows) == 1
    assert metric_rows[0]["status"] == "retrying"
    assert metric_rows[0]["priority"] == "p1"
    assert metric_rows[0]["role"] == "reconcile"
    assert metric_rows[0]["server_affinity"] == "srv-a"
    assert metric_rows[0]["backlog_total"] == 1.0
    assert float(metric_rows[0]["lag_seconds"]) >= 0.0


@pytest.mark.django_db
def test_workflow_enqueue_outbox_rollback_does_not_persist_or_publish():
    execution_id = str(uuid4())
    message = OperationsService._build_execution_envelope(
        operation_id=execution_id,
        operation_type="execute_workflow",
        entity="Workflow",
        target_databases=[],
        payload_data={"execution_id": execution_id},
        execution_config={"idempotency_key": execution_id},
        metadata={"created_by": "test"},
    )

    with patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client:
        with transaction.atomic():
            OperationsService._upsert_workflow_root_operation(
                execution_id=execution_id,
                message_payload=message,
            )
            OperationsService._enqueue_workflow_outbox_intent(
                operation_id=execution_id,
                message_payload=message,
                stream_name=mock_redis_client.STREAM_WORKFLOWS,
            )
            transaction.set_rollback(True)

        mock_redis_client.enqueue_operation_stream.assert_not_called()

    assert WorkflowEnqueueOutbox.objects.filter(operation_id=execution_id).count() == 0
    assert BatchOperation.objects.filter(id=execution_id).count() == 0


@pytest.mark.django_db
def test_workflow_root_projection_status_chain_enqueue_to_completed():
    execution_id = str(uuid4())

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher"),
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123999-0"

        enqueue_result = OperationsService.enqueue_workflow_execution(execution_id=execution_id)
        assert enqueue_result.success is True

    root = BatchOperation.objects.get(id=execution_id)
    assert root.status == BatchOperation.STATUS_QUEUED

    moved_to_running = OperationsService.sync_workflow_root_operation_status(
        execution_id=execution_id,
        workflow_status="running",
        node_id="approval_gate",
    )
    assert moved_to_running is True

    root.refresh_from_db()
    assert root.status == BatchOperation.STATUS_PROCESSING
    assert root.metadata.get("workflow_status") == "running"
    assert root.metadata.get("node_id") == "approval_gate"

    moved_to_completed = OperationsService.sync_workflow_root_operation_status(
        execution_id=execution_id,
        workflow_status="completed",
    )
    assert moved_to_completed is True

    root.refresh_from_db()
    assert root.status == BatchOperation.STATUS_COMPLETED
    assert root.metadata.get("workflow_status") == "completed"
    assert root.progress == 100
    assert root.completed_at is not None


@pytest.mark.django_db
def test_workflow_root_projection_status_chain_enqueue_to_failed_is_non_regressive():
    execution_id = str(uuid4())

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher"),
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389124888-0"

        enqueue_result = OperationsService.enqueue_workflow_execution(execution_id=execution_id)
        assert enqueue_result.success is True

    moved_to_failed = OperationsService.sync_workflow_root_operation_status(
        execution_id=execution_id,
        workflow_status="failed",
        error_message="bridge failed",
        error_code="POOL_RUNTIME_ROUTE_DISABLED",
        error_details={"attempts": 3},
    )
    assert moved_to_failed is True

    root = BatchOperation.objects.get(id=execution_id)
    assert root.status == BatchOperation.STATUS_FAILED
    assert root.metadata.get("workflow_status") == "failed"
    assert root.metadata.get("error") == "bridge failed"
    assert root.metadata.get("error_code") == "POOL_RUNTIME_ROUTE_DISABLED"
    assert root.metadata.get("error_details") == {"attempts": 3}

    no_regression = OperationsService.sync_workflow_root_operation_status(
        execution_id=execution_id,
        workflow_status="completed",
    )
    assert no_regression is False

    root.refresh_from_db()
    assert root.status == BatchOperation.STATUS_FAILED
    assert root.metadata.get("workflow_status") == "failed"


@pytest.mark.django_db
def test_sync_workflow_root_status_reconciles_missing_projection_and_emits_alert():
    template = WorkflowTemplate.objects.create(
        name=f"workflow-reconcile-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node 1",
                    "type": "operation",
                    "template_id": "tpl-reconcile",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    tenant = Tenant.objects.create(
        slug=f"tenant-reconcile-{uuid4().hex[:8]}",
        name="Tenant Reconcile",
    )
    execution = template.create_execution(
        {"executed_by": "reconcile-test-user"},
        tenant=tenant,
        execution_consumer="pools",
    )
    execution_id = str(execution.id)
    assert BatchOperation.objects.filter(id=execution_id).count() == 0

    with patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client:
        synced = OperationsService.sync_workflow_root_operation_status(
            execution_id=execution_id,
            workflow_status="running",
            node_id="n1",
            trace_id="trace-reconcile-1",
        )

    assert synced is True
    root = BatchOperation.objects.get(id=execution_id)
    assert root.status == BatchOperation.STATUS_PROCESSING
    assert root.metadata.get("workflow_execution_id") == execution_id
    assert root.metadata.get("root_operation_id") == execution_id
    assert root.metadata.get("workflow_status") == "running"
    assert root.metadata.get("execution_consumer") == "pools"
    assert root.metadata.get("lane") == "workflows"
    assert root.metadata.get("trace_id") == "trace-reconcile-1"

    mock_redis_client.add_timeline_event.assert_called_once()
    alert_kwargs = mock_redis_client.add_timeline_event.call_args.kwargs
    assert alert_kwargs["event"] == "projection.repaired"
    assert alert_kwargs["metadata"]["repair_reason"] == "missing_root_projection"
    assert alert_kwargs["metadata"]["projection_created"] is True
    assert alert_kwargs["metadata"]["execution_consumer"] == "pools"
    assert alert_kwargs["metadata"]["lane"] == "workflows"
