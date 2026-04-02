from __future__ import annotations

from datetime import date
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolRun,
    PoolRunCommandOutbox,
    PoolRunCommandOutboxIntent,
    PoolRunCommandResultClass,
    PoolRunCommandType,
    PoolRunCommandLog,
    PoolRunMode,
)
from apps.intercompany_pools.safe_commands import (
    CONFLICT_REASON_IDEMPOTENCY_KEY_REUSED,
    CONFLICT_REASON_READINESS_BLOCKED,
    CONFLICT_REASON_TERMINAL_STATE,
    TERMINAL_REASON_ABORTED_BY_OPERATOR,
    process_pool_run_safe_command,
)
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


User = get_user_model()


def _create_safe_run_with_awaiting_approval_execution(
    *,
    input_context_overrides: dict[str, object] | None = None,
) -> PoolRun:
    tenant = Tenant.objects.create(slug=f"safe-commands-{uuid4().hex[:8]}", name="Safe Commands")
    pool = OrganizationPool.objects.create(tenant=tenant, code=f"pool-{uuid4().hex[:6]}", name="Pool Safe")
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        mode=PoolRunMode.SAFE,
        period_start=date(2026, 1, 1),
    )
    run.mark_validated(summary={"rows": 1}, diagnostics=[])
    run.save(update_fields=["status", "validated_at", "validation_summary", "diagnostics", "updated_at"])

    template = WorkflowTemplate.objects.create(
        name=f"safe-cmd-template-{uuid4().hex[:8]}",
        description="",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure={
            "nodes": [
                {
                    "id": "approval_gate",
                    "name": "Approval Gate",
                    "type": "operation",
                    "template_id": "pool.approval_gate",
                }
            ],
            "edges": [],
        },
        is_valid=True,
        is_active=True,
    )
    input_context: dict[str, object] = {
        "pool_run_id": str(run.id),
        "approval_required": True,
        "approval_state": "awaiting_approval",
        "approved_at": None,
        "publication_step_state": "not_enqueued",
    }
    if input_context_overrides:
        input_context.update(input_context_overrides)

    execution = template.create_execution(
        input_context,
        tenant=tenant,
        execution_consumer="pools",
    )
    execution.start()
    execution.save()
    execution.complete({"ready": True})
    execution.save(update_fields=["status", "final_result", "completed_at"])

    run.workflow_execution_id = execution.id
    run.workflow_status = execution.status
    run.execution_backend = "workflow_core"
    run.workflow_template_name = template.name
    run.save(
        update_fields=[
            "workflow_execution_id",
            "workflow_status",
            "execution_backend",
            "workflow_template_name",
            "updated_at",
        ]
    )
    return run


@pytest.mark.django_db
def test_safe_commands_confirm_then_abort_keeps_single_winner_outbox() -> None:
    run = _create_safe_run_with_awaiting_approval_execution()
    operator = User.objects.create_user(
        username=f"safe-operator-{uuid4().hex[:8]}",
        email=f"safe-operator-{uuid4().hex[:8]}@example.test",
    )

    confirm = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-race-1",
        requested_by=operator,
    )
    abort = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.ABORT_PUBLICATION,
        idempotency_key="abort-race-1",
    )

    assert confirm.response_status_code == 202
    assert confirm.result_class == PoolRunCommandResultClass.ACCEPTED
    assert confirm.outbox_entry_id is not None

    run = PoolRun.objects.get(id=run.id)
    assert run.publication_confirmed_at is not None
    assert run.publication_confirmed_by == operator

    assert abort.response_status_code == 409
    assert abort.result_class == PoolRunCommandResultClass.CONFLICT
    assert abort.conflict_reason == CONFLICT_REASON_TERMINAL_STATE
    assert abort.outbox_entry_id is None

    outbox_entries = list(PoolRunCommandOutbox.objects.filter(run=run).order_by("id"))
    assert len(outbox_entries) == 1
    assert outbox_entries[0].intent_type == PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION
    metadata = (outbox_entries[0].message_payload or {}).get("metadata") or {}
    assert metadata.get("created_by") == operator.username
    assert metadata.get("workflow_execution_id") == str(run.workflow_execution_id)
    assert metadata.get("root_operation_id") == str(run.workflow_execution_id)
    assert metadata.get("execution_consumer") == "pools"
    assert metadata.get("lane") == "workflows"

    execution = WorkflowExecution.objects.get(id=run.workflow_execution_id)
    publication_auth = execution.input_context.get("publication_auth")
    assert publication_auth == {
        "strategy": "actor",
        "actor_username": operator.username,
        "source": "confirm_publication",
    }


