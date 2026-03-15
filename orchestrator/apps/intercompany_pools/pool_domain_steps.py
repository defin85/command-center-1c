from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from django.utils import timezone

from .document_plan_artifact_contract import (
    POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY,
    POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_SLOTS_CONTEXT_KEY,
    POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY,
    POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY,
    build_publication_payload_from_document_plan_artifact,
    compile_document_plan_artifact_v1,
    validate_compiled_document_policy_slots_snapshot,
    validate_document_plan_artifact_v1,
)
from .distribution_artifact_contract import (
    POOL_DISTRIBUTION_ARTIFACT_INVALID,
    POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY,
    resolve_distribution_artifact_for_downstream_compile,
    validate_distribution_artifact_v1,
)
from .master_data_artifact_contract import (
    MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
    POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY,
)
from .master_data_errors import (
    MASTER_DATA_BINDING_AMBIGUOUS,
    MASTER_DATA_BINDING_CONFLICT,
    MASTER_DATA_ENTITY_NOT_FOUND,
    MasterDataResolveError,
)
from .master_data_feature_flags import (
    MasterDataGateConfigInvalidError,
    is_pool_master_data_gate_enabled,
)
from .master_data_gate import (
    collect_master_data_resolution_readiness_blockers,
    execute_master_data_resolve_upsert_gate,
    publication_payload_requires_master_data_resolution,
)
from .models import Organization, PoolMasterParty, PoolRun, PoolRunDirection, PoolRunMode
from .organization_party_binding_backfill import (
    REMEDIATION_REASON_AMBIGUOUS_MATCH,
    REMEDIATION_REASON_CANDIDATE_ALREADY_BOUND,
    REMEDIATION_REASON_NO_MATCH,
)
from .runtime_distribution import (
    build_publication_payload_from_artifact,
    compute_distribution_runtime_state,
    load_runtime_topology_for_period,
)
from .run_input_sanitizer import sanitize_run_input_for_runtime_contract


APPROVAL_STATE_NOT_REQUIRED = "not_required"
APPROVAL_STATE_PREPARING = "preparing"
APPROVAL_STATE_AWAITING_APPROVAL = "awaiting_approval"
APPROVAL_STATE_APPROVED = "approved"

PUBLICATION_STEP_STATE_NOT_ENQUEUED = "not_enqueued"
PUBLICATION_STEP_STATE_QUEUED = "queued"
PUBLICATION_STEP_STATE_STARTED = "started"
PUBLICATION_STEP_STATE_COMPLETED = "completed"

_OP_PREPARE_INPUT = "pool.prepare_input"
_OP_DISTRIBUTION_TOP_DOWN = "pool.distribution_calculation.top_down"
_OP_DISTRIBUTION_BOTTOM_UP = "pool.distribution_calculation.bottom_up"
_OP_RECONCILIATION = "pool.reconciliation_report"
_OP_APPROVAL_GATE = "pool.approval_gate"
_OP_MASTER_DATA_GATE = "pool.master_data_gate"
_OP_PUBLICATION = "pool.publication_odata"
POOL_RUNTIME_PUBLICATION_PATH_DISABLED = "POOL_RUNTIME_PUBLICATION_PATH_DISABLED"
POOL_RUNTIME_RETRY_PAYLOAD_INVALID = "POOL_RUNTIME_RETRY_PAYLOAD_INVALID"
POOL_DISTRIBUTION_BALANCE_MISMATCH = "POOL_DISTRIBUTION_BALANCE_MISMATCH"
POOL_DISTRIBUTION_COVERAGE_GAP = "POOL_DISTRIBUTION_COVERAGE_GAP"
POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_REQUIRED = "POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_REQUIRED"
MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING = "MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING"
POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY = "pool_runtime_readiness_blockers"


