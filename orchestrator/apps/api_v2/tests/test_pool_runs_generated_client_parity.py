from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_openapi_contract() -> dict[str, Any]:
    contract_path = _repo_root() / "contracts" / "orchestrator" / "openapi.yaml"
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _schema(contract: dict[str, Any], name: str) -> dict[str, Any]:
    components = contract.get("components")
    assert isinstance(components, dict)
    schemas = components.get("schemas")
    assert isinstance(schemas, dict)
    value = schemas.get(name)
    assert isinstance(value, dict), f"schema not found: {name}"
    return value


def _generated_model_fields(filename: str) -> set[str]:
    model_path = _repo_root() / "frontend" / "src" / "api" / "generated" / "model" / filename
    content = model_path.read_text(encoding="utf-8")
    return set(re.findall(r"^\s{2}([a-zA-Z0-9_]+)\??:", content, flags=re.MULTILINE))


def test_generated_v2_has_safe_command_operations_from_openapi() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)
    assert "/api/v2/pools/runs/{run_id}/confirm-publication/" in paths
    assert "/api/v2/pools/runs/{run_id}/abort-publication/" in paths

    generated_v2_path = _repo_root() / "frontend" / "src" / "api" / "generated" / "v2" / "v2.ts"
    content = generated_v2_path.read_text(encoding="utf-8")

    assert "postPoolsRunsConfirmPublication" in content
    assert "postPoolsRunsAbortPublication" in content
    assert "url: `/api/v2/pools/runs/${runId}/confirm-publication/`" in content
    assert "url: `/api/v2/pools/runs/${runId}/abort-publication/`" in content


def test_generated_v2_has_document_policy_migration_operation_from_openapi() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)
    assert "/api/v2/pools/{pool_id}/document-policy-migrations/" in paths

    generated_v2_path = _repo_root() / "frontend" / "src" / "api" / "generated" / "v2" / "v2.ts"
    content = generated_v2_path.read_text(encoding="utf-8")

    assert "postPoolsDocumentPolicyMigrate" in content
    assert "url: `/api/v2/pools/${poolId}/document-policy-migrations/`" in content


def test_generated_models_cover_contract_pool_runs_schemas() -> None:
    contract = _load_openapi_contract()

    checks = {
        "PoolRun": "poolRun.ts",
        "PoolPublicationAttempt": "poolPublicationAttempt.ts",
        "PoolRunReadinessCheck": "poolRunReadinessCheck.ts",
        "PoolRunReadinessChecklist": "poolRunReadinessChecklist.ts",
        "PoolRunConfirmPublicationReadinessProblemDetails": "poolRunConfirmPublicationReadinessProblemDetails.ts",
        "PoolRunSafeCommandResponse": "poolRunSafeCommandResponse.ts",
        "PoolRunSafeCommandConflict": "poolRunSafeCommandConflict.ts",
        "PoolRunProvenance": "poolRunProvenance.ts",
        "PoolRunRetryChainAttempt": "poolRunRetryChainAttempt.ts",
    }

    for schema_name, model_file in checks.items():
        schema = _schema(contract, schema_name)
        properties = schema.get("properties")
        assert isinstance(properties, dict)
        contract_fields = set(properties.keys())
        generated_fields = _generated_model_fields(model_file)
        assert contract_fields.issubset(generated_fields), (
            f"{schema_name} fields missing in generated model {model_file}: "
            f"{sorted(contract_fields - generated_fields)}"
        )


def test_generated_pool_run_create_request_requires_binding_field() -> None:
    model_path = _repo_root() / "frontend" / "src" / "api" / "generated" / "model" / "poolRunCreateRequest.ts"
    content = model_path.read_text(encoding="utf-8")

    assert re.search(r"pool_workflow_binding_id: string;", content)


def test_generated_pool_workflow_binding_revision_contract_is_present() -> None:
    model_path = _repo_root() / "frontend" / "src" / "api" / "generated" / "model" / "poolWorkflowBindingRead.ts"
    content = model_path.read_text(encoding="utf-8")

    assert re.search(r"binding_id: string;", content)
    assert re.search(r"pool_id: string;", content)
    assert re.search(r"revision: number;", content)
    assert re.search(r"status: PoolWorkflowBindingReadStatus;", content)


def test_generated_pool_workflow_binding_input_keeps_mutating_fields_optional() -> None:
    model_path = _repo_root() / "frontend" / "src" / "api" / "generated" / "model" / "poolWorkflowBindingInput.ts"
    content = model_path.read_text(encoding="utf-8")

    assert re.search(r"binding_id\?: string;", content)
    assert re.search(r"pool_id\?: string;", content)
    assert re.search(r"revision\?: number;", content)
    assert re.search(r"status\?: PoolWorkflowBindingInputStatus;", content)


