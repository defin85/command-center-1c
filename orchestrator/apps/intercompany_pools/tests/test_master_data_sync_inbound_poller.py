from __future__ import annotations

from uuid import uuid4

import pytest

from django.db import transaction

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_inbound_poller import (
    InboundPollerTransportError,
    MasterDataSyncInboundChange,
    MasterDataSyncInboundProcessResult,
    MasterDataSyncSelectChangesResult,
    poll_master_data_sync_inbound_changes,
    process_master_data_sync_inbound_batch,
    schedule_master_data_sync_notify_changes_received_after_commit,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncCheckpoint,
    PoolMasterDataSyncCheckpointStatus,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-inbound-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_poller_creates_checkpoint_and_reads_changes_from_empty_checkpoint() -> None:
    tenant = Tenant.objects.create(slug=f"sync-inbound-{uuid4().hex[:6]}", name="Sync Inbound")
    database = _create_database(tenant=tenant, suffix="create")
    call_args: dict[str, object] = {}

    def _select_changes(*, checkpoint_token: str, **kwargs):
        call_args["checkpoint_token"] = checkpoint_token
        return MasterDataSyncSelectChangesResult(
            changes=[
                MasterDataSyncInboundChange(
                    origin_system="ib",
                    origin_event_id="evt-001",
                    canonical_id="item-001",
                    entity_type=PoolMasterDataEntityType.ITEM,
                    payload={"name": "Item 001"},
                    payload_fingerprint="fp-001",
                )
            ],
            source_checkpoint_token=checkpoint_token,
            next_checkpoint_token="cp-001",
        )

    result = poll_master_data_sync_inbound_changes(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        select_changes=_select_changes,
    )

    assert call_args["checkpoint_token"] == ""
    assert len(result.changes) == 1
    assert result.next_checkpoint_token == "cp-001"

    checkpoint = PoolMasterDataSyncCheckpoint.objects.get(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
    )
    assert checkpoint.status == PoolMasterDataSyncCheckpointStatus.ACTIVE
    assert checkpoint.checkpoint_token == ""
    assert checkpoint.metadata["pending_checkpoint_token"] == "cp-001"


@pytest.mark.django_db
def test_poller_uses_existing_checkpoint_token() -> None:
    tenant = Tenant.objects.create(slug=f"sync-inbound-existing-{uuid4().hex[:6]}", name="Sync Inbound Existing")
    database = _create_database(tenant=tenant, suffix="existing")
    PoolMasterDataSyncCheckpoint.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.CONTRACT,
        status=PoolMasterDataSyncCheckpointStatus.ACTIVE,
        checkpoint_token="cp-existing",
    )

    captured: dict[str, str] = {}

    def _select_changes(*, checkpoint_token: str, **kwargs):
        captured["checkpoint_token"] = checkpoint_token
        return MasterDataSyncSelectChangesResult(
            changes=[],
            source_checkpoint_token=checkpoint_token,
            next_checkpoint_token=checkpoint_token,
        )

    poll_master_data_sync_inbound_changes(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.CONTRACT,
        select_changes=_select_changes,
    )

    assert captured["checkpoint_token"] == "cp-existing"


@pytest.mark.django_db
def test_poller_marks_checkpoint_error_on_select_changes_failure() -> None:
    tenant = Tenant.objects.create(slug=f"sync-inbound-error-{uuid4().hex[:6]}", name="Sync Inbound Error")
    database = _create_database(tenant=tenant, suffix="error")

    def _failing_select_changes(**kwargs):
        raise InboundPollerTransportError(code="SELECT_CHANGES_FAILED", detail="transport unavailable")

    with pytest.raises(InboundPollerTransportError):
        poll_master_data_sync_inbound_changes(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.PARTY,
            select_changes=_failing_select_changes,
        )

    checkpoint = PoolMasterDataSyncCheckpoint.objects.get(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
    )
    assert checkpoint.status == PoolMasterDataSyncCheckpointStatus.ERROR
    assert checkpoint.last_error_code == "SELECT_CHANGES_FAILED"
    assert "transport unavailable" in checkpoint.last_error


