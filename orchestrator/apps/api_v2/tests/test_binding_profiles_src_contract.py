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


def test_binding_profiles_first_class_paths_are_tracked_in_src_contract() -> None:
    contract = _load_src_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    assert paths.get("/api/v2/pools/binding-profiles/") == {
        "$ref": "paths/api_v2_pools_binding-profiles_.yaml"
    }
    assert paths.get("/api/v2/pools/binding-profiles/{binding_profile_id}/") == {
        "$ref": "paths/api_v2_pools_binding-profiles_{binding_profile_id}_.yaml"
    }
    assert paths.get("/api/v2/pools/binding-profiles/{binding_profile_id}/revisions/") == {
        "$ref": "paths/api_v2_pools_binding-profiles_{binding_profile_id}_revisions_.yaml"
    }
    assert paths.get("/api/v2/pools/binding-profiles/{binding_profile_id}/deactivate/") == {
        "$ref": "paths/api_v2_pools_binding-profiles_{binding_profile_id}_deactivate_.yaml"
    }


def test_binding_profiles_collection_src_contract_uses_get_and_post_catalog_surface() -> None:
    path_item = _load_src_path_item("api_v2_pools_binding-profiles_.yaml")
    get_op = path_item.get("get")
    post_op = path_item.get("post")
    assert isinstance(get_op, dict)
    assert isinstance(post_op, dict)
    assert get_op["summary"] == "List reusable execution packs"
    assert post_op["summary"] == "Create reusable execution pack"

    get_responses = get_op.get("responses")
    assert isinstance(get_responses, dict)
    assert get_responses["200"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/BindingProfileListResponse.yaml"
    }

    post_request_body = post_op.get("requestBody")
    assert isinstance(post_request_body, dict)
    assert post_request_body["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/BindingProfileCreateRequest.yaml"
    }

    post_responses = post_op.get("responses")
    assert isinstance(post_responses, dict)
    assert post_responses["201"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/BindingProfileMutationResponse.yaml"
    }
    assert post_responses["409"]["content"]["application/problem+json"]["schema"] == {
        "$ref": "../components/schemas/ProblemDetailsError.yaml"
    }


def test_binding_profiles_detail_and_actions_are_split_into_detail_revisions_and_deactivate_paths() -> None:
    detail_path = _load_src_path_item("api_v2_pools_binding-profiles_{binding_profile_id}_.yaml")
    detail_get = detail_path.get("get")
    assert isinstance(detail_get, dict)
    assert detail_get["summary"] == "Get reusable execution pack detail"
    assert detail_get["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/BindingProfileDetailResponse.yaml"
    }

    revisions_path = _load_src_path_item("api_v2_pools_binding-profiles_{binding_profile_id}_revisions_.yaml")
    revisions_post = revisions_path.get("post")
    assert isinstance(revisions_post, dict)
    assert revisions_post["summary"] == "Create a new immutable execution-pack revision"
    assert revisions_post["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/BindingProfileRevisionCreateRequest.yaml"
    }
    assert revisions_post["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/BindingProfileMutationResponse.yaml"
    }

    deactivate_path = _load_src_path_item("api_v2_pools_binding-profiles_{binding_profile_id}_deactivate_.yaml")
    deactivate_post = deactivate_path.get("post")
    assert isinstance(deactivate_post, dict)
    assert deactivate_post["summary"] == "Deactivate reusable execution pack"
    assert deactivate_post["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/BindingProfileMutationResponse.yaml"
    }


def test_binding_profile_revision_src_schema_requires_opaque_revision_identity() -> None:
    payload = _load_src_schema("BindingProfileRevision.yaml")
    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties.get("binding_profile_revision_id") == {
        "type": "string",
        "description": "Opaque immutable runtime pin for a reusable execution-pack revision.",
    }
    assert properties.get("revision_number") == {
        "type": "integer",
        "minimum": 1,
        "description": "Human-readable monotonic revision number within the profile.",
    }
    assert properties.get("workflow") == {"$ref": "./WorkflowDefinitionRef.yaml"}
    assert properties.get("topology_template_compatibility") == {
        "$ref": "./ExecutionPackTopologyCompatibilitySummary.yaml"
    }

    write_payload = _load_src_schema("BindingProfileRevisionWrite.yaml")
    write_properties = write_payload.get("properties")
    assert isinstance(write_properties, dict)
    assert write_properties.get("contract_version") == {
        "type": "string",
        "description": "Execution-pack revision contract version.",
    }

    required = payload.get("required")
    assert required == [
        "binding_profile_revision_id",
        "binding_profile_id",
        "revision_number",
        "workflow",
        "decisions",
        "parameters",
        "role_mapping",
        "metadata",
        "topology_template_compatibility",
        "created_at",
    ]


def test_binding_profile_read_src_schema_exposes_latest_revision_and_revisions() -> None:
    payload = _load_src_schema("BindingProfileDetail.yaml")
    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties.get("latest_revision") == {"$ref": "./BindingProfileRevision.yaml"}
    assert properties.get("revisions") == {
        "type": "array",
        "items": {"$ref": "./BindingProfileRevision.yaml"},
    }
    assert properties.get("usage_summary") == {"$ref": "./BindingProfileUsageSummary.yaml"}
    assert properties.get("status") == {
        "type": "string",
        "enum": ["active", "deactivated"],
    }

    required = payload.get("required")
    assert required == [
        "binding_profile_id",
        "code",
        "name",
        "status",
        "latest_revision_number",
        "latest_revision",
        "revisions",
        "usage_summary",
        "created_at",
        "updated_at",
    ]


def test_execution_pack_topology_compatibility_src_schema_tracks_machine_readable_diagnostics() -> None:
    summary = _load_src_schema("ExecutionPackTopologyCompatibilitySummary.yaml")
    summary_properties = summary.get("properties")
    assert isinstance(summary_properties, dict)
    assert summary_properties["status"] == {
        "type": "string",
        "enum": ["compatible", "incompatible"],
    }
    assert summary_properties["topology_aware_ready"] == {"type": "boolean"}
    assert summary_properties["covered_slot_keys"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert summary_properties["diagnostics"] == {
        "type": "array",
        "items": {"$ref": "./ExecutionPackTopologyCompatibilityDiagnostic.yaml"},
    }

    diagnostic = _load_src_schema("ExecutionPackTopologyCompatibilityDiagnostic.yaml")
    diagnostic_properties = diagnostic.get("properties")
    assert isinstance(diagnostic_properties, dict)
    assert diagnostic_properties["decision_revision"] == {
        "type": "integer",
        "minimum": 1,
    }
    assert diagnostic_properties["field_or_table_path"] == {"type": "string"}
