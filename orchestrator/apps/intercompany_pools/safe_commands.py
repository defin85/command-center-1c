from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.operations.services import OperationsService
from apps.templates.workflow.models import WorkflowExecution

from .command_log import PoolRunCommandIdempotencyConflict, record_pool_run_command_outcome
from .command_outbox import enqueue_pool_run_command_outbox_intent
from .models import (
    PoolRun,
    PoolRunCommandCasOutcome,
    PoolRunCommandLog,
    PoolRunCommandOutbox,
    PoolRunCommandOutboxIntent,
    PoolRunCommandOutboxStatus,
    PoolRunCommandResultClass,
    PoolRunCommandType,
    PoolRunMode,
)


APPROVAL_STATE_NOT_REQUIRED = "not_required"
APPROVAL_STATE_PREPARING = "preparing"
APPROVAL_STATE_AWAITING_APPROVAL = "awaiting_approval"
APPROVAL_STATE_APPROVED = "approved"

PUBLICATION_STEP_STATE_NOT_ENQUEUED = "not_enqueued"
PUBLICATION_STEP_STATE_QUEUED = "queued"
PUBLICATION_STEP_STATE_STARTED = "started"
PUBLICATION_STEP_STATE_COMPLETED = "completed"

TERMINAL_REASON_ABORTED_BY_OPERATOR = "aborted_by_operator"

CONFLICT_REASON_NOT_SAFE_RUN = "not_safe_run"
CONFLICT_REASON_AWAITING_PRE_PUBLISH = "awaiting_pre_publish"
CONFLICT_REASON_READINESS_BLOCKED = "readiness_blocked"
CONFLICT_REASON_PUBLICATION_STARTED = "publication_started"
CONFLICT_REASON_TERMINAL_STATE = "terminal_state"
CONFLICT_REASON_IDEMPOTENCY_KEY_REUSED = "idempotency_key_reused"

PUBLICATION_AUTH_STRATEGY_ACTOR = "actor"
PUBLICATION_AUTH_STRATEGY_SERVICE = "service"
PUBLICATION_AUTH_SOURCE_CONFIRM_PUBLICATION = "confirm_publication"

_VALID_APPROVAL_STATES = {
    APPROVAL_STATE_NOT_REQUIRED,
    APPROVAL_STATE_PREPARING,
    APPROVAL_STATE_AWAITING_APPROVAL,
    APPROVAL_STATE_APPROVED,
}
_VALID_PUBLICATION_STATES = {
    PUBLICATION_STEP_STATE_NOT_ENQUEUED,
    PUBLICATION_STEP_STATE_QUEUED,
    PUBLICATION_STEP_STATE_STARTED,
    PUBLICATION_STEP_STATE_COMPLETED,
}


@dataclass(frozen=True)
class SafeCommandOutcome:
    run_id: UUID
    command_type: str
    response_status_code: int
    result_class: str
    conflict_reason: str | None
    replayed: bool
    command_log_id: int | None
    outbox_entry_id: int | None
    response_snapshot: dict[str, Any]


