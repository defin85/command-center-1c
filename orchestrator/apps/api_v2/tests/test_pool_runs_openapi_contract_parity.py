from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from rest_framework import serializers

from apps.api_v2.serializers.common import ExecutionPlanSerializer
from apps.api_v2.views import decisions as decisions_view
from apps.api_v2.views import intercompany_pools as pools_view
from apps.api_v2.views import pool_document_policy_migrations as migration_view


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


def _resolve_schema_reference(contract: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    ref = candidate.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        schema_name = ref.split("/")[-1]
        return _schema(contract, schema_name)
    return candidate


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
        assert ok_ref == "#/components/schemas/PoolRunSafeCommandResponse"
        assert accepted_ref == "#/components/schemas/PoolRunSafeCommandResponse"
        conflict_content = responses["409"]["content"]
        assert isinstance(conflict_content, dict)
        assert conflict_content["application/json"]["schema"]["$ref"] == "#/components/schemas/PoolRunSafeCommandConflict"
        if path.endswith("/confirm-publication/"):
            assert conflict_content["application/problem+json"]["schema"]["$ref"] == (
                "#/components/schemas/PoolRunConfirmPublicationReadinessProblemDetails"
            )


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


def test_pool_run_retry_request_target_database_ids_parity_with_runtime_serializer() -> None:
    contract = _load_openapi_contract()
    retry_request_schema = _schema(contract, "PoolRunRetryRequest")
    properties = retry_request_schema.get("properties")
    assert isinstance(properties, dict)

    target_ids_schema = properties.get("target_database_ids")
    assert isinstance(target_ids_schema, dict)
    assert target_ids_schema.get("type") == "array"
    assert target_ids_schema.get("minItems") == 1
    assert target_ids_schema.get("items") == {"type": "string", "format": "uuid"}

    runtime_field = pools_view.PoolRunRetryRequestSerializer().fields.get("target_database_ids")
    assert isinstance(runtime_field, serializers.ListField)
    assert runtime_field.required is False
    assert runtime_field.allow_empty is False
    assert isinstance(runtime_field.child, serializers.UUIDField)

    raw_target_ids = [
        UUID("11111111-1111-1111-1111-111111111111"),
        UUID("77777777-7777-7777-7777-777777777777"),
        "11111111-1111-1111-1111-111111111111",
        "   ",
        None,
    ]
    assert pools_view._normalize_retry_target_ids(raw_target_ids) == [
        "11111111-1111-1111-1111-111111111111",
        "77777777-7777-7777-7777-777777777777",
    ]


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
    readiness_checklist = properties.get("readiness_checklist")
    assert readiness_checklist == {"$ref": "#/components/schemas/PoolRunReadinessChecklist"}


def test_pool_run_create_request_requires_binding_matches_runtime_serializer() -> None:
    contract = _load_openapi_contract()
    request_schema = _schema(contract, "PoolRunCreateRequest")
    properties = request_schema.get("properties")
    assert isinstance(properties, dict)
    assert "pool_workflow_binding_id" in properties

    required = request_schema.get("required")
    assert isinstance(required, list)
    assert {"pool_id", "pool_workflow_binding_id", "direction", "period_start", "run_input"}.issubset(set(required))

    runtime_field = pools_view.PoolRunCreateRequestSerializer().fields.get("pool_workflow_binding_id")
    assert isinstance(runtime_field, serializers.CharField)
    assert runtime_field.required is True
    assert runtime_field.allow_blank is False


def test_pool_workflow_binding_write_schema_keeps_server_managed_fields_optional_for_create_requests() -> None:
    contract = _load_openapi_contract()
    binding_schema = _schema(contract, "PoolWorkflowBindingInput")
    properties = binding_schema.get("properties")
    assert isinstance(properties, dict)
    required = binding_schema.get("required")
    assert isinstance(required, list)
    assert set(required) == {"binding_profile_revision_id", "effective_from"}

    revision_schema = properties.get("revision")
    assert isinstance(revision_schema, dict)
    assert revision_schema.get("type") == "integer"
    assert revision_schema.get("minimum") == 1

    runtime_field = pools_view.PoolWorkflowBindingInputSerializer().fields.get("revision")
    assert isinstance(runtime_field, serializers.IntegerField)
    assert runtime_field.required is False
    assert runtime_field.min_value == 1

    binding_id_field = pools_view.PoolWorkflowBindingInputSerializer().fields.get("binding_id")
    assert isinstance(binding_id_field, serializers.CharField)
    assert binding_id_field.required is False

    pool_id_field = pools_view.PoolWorkflowBindingInputSerializer().fields.get("pool_id")
    assert isinstance(pool_id_field, serializers.UUIDField)
    assert pool_id_field.required is False

    binding_profile_revision_id_field = pools_view.PoolWorkflowBindingInputSerializer().fields.get(
        "binding_profile_revision_id"
    )
    assert isinstance(binding_profile_revision_id_field, serializers.CharField)
    assert binding_profile_revision_id_field.required is True
    assert "workflow" not in properties

    status_field = pools_view.PoolWorkflowBindingInputSerializer().fields.get("status")
    assert isinstance(status_field, serializers.ChoiceField)
    assert status_field.required is False


def test_pool_workflow_binding_read_schema_requires_server_managed_fields() -> None:
    contract = _load_openapi_contract()
    binding_schema = _schema(contract, "PoolWorkflowBindingRead")
    properties = binding_schema.get("properties")
    assert isinstance(properties, dict)
    required = binding_schema.get("required", [])
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
    }.issubset(set(required))

    revision_schema = properties.get("revision")
    assert isinstance(revision_schema, dict)
    assert revision_schema.get("type") == "integer"
    assert revision_schema.get("minimum") == 1

    runtime_fields = pools_view.PoolWorkflowBindingReadSerializer().fields
    assert runtime_fields["binding_id"].required is True
    assert runtime_fields["pool_id"].required is True
    assert runtime_fields["binding_profile_id"].required is True
    assert runtime_fields["binding_profile_revision_id"].required is True
    assert runtime_fields["binding_profile_revision_number"].required is True
    assert runtime_fields["revision"].required is True
    assert runtime_fields["status"].required is True
    assert runtime_fields["resolved_profile"].required is True