def execute_pool_runtime_step(
    *,
    operation_type: str,
    rendered_data: dict[str, Any],
    context: dict[str, Any],
    execution: Any,
) -> dict[str, Any]:
    run = _resolve_pool_run(context=context, execution=execution)
    execution_context = execution.input_context if isinstance(getattr(execution, "input_context", None), dict) else {}

    if operation_type == _OP_PREPARE_INPUT:
        return _execute_prepare_input(run=run, execution=execution, execution_context=execution_context)

    if operation_type == _OP_DISTRIBUTION_TOP_DOWN:
        return _execute_distribution_top_down(run=run, execution=execution, execution_context=execution_context)

    if operation_type == _OP_DISTRIBUTION_BOTTOM_UP:
        return _execute_distribution_bottom_up(run=run, execution=execution, execution_context=execution_context)

    if operation_type == _OP_RECONCILIATION:
        return _execute_reconciliation(run=run, execution=execution, execution_context=execution_context)

    if operation_type == _OP_APPROVAL_GATE:
        return _execute_approval_gate(run=run, execution=execution, execution_context=execution_context)

    if operation_type == _OP_MASTER_DATA_GATE:
        return _execute_master_data_gate(
            run=run,
            execution=execution,
            execution_context=execution_context,
        )

    if operation_type == _OP_PUBLICATION:
        return _execute_publication(
            run=run,
            execution=execution,
            execution_context=execution_context,
            rendered_data=rendered_data,
        )

    raise ValueError(f"POOL_RUNTIME_STEP_UNSUPPORTED: unsupported operation_type '{operation_type}'")


def _resolve_pool_run(*, context: dict[str, Any], execution: Any) -> PoolRun:
    pool_run_id = str(context.get("pool_run_id") or "").strip()
    if not pool_run_id:
        raise ValueError("POOL_RUNTIME_CONTEXT_INVALID: missing pool_run_id in workflow context")

    run = PoolRun.objects.filter(id=pool_run_id).first()
    if run is None:
        raise ValueError(f"POOL_RUNTIME_RUN_NOT_FOUND: pool run '{pool_run_id}' was not found")

    execution_id = str(getattr(execution, "id", "") or "").strip()
    if execution_id and run.workflow_execution_id and str(run.workflow_execution_id) != execution_id:
        raise ValueError(
            "POOL_RUNTIME_RUN_LINK_MISMATCH: "
            f"run '{run.id}' is linked to execution '{run.workflow_execution_id}', got '{execution_id}'"
        )

    execution_tenant_id = str(getattr(execution, "tenant_id", "") or "").strip()
    if execution_tenant_id and execution_tenant_id != str(run.tenant_id):
        raise ValueError(
            "POOL_RUNTIME_TENANT_MISMATCH: "
            f"execution tenant '{execution_tenant_id}' does not match run tenant '{run.tenant_id}'"
        )

    return run


