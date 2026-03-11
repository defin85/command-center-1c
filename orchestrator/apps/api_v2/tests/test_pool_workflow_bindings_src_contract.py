from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_src_openapi_contract() -> dict[str, Any]:
    contract_path = (
        Path(__file__).resolve().parents[4] / "contracts" / "orchestrator" / "src" / "openapi.yaml"
    )
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _load_src_path_item(filename: str) -> dict[str, Any]:
    path_item = (
        Path(__file__).resolve().parents[4]
        / "contracts"
        / "orchestrator"
        / "src"
        / "paths"
        / filename
    )
    payload = yaml.safe_load(path_item.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _load_src_schema(filename: str) -> dict[str, Any]:
    schema_path = (
        Path(__file__).resolve().parents[4]
        / "contracts"
        / "orchestrator"
        / "src"
        / "components"
        / "schemas"
        / filename
    )
    payload = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_pool_workflow_bindings_first_class_paths_are_tracked_in_src_contract() -> None:
    contract = _load_src_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    assert paths.get("/api/v2/pools/workflow-bindings/") == {
        "$ref": "paths/api_v2_pools_workflow-bindings_.yaml"
    }
    assert paths.get("/api/v2/pools/workflow-bindings/upsert/") == {
        "$ref": "paths/api_v2_pools_workflow-bindings_upsert_.yaml"
    }
    assert paths.get("/api/v2/pools/workflow-bindings/{binding_id}/") == {
        "$ref": "paths/api_v2_pools_workflow-bindings_{binding_id}_.yaml"
    }
    assert paths.get("/api/v2/pools/workflow-bindings/preview/") == {
        "$ref": "paths/api_v2_pools_workflow-bindings_preview_.yaml"
    }


def test_pool_workflow_bindings_preview_src_contract_uses_dedicated_request_schema() -> None:
    path_item = _load_src_path_item("api_v2_pools_workflow-bindings_preview_.yaml")
    post = path_item.get("post")
    assert isinstance(post, dict)

    request_body = post.get("requestBody")
    assert isinstance(request_body, dict)
    content = request_body.get("content")
    assert isinstance(content, dict)

    expected_schema = {"$ref": "../components/schemas/PoolWorkflowBindingPreviewRequest.yaml"}
    assert content["application/json"]["schema"] == expected_schema
    assert content["application/x-www-form-urlencoded"]["schema"] == expected_schema
    assert content["multipart/form-data"]["schema"] == expected_schema


def test_pool_workflow_binding_input_src_schema_includes_optional_revision_field() -> None:
    payload = _load_src_schema("PoolWorkflowBindingInput.yaml")

    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties.get("revision") == {
        "type": "integer",
        "minimum": 1,
        "description": "Server-managed optimistic concurrency revision for update/delete operations.",
    }


def test_pool_workflow_binding_read_src_schema_requires_server_managed_fields() -> None:
    payload = _load_src_schema("PoolWorkflowBindingRead.yaml")

    required = payload.get("required")
    assert isinstance(required, list)
    assert {"binding_id", "pool_id", "revision", "workflow", "effective_from", "status"}.issubset(
        set(required)
    )


def test_pool_workflow_bindings_mutating_src_contract_requires_revision_conflict_semantics() -> None:
    upsert_path = _load_src_path_item("api_v2_pools_workflow-bindings_upsert_.yaml")
    upsert_post = upsert_path.get("post")
    assert isinstance(upsert_post, dict)

    upsert_responses = upsert_post.get("responses")
    assert isinstance(upsert_responses, dict)
    assert upsert_responses["409"]["content"]["application/problem+json"]["schema"] == {
        "$ref": "../components/schemas/ProblemDetailsError.yaml"
    }

    detail_path = _load_src_path_item("api_v2_pools_workflow-bindings_{binding_id}_.yaml")
    detail_delete = detail_path.get("delete")
    assert isinstance(detail_delete, dict)

    parameters = detail_delete.get("parameters")
    assert isinstance(parameters, list)
    revision_parameter = next(
        (parameter for parameter in parameters if parameter.get("name") == "revision"),
        None,
    )
    assert revision_parameter == {
        "name": "revision",
        "in": "query",
        "required": True,
        "schema": {
            "type": "integer",
            "minimum": 1,
        },
    }

    delete_responses = detail_delete.get("responses")
    assert isinstance(delete_responses, dict)
    assert delete_responses["409"]["content"]["application/problem+json"]["schema"] == {
        "$ref": "../components/schemas/ProblemDetailsError.yaml"
    }


def test_pool_upsert_src_contract_does_not_expose_workflow_bindings_write_field() -> None:
    payload = _load_src_schema("OrganizationPoolUpsertRequest.yaml")

    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert "workflow_bindings" not in properties
