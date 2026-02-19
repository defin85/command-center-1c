from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_internal_contract() -> dict[str, Any]:
    contract_path = (
        Path(__file__).resolve().parents[4] / "contracts" / "orchestrator-internal" / "openapi.yaml"
    )
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _schema(contract: dict[str, Any], name: str) -> dict[str, Any]:
    components = contract.get("components")
    assert isinstance(components, dict)
    schemas = components.get("schemas")
    assert isinstance(schemas, dict)
    schema = schemas.get(name)
    assert isinstance(schema, dict), f"schema not found: {name}"
    return schema


def test_execute_pool_runtime_step_path_has_canonical_status_matrix_contract() -> None:
    contract = _load_internal_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    path_item = paths.get("/api/v2/internal/workflows/execute-pool-runtime-step")
    assert isinstance(path_item, dict)
    post = path_item.get("post")
    assert isinstance(post, dict)
    assert post.get("operationId") == "executePoolRuntimeStepV2"

    description = str(post.get("description") or "")
    assert "Retry classification matrix" in description
    assert "retryable" in description
    assert "non-retryable" in description

    request_schema_ref = post["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert request_schema_ref == "#/components/schemas/PoolRuntimeStepExecutionRequest"

    responses = post.get("responses")
    assert isinstance(responses, dict)
    assert {"200", "400", "401", "404", "409", "429", "500"}.issubset(set(responses.keys()))

    ok_ref = responses["200"]["content"]["application/json"]["schema"]["$ref"]
    conflict_ref = responses["409"]["content"]["application/json"]["schema"]["$ref"]
    assert ok_ref == "#/components/schemas/PoolRuntimeStepExecutionResponse"
    assert conflict_ref == "#/components/schemas/ErrorResponse"

    conflict_examples = responses["409"]["content"]["application/json"].get("examples")
    assert isinstance(conflict_examples, dict)
    assert {"contextMismatch", "idempotencyConflict", "publicationPathDisabled"}.issubset(
        set(conflict_examples.keys())
    )

    publication_example = conflict_examples["publicationPathDisabled"].get("value")
    assert isinstance(publication_example, dict)
    assert publication_example.get("code") == "POOL_RUNTIME_PUBLICATION_PATH_DISABLED"


def test_pool_runtime_step_request_schema_contains_context_and_retry_fields() -> None:
    contract = _load_internal_contract()
    request_schema = _schema(contract, "PoolRuntimeStepExecutionRequest")
    required = set(request_schema.get("required") or [])

    assert {
        "tenant_id",
        "pool_run_id",
        "workflow_execution_id",
        "node_id",
        "operation_type",
        "operation_ref",
        "step_attempt",
        "transport_attempt",
        "idempotency_key",
        "payload",
    }.issubset(required)

    properties = request_schema.get("properties")
    assert isinstance(properties, dict)
    operation_ref = properties.get("operation_ref")
    assert operation_ref == {"$ref": "#/components/schemas/PoolRuntimeOperationRef"}
    publication_auth = properties.get("publication_auth")
    assert publication_auth == {"$ref": "#/components/schemas/PoolRuntimePublicationAuth"}


def test_pool_runtime_publication_auth_schema_contains_fail_closed_fields() -> None:
    contract = _load_internal_contract()
    publication_auth_schema = _schema(contract, "PoolRuntimePublicationAuth")

    required = set(publication_auth_schema.get("required") or [])
    assert {"strategy", "source"}.issubset(required)

    properties = publication_auth_schema.get("properties")
    assert isinstance(properties, dict)
    assert set(properties.get("strategy", {}).get("enum") or []) == {"actor", "service"}
    assert "actor_username" in properties


def test_pool_runtime_step_response_schema_contains_idempotency_and_status_fields() -> None:
    contract = _load_internal_contract()
    response_schema = _schema(contract, "PoolRuntimeStepExecutionResponse")
    required = set(response_schema.get("required") or [])

    assert {
        "success",
        "workflow_execution_id",
        "pool_run_id",
        "node_id",
        "step_attempt",
        "transport_attempt",
        "idempotency_key",
        "status",
    }.issubset(required)

    properties = response_schema.get("properties")
    assert isinstance(properties, dict)
    assert set(properties.get("status", {}).get("enum") or []) == {"completed", "failed"}
    assert "side_effect_applied" in properties
    assert "idempotency_replayed" in properties