def test_pool_workflow_binding_preview_schema_exposes_slot_coverage_summary() -> None:
    contract = _load_openapi_contract()
    preview_schema = _schema(contract, "PoolWorkflowBindingPreviewResponse")
    properties = preview_schema.get("properties")
    assert isinstance(properties, dict)

    assert properties["compiled_document_policy_slots"]["type"] == "object"
    slot_coverage_summary = properties.get("slot_coverage_summary")
    assert isinstance(slot_coverage_summary, dict)
    assert slot_coverage_summary["type"] == "object"
    assert slot_coverage_summary["properties"]["total_edges"] == {"type": "integer"}
    assert slot_coverage_summary["properties"]["items"]["type"] == "array"

    required = preview_schema.get("required")
    assert isinstance(required, list)
    assert {"workflow_binding", "compiled_document_policy_slots", "slot_coverage_summary", "runtime_projection"}.issubset(
        set(required)
    )
    assert "compiled_document_policy" not in required


def test_pool_runtime_projection_schema_exposes_slot_lineage_contract() -> None:
    contract = _load_openapi_contract()
    runtime_projection_schema = _schema(contract, "PoolRuntimeProjection")
    runtime_projection_properties = runtime_projection_schema.get("properties")
    assert isinstance(runtime_projection_properties, dict)

    workflow_binding = runtime_projection_properties.get("workflow_binding")
    assert isinstance(workflow_binding, dict)
    workflow_binding_properties = workflow_binding.get("properties")
    assert isinstance(workflow_binding_properties, dict)
    assert workflow_binding_properties["binding_profile_id"] == {"type": "string"}
    assert workflow_binding_properties["binding_profile_revision_id"] == {"type": "string"}
    assert workflow_binding_properties["binding_profile_revision_number"] == {
        "type": "integer",
        "minimum": 1,
    }
    assert workflow_binding_properties["attachment_revision"] == {
        "type": "integer",
        "minimum": 1,
    }

    document_policy_projection = runtime_projection_properties.get("document_policy_projection")
    assert isinstance(document_policy_projection, dict)
    projection_properties = document_policy_projection.get("properties")
    assert isinstance(projection_properties, dict)

    assert projection_properties["compiled_document_policy_slots"]["type"] == "object"

    slot_coverage_summary = projection_properties.get("slot_coverage_summary")
    assert isinstance(slot_coverage_summary, dict)
    assert slot_coverage_summary["type"] == "object"
    assert slot_coverage_summary["properties"]["total_edges"] == {"type": "integer"}
    assert slot_coverage_summary["properties"]["items"]["type"] == "array"

    policy_refs = projection_properties.get("policy_refs")
    assert isinstance(policy_refs, dict)
    assert policy_refs["type"] == "array"
    policy_ref_item = policy_refs.get("items")
    assert isinstance(policy_ref_item, dict)
    policy_ref_properties = policy_ref_item.get("properties")
    assert isinstance(policy_ref_properties, dict)
    assert policy_ref_properties["slot_key"]["type"] == "string"
    assert policy_ref_properties["slot_key"]["nullable"] is True
    edge_ref = policy_ref_properties.get("edge_ref")
    assert isinstance(edge_ref, dict)
    edge_ref_properties = edge_ref.get("properties")
    assert isinstance(edge_ref_properties, dict)
    assert {"parent_node_id", "child_node_id"}.issubset(set(edge_ref_properties.keys()))