def process_pool_run_safe_command(
    *,
    run_id: UUID,
    command_type: str,
    idempotency_key: str,
    requested_by=None,
    now: datetime | None = None,
) -> SafeCommandOutcome:
    if command_type not in {
        PoolRunCommandType.CONFIRM_PUBLICATION,
        PoolRunCommandType.ABORT_PUBLICATION,
    }:
        raise ValueError(f"Unsupported command_type '{command_type}'")

    normalized_key = str(idempotency_key or "").strip()
    if not normalized_key:
        raise ValueError("Idempotency key must be non-empty")

    decision_time = now or timezone.now()
    command_fingerprint = "v1"

    with transaction.atomic():
        run_link = PoolRun.objects.filter(id=run_id).values("workflow_execution_id").first()
        if run_link is None:
            raise PoolRun.DoesNotExist(f"Pool run {run_id} does not exist")
        initial_execution_id = run_link.get("workflow_execution_id")
        if initial_execution_id is None:
            raise ValueError("Pool run is not linked to workflow execution")

        execution = WorkflowExecution.objects.select_for_update().get(id=initial_execution_id)
        run = PoolRun.objects.select_for_update().filter(id=run_id).first()
        if run is None:
            raise PoolRun.DoesNotExist(f"Pool run {run_id} does not exist")
        if run.workflow_execution_id is None:
            raise ValueError("Pool run is not linked to workflow execution")
        if run.workflow_execution_id != execution.id:
            raise RuntimeError("Pool run workflow execution changed during safe command processing")

        existing = _load_existing_command_log(
            run=run,
            command_type=command_type,
            idempotency_key=normalized_key,
            replay_time=decision_time,
        )
        if existing is not None:
            return _build_replay_outcome(existing=existing, run=run, command_type=command_type)

        conflicting = _load_cross_command_key_reuse(
            run=run,
            command_type=command_type,
            idempotency_key=normalized_key,
        )
        if conflicting is not None:
            snapshot = _build_conflict_snapshot(
                run=run,
                command_type=command_type,
                conflict_reason=CONFLICT_REASON_IDEMPOTENCY_KEY_REUSED,
            )
            return SafeCommandOutcome(
                run_id=run.id,
                command_type=command_type,
                response_status_code=409,
                result_class=PoolRunCommandResultClass.CONFLICT,
                conflict_reason=CONFLICT_REASON_IDEMPOTENCY_KEY_REUSED,
                replayed=False,
                command_log_id=None,
                outbox_entry_id=None,
                response_snapshot=snapshot,
            )

        decision = _decide_command_outcome(
            run=run,
            execution=execution,
            command_type=command_type,
            requested_by=requested_by,
        )

        outbox_entry_id: int | None = None
        if decision["result_class"] == PoolRunCommandResultClass.ACCEPTED:
            has_pending_opposite_outbox = _has_pending_opposite_outbox(
                run=run,
                command_type=command_type,
            )
            if has_pending_opposite_outbox:
                decision = {
                    "result_class": PoolRunCommandResultClass.CONFLICT,
                    "response_status_code": 409,
                    "conflict_reason": CONFLICT_REASON_TERMINAL_STATE,
                    "cas_outcome": PoolRunCommandCasOutcome.LOST,
                    "updates": {},
                    "outbox_intent": None,
                    "message_payload": None,
                }

        updates = decision["updates"]
        if updates:
            input_context = execution.input_context if isinstance(execution.input_context, dict) else {}
            input_context.update(updates)
            execution.input_context = input_context
            execution.save(update_fields=["input_context"])

        approval_state = _resolve_approval_state(run=run, execution=execution)
        if (
            command_type == PoolRunCommandType.CONFIRM_PUBLICATION
            and approval_state == APPROVAL_STATE_APPROVED
            and run.publication_confirmed_at is None
        ):
            run.confirm_publication(confirmed_by=requested_by)
            run.save(
                update_fields=[
                    "publication_confirmed_at",
                    "publication_confirmed_by",
                    "updated_at",
                ]
            )

        response_snapshot = _build_response_snapshot(
            run=run,
            execution=execution,
            command_type=command_type,
            result_class=decision["result_class"],
            conflict_reason=decision["conflict_reason"],
        )

        try:
            write_result = record_pool_run_command_outcome(
                run=run,
                command_type=command_type,
                idempotency_key=normalized_key,
                command_fingerprint=command_fingerprint,
                result_class=decision["result_class"],
                response_status_code=decision["response_status_code"],
                response_snapshot=response_snapshot,
                cas_outcome=decision["cas_outcome"],
                created_by=requested_by,
                now=decision_time,
            )
        except PoolRunCommandIdempotencyConflict:
            snapshot = _build_conflict_snapshot(
                run=run,
                command_type=command_type,
                conflict_reason=CONFLICT_REASON_IDEMPOTENCY_KEY_REUSED,
            )
            return SafeCommandOutcome(
                run_id=run.id,
                command_type=command_type,
                response_status_code=409,
                result_class=PoolRunCommandResultClass.CONFLICT,
                conflict_reason=CONFLICT_REASON_IDEMPOTENCY_KEY_REUSED,
                replayed=False,
                command_log_id=None,
                outbox_entry_id=None,
                response_snapshot=snapshot,
            )

        command_log = write_result.entry

        if decision["outbox_intent"] and isinstance(decision["message_payload"], dict):
            outbox_entry = enqueue_pool_run_command_outbox_intent(
                run=run,
                command_log=command_log,
                intent_type=decision["outbox_intent"],
                message_payload=decision["message_payload"],
            ).entry
            outbox_entry_id = outbox_entry.id

        return SafeCommandOutcome(
            run_id=run.id,
            command_type=command_type,
            response_status_code=decision["response_status_code"],
            result_class=decision["result_class"],
            conflict_reason=decision["conflict_reason"],
            replayed=False,
            command_log_id=command_log.id,
            outbox_entry_id=outbox_entry_id,
            response_snapshot=response_snapshot,
        )


