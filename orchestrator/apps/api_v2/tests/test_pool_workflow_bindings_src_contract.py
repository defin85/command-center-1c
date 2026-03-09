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


def test_pool_upsert_src_contract_does_not_expose_workflow_bindings_write_field() -> None:
    schema_path = (
        Path(__file__).resolve().parents[4]
        / "contracts"
        / "orchestrator"
        / "src"
        / "components"
        / "schemas"
        / "OrganizationPoolUpsertRequest.yaml"
    )
    payload = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)

    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert "workflow_bindings" not in properties
