from datetime import date

import pytest
from django_fsm import TransitionNotAllowed

from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolRun,
    PoolRunAuditEvent,
    PoolRunDirection,
    PoolRunMode,
)
from apps.intercompany_pools.runs import build_pool_run_idempotency_key, upsert_pool_run
from apps.tenancy.models import Tenant


@pytest.fixture
def run_fixture() -> PoolRun:
    tenant = Tenant.objects.create(slug="pool-run", name="Pool Run")
    pool = OrganizationPool.objects.create(tenant=tenant, code="pool-run", name="Pool Run")
    return PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.BOTTOM_UP,
        period_start=date(2026, 1, 1),
    )


@pytest.mark.django_db
def test_pool_run_happy_path_to_published(run_fixture: PoolRun) -> None:
    run = run_fixture
    run.mark_validated(summary={"rows": 10}, diagnostics=[])
    run.save()
    assert run.status == PoolRun.STATUS_VALIDATED
    assert run.validated_at is not None

    run.confirm_publication()
    run.save(update_fields=["publication_confirmed_at", "publication_confirmed_by", "updated_at"])
    run.start_publishing()
    run.save()
    assert run.status == PoolRun.STATUS_PUBLISHING
    assert run.publishing_started_at is not None

    run.mark_published(summary={"targets": 3, "ok": 3})
    run.save()
    assert run.status == PoolRun.STATUS_PUBLISHED
    assert run.completed_at is not None
    assert run.is_terminal is True
    events = list(
        PoolRunAuditEvent.objects.filter(run=run).order_by("created_at").values_list("event_type", flat=True)
    )
    assert "run.validated" in events
    assert "run.publication_confirmed" in events
    assert "run.publishing_started" in events
    assert "run.published" in events


@pytest.mark.django_db
def test_pool_run_allows_failure_from_draft(run_fixture: PoolRun) -> None:
    run = run_fixture
    run.mark_failed(error="validation failed", diagnostics=[{"code": "bad_input"}])
    run.save()

    assert run.status == PoolRun.STATUS_FAILED
    assert run.last_error == "validation failed"
    assert run.completed_at is not None
    assert run.is_terminal is True


@pytest.mark.django_db
def test_pool_run_rejects_invalid_transition(run_fixture: PoolRun) -> None:
    run = run_fixture
    with pytest.raises(TransitionNotAllowed):
        run.mark_published(summary={})


@pytest.mark.django_db
def test_pool_run_safe_mode_requires_confirmation(run_fixture: PoolRun) -> None:
    run = run_fixture
    run.mark_validated()
    run.save()
    with pytest.raises(TransitionNotAllowed):
        run.start_publishing()


@pytest.mark.django_db
def test_pool_run_unsafe_mode_can_start_without_confirmation(run_fixture: PoolRun) -> None:
    run = run_fixture
    run.mode = PoolRunMode.UNSAFE
    run.save(update_fields=["mode", "updated_at"])
    run.mark_validated()
    run.save()
    run.start_publishing()
    run.save()
    assert run.status == PoolRun.STATUS_PUBLISHING


@pytest.mark.django_db
def test_build_pool_run_idempotency_key_is_deterministic(run_fixture: PoolRun) -> None:
    run = run_fixture
    key1 = build_pool_run_idempotency_key(
        pool_id=str(run.pool_id),
        period_start=run.period_start,
        period_end=run.period_end,
        direction=run.direction,
        run_input={
            "source_payload": [{"inn": "770000000001", "amount": "10.00"}],
            "starting_amount": "100.0",
        },
    )
    key2 = build_pool_run_idempotency_key(
        pool_id=str(run.pool_id),
        period_start=run.period_start,
        period_end=run.period_end,
        direction=run.direction,
        run_input={
            "starting_amount": "100.00",
            "source_payload": [{"amount": "10", "inn": "770000000001"}],
        },
    )
    key3 = build_pool_run_idempotency_key(
        pool_id=str(run.pool_id),
        period_start=run.period_start,
        period_end=run.period_end,
        direction=run.direction,
        run_input={
            "source_payload": [{"inn": "770000000001", "amount": "99.00"}],
            "starting_amount": "100.00",
        },
    )
    assert key1 == key2
    assert key1 != key3


