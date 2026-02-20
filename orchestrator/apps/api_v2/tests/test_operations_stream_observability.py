from apps.api_v2.views.operations.streams_sse import _normalize_observability_fields


def test_normalize_observability_fields_projects_contract_from_metadata():
    payload = {
        "workflow_execution_id": "wf-100",
        "node_id": "node-a",
        "metadata": {
            "root_operation_id": "wf-100",
            "execution_consumer": "pools",
            "lane": "workflows",
        },
    }

    normalized = _normalize_observability_fields(payload, operation_id="op-100")

    assert normalized["workflow_execution_id"] == "wf-100"
    assert normalized["node_id"] == "node-a"
    assert normalized["root_operation_id"] == "wf-100"
    assert normalized["execution_consumer"] == "pools"
    assert normalized["lane"] == "workflows"


def test_normalize_observability_fields_applies_defaults():
    payload = {"metadata": {}}

    normalized = _normalize_observability_fields(payload, operation_id="op-101")

    assert normalized["workflow_execution_id"] is None
    assert normalized["node_id"] is None
    assert normalized["root_operation_id"] == "op-101"
    assert normalized["execution_consumer"] == "operations"
    assert normalized["lane"] == "operations"
    assert normalized["metadata"]["root_operation_id"] == "op-101"
    assert normalized["metadata"]["execution_consumer"] == "operations"
    assert normalized["metadata"]["lane"] == "operations"

