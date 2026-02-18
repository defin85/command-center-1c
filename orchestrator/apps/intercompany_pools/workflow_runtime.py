from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.operations.services import OperationsService
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate

from .models import PoolRun, PoolRunMode, PoolSchemaTemplate, PoolSchemaTemplateFormat
from .runtime_template_registry import sync_pool_runtime_template_registry
from .workflow_compiler import PoolWorkflowRunContext, compile_pool_execution_plan


User = get_user_model()

_DEFAULT_TEMPLATE_CODE = "__runtime-default__"
_DEFAULT_TEMPLATE_NAME = "Pools Runtime Default Template"

APPROVAL_STATE_NOT_REQUIRED = "not_required"
APPROVAL_STATE_PREPARING = "preparing"
APPROVAL_STATE_AWAITING_APPROVAL = "awaiting_approval"
APPROVAL_STATE_APPROVED = "approved"

PUBLICATION_STEP_STATE_NOT_ENQUEUED = "not_enqueued"
PUBLICATION_STEP_STATE_QUEUED = "queued"
PUBLICATION_STEP_STATE_STARTED = "started"
PUBLICATION_STEP_STATE_COMPLETED = "completed"

ATTEMPT_KIND_INITIAL = "initial"
ATTEMPT_KIND_RETRY = "retry"


@dataclass(frozen=True)
class PoolWorkflowStartResult:
    run: PoolRun
    execution_id: str | None
    enqueue_success: bool
    enqueue_status: str
    enqueue_error: str | None
    created_execution: bool


@dataclass(frozen=True)
class PoolWorkflowRetryStartResult:
    run: PoolRun
    execution_id: str
    operation_id: str | None
    enqueue_success: bool
    enqueue_status: str
    enqueue_error: str | None


def start_pool_run_workflow_execution(
    *,
    run: PoolRun,
    requested_by: User | None = None,
) -> PoolWorkflowStartResult:
    execution_id: str | None = None
    created_execution = False

    with transaction.atomic():
        locked_run = (
            PoolRun.objects.select_for_update()
            .get(id=run.id)
        )

        if locked_run.workflow_execution_id:
            return PoolWorkflowStartResult(
                run=locked_run,
                execution_id=str(locked_run.workflow_execution_id),
                enqueue_success=True,
                enqueue_status=locked_run.workflow_status or "linked",
                enqueue_error=None,
                created_execution=False,
            )

        sync_pool_runtime_template_registry()
        schema_template = locked_run.schema_template or _get_or_create_default_schema_template(locked_run)
        plan = compile_pool_execution_plan(
            schema_template=schema_template,
            run_context=PoolWorkflowRunContext(
                pool_id=str(locked_run.pool_id),
                period_start=locked_run.period_start,
                period_end=locked_run.period_end,
                direction=locked_run.direction,
                mode=locked_run.mode,
                run_input=locked_run.run_input if isinstance(locked_run.run_input, dict) else {},
            ),
        )
        save_fields = {
            "updated_at",
            "workflow_execution_id",
            "workflow_status",
            "execution_backend",
            "workflow_template_name",
        }

        if locked_run.schema_template_id is None:
            locked_run.schema_template = schema_template
            save_fields.add("schema_template")

        if locked_run.status == PoolRun.STATUS_DRAFT:
            locked_run.mark_validated(
                summary=locked_run.validation_summary,
                diagnostics=locked_run.diagnostics,
            )
            save_fields.update({"status", "validated_at", "validation_summary", "diagnostics"})

        if (
            locked_run.mode == PoolRunMode.UNSAFE
            and locked_run.publication_confirmed_at is None
        ):
            locked_run.confirm_publication(confirmed_by=requested_by)
            save_fields.update({"publication_confirmed_at", "publication_confirmed_by"})

        workflow_template = _resolve_or_create_workflow_template(plan=plan, requested_by=requested_by)
        execution = workflow_template.create_execution(
            _build_input_context(run=locked_run),
            tenant=locked_run.tenant,
            execution_consumer="pools",
        )
        execution.input_context = _with_lineage_metadata(
            input_context=execution.input_context,
            execution_id=str(execution.id),
            root_workflow_run_id=str(execution.id),
            parent_workflow_run_id=None,
            attempt_number=1,
            attempt_kind=ATTEMPT_KIND_INITIAL,
        )
        execution.execution_plan = _build_execution_plan_snapshot(
            run=locked_run,
            plan=plan,
            workflow_template=workflow_template,
            execution_context=execution.input_context,
        )
        execution.bindings = _build_execution_bindings(plan=plan)
        execution.save(update_fields=["input_context", "execution_plan", "bindings"])

        locked_run.workflow_execution_id = execution.id
        locked_run.workflow_status = execution.status
        locked_run.execution_backend = "workflow_core"
        locked_run.workflow_template_name = workflow_template.name

        locked_run.save(update_fields=sorted(save_fields))
        locked_run.add_audit_event(
            event_type="run.workflow_execution_linked",
            actor=requested_by,
            status_before=locked_run.status,
            status_after=locked_run.status,
            payload={
                "workflow_execution_id": str(execution.id),
                "workflow_template_name": workflow_template.name,
                "plan_key": plan.plan_key,
                "definition_key": plan.plan_key,
                "approval_required": locked_run.mode == PoolRunMode.SAFE,
            },
        )
        execution_id = str(execution.id)
        created_execution = True

    enqueue_result = OperationsService.enqueue_workflow_execution(
        execution_id=execution_id or "",
        workflow_config={
            "pool_run_id": str(run.id),
            "pool_run_idempotency_key": run.idempotency_key,
            "execution_consumer": "pools",
            "priority": "normal",
            "idempotency_key": run.idempotency_key or (execution_id or ""),
        },
    )
    run_refresh = PoolRun.objects.get(id=run.id)

    if enqueue_result.success:
        run_refresh.workflow_status = "queued"
        run_refresh.save(update_fields=["workflow_status", "updated_at"])
        run_refresh.add_audit_event(
            event_type="run.workflow_execution_enqueued",
            actor=requested_by,
            status_before=run_refresh.status,
            status_after=run_refresh.status,
            payload={
                "workflow_execution_id": execution_id,
                "operation_id": enqueue_result.operation_id,
                "enqueue_status": enqueue_result.status,
            },
        )
    else:
        run_refresh.add_audit_event(
            event_type="run.workflow_execution_enqueue_failed",
            actor=requested_by,
            status_before=run_refresh.status,
            status_after=run_refresh.status,
            payload={
                "workflow_execution_id": execution_id,
                "enqueue_status": enqueue_result.status,
                "error": enqueue_result.error,
                "error_code": enqueue_result.error_code,
            },
        )

    return PoolWorkflowStartResult(
        run=run_refresh,
        execution_id=execution_id,
        enqueue_success=enqueue_result.success,
        enqueue_status=enqueue_result.status,
        enqueue_error=enqueue_result.error,
        created_execution=created_execution,
    )