@pytest.mark.django_db
def test_safe_commands_abort_then_confirm_keeps_single_winner_outbox() -> None:
    run = _create_safe_run_with_awaiting_approval_execution()

    abort = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.ABORT_PUBLICATION,
        idempotency_key="abort-race-2",
    )
    confirm = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-race-2",
    )

    assert abort.response_status_code == 202
    assert abort.result_class == PoolRunCommandResultClass.ACCEPTED
    assert abort.outbox_entry_id is not None

    assert confirm.response_status_code == 409
    assert confirm.result_class == PoolRunCommandResultClass.CONFLICT
    assert confirm.conflict_reason == CONFLICT_REASON_TERMINAL_STATE
    assert confirm.outbox_entry_id is None

    execution = WorkflowExecution.objects.get(id=run.workflow_execution_id)
    assert execution.input_context.get("terminal_reason") == TERMINAL_REASON_ABORTED_BY_OPERATOR

    outbox_entries = list(PoolRunCommandOutbox.objects.filter(run=run).order_by("id"))
    assert len(outbox_entries) == 1
    assert outbox_entries[0].intent_type == PoolRunCommandOutboxIntent.CANCEL_WORKFLOW_EXECUTION


@pytest.mark.django_db
def test_safe_commands_replay_same_idempotency_key_returns_snapshot_without_new_outbox() -> None:
    run = _create_safe_run_with_awaiting_approval_execution()

    first = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-replay",
    )
    replay = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-replay",
    )

    assert first.response_status_code == 202
    assert first.result_class == PoolRunCommandResultClass.ACCEPTED
    assert replay.replayed is True
    assert replay.response_status_code == 202
    assert replay.result_class == PoolRunCommandResultClass.ACCEPTED
    assert replay.response_snapshot == first.response_snapshot
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 1


@pytest.mark.django_db
def test_safe_commands_reused_key_for_other_command_returns_idempotency_conflict() -> None:
    run = _create_safe_run_with_awaiting_approval_execution()

    first = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.ABORT_PUBLICATION,
        idempotency_key="shared-safe-key",
    )
    reused = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="shared-safe-key",
    )

    assert first.response_status_code == 202
    assert reused.response_status_code == 409
    assert reused.result_class == PoolRunCommandResultClass.CONFLICT
    assert reused.conflict_reason == CONFLICT_REASON_IDEMPOTENCY_KEY_REUSED
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 1


@pytest.mark.django_db
def test_safe_commands_confirm_returns_readiness_blocked_conflict_without_outbox() -> None:
    blocker = {
        "code": "POOL_DOCUMENT_POLICY_MAPPING_INVALID",
        "detail": "Document policy is incomplete for minimal_documents_full_payload.",
        "entity_name": "Document_Sales",
        "field_or_table_path": "Goods",
    }
    run = _create_safe_run_with_awaiting_approval_execution(
        input_context_overrides={"pool_runtime_readiness_blockers": [blocker]}
    )

    outcome = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-readiness-blocked-1",
    )

    assert outcome.response_status_code == 409
    assert outcome.result_class == PoolRunCommandResultClass.CONFLICT
    assert outcome.conflict_reason == CONFLICT_REASON_READINESS_BLOCKED
    assert outcome.outbox_entry_id is None
    assert outcome.response_snapshot["readiness_blockers"] == [blocker]
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0