def test_pool_workflow_binding_mutating_paths_expose_revision_conflict_contract() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    upsert_path = paths.get("/api/v2/pools/workflow-bindings/upsert/")
    assert isinstance(upsert_path, dict)
    upsert_post = upsert_path.get("post")
    assert isinstance(upsert_post, dict)
    request_schema = (
        upsert_post["requestBody"]["content"]["application/json"]["schema"]
    )
    assert request_schema["$ref"] == "#/components/schemas/PoolWorkflowBindingUpsertRequest"
    upsert_request_schema = _schema(contract, "PoolWorkflowBindingUpsertRequest")
    request_properties = upsert_request_schema.get("properties")
    assert isinstance(request_properties, dict)
    assert request_properties["workflow_binding"]["$ref"] == "#/components/schemas/PoolWorkflowBindingInput"
    upsert_responses = upsert_post.get("responses")
    assert isinstance(upsert_responses, dict)
    assert (
        upsert_responses["409"]["content"]["application/problem+json"]["schema"]["$ref"]
        == "#/components/schemas/ProblemDetailsError"
    )

    detail_path = paths.get("/api/v2/pools/workflow-bindings/{binding_id}/")
    assert isinstance(detail_path, dict)
    delete = detail_path.get("delete")
    assert isinstance(delete, dict)
    parameters = delete.get("parameters")
    assert isinstance(parameters, list)

    revision_parameter = next(
        (parameter for parameter in parameters if parameter.get("name") == "revision"),
        None,
    )
    assert isinstance(revision_parameter, dict)
    assert revision_parameter.get("in") == "query"
    assert revision_parameter.get("required") is True
    assert revision_parameter.get("schema") == {"type": "integer", "minimum": 1}
    assert (
        delete.get("responses", {})["409"]["content"]["application/problem+json"]["schema"]["$ref"]
        == "#/components/schemas/ProblemDetailsError"
    )

    runtime_delete_field = pools_view.PoolWorkflowBindingDeleteQuerySerializer().fields.get("revision")
    assert isinstance(runtime_delete_field, serializers.IntegerField)
    assert runtime_delete_field.required is True
    assert runtime_delete_field.min_value == 1


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


def test_pool_publication_attempt_schema_contains_canonical_diagnostics() -> None:
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
    extended_fields = {
        "external_document_identity",
        "publication_identity_strategy",
        "request_summary",
        "response_summary",
    }
    assert canonical_fields.issubset(contract_fields)
    assert extended_fields.issubset(contract_fields)


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


