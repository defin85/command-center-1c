from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from django.utils import timezone

from .document_plan_artifact_contract import (
    POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY,
    build_publication_payload_from_document_plan_artifact,
    compile_document_plan_artifact_v1,
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
from .master_data_errors import MasterDataResolveError
from .master_data_feature_flags import (
    MasterDataGateConfigInvalidError,
    is_pool_master_data_gate_enabled,
)
from .master_data_gate import execute_master_data_resolve_upsert_gate
from .models import Organization, PoolRun, PoolRunDirection, PoolRunMode
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
MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING = "MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING"


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

    publication_payload = build_publication_payload_from_artifact(
        artifact=distribution_artifact,
        run_input=_run_input(run),
    )
    topology = load_runtime_topology_for_period(run=run)
    document_plan_artifact = compile_document_plan_artifact_v1(
        run=run,
        distribution_artifact=distribution_artifact,
        topology=topology,
    )
    if document_plan_artifact is not None:
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

    if not gate_enabled:
        summary = {
            "status": "skipped",
            "reason": "feature_disabled",
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "targets_count": 0,
            "bindings_count": 0,
        }
        _update_execution_context(
            execution=execution,
            updates={"pool_runtime_master_data_gate": summary},
        )
        return {
            "step": "master_data_gate",
            "pool_run_id": str(run.id),
            "summary": summary,
        }

    missing_bindings = _collect_missing_master_party_bindings(run=run)
    if missing_bindings:
        diagnostic = {
            "error_code": MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING,
            "missing_count": len(missing_bindings),
            "missing_organization_bindings": missing_bindings,
        }
        summary = {
            "status": "failed",
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "error_code": MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING,
            "detail": "Missing Organization->Party binding for publication target organizations.",
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
        raise ValueError(f"{MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING}: diagnostic={diagnostic_json}")

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
    }
    _update_execution_context(execution=execution, updates=updates)
    return {
        "step": "master_data_gate",
        "pool_run_id": str(run.id),
        "summary": summary,
        "publication_payload": publication_payload,
        "master_data_binding_artifact": binding_artifact,
    }


def _collect_missing_master_party_bindings(*, run: PoolRun) -> list[dict[str, str]]:
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

    missing: list[dict[str, str]] = []
    for organization in organizations:
        if organization.master_party_id is not None:
            continue
        missing.append(
            {
                "organization_id": str(organization.id),
                "name": str(organization.name or ""),
                "inn": str(organization.inn or ""),
                "database_id": str(organization.database_id) if organization.database_id else "",
            }
        )

    missing.sort(
        key=lambda item: (
            item.get("name", ""),
            item.get("inn", ""),
            item.get("organization_id", ""),
        )
    )
    return missing


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
