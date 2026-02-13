from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.operations.services import OperationsService
from apps.templates.workflow.models import WorkflowTemplate

from .models import PoolRun, PoolRunMode, PoolSchemaTemplate, PoolSchemaTemplateFormat
from .workflow_compiler import PoolWorkflowRunContext, compile_pool_execution_plan


User = get_user_model()

_DEFAULT_TEMPLATE_CODE = "__runtime-default__"
_DEFAULT_TEMPLATE_NAME = "Pools Runtime Default Template"


@dataclass(frozen=True)
class PoolWorkflowStartResult:
    run: PoolRun
    execution_id: str | None
    enqueue_success: bool
    enqueue_status: str
    enqueue_error: str | None
    created_execution: bool


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

        schema_template = locked_run.schema_template or _get_or_create_default_schema_template(locked_run)
        plan = compile_pool_execution_plan(
            schema_template=schema_template,
            run_context=PoolWorkflowRunContext(
                pool_id=str(locked_run.pool_id),
                period_start=locked_run.period_start,
                period_end=locked_run.period_end,
                direction=locked_run.direction,
                mode=locked_run.mode,
                source_hash=locked_run.source_hash,
            ),
        )
        workflow_template = _resolve_or_create_workflow_template(plan=plan, requested_by=requested_by)
        execution = workflow_template.create_execution(_build_input_context(run=locked_run))
        execution.execution_plan = _build_execution_plan_snapshot(
            run=locked_run,
            plan=plan,
            workflow_template=workflow_template,
        )
        execution.bindings = _build_execution_bindings(plan=plan)
        execution.save(update_fields=["execution_plan", "bindings"])

        save_fields = {
            "updated_at",
            "workflow_execution_id",
            "workflow_status",
            "execution_backend",
            "workflow_template_name",
        }
        locked_run.workflow_execution_id = execution.id
        locked_run.workflow_status = execution.status
        locked_run.execution_backend = "workflow_core"
        locked_run.workflow_template_name = workflow_template.name

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
            save_fields.update(
                {"publication_confirmed_at", "publication_confirmed_by"}
            )

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
                "approval_required": locked_run.mode == PoolRunMode.SAFE,
            },
        )
        execution_id = str(execution.id)
        created_execution = True

    enqueue_result = OperationsService.enqueue_workflow_execution(
        execution_id=execution_id or "",
        workflow_config={
            "pool_run_id": str(run.id),
            "execution_consumer": "pools",
            "priority": "normal",
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


def _build_input_context(*, run: PoolRun) -> dict[str, Any]:
    return {
        "pool_run_id": str(run.id),
        "pool_id": str(run.pool_id),
        "tenant_id": str(run.tenant_id),
        "direction": run.direction,
        "mode": run.mode,
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat() if run.period_end else None,
        "source_hash": run.source_hash,
        "approval_required": run.mode == PoolRunMode.SAFE,
        "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
    }


def _build_execution_plan_snapshot(
    *,
    run: PoolRun,
    plan,
    workflow_template: WorkflowTemplate,
) -> dict[str, Any]:
    return {
        "kind": "workflow",
        "plan_version": plan.plan_version,
        "workflow_id": str(workflow_template.id),
        "input_context_masked": {
            "pool_run_id": str(run.id),
            "pool_id": str(run.pool_id),
            "tenant_id": str(run.tenant_id),
            "direction": run.direction,
            "mode": run.mode,
            "period_start": run.period_start.isoformat(),
            "period_end": run.period_end.isoformat() if run.period_end else None,
            "source_hash": run.source_hash,
        },
        "targets": {
            "entity": "pool_run",
            "pool_id": str(run.pool_id),
            "approval_required": run.mode == PoolRunMode.SAFE,
        },
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
    return bindings


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
