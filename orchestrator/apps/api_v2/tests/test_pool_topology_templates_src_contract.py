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


def test_topology_templates_first_class_paths_are_tracked_in_src_contract() -> None:
    contract = _load_src_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    assert paths.get("/api/v2/pools/topology-templates/") == {
        "$ref": "paths/api_v2_pools_topology-templates_.yaml"
    }
    assert paths.get("/api/v2/pools/topology-templates/{topology_template_id}/revisions/") == {
        "$ref": "paths/api_v2_pools_topology-templates_{topology_template_id}_revisions_.yaml"
    }


def test_topology_templates_collection_src_contract_uses_get_and_post_catalog_surface() -> None:
    path_item = _load_src_path_item("api_v2_pools_topology-templates_.yaml")
    get_op = path_item.get("get")
    post_op = path_item.get("post")
    assert isinstance(get_op, dict)
    assert isinstance(post_op, dict)

    assert get_op["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/TopologyTemplateListResponse.yaml"
    }
    assert post_op["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/TopologyTemplateCreateRequest.yaml"
    }
    assert post_op["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/TopologyTemplateMutationResponse.yaml"
    }


def test_topology_template_revisions_src_contract_uses_dedicated_revision_write_schema() -> None:
    path_item = _load_src_path_item("api_v2_pools_topology-templates_{topology_template_id}_revisions_.yaml")
    post_op = path_item.get("post")
    assert isinstance(post_op, dict)

    assert post_op["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/TopologyTemplateRevisionCreateRequest.yaml"
    }
    assert post_op["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "../components/schemas/TopologyTemplateMutationResponse.yaml"
    }


def test_topology_template_src_schema_requires_latest_revision_projection() -> None:
    payload = _load_src_schema("TopologyTemplate.yaml")
    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties["latest_revision"] == {"$ref": "./TopologyTemplateRevision.yaml"}
    assert properties["revisions"] == {
        "type": "array",
        "items": {"$ref": "./TopologyTemplateRevision.yaml"},
    }
    assert properties["status"] == {
        "type": "string",
        "enum": ["active", "deactivated"],
    }


def test_pool_topology_snapshot_upsert_src_schema_allows_template_based_instantiation_contract() -> None:
    payload = _load_src_schema("PoolTopologySnapshotUpsertRequest.yaml")
    properties = payload.get("properties")
    assert isinstance(properties, dict)
    assert properties["topology_template_revision_id"] == {"type": "string"}
    assert properties["slot_assignments"] == {
        "type": "array",
        "items": {"$ref": "./PoolTopologyTemplateSlotAssignmentInput.yaml"},
    }
    assert properties["edge_selector_overrides"] == {
        "type": "array",
        "items": {"$ref": "./PoolTopologyTemplateEdgeSelectorOverrideInput.yaml"},
    }
    required = payload.get("required")
    assert required == ["effective_from", "version"]