def start_pool_run_retry_workflow_execution(
    *,
    run: PoolRun,
    retry_request: dict[str, Any],
    requested_by: User | None = None,
) -> PoolWorkflowRetryStartResult:
    with transaction.atomic():
        locked_run = PoolRun.objects.select_for_update().get(id=run.id)
        if not locked_run.workflow_execution_id:
            raise ValueError("Pool run is not linked to workflow execution.")

        parent_execution = (
            locked_run.workflow_execution_id
            and WorkflowExecution.objects.filter(
                id=locked_run.workflow_execution_id,
                execution_consumer="pools",
            )
            .only("id", "input_context")
            .first()
        )
        if parent_execution is None:
            raise ValueError("Linked workflow execution is unavailable for retry.")

        parent_input_context = (
            parent_execution.input_context if isinstance(parent_execution.input_context, dict) else {}
        )
        root_workflow_run_id = str(
            parent_input_context.get("root_workflow_run_id") or parent_execution.id
        )
        parent_workflow_run_id = str(parent_execution.id)
        next_attempt_number = _parse_context_attempt_number(
            parent_input_context.get("attempt_number")
        ) + 1

        sync_pool_runtime_template_registry()
        schema_template = locked_run.schema_template or _get_or_create_default_schema_template(locked_run)
        plan = compile_pool_execution_plan(
            schema_template=schema_template,
            run_context=PoolWorkflowRunContext(
                pool_id=str(locked_run.pool_id),
                period_start=locked_run.period_start,
                period_end=locked_run.period_end,
                direction=locked_run.direction,
                mode=locked_run.mode,
                run_input=locked_run.run_input if isinstance(locked_run.run_input, dict) else {},
            ),
        )
        workflow_template = _resolve_or_create_workflow_template(plan=plan, requested_by=requested_by)

        retry_input_context = _build_input_context(run=locked_run)
        retry_input_context["retry_request"] = _summarize_retry_request(retry_request)
        retry_input_context["pool_runtime_publication_payload"] = _build_retry_publication_payload(
            retry_request
        )
        execution = workflow_template.create_execution(
            retry_input_context,
            tenant=locked_run.tenant,
            execution_consumer="pools",
        )
        execution.input_context = _with_lineage_metadata(
            input_context=execution.input_context,
            execution_id=str(execution.id),
            root_workflow_run_id=root_workflow_run_id,
            parent_workflow_run_id=parent_workflow_run_id,
            attempt_number=next_attempt_number,
            attempt_kind=ATTEMPT_KIND_RETRY,
        )
        execution.execution_plan = _build_execution_plan_snapshot(
            run=locked_run,
            plan=plan,
            workflow_template=workflow_template,
            execution_context=execution.input_context,
        )
        execution.bindings = _build_execution_bindings(plan=plan)
        execution.save(update_fields=["input_context", "execution_plan", "bindings"])

        locked_run.workflow_execution_id = execution.id
        locked_run.workflow_status = execution.status
        locked_run.execution_backend = "workflow_core"
        locked_run.workflow_template_name = workflow_template.name
        locked_run.save(
            update_fields=[
                "workflow_execution_id",
                "workflow_status",
                "execution_backend",
                "workflow_template_name",
                "updated_at",
            ]
        )
        locked_run.add_audit_event(
            event_type="run.retry_workflow_execution_linked",
            actor=requested_by,
            status_before=locked_run.status,
            status_after=locked_run.status,
            payload={
                "workflow_execution_id": str(execution.id),
                "parent_workflow_run_id": parent_workflow_run_id,
                "root_workflow_run_id": root_workflow_run_id,
                "attempt_number": next_attempt_number,
                "definition_key": plan.plan_key,
            },
        )

    execution_id = str(locked_run.workflow_execution_id)
    enqueue_result = OperationsService.enqueue_workflow_execution(
        execution_id=execution_id,
        workflow_config={
            "pool_run_id": str(run.id),
            "pool_run_idempotency_key": run.idempotency_key,
            "execution_consumer": "pools",
            "priority": "normal",
            "idempotency_key": execution_id,
        },
    )

    run_refresh = PoolRun.objects.get(id=run.id)
    if enqueue_result.success:
        run_refresh.workflow_status = "queued"
        run_refresh.save(update_fields=["workflow_status", "updated_at"])
        run_refresh.add_audit_event(
            event_type="run.retry_workflow_execution_enqueued",
            actor=requested_by,
            status_before=run_refresh.status,
            status_after=run_refresh.status,
            payload={
                "workflow_execution_id": execution_id,
                "operation_id": enqueue_result.operation_id,
                "enqueue_status": enqueue_result.status,
            },
        )
    else:
        run_refresh.add_audit_event(
            event_type="run.retry_workflow_execution_enqueue_failed",
            actor=requested_by,
            status_before=run_refresh.status,
            status_after=run_refresh.status,
            payload={
                "workflow_execution_id": execution_id,
                "enqueue_status": enqueue_result.status,
                "error": enqueue_result.error,
                "error_code": enqueue_result.error_code,
            },
        )

    return PoolWorkflowRetryStartResult(
        run=run_refresh,
        execution_id=execution_id,
        operation_id=enqueue_result.operation_id or None,
        enqueue_success=enqueue_result.success,
        enqueue_status=enqueue_result.status,
        enqueue_error=enqueue_result.error,
    )


