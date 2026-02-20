import json
from unittest.mock import MagicMock, patch

from apps.operations.events import OperationEventPublisher


def _build_publisher(fake_redis: MagicMock) -> OperationEventPublisher:
    with patch("apps.operations.events.redis.from_url", return_value=fake_redis):
        return OperationEventPublisher()


def test_event_publisher_exposes_observability_contract_in_event_payload():
    fake_redis = MagicMock()
    publisher = _build_publisher(fake_redis)

    publisher.publish(
        operation_id="op-1",
        state="QUEUED",
        microservice="orchestrator",
        workflow_execution_id="wf-1",
        node_id="node-1",
        root_operation_id="wf-1",
        execution_consumer="pools",
        lane="workflows",
    )

    call_args = fake_redis.xadd.call_args
    assert call_args is not None
    stream_fields = call_args.args[1]
    payload = json.loads(stream_fields["data"])

    assert payload["workflow_execution_id"] == "wf-1"
    assert payload["node_id"] == "node-1"
    assert payload["root_operation_id"] == "wf-1"
    assert payload["execution_consumer"] == "pools"
    assert payload["lane"] == "workflows"
    assert payload["metadata"]["root_operation_id"] == "wf-1"
    assert payload["metadata"]["execution_consumer"] == "pools"
    assert payload["metadata"]["lane"] == "workflows"


def test_event_publisher_fills_observability_defaults_when_metadata_missing():
    fake_redis = MagicMock()
    publisher = _build_publisher(fake_redis)

    publisher.publish(
        operation_id="op-2",
        state="QUEUED",
        microservice="orchestrator",
    )

    call_args = fake_redis.xadd.call_args
    assert call_args is not None
    stream_fields = call_args.args[1]
    payload = json.loads(stream_fields["data"])

    assert payload["workflow_execution_id"] is None
    assert payload["node_id"] is None
    assert payload["root_operation_id"] == "op-2"
    assert payload["execution_consumer"] == "operations"
    assert payload["lane"] == "operations"
    assert payload["metadata"]["root_operation_id"] == "op-2"
    assert payload["metadata"]["execution_consumer"] == "operations"
    assert payload["metadata"]["lane"] == "operations"