@pytest.mark.django_db
def test_build_pool_run_idempotency_key_changes_with_workflow_binding() -> None:
    tenant = Tenant.objects.create(slug="pool-run-binding-key", name="Pool Run Binding Key")
    pool = OrganizationPool.objects.create(tenant=tenant, code="pool-binding-key", name="Pool Binding Key")

    base_kwargs = {
        "pool_id": str(pool.id),
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
        "direction": PoolRunDirection.BOTTOM_UP,
        "run_input": {"source_payload": [{"inn": "770000000001", "amount": "10.00"}]},
    }

    first = build_pool_run_idempotency_key(workflow_binding_id="binding-a", **base_kwargs)
    second = build_pool_run_idempotency_key(workflow_binding_id="binding-b", **base_kwargs)

    assert first != second


@pytest.mark.django_db
def test_build_pool_run_idempotency_key_changes_with_attachment_revision() -> None:
    tenant = Tenant.objects.create(slug="pool-run-attachment-revision", name="Pool Run Attachment Revision")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code="pool-attachment-revision",
        name="Pool Attachment Revision",
    )

    base_kwargs = {
        "pool_id": str(pool.id),
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
        "direction": PoolRunDirection.BOTTOM_UP,
        "workflow_binding_id": "binding-a",
        "binding_profile_revision_id": "profile-revision-a",
        "run_input": {"source_payload": [{"inn": "770000000001", "amount": "10.00"}]},
    }

    first = build_pool_run_idempotency_key(workflow_binding_revision=1, **base_kwargs)
    second = build_pool_run_idempotency_key(workflow_binding_revision=2, **base_kwargs)

    assert first != second


@pytest.mark.django_db
def test_build_pool_run_idempotency_key_changes_with_profile_revision_pin() -> None:
    tenant = Tenant.objects.create(slug="pool-run-profile-revision", name="Pool Run Profile Revision")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code="pool-profile-revision",
        name="Pool Profile Revision",
    )

    base_kwargs = {
        "pool_id": str(pool.id),
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
        "direction": PoolRunDirection.BOTTOM_UP,
        "workflow_binding_id": "binding-a",
        "workflow_binding_revision": 3,
        "run_input": {"source_payload": [{"inn": "770000000001", "amount": "10.00"}]},
    }

    first = build_pool_run_idempotency_key(
        binding_profile_revision_id="profile-revision-a",
        **base_kwargs,
    )
    second = build_pool_run_idempotency_key(
        binding_profile_revision_id="profile-revision-b",
        **base_kwargs,
    )

    assert first != second


@pytest.mark.django_db
def test_upsert_pool_run_reuses_existing_run(run_fixture: PoolRun) -> None:
    run = run_fixture
    first = upsert_pool_run(
        tenant=run.tenant,
        pool=run.pool,
        direction=run.direction,
        period_start=run.period_start,
        period_end=run.period_end,
        run_input={"source_payload": [{"inn": "770000000001", "amount": "10.00"}]},
        mode=PoolRunMode.SAFE,
        validation_summary={"version": 1},
    )
    second = upsert_pool_run(
        tenant=run.tenant,
        pool=run.pool,
        direction=run.direction,
        period_start=run.period_start,
        period_end=run.period_end,
        run_input={"source_payload": [{"inn": "770000000001", "amount": "10.00"}]},
        mode=PoolRunMode.UNSAFE,
        validation_summary={"version": 2},
    )

    assert first.created is True
    assert second.created is False
    assert first.run.id == second.run.id
    state = PoolRun.objects.filter(id=second.run.id).values("mode", "validation_summary", "run_input").get()
    assert state["mode"] == PoolRunMode.UNSAFE
    assert state["validation_summary"] == {"version": 2}
    assert state["run_input"] == {"source_payload": [{"inn": "770000000001", "amount": "10.00"}]}
    event_types = list(
        PoolRunAuditEvent.objects.filter(run_id=second.run.id).values_list("event_type", flat=True)
    )
    assert "run.created" in event_types
    assert "run.upserted" in event_types


@pytest.mark.django_db
def test_upsert_pool_run_does_not_reuse_existing_run_for_different_binding(run_fixture: PoolRun) -> None:
    run = run_fixture
    first = upsert_pool_run(
        tenant=run.tenant,
        pool=run.pool,
        direction=run.direction,
        period_start=run.period_start,
        period_end=run.period_end,
        workflow_binding_id="binding-a",
        run_input={"source_payload": [{"inn": "770000000001", "amount": "10.00"}]},
        mode=PoolRunMode.SAFE,
    )
    second = upsert_pool_run(
        tenant=run.tenant,
        pool=run.pool,
        direction=run.direction,
        period_start=run.period_start,
        period_end=run.period_end,
        workflow_binding_id="binding-b",
        run_input={"source_payload": [{"inn": "770000000001", "amount": "10.00"}]},
        mode=PoolRunMode.SAFE,
    )

    assert first.created is True
    assert second.created is True
    assert first.run.id != second.run.id
