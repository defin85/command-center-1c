from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.intercompany_pools.command_log import record_pool_run_command_outcome
from apps.intercompany_pools.command_outbox import (
    PoolRunCommandOutboxConflict,
    dispatch_pool_run_command_outbox,
    enqueue_pool_run_command_outbox_intent,
)
from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolRun,
    PoolRunCommandOutbox,
    PoolRunCommandOutboxIntent,
    PoolRunCommandOutboxStatus,
    PoolRunCommandResultClass,
    PoolRunCommandType,
)
from apps.tenancy.models import Tenant


@pytest.fixture
def run_fixture() -> PoolRun:
    tenant = Tenant.objects.create(slug="pool-command-outbox", name="Pool Command Outbox")
    pool = OrganizationPool.objects.create(tenant=tenant, code="pool-command-outbox", name="Pool Command Outbox")
    return PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        period_start=date(2026, 1, 1),
    )


@pytest.mark.django_db
def test_enqueue_pool_run_command_outbox_intent_is_idempotent_by_command_log(run_fixture: PoolRun) -> None:
    command_log = record_pool_run_command_outcome(
        run=run_fixture,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-outbox-idem",
        command_fingerprint="awaiting_approval",
        result_class=PoolRunCommandResultClass.ACCEPTED,
        response_status_code=202,
        response_snapshot={"status": "accepted"},
    ).entry

    message_payload = {
        "operation_id": str(run_fixture.workflow_execution_id or run_fixture.id),
        "operation_type": "execute_workflow",
        "execution_config": {"idempotency_key": str(run_fixture.workflow_execution_id or run_fixture.id)},
    }
    first = enqueue_pool_run_command_outbox_intent(
        run=run_fixture,
        intent_type=PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION,
        command_log=command_log,
        message_payload=message_payload,
    )
    second = enqueue_pool_run_command_outbox_intent(
        run=run_fixture,
        intent_type=PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION,
        command_log=command_log,
        message_payload=message_payload,
    )

    assert first.created is True
    assert second.created is False
    assert first.entry.id == second.entry.id
    assert PoolRunCommandOutbox.objects.count() == 1


@pytest.mark.django_db
def test_enqueue_pool_run_command_outbox_intent_rejects_incompatible_reuse(run_fixture: PoolRun) -> None:
    command_log = record_pool_run_command_outcome(
        run=run_fixture,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-outbox-conflict",
        command_fingerprint="awaiting_approval",
        result_class=PoolRunCommandResultClass.ACCEPTED,
        response_status_code=202,
        response_snapshot={"status": "accepted"},
    ).entry

    enqueue_pool_run_command_outbox_intent(
        run=run_fixture,
        intent_type=PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION,
        command_log=command_log,
        message_payload={"operation_id": str(run_fixture.id), "operation_type": "execute_workflow"},
    )

    with pytest.raises(PoolRunCommandOutboxConflict):
        enqueue_pool_run_command_outbox_intent(
            run=run_fixture,
            intent_type=PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION,
            command_log=command_log,
            message_payload={"operation_id": str(run_fixture.id), "operation_type": "cancel_workflow"},
        )


@pytest.mark.django_db
def test_dispatch_pool_run_command_outbox_marks_entry_as_dispatched(run_fixture: PoolRun) -> None:
    now = timezone.now()
    outbox = PoolRunCommandOutbox.objects.create(
        run=run_fixture,
        tenant_id=run_fixture.tenant_id,
        intent_type=PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION,
        message_payload={
            "operation_id": str(run_fixture.id),
            "operation_type": "execute_workflow",
            "execution_config": {"idempotency_key": str(run_fixture.id)},
        },
        next_retry_at=now - timedelta(seconds=1),
    )

    with patch("apps.intercompany_pools.command_outbox.redis_client.enqueue_operation_stream") as enqueue:
        enqueue.return_value = "1702389123456-0"
        result = dispatch_pool_run_command_outbox(now=now, batch_size=10)

    assert result.claimed == 1
    assert result.dispatched == 1
    assert result.failed == 0

    outbox.refresh_from_db()
    assert outbox.status == PoolRunCommandOutboxStatus.DISPATCHED
    assert outbox.stream_message_id == "1702389123456-0"
    assert outbox.dispatch_attempts == 1
    assert outbox.dispatched_at is not None
    assert outbox.last_error == ""
    assert outbox.last_error_code == ""
    enqueue.assert_called_once_with(
        outbox.message_payload,
        stream_name="commands:worker:workflows",
    )


