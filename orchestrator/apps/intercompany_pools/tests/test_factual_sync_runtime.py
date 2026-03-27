from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    OrganizationPool,
    PoolFactualLane,
    PoolFactualSyncCheckpoint,
)
from apps.tenancy.models import Tenant


def _create_database(
    *,
    tenant: Tenant,
    suffix: str,
    status: str = Database.STATUS_ACTIVE,
    metadata: dict | None = None,
) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-sync-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-sync-{suffix}.odata",
        username="admin",
        password="secret",
        status=status,
        metadata=metadata or {},
        server_address="srv-factual",
        server_port=1540,
    )


def _create_checkpoint(
    *,
    tenant: Tenant,
    pool: OrganizationPool,
    database: Database,
) -> PoolFactualSyncCheckpoint:
    return PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        source_checkpoint_token="cp-initial",
    )


def _create_pool(*, tenant: Tenant, suffix: str) -> OrganizationPool:
    return OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-sync-pool-{suffix}-{uuid4().hex[:6]}",
        name=f"Factual Sync Pool {suffix}",
    )


@pytest.mark.django_db
def test_build_factual_sales_report_sync_contract_is_bounded_and_minute_scale() -> None:
    from apps.intercompany_pools.factual_sync_runtime import build_factual_sales_report_sync_contract

    tenant = Tenant.objects.create(slug=f"factual-sync-contract-{uuid4().hex[:6]}", name="Factual Sync Contract")
    database = _create_database(tenant=tenant, suffix="contract")
    fixed_now = datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc)

    contract = build_factual_sales_report_sync_contract(
        database=database,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-b", "org-a", "org-b"),
        account_codes=("62.01", "90.01", "62.01"),
        movement_kinds=("credit", "debit", "credit"),
        activity="active",
        now=fixed_now,
    )

    assert contract["role"] == "read"
    assert contract["polling_tier"] == "active"
    assert contract["poll_interval_seconds"] == "120"
    assert contract["freshness_target_seconds"] == "120"
    assert contract["source_profile"] == "sales_report_v1"
    assert contract["read_boundary_kind"] == "odata"
    assert contract["direct_db_access"] == "0"
    assert contract["read_boundary_entity_allowlist"] == (
        "AccountingRegister_Хозрасчетный,"
        "Document_ВозвратТоваровОтПокупателя,"
        "Document_КорректировкаРеализации,"
        "Document_РеализацияТоваровУслуг,"
        "InformationRegister_ДанныеПервичныхДокументов"
    )
    assert contract["read_boundary_function_allowlist"] == "Balance,BalanceAndTurnovers,Turnovers"
    assert contract["accounting_register_entity"] == "AccountingRegister_Хозрасчетный"
    assert contract["accounting_register_function"] == "Turnovers"
    assert contract["information_register_entity"] == "InformationRegister_ДанныеПервичныхДокументов"
    assert contract["document_entities"] == (
        "Document_ВозвратТоваровОтПокупателя,"
        "Document_КорректировкаРеализации,"
        "Document_РеализацияТоваровУслуг"
    )
    assert contract["organization_ids"] == "org-a,org-b"
    assert contract["account_codes"] == "62.01,90.01"
    assert contract["movement_kinds"] == "credit,debit"
    assert contract["quarter_start"] == "2026-01-01"
    assert contract["quarter_end"] == "2026-03-31"
    assert contract["scope_fingerprint"]


@pytest.mark.django_db
def test_build_factual_sales_report_sync_contract_rejects_unbounded_scope() -> None:
    from apps.intercompany_pools.factual_sync_runtime import build_factual_sales_report_sync_contract

    tenant = Tenant.objects.create(slug=f"factual-sync-invalid-{uuid4().hex[:6]}", name="Factual Sync Invalid")
    database = _create_database(tenant=tenant, suffix="invalid")

    with pytest.raises(ValueError, match="organization_ids"):
        build_factual_sales_report_sync_contract(
            database=database,
            quarter_start=date(2026, 1, 1),
            quarter_end=date(2026, 3, 31),
            organization_ids=(),
            account_codes=("62.01",),
            movement_kinds=("credit",),
        )


@pytest.mark.django_db
def test_resolve_factual_sync_source_state_detects_maintenance_status() -> None:
    from apps.intercompany_pools.factual_sync_runtime import (
        ERROR_CODE_POOL_FACTUAL_SYNC_SOURCE_MAINTENANCE,
        SOURCE_STATE_MAINTENANCE,
        resolve_factual_sync_source_state,
    )

    tenant = Tenant.objects.create(slug=f"factual-sync-maint-{uuid4().hex[:6]}", name="Factual Sync Maint")
    database = _create_database(
        tenant=tenant,
        suffix="maint",
        status=Database.STATUS_MAINTENANCE,
        metadata={"denied_message": "Planned maintenance"},
    )

    state = resolve_factual_sync_source_state(database=database)

    assert state.state == SOURCE_STATE_MAINTENANCE
    assert state.code == ERROR_CODE_POOL_FACTUAL_SYNC_SOURCE_MAINTENANCE
    assert "planned maintenance" in state.detail.lower()


