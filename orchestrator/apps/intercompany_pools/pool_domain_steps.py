from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PoolRun, PoolRunDirection, PoolRunMode
from .publication import publish_run_documents, retry_failed_run_documents


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
    run_input = _run_input(run)
    prepared_input = execution_context.get("pool_runtime_prepared_input")
    prepared_payload = dict(prepared_input) if isinstance(prepared_input, dict) else {}
    starting_amount = _parse_decimal(prepared_payload.get("starting_amount") or run_input.get("starting_amount"))
    distribution_summary = {
        "direction": "top_down",
        "starting_amount": _decimal_to_string(starting_amount),
        "source": "run_input",
    }
    _update_execution_context(
        execution=execution,
        updates={"pool_runtime_distribution": distribution_summary},
    )
    return {
        "step": "distribution_calculation",
        "pool_run_id": str(run.id),
        "distribution": distribution_summary,
    }


def _execute_distribution_bottom_up(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    run_input = _run_input(run)
    source_rows = _source_rows(run_input=run_input)
    source_total = _sum_source_amounts(source_rows)
    distribution_summary = {
        "direction": "bottom_up",
        "source_rows_count": len(source_rows),
        "source_total_amount": _decimal_to_string(source_total),
    }

    prepared_input = execution_context.get("pool_runtime_prepared_input")
    if isinstance(prepared_input, dict):
        prepared_total = _parse_decimal(prepared_input.get("source_total_amount"))
        distribution_summary["prepared_total_amount"] = _decimal_to_string(prepared_total)

    _update_execution_context(
        execution=execution,
        updates={"pool_runtime_distribution": distribution_summary},
    )
    return {
        "step": "distribution_calculation",
        "pool_run_id": str(run.id),
        "distribution": distribution_summary,
    }


def _execute_reconciliation(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    distribution = execution_context.get("pool_runtime_distribution")
    distribution_payload = dict(distribution) if isinstance(distribution, dict) else {}
    prepared = execution_context.get("pool_runtime_prepared_input")
    prepared_payload = dict(prepared) if isinstance(prepared, dict) else {}

    report: dict[str, Any] = {
        "run_direction": run.direction,
        "distribution_available": bool(distribution_payload),
        "prepared_input_available": bool(prepared_payload),
        "status": "ok",
        "generated_at": timezone.now().isoformat(),
    }

    source_total = _parse_decimal(
        distribution_payload.get("source_total_amount") or prepared_payload.get("source_total_amount")
    )
    starting_amount = _parse_decimal(
        distribution_payload.get("starting_amount") or prepared_payload.get("starting_amount")
    )
    if source_total is not None and starting_amount is not None:
        report["balanced"] = source_total == starting_amount
        report["source_total_amount"] = _decimal_to_string(source_total)
        report["starting_amount"] = _decimal_to_string(starting_amount)
        if source_total != starting_amount:
            report["status"] = "drift"
            report["delta"] = _decimal_to_string(source_total - starting_amount)

    _update_execution_context(execution=execution, updates={"pool_runtime_reconciliation": report})
    return {
        "step": "reconciliation_report",
        "pool_run_id": str(run.id),
        "report": report,
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
    approval_state = _resolve_approval_state(run=run, execution_context=execution_context)
    if run.mode == PoolRunMode.SAFE and approval_state != APPROVAL_STATE_APPROVED:
        raise ValueError(
            "POOL_RUNTIME_APPROVAL_REQUIRED: publication step requires approved state for safe mode"
        )

    publication_payload = _publication_payload(run=run, rendered_data=rendered_data)
    entity_name = str(publication_payload.get("entity_name") or "Document_IntercompanyPoolDistribution").strip()
    documents_by_database = _normalize_documents_by_database(
        publication_payload.get("documents_by_database")
    )
    max_attempts = _positive_int(publication_payload.get("max_attempts"), default=5)
    retry_interval_seconds = _positive_int(
        publication_payload.get("retry_interval_seconds"),
        default=0,
    )
    external_key_field = str(publication_payload.get("external_key_field") or "ExternalRunKey").strip() or "ExternalRunKey"

    _update_execution_context(execution=execution, updates={"publication_step_state": PUBLICATION_STEP_STATE_STARTED})

    if not documents_by_database:
        _update_execution_context(execution=execution, updates={"publication_step_state": PUBLICATION_STEP_STATE_COMPLETED})
        return {
            "step": "publication_odata",
            "pool_run_id": str(run.id),
            "status": "skipped_no_targets",
            "entity_name": entity_name,
            "documents_targets": 0,
        }

    retry_failed_only = bool(publication_payload.get("retry_failed_only"))
    try:
        if retry_failed_only:
            summary = retry_failed_run_documents(
                run=run,
                entity_name=entity_name,
                documents_by_database=documents_by_database,
                max_attempts=max_attempts,
                retry_interval_seconds=retry_interval_seconds,
                external_key_field=external_key_field,
            )
        else:
            summary = publish_run_documents(
                run=run,
                entity_name=entity_name,
                documents_by_database=documents_by_database,
                max_attempts=max_attempts,
                retry_interval_seconds=retry_interval_seconds,
                external_key_field=external_key_field,
            )
    except (ValidationError, ValueError) as exc:
        raise ValueError(f"POOL_RUNTIME_PUBLICATION_FAILED: {exc}") from exc

    _update_execution_context(execution=execution, updates={"publication_step_state": PUBLICATION_STEP_STATE_COMPLETED})

    return {
        "step": "publication_odata",
        "pool_run_id": str(run.id),
        "status": "published",
        "entity_name": entity_name,
        "documents_targets": summary.total_targets,
        "succeeded_targets": summary.succeeded_targets,
        "failed_targets": summary.failed_targets,
        "max_attempts": summary.max_attempts,
    }


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


def _publication_payload(*, run: PoolRun, rendered_data: dict[str, Any]) -> dict[str, Any]:
    run_input = _run_input(run)
    payload = run_input.get("publication")
    if isinstance(payload, Mapping):
        return dict(payload)

    if isinstance(run_input.get("documents_by_database"), Mapping):
        return {
            "documents_by_database": run_input.get("documents_by_database"),
            "entity_name": run_input.get("entity_name"),
            "max_attempts": run_input.get("max_attempts"),
            "retry_interval_seconds": run_input.get("retry_interval_seconds"),
            "external_key_field": run_input.get("external_key_field"),
        }

    runtime_data = rendered_data.get("pool_runtime")
    if isinstance(runtime_data, Mapping):
        return dict(runtime_data)
    return {}


def _normalize_documents_by_database(value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for raw_database_id, raw_documents in value.items():
        database_id = str(raw_database_id or "").strip()
        if not database_id:
            continue
        if not isinstance(raw_documents, list):
            continue
        documents = [dict(document) for document in raw_documents if isinstance(document, Mapping)]
        if not documents:
            continue
        result[database_id] = documents
    return result


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


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
