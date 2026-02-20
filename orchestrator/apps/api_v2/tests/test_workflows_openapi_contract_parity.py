from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from apps.api_v2.views.workflows.common import (
    ExecuteWorkflowResponseSerializer,
    WorkflowEnqueueFailClosedErrorResponseSerializer,
)


def _load_openapi_contract() -> dict[str, Any]:
    contract_path = (
        Path(__file__).resolve().parents[4] / "contracts" / "orchestrator" / "openapi.yaml"
    )
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _schema(contract: dict[str, Any], name: str) -> dict[str, Any]:
    components = contract.get("components")
    assert isinstance(components, dict)
    schemas = components.get("schemas")
    assert isinstance(schemas, dict)
    item = schemas.get(name)
    assert isinstance(item, dict), f"schema not found: {name}"
    return item


def test_execute_workflow_path_declares_fail_closed_503_contract() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    path_item = paths.get("/api/v2/workflows/execute-workflow/")
    assert isinstance(path_item, dict)
    post = path_item.get("post")
    assert isinstance(post, dict)

    responses = post.get("responses")
    assert isinstance(responses, dict)
    assert "503" in responses
    schema_ref = responses["503"]["content"]["application/json"]["schema"]["$ref"]
    assert schema_ref == "#/components/schemas/WorkflowEnqueueFailClosedErrorResponse"


def test_execute_workflow_response_schema_covers_runtime_fields() -> None:
    contract = _load_openapi_contract()
    response_schema = _schema(contract, "ExecuteWorkflowResponse")
    properties = response_schema.get("properties")
    assert isinstance(properties, dict)

    runtime_fields = set(ExecuteWorkflowResponseSerializer().fields.keys())
    assert runtime_fields.issubset(set(properties.keys()))
    assert "operation_id" in properties


def test_workflow_enqueue_fail_closed_error_schema_covers_runtime_fields() -> None:
    contract = _load_openapi_contract()
    response_schema = _schema(contract, "WorkflowEnqueueFailClosedErrorResponse")
    properties = response_schema.get("properties")
    assert isinstance(properties, dict)

    runtime_fields = set(WorkflowEnqueueFailClosedErrorResponseSerializer().fields.keys())
    assert runtime_fields.issubset(set(properties.keys()))

    details_schema = _schema(contract, "WorkflowEnqueueFailClosedErrorDetails")
    details_required = details_schema.get("required")
    assert isinstance(details_required, list)
    assert "execution_id" in details_required

