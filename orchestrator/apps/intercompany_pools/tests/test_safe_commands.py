from __future__ import annotations

from datetime import date
from unittest.mock import patch
from uuid import uuid4

import pytest

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
    CONFLICT_REASON_TERMINAL_STATE,
    TERMINAL_REASON_ABORTED_BY_OPERATOR,
    process_pool_run_safe_command,
)
from apps.templates.workflow.models import WorkflowExecution, WorkflowTemplate, WorkflowType
from apps.tenancy.models import Tenant


def _create_safe_run_with_awaiting_approval_execution() -> PoolRun:
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
    execution = template.create_execution(
        {
            "pool_run_id": str(run.id),
            "approval_required": True,
            "approval_state": "awaiting_approval",
            "approved_at": None,
            "publication_step_state": "not_enqueued",
        },
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

    confirm = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-race-1",
    )
    abort = process_pool_run_safe_command(
        run_id=run.id,
        command_type=PoolRunCommandType.ABORT_PUBLICATION,
        idempotency_key="abort-race-1",
    )

    assert confirm.response_status_code == 202
    assert confirm.result_class == PoolRunCommandResultClass.ACCEPTED
    assert confirm.outbox_entry_id is not None

    assert abort.response_status_code == 409
    assert abort.result_class == PoolRunCommandResultClass.CONFLICT
    assert abort.conflict_reason == CONFLICT_REASON_TERMINAL_STATE
    assert abort.outbox_entry_id is None

    outbox_entries = list(PoolRunCommandOutbox.objects.filter(run=run).order_by("id"))
    assert len(outbox_entries) == 1
    assert outbox_entries[0].intent_type == PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION


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
def test_safe_commands_variant_a_atomicity_rolls_back_command_log_when_outbox_write_fails() -> None:
    run = _create_safe_run_with_awaiting_approval_execution()
    execution = WorkflowExecution.objects.get(id=run.workflow_execution_id)
    before_context = dict(execution.input_context)

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
    assert PoolRunCommandLog.objects.filter(run=run).count() == 0
    assert PoolRunCommandOutbox.objects.filter(run=run).count() == 0
