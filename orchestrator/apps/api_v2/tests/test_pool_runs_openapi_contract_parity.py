from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from apps.api_v2.serializers.common import ExecutionPlanSerializer
from apps.api_v2.views import intercompany_pools as pools_view


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


def test_pool_run_safe_commands_paths_are_in_contract_with_expected_responses() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    expected_paths = {
        "/api/v2/pools/runs/{run_id}/confirm-publication/": "v2_pools_runs_confirm_publication",
        "/api/v2/pools/runs/{run_id}/abort-publication/": "v2_pools_runs_abort_publication",
    }
    expected_statuses = {"200", "202", "400", "401", "404", "409"}

    for path, operation_id in expected_paths.items():
        path_item = paths.get(path)
        assert isinstance(path_item, dict), f"path missing: {path}"
        post = path_item.get("post")
        assert isinstance(post, dict), f"post missing: {path}"
        assert post.get("operationId") == operation_id

        responses = post.get("responses")
        assert isinstance(responses, dict)
        assert expected_statuses.issubset(set(responses.keys()))

        ok_ref = responses["200"]["content"]["application/json"]["schema"]["$ref"]
        accepted_ref = responses["202"]["content"]["application/json"]["schema"]["$ref"]
        conflict_ref = responses["409"]["content"]["application/json"]["schema"]["$ref"]
        assert ok_ref == "#/components/schemas/PoolRunSafeCommandResponse"
        assert accepted_ref == "#/components/schemas/PoolRunSafeCommandResponse"
        assert conflict_ref == "#/components/schemas/PoolRunSafeCommandConflict"


def test_pool_run_retry_path_and_payload_schema_are_in_contract_with_expected_responses() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    path = "/api/v2/pools/runs/{run_id}/retry/"
    path_item = paths.get(path)
    assert isinstance(path_item, dict), f"path missing: {path}"
    post = path_item.get("post")
    assert isinstance(post, dict), f"post missing: {path}"
    assert post.get("operationId") == "v2_pools_runs_retry"

    responses = post.get("responses")
    assert isinstance(responses, dict)
    expected_statuses = {"202", "400", "401", "404", "409"}
    assert expected_statuses.issubset(set(responses.keys()))

    accepted_ref = responses["202"]["content"]["application/json"]["schema"]["$ref"]
    conflict_ref = responses["409"]["content"]["application/json"]["schema"]["$ref"]
    assert accepted_ref == "#/components/schemas/PoolRunRetryAcceptedResponse"
    assert conflict_ref == "#/components/schemas/PoolRunSafeCommandConflict"

    accepted_schema = _schema(contract, "PoolRunRetryAcceptedResponse")
    accepted_properties = accepted_schema.get("properties")
    assert isinstance(accepted_properties, dict)
    runtime_response_fields = set(pools_view.PoolRunRetryAcceptedResponseSerializer().fields.keys())
    assert runtime_response_fields.issubset(set(accepted_properties.keys()))

    summary_schema = _schema(contract, "PoolRunRetryTargetSummary")
    summary_properties = summary_schema.get("properties")
    assert isinstance(summary_properties, dict)
    runtime_summary_fields = set(pools_view.PoolRunRetryTargetSummarySerializer().fields.keys())
    assert runtime_summary_fields.issubset(set(summary_properties.keys()))


def test_pool_run_schema_covers_runtime_serializer_fields() -> None:
    contract = _load_openapi_contract()
    pool_run_schema = _schema(contract, "PoolRun")
    properties = pool_run_schema.get("properties")
    assert isinstance(properties, dict)

    runtime_fields = set(pools_view.PoolRunSerializer().fields.keys())
    contract_fields = set(properties.keys())
    assert runtime_fields.issubset(contract_fields)

    provenance = properties.get("provenance")
    assert provenance == {"$ref": "#/components/schemas/PoolRunProvenance"}


def test_safe_command_payload_schemas_cover_runtime_serializer_fields() -> None:
    contract = _load_openapi_contract()

    response_schema = _schema(contract, "PoolRunSafeCommandResponse")
    response_properties = response_schema.get("properties")
    assert isinstance(response_properties, dict)
    runtime_response_fields = set(pools_view.PoolRunSafeCommandResponseSerializer().fields.keys())
    assert runtime_response_fields.issubset(set(response_properties.keys()))

    conflict_schema = _schema(contract, "PoolRunSafeCommandConflict")
    conflict_properties = conflict_schema.get("properties")
    assert isinstance(conflict_properties, dict)
    runtime_conflict_fields = set(pools_view.PoolRunSafeCommandConflictSerializer().fields.keys())
    assert runtime_conflict_fields.issubset(set(conflict_properties.keys()))


def test_pool_publication_attempt_schema_contains_canonical_and_alias_diagnostics() -> None:
    contract = _load_openapi_contract()
    schema = _schema(contract, "PoolPublicationAttempt")
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    contract_fields = set(properties.keys())

    runtime_fields = set(pools_view.PoolPublicationAttemptSerializer().fields.keys())
    assert runtime_fields.issubset(contract_fields)

    canonical_fields = {
        "target_database_id",
        "payload_summary",
        "http_error",
        "transport_error",
        "domain_error_code",
        "domain_error_message",
        "attempt_number",
        "attempt_timestamp",
    }
    alias_fields = {
        "external_document_identity",
        "identity_strategy",
        "publication_identity_strategy",
        "http_status",
        "error_code",
        "error_message",
        "request_summary",
        "response_summary",
    }
    assert canonical_fields.issubset(contract_fields)
    assert alias_fields.issubset(contract_fields)


def test_pool_run_provenance_schema_uses_structured_retry_chain_model() -> None:
    contract = _load_openapi_contract()
    provenance_schema = _schema(contract, "PoolRunProvenance")
    provenance_properties = provenance_schema.get("properties")
    assert isinstance(provenance_properties, dict)

    assert {"workflow_run_id", "workflow_status", "execution_backend", "retry_chain"}.issubset(
        set(provenance_properties.keys())
    )

    retry_chain = provenance_properties.get("retry_chain")
    assert isinstance(retry_chain, dict)
    items = retry_chain.get("items")
    assert items == {"$ref": "#/components/schemas/PoolRunRetryChainAttempt"}

    attempt_schema = _schema(contract, "PoolRunRetryChainAttempt")
    attempt_properties = attempt_schema.get("properties")
    assert isinstance(attempt_properties, dict)
    assert {
        "workflow_run_id",
        "parent_workflow_run_id",
        "attempt_number",
        "attempt_kind",
        "status",
    }.issubset(set(attempt_properties.keys()))


def test_execution_plan_schema_covers_runtime_serializer_fields() -> None:
    contract = _load_openapi_contract()
    execution_plan_schema = _schema(contract, "ExecutionPlan")
    properties = execution_plan_schema.get("properties")
    assert isinstance(properties, dict)

    runtime_fields = set(ExecutionPlanSerializer().fields.keys())
    contract_fields = set(properties.keys())
    assert runtime_fields.issubset(contract_fields)