def test_generated_pool_workflow_binding_preview_response_covers_slot_projection_contract() -> None:
    contract = _load_openapi_contract()
    schema = _schema(contract, "PoolWorkflowBindingPreviewResponse")
    properties = schema.get("properties")
    assert isinstance(properties, dict)

    generated_fields = _generated_model_fields("poolWorkflowBindingPreviewResponse.ts")
    assert {"workflow_binding", "compiled_document_policy_slots", "slot_coverage_summary", "runtime_projection"}.issubset(
        generated_fields
    )
    assert "compiled_document_policy" in generated_fields
    assert set(properties.keys()).issubset(generated_fields), (
        "PoolWorkflowBindingPreviewResponse fields missing in generated model "
        f"poolWorkflowBindingPreviewResponse.ts: {sorted(set(properties.keys()) - generated_fields)}"
    )


def test_generated_pool_workflow_binding_delete_params_require_revision() -> None:
    model_path = (
        _repo_root()
        / "frontend"
        / "src"
        / "api"
        / "generated"
        / "model"
        / "delPoolsWorkflowBindingsDeleteParams.ts"
    )
    content = model_path.read_text(encoding="utf-8")

    assert re.search(r"revision: number;", content)


def test_generated_models_cover_shared_metadata_and_decision_surfaces() -> None:
    contract = _load_openapi_contract()

    checks = {
        "DecisionTable": "decisionTable.ts",
        "PoolODataMetadataCatalogResponse": "poolODataMetadataCatalogResponse.ts",
        "PoolWorkflowBindingInput": "poolWorkflowBindingInput.ts",
        "PoolWorkflowBindingRead": "poolWorkflowBindingRead.ts",
    }

    for schema_name, model_file in checks.items():
        schema = _schema(contract, schema_name)
        properties = schema.get("properties")
        assert isinstance(properties, dict)
        generated_fields = _generated_model_fields(model_file)
        assert set(properties.keys()).issubset(generated_fields), (
            f"{schema_name} fields missing in generated model {model_file}: "
            f"{sorted(set(properties.keys()) - generated_fields)}"
        )


def test_generated_models_cover_document_policy_migration_schemas() -> None:
    contract = _load_openapi_contract()

    checks = {
        "PoolDocumentPolicyMigrationRequest": "poolDocumentPolicyMigrationRequest.ts",
        "PoolDocumentPolicyMigrationResponse": "poolDocumentPolicyMigrationResponse.ts",
        "PoolDocumentPolicyMigrationReport": "poolDocumentPolicyMigrationReport.ts",
        "PoolDocumentPolicyMigrationSource": "poolDocumentPolicyMigrationSource.ts",
        "PoolDocumentPolicyMigrationDecisionRef": "poolDocumentPolicyMigrationDecisionRef.ts",
    }

    for schema_name, model_file in checks.items():
        schema = _schema(contract, schema_name)
        properties = schema.get("properties")
        assert isinstance(properties, dict)
        generated_fields = _generated_model_fields(model_file)
        assert set(properties.keys()).issubset(generated_fields), (
            f"{schema_name} fields missing in generated model {model_file}: "
            f"{sorted(set(properties.keys()) - generated_fields)}"
        )

    report_content = (
        _repo_root()
        / "frontend"
        / "src"
        / "api"
        / "generated"
        / "model"
        / "poolDocumentPolicyMigrationReport.ts"
    ).read_text(encoding="utf-8")
    assert re.search(r"slot_key: string;", report_content)
    assert re.search(r"legacy_payload_removed: boolean;", report_content)
    assert re.search(r"affected_bindings: PoolDocumentPolicyMigrationReportAffectedBindingsItem\[];", report_content)

    affected_binding_content = (
        _repo_root()
        / "frontend"
        / "src"
        / "api"
        / "generated"
        / "model"
        / "poolWorkflowBindingDecisionRef.ts"
    ).read_text(encoding="utf-8")
    assert re.search(r"decision_table_id: string;", affected_binding_content)
    assert re.search(r"decision_key: string;", affected_binding_content)
    assert re.search(r"slot_key\?: string \| null;", affected_binding_content)
    assert re.search(r"decision_revision: number;", affected_binding_content)


