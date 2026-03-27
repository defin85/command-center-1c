from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.models import OrganizationPool
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-read-lane-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-read-lane-{suffix}.odata",
        username="admin",
        password="secret",
        server_address="srv-read-lane",
        server_port=1540,
    )


def _create_pool(*, tenant: Tenant, suffix: str) -> OrganizationPool:
    return OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-read-lane-pool-{suffix}-{uuid4().hex[:6]}",
        name=f"Factual Read Lane Pool {suffix}",
    )


@pytest.mark.django_db
def test_build_factual_read_lane_execution_context_is_read_only_materialization_contract() -> None:
    from apps.intercompany_pools.factual_read_lane import build_factual_read_lane_execution_context

    tenant = Tenant.objects.create(slug=f"factual-read-lane-{uuid4().hex[:6]}", name="Factual Read Lane")
    database = _create_database(tenant=tenant, suffix="contract")
    pool = _create_pool(tenant=tenant, suffix="contract")
    fixed_now = datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc)

    context = build_factual_read_lane_execution_context(
        tenant_id=str(tenant.id),
        pool_id=str(pool.id),
        database=database,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-b", "org-a"),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
        actions=("sync_source_slice", "update_checkpoint", "refresh_batch_settlement"),
        activity="active",
        now=fixed_now,
    )

    assert context["contract_version"] == "pool_factual_read_lane.v1"
    assert context["subsystem"] == "factual_read_projection"
    assert context["lane"] == "read"
    assert context["role"] == "read"
    assert context["factual_use_case"] == "factual:read"
    assert context["materialization_targets"] == (
        "pool_batch_settlements,pool_factual_balance_snapshots,pool_factual_sync_checkpoints"
    )
    assert context["actions"] == "refresh_batch_settlement,sync_source_slice,update_checkpoint"
    assert context["direct_db_access"] == "0"


def test_validate_factual_read_lane_execution_context_rejects_create_run_and_review_actions() -> None:
    from apps.intercompany_pools.factual_read_lane import (
        FACTUAL_READ_LANE_CONTRACT_INVALID,
        validate_factual_read_lane_execution_context,
    )

    with pytest.raises(ValueError, match=FACTUAL_READ_LANE_CONTRACT_INVALID):
        validate_factual_read_lane_execution_context(
            input_context={
                "contract_version": "pool_factual_read_lane.v1",
                "tenant_id": str(uuid4()),
                "pool_id": str(uuid4()),
                "database_id": str(uuid4()),
                "lane": "read",
                "subsystem": "factual_read_projection",
                "actions": ["sync_source_slice", "create_run", "attribute"],
                "materialization_targets": [
                    "pool_factual_sync_checkpoints",
                    "pool_factual_balance_snapshots",
                    "pool_batch_settlements",
                ],
            }
        )


def test_validate_factual_read_lane_execution_context_requires_materialization_targets() -> None:
    from apps.intercompany_pools.factual_read_lane import FACTUAL_READ_LANE_CONTRACT_INVALID, validate_factual_read_lane_execution_context

    with pytest.raises(ValueError, match=FACTUAL_READ_LANE_CONTRACT_INVALID):
        validate_factual_read_lane_execution_context(
            input_context={
                "contract_version": "pool_factual_read_lane.v1",
                "tenant_id": str(uuid4()),
                "pool_id": str(uuid4()),
                "database_id": str(uuid4()),
                "lane": "read",
                "subsystem": "factual_read_projection",
                "actions": ["sync_source_slice"],
                "materialization_targets": ["pool_factual_balance_snapshots"],
            }
        )