def _load_existing_command_log(
    *,
    run: PoolRun,
    command_type: str,
    idempotency_key: str,
    replay_time: datetime,
) -> PoolRunCommandLog | None:
    existing = (
        PoolRunCommandLog.objects.select_for_update()
        .filter(run=run, command_type=command_type, idempotency_key=idempotency_key)
        .first()
    )
    if existing is None:
        return None
    PoolRunCommandLog.objects.filter(id=existing.id).update(
        replay_count=existing.replay_count + 1,
        last_replayed_at=replay_time,
    )
    existing.refresh_from_db(fields=["replay_count", "last_replayed_at"])
    return existing


def _load_cross_command_key_reuse(
    *,
    run: PoolRun,
    command_type: str,
    idempotency_key: str,
) -> PoolRunCommandLog | None:
    return (
        PoolRunCommandLog.objects.select_for_update()
        .filter(run=run, idempotency_key=idempotency_key)
        .exclude(command_type=command_type)
        .first()
    )


def _has_pending_opposite_outbox(*, run: PoolRun, command_type: str) -> bool:
    opposite_intent = (
        PoolRunCommandOutboxIntent.CANCEL_WORKFLOW_EXECUTION
        if command_type == PoolRunCommandType.CONFIRM_PUBLICATION
        else PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION
    )
    return PoolRunCommandOutbox.objects.filter(
        run=run,
        status=PoolRunCommandOutboxStatus.PENDING,
        intent_type=opposite_intent,
    ).exists()