def _build_input_context(*, run: PoolRun) -> dict[str, Any]:
    return {
        "pool_run_id": str(run.id),
        "pool_run_idempotency_key": run.idempotency_key,
        "pool_id": str(run.pool_id),
        "tenant_id": str(run.tenant_id),
        "direction": run.direction,
        "mode": run.mode,
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat() if run.period_end else None,
        "run_input": run.run_input if isinstance(run.run_input, dict) else {},
        "approval_required": run.mode == PoolRunMode.SAFE,
        "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
        "approval_state": _resolve_approval_state_for_input_context(run=run),
        "publication_step_state": _resolve_publication_step_state_for_input_context(run=run),
    }


def _with_lineage_metadata(
    *,
    input_context: dict[str, Any] | None,
    execution_id: str,
    root_workflow_run_id: str,
    parent_workflow_run_id: str | None,
    attempt_number: int,
    attempt_kind: str,
) -> dict[str, Any]:
    context = dict(input_context or {})
    context["workflow_run_id"] = execution_id
    context["root_workflow_run_id"] = root_workflow_run_id
    context["parent_workflow_run_id"] = parent_workflow_run_id
    context["attempt_number"] = int(attempt_number)
    context["attempt_kind"] = str(attempt_kind or ATTEMPT_KIND_INITIAL)
    return context