def _execute_prepare_input(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    run_input = _run_input(run)
    approval_state = _resolve_approval_state(run=run, execution_context=execution_context)
    publication_step_state = _resolve_publication_step_state(
        run=run,
        approval_state=approval_state,
        execution_context=execution_context,
    )
    approved_at = _resolve_approved_at(run=run, execution_context=execution_context)

    prepared_payload: dict[str, Any] = {
        "direction": run.direction,
        "mode": run.mode,
    }
    source_rows = _source_rows(run_input=run_input)
    if run.direction == PoolRunDirection.TOP_DOWN:
        starting_amount = _parse_decimal(run_input.get("starting_amount"))
        prepared_payload["starting_amount"] = _decimal_to_string(starting_amount)
    else:
        prepared_payload["source_rows_count"] = len(source_rows)
        prepared_payload["source_total_amount"] = _decimal_to_string(_sum_source_amounts(source_rows))
        source_artifact_id = str(run_input.get("source_artifact_id") or "").strip()
        if source_artifact_id:
            prepared_payload["source_artifact_id"] = source_artifact_id

    updates: dict[str, Any] = {
        "approval_state": approval_state,
        "publication_step_state": publication_step_state,
        "pool_runtime_prepared_input": prepared_payload,
    }
    if approved_at is not None:
        updates["approved_at"] = approved_at
    _update_execution_context(execution=execution, updates=updates)

    return {
        "step": "prepare_input",
        "pool_run_id": str(run.id),
        "prepared_input": prepared_payload,
        "approval_state": approval_state,
        "publication_step_state": publication_step_state,
    }


def _execute_distribution_top_down(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    return _execute_distribution_calculation(
        run=run,
        execution=execution,
        expected_direction=PoolRunDirection.TOP_DOWN,
        execution_context=execution_context,
    )


def _execute_distribution_bottom_up(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    return _execute_distribution_calculation(
        run=run,
        execution=execution,
        expected_direction=PoolRunDirection.BOTTOM_UP,
        execution_context=execution_context,
    )


def _execute_reconciliation(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    distribution_artifact = resolve_distribution_artifact_for_downstream_compile(
        execution_context=execution_context
    )
    coverage_payload = distribution_artifact.get("coverage")
    coverage = dict(coverage_payload) if isinstance(coverage_payload, Mapping) else {}
    balance_payload = distribution_artifact.get("balance")
    balance = dict(balance_payload) if isinstance(balance_payload, Mapping) else {}

    if not bool(balance.get("is_balanced")):
        delta = _decimal_to_string(_parse_decimal(balance.get("delta")))
        source_total = _decimal_to_string(_parse_decimal(balance.get("source_total")))
        distributed_total = _decimal_to_string(_parse_decimal(balance.get("distributed_total")))
        raise ValueError(
            f"{POOL_DISTRIBUTION_BALANCE_MISMATCH}: "
            f"source_total={source_total}, distributed_total={distributed_total}, delta={delta}"
        )

    if not bool(coverage.get("is_full")):
        missing_nodes_raw = coverage.get("missing_target_node_ids")
        missing_nodes = (
            [str(node_id).strip() for node_id in missing_nodes_raw if str(node_id).strip()]
            if isinstance(missing_nodes_raw, list)
            else []
        )
        missing_nodes_text = ", ".join(missing_nodes) if missing_nodes else "unknown"
        raise ValueError(
            f"{POOL_DISTRIBUTION_COVERAGE_GAP}: missing publish-target nodes: {missing_nodes_text}"
        )

    document_plan_artifact = _resolve_persisted_document_plan_artifact(
        execution_context=execution_context
    )
    if document_plan_artifact is None:
        compiled_document_policy_slots = _resolve_compiled_document_policy_slots_for_execution_context(
            execution_context=execution_context
        )
        compiled_document_policy = _resolve_compiled_document_policy_for_execution_context(
            execution_context=execution_context
        )
        document_policy_source = _resolve_document_policy_source_for_execution_context(
            execution_context=execution_context
        )
        if (
            _has_workflow_binding_context(execution_context)
            and compiled_document_policy_slots is None
        ):
            raise ValueError(
                f"{POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_REQUIRED}: "
                "compiled document policy slots are required for workflow-bound reconciliation"
            )
        publication_payload = build_publication_payload_from_artifact(
            artifact=distribution_artifact,
            run_input=_run_input(run),
        )
        topology = load_runtime_topology_for_period(run=run)
        try:
            document_plan_artifact = compile_document_plan_artifact_v1(
                run=run,
                distribution_artifact=distribution_artifact,
                topology=topology,
                compiled_document_policy_slots=compiled_document_policy_slots,
                compiled_document_policy=compiled_document_policy,
                document_policy_source=document_policy_source,
            )
        except ValueError as exc:
            blocker = _build_readiness_blocker_from_error(exc)
            if blocker is not None:
                _update_execution_context(
                    execution=execution,
                    updates={POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: [blocker]},
                )
            raise
        if document_plan_artifact is not None:
            publication_payload = build_publication_payload_from_document_plan_artifact(
                artifact=document_plan_artifact,
                run_input=_run_input(run),
            )
    else:
        publication_payload = build_publication_payload_from_document_plan_artifact(
            artifact=document_plan_artifact,
            run_input=_run_input(run),
        )
    locked_retry_payload = _resolve_locked_retry_publication_payload(
        execution_context=execution_context
    )
    if locked_retry_payload is not None:
        publication_payload = locked_retry_payload
    report: dict[str, Any] = {
        "run_direction": run.direction,
        "distribution_artifact_version": distribution_artifact.get("version"),
        "topology_version_ref": distribution_artifact.get("topology_version_ref"),
        "balanced": True,
        "coverage_full": True,
        "missing_target_node_ids": [],
        "source_total_amount": balance.get("source_total"),
        "distributed_total_amount": balance.get("distributed_total"),
        "delta": balance.get("delta"),
        "status": "ok",
        "generated_at": timezone.now().isoformat(),
    }

    execution_updates: dict[str, Any] = {
        "pool_runtime_reconciliation": report,
        "pool_runtime_publication_payload": publication_payload,
        POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: [],
    }
    if document_plan_artifact is not None:
        execution_updates[POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY] = document_plan_artifact

    _update_execution_context(
        execution=execution,
        updates=execution_updates,
    )
    response = {
        "step": "reconciliation_report",
        "pool_run_id": str(run.id),
        "report": report,
        "distribution_artifact": distribution_artifact,
        "publication_payload": publication_payload,
    }
    if document_plan_artifact is not None:
        response["document_plan_artifact"] = document_plan_artifact
    return response


def _resolve_persisted_document_plan_artifact(
    *,
    execution_context: dict[str, Any],
) -> dict[str, Any] | None:
    artifact_raw = execution_context.get(POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY)
    if artifact_raw is None:
        return None
    return validate_document_plan_artifact_v1(artifact=artifact_raw)


def _resolve_compiled_document_policy_for_execution_context(
    *,
    execution_context: dict[str, Any],
) -> dict[str, Any] | None:
    raw_policy = execution_context.get(POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY)
    if not isinstance(raw_policy, Mapping):
        return None
    return dict(raw_policy)


def _resolve_compiled_document_policy_slots_for_execution_context(
    *,
    execution_context: dict[str, Any],
) -> dict[str, dict[str, Any]] | None:
    return validate_compiled_document_policy_slots_snapshot(
        execution_context.get(POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_SLOTS_CONTEXT_KEY)
    )


def _resolve_document_policy_source_for_execution_context(
    *,
    execution_context: dict[str, Any],
) -> str | None:
    source = str(execution_context.get(POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY) or "").strip()
    return source or None


def _has_workflow_binding_context(execution_context: dict[str, Any]) -> bool:
    binding = execution_context.get("pool_workflow_binding")
    return isinstance(binding, Mapping) and bool(binding)


def _execute_distribution_calculation(
    *,
    run: PoolRun,
    execution: Any,
    expected_direction: str,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    if run.direction != expected_direction:
        raise ValueError(
            "POOL_DISTRIBUTION_DIRECTION_MISMATCH: "
            f"run direction '{run.direction}' does not match operation direction '{expected_direction}'"
        )

    runtime_state = compute_distribution_runtime_state(run=run, run_input=_run_input(run))
    summary_payload = runtime_state.get("summary")
    distribution_summary = dict(summary_payload) if isinstance(summary_payload, Mapping) else {}
    artifact_payload = runtime_state.get("artifact")
    distribution_artifact = validate_distribution_artifact_v1(artifact=artifact_payload)
    publication_payload_raw = runtime_state.get("publication_payload")
    publication_payload = (
        dict(publication_payload_raw)
        if isinstance(publication_payload_raw, Mapping)
        else build_publication_payload_from_artifact(
            artifact=distribution_artifact,
            run_input=_run_input(run),
        )
    )
    locked_retry_payload = _resolve_locked_retry_publication_payload(
        execution_context=execution_context
    )
    if locked_retry_payload is not None:
        publication_payload = locked_retry_payload
    if not publication_payload:
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: publication_payload is missing for distribution artifact"
        )

    _update_execution_context(
        execution=execution,
        updates={
            "pool_runtime_distribution": distribution_summary,
            POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY: distribution_artifact,
            "pool_runtime_publication_payload": publication_payload,
        },
    )
    return {
        "step": "distribution_calculation",
        "pool_run_id": str(run.id),
        "distribution": distribution_summary,
        "distribution_artifact": distribution_artifact,
        "publication_payload": publication_payload,
    }

def _execute_approval_gate(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    if run.mode == PoolRunMode.UNSAFE:
        approval_state = APPROVAL_STATE_NOT_REQUIRED
        publication_step_state = PUBLICATION_STEP_STATE_QUEUED
        awaiting_approval = False
    elif _resolve_approved_at(run=run, execution_context=execution_context) is not None:
        approval_state = APPROVAL_STATE_APPROVED
        publication_step_state = PUBLICATION_STEP_STATE_QUEUED
        awaiting_approval = False
    else:
        approval_state = APPROVAL_STATE_AWAITING_APPROVAL
        publication_step_state = PUBLICATION_STEP_STATE_NOT_ENQUEUED
        awaiting_approval = True

    updates = {
        "approval_state": approval_state,
        "publication_step_state": publication_step_state,
    }
    approved_at = _resolve_approved_at(run=run, execution_context=execution_context)
    if approved_at is not None:
        updates["approved_at"] = approved_at
    _update_execution_context(execution=execution, updates=updates)

    return {
        "step": "approval_gate",
        "pool_run_id": str(run.id),
        "approval_state": approval_state,
        "publication_step_state": publication_step_state,
        "awaiting_approval": awaiting_approval,
    }


def _execute_publication(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
    rendered_data: dict[str, Any],
) -> dict[str, Any]:
    _ = (run, execution, execution_context, rendered_data)
    raise ValueError(
        f"{POOL_RUNTIME_PUBLICATION_PATH_DISABLED}: "
        "publication OData side effects are disabled in orchestrator pool-domain runtime"
    )


def _execute_master_data_gate(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    requires_resolution = publication_payload_requires_master_data_resolution(
        execution_context=execution_context,
    )
    try:
        gate_enabled = is_pool_master_data_gate_enabled(
            tenant_id=str(run.tenant_id),
            fail_closed_on_invalid=True,
        )
    except MasterDataGateConfigInvalidError as exc:
        diagnostic = exc.to_diagnostic()
        summary = {
            "status": "failed",
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "error_code": exc.code,
            "detail": exc.detail,
            "diagnostic": diagnostic,
        }
        _update_execution_context(
            execution=execution,
            updates={"pool_runtime_master_data_gate": summary},
        )
        diagnostic_json = json.dumps(
            diagnostic,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        raise ValueError(f"{exc.code}: diagnostic={diagnostic_json}") from exc

    if not gate_enabled and not requires_resolution:
        summary = {
            "status": "skipped",
            "reason": "feature_disabled",
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "targets_count": 0,
            "bindings_count": 0,
        }
        _update_execution_context(
            execution=execution,
            updates={
                "pool_runtime_master_data_gate": summary,
                POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: [],
            },
        )
        return {
            "step": "master_data_gate",
            "pool_run_id": str(run.id),
            "summary": summary,
        }

    readiness_blockers = _collect_master_data_readiness_blockers(
        run=run,
        execution_context=execution_context,
    )
    if readiness_blockers:
        primary_blocker = readiness_blockers[0]
        error_code = str(primary_blocker.get("code") or "").strip() or MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING
        detail = str(primary_blocker.get("detail") or "").strip() or "Master-data readiness blocked publication."
        diagnostic = _build_master_data_gate_blocked_diagnostic(
            readiness_blockers=readiness_blockers,
            error_code=error_code,
        )
        summary = {
            "status": "failed",
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "error_code": error_code,
            "detail": detail,
            "diagnostic": diagnostic,
        }
        _update_execution_context(
            execution=execution,
            updates={
                "pool_runtime_master_data_gate": summary,
                POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: readiness_blockers,
            },
        )
        diagnostic_json = json.dumps(
            diagnostic,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        raise ValueError(f"{error_code}: diagnostic={diagnostic_json}")

    try:
        gate_result = execute_master_data_resolve_upsert_gate(
            run=run,
            execution_context=execution_context,
        )
    except MasterDataResolveError as exc:
        diagnostic = exc.to_diagnostic()
        summary = {
            "status": "failed",
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "error_code": exc.code,
            "detail": exc.detail,
            "diagnostic": diagnostic,
        }
        readiness_blockers = [_build_readiness_blocker_from_master_data_error(exc)]
        _update_execution_context(
            execution=execution,
            updates={
                "pool_runtime_master_data_gate": summary,
                POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: readiness_blockers,
            },
        )
        diagnostic_json = json.dumps(
            diagnostic,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        raise ValueError(f"{exc.code}: diagnostic={diagnostic_json}") from exc

    publication_payload = gate_result.get("publication_payload")
    binding_artifact = gate_result.get("binding_artifact")
    summary = (
        dict(gate_result.get("summary"))
        if isinstance(gate_result.get("summary"), Mapping)
        else {}
    )
    summary.setdefault("status", "completed")
    summary.setdefault("mode", MASTER_DATA_GATE_MODE_RESOLVE_UPSERT)

    updates = {
        "pool_runtime_publication_payload": publication_payload,
        POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY: binding_artifact,
        "pool_runtime_master_data_gate": summary,
        POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: [],
    }
    _update_execution_context(execution=execution, updates=updates)
    return {
        "step": "master_data_gate",
        "pool_run_id": str(run.id),
        "summary": summary,
        "publication_payload": publication_payload,
        "master_data_binding_artifact": binding_artifact,
    }


def _collect_master_data_readiness_blockers(
    *,
    run: PoolRun,
    execution_context: dict[str, Any],
) -> list[dict[str, Any]]:
    blockers = [
        *_collect_missing_master_party_binding_blockers(run=run),
        *collect_master_data_resolution_readiness_blockers(
            run=run,
            execution_context=execution_context,
        ),
    ]
    return _sort_readiness_blockers(blockers)


def _collect_missing_master_party_binding_blockers(*, run: PoolRun) -> list[dict[str, Any]]:
    try:
        topology = load_runtime_topology_for_period(run=run)
    except ValueError as exc:
        message = str(exc)
        if message.startswith("POOL_DISTRIBUTION_INPUT_INVALID") or message.startswith("POOL_DISTRIBUTION_GRAPH_INVALID"):
            return []
        raise
    raw_node_models = topology.get("node_models")
    if not isinstance(raw_node_models, Mapping):
        return []
    node_models = dict(raw_node_models)

    raw_target_node_ids = topology.get("publish_target_node_ids")
    if not isinstance(raw_target_node_ids, list):
        return []

    organization_ids: set[str] = set()
    for raw_node_id in raw_target_node_ids:
        node_id = str(raw_node_id or "").strip()
        if not node_id:
            continue
        node = node_models.get(node_id)
        if node is None:
            continue
        organization_id = str(getattr(node, "organization_id", "") or "").strip()
        if organization_id:
            organization_ids.add(organization_id)

    if not organization_ids:
        return []

    organizations = Organization.objects.filter(
        tenant_id=run.tenant_id,
        id__in=organization_ids,
    ).only("id", "name", "inn", "database_id", "master_party_id")

    bound_party_ids = {
        str(value)
        for value in Organization.objects.filter(tenant_id=run.tenant_id)
        .exclude(master_party_id__isnull=True)
        .values_list("master_party_id", flat=True)
    }

    missing: list[dict[str, Any]] = []
    for organization in organizations:
        if organization.master_party_id is not None:
            continue
        candidate_parties = _find_master_party_candidates_for_organization(organization=organization)
        remediation_reason = REMEDIATION_REASON_NO_MATCH
        if len(candidate_parties) > 1:
            remediation_reason = REMEDIATION_REASON_AMBIGUOUS_MATCH
        elif len(candidate_parties) == 1 and str(candidate_parties[0].id) in bound_party_ids:
            remediation_reason = REMEDIATION_REASON_CANDIDATE_ALREADY_BOUND
        elif len(candidate_parties) == 1:
            remediation_reason = "candidate_available"
        missing.append(
            {
                "code": MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING,
                "detail": "Missing Organization->Party binding for publication target organization.",
                "kind": "organization_party_binding_missing",
                "organization_id": str(organization.id),
                "database_id": str(organization.database_id) if organization.database_id else "",
                "diagnostic": {
                    "organization_name": str(organization.name or ""),
                    "organization_inn": str(organization.inn or ""),
                    "remediation_reason": remediation_reason,
                    "candidate_party_ids": [str(item.id) for item in candidate_parties],
                    "candidate_party_canonical_ids": [
                        str(item.canonical_id) for item in candidate_parties
                    ],
                },
            }
        )

    missing.sort(
        key=lambda item: (
            str(item.get("database_id") or ""),
            item.get("organization_id", ""),
        )
    )
    return missing


def _find_master_party_candidates_for_organization(*, organization: Organization) -> list[PoolMasterParty]:
    inn = str(organization.inn or "").strip()
    if not inn:
        return []

    candidates = PoolMasterParty.objects.filter(
        tenant_id=organization.tenant_id,
        inn=inn,
        is_our_organization=True,
    )
    kpp = str(organization.kpp or "").strip()
    if kpp:
        candidates = candidates.filter(kpp=kpp)
    return list(candidates.order_by("canonical_id", "id"))


def _build_master_data_gate_blocked_diagnostic(
    *,
    readiness_blockers: list[dict[str, Any]],
    error_code: str,
) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {
        "error_code": error_code,
        "blockers_count": len(readiness_blockers),
    }
    primary_diagnostic = readiness_blockers[0].get("diagnostic")
    if isinstance(primary_diagnostic, Mapping):
        diagnostic.update(dict(primary_diagnostic))
    primary_entity_type = str(readiness_blockers[0].get("entity_name") or "").strip()
    primary_database_id = str(readiness_blockers[0].get("database_id") or "").strip()
    if primary_entity_type and "entity_type" not in diagnostic:
        diagnostic["entity_type"] = primary_entity_type
    if primary_database_id and "target_database_id" not in diagnostic:
        diagnostic["target_database_id"] = primary_database_id

    missing_organization_bindings: list[dict[str, Any]] = []
    for blocker in readiness_blockers:
        if str(blocker.get("code") or "").strip() != MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING:
            continue
        row = {
            "organization_id": blocker.get("organization_id"),
            "database_id": blocker.get("database_id"),
        }
        blocker_diagnostic = blocker.get("diagnostic")
        if isinstance(blocker_diagnostic, Mapping):
            if "organization_name" in blocker_diagnostic:
                row["name"] = blocker_diagnostic.get("organization_name")
            if "organization_inn" in blocker_diagnostic:
                row["inn"] = blocker_diagnostic.get("organization_inn")
            if "remediation_reason" in blocker_diagnostic:
                row["remediation_reason"] = blocker_diagnostic.get("remediation_reason")
            if "candidate_party_ids" in blocker_diagnostic:
                row["candidate_party_ids"] = blocker_diagnostic.get("candidate_party_ids")
            if "candidate_party_canonical_ids" in blocker_diagnostic:
                row["candidate_party_canonical_ids"] = blocker_diagnostic.get("candidate_party_canonical_ids")
        missing_organization_bindings.append(row)

    if missing_organization_bindings:
        diagnostic["missing_count"] = len(missing_organization_bindings)
        diagnostic["missing_organization_bindings"] = missing_organization_bindings

    return diagnostic


def _build_readiness_blocker_from_master_data_error(exc: MasterDataResolveError) -> dict[str, Any]:
    blocker: dict[str, Any] = {
        "code": exc.code,
        "detail": exc.detail,
        "diagnostic": exc.to_diagnostic(),
    }
    if exc.code == MASTER_DATA_ENTITY_NOT_FOUND:
        blocker["kind"] = "canonical_entity_missing"
    elif exc.code == MASTER_DATA_BINDING_AMBIGUOUS:
        blocker["kind"] = "binding_ambiguous"
    elif exc.code == MASTER_DATA_BINDING_CONFLICT:
        blocker["kind"] = "binding_conflict"
    if exc.entity_type:
        blocker["entity_name"] = exc.entity_type
    if exc.canonical_id:
        blocker["field_or_table_path"] = exc.canonical_id
    if exc.target_database_id:
        blocker["database_id"] = exc.target_database_id
    return blocker


def _sort_readiness_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    code_priority = {
        MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING: 0,
        MASTER_DATA_BINDING_CONFLICT: 10,
        MASTER_DATA_BINDING_AMBIGUOUS: 20,
        MASTER_DATA_ENTITY_NOT_FOUND: 30,
    }
    return sorted(
        blockers,
        key=lambda blocker: (
            code_priority.get(str(blocker.get("code") or "").strip(), 100),
            str(blocker.get("kind") or ""),
            str(blocker.get("database_id") or ""),
            str(blocker.get("organization_id") or ""),
            str(blocker.get("entity_name") or ""),
            str(blocker.get("field_or_table_path") or ""),
            str(blocker.get("detail") or ""),
        ),
    )


def _resolve_locked_retry_publication_payload(
    *,
    execution_context: dict[str, Any],
) -> dict[str, Any] | None:
    retry_settings_raw = execution_context.get("pool_runtime_retry_settings")
    retry_settings = dict(retry_settings_raw) if isinstance(retry_settings_raw, Mapping) else {}
    if not bool(retry_settings.get("use_retry_subset_payload")):
        return None

    payload_raw = execution_context.get("pool_runtime_publication_payload")
    if not isinstance(payload_raw, Mapping):
        raise ValueError(
            f"{POOL_RUNTIME_RETRY_PAYLOAD_INVALID}: "
            "pool_runtime_publication_payload is required when use_retry_subset_payload=true"
        )
    publication_payload = dict(payload_raw)
    pool_runtime_payload = publication_payload.get("pool_runtime")
    if not isinstance(pool_runtime_payload, Mapping):
        raise ValueError(
            f"{POOL_RUNTIME_RETRY_PAYLOAD_INVALID}: "
            "pool_runtime_publication_payload.pool_runtime must be an object"
        )
    documents_by_database = pool_runtime_payload.get("documents_by_database")
    if not isinstance(documents_by_database, Mapping):
        raise ValueError(
            f"{POOL_RUNTIME_RETRY_PAYLOAD_INVALID}: "
            "pool_runtime_publication_payload.pool_runtime.documents_by_database must be an object"
        )
    return publication_payload


def _build_readiness_blocker_from_error(exc: ValueError) -> dict[str, Any] | None:
    message = str(exc).strip()
    if ":" not in message:
        return None
    raw_code, raw_detail = message.split(":", 1)
    code = raw_code.strip()
    detail = raw_detail.strip()
    if not code:
        return None

    blocker: dict[str, Any] = {
        "code": code,
        "detail": detail,
    }
    entity_marker = "for entity '"
    if entity_marker in detail:
        entity_name = detail.split(entity_marker, 1)[1].split("'", 1)[0].strip()
        if entity_name:
            blocker["entity_name"] = entity_name
    table_marker = ".table_parts_mapping."
    if table_marker in detail:
        table_part_name = detail.split(table_marker, 1)[1].split("[", 1)[0].split(" ", 1)[0].strip()
        if table_part_name:
            blocker["field_or_table_path"] = table_part_name
    field_marker = ".field_mapping."
    if "field_or_table_path" not in blocker and field_marker in detail:
        field_name = detail.split(field_marker, 1)[1].split(" ", 1)[0].strip()
        if field_name:
            blocker["field_or_table_path"] = field_name
    return blocker


def _run_input(run: PoolRun) -> dict[str, Any]:
    return sanitize_run_input_for_runtime_contract(run_input=run.run_input)


def _source_rows(*, run_input: dict[str, Any]) -> list[dict[str, Any]]:
    source_payload = run_input.get("source_payload")
    if isinstance(source_payload, list):
        return [dict(item) for item in source_payload if isinstance(item, Mapping)]
    if isinstance(source_payload, Mapping):
        rows = source_payload.get("rows")
        if isinstance(rows, list):
            return [dict(item) for item in rows if isinstance(item, Mapping)]
    return []


def _sum_source_amounts(source_rows: list[dict[str, Any]]) -> Decimal | None:
    total = Decimal("0")
    has_amounts = False
    for row in source_rows:
        amount = _parse_decimal(row.get("amount"))
        if amount is None:
            continue
        total += amount
        has_amounts = True
    if not has_amounts:
        return None
    return total


def _resolve_approval_state(*, run: PoolRun, execution_context: dict[str, Any]) -> str:
    if run.mode == PoolRunMode.UNSAFE:
        return APPROVAL_STATE_NOT_REQUIRED
    if _resolve_approved_at(run=run, execution_context=execution_context) is not None:
        return APPROVAL_STATE_APPROVED
    raw_state = str(execution_context.get("approval_state") or "").strip().lower()
    if raw_state in {APPROVAL_STATE_PREPARING, APPROVAL_STATE_AWAITING_APPROVAL, APPROVAL_STATE_APPROVED}:
        return raw_state
    return APPROVAL_STATE_PREPARING


def _resolve_publication_step_state(
    *,
    run: PoolRun,
    approval_state: str,
    execution_context: dict[str, Any],
) -> str:
    raw_state = str(execution_context.get("publication_step_state") or "").strip().lower()
    if raw_state in {
        PUBLICATION_STEP_STATE_NOT_ENQUEUED,
        PUBLICATION_STEP_STATE_QUEUED,
        PUBLICATION_STEP_STATE_STARTED,
        PUBLICATION_STEP_STATE_COMPLETED,
    }:
        return raw_state
    if run.mode == PoolRunMode.SAFE and approval_state != APPROVAL_STATE_APPROVED:
        return PUBLICATION_STEP_STATE_NOT_ENQUEUED
    return PUBLICATION_STEP_STATE_QUEUED


def _resolve_approved_at(*, run: PoolRun, execution_context: dict[str, Any]) -> str | None:
    context_value = execution_context.get("approved_at")
    if isinstance(context_value, str) and context_value.strip():
        return context_value.strip()
    if context_value is not None and not isinstance(context_value, str):
        return str(context_value)
    if run.publication_confirmed_at is not None:
        return run.publication_confirmed_at.isoformat()
    return None


def _update_execution_context(*, execution: Any, updates: dict[str, Any]) -> None:
    if not updates:
        return
    current = execution.input_context if isinstance(getattr(execution, "input_context", None), dict) else {}
    next_context = dict(current)
    changed = False
    for key, value in updates.items():
        if next_context.get(key) != value:
            next_context[key] = value
            changed = True
    if not changed:
        return
    execution.input_context = next_context
    execution.save(update_fields=["input_context"])


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")