@pytest.mark.django_db
def test_dispatch_pool_run_command_outbox_retries_with_backoff_and_republish(run_fixture: PoolRun) -> None:
    now = timezone.now()
    outbox = PoolRunCommandOutbox.objects.create(
        run=run_fixture,
        tenant_id=run_fixture.tenant_id,
        intent_type=PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION,
        message_payload={
            "operation_id": str(run_fixture.id),
            "operation_type": "execute_workflow",
            "execution_config": {"idempotency_key": str(run_fixture.id)},
        },
        next_retry_at=now - timedelta(seconds=1),
    )

    enqueue_path = "apps.intercompany_pools.command_outbox.redis_client.enqueue_operation_stream"
    with patch(enqueue_path) as enqueue:
        enqueue.side_effect = [RuntimeError("redis down"), "1702389123555-0"]
        first = dispatch_pool_run_command_outbox(
            now=now,
            batch_size=10,
            retry_base_seconds=3,
            retry_cap_seconds=120,
        )

        outbox.refresh_from_db()
        retry_time = outbox.next_retry_at
        second = dispatch_pool_run_command_outbox(
            now=retry_time,
            batch_size=10,
            retry_base_seconds=3,
            retry_cap_seconds=120,
        )

    assert first.claimed == 1
    assert first.dispatched == 0
    assert first.failed == 1

    outbox.refresh_from_db()
    assert outbox.status == PoolRunCommandOutboxStatus.DISPATCHED
    assert outbox.dispatch_attempts == 2
    assert outbox.stream_message_id == "1702389123555-0"
    assert outbox.last_error == ""
    assert outbox.last_error_code == ""

    assert second.claimed == 1
    assert second.dispatched == 1
    assert second.failed == 0
    assert enqueue.call_count == 2
    first_payload = enqueue.call_args_list[0].args[0]
    second_payload = enqueue.call_args_list[1].args[0]
    assert first_payload == outbox.message_payload
    assert second_payload == outbox.message_payload


@pytest.mark.django_db
def test_dispatch_pool_run_command_outbox_records_variant_a_sli_metrics(run_fixture: PoolRun) -> None:
    now = timezone.now()
    claimed = PoolRunCommandOutbox.objects.create(
        run=run_fixture,
        tenant_id=run_fixture.tenant_id,
        intent_type=PoolRunCommandOutboxIntent.ENQUEUE_WORKFLOW_EXECUTION,
        message_payload={
            "operation_id": str(run_fixture.id),
            "operation_type": "execute_workflow",
            "execution_config": {"idempotency_key": str(run_fixture.id)},
        },
        dispatch_attempts=0,
        next_retry_at=now - timedelta(seconds=1),
    )
    saturated_pending = PoolRunCommandOutbox.objects.create(
        run=run_fixture,
        tenant_id=run_fixture.tenant_id,
        intent_type=PoolRunCommandOutboxIntent.CANCEL_WORKFLOW_EXECUTION,
        message_payload={
            "operation_id": str(run_fixture.id),
            "operation_type": "cancel_workflow",
        },
        dispatch_attempts=5,
        next_retry_at=now - timedelta(minutes=5),
    )

    with (
        patch("apps.intercompany_pools.command_outbox.redis_client.enqueue_operation_stream", return_value="1702389123999-0"),
        patch("apps.intercompany_pools.command_outbox.set_pool_run_command_outbox_lag_seconds") as set_lag,
        patch("apps.intercompany_pools.command_outbox.set_pool_run_command_outbox_retry_saturation") as set_saturation,
    ):
        result = dispatch_pool_run_command_outbox(now=now, batch_size=1)

    assert result.claimed == 1
    assert result.dispatched == 1
    assert result.failed == 0

    claimed.refresh_from_db()
    saturated_pending.refresh_from_db()
    assert claimed.status == PoolRunCommandOutboxStatus.DISPATCHED
    assert saturated_pending.status == PoolRunCommandOutboxStatus.PENDING

    lag_seconds = float(set_lag.call_args.args[0])
    assert lag_seconds >= 0.0
    set_saturation.assert_called_once_with(1.0, saturated_pending=1, total_pending=1)
