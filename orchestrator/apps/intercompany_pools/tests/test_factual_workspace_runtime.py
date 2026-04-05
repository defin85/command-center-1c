from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.factual_scope_selection import FACTUAL_SCOPE_CONTRACT_VERSION
from apps.intercompany_pools.factual_sync_runtime import build_factual_sales_report_sync_scope
from apps.intercompany_pools.factual_workspace_runtime import (
    _get_or_create_checkpoint_for_scope,
    _update_checkpoint_scope_contract,
)
from apps.intercompany_pools.models import OrganizationPool, PoolFactualLane, PoolFactualSyncCheckpoint
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-workspace-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-workspace-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_pool(*, tenant: Tenant, suffix: str) -> OrganizationPool:
    return OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-workspace-pool-{suffix}-{uuid4().hex[:6]}",
        name=f"Factual Workspace Pool {suffix}",
    )


@pytest.mark.django_db
def test_get_or_create_checkpoint_for_scope_upgrades_legacy_checkpoint_and_backfills_scope_contract() -> None:
    tenant = Tenant.objects.create(
        slug=f"factual-workspace-upgrade-{uuid4().hex[:6]}",
        name="Factual Workspace Upgrade",
    )
    pool = _create_pool(tenant=tenant, suffix="upgrade")
    database = _create_database(tenant=tenant, suffix="upgrade")
    legacy_checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        scope_fingerprint="",
        metadata={},
    )
    scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-a",),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
        selector_key=f"pool:{pool.id}:sales_report_v1:2026-01-01",
        gl_account_set_id=str(uuid4()),
        gl_account_set_revision_id="gl_account_set_rev_v1",
        effective_members=(
            {
                "canonical_id": "factual_sales_report_62_01",
                "code": "62.01",
                "name": "62.01",
                "chart_identity": "ChartOfAccounts_Хозрасчетный",
                "sort_order": 0,
            },
            {
                "canonical_id": "factual_sales_report_90_01",
                "code": "90.01",
                "name": "90.01",
                "chart_identity": "ChartOfAccounts_Хозрасчетный",
                "sort_order": 1,
            },
        ),
        resolved_bindings=(
            {
                "canonical_id": "factual_sales_report_62_01",
                "code": "62.01",
                "name": "62.01",
                "chart_identity": "ChartOfAccounts_Хозрасчетный",
                "target_ref_key": "account-62",
                "binding_source": "binding_table",
            },
            {
                "canonical_id": "factual_sales_report_90_01",
                "code": "90.01",
                "name": "90.01",
                "chart_identity": "ChartOfAccounts_Хозрасчетный",
                "target_ref_key": "account-90",
                "binding_source": "binding_table",
            },
        ),
        contract_version=FACTUAL_SCOPE_CONTRACT_VERSION,
    )

    checkpoint, created = _get_or_create_checkpoint_for_scope(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        scope_fingerprint=scope.scope_fingerprint,
        default_entrypoint="pools_factual_workspace",
    )

    assert created is False
    assert checkpoint.id == legacy_checkpoint.id
    assert checkpoint.scope_fingerprint == scope.scope_fingerprint
    assert checkpoint.metadata["default_entrypoint"] == "pools_factual_workspace"

    checkpoint = _update_checkpoint_scope_contract(
        checkpoint=checkpoint,
        scope=scope,
        default_entrypoint="pools_factual_workspace",
    )
    checkpoint.refresh_from_db()

    assert checkpoint.metadata["source_scope"]["scope_fingerprint"] == scope.scope_fingerprint
    assert checkpoint.metadata["factual_scope_contract"]["contract_version"] == FACTUAL_SCOPE_CONTRACT_VERSION
    assert checkpoint.metadata["factual_scope_contract"]["selector_key"] == f"pool:{pool.id}:sales_report_v1:2026-01-01"
    assert checkpoint.metadata["factual_scope_contract"]["resolved_bindings"][0]["target_ref_key"] == "account-62"
