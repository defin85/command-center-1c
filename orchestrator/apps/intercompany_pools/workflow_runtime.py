from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.operations.services import OperationsService
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate

from .document_plan_artifact_contract import (
    POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY,
    POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY,
    POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY,
    build_publication_payload_from_document_plan_artifact,
    compile_document_plan_artifact_v1,
    validate_document_plan_artifact_v1,
)
from .binding_preview import build_pool_workflow_binding_runtime_bundle
from .distribution_artifact_contract import validate_distribution_artifact_v1
from .master_data_artifact_contract import (
    POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY,
    build_master_data_binding_artifact_ref,
    build_master_data_snapshot_ref,
    validate_master_data_binding_artifact_v1,
)
from .models import PoolRun, PoolRunMode, PoolSchemaTemplate, PoolSchemaTemplateFormat
from .models import PoolPublicationAttempt, PoolPublicationAttemptStatus
from .publication_auth_mapping import (
    PUBLICATION_AUTH_STRATEGY_ACTOR,
    PUBLICATION_AUTH_STRATEGY_SERVICE,
    build_publication_auth_fail_closed_error,
    evaluate_publication_auth_coverage,
)
from .runtime_projection_contract import (
    POOL_RUNTIME_PROJECTION_CONTEXT_KEY,
    build_pool_runtime_projection_v1,
    validate_pool_runtime_projection_v1,
)
from .runtime_template_registry import sync_pool_runtime_template_registry
from .runtime_distribution import compute_distribution_runtime_state, load_runtime_topology_for_period
from .run_input_sanitizer import sanitize_run_input_for_runtime_contract
from .workflow_authoring_contract import PoolWorkflowBindingContract
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

