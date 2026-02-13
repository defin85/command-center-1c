from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.intercompany_pools.command_log import (
    PoolRunCommandIdempotencyConflict,
    cleanup_expired_pool_run_command_logs,
    record_pool_run_command_outcome,
)
from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolRun,
    PoolRunCommandCasOutcome,
    PoolRunCommandLog,
    PoolRunCommandResultClass,
    PoolRunCommandType,
)
from apps.tenancy.models import Tenant


@pytest.fixture
def run_fixture() -> PoolRun:
    tenant = Tenant.objects.create(slug="pool-command-log", name="Pool Command Log")
    pool = OrganizationPool.objects.create(tenant=tenant, code="pool-command-log", name="Pool Command Log")
    return PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        period_start=date(2026, 1, 1),
    )


@pytest.mark.django_db
def test_record_pool_run_command_outcome_creates_command_log_entry(run_fixture: PoolRun) -> None:
    result = record_pool_run_command_outcome(
        run=run_fixture,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-1",
        command_fingerprint="awaiting_approval",
        result_class=PoolRunCommandResultClass.ACCEPTED,
        response_status_code=202,
        response_snapshot={"status": "accepted"},
        cas_outcome=PoolRunCommandCasOutcome.WON,
    )

    assert result.replayed is False
    assert result.entry.run_id == run_fixture.id
    assert result.entry.tenant_id == run_fixture.tenant_id
    assert result.entry.command_type == PoolRunCommandType.CONFIRM_PUBLICATION
    assert result.entry.result_class == PoolRunCommandResultClass.ACCEPTED
    assert result.entry.response_status_code == 202
    assert result.entry.response_snapshot == {"status": "accepted"}
    assert result.entry.replay_count == 0
    assert result.entry.last_replayed_at is None


@pytest.mark.django_db
def test_record_pool_run_command_outcome_returns_deterministic_replay(run_fixture: PoolRun) -> None:
    first = record_pool_run_command_outcome(
        run=run_fixture,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-2",
        command_fingerprint="awaiting_approval",
        result_class=PoolRunCommandResultClass.ACCEPTED,
        response_status_code=202,
        response_snapshot={"status": "accepted"},
    )

    second = record_pool_run_command_outcome(
        run=run_fixture,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-2",
        command_fingerprint="awaiting_approval",
        result_class=PoolRunCommandResultClass.NOOP,
        response_status_code=200,
        response_snapshot={"status": "noop"},
    )

    assert first.entry.id == second.entry.id
    assert second.replayed is True

    entry = PoolRunCommandLog.objects.get(id=first.entry.id)
    assert entry.result_class == PoolRunCommandResultClass.ACCEPTED
    assert entry.response_status_code == 202
    assert entry.response_snapshot == {"status": "accepted"}
    assert entry.replay_count == 1
    assert entry.last_replayed_at is not None


@pytest.mark.django_db
def test_record_pool_run_command_outcome_rejects_reused_key_with_incompatible_fingerprint(run_fixture: PoolRun) -> None:
    first = record_pool_run_command_outcome(
        run=run_fixture,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="confirm-3",
        command_fingerprint="awaiting_approval",
        result_class=PoolRunCommandResultClass.ACCEPTED,
        response_status_code=202,
        response_snapshot={"status": "accepted"},
    )

    with pytest.raises(PoolRunCommandIdempotencyConflict) as conflict:
        record_pool_run_command_outcome(
            run=run_fixture,
            command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
            idempotency_key="confirm-3",
            command_fingerprint="queued",
            result_class=PoolRunCommandResultClass.NOOP,
            response_status_code=200,
            response_snapshot={"status": "noop"},
        )

    assert conflict.value.existing_entry.id == first.entry.id


@pytest.mark.django_db
def test_record_pool_run_command_outcome_rejects_reused_key_for_other_command_type(run_fixture: PoolRun) -> None:
    first = record_pool_run_command_outcome(
        run=run_fixture,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="shared-key",
        command_fingerprint="awaiting_approval",
        result_class=PoolRunCommandResultClass.ACCEPTED,
        response_status_code=202,
        response_snapshot={"status": "accepted"},
    )

    with pytest.raises(PoolRunCommandIdempotencyConflict) as conflict:
        record_pool_run_command_outcome(
            run=run_fixture,
            command_type=PoolRunCommandType.ABORT_PUBLICATION,
            idempotency_key="shared-key",
            command_fingerprint="awaiting_approval",
            result_class=PoolRunCommandResultClass.ACCEPTED,
            response_status_code=202,
            response_snapshot={"status": "accepted"},
        )

    assert conflict.value.existing_entry.id == first.entry.id


@pytest.mark.django_db
def test_cleanup_expired_pool_run_command_logs_deletes_only_expired_entries(run_fixture: PoolRun) -> None:
    now = timezone.now()
    expired = PoolRunCommandLog.objects.create(
        run=run_fixture,
        tenant_id=run_fixture.tenant_id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="expired",
        command_fingerprint="awaiting_approval",
        result_class=PoolRunCommandResultClass.ACCEPTED,
        response_status_code=202,
        response_snapshot={"status": "accepted"},
        expires_at=now - timedelta(minutes=1),
    )
    active = PoolRunCommandLog.objects.create(
        run=run_fixture,
        tenant_id=run_fixture.tenant_id,
        command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
        idempotency_key="active",
        command_fingerprint="awaiting_approval",
        result_class=PoolRunCommandResultClass.ACCEPTED,
        response_status_code=202,
        response_snapshot={"status": "accepted"},
        expires_at=now + timedelta(days=1),
    )

    deleted = cleanup_expired_pool_run_command_logs(now=now, batch_size=1)

    assert deleted == 1
    assert not PoolRunCommandLog.objects.filter(id=expired.id).exists()
    assert PoolRunCommandLog.objects.filter(id=active.id).exists()


@pytest.mark.django_db
def test_record_pool_run_command_outcome_records_write_error_metric_on_storage_failure(
    run_fixture: PoolRun,
) -> None:
    with (
        patch("apps.intercompany_pools.command_log.record_pool_run_command_log_write_error") as record_error,
        patch("apps.intercompany_pools.command_log.PoolRunCommandLog.objects.create", side_effect=RuntimeError("db down")),
    ):
        with pytest.raises(RuntimeError, match="db down"):
            record_pool_run_command_outcome(
                run=run_fixture,
                command_type=PoolRunCommandType.CONFIRM_PUBLICATION,
                idempotency_key="metrics-write-error",
                command_fingerprint="awaiting_approval",
                result_class=PoolRunCommandResultClass.ACCEPTED,
                response_status_code=202,
                response_snapshot={"status": "accepted"},
            )

    record_error.assert_called_once_with("RuntimeError")
