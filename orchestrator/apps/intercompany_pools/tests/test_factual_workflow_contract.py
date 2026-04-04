from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.factual_scope_selection import FACTUAL_SCOPE_CONTRACT_VERSION
from apps.intercompany_pools.factual_sync_runtime import build_factual_sales_report_sync_scope
from apps.intercompany_pools.factual_workflow_contract import (
    build_pool_factual_sync_workflow_input_context,
    validate_pool_factual_sync_workflow_input_context,
)
from apps.intercompany_pools.models import OrganizationPool, PoolFactualLane
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-workflow-contract-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-workflow-contract-{suffix}.odata",
        username="admin",
        password="secret",
        server_address="srv-factual",
        server_port=1540,
    )


@pytest.mark.django_db
def test_build_pool_factual_sync_workflow_input_context_dual_writes_factual_scope_contract() -> None:
    tenant = Tenant.objects.create(
        slug=f"factual-workflow-contract-{uuid4().hex[:6]}",
        name="Factual Workflow Contract",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-workflow-contract-pool-{uuid4().hex[:6]}",
        name="Factual Workflow Contract Pool",
    )
    database = _create_database(tenant=tenant, suffix="dual-write")
    scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-a", "org-b"),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
        selector_key=f"pool:{pool.id}:sales_report_v1:2026-01-01",
        gl_account_set_id=str(uuid4()),
        gl_account_set_revision_id="gl_account_set_rev_test",
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

    payload = build_pool_factual_sync_workflow_input_context(
        checkpoint_id=str(uuid4()),
        tenant_id=str(tenant.id),
        pool_id=str(pool.id),
        database=database,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-a", "org-b"),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
        lane=PoolFactualLane.READ,
        correlation_id="corr-factual-contract-001",
        origin_system="tests",
        origin_event_id="evt-factual-contract-001",
        scope=scope,
    )

    assert payload["scope_fingerprint"] == scope.scope_fingerprint
    assert payload["factual_scope_contract"]["contract_version"] == FACTUAL_SCOPE_CONTRACT_VERSION
    assert payload["factual_scope_contract"]["gl_account_set_revision_id"] == "gl_account_set_rev_test"
    assert payload["factual_scope_contract"]["resolved_bindings"][0]["target_ref_key"] == "account-62"


@pytest.mark.django_db
def test_validate_pool_factual_sync_workflow_input_context_rejects_mismatched_nested_account_codes() -> None:
    tenant = Tenant.objects.create(
        slug=f"factual-workflow-contract-mismatch-{uuid4().hex[:6]}",
        name="Factual Workflow Contract Mismatch",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-workflow-contract-mismatch-pool-{uuid4().hex[:6]}",
        name="Factual Workflow Contract Mismatch Pool",
    )
    database = _create_database(tenant=tenant, suffix="mismatch")
    scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-a",),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
        selector_key=f"pool:{pool.id}:sales_report_v1:2026-01-01",
        gl_account_set_id=str(uuid4()),
        gl_account_set_revision_id="gl_account_set_rev_test",
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
    payload = build_pool_factual_sync_workflow_input_context(
        checkpoint_id=str(uuid4()),
        tenant_id=str(tenant.id),
        pool_id=str(pool.id),
        database=database,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=("org-a",),
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
        lane=PoolFactualLane.READ,
        correlation_id="corr-factual-contract-002",
        origin_system="tests",
        origin_event_id="evt-factual-contract-002",
        scope=scope,
    )
    payload["account_codes"] = "62.01"

    with pytest.raises(ValueError, match="factual_scope_contract.effective_members codes"):
        validate_pool_factual_sync_workflow_input_context(input_context=payload)