@pytest.mark.django_db
def test_safe_commands_readiness_blocked_conflict_replay_preserves_same_snapshot() -> None:
    blockers = [
        {
            "code": "MASTER_DATA_BINDING_CONFLICT",
            "detail": "Canonical master-data entity does not provide ib_ref_key for the target database binding scope.",
            "kind": "binding_source_missing",
            "entity_name": "party",
            "field_or_table_path": "party-without-refs",
            "database_id": "11111111-1111-1111-1111-111111111111",
            "diagnostic": {
                "canonical_id": "party-without-refs",
                "token": "master_data.party.party-without-refs.counterparty.ref",
                "scope_hint": "counterparty",
            },
        },
        {
            "code": "MASTER_DATA_ENTITY_NOT_FOUND",
            "detail": "Canonical master-data entity is missing for the publication target binding scope.",
            "kind": "canonical_entity_missing",
            "entity_name": "party",
            "field_or_table_path": "missing-party",
            "database_id": "22222222-2222-2222-2222-222222222222",
            "diagnostic": {
                "canonical_id": "missing-party",
                "token": "master_data.party.missing-party.counterparty.ref",
                "scope_hint": "counterparty",
            },
        },
    ]
    run = _create_safe_run_with_awaiting_approval_execution(
        input_context_overrides={"pool_runtime_readiness_blockers": blockers}
    )

    first = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-readiness-blocked-replay",
    )
    replay = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-readiness-blocked-replay",
    )

    assert first.response_status_code == 409
    assert first.result_class == PoolRunCommandResultClass.CONFLICT
    assert first.conflict_reason == CONFLICT_REASON_READINESS_BLOCKED
    assert replay.replayed is True
    assert replay.response_status_code == 409
    assert replay.result_class == PoolRunCommandResultClass.CONFLICT
    assert replay.conflict_reason == CONFLICT_REASON_READINESS_BLOCKED
    assert replay.response_snapshot == first.response_snapshot
    assert replay.response_snapshot["readiness_blockers"] == blockers
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0


@pytest.mark.django_db
def test_safe_commands_confirm_noop_backfills_pool_run_confirmation_for_approved_execution() -> None:
    operator = User.objects.create_user(
        username=f"safe-approved-{uuid4().hex[:8]}",
        email=f"safe-approved-{uuid4().hex[:8]}@example.test",
    )
    run = _create_safe_run_with_awaiting_approval_execution(
        input_context_overrides={
            "approval_state": "approved",
            "approved_at": timezone.now().isoformat(),
            "publication_step_state": "queued",
        }
    )

    outcome = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-approved-backfill-1",
        requested_by=operator,
    )

    assert outcome.response_status_code == 200
    assert outcome.result_class == PoolRunCommandResultClass.NOOP
    run = PoolRun.objects.get(id=run.id)
    assert run.publication_confirmed_at is not None
    assert run.publication_confirmed_by == operator
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0


@pytest.mark.django_db
def test_safe_commands_confirm_locks_workflow_execution_before_pool_run() -> None:
    run = _create_safe_run_with_awaiting_approval_execution()

    lock_order: list[str] = []
    original_execution_select_for_update = WorkflowExecution.objects.select_for_update
    original_run_select_for_update = PoolRun.objects.select_for_update

    def _track_execution_lock(*args, **kwargs):
        lock_order.append("execution")
        return original_execution_select_for_update(*args, **kwargs)

    def _track_run_lock(*args, **kwargs):
        lock_order.append("run")
        return original_run_select_for_update(*args, **kwargs)

    with (
        patch.object(WorkflowExecution.objects, "select_for_update", side_effect=_track_execution_lock),
        patch.object(PoolRun.objects, "select_for_update", side_effect=_track_run_lock),
    ):
        outcome = process_pool_run_safe_command(
            run_id=run.id,
            command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
            idempotency_key="confirm-lock-order-1",
        )

    assert outcome.response_status_code == 202
    assert lock_order
    assert lock_order[0] == "execution"
    assert "run" in lock_order[1:]


@pytest.mark.django_db
def test_safe_commands_variant_a_atomicity_rolls_back_command_log_when_outbox_write_fails() -> None:
    run = _create_safe_run_with_awaiting_approval_execution()
    execution = WorkflowExecution.objects.get(id=run.workflow_execution_id)
    before_context = dict(execution.input_context)
    assert run.publication_confirmed_at is None

    with patch(
        "apps.intercompany_pools.safe_commands.enqueue_pool_run_command_outbox_intent",
        side_effect=RuntimeError("forced outbox failure"),
    ):
        with pytest.raises(RuntimeError, match="forced outbox failure"):
            process_pool_run_safe_command(
                run_id=run.id,
                command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
                idempotency_key="confirm-atomicity-fail-1",
            )

    refreshed_context = WorkflowExecution.objects.values_list("input_context", flat=True).get(id=execution.id)
    assert refreshed_context == before_context
    run = PoolRun.objects.get(id=run.id)
    assert run.publication_confirmed_at is None
    assert PoolRunCommandLog.objects.filter(run=run).count() == 0
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0