def _parse_context_attempt_number(raw_attempt_number: object) -> int:
    try:
        value = int(raw_attempt_number)
    except (TypeError, ValueError):
        return 1
    if value < 1:
        return 1
    return value


def _summarize_retry_request(retry_request: dict[str, Any]) -> dict[str, Any]:
    payload = retry_request if isinstance(retry_request, dict) else {}
    target_ids = sorted(str(key) for key in (payload.get("documents_by_database") or {}).keys())
    documents_by_database = payload.get("documents_by_database") or {}
    documents_total = 0
    if isinstance(documents_by_database, dict):
        for documents in documents_by_database.values():
            if isinstance(documents, list):
                documents_total += len(documents)
    return {
        "entity_name": str(payload.get("entity_name") or "").strip(),
        "requested_target_ids": target_ids,
        "requested_targets_count": len(target_ids),
        "requested_documents_count": documents_total,
        "max_attempts": payload.get("max_attempts"),
        "retry_interval_seconds": payload.get("retry_interval_seconds"),
        "external_key_field": str(payload.get("external_key_field") or "").strip(),
    }


def _build_retry_publication_payload(retry_request: dict[str, Any]) -> dict[str, Any]:
    payload = retry_request if isinstance(retry_request, dict) else {}
    documents_by_database: dict[str, list[dict[str, Any]]] = {}
    raw_documents_by_database = payload.get("documents_by_database")
    if isinstance(raw_documents_by_database, dict):
        for raw_database_id, raw_documents in raw_documents_by_database.items():
            database_id = str(raw_database_id or "").strip()
            if not database_id or not isinstance(raw_documents, list):
                continue
            normalized_documents = [
                dict(item)
                for item in raw_documents
                if isinstance(item, dict)
            ]
            if normalized_documents:
                documents_by_database[database_id] = normalized_documents
    publication_payload = {
        "entity_name": str(payload.get("entity_name") or "").strip(),
        "documents_by_database": documents_by_database,
        "max_attempts": payload.get("max_attempts"),
        "retry_interval_seconds": payload.get("retry_interval_seconds"),
        "external_key_field": str(payload.get("external_key_field") or "").strip(),
    }
    return {"pool_runtime": publication_payload}


def _resolve_approval_state_for_input_context(*, run: PoolRun) -> str:
    if run.mode == PoolRunMode.UNSAFE:
        return APPROVAL_STATE_NOT_REQUIRED
    if run.publication_confirmed_at is not None:
        return APPROVAL_STATE_APPROVED
    return APPROVAL_STATE_PREPARING


def _resolve_publication_step_state_for_input_context(*, run: PoolRun) -> str:
    if run.mode == PoolRunMode.SAFE and run.publication_confirmed_at is None:
        return PUBLICATION_STEP_STATE_NOT_ENQUEUED
    if run.publishing_started_at is not None:
        return PUBLICATION_STEP_STATE_STARTED
    return PUBLICATION_STEP_STATE_QUEUED