def test_pool_topology_and_graph_schemas_include_metadata_contract_fields() -> None:
    contract = _load_openapi_contract()

    checks = (
        ("PoolTopologySnapshotNodeInput", pools_view.PoolTopologySnapshotNodeInputSerializer),
        ("PoolTopologySnapshotEdgeInput", pools_view.PoolTopologySnapshotEdgeInputSerializer),
        ("PoolGraphNode", pools_view.PoolGraphNodeSerializer),
        ("PoolGraphEdge", pools_view.PoolGraphEdgeSerializer),
    )

    for schema_name, serializer_cls in checks:
        schema = _schema(contract, schema_name)
        properties = schema.get("properties")
        assert isinstance(properties, dict)
        assert "metadata" in properties, f"{schema_name}.metadata missing in OpenAPI contract"

        if schema_name in {"PoolTopologySnapshotEdgeInput", "PoolGraphEdge"}:
            metadata_schema = properties["metadata"]
            assert isinstance(metadata_schema, dict)
            assert metadata_schema.get("type") == "object"
            assert metadata_schema.get("additionalProperties") is True
            metadata_properties = metadata_schema.get("properties")
            assert isinstance(metadata_properties, dict)
            document_policy_key = metadata_properties.get("document_policy_key")
            assert isinstance(document_policy_key, dict)
            assert document_policy_key.get("type") == "string"

        runtime_fields = set(serializer_cls().fields.keys())
        contract_fields = set(properties.keys())
        assert runtime_fields.issubset(contract_fields)


def test_pool_metadata_catalog_paths_and_schemas_are_in_contract() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    get_path = "/api/v2/pools/odata-metadata/catalog/"
    refresh_path = "/api/v2/pools/odata-metadata/catalog/refresh/"

    get_item = paths.get(get_path)
    assert isinstance(get_item, dict), f"path missing: {get_path}"
    get_op = get_item.get("get")
    assert isinstance(get_op, dict), f"get operation missing: {get_path}"
    assert get_op.get("operationId") == "v2_pools_odata_metadata_catalog_get"

    get_parameters = get_op.get("parameters")
    assert isinstance(get_parameters, list)
    database_id_param = next(
        (
            item
            for item in get_parameters
            if isinstance(item, dict)
            and item.get("in") == "query"
            and item.get("name") == "database_id"
        ),
        None,
    )
    assert isinstance(database_id_param, dict), "query parameter database_id is missing"
    assert database_id_param.get("required") is True

    get_responses = get_op.get("responses")
    assert isinstance(get_responses, dict)
    assert {"200", "400", "401", "404", "409"}.issubset(set(get_responses.keys()))
    get_ok_ref = get_responses["200"]["content"]["application/json"]["schema"]["$ref"]
    assert get_ok_ref == "#/components/schemas/PoolODataMetadataCatalogResponse"

    refresh_item = paths.get(refresh_path)
    assert isinstance(refresh_item, dict), f"path missing: {refresh_path}"
    refresh_op = refresh_item.get("post")
    assert isinstance(refresh_op, dict), f"post operation missing: {refresh_path}"
    assert refresh_op.get("operationId") == "v2_pools_odata_metadata_catalog_refresh"

    request_body = refresh_op.get("requestBody")
    assert isinstance(request_body, dict)
    refresh_request_ref = request_body["content"]["application/json"]["schema"]["$ref"]
    assert refresh_request_ref == "#/components/schemas/PoolODataMetadataCatalogRefreshRequest"

    refresh_responses = refresh_op.get("responses")
    assert isinstance(refresh_responses, dict)
    assert {"200", "400", "401", "404", "409"}.issubset(set(refresh_responses.keys()))
    refresh_ok_ref = refresh_responses["200"]["content"]["application/json"]["schema"]["$ref"]
    assert refresh_ok_ref == "#/components/schemas/PoolODataMetadataCatalogResponse"

    response_schema = _schema(contract, "PoolODataMetadataCatalogResponse")
    response_properties = response_schema.get("properties")
    assert isinstance(response_properties, dict)
    runtime_response_fields = set(pools_view.PoolODataMetadataCatalogResponseSerializer().fields.keys())
    assert runtime_response_fields.issubset(set(response_properties.keys()))

    request_schema = _schema(contract, "PoolODataMetadataCatalogRefreshRequest")
    request_properties = request_schema.get("properties")
    assert isinstance(request_properties, dict)
    runtime_request_fields = set(pools_view.PoolODataMetadataCatalogRefreshRequestSerializer().fields.keys())
    assert runtime_request_fields.issubset(set(request_properties.keys()))


