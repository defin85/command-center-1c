from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from apps.api_v2.views.timeline import TimelineEventSerializer
from apps.operations.serializers import BatchOperationSerializer


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


def test_operations_list_path_declares_observability_filters() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    path_item = paths.get("/api/v2/operations/list-operations/")
    assert isinstance(path_item, dict)
    get_op = path_item.get("get")
    assert isinstance(get_op, dict)
    params = get_op.get("parameters")
    assert isinstance(params, list)
    names = {item.get("name") for item in params if isinstance(item, dict)}

    assert "workflow_execution_id" in names
    assert "node_id" in names
    assert "root_operation_id" in names
    assert "execution_consumer" in names
    assert "lane" in names


def test_batch_operation_schema_covers_runtime_serializer_observability_fields() -> None:
    contract = _load_openapi_contract()
    schema = _schema(contract, "BatchOperation")
    properties = schema.get("properties")
    assert isinstance(properties, dict)

    runtime_fields = set(BatchOperationSerializer().fields.keys())
    assert runtime_fields.issubset(set(properties.keys()))

    for field_name in (
        "workflow_execution_id",
        "node_id",
        "root_operation_id",
        "execution_consumer",
        "lane",
    ):
        assert field_name in properties


def test_timeline_event_schema_covers_runtime_serializer_observability_fields() -> None:
    contract = _load_openapi_contract()
    schema = _schema(contract, "TimelineEvent")
    properties = schema.get("properties")
    assert isinstance(properties, dict)

    runtime_fields = set(TimelineEventSerializer().fields.keys())
    assert runtime_fields.issubset(set(properties.keys()))

    for field_name in ("root_operation_id", "execution_consumer", "lane"):
        assert field_name in properties