def _decide_command_outcome(
    *,
    run: PoolRun,
    execution: WorkflowExecution,
    command_type: str,
    requested_by=None,
) -> dict[str, Any]:
    approval_state = _resolve_approval_state(run=run, execution=execution)
    publication_step_state = _resolve_publication_step_state(run=run, execution=execution, approval_state=approval_state)
    terminal_reason = _resolve_terminal_reason(execution=execution)
    publication_started = publication_step_state in {
        PUBLICATION_STEP_STATE_STARTED,
        PUBLICATION_STEP_STATE_COMPLETED,
    }

    if run.mode != PoolRunMode.SAFE or approval_state == APPROVAL_STATE_NOT_REQUIRED:
        return {
            "result_class": PoolRunCommandResultClass.CONFLICT,
            "response_status_code": 409,
            "conflict_reason": CONFLICT_REASON_NOT_SAFE_RUN,
            "cas_outcome": PoolRunCommandCasOutcome.NOT_APPLICABLE,
            "updates": {},
            "outbox_intent": None,
            "message_payload": None,
        }

    if command_type == PoolRunCommandType.CONFIRM_PUBLICATION:
        if terminal_reason or run.is_terminal:
            return {
                "result_class": PoolRunCommandResultClass.CONFLICT,
                "response_status_code": 409,
                "conflict_reason": CONFLICT_REASON_TERMINAL_STATE,
                "cas_outcome": PoolRunCommandCasOutcome.LOST,
                "updates": {},
                "outbox_intent": None,
                "message_payload": None,
            }
        if approval_state == APPROVAL_STATE_PREPARING:
            return {
                "result_class": PoolRunCommandResultClass.CONFLICT,
                "response_status_code": 409,
                "conflict_reason": CONFLICT_REASON_AWAITING_PRE_PUBLISH,
                "cas_outcome": PoolRunCommandCasOutcome.NOT_APPLICABLE,
                "updates": {},
                "outbox_intent": None,
                "message_payload": None,
            }
        readiness_blockers = _resolve_readiness_blockers(execution=execution)
        if approval_state == APPROVAL_STATE_AWAITING_APPROVAL and readiness_blockers:
            return {
                "result_class": PoolRunCommandResultClass.CONFLICT,
                "response_status_code": 409,
                "conflict_reason": CONFLICT_REASON_READINESS_BLOCKED,
                "cas_outcome": PoolRunCommandCasOutcome.NOT_APPLICABLE,
                "updates": {},
                "outbox_intent": None,
                "message_payload": None,
            }
        if approval_state == APPROVAL_STATE_AWAITING_APPROVAL:
            updates = {"approval_state": APPROVAL_STATE_APPROVED, "approved_at": timezone.now().isoformat()}
            if publication_step_state not in {PUBLICATION_STEP_STATE_STARTED, PUBLICATION_STEP_STATE_COMPLETED}:
                updates["publication_step_state"] = PUBLICATION_STEP_STATE_QUEUED
            updates["publication_auth"] = _build_publication_auth_context(
                requested_by=requested_by,
                source=PUBLICATION_AUTH_SOURCE_CONFIRM_PUBLICATION,
            )
            return {
                "result_class": PoolRunCommandResultClass.ACCEPTED,
                "response_status_code": 202,
                "conflict_reason": None,
                "cas_outcome": PoolRunCommandCasOutcome.WON,
                "updates": updates,
                "outbox_intent": PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION,
                "message_payload": _build_enqueue_workflow_message(
                    execution_id=str(execution.id),
                    requested_by=requested_by,
                ),
            }
        if approval_state == APPROVAL_STATE_APPROVED:
            return {
                "result_class": PoolRunCommandResultClass.NOOP,
                "response_status_code": 200,
                "conflict_reason": None,
                "cas_outcome": PoolRunCommandCasOutcome.NOT_APPLICABLE,
                "updates": {},
                "outbox_intent": None,
                "message_payload": None,
            }
        return {
            "result_class": PoolRunCommandResultClass.CONFLICT,
            "response_status_code": 409,
            "conflict_reason": CONFLICT_REASON_TERMINAL_STATE,
            "cas_outcome": PoolRunCommandCasOutcome.LOST,
            "updates": {},
            "outbox_intent": None,
            "message_payload": None,
        }

    # abort-publication
    if terminal_reason == TERMINAL_REASON_ABORTED_BY_OPERATOR:
        return {
            "result_class": PoolRunCommandResultClass.NOOP,
            "response_status_code": 200,
            "conflict_reason": None,
            "cas_outcome": PoolRunCommandCasOutcome.NOT_APPLICABLE,
            "updates": {},
            "outbox_intent": None,
            "message_payload": None,
        }
    if terminal_reason or run.is_terminal:
        return {
            "result_class": PoolRunCommandResultClass.CONFLICT,
            "response_status_code": 409,
            "conflict_reason": CONFLICT_REASON_TERMINAL_STATE,
            "cas_outcome": PoolRunCommandCasOutcome.LOST,
            "updates": {},
            "outbox_intent": None,
            "message_payload": None,
        }
    if publication_started:
        return {
            "result_class": PoolRunCommandResultClass.CONFLICT,
            "response_status_code": 409,
            "conflict_reason": CONFLICT_REASON_PUBLICATION_STARTED,
            "cas_outcome": PoolRunCommandCasOutcome.LOST,
            "updates": {},
            "outbox_intent": None,
            "message_payload": None,
        }
    if approval_state in {APPROVAL_STATE_PREPARING, APPROVAL_STATE_AWAITING_APPROVAL}:
        return {
            "result_class": PoolRunCommandResultClass.ACCEPTED,
            "response_status_code": 202,
            "conflict_reason": None,
            "cas_outcome": PoolRunCommandCasOutcome.WON,
            "updates": {"terminal_reason": TERMINAL_REASON_ABORTED_BY_OPERATOR},
            "outbox_intent": PoolRunCommandOutboxIntent.CANCEL_WORKFLOW_EXECUTION,
            "message_payload": _build_cancel_workflow_message(
                execution_id=str(execution.id),
                requested_by=requested_by,
            ),
        }
    return {
        "result_class": PoolRunCommandResultClass.CONFLICT,
        "response_status_code": 409,
        "conflict_reason": CONFLICT_REASON_TERMINAL_STATE,
        "cas_outcome": PoolRunCommandCasOutcome.LOST,
        "updates": {},
        "outbox_intent": None,
        "message_payload": None,
    }