def test_document_policy_migration_path_and_schemas_are_in_contract() -> None:
    contract = _load_openapi_contract()
    paths = contract.get("paths")
    assert isinstance(paths, dict)

    path = "/api/v2/pools/{pool_id}/document-policy-migrations/"
    path_item = paths.get(path)
    assert isinstance(path_item, dict), f"path missing: {path}"
    post = path_item.get("post")
    assert isinstance(post, dict), f"post missing: {path}"
    assert post.get("operationId") == "v2_pools_document_policy_migrate"

    request_body = post.get("requestBody")
    assert isinstance(request_body, dict)
    request_ref = request_body["content"]["application/json"]["schema"]["$ref"]
    assert request_ref == "#/components/schemas/PoolDocumentPolicyMigrationRequest"

    responses = post.get("responses")
    assert isinstance(responses, dict)
    assert {"200", "201", "400", "401", "404"}.issubset(set(responses.keys()))
    ok_ref = responses["200"]["content"]["application/json"]["schema"]["$ref"]
    created_ref = responses["201"]["content"]["application/json"]["schema"]["$ref"]
    assert ok_ref == "#/components/schemas/PoolDocumentPolicyMigrationResponse"
    assert created_ref == "#/components/schemas/PoolDocumentPolicyMigrationResponse"
    assert (
        responses["400"]["content"]["application/problem+json"]["schema"]["$ref"]
        == "#/components/schemas/ProblemDetailsError"
    )

    request_schema = _schema(contract, "PoolDocumentPolicyMigrationRequest")
    request_properties = request_schema.get("properties")
    assert isinstance(request_properties, dict)
    runtime_request_fields = set(
        migration_view.PoolDocumentPolicyMigrationRequestSerializer().fields.keys()
    )
    assert runtime_request_fields.issubset(set(request_properties.keys()))

    response_schema = _schema(contract, "PoolDocumentPolicyMigrationResponse")
    response_properties = response_schema.get("properties")
    assert isinstance(response_properties, dict)
    runtime_response_fields = set(
        migration_view.PoolDocumentPolicyMigrationResponseSerializer().fields.keys()
    )
    assert runtime_response_fields.issubset(set(response_properties.keys()))

    report_schema = _schema(contract, "PoolDocumentPolicyMigrationReport")
    report_properties = report_schema.get("properties")
    assert isinstance(report_properties, dict)
    assert {"slot_key", "legacy_payload_removed", "affected_bindings"}.issubset(
        set(report_properties.keys())
    )
    affected_bindings = report_properties.get("affected_bindings")
    assert isinstance(affected_bindings, dict)
    assert affected_bindings.get("type") == "array"
    affected_binding_item = affected_bindings.get("items")
    assert isinstance(affected_binding_item, dict)
    affected_binding_properties = affected_binding_item.get("properties")
    assert isinstance(affected_binding_properties, dict)
    assert {"binding_id", "revision", "updated", "decision_ref"}.issubset(
        set(affected_binding_properties.keys())
    )


def test_decision_table_schema_includes_metadata_context_and_compatibility_fields() -> None:
    contract = _load_openapi_contract()
    decision_schema = _schema(contract, "DecisionTable")
    decision_properties = decision_schema.get("properties")
    assert isinstance(decision_properties, dict)

    runtime_decision_fields = set(decisions_view.DecisionTableReadSerializer().fields.keys())
    assert runtime_decision_fields.issubset(set(decision_properties.keys()))

    metadata_context_schema = _schema(contract, "DecisionRevisionMetadataContext")
    metadata_context_properties = metadata_context_schema.get("properties")
    assert isinstance(metadata_context_properties, dict)
    runtime_metadata_context_fields = set(
        decisions_view.DecisionRevisionMetadataContextSerializer().fields.keys()
    )
    assert runtime_metadata_context_fields.issubset(set(metadata_context_properties.keys()))


    compatibility_schema = _schema(contract, "DecisionMetadataCompatibility")
    compatibility_properties = compatibility_schema.get("properties")
    assert isinstance(compatibility_properties, dict)
    runtime_compatibility_fields = set(
        decisions_view.DecisionMetadataCompatibilitySerializer().fields.keys()
    )
    assert runtime_compatibility_fields.issubset(set(compatibility_properties.keys()))


