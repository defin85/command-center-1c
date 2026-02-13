import pytest
from unittest.mock import patch
from uuid import uuid4

from apps.operations.factory import BatchOperationFactory
from apps.operations.models import BatchOperation
from apps.operations.services import OperationsService


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
            "stream_name": mock_redis_client.STREAM_WORKFLOWS,
        }

        mock_event_publisher.publish.assert_not_called()


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
        mock_event_publisher.publish.assert_called_once()