def _build_replay_outcome(*, existing: PoolRunCommandLog, run: PoolRun, command_type: str) -> SafeCommandOutcome:
    snapshot = existing.response_snapshot if isinstance(existing.response_snapshot, dict) else {}
    return SafeCommandOutcome(
        run_id=run.id,
        command_type=command_type,
        response_status_code=int(existing.response_status_code),
        result_class=existing.result_class,
        conflict_reason=str(snapshot.get("conflict_reason") or "").strip() or None,
        replayed=True,
        command_log_id=existing.id,
        outbox_entry_id=None,
        response_snapshot=snapshot,
    )


def _build_response_snapshot(
    *,
    run: PoolRun,
    execution: WorkflowExecution | None,
    command_type: str,
    result_class: str,
    conflict_reason: str | None,
) -> dict[str, Any]:
    snapshot = {
        "run_id": str(run.id),
        "command_type": command_type,
        "result_class": result_class,
        "conflict_reason": conflict_reason,
    }
    if conflict_reason == CONFLICT_REASON_READINESS_BLOCKED:
        snapshot["readiness_blockers"] = _resolve_readiness_blockers(execution=execution)
    return snapshot


def _build_conflict_snapshot(*, run: PoolRun, command_type: str, conflict_reason: str) -> dict[str, Any]:
    return _build_response_snapshot(
        run=run,
        execution=None,
        command_type=command_type,
        result_class=PoolRunCommandResultClass.CONFLICT,
        conflict_reason=conflict_reason,
    )


def _resolve_approval_state(*, run: PoolRun, execution: WorkflowExecution) -> str:
    context = execution.input_context if isinstance(execution.input_context, dict) else {}
    raw_state = str(context.get("approval_state") or "").strip().lower()
    if raw_state in _VALID_APPROVAL_STATES:
        return raw_state
    if run.mode != PoolRunMode.SAFE:
        return APPROVAL_STATE_NOT_REQUIRED
    if context.get("approved_at") or run.publication_confirmed_at is not None:
        return APPROVAL_STATE_APPROVED
    if execution.status == WorkflowExecution.STATUS_COMPLETED:
        return APPROVAL_STATE_AWAITING_APPROVAL
    return APPROVAL_STATE_PREPARING


