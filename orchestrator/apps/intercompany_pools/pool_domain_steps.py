from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from django.utils import timezone

from .models import PoolRun, PoolRunDirection, PoolRunMode
from .runtime_distribution import (
    DISTRIBUTION_ARTIFACT_VERSION,
    build_publication_payload_from_artifact,
    compute_distribution_runtime_state,
)


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
_OP_PUBLICATION = "pool.publication_odata"
POOL_RUNTIME_PUBLICATION_PATH_DISABLED = "POOL_RUNTIME_PUBLICATION_PATH_DISABLED"
POOL_DISTRIBUTION_ARTIFACT_INVALID = "POOL_DISTRIBUTION_ARTIFACT_INVALID"
POOL_DISTRIBUTION_BALANCE_MISMATCH = "POOL_DISTRIBUTION_BALANCE_MISMATCH"
POOL_DISTRIBUTION_COVERAGE_GAP = "POOL_DISTRIBUTION_COVERAGE_GAP"

_REQUIRED_DISTRIBUTION_ARTIFACT_FIELDS = {
    "version",
    "topology_version_ref",
    "node_totals",
    "edge_allocations",
    "coverage",
    "balance",
    "input_provenance",
}


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
    _ = execution_context
    return _execute_distribution_calculation(
        run=run,
        execution=execution,
        expected_direction=PoolRunDirection.TOP_DOWN,
    )


def _execute_distribution_bottom_up(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    _ = execution_context
    return _execute_distribution_calculation(
        run=run,
        execution=execution,
        expected_direction=PoolRunDirection.BOTTOM_UP,
    )


def _execute_reconciliation(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    distribution_artifact = _validate_distribution_artifact_contract(
        artifact=execution_context.get("pool_runtime_distribution_artifact")
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

    _update_execution_context(
        execution=execution,
        updates={
            "pool_runtime_reconciliation": report,
            "pool_runtime_publication_payload": publication_payload,
        },
    )
    return {
        "step": "reconciliation_report",
        "pool_run_id": str(run.id),
        "report": report,
        "distribution_artifact": distribution_artifact,
        "publication_payload": publication_payload,
    }


def _execute_distribution_calculation(
    *,
    run: PoolRun,
    execution: Any,
    expected_direction: str,
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
    distribution_artifact = _validate_distribution_artifact_contract(artifact=artifact_payload)
    publication_payload_raw = runtime_state.get("publication_payload")
    publication_payload = (
        dict(publication_payload_raw)
        if isinstance(publication_payload_raw, Mapping)
        else build_publication_payload_from_artifact(
            artifact=distribution_artifact,
            run_input=_run_input(run),
        )
    )
    if not publication_payload:
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: publication_payload is missing for distribution artifact"
        )

    _update_execution_context(
        execution=execution,
        updates={
            "pool_runtime_distribution": distribution_summary,
            "pool_runtime_distribution_artifact": distribution_artifact,
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


def _validate_distribution_artifact_contract(*, artifact: Any) -> dict[str, Any]:
    if not isinstance(artifact, Mapping):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: distribution_artifact.v1 is missing in execution context"
        )
    artifact_payload = dict(artifact)
    missing_fields = sorted(
        field_name
        for field_name in _REQUIRED_DISTRIBUTION_ARTIFACT_FIELDS
        if field_name not in artifact_payload
    )
    if missing_fields:
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: missing required artifact fields: {', '.join(missing_fields)}"
        )
    version = str(artifact_payload.get("version") or "").strip()
    if version != DISTRIBUTION_ARTIFACT_VERSION:
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: unexpected artifact version '{version or '<empty>'}'"
        )
    if not isinstance(artifact_payload.get("coverage"), Mapping):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: field 'coverage' must be an object in distribution_artifact.v1"
        )
    if not isinstance(artifact_payload.get("balance"), Mapping):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: field 'balance' must be an object in distribution_artifact.v1"
        )
    if not isinstance(artifact_payload.get("node_totals"), list):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: field 'node_totals' must be an array in distribution_artifact.v1"
        )
    if not isinstance(artifact_payload.get("edge_allocations"), list):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: field 'edge_allocations' must be an array in distribution_artifact.v1"
        )
    if not isinstance(artifact_payload.get("input_provenance"), Mapping):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: field 'input_provenance' must be an object in distribution_artifact.v1"
        )
    return artifact_payload


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


def _run_input(run: PoolRun) -> dict[str, Any]:
    return dict(run.run_input) if isinstance(run.run_input, dict) else {}


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