def test_generated_pool_runtime_projection_model_covers_slot_lineage_contract() -> None:
    contract = _load_openapi_contract()
    schema = _schema(contract, "PoolRuntimeProjection")
    properties = schema.get("properties")
    assert isinstance(properties, dict)

    generated_fields = _generated_model_fields("poolRuntimeProjection.ts")
    assert set(properties.keys()).issubset(generated_fields)

    projection_content = (
        _repo_root()
        / "frontend"
        / "src"
        / "api"
        / "generated"
        / "model"
        / "poolRuntimeProjectionDocumentPolicyProjection.ts"
    ).read_text(encoding="utf-8")
    assert re.search(r"compiled_document_policy_slots:", projection_content)
    assert re.search(r"slot_coverage_summary:", projection_content)

    policy_ref_content = (
        _repo_root()
        / "frontend"
        / "src"
        / "api"
        / "generated"
        / "model"
        / "poolRuntimeProjectionDocumentPolicyProjectionPolicyRefsItem.ts"
    ).read_text(encoding="utf-8")
    assert re.search(r"slot_key: string \| null;", policy_ref_content)
    assert re.search(
        r"edge_ref: PoolRuntimeProjectionDocumentPolicyProjectionPolicyRefsItemEdgeRef;",
        policy_ref_content,
    )

    slot_coverage_content = (
        _repo_root()
        / "frontend"
        / "src"
        / "api"
        / "generated"
        / "model"
        / "poolRuntimeProjectionDocumentPolicyProjectionSlotCoverageSummary.ts"
    ).read_text(encoding="utf-8")
    assert re.search(r"total_edges: number;", slot_coverage_content)
    assert re.search(r"items: PoolRuntimeProjectionDocumentPolicyProjectionSlotCoverageSummaryItemsItem\[];", slot_coverage_content)


def test_generated_gateway_routes_include_document_policy_migration_path() -> None:
    routes_path = (
        _repo_root()
        / "go-services"
        / "api-gateway"
        / "internal"
        / "routes"
        / "generated"
        / "orchestrator_routes.go"
    )
    content = routes_path.read_text(encoding="utf-8")

    assert 'Path: "/pools/:pool_id/document-policy-migrations/"' in content
    assert 'OperationID: "v2_pools_document_policy_migrate"' in content


def test_generated_retry_chain_attempt_kind_enum_matches_contract() -> None:
    contract = _load_openapi_contract()
    retry_chain_schema = _schema(contract, "PoolRunRetryChainAttempt")
    attempt_kind = retry_chain_schema.get("properties", {}).get("attempt_kind")
    assert isinstance(attempt_kind, dict)
    assert attempt_kind.get("enum") == ["initial", "retry"]

    enum_path = (
        _repo_root()
        / "frontend"
        / "src"
        / "api"
        / "generated"
        / "model"
        / "poolRunRetryChainAttemptAttemptKind.ts"
    )
    enum_content = enum_path.read_text(encoding="utf-8")
    assert re.search(r"initial:\s*['\"]initial['\"]", enum_content)
    assert re.search(r"retry:\s*['\"]retry['\"]", enum_content)


def test_generated_models_cover_graph_metadata_fields_from_contract() -> None:
    contract = _load_openapi_contract()

    checks = {
        "PoolGraphNode": "poolGraphNode.ts",
        "PoolGraphEdge": "poolGraphEdge.ts",
    }

    for schema_name, model_file in checks.items():
        schema = _schema(contract, schema_name)
        properties = schema.get("properties")
        assert isinstance(properties, dict)
        assert "metadata" in properties, f"{schema_name}.metadata missing in OpenAPI contract"

        generated_fields = _generated_model_fields(model_file)
        assert "metadata" in generated_fields, f"{schema_name}.metadata missing in generated {model_file}"


def test_generated_edge_metadata_models_include_document_policy_key() -> None:
    checks = (
        "poolGraphEdgeMetadata.ts",
        "poolTopologySnapshotEdgeInputMetadata.ts",
    )

    for model_file in checks:
        content = (
            _repo_root()
            / "frontend"
            / "src"
            / "api"
            / "generated"
            / "model"
            / model_file
        ).read_text(encoding="utf-8")
        assert re.search(r"document_policy_key\?: string;", content), (
            f"document_policy_key missing in generated metadata model {model_file}"
        )


def test_pool_upsert_generated_client_does_not_expose_workflow_bindings_write_field() -> None:
    contract = _load_openapi_contract()
    schema = _schema(contract, "OrganizationPoolUpsertRequest")
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    assert "workflow_bindings" not in properties

    generated_fields = _generated_model_fields("organizationPoolUpsertRequest.ts")
    assert "workflow_bindings" not in generated_fields


def test_generated_confirm_publication_error_alias_uses_readiness_problem_details_model() -> None:
    generated_v2_path = _repo_root() / "frontend" / "src" / "api" / "generated" / "v2" / "v2.ts"
    content = generated_v2_path.read_text(encoding="utf-8")

    assert re.search(r"import type \{ ErrorType \} from ['\"]\.\./\.\./mutator['\"]", content)
    assert re.search(
        r"import type \{ PoolRunConfirmPublicationReadinessProblemDetails \} from ['\"]\.\./model/poolRunConfirmPublicationReadinessProblemDetails['\"]",
        content,
    )
    assert re.search(r"export type PostPoolsRunsConfirmPublicationError = ErrorType<", content)
    assert "PoolRunConfirmPublicationReadinessProblemDetails" in content
