from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from apps.api_v2.views import intercompany_pools_binding_profiles as binding_profiles_view


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


def test_binding_profiles_paths_are_present_in_generated_openapi_contract() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    collection = paths.get("/api/v2/pools/binding-profiles/")
    assert isinstance(collection, dict)
    assert collection["get"]["operationId"] == "v2_pools_binding_profiles_list"
    assert collection["post"]["operationId"] == "v2_pools_binding_profiles_create"
    assert collection["post"]["responses"]["201"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/BindingProfileMutationResponse"
    )

    detail = paths.get("/api/v2/pools/binding-profiles/{binding_profile_id}/")
    assert isinstance(detail, dict)
    assert detail["get"]["operationId"] == "v2_pools_binding_profiles_detail"

    revisions = paths.get("/api/v2/pools/binding-profiles/{binding_profile_id}/revisions/")
    assert isinstance(revisions, dict)
    assert revisions["post"]["operationId"] == "v2_pools_binding_profiles_revise"

    deactivate = paths.get("/api/v2/pools/binding-profiles/{binding_profile_id}/deactivate/")
    assert isinstance(deactivate, dict)
    assert deactivate["post"]["operationId"] == "v2_pools_binding_profiles_deactivate"


def test_binding_profile_detail_schema_covers_runtime_serializer_fields() -> None:
    contract = _load_openapi_contract()
    detail_schema = _schema(contract, "BindingProfileDetail")
    properties = detail_schema.get("properties")
    assert isinstance(properties, dict)

    runtime_fields = set(binding_profiles_view.BindingProfileDetailSerializer().fields.keys())
    assert runtime_fields.issubset(set(properties.keys()))
    assert properties["latest_revision"] == {"$ref": "#/components/schemas/BindingProfileRevision"}
    assert properties["revisions"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/BindingProfileRevision"},
    }
    assert properties["usage_summary"] == {"$ref": "#/components/schemas/BindingProfileUsageSummary"}
    assert properties["status"]["enum"] == ["active", "deactivated"]


def test_binding_profile_revision_schema_uses_opaque_revision_identity_and_runtime_serializer_shape() -> None:
    contract = _load_openapi_contract()
    revision_schema = _schema(contract, "BindingProfileRevision")
    properties = revision_schema.get("properties")
    assert isinstance(properties, dict)

    runtime_fields = set(binding_profiles_view.BindingProfileRevisionReadSerializer().fields.keys())
    assert runtime_fields.issubset(set(properties.keys()))
    assert properties["binding_profile_revision_id"]["type"] == "string"
    assert properties["binding_profile_id"]["type"] == "string"
    assert properties["binding_profile_id"]["format"] == "uuid"
    assert properties["revision_number"]["minimum"] == 1