def _build_execution_plan_snapshot(
    *,
    run: PoolRun,
    plan,
    workflow_template: WorkflowTemplate,
    execution_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_input = run.run_input if isinstance(run.run_input, dict) else {}
    execution_lineage = _build_execution_lineage_snapshot(execution_context=execution_context)
    return {
        "kind": "workflow",
        "plan_version": plan.plan_version,
        "workflow_id": str(workflow_template.id),
        "definition": {
            "definition_key": plan.plan_key,
            "workflow_template_id": str(workflow_template.id),
            "workflow_template_name": workflow_template.name,
            "workflow_template_version": int(workflow_template.version_number or 1),
            "template_version": plan.template_version,
        },
        "input_context_masked": {
            "pool_run_id": str(run.id),
            "pool_id": str(run.pool_id),
            "tenant_id": str(run.tenant_id),
            "direction": run.direction,
            "mode": run.mode,
            "period_start": run.period_start.isoformat(),
            "period_end": run.period_end.isoformat() if run.period_end else None,
            "run_input": run_input,
        },
        "execution_snapshot": {
            "pool_run_id": str(run.id),
            "seed": run.seed,
            "period_start": run.period_start.isoformat(),
            "period_end": run.period_end.isoformat() if run.period_end else None,
            "run_input": run_input,
            "lineage": execution_lineage,
        },
        "targets": {
            "entity": "pool_run",
            "pool_id": str(run.pool_id),
            "approval_required": run.mode == PoolRunMode.SAFE,
        },
        "operation_bindings": _build_operation_binding_snapshot(plan=plan),
    }


def _build_execution_lineage_snapshot(
    *,
    execution_context: dict[str, Any] | None,
) -> dict[str, Any]:
    context = execution_context if isinstance(execution_context, dict) else {}
    return {
        "workflow_run_id": str(context.get("workflow_run_id") or ""),
        "root_workflow_run_id": str(context.get("root_workflow_run_id") or ""),
        "parent_workflow_run_id": (
            str(context.get("parent_workflow_run_id"))
            if context.get("parent_workflow_run_id") is not None
            else None
        ),
        "attempt_number": _parse_context_attempt_number(context.get("attempt_number")),
        "attempt_kind": str(context.get("attempt_kind") or ATTEMPT_KIND_INITIAL),
    }


def _build_execution_bindings(*, plan) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    if plan.workflow_binding_hint:
        bindings.append(
            {
                "target_ref": "workflow.binding_hint",
                "source_ref": f"pool_schema_template.metadata.workflow_binding:{plan.workflow_binding_hint}",
                "resolve_at": "api",
                "sensitive": False,
                "status": "applied",
            }
        )
    else:
        bindings.append(
            {
                "target_ref": "workflow.binding_hint",
                "source_ref": "pool_schema_template.metadata.workflow_binding",
                "resolve_at": "api",
                "sensitive": False,
                "status": "skipped",
                "reason": "missing_source",
            }
        )
    for step in getattr(plan, "steps", ()):
        template_exposure_id = str(getattr(step, "template_exposure_id", "") or "").strip()
        template_exposure_revision = getattr(step, "template_exposure_revision", None)
        if not template_exposure_id or template_exposure_revision is None:
            continue
        bindings.append(
            {
                "target_ref": f"workflow.operation_ref.{step.node_id}",
                "source_ref": f"operation_exposure:{template_exposure_id}@{template_exposure_revision}",
                "resolve_at": "compile",
                "sensitive": False,
                "status": "applied",
                "binding_mode": "pinned_exposure",
                "alias": step.operation_alias,
            }
        )
    return bindings


def _build_operation_binding_snapshot(*, plan) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for step in getattr(plan, "steps", ()):
        template_exposure_id = str(getattr(step, "template_exposure_id", "") or "").strip()
        template_exposure_revision = getattr(step, "template_exposure_revision", None)
        if not template_exposure_id or template_exposure_revision is None:
            continue
        snapshot.append(
            {
                "node_id": step.node_id,
                "alias": step.operation_alias,
                "binding_mode": "pinned_exposure",
                "template_exposure_id": template_exposure_id,
                "template_exposure_revision": int(template_exposure_revision),
            }
        )
    return snapshot


def _resolve_or_create_workflow_template(*, plan, requested_by: User | None) -> WorkflowTemplate:
    template = (
        WorkflowTemplate.objects.filter(name=plan.workflow_template_name)
        .order_by("-version_number")
        .first()
    )
    if template is not None:
        return template

    template = plan.build_workflow_template(created_by=requested_by)
    try:
        template.save()
    except IntegrityError:
        existing = (
            WorkflowTemplate.objects.filter(name=plan.workflow_template_name)
            .order_by("-version_number")
            .first()
        )
        if existing is not None:
            return existing
        raise
    return template


def _get_or_create_default_schema_template(run: PoolRun) -> PoolSchemaTemplate:
    template, _ = PoolSchemaTemplate.objects.get_or_create(
        tenant=run.tenant,
        code=_DEFAULT_TEMPLATE_CODE,
        defaults={
            "name": _DEFAULT_TEMPLATE_NAME,
            "format": PoolSchemaTemplateFormat.JSON,
            "is_public": False,
            "is_active": True,
            "schema": {},
            "metadata": {
                "managed_by": "pool_workflow_runtime",
                "created_at": timezone.now().isoformat(),
            },
        },
    )
    return template