@pytest.mark.django_db(transaction=True)
def test_acknowledge_after_commit_advances_checkpoint_position() -> None:
    tenant = Tenant.objects.create(slug=f"sync-inbound-ack-{uuid4().hex[:6]}", name="Sync Inbound Ack")
    database = _create_database(tenant=tenant, suffix="ack")
    checkpoint = PoolMasterDataSyncCheckpoint.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
        status=PoolMasterDataSyncCheckpointStatus.ACTIVE,
        checkpoint_token="cp-001",
        metadata={
            "source_checkpoint_token": "cp-001",
            "pending_checkpoint_token": "cp-002",
        },
    )

    notify_calls: list[dict[str, str]] = []

    def _notify_changes_received(*, checkpoint_token: str, next_checkpoint_token: str, **kwargs):
        notify_calls.append(
            {
                "checkpoint_token": checkpoint_token,
                "next_checkpoint_token": next_checkpoint_token,
            }
        )

    with transaction.atomic():
        scheduled = schedule_master_data_sync_notify_changes_received_after_commit(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            notify_changes_received=_notify_changes_received,
        )
        assert scheduled is True
        assert notify_calls == []

    checkpoint.refresh_from_db()
    assert len(notify_calls) == 1
    assert notify_calls[0]["checkpoint_token"] == "cp-001"
    assert notify_calls[0]["next_checkpoint_token"] == "cp-002"
    assert checkpoint.checkpoint_token == "cp-002"
    assert checkpoint.status == PoolMasterDataSyncCheckpointStatus.ACTIVE
    assert checkpoint.last_error_code == ""
    assert "pending_checkpoint_token" not in checkpoint.metadata
    assert checkpoint.metadata["source_checkpoint_token"] == "cp-002"
    assert checkpoint.last_applied_at is not None


@pytest.mark.django_db(transaction=True)
def test_acknowledge_is_not_called_on_rollback() -> None:
    tenant = Tenant.objects.create(slug=f"sync-inbound-rollback-{uuid4().hex[:6]}", name="Sync Inbound Rollback")
    database = _create_database(tenant=tenant, suffix="rollback")
    checkpoint = PoolMasterDataSyncCheckpoint.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.CONTRACT,
        status=PoolMasterDataSyncCheckpointStatus.ACTIVE,
        checkpoint_token="cp-100",
        metadata={
            "source_checkpoint_token": "cp-100",
            "pending_checkpoint_token": "cp-101",
        },
    )

    notify_calls: list[str] = []

    def _notify_changes_received(**kwargs):
        notify_calls.append("called")

    with pytest.raises(RuntimeError, match="force rollback"):
        with transaction.atomic():
            scheduled = schedule_master_data_sync_notify_changes_received_after_commit(
                tenant_id=str(tenant.id),
                database_id=str(database.id),
                entity_type=PoolMasterDataEntityType.CONTRACT,
                notify_changes_received=_notify_changes_received,
            )
            assert scheduled is True
            raise RuntimeError("force rollback")

    checkpoint.refresh_from_db()
    assert notify_calls == []
    assert checkpoint.checkpoint_token == "cp-100"
    assert checkpoint.status == PoolMasterDataSyncCheckpointStatus.ACTIVE
    assert checkpoint.metadata["pending_checkpoint_token"] == "cp-101"


@pytest.mark.django_db(transaction=True)
def test_acknowledge_error_marks_checkpoint_error_without_advancing_token() -> None:
    tenant = Tenant.objects.create(slug=f"sync-inbound-ack-err-{uuid4().hex[:6]}", name="Sync Inbound Ack Error")
    database = _create_database(tenant=tenant, suffix="ack-err")
    checkpoint = PoolMasterDataSyncCheckpoint.objects.create(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataSyncCheckpointStatus.ACTIVE,
        checkpoint_token="cp-201",
        metadata={
            "source_checkpoint_token": "cp-201",
            "pending_checkpoint_token": "cp-202",
        },
    )

    def _failing_notify_changes_received(**kwargs):
        raise InboundPollerTransportError(code="NOTIFY_CHANGES_FAILED", detail="notify transport unavailable")

    with pytest.raises(InboundPollerTransportError):
        with transaction.atomic():
            schedule_master_data_sync_notify_changes_received_after_commit(
                tenant_id=str(tenant.id),
                database_id=str(database.id),
                entity_type=PoolMasterDataEntityType.PARTY,
                notify_changes_received=_failing_notify_changes_received,
            )

    checkpoint.refresh_from_db()
    assert checkpoint.checkpoint_token == "cp-201"
    assert checkpoint.status == PoolMasterDataSyncCheckpointStatus.ERROR
    assert checkpoint.last_error_code == "NOTIFY_CHANGES_FAILED"
    assert "notify transport unavailable" in checkpoint.last_error
    assert checkpoint.metadata["pending_checkpoint_token"] == "cp-202"