PUBLICATION_AUTH_SOURCE_RUN_CREATE = "run_create"
PUBLICATION_AUTH_SOURCE_CONFIRM_PUBLICATION = "confirm_publication"
PUBLICATION_AUTH_SOURCE_RETRY_PUBLICATION = "retry_publication"
POOL_RUNTIME_RETRY_PAYLOAD_INVALID = "POOL_RUNTIME_RETRY_PAYLOAD_INVALID"
POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY = "pool_workflow_binding"
POOL_RUNTIME_DECISIONS_CONTEXT_KEY = "decisions"
POOL_WORKFLOW_BINDING_REQUIRED = "POOL_WORKFLOW_BINDING_REQUIRED"


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
    workflow_binding: dict[str, Any] | None = None,
) -> PoolWorkflowStartResult:
    execution_id: str | None = None
    created_execution = False
    normalized_workflow_binding = _normalize_runtime_workflow_binding(workflow_binding)
    if normalized_workflow_binding is None:
        raise ValueError(
            f"{POOL_WORKFLOW_BINDING_REQUIRED}: pool_workflow_binding_id is required for workflow runtime start"
        )

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

        _validate_publication_auth_mapping_for_run(run=locked_run, requested_by=requested_by)

        sync_pool_runtime_template_registry()
        schema_template = locked_run.schema_template or _get_or_create_default_schema_template(locked_run)
        bundle = build_pool_workflow_binding_runtime_bundle(
            tenant=locked_run.tenant,
            pool=locked_run.pool,
            pool_workflow_binding_id=str(normalized_workflow_binding["binding_id"]),
            workflow_binding=normalized_workflow_binding,
            direction=locked_run.direction,
            mode=locked_run.mode,
            period_start=locked_run.period_start,
            period_end=locked_run.period_end,
            run_input=locked_run.run_input,
            schema_template=schema_template,
            run=locked_run,
        )
        sanitized_run_input = bundle["run_input"]
        document_plan_artifact = bundle["document_plan_artifact"]
        decision_outputs = bundle["decision_outputs"]
        master_data_snapshot_ref = build_master_data_snapshot_ref(
            run=locked_run,
            run_input=sanitized_run_input,
        )
        master_data_binding_artifact_ref = build_master_data_binding_artifact_ref(
            run=locked_run,
            snapshot_ref=master_data_snapshot_ref,
            document_plan_artifact=document_plan_artifact,
        )
        plan = bundle["plan"]
        runtime_projection = bundle["runtime_projection"]
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
            _build_input_context(
                run=locked_run,
                requested_by=requested_by,
                publication_auth_source=PUBLICATION_AUTH_SOURCE_RUN_CREATE,
                master_data_snapshot_ref=master_data_snapshot_ref,
                master_data_binding_artifact_ref=master_data_binding_artifact_ref,
                runtime_projection=runtime_projection,
                workflow_binding=normalized_workflow_binding,
                decision_outputs=decision_outputs,
                compiled_document_policy=bundle["compiled_document_policy"],
                document_policy_source=bundle["document_policy_source"],
                document_plan_artifact=document_plan_artifact,
            ),
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
        locked_run.workflow_binding_snapshot = normalized_workflow_binding
        locked_run.runtime_projection_snapshot = runtime_projection
        save_fields.update({"workflow_binding_snapshot", "runtime_projection_snapshot"})

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

        _validate_publication_auth_mapping_for_run(run=locked_run, requested_by=requested_by)

        parent_input_context = (
            parent_execution.input_context if isinstance(parent_execution.input_context, dict) else {}
        )
        retry_workflow_binding = _resolve_retry_workflow_binding(parent_input_context)
        if retry_workflow_binding is None:
            raise ValueError(
                f"{POOL_WORKFLOW_BINDING_REQUIRED}: retry requires persisted pool workflow binding snapshot"
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
        sanitized_run_input = sanitize_run_input_for_runtime_contract(run_input=locked_run.run_input)
        retry_publication_payload = _build_retry_publication_payload(
            run=locked_run,
            retry_request=retry_request,
            parent_input_context=parent_input_context,
        )
        document_plan_artifact = _build_retry_compile_document_plan_artifact(
            parent_input_context=parent_input_context,
            retry_publication_payload=retry_publication_payload,
        )
        if document_plan_artifact is None:
            retry_bundle = build_pool_workflow_binding_runtime_bundle(
                tenant=locked_run.tenant,
                pool=locked_run.pool,
                pool_workflow_binding_id=str(retry_workflow_binding["binding_id"]),
                workflow_binding=retry_workflow_binding,
                direction=locked_run.direction,
                mode=locked_run.mode,
                period_start=locked_run.period_start,
                period_end=locked_run.period_end,
                run_input=locked_run.run_input,
                schema_template=schema_template,
                run=locked_run,
            )
            sanitized_run_input = retry_bundle["run_input"]
            document_plan_artifact = retry_bundle["document_plan_artifact"]
            plan = retry_bundle["plan"]
            runtime_projection = retry_bundle["runtime_projection"]
            decision_outputs = retry_bundle["decision_outputs"]
            compiled_document_policy = retry_bundle["compiled_document_policy"]
            document_policy_source = retry_bundle["document_policy_source"]
        else:
            compiled_document_policy = _resolve_retry_compiled_document_policy(parent_input_context)
            document_policy_source = _resolve_retry_document_policy_source(parent_input_context)
            plan = compile_pool_execution_plan(
                schema_template=schema_template,
                run_context=PoolWorkflowRunContext(
                    pool_id=str(locked_run.pool_id),
                    period_start=locked_run.period_start,
                    period_end=locked_run.period_end,
                    direction=locked_run.direction,
                    mode=locked_run.mode,
                    run_input=sanitized_run_input,
                    document_plan_artifact=document_plan_artifact,
                    workflow_binding=retry_workflow_binding,
                ),
            )
            runtime_projection = build_pool_runtime_projection_v1(
                run=locked_run,
                plan=plan,
                document_plan_artifact=document_plan_artifact,
                compiled_document_policy=compiled_document_policy,
            )
            decision_outputs = _resolve_retry_decision_outputs(parent_input_context)
        master_data_snapshot_ref = _resolve_retry_master_data_snapshot_ref(
            run=locked_run,
            run_input=sanitized_run_input,
            parent_input_context=parent_input_context,
        )
        master_data_binding_artifact_ref = _resolve_retry_master_data_binding_artifact_ref(
            run=locked_run,
            parent_input_context=parent_input_context,
            master_data_snapshot_ref=master_data_snapshot_ref,
            document_plan_artifact=document_plan_artifact,
        )
        workflow_template = _resolve_or_create_workflow_template(plan=plan, requested_by=requested_by)

        retry_input_context = _build_input_context(
            run=locked_run,
            requested_by=requested_by,
            publication_auth_source=PUBLICATION_AUTH_SOURCE_RETRY_PUBLICATION,
            fallback_publication_auth=parent_input_context.get("publication_auth"),
            master_data_snapshot_ref=master_data_snapshot_ref,
            master_data_binding_artifact_ref=master_data_binding_artifact_ref,
            runtime_projection=runtime_projection,
            workflow_binding=retry_workflow_binding,
            decision_outputs=decision_outputs,
            compiled_document_policy=compiled_document_policy,
            document_policy_source=document_policy_source,
            document_plan_artifact=document_plan_artifact,
        )
        persisted_binding_artifact = parent_input_context.get(
            POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY
        )
        if isinstance(persisted_binding_artifact, dict):
            try:
                retry_input_context[
                    POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY
                ] = validate_master_data_binding_artifact_v1(
                    artifact=persisted_binding_artifact
                )
            except ValueError:
                pass
        retry_input_context["retry_request"] = _summarize_retry_request(retry_request)
        retry_input_context["pool_runtime_publication_payload"] = retry_publication_payload
        retry_input_context["pool_runtime_retry_settings"] = {
            "use_retry_subset_payload": bool(retry_request.get("use_retry_subset_payload")),
        }
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
        locked_run.workflow_binding_snapshot = retry_workflow_binding
        locked_run.runtime_projection_snapshot = runtime_projection
        locked_run.save(
            update_fields=[
                "workflow_execution_id",
                "workflow_status",
                "execution_backend",
                "workflow_template_name",
                "workflow_binding_snapshot",
                "runtime_projection_snapshot",
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


def _build_input_context(
    *,
    run: PoolRun,
    requested_by: User | None = None,
    publication_auth_source: str = PUBLICATION_AUTH_SOURCE_RUN_CREATE,
    fallback_publication_auth: object | None = None,
    master_data_snapshot_ref: str = "",
    master_data_binding_artifact_ref: str = "",
    runtime_projection: dict[str, Any] | None = None,
    workflow_binding: dict[str, Any] | None = None,
    decision_outputs: Mapping[str, Any] | None = None,
    compiled_document_policy: Mapping[str, Any] | None = None,
    document_policy_source: str | None = None,
    document_plan_artifact: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    run_input = sanitize_run_input_for_runtime_contract(run_input=run.run_input)
    context = {
        "pool_run_id": str(run.id),
        "pool_run_idempotency_key": run.idempotency_key,
        "pool_id": str(run.pool_id),
        "tenant_id": str(run.tenant_id),
        "direction": run.direction,
        "mode": run.mode,
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat() if run.period_end else None,
        "run_input": run_input,
        "approval_required": run.mode == PoolRunMode.SAFE,
        "approved_at": run.publication_confirmed_at.isoformat() if run.publication_confirmed_at else None,
        "approval_state": _resolve_approval_state_for_input_context(run=run),
        "publication_step_state": _resolve_publication_step_state_for_input_context(run=run),
        "publication_auth": _build_publication_auth_context(
            requested_by=requested_by,
            source=publication_auth_source,
            fallback=fallback_publication_auth,
        ),
        "master_data_snapshot_ref": str(master_data_snapshot_ref or "").strip(),
        "master_data_binding_artifact_ref": str(master_data_binding_artifact_ref or "").strip(),
    }
    if isinstance(runtime_projection, dict):
        context[POOL_RUNTIME_PROJECTION_CONTEXT_KEY] = validate_pool_runtime_projection_v1(
            projection=runtime_projection
        )
    normalized_workflow_binding = _normalize_runtime_workflow_binding(workflow_binding)
    if normalized_workflow_binding is not None:
        context[POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY] = normalized_workflow_binding
    normalized_decision_outputs = _normalize_decision_outputs(decision_outputs)
    if normalized_decision_outputs:
        context[POOL_RUNTIME_DECISIONS_CONTEXT_KEY] = normalized_decision_outputs
    if isinstance(compiled_document_policy, Mapping):
        context[POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY] = dict(compiled_document_policy)
    normalized_document_policy_source = str(document_policy_source or "").strip()
    if normalized_document_policy_source:
        context[POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY] = normalized_document_policy_source
    if isinstance(document_plan_artifact, Mapping):
        context[POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY] = validate_document_plan_artifact_v1(
            artifact=document_plan_artifact
        )
    return context


def _normalize_runtime_workflow_binding(
    workflow_binding: object | None,
) -> dict[str, Any] | None:
    if not isinstance(workflow_binding, dict) or not workflow_binding:
        return None
    binding = PoolWorkflowBindingContract(**workflow_binding)
    return binding.model_dump(mode="json")


def _resolve_retry_workflow_binding(
    parent_input_context: dict[str, Any],
) -> dict[str, Any] | None:
    return _normalize_runtime_workflow_binding(
        parent_input_context.get(POOL_RUNTIME_WORKFLOW_BINDING_CONTEXT_KEY)
    )


def _normalize_decision_outputs(
    decision_outputs: object | None,
) -> dict[str, Any]:
    if not isinstance(decision_outputs, Mapping):
        return {}
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in dict(decision_outputs).items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        normalized[key] = raw_value
    return normalized


def _resolve_retry_decision_outputs(
    parent_input_context: dict[str, Any],
) -> dict[str, Any]:
    return _normalize_decision_outputs(
        parent_input_context.get(POOL_RUNTIME_DECISIONS_CONTEXT_KEY)
    )


def _resolve_retry_compiled_document_policy(
    parent_input_context: dict[str, Any],
) -> dict[str, Any] | None:
    raw_policy = parent_input_context.get(POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY)
    if not isinstance(raw_policy, Mapping):
        return None
    return dict(raw_policy)


def _resolve_retry_document_policy_source(
    parent_input_context: dict[str, Any],
) -> str | None:
    source = str(parent_input_context.get(POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY) or "").strip()
    return source or None


def _build_publication_auth_context(
    *,
    requested_by: User | None,
    source: str,
    fallback: object | None = None,
) -> dict[str, str]:
    fallback_context = _normalize_publication_auth_context(fallback)
    actor_username = _resolve_actor_username(requested_by=requested_by)
    if actor_username:
        strategy = PUBLICATION_AUTH_STRATEGY_ACTOR
    elif fallback_context is not None:
        strategy = fallback_context["strategy"]
        if strategy == PUBLICATION_AUTH_STRATEGY_ACTOR:
            actor_username = fallback_context["actor_username"]
    else:
        strategy = PUBLICATION_AUTH_STRATEGY_SERVICE

    normalized_source = str(source or "").strip()
    if not normalized_source and fallback_context is not None:
        normalized_source = fallback_context["source"]
    if not normalized_source:
        normalized_source = PUBLICATION_AUTH_SOURCE_RUN_CREATE

    return {
        "strategy": strategy,
        "actor_username": actor_username if strategy == PUBLICATION_AUTH_STRATEGY_ACTOR else "",
        "source": normalized_source,
    }


def _normalize_publication_auth_context(raw: object | None) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    strategy = str(raw.get("strategy") or "").strip().lower()
    if strategy not in {
        PUBLICATION_AUTH_STRATEGY_ACTOR,
        PUBLICATION_AUTH_STRATEGY_SERVICE,
    }:
        return None
    actor_username = str(raw.get("actor_username") or "").strip()
    if strategy == PUBLICATION_AUTH_STRATEGY_ACTOR and not actor_username:
        return None
    source = str(raw.get("source") or "").strip()
    return {
        "strategy": strategy,
        "actor_username": actor_username if strategy == PUBLICATION_AUTH_STRATEGY_ACTOR else "",
        "source": source,
    }


def _resolve_actor_username(*, requested_by: User | None) -> str:
    if requested_by is None:
        return ""
    return str(getattr(requested_by, "username", "") or "").strip()


def _validate_publication_auth_mapping_for_run(
    *,
    run: PoolRun,
    requested_by: User | None,
) -> None:
    actor_username = _resolve_actor_username(requested_by=requested_by)
    strategy = (
        PUBLICATION_AUTH_STRATEGY_ACTOR
        if actor_username
        else PUBLICATION_AUTH_STRATEGY_SERVICE
    )
    coverage = evaluate_publication_auth_coverage(
        pool=run.pool,
        target_date=run.period_start,
        strategy=strategy,
        actor_username=actor_username,
    )
    if not coverage.has_gaps:
        return
    error_code, detail = build_publication_auth_fail_closed_error(coverage)
    if not error_code:
        return
    raise ValueError(f"{error_code}: {detail}")


def _build_atomic_compile_document_plan_artifact(
    *,
    run: PoolRun,
    run_input: dict[str, Any],
    compiled_document_policy: Mapping[str, Any] | None = None,
    document_policy_source: str | None = None,
) -> dict[str, Any] | None:
    try:
        distribution_state = compute_distribution_runtime_state(
            run=run,
            run_input=run_input,
        )
        distribution_artifact = validate_distribution_artifact_v1(
            artifact=distribution_state.get("artifact"),
        )
        topology = load_runtime_topology_for_period(run=run)
        return compile_document_plan_artifact_v1(
            run=run,
            distribution_artifact=distribution_artifact,
            topology=topology,
            compiled_document_policy=compiled_document_policy,
            document_policy_source=document_policy_source,
        )
    except Exception:
        return None


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
    target_ids = _extract_retry_target_ids(payload)
    documents_by_database = payload.get("documents_by_database") or {}
    documents_total = 0
    if isinstance(documents_by_database, dict):
        for documents in documents_by_database.values():
            if isinstance(documents, list):
                documents_total += len(documents)
    return {
        "entity_name": str(payload.get("entity_name") or "").strip(),
        "requested_target_ids": target_ids,
        "target_database_ids": target_ids,
        "requested_targets_count": len(target_ids),
        "requested_documents_count": documents_total,
        "use_retry_subset_payload": bool(payload.get("use_retry_subset_payload")),
        "max_attempts": payload.get("max_attempts"),
        "retry_interval_seconds": payload.get("retry_interval_seconds"),
        "external_key_field": str(payload.get("external_key_field") or "").strip(),
    }


def _build_retry_publication_payload(
    *,
    run: PoolRun,
    retry_request: dict[str, Any],
    parent_input_context: dict[str, Any],
) -> dict[str, Any]:
    payload = retry_request if isinstance(retry_request, dict) else {}
    target_database_ids = _extract_retry_target_ids(payload)
    document_plan_artifact = _resolve_retry_document_plan_artifact(parent_input_context)
    if document_plan_artifact is not None:
        compiled_payload = build_publication_payload_from_document_plan_artifact(
            artifact=document_plan_artifact,
            run_input=payload,
        )
        return _filter_retry_publication_payload_from_artifact(
            run=run,
            publication_payload=compiled_payload,
            target_database_ids=target_database_ids,
        )

    return _build_retry_publication_payload_from_request(
        payload=payload,
        target_database_ids=target_database_ids,
    )


def _build_retry_compile_document_plan_artifact(
    *,
    parent_input_context: dict[str, Any],
    retry_publication_payload: dict[str, Any],
) -> dict[str, Any] | None:
    artifact = _resolve_retry_document_plan_artifact(parent_input_context)
    if artifact is None:
        return None

    pool_runtime_payload = retry_publication_payload.get("pool_runtime")
    if not isinstance(pool_runtime_payload, dict):
        return None
    chains_by_database_raw = pool_runtime_payload.get("document_chains_by_database")
    if not isinstance(chains_by_database_raw, dict):
        return None

    targets_raw = artifact.get("targets")
    if not isinstance(targets_raw, list):
        return None

    filtered_targets: list[dict[str, Any]] = []
    filtered_chains_count = 0
    filtered_documents_count = 0

    for target_raw in targets_raw:
        if not isinstance(target_raw, dict):
            continue
        target = dict(target_raw)
        database_id = str(target.get("database_id") or "").strip()
        if not database_id:
            continue
        chains_raw = chains_by_database_raw.get(database_id)
        if not isinstance(chains_raw, list):
            continue

        filtered_chains: list[dict[str, Any]] = []
        for chain_raw in chains_raw:
            if not isinstance(chain_raw, dict):
                continue
            chain = dict(chain_raw)
            documents_raw = chain.get("documents")
            if not isinstance(documents_raw, list):
                continue
            documents = [
                dict(document_raw)
                for document_raw in documents_raw
                if isinstance(document_raw, dict)
            ]
            if not documents:
                continue
            chain["documents"] = documents
            filtered_chains.append(chain)
            filtered_documents_count += len(documents)

        if not filtered_chains:
            continue
        target["chains"] = filtered_chains
        filtered_targets.append(target)
        filtered_chains_count += len(filtered_chains)

    if not filtered_targets:
        return None

    retry_artifact = dict(artifact)
    retry_artifact["targets"] = filtered_targets
    compile_summary_raw = retry_artifact.get("compile_summary")
    compile_summary = (
        dict(compile_summary_raw)
        if isinstance(compile_summary_raw, dict)
        else {}
    )
    compile_summary["targets_count"] = len(filtered_targets)
    compile_summary["chains_count"] = filtered_chains_count
    compile_summary["documents_count"] = filtered_documents_count
    retry_artifact["compile_summary"] = compile_summary
    return validate_document_plan_artifact_v1(artifact=retry_artifact)


def _build_retry_publication_payload_from_request(
    *,
    payload: dict[str, Any],
    target_database_ids: list[str],
) -> dict[str, Any]:
    target_database_set = set(target_database_ids)
    documents_by_database: dict[str, list[dict[str, Any]]] = {}
    raw_documents_by_database = payload.get("documents_by_database")
    if isinstance(raw_documents_by_database, dict):
        for raw_database_id, raw_documents in raw_documents_by_database.items():
            database_id = str(raw_database_id or "").strip()
            if not database_id or not isinstance(raw_documents, list):
                continue
            if target_database_set and database_id not in target_database_set:
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


def _extract_retry_target_ids(payload: dict[str, Any]) -> list[str]:
    target_ids_raw = payload.get("target_database_ids")
    if isinstance(target_ids_raw, list):
        seen: set[str] = set()
        target_ids: list[str] = []
        for raw_target_id in target_ids_raw:
            target_id = str(raw_target_id or "").strip()
            if not target_id or target_id in seen:
                continue
            seen.add(target_id)
            target_ids.append(target_id)
        if target_ids:
            return sorted(target_ids)

    raw_documents_by_database = payload.get("documents_by_database")
    if isinstance(raw_documents_by_database, dict):
        return sorted(
            {
                str(raw_database_id or "").strip()
                for raw_database_id in raw_documents_by_database.keys()
                if str(raw_database_id or "").strip()
            }
        )
    return []


def _resolve_retry_document_plan_artifact(
    parent_input_context: dict[str, Any],
) -> dict[str, Any] | None:
    artifact_raw = parent_input_context.get(POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY)
    if artifact_raw is None:
        return None
    try:
        return validate_document_plan_artifact_v1(artifact=artifact_raw)
    except ValueError as exc:
        raise ValueError(
            f"{POOL_RUNTIME_RETRY_PAYLOAD_INVALID}: "
            f"persisted document_plan_artifact is invalid: {exc}"
        ) from exc


def _filter_retry_publication_payload_from_artifact(
    *,
    run: PoolRun,
    publication_payload: dict[str, Any],
    target_database_ids: list[str],
) -> dict[str, Any]:
    pool_runtime_raw = publication_payload.get("pool_runtime")
    if not isinstance(pool_runtime_raw, dict):
        raise ValueError(
            f"{POOL_RUNTIME_RETRY_PAYLOAD_INVALID}: "
            "artifact-based retry payload must contain pool_runtime object"
        )
    pool_runtime = dict(pool_runtime_raw)
    target_database_set = set(target_database_ids)

    raw_chains_by_database = pool_runtime.get("document_chains_by_database")
    chains_by_database_input = (
        dict(raw_chains_by_database)
        if isinstance(raw_chains_by_database, dict)
        else {}
    )
    raw_documents_by_database = pool_runtime.get("documents_by_database")
    documents_by_database_input = (
        dict(raw_documents_by_database)
        if isinstance(raw_documents_by_database, dict)
        else {}
    )

    failed_document_keys_by_database = _collect_failed_document_keys_for_retry(
        run=run,
        target_database_ids=target_database_ids,
    )
    successful_document_refs_by_database = _collect_successful_document_refs_for_retry(
        run=run,
        target_database_ids=target_database_ids,
    )

    filtered_chains_by_database: dict[str, list[dict[str, Any]]] = {}
    for database_id, chains_raw in chains_by_database_input.items():
        normalized_database_id = str(database_id or "").strip()
        if not normalized_database_id:
            continue
        if target_database_set and normalized_database_id not in target_database_set:
            continue
        if not isinstance(chains_raw, list):
            continue
        failed_document_keys = failed_document_keys_by_database.get(normalized_database_id)
        filtered_chains = _filter_retry_chains_by_document_keys(
            chains_raw=chains_raw,
            failed_document_keys=failed_document_keys,
            successful_document_refs=successful_document_refs_by_database.get(normalized_database_id),
        )
        if filtered_chains:
            filtered_chains_by_database[normalized_database_id] = filtered_chains

    filtered_documents_by_database = _build_legacy_documents_by_database_from_chains(
        chains_by_database=filtered_chains_by_database
    )
    if not filtered_documents_by_database:
        for database_id, documents_raw in documents_by_database_input.items():
            normalized_database_id = str(database_id or "").strip()
            if not normalized_database_id:
                continue
            if target_database_set and normalized_database_id not in target_database_set:
                continue
            if not isinstance(documents_raw, list):
                continue
            normalized_documents = [
                dict(item)
                for item in documents_raw
                if isinstance(item, dict)
            ]
            if normalized_documents:
                filtered_documents_by_database[normalized_database_id] = normalized_documents

    if target_database_set and not filtered_documents_by_database and not filtered_chains_by_database:
        raise ValueError(
            f"{POOL_RUNTIME_RETRY_PAYLOAD_INVALID}: "
            "no retry targets available after applying target_database_ids filter"
        )

    pool_runtime["documents_by_database"] = filtered_documents_by_database
    pool_runtime["document_chains_by_database"] = filtered_chains_by_database
    return {"pool_runtime": pool_runtime}


def _collect_failed_document_keys_for_retry(
    *,
    run: PoolRun,
    target_database_ids: list[str],
) -> dict[str, set[str]]:
    if not target_database_ids:
        return {}

    attempt_rows = (
        PoolPublicationAttempt.objects.filter(
            run=run,
            target_database_id__in=target_database_ids,
        )
        .order_by("target_database_id", "attempt_number", "created_at")
        .only("target_database_id", "status", "request_summary", "response_summary")
    )
    successful_keys_by_database: dict[str, set[str]] = defaultdict(set)
    latest_request_keys_by_database: dict[str, list[str]] = {}

    for attempt in attempt_rows:
        database_id = str(attempt.target_database_id)
        request_summary = (
            attempt.request_summary if isinstance(attempt.request_summary, dict) else {}
        )
        response_summary = (
            attempt.response_summary if isinstance(attempt.response_summary, dict) else {}
        )

        request_keys = _normalize_document_keys(
            request_summary.get("document_idempotency_keys")
        )
        if request_keys:
            latest_request_keys_by_database[database_id] = request_keys

        successful_keys = _normalize_document_keys(
            response_summary.get("successful_document_idempotency_keys")
        )
        if (
            not successful_keys
            and attempt.status == PoolPublicationAttemptStatus.SUCCESS
            and request_keys
        ):
            successful_keys = request_keys
        successful_keys_by_database[database_id].update(successful_keys)

    failed_keys_by_database: dict[str, set[str]] = {}
    for database_id in target_database_ids:
        latest_request_keys = latest_request_keys_by_database.get(database_id)
        if not latest_request_keys:
            continue
        successful_keys = successful_keys_by_database.get(database_id, set())
        failed_keys = {
            key
            for key in latest_request_keys
            if key not in successful_keys
        }
        failed_keys_by_database[database_id] = failed_keys
    return failed_keys_by_database


def _collect_successful_document_refs_for_retry(
    *,
    run: PoolRun,
    target_database_ids: list[str],
) -> dict[str, dict[str, str]]:
    if not target_database_ids:
        return {}

    attempt_rows = (
        PoolPublicationAttempt.objects.filter(
            run=run,
            target_database_id__in=target_database_ids,
        )
        .order_by("target_database_id", "attempt_number", "created_at")
        .only("target_database_id", "response_summary")
    )
    refs_by_database: dict[str, dict[str, str]] = defaultdict(dict)
    for attempt in attempt_rows:
        database_id = str(attempt.target_database_id)
        response_summary = (
            attempt.response_summary if isinstance(attempt.response_summary, dict) else {}
        )
        successful_refs = response_summary.get("successful_document_refs")
        if not isinstance(successful_refs, dict):
            continue
        normalized_refs = refs_by_database[database_id]
        for raw_key, raw_ref in successful_refs.items():
            document_key = str(raw_key or "").strip()
            document_ref = str(raw_ref or "").strip()
            if not document_key or not document_ref:
                continue
            normalized_refs[document_key] = document_ref
    return {
        database_id: dict(refs)
        for database_id, refs in refs_by_database.items()
        if refs
    }


def _normalize_document_keys(raw_keys: object) -> list[str]:
    if not isinstance(raw_keys, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_key in raw_keys:
        key = str(raw_key or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


def _filter_retry_chains_by_document_keys(
    *,
    chains_raw: list[Any],
    failed_document_keys: set[str] | None,
    successful_document_refs: dict[str, str] | None,
) -> list[dict[str, Any]]:
    filtered_chains: list[dict[str, Any]] = []
    for chain_raw in chains_raw:
        if not isinstance(chain_raw, dict):
            continue
        chain = dict(chain_raw)
        documents_raw = chain.get("documents")
        if not isinstance(documents_raw, list):
            continue

        document_idempotency_by_id: dict[str, str] = {}
        included_document_ids: set[str] = set()
        for document_raw in documents_raw:
            if not isinstance(document_raw, dict):
                continue
            document_id = str(document_raw.get("document_id") or "").strip()
            document_key = str(document_raw.get("idempotency_key") or "").strip()
            if document_id and document_key:
                document_idempotency_by_id[document_id] = document_key
            if _is_document_selected_for_retry(
                document=document_raw,
                failed_document_keys=failed_document_keys,
            ) and document_id:
                included_document_ids.add(document_id)

        filtered_documents: list[dict[str, Any]] = []
        for document_raw in documents_raw:
            if not isinstance(document_raw, dict):
                continue
            if not _is_document_selected_for_retry(
                document=document_raw,
                failed_document_keys=failed_document_keys,
            ):
                continue
            document = dict(document_raw)

            resolved_link_refs = (
                dict(document.get("resolved_link_refs"))
                if isinstance(document.get("resolved_link_refs"), dict)
                else {}
            )
            for dependency_document_id in _extract_document_ref_dependencies(document=document):
                if dependency_document_id in included_document_ids:
                    continue
                dependency_document_key = document_idempotency_by_id.get(dependency_document_id)
                if not dependency_document_key:
                    continue
                if not isinstance(successful_document_refs, dict):
                    continue
                dependency_document_ref = str(
                    successful_document_refs.get(dependency_document_key) or ""
                ).strip()
                if dependency_document_ref:
                    resolved_link_refs[dependency_document_id] = dependency_document_ref
            if resolved_link_refs:
                document["resolved_link_refs"] = resolved_link_refs

            filtered_documents.append(document)

        if not filtered_documents:
            continue
        chain["documents"] = filtered_documents
        filtered_chains.append(chain)
    return filtered_chains


def _is_document_selected_for_retry(
    *,
    document: dict[str, Any],
    failed_document_keys: set[str] | None,
) -> bool:
    if not failed_document_keys:
        return True
    document_key = str(document.get("idempotency_key") or "").strip()
    if not document_key:
        return True
    return document_key in failed_document_keys


def _extract_document_ref_dependencies(*, document: dict[str, Any]) -> set[str]:
    dependencies: set[str] = set()
    link_to = str(document.get("link_to") or "").strip()
    if link_to:
        dependencies.add(link_to)

    link_rules = document.get("link_rules")
    if isinstance(link_rules, dict):
        depends_on = str(link_rules.get("depends_on") or "").strip()
        if depends_on:
            dependencies.add(depends_on)

    _collect_document_ref_dependencies(document.get("field_mapping"), dependencies)
    _collect_document_ref_dependencies(document.get("table_parts_mapping"), dependencies)
    return dependencies


def _collect_document_ref_dependencies(value: object, dependencies: set[str]) -> None:
    if isinstance(value, str):
        token = value.strip()
        if token.endswith(".ref"):
            document_id = token.removesuffix(".ref").strip()
            if document_id:
                dependencies.add(document_id)
        return
    if isinstance(value, dict):
        for nested_value in value.values():
            _collect_document_ref_dependencies(nested_value, dependencies)
        return
    if isinstance(value, list):
        for nested_value in value:
            _collect_document_ref_dependencies(nested_value, dependencies)


def _build_legacy_documents_by_database_from_chains(
    *,
    chains_by_database: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    documents_by_database: dict[str, list[dict[str, Any]]] = {}
    for database_id, chains in chains_by_database.items():
        if not isinstance(chains, list):
            continue
        documents: list[dict[str, Any]] = []
        for chain in chains:
            if not isinstance(chain, dict):
                continue
            allocation = chain.get("allocation")
            allocation_payload = allocation if isinstance(allocation, dict) else {}
            amount = str(allocation_payload.get("amount") or "").strip()
            if not amount:
                continue
            documents.append({"Amount": amount})
        if documents:
            documents_by_database[database_id] = documents
    return documents_by_database


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
    run_input = sanitize_run_input_for_runtime_contract(run_input=run.run_input)
    execution_lineage = _build_execution_lineage_snapshot(execution_context=execution_context)
    publication_auth = _normalize_publication_auth_context(
        (execution_context or {}).get("publication_auth")
        if isinstance(execution_context, dict)
        else None
    )
    master_data_snapshot_ref = (
        str((execution_context or {}).get("master_data_snapshot_ref") or "")
        if isinstance(execution_context, dict)
        else ""
    )
    master_data_binding_artifact_ref = (
        str((execution_context or {}).get("master_data_binding_artifact_ref") or "")
        if isinstance(execution_context, dict)
        else ""
    )
    runtime_projection = (
        validate_pool_runtime_projection_v1(
            projection=(execution_context or {}).get(POOL_RUNTIME_PROJECTION_CONTEXT_KEY)
        )
        if isinstance((execution_context or {}).get(POOL_RUNTIME_PROJECTION_CONTEXT_KEY), dict)
        else None
    )
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
            "publication_auth": publication_auth,
            "master_data_snapshot_ref": master_data_snapshot_ref,
            "master_data_binding_artifact_ref": master_data_binding_artifact_ref,
            POOL_RUNTIME_PROJECTION_CONTEXT_KEY: runtime_projection,
        },
        "execution_snapshot": {
            "pool_run_id": str(run.id),
            "seed": run.seed,
            "period_start": run.period_start.isoformat(),
            "period_end": run.period_end.isoformat() if run.period_end else None,
            "run_input": run_input,
            "publication_auth": publication_auth,
            "master_data_snapshot_ref": master_data_snapshot_ref,
            "master_data_binding_artifact_ref": master_data_binding_artifact_ref,
            POOL_RUNTIME_PROJECTION_CONTEXT_KEY: runtime_projection,
            "lineage": execution_lineage,
        },
        "targets": {
            "entity": "pool_run",
            "pool_id": str(run.pool_id),
            "approval_required": run.mode == PoolRunMode.SAFE,
        },
        "runtime_projection": runtime_projection,
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
    if isinstance(getattr(plan, "workflow_binding_snapshot", None), dict):
        workflow_binding_snapshot = dict(plan.workflow_binding_snapshot)
        binding_mode = str(workflow_binding_snapshot.get("binding_mode") or "").strip()
        bindings.append(
            {
                "target_ref": "workflow.binding",
                "source_ref": (
                    f"pool_workflow_binding:{workflow_binding_snapshot.get('binding_id')}"
                    if binding_mode == "pool_workflow_binding"
                    else "pool_schema_template.metadata.workflow_binding"
                ),
                "resolve_at": "compile",
                "sensitive": False,
                "status": "applied" if binding_mode != "unbound" else "skipped",
                "binding_mode": binding_mode or "unbound",
                "provenance": workflow_binding_snapshot,
            }
        )
    elif plan.workflow_binding_hint:
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
        binding = {
            "target_ref": f"workflow.operation_ref.{step.node_id}",
            "source_ref": f"operation_exposure:{template_exposure_id}@{template_exposure_revision}",
            "resolve_at": "compile",
            "sensitive": False,
            "status": "applied",
            "binding_mode": "pinned_exposure",
            "alias": step.operation_alias,
        }
        provenance = getattr(step, "provenance", None)
        if isinstance(provenance, dict) and provenance:
            binding["provenance"] = dict(provenance)
        bindings.append(binding)
    return bindings


def _resolve_retry_master_data_snapshot_ref(
    *,
    run: PoolRun,
    run_input: dict[str, Any],
    parent_input_context: dict[str, Any],
) -> str:
    persisted_ref = str(parent_input_context.get("master_data_snapshot_ref") or "").strip()
    if persisted_ref:
        return persisted_ref
    return build_master_data_snapshot_ref(run=run, run_input=run_input)


def _resolve_retry_master_data_binding_artifact_ref(
    *,
    run: PoolRun,
    parent_input_context: dict[str, Any],
    master_data_snapshot_ref: str,
    document_plan_artifact: dict[str, Any] | None,
) -> str:
    persisted_ref = str(parent_input_context.get("master_data_binding_artifact_ref") or "").strip()
    if persisted_ref:
        return persisted_ref
    return build_master_data_binding_artifact_ref(
        run=run,
        snapshot_ref=master_data_snapshot_ref,
        document_plan_artifact=document_plan_artifact,
    )


def _build_operation_binding_snapshot(*, plan) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for step in getattr(plan, "steps", ()):
        template_exposure_id = str(getattr(step, "template_exposure_id", "") or "").strip()
        template_exposure_revision = getattr(step, "template_exposure_revision", None)
        if not template_exposure_id or template_exposure_revision is None:
            continue
        item = {
            "node_id": step.node_id,
            "alias": step.operation_alias,
            "binding_mode": "pinned_exposure",
            "template_exposure_id": template_exposure_id,
            "template_exposure_revision": int(template_exposure_revision),
        }
        provenance = getattr(step, "provenance", None)
        if isinstance(provenance, dict) and provenance:
            item["provenance"] = dict(provenance)
        snapshot.append(item)
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
