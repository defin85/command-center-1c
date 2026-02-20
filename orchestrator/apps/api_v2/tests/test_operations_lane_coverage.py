from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.operations.models import BatchOperation
from apps.operations.services import OperationsService
from apps.templates.workflow.models import WorkflowTemplate, WorkflowType


@pytest.mark.django_db
def test_operations_endpoints_cover_workflow_root_and_atomic_steps_across_lanes():
    user = User.objects.create_user(
        username=f"lane-user-{uuid4().hex[:8]}",
        password="pass",
    )
    client = APIClient()
    client.force_authenticate(user=user)

    template = WorkflowTemplate.objects.create(
        name=f"lane-workflow-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node 1",
                    "type": "operation",
                    "template_id": "tpl-lane",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    execution = template.create_execution(
        {"executed_by": user.username},
        execution_consumer="workflows",
    )
    execution_id = str(execution.id)

    with (
        patch("apps.operations.services.operations_service.workflow.redis_client") as mock_redis_client,
        patch("apps.operations.services.operations_service.workflow.event_publisher"),
    ):
        mock_redis_client.enqueue_operation_stream.return_value = "1702389123555-3"
        enqueue_result = OperationsService.enqueue_workflow_execution(execution_id=execution_id)
        assert enqueue_result.success is True

    root_operation = BatchOperation.objects.get(id=execution_id)
    assert root_operation.created_by == user.username
    assert root_operation.metadata.get("lane") == "workflows"

    atomic_operation_id = f"{execution_id}:node-n1"
    BatchOperation.objects.create(
        id=atomic_operation_id,
        name="Atomic workflow step",
        operation_type=BatchOperation.TYPE_QUERY,
        target_entity="Infobase",
        status=BatchOperation.STATUS_QUEUED,
        created_by=user.username,
        metadata={
            "workflow_execution_id": execution_id,
            "node_id": "n1",
            "root_operation_id": execution_id,
            "execution_consumer": "workflows",
            "lane": "operations",
        },
    )

    list_response = client.get(
        f"/api/v2/operations/list-operations/?workflow_execution_id={execution_id}&limit=20"
    )
    assert list_response.status_code == 200
    operations_payload = list_response.json()["operations"]
    operation_ids = {item["id"] for item in operations_payload}
    assert execution_id in operation_ids
    assert atomic_operation_id in operation_ids
    operations_by_id = {item["id"]: item for item in operations_payload}
    root_payload = operations_by_id[execution_id]
    assert root_payload["workflow_execution_id"] == execution_id
    assert root_payload["node_id"] is None
    assert root_payload["root_operation_id"] == execution_id
    assert root_payload["execution_consumer"] == "workflows"
    assert root_payload["lane"] == "workflows"
    atomic_payload = operations_by_id[atomic_operation_id]
    assert atomic_payload["workflow_execution_id"] == execution_id
    assert atomic_payload["node_id"] == "n1"
    assert atomic_payload["root_operation_id"] == execution_id
    assert atomic_payload["execution_consumer"] == "workflows"
    assert atomic_payload["lane"] == "operations"
    lanes = {
        str(item.get("metadata", {}).get("lane") or "")
        for item in operations_payload
    }
    assert "workflows" in lanes
    assert "operations" in lanes

    node_filter_response = client.get(
        f"/api/v2/operations/list-operations/?workflow_execution_id={execution_id}&node_id=n1&limit=20"
    )
    assert node_filter_response.status_code == 200
    node_filtered_ids = {item["id"] for item in node_filter_response.json()["operations"]}
    assert atomic_operation_id in node_filtered_ids
    assert execution_id not in node_filtered_ids

    root_filter_response = client.get(
        f"/api/v2/operations/list-operations/?root_operation_id={execution_id}&limit=20"
    )
    assert root_filter_response.status_code == 200
    root_filtered_ids = {item["id"] for item in root_filter_response.json()["operations"]}
    assert execution_id in root_filtered_ids
    assert atomic_operation_id in root_filtered_ids

    consumer_filter_response = client.get(
        "/api/v2/operations/list-operations/"
        f"?workflow_execution_id={execution_id}&execution_consumer=workflows&limit=20"
    )
    assert consumer_filter_response.status_code == 200
    consumer_filtered_ids = {item["id"] for item in consumer_filter_response.json()["operations"]}
    assert execution_id in consumer_filtered_ids
    assert atomic_operation_id in consumer_filtered_ids

    lane_filter_response = client.get(
        f"/api/v2/operations/list-operations/?workflow_execution_id={execution_id}&lane=workflows&limit=20"
    )
    assert lane_filter_response.status_code == 200
    lane_filtered_ids = {item["id"] for item in lane_filter_response.json()["operations"]}
    assert execution_id in lane_filtered_ids
    assert atomic_operation_id not in lane_filtered_ids

    detail_response = client.get(
        f"/api/v2/operations/get-operation/?operation_id={execution_id}&include_tasks=false"
    )
    assert detail_response.status_code == 200
    detail_operation = detail_response.json()["operation"]
    assert detail_operation["workflow_execution_id"] == execution_id
    assert detail_operation["root_operation_id"] == execution_id
    assert detail_operation["execution_consumer"] == "workflows"
    assert detail_operation["lane"] == "workflows"

    stream_ticket_response = client.post(
        "/api/v2/operations/stream-ticket/",
        {"operation_id": execution_id},
        format="json",
    )
    assert stream_ticket_response.status_code == 200
    assert stream_ticket_response.json().get("ticket")

    with patch(
        "apps.operations.services.timeline_service.TimelineService._fetch_timeline_from_redis"
    ) as mock_fetch:
        mock_fetch.return_value = (
            [
                {
                    "timestamp": 1734567890123,
                    "event": "operation.queued",
                    "service": "orchestrator",
                    "workflow_execution_id": execution_id,
                    "node_id": None,
                    "metadata": {"lane": "workflows"},
                }
            ],
            1,
            0,
        )
        timeline_response = client.post(
            "/api/v2/operations/get-operation-timeline/",
            {"operation_id": execution_id},
            format="json",
        )

    assert timeline_response.status_code == 200
    timeline_payload = timeline_response.json()
    assert timeline_payload["operation_id"] == execution_id
    assert timeline_payload["timeline"][0]["workflow_execution_id"] == execution_id
