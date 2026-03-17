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


def test_pool_workflow_bindings_collection_src_contract_uses_get_and_put_collection_surface() -> None:
    path_item = _load_src_path_item("api_v2_pools_workflow-bindings_.yaml")
    get_op = path_item.get("get")
    put_op = path_item.get("put")
    assert isinstance(get_op, dict)
    assert isinstance(put_op, dict)

    get_responses = get_op.get("responses")
    assert isinstance(get_responses, dict)
    assert get_responses["200"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/PoolWorkflowBindingCollectionResponse.yaml"
    }

    put_request_body = put_op.get("requestBody")
    assert isinstance(put_request_body, dict)
    put_content = put_request_body.get("content")
    assert isinstance(put_content, dict)
    assert put_content["application/json"]["schema"] == {
        "$ref": "../components/schemas/PoolWorkflowBindingCollectionReplaceRequest.yaml"
    }

    put_responses = put_op.get("responses")
    assert isinstance(put_responses, dict)
    assert put_responses["200"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/PoolWorkflowBindingCollectionResponse.yaml"
    }
    assert put_responses["409"]["content"]["application/problem+json"]["schema"] == {
        "$ref": "../components/schemas/ProblemDetailsError.yaml"
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


def test_pool_workflow_bindings_preview_response_src_contract_exposes_slot_projection() -> None:
    payload = _load_src_schema("PoolWorkflowBindingPreviewResponse.yaml")

    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties.get("compiled_document_policy_slots") == {
        "type": "object",
        "description": "Canonical slot-based publication policy projection keyed by binding slot_key.",
        "additionalProperties": {
            "type": "object",
            "additionalProperties": True,
        },
    }
    slot_coverage_summary = properties.get("slot_coverage_summary")
    assert isinstance(slot_coverage_summary, dict)
    assert slot_coverage_summary["type"] == "object"
    assert slot_coverage_summary["properties"]["total_edges"] == {"type": "integer"}
    assert slot_coverage_summary["properties"]["items"]["type"] == "array"
    coverage_properties = slot_coverage_summary["properties"]["items"]["items"]["properties"]["coverage"][
        "properties"
    ]
    assert coverage_properties["code"] == {"type": "string", "nullable": True}

    required = payload.get("required")
    assert required == [
        "workflow_binding",
        "compiled_document_policy_slots",
        "slot_coverage_summary",
        "runtime_projection",
    ]
    assert "compiled_document_policy" not in required


def test_pool_workflow_binding_decision_ref_src_schema_splits_slot_key_from_decision_key() -> None:
    payload = _load_src_schema("PoolWorkflowBindingDecisionRef.yaml")

    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties["decision_table_id"] == {"type": "string"}
    assert properties["decision_key"]["type"] == "string"
    assert properties["slot_key"] == {
        "type": "string",
        "nullable": True,
        "description": "Binding-local publication slot identity for policy-bearing decisions.",
    }
    assert properties["decision_revision"] == {"type": "integer", "minimum": 1}

    required = payload.get("required")
    assert required == ["decision_table_id", "decision_key", "decision_revision"]


def test_pool_workflow_binding_input_src_schema_includes_optional_revision_field() -> None:
    payload = _load_src_schema("PoolWorkflowBindingInput.yaml")

    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties.get("revision") == {
        "type": "integer",
        "minimum": 1,
        "description": "Server-managed optimistic concurrency revision for update/delete operations.",
    }
    assert properties.get("binding_profile_revision_id") == {
        "type": "string",
        "description": "Opaque pinned reusable binding profile revision identifier.",
    }
    assert "workflow" not in properties
    assert "decisions" not in properties


def test_pool_workflow_binding_read_src_schema_requires_server_managed_fields() -> None:
    payload = _load_src_schema("PoolWorkflowBindingRead.yaml")

    required = payload.get("required")
    assert isinstance(required, list)
    assert {
        "binding_id",
        "pool_id",
        "binding_profile_id",
        "binding_profile_revision_id",
        "binding_profile_revision_number",
        "revision",
        "effective_from",
        "status",
        "resolved_profile",
    }.issubset(
        set(required)
    )

    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties["resolved_profile"] == {
        "$ref": "./PoolWorkflowBindingResolvedProfile.yaml",
    }
    assert properties["profile_lifecycle_warning"] == {
        "allOf": [{"$ref": "./PoolWorkflowBindingProfileLifecycleWarning.yaml"}],
        "nullable": True,
    }


def test_pool_workflow_binding_collection_response_src_schema_requires_etag_and_bindings() -> None:
    payload = _load_src_schema("PoolWorkflowBindingCollectionResponse.yaml")

    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties.get("workflow_bindings") == {
        "type": "array",
        "items": {"$ref": "./PoolWorkflowBindingRead.yaml"},
    }
    assert properties.get("collection_etag") == {
        "type": "string",
        "description": "Opaque optimistic concurrency token for the entire binding collection.",
    }

    required = payload.get("required")
    assert required == ["pool_id", "workflow_bindings", "collection_etag"]


def test_pool_workflow_binding_collection_replace_request_src_schema_requires_expected_collection_etag() -> None:
    payload = _load_src_schema("PoolWorkflowBindingCollectionReplaceRequest.yaml")

    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties.get("expected_collection_etag") == {
        "type": "string",
        "description": "Opaque concurrency token returned by the previous collection read.",
    }
    assert properties.get("workflow_bindings") == {
        "type": "array",
        "items": {"$ref": "./PoolWorkflowBindingInput.yaml"},
    }

    required = payload.get("required")
    assert required == ["pool_id", "expected_collection_etag", "workflow_bindings"]


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