def test_problem_details_error_schema_supports_field_and_referential_error_shapes() -> None:
    contract = _load_openapi_contract()
    problem_schema = _schema(contract, "ProblemDetailsError")
    properties = problem_schema.get("properties")
    assert isinstance(properties, dict)

    errors_schema = properties.get("errors")
    assert isinstance(errors_schema, dict)
    one_of = errors_schema.get("oneOf")
    assert isinstance(one_of, list) and one_of

    field_errors_variant: dict[str, Any] | None = None
    referential_variant: dict[str, Any] | None = None
    for variant_raw in one_of:
        assert isinstance(variant_raw, dict)
        variant = _resolve_schema_reference(contract, variant_raw)
        if variant.get("type") == "object":
            field_errors_variant = variant
        if variant.get("type") == "array":
            referential_variant = variant

    assert isinstance(field_errors_variant, dict), "field-errors variant missing in ProblemDetailsError.errors"
    additional = field_errors_variant.get("additionalProperties")
    assert isinstance(additional, dict)
    assert isinstance(additional.get("oneOf"), list) and additional["oneOf"]

    assert isinstance(referential_variant, dict), "referential array variant missing in ProblemDetailsError.errors"
    items_raw = referential_variant.get("items")
    assert isinstance(items_raw, dict)
    referential_item_schema = _resolve_schema_reference(contract, items_raw)
    required = referential_item_schema.get("required")
    assert isinstance(required, list)
    assert {"code", "path", "detail"}.issubset(set(required))


def test_confirm_publication_readiness_problem_details_schema_matches_runtime_serializer() -> None:
    contract = _load_openapi_contract()
    schema = _schema(contract, "PoolRunConfirmPublicationReadinessProblemDetails")
    properties = schema.get("properties")
    assert isinstance(properties, dict)

    runtime_fields = set(pools_view.PoolRunConfirmPublicationReadinessProblemDetailsSerializer().fields.keys())
    assert runtime_fields.issubset(set(properties.keys()))

    code_schema = properties.get("code")
    assert isinstance(code_schema, dict)
    assert code_schema.get("enum") == ["POOL_RUN_READINESS_BLOCKED"]

    errors_schema = properties.get("errors")
    assert isinstance(errors_schema, dict)
    assert errors_schema.get("type") == "array"
    assert errors_schema.get("items") == {"$ref": "#/components/schemas/PoolRunReadinessBlocker"}


def test_pool_run_readiness_blocker_schema_includes_topology_alias_context_fields() -> None:
    contract = _load_openapi_contract()
    schema = _schema(contract, "PoolRunReadinessBlocker")
    properties = schema.get("properties")
    assert isinstance(properties, dict)

    assert {"edge_ref", "participant_side", "required_role"}.issubset(set(properties.keys()))

    edge_ref_schema = properties.get("edge_ref")
    assert isinstance(edge_ref_schema, dict)
    assert edge_ref_schema == {"$ref": "#/components/schemas/PoolRunReadinessBlockerEdgeRef"}

    edge_ref_component = _schema(contract, "PoolRunReadinessBlockerEdgeRef")
    edge_ref_properties = edge_ref_component.get("properties")
    assert isinstance(edge_ref_properties, dict)
    assert {"parent_node_id", "child_node_id"}.issubset(set(edge_ref_properties.keys()))

    participant_side_schema = properties.get("participant_side")
    assert isinstance(participant_side_schema, dict)
    assert participant_side_schema.get("type") == "string"

    required_role_schema = properties.get("required_role")
    assert isinstance(required_role_schema, dict)
    assert required_role_schema.get("type") == "string"