@pytest.mark.django_db
def test_resolve_factual_sync_source_state_detects_blocked_external_sessions() -> None:
    from apps.intercompany_pools.factual_sync_runtime import (
        ERROR_CODE_POOL_FACTUAL_SYNC_EXTERNAL_SESSIONS_BLOCKED,
        SOURCE_STATE_BLOCKED_EXTERNAL_SESSIONS,
        resolve_factual_sync_source_state,
    )

    tenant = Tenant.objects.create(slug=f"factual-sync-blocked-{uuid4().hex[:6]}", name="Factual Sync Blocked")
    fixed_now = datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc)
    database = _create_database(
        tenant=tenant,
        suffix="blocked",
        metadata={
            "sessions_deny": True,
            "denied_from": "2026-03-27T09:00:00Z",
            "denied_to": "2026-03-27T11:00:00Z",
            "denied_message": "External sessions denied",
        },
    )

    state = resolve_factual_sync_source_state(database=database, now=fixed_now)

    assert state.state == SOURCE_STATE_BLOCKED_EXTERNAL_SESSIONS
    assert state.code == ERROR_CODE_POOL_FACTUAL_SYNC_EXTERNAL_SESSIONS_BLOCKED
    assert state.window_from == datetime(2026, 3, 27, 9, 0, tzinfo=dt_timezone.utc)
    assert state.window_to == datetime(2026, 3, 27, 11, 0, tzinfo=dt_timezone.utc)


@pytest.mark.django_db
def test_mark_factual_sync_checkpoint_success_persists_freshness_metadata() -> None:
    from apps.intercompany_pools.factual_sync_runtime import (
        build_factual_sales_report_sync_scope,
        mark_factual_sync_checkpoint_success,
        resolve_factual_sync_source_state,
    )

    tenant = Tenant.objects.create(slug=f"factual-sync-success-{uuid4().hex[:6]}", name="Factual Sync Success")
    database = _create_database(tenant=tenant, suffix="success")
    pool = _create_pool(tenant=tenant, suffix="success")
    checkpoint = _create_checkpoint(tenant=tenant, pool=pool, database=database)
    fixed_now = datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc)
    scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-b", "org-a"),
        account_codes=("62.01",),
        movement_kinds=("credit",),
    )

    mark_factual_sync_checkpoint_success(
        checkpoint=checkpoint,
        scope=scope,
        source_state=resolve_factual_sync_source_state(database=database, now=fixed_now),
        source_checkpoint_token="cp-002",
        synced_at=fixed_now,
    )

    checkpoint.refresh_from_db()
    assert checkpoint.source_checkpoint_token == "cp-002"
    assert checkpoint.last_synced_at == fixed_now
    assert checkpoint.last_error_code == ""
    assert checkpoint.last_error == ""
    assert checkpoint.metadata["freshness_target_seconds"] == 120
    assert checkpoint.metadata["freshness_state"] == "fresh"
    assert checkpoint.metadata["source_availability"] == "available"
    assert checkpoint.metadata["source_scope"]["organization_ids"] == ["org-a", "org-b"]
    assert checkpoint.metadata["source_scope"]["account_codes"] == ["62.01"]


@pytest.mark.django_db
def test_mark_factual_sync_checkpoint_error_marks_stale_and_sanitizes_detail() -> None:
    from apps.intercompany_pools.factual_sync_runtime import (
        ERROR_CODE_POOL_FACTUAL_SYNC_EXTERNAL_SESSIONS_BLOCKED,
        FactualSyncTransportError,
        build_factual_sales_report_sync_scope,
        mark_factual_sync_checkpoint_error,
        resolve_factual_sync_source_state,
    )

    tenant = Tenant.objects.create(slug=f"factual-sync-error-{uuid4().hex[:6]}", name="Factual Sync Error")
    fixed_now = datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc)
    database = _create_database(
        tenant=tenant,
        suffix="error",
        metadata={
            "sessions_deny": True,
            "denied_from": "2026-03-27T09:00:00Z",
            "denied_to": "2026-03-27T11:00:00Z",
            "denied_message": "External sessions denied",
        },
    )
    pool = _create_pool(tenant=tenant, suffix="error")
    checkpoint = _create_checkpoint(tenant=tenant, pool=pool, database=database)
    scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-a",),
        account_codes=("62.01",),
        movement_kinds=("credit",),
    )

    source_state = resolve_factual_sync_source_state(database=database, now=fixed_now)
    mark_factual_sync_checkpoint_error(
        checkpoint=checkpoint,
        scope=scope,
        source_state=source_state,
        error=FactualSyncTransportError(
            code=ERROR_CODE_POOL_FACTUAL_SYNC_EXTERNAL_SESSIONS_BLOCKED,
            detail="auth failed password=super-secret url=http://user:pwd@localhost/odata",
        ),
        failed_at=fixed_now,
    )

    checkpoint.refresh_from_db()
    assert checkpoint.last_error_code == ERROR_CODE_POOL_FACTUAL_SYNC_EXTERNAL_SESSIONS_BLOCKED
    assert checkpoint.metadata["freshness_state"] == "stale"
    assert checkpoint.metadata["source_availability"] == "blocked_external_sessions"
    assert checkpoint.metadata["last_error_at"] == fixed_now.isoformat()
    assert "password=***" in checkpoint.last_error
    assert "http://***:***@localhost/odata" in checkpoint.last_error
    assert "super-secret" not in checkpoint.last_error