def _resolve_publication_step_state(*, run: PoolRun, execution: WorkflowExecution, approval_state: str) -> str:
    context = execution.input_context if isinstance(execution.input_context, dict) else {}
    raw_state = str(context.get("publication_step_state") or "").strip().lower()
    if raw_state in _VALID_PUBLICATION_STATES:
        return raw_state

    if run.mode == PoolRunMode.SAFE and approval_state != APPROVAL_STATE_APPROVED:
        return PUBLICATION_STEP_STATE_NOT_ENQUEUED
    if run.publishing_started_at is not None:
        return PUBLICATION_STEP_STATE_STARTED
    return PUBLICATION_STEP_STATE_QUEUED


def _resolve_terminal_reason(*, execution: WorkflowExecution) -> str | None:
    context = execution.input_context if isinstance(execution.input_context, dict) else {}
    reason = str(context.get("terminal_reason") or "").strip().lower()
    return reason or None


def _resolve_readiness_blockers(*, execution: WorkflowExecution | None) -> list[dict[str, Any]]:
    if execution is None:
        return []
    context = execution.input_context if isinstance(execution.input_context, dict) else {}
    raw_blockers = context.get("pool_runtime_readiness_blockers")
    if not isinstance(raw_blockers, list):
        return []

    blockers: list[dict[str, Any]] = []
    for raw_blocker in raw_blockers:
        if isinstance(raw_blocker, dict):
            blockers.append(dict(raw_blocker))
    return blockers


def _build_enqueue_workflow_message(*, execution_id: str, requested_by=None) -> dict[str, Any]:
    created_by = _resolve_request_actor_username(requested_by=requested_by) or "workflow_engine"
    data = {
        "execution_id": execution_id,
        "execution_consumer": "pools",
        "priority": "normal",
    }
    return OperationsService._build_execution_envelope(
        operation_id=execution_id,
        operation_type="execute_workflow",
        entity="Workflow",
        target_databases=[],
        payload_data=data,
        execution_config={
            "batch_size": 100,
            "timeout_seconds": 300,
            "retry_count": 1,
            "priority": "normal",
            "idempotency_key": execution_id,
        },
        metadata={
            "created_by": created_by,
            "template_id": None,
            "tags": ["workflow", "pools"],
            "workflow_execution_id": execution_id,
            "root_operation_id": execution_id,
            "execution_consumer": "pools",
            "lane": "workflows",
        },
    )


def _build_cancel_workflow_message(*, execution_id: str, requested_by=None) -> dict[str, Any]:
    created_by = _resolve_request_actor_username(requested_by=requested_by) or "workflow_engine"
    operation_id = f"{execution_id}:cancel"
    return OperationsService._build_execution_envelope(
        operation_id=operation_id,
        operation_type="cancel_workflow",
        entity="Workflow",
        target_databases=[],
        payload_data={"execution_id": execution_id},
        execution_config={
            "batch_size": 1,
            "timeout_seconds": 60,
            "retry_count": 1,
            "priority": "normal",
            "idempotency_key": operation_id,
        },
        metadata={
            "created_by": created_by,
            "template_id": None,
            "tags": ["workflow", "pools", "cancel"],
            "workflow_execution_id": execution_id,
            "root_operation_id": execution_id,
            "execution_consumer": "pools",
            "lane": "workflows",
        },
    )


def _build_publication_auth_context(*, requested_by, source: str) -> dict[str, str]:
    actor_username = _resolve_request_actor_username(requested_by=requested_by)
    strategy = PUBLICATION_AUTH_STRATEGY_ACTOR if actor_username else PUBLICATION_AUTH_STRATEGY_SERVICE
    return {
        "strategy": strategy,
        "actor_username": actor_username if strategy == PUBLICATION_AUTH_STRATEGY_ACTOR else "",
        "source": str(source or "").strip() or PUBLICATION_AUTH_SOURCE_CONFIRM_PUBLICATION,
    }


def _resolve_request_actor_username(*, requested_by) -> str:
    if requested_by is None:
        return ""
    return str(getattr(requested_by, "username", "") or "").strip()
