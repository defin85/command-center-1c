from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.operations.services import OperationsService
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate

from .document_plan_artifact_contract import (
    POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY,
    build_publication_payload_from_document_plan_artifact,
    validate_document_plan_artifact_v1,
)
from .models import PoolRun, PoolRunMode, PoolSchemaTemplate, PoolSchemaTemplateFormat
from .models import PoolPublicationAttempt, PoolPublicationAttemptStatus
from .publication_auth_mapping import (
    PUBLICATION_AUTH_STRATEGY_ACTOR,
    PUBLICATION_AUTH_STRATEGY_SERVICE,
    build_publication_auth_fail_closed_error,
    evaluate_publication_auth_coverage,
)
from .runtime_template_registry import sync_pool_runtime_template_registry
from .run_input_sanitizer import sanitize_run_input_for_runtime_contract
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

        _validate_publication_auth_mapping_for_run(run=locked_run, requested_by=requested_by)

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
                run_input=sanitize_run_input_for_runtime_contract(run_input=locked_run.run_input),
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
            _build_input_context(
                run=locked_run,
                requested_by=requested_by,
                publication_auth_source=PUBLICATION_AUTH_SOURCE_RUN_CREATE,
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
                run_input=sanitize_run_input_for_runtime_contract(run_input=locked_run.run_input),
            ),
        )
        workflow_template = _resolve_or_create_workflow_template(plan=plan, requested_by=requested_by)

        retry_input_context = _build_input_context(
            run=locked_run,
            requested_by=requested_by,
            publication_auth_source=PUBLICATION_AUTH_SOURCE_RETRY_PUBLICATION,
            fallback_publication_auth=parent_input_context.get("publication_auth"),
        )
        retry_publication_payload = _build_retry_publication_payload(
            run=locked_run,
            retry_request=retry_request,
            parent_input_context=parent_input_context,
        )
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


def _build_input_context(
    *,
    run: PoolRun,
    requested_by: User | None = None,
    publication_auth_source: str = PUBLICATION_AUTH_SOURCE_RUN_CREATE,
    fallback_publication_auth: object | None = None,
) -> dict[str, Any]:
    run_input = sanitize_run_input_for_runtime_contract(run_input=run.run_input)
    return {
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
    }


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
) -> list[dict[str, Any]]:
    filtered_chains: list[dict[str, Any]] = []
    for chain_raw in chains_raw:
        if not isinstance(chain_raw, dict):
            continue
        chain = dict(chain_raw)
        documents_raw = chain.get("documents")
        if not isinstance(documents_raw, list):
            continue

        filtered_documents: list[dict[str, Any]] = []
        for document_raw in documents_raw:
            if not isinstance(document_raw, dict):
                continue
            document = dict(document_raw)
            document_key = str(document.get("idempotency_key") or "").strip()
            if failed_document_keys and document_key and document_key not in failed_document_keys:
                continue
            filtered_documents.append(document)

        if not filtered_documents:
            continue
        chain["documents"] = filtered_documents
        filtered_chains.append(chain)
    return filtered_chains


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
        },
        "execution_snapshot": {
            "pool_run_id": str(run.id),
            "seed": run.seed,
            "period_start": run.period_start.isoformat(),
            "period_end": run.period_end.isoformat() if run.period_end else None,
            "run_input": run_input,
            "publication_auth": publication_auth,
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