@pytest.mark.django_db(transaction=True)
def test_recovery_replay_skips_duplicate_apply_after_notify_failure_restart() -> None:
    tenant = Tenant.objects.create(slug=f"sync-inbound-replay-{uuid4().hex[:6]}", name="Sync Inbound Replay")
    database = _create_database(tenant=tenant, suffix="replay")
    inbound_change = MasterDataSyncInboundChange(
        origin_system="ib",
        origin_event_id="evt-replay-001",
        canonical_id="item-777",
        entity_type=PoolMasterDataEntityType.ITEM,
        payload={"name": "Replay Item"},
        payload_fingerprint="fp-replay-001",
    )
    poll_checkpoint_tokens: list[str] = []

    def _select_changes(*, checkpoint_token: str, **kwargs):
        poll_checkpoint_tokens.append(checkpoint_token)
        return MasterDataSyncSelectChangesResult(
            changes=[inbound_change],
            source_checkpoint_token=checkpoint_token,
            next_checkpoint_token="cp-replay-001",
        )

    apply_calls: list[str] = []

    def _apply_change(*, change: MasterDataSyncInboundChange, **kwargs):
        apply_calls.append(change.origin_event_id)

    def _failing_notify(**kwargs):
        raise InboundPollerTransportError(code="NOTIFY_CHANGES_FAILED", detail="notify unavailable")

    with pytest.raises(InboundPollerTransportError):
        process_master_data_sync_inbound_batch(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            select_changes=_select_changes,
            apply_change=_apply_change,
            notify_changes_received=_failing_notify,
        )

    checkpoint = PoolMasterDataSyncCheckpoint.objects.get(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.ITEM,
    )
    assert checkpoint.checkpoint_token == ""
    assert checkpoint.status == PoolMasterDataSyncCheckpointStatus.ERROR
    assert checkpoint.metadata["pending_checkpoint_token"] == "cp-replay-001"
    assert len(checkpoint.metadata["inbound_applied_fingerprints"]) == 1
    assert apply_calls == ["evt-replay-001"]
    assert poll_checkpoint_tokens == [""]

    notify_calls: list[dict[str, str]] = []

    def _notify_ok(*, checkpoint_token: str, next_checkpoint_token: str, **kwargs):
        notify_calls.append(
            {
                "checkpoint_token": checkpoint_token,
                "next_checkpoint_token": next_checkpoint_token,
            }
        )

    result = process_master_data_sync_inbound_batch(
        tenant_id=str(tenant.id),
        database_id=str(database.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        select_changes=_select_changes,
        apply_change=_apply_change,
        notify_changes_received=_notify_ok,
    )

    assert isinstance(result, MasterDataSyncInboundProcessResult)
    assert result.polled == 1
    assert result.applied == 0
    assert result.duplicates == 1
    assert result.ack_scheduled is True
    assert result.next_checkpoint_token == "cp-replay-001"
    assert apply_calls == ["evt-replay-001"]
    assert poll_checkpoint_tokens == ["", ""]
    assert notify_calls == [{"checkpoint_token": "", "next_checkpoint_token": "cp-replay-001"}]

    checkpoint.refresh_from_db()
    assert checkpoint.checkpoint_token == "cp-replay-001"
    assert checkpoint.status == PoolMasterDataSyncCheckpointStatus.ACTIVE
    assert checkpoint.last_error_code == ""
    assert "pending_checkpoint_token" not in checkpoint.metadata


@pytest.mark.django_db(transaction=True)
def test_recovery_does_not_ack_when_local_apply_raises() -> None:
    tenant = Tenant.objects.create(slug=f"sync-inbound-apply-{uuid4().hex[:6]}", name="Sync Inbound Apply Error")
    database = _create_database(tenant=tenant, suffix="apply")
    inbound_change = MasterDataSyncInboundChange(
        origin_system="ib",
        origin_event_id="evt-apply-001",
        canonical_id="party-100",
        entity_type=PoolMasterDataEntityType.PARTY,
        payload={"name": "Party 100"},
        payload_fingerprint="fp-apply-001",
    )
    notify_calls: list[str] = []

    def _select_changes(*, checkpoint_token: str, **kwargs):
        return MasterDataSyncSelectChangesResult(
            changes=[inbound_change],
            source_checkpoint_token=checkpoint_token,
            next_checkpoint_token="cp-apply-001",
        )

    def _apply_failing(**kwargs):
        raise RuntimeError("apply failed in local transaction")

    def _notify(**kwargs):
        notify_calls.append("called")

    with pytest.raises(RuntimeError, match="apply failed"):
        process_master_data_sync_inbound_batch(
            tenant_id=str(tenant.id),
            database_id=str(database.id),
            entity_type=PoolMasterDataEntityType.PARTY,
            select_changes=_select_changes,
            apply_change=_apply_failing,
            notify_changes_received=_notify,
        )

    checkpoint = PoolMasterDataSyncCheckpoint.objects.get(
        tenant=tenant,
        database=database,
        entity_type=PoolMasterDataEntityType.PARTY,
    )
    assert notify_calls == []
    assert checkpoint.checkpoint_token == ""
    assert checkpoint.status == PoolMasterDataSyncCheckpointStatus.ERROR
    assert checkpoint.last_error_code == "INBOUND_APPLY_FAILED"
    assert checkpoint.metadata["pending_checkpoint_token"] == "cp-apply-001"
