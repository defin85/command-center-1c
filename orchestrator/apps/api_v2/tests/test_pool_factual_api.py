from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSettlement,
    PoolBatchSettlementStatus,
    PoolBatchSourceType,
    PoolEdgeVersion,
    PoolFactualBalanceSnapshot,
    PoolFactualLane,
    PoolFactualReviewItem,
    PoolFactualReviewReason,
    PoolFactualReviewStatus,
    PoolFactualSyncCheckpoint,
    PoolNodeVersion,
)
from apps.intercompany_pools.factual_workflow_runtime import PoolFactualSyncWorkflowStartResult
from apps.tenancy.models import Tenant, TenantMember


@pytest.fixture
def default_tenant() -> Tenant:
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "Default"})
    return tenant


@pytest.fixture
def user(default_tenant: Tenant) -> User:
    user = User.objects.create_user(username=f"pool-factual-user-{uuid4().hex[:8]}", password="pass")
    TenantMember.objects.get_or_create(
        tenant=default_tenant,
        user=user,
        defaults={"role": TenantMember.ROLE_ADMIN},
    )
    return user


@pytest.fixture
def authenticated_client(user: User, default_tenant: Tenant) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_CC1C_TENANT_ID=str(default_tenant.id))
    return client


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"pool-factual-db-{suffix}-{uuid4().hex[:6]}",
        host="localhost",
        odata_url=f"http://localhost/odata/pool-factual-{suffix}.odata",
        username="user",
        password="pass",
    )


def _create_pool_scope(*, tenant: Tenant, suffix: str) -> tuple[OrganizationPool, Organization, PoolEdgeVersion, Database]:
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"pool-factual-{suffix}-{uuid4().hex[:6]}",
        name=f"Pool Factual {suffix}",
    )
    root = Organization.objects.create(
        tenant=tenant,
        name=f"Root {suffix}",
        inn=f"77{uuid4().int % 10**10:010d}",
    )
    database = _create_database(tenant=tenant, suffix=suffix)
    leaf = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Leaf {suffix}",
        inn=f"78{uuid4().int % 10**10:010d}",
    )
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    leaf_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=leaf,
        effective_from=date(2026, 1, 1),
    )
    edge = PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_node,
        effective_from=date(2026, 1, 1),
    )
    return pool, leaf, edge, database


def _build_resolved_factual_scope(
    *,
    pool: OrganizationPool,
    organization_ids: tuple[str, ...],
    quarter_start: date = date(2026, 1, 1),
):
    from apps.intercompany_pools.factual_sync_runtime import build_factual_sales_report_sync_scope

    if quarter_start.month == 10:
        quarter_end = date(quarter_start.year + 1, 1, 1) - timedelta(days=1)
    else:
        quarter_end = date(quarter_start.year, quarter_start.month + 3, 1) - timedelta(days=1)
    return build_factual_sales_report_sync_scope(
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        organization_ids=organization_ids,
        account_codes=("62.01", "90.01"),
        movement_kinds=("credit", "debit"),
    )


def test_build_pool_factual_workspace_summary_uses_review_attention_when_settlement_attention_is_clear() -> None:
    from apps.api_v2.views.intercompany_pools import _build_pool_factual_workspace_summary

    synced_at = datetime.now(dt_timezone.utc)
    batch = PoolBatch()
    batch.settlement = PoolBatchSettlement(
        status=PoolBatchSettlementStatus.DISTRIBUTED,
        incoming_amount=Decimal("10.00"),
        outgoing_amount=Decimal("10.00"),
        open_balance=Decimal("0.00"),
        freshness_at=synced_at,
    )
    checkpoint = PoolFactualSyncCheckpoint(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        last_synced_at=synced_at,
        updated_at=synced_at,
        metadata={
            "freshness_state": "fresh",
            "source_availability": "available",
            "source_availability_detail": "",
            "freshness_target_seconds": 120,
        },
    )

    summary = _build_pool_factual_workspace_summary(
        quarter_start=date(2026, 1, 1),
        settlements=[batch],
        edge_balances=[],
        checkpoints=[checkpoint],
        review_queue={
            "summary": {
                "pending_total": 1,
                "attention_required_total": 1,
            }
        },
    )

    assert summary["pending_review_total"] == 1
    assert summary["attention_required_total"] == 1


def test_build_pool_factual_workspace_summary_uses_worst_checkpoint_source_state() -> None:
    from apps.api_v2.views.intercompany_pools import _build_pool_factual_workspace_summary

    fresh_synced_at = datetime.now(dt_timezone.utc)
    batch = PoolBatch()
    batch.settlement = PoolBatchSettlement(
        status=PoolBatchSettlementStatus.DISTRIBUTED,
        incoming_amount=Decimal("10.00"),
        outgoing_amount=Decimal("10.00"),
        open_balance=Decimal("0.00"),
        freshness_at=fresh_synced_at,
    )
    blocked_checkpoint = PoolFactualSyncCheckpoint(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        last_synced_at=fresh_synced_at,
        updated_at=fresh_synced_at,
        metadata={
            "freshness_state": "fresh",
            "source_availability": "blocked_external_sessions",
            "source_availability_detail": "locked by external sessions",
            "freshness_target_seconds": 120,
        },
    )
    latest_checkpoint = PoolFactualSyncCheckpoint(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        last_synced_at=fresh_synced_at + timedelta(microseconds=1),
        updated_at=fresh_synced_at + timedelta(microseconds=1),
        metadata={
            "freshness_state": "fresh",
            "source_availability": "available",
            "source_availability_detail": "",
            "freshness_target_seconds": 120,
        },
    )

    summary = _build_pool_factual_workspace_summary(
        quarter_start=date(2026, 1, 1),
        settlements=[batch],
        edge_balances=[],
        checkpoints=[blocked_checkpoint, latest_checkpoint],
        review_queue={"summary": {"pending_total": 0, "attention_required_total": 0}},
    )

    assert summary["backlog_total"] == 0
    assert summary["freshness_state"] == "fresh"
    assert summary["source_availability"] == "blocked_external_sessions"
    assert summary["source_availability_detail"] == "locked by external sessions"


def test_build_pool_factual_workspace_summary_exposes_latest_scope_lineage() -> None:
    from apps.api_v2.views.intercompany_pools import _build_pool_factual_workspace_summary

    synced_at = datetime.now(dt_timezone.utc)
    gl_account_set_id = str(uuid4())
    checkpoint = PoolFactualSyncCheckpoint(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        last_synced_at=synced_at,
        updated_at=synced_at,
        scope_fingerprint="scope-fp-001",
        metadata={
            "freshness_state": "fresh",
            "source_availability": "available",
            "source_availability_detail": "",
            "freshness_target_seconds": 120,
            "factual_scope_contract": {
                "contract_version": "factual_scope_contract.v2",
                "selector_key": "pool:pool-1:sales_report_v1:2026-01-01",
                "gl_account_set_id": gl_account_set_id,
                "gl_account_set_revision_id": "gl_account_set_rev_test",
                "scope_fingerprint": "scope-fp-001",
                "effective_members": [
                    {
                        "canonical_id": "factual_sales_report_62_01",
                        "code": "62.01",
                        "name": "62.01",
                        "chart_identity": "ChartOfAccounts_Хозрасчетный",
                        "sort_order": 0,
                    }
                ],
                "resolved_bindings": [
                    {
                        "canonical_id": "factual_sales_report_62_01",
                        "code": "62.01",
                        "name": "62.01",
                        "chart_identity": "ChartOfAccounts_Хозрасчетный",
                        "target_ref_key": "account-62",
                        "binding_source": "binding_table",
                    }
                ],
            },
        },
    )

    summary = _build_pool_factual_workspace_summary(
        quarter_start=date(2026, 1, 1),
        settlements=[],
        edge_balances=[],
        checkpoints=[checkpoint],
        review_queue={"summary": {"pending_total": 0, "attention_required_total": 0}},
    )

    assert summary["scope_fingerprint"] == "scope-fp-001"
    assert summary["scope_contract_version"] == "factual_scope_contract.v2"
    assert summary["gl_account_set_revision_id"] == "gl_account_set_rev_test"
    assert summary["scope_contract"]["selector_key"] == "pool:pool-1:sales_report_v1:2026-01-01"
    assert summary["scope_contract"]["gl_account_set_id"] == gl_account_set_id
    assert summary["scope_contract"]["resolved_bindings"][0]["target_ref_key"] == "account-62"


@pytest.mark.django_db
def test_get_pool_factual_workspace_returns_live_summary_settlements_edges_and_review_queue(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    pool, leaf, edge, database = _create_pool_scope(tenant=default_tenant, suffix="workspace")
    synced_at = datetime.now(dt_timezone.utc)

    receipt_batch = PoolBatch.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.MANUAL,
        period_start=date(2026, 1, 1),
        source_reference="receipt-q1",
    )
    PoolBatchSettlement.objects.create(
        tenant=default_tenant,
        batch=receipt_batch,
        status=PoolBatchSettlementStatus.PARTIALLY_CLOSED,
        incoming_amount=Decimal("120.00"),
        outgoing_amount=Decimal("80.00"),
        open_balance=Decimal("40.00"),
        summary={"note": "receipt"},
        freshness_at=synced_at,
    )

    sale_batch = PoolBatch.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch_kind=PoolBatchKind.SALE,
        source_type=PoolBatchSourceType.MANUAL,
        period_start=date(2026, 1, 1),
        source_reference="sale-q1",
    )
    PoolBatchSettlement.objects.create(
        tenant=default_tenant,
        batch=sale_batch,
        status=PoolBatchSettlementStatus.ATTENTION_REQUIRED,
        incoming_amount=Decimal("50.00"),
        outgoing_amount=Decimal("35.00"),
        open_balance=Decimal("15.00"),
        summary={"note": "sale"},
        freshness_at=synced_at,
    )

    PoolFactualBalanceSnapshot.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch=receipt_batch,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat=Decimal("120.00"),
        amount_without_vat=Decimal("100.00"),
        vat_amount=Decimal("20.00"),
        incoming_amount=Decimal("120.00"),
        outgoing_amount=Decimal("80.00"),
        open_balance=Decimal("40.00"),
        freshness_at=synced_at,
    )
    PoolFactualSyncCheckpoint.objects.create(
        tenant=default_tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        source_checkpoint_token="cp-001",
        last_synced_at=synced_at,
        metadata={
            "freshness_state": "fresh",
            "source_availability": "available",
            "source_availability_detail": "",
            "factual_scope_contract": {
                "contract_version": "factual_scope_contract.v2",
                "selector_key": f"pool:{pool.id}:sales_report_v1:2026-01-01",
                "gl_account_set_id": str(uuid4()),
                "gl_account_set_revision_id": "gl_account_set_rev_workspace",
                "scope_fingerprint": "scope-fp-workspace",
                "effective_members": [
                    {
                        "canonical_id": "factual_sales_report_62_01",
                        "code": "62.01",
                        "name": "62.01",
                        "chart_identity": "ChartOfAccounts_Хозрасчетный",
                        "sort_order": 0,
                    }
                ],
                "resolved_bindings": [
                    {
                        "canonical_id": "factual_sales_report_62_01",
                        "code": "62.01",
                        "name": "62.01",
                        "chart_identity": "ChartOfAccounts_Хозрасчетный",
                        "target_ref_key": "account-62",
                        "binding_source": "binding_table",
                    }
                ],
            },
        },
    )
    PoolFactualReviewItem.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch=receipt_batch,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'workspace-sale')",
    )
    PoolFactualReviewItem.objects.create(
        tenant=default_tenant,
        pool=pool,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.LATE_CORRECTION,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_КорректировкаРеализации(guid'workspace-late')",
    )

    with patch(
        "apps.intercompany_pools.factual_workspace_runtime.ensure_pool_factual_workspace_default_sync",
        return_value=tuple(),
    ):
        response = authenticated_client.get(f"/api/v2/pools/factual/workspace/?pool_id={pool.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["quarter"] == "2026Q1"
    assert payload["summary"]["incoming_amount"] == "170.00"
    assert payload["summary"]["outgoing_amount"] == "115.00"
    assert payload["summary"]["open_balance"] == "55.00"
    assert payload["summary"]["pending_review_total"] == 2
    assert payload["summary"]["attention_required_total"] == 1
    assert payload["summary"]["backlog_total"] == 0
    assert payload["summary"]["freshness_state"] == "fresh"
    assert payload["summary"]["source_availability"] == "available"
    assert payload["summary"]["scope_contract"]["scope_fingerprint"] == "scope-fp-workspace"
    assert payload["summary"]["scope_contract"]["resolved_bindings"][0]["target_ref_key"] == "account-62"
    assert len(payload["settlements"]) == 2
    assert len(payload["edge_balances"]) == 1
    assert payload["review_queue"]["summary"] == {
        "pending_total": 2,
        "unattributed_total": 1,
        "late_correction_total": 1,
        "attention_required_total": 1,
    }


@pytest.mark.django_db
def test_get_pool_factual_workspace_preserves_carry_forward_linkage_in_settlement_summary(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    pool, leaf, edge, _database = _create_pool_scope(tenant=default_tenant, suffix="workspace-carry-forward")
    batch = PoolBatch.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.MANUAL,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        source_reference="receipt-q1-carry-forward",
    )
    settlement = PoolBatchSettlement.objects.create(
        tenant=default_tenant,
        batch=batch,
        status=PoolBatchSettlementStatus.CARRIED_FORWARD,
        incoming_amount=Decimal("120.00"),
        outgoing_amount=Decimal("80.00"),
        open_balance=Decimal("40.00"),
        summary={
            "carry_forward": {
                "source_snapshot_id": str(uuid4()),
                "target_snapshot_id": str(uuid4()),
                "target_quarter_start": "2026-04-01",
                "target_quarter_end": "2026-06-30",
                "applied_at": "2026-04-01T00:05:00+00:00",
            }
        },
        freshness_at=datetime(2026, 3, 31, 20, 15, tzinfo=dt_timezone.utc),
    )
    PoolFactualBalanceSnapshot.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat=Decimal("120.00"),
        amount_without_vat=Decimal("100.00"),
        vat_amount=Decimal("20.00"),
        incoming_amount=Decimal("120.00"),
        outgoing_amount=Decimal("80.00"),
        open_balance=Decimal("40.00"),
    )

    with patch(
        "apps.intercompany_pools.factual_workspace_runtime.ensure_pool_factual_workspace_default_sync",
        return_value=tuple(),
    ):
        response = authenticated_client.get(
            f"/api/v2/pools/factual/workspace/?pool_id={pool.id}&quarter_start=2026-01-01"
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["settlements"]) == 1
    settlement_payload = payload["settlements"][0]["settlement"]
    assert settlement_payload["status"] == PoolBatchSettlementStatus.CARRIED_FORWARD
    assert settlement_payload["incoming_amount"] == "120.00"
    assert settlement_payload["outgoing_amount"] == "80.00"
    assert settlement_payload["open_balance"] == "40.00"
    assert settlement_payload["summary"]["carry_forward"]["target_quarter_start"] == "2026-04-01"
    assert settlement_payload["summary"]["carry_forward"]["target_quarter_end"] == "2026-06-30"
    assert settlement_payload["summary"]["carry_forward"]["source_snapshot_id"] == settlement.summary["carry_forward"]["source_snapshot_id"]
    assert settlement_payload["summary"]["carry_forward"]["target_snapshot_id"] == settlement.summary["carry_forward"]["target_snapshot_id"]


@pytest.mark.django_db
def test_apply_pool_factual_review_action_endpoint_updates_queue(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    user: User,
) -> None:
    pool, leaf, edge, database = _create_pool_scope(tenant=default_tenant, suffix="review-action")
    batch = PoolBatch.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.MANUAL,
        period_start=date(2026, 1, 1),
        source_reference="receipt-q1",
    )
    settlement = PoolBatchSettlement.objects.create(
        tenant=default_tenant,
        batch=batch,
        status=PoolBatchSettlementStatus.ATTENTION_REQUIRED,
        incoming_amount=Decimal("15.00"),
        outgoing_amount=Decimal("0.00"),
        open_balance=Decimal("15.00"),
        summary={},
        freshness_at=datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc),
    )
    PoolFactualBalanceSnapshot.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat=Decimal("15.00"),
        amount_without_vat=Decimal("12.50"),
        vat_amount=Decimal("2.50"),
        incoming_amount=Decimal("15.00"),
        outgoing_amount=Decimal("0.00"),
        open_balance=Decimal("15.00"),
        freshness_at=datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc),
    )
    PoolFactualBalanceSnapshot.objects.create(
        tenant=default_tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat=Decimal("-15.00"),
        amount_without_vat=Decimal("-12.50"),
        vat_amount=Decimal("-2.50"),
        incoming_amount=Decimal("0.00"),
        outgoing_amount=Decimal("15.00"),
        open_balance=Decimal("-15.00"),
        freshness_at=datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc),
    )
    PoolFactualSyncCheckpoint.objects.create(
        tenant=default_tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        source_checkpoint_token="cp-review-action-001",
        last_synced_at=datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc),
        metadata={
            "freshness_state": "fresh",
            "source_availability": "available",
            "source_availability_detail": "",
        },
    )
    review_item = PoolFactualReviewItem.objects.create(
        tenant=default_tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'review-action-sale')",
        delta_payload={
            "amount_with_vat": "15.00",
            "amount_without_vat": "12.50",
            "vat_amount": "2.50",
            "kind": "sale",
        },
        metadata={"raw_organization_id": str(leaf.id)},
    )

    response = authenticated_client.post(
        "/api/v2/pools/factual/review-actions/",
        {
            "review_item_id": str(review_item.id),
            "action": "attribute",
            "batch_id": str(batch.id),
            "edge_id": str(edge.id),
            "organization_id": str(leaf.id),
            "note": "manual attribution from API",
            "metadata": {"resolution_code": "ATTRIBUTED_FROM_WORKSPACE"},
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    review_item.refresh_from_db()

    assert payload["review_item"]["id"] == str(review_item.id)
    assert payload["review_item"]["status"] == "attributed"
    assert payload["review_queue"]["summary"]["pending_total"] == 0
    assert review_item.status == PoolFactualReviewStatus.ATTRIBUTED
    assert review_item.batch_id == batch.id
    assert review_item.resolved_by_id == user.id
    assert review_item.metadata["last_resolution"]["note"] == "manual attribution from API"
    settlement.refresh_from_db()
    assert settlement.status == PoolBatchSettlementStatus.CLOSED
    assert settlement.incoming_amount == Decimal("15.00")
    assert settlement.outgoing_amount == Decimal("15.00")
    assert settlement.open_balance == Decimal("0.00")
    assert settlement.summary["review_queue"]["summary"]["pending_total"] == 0

    workspace_response = authenticated_client.get(f"/api/v2/pools/factual/workspace/?pool_id={pool.id}")

    assert workspace_response.status_code == 200
    workspace_payload = workspace_response.json()
    assert workspace_payload["summary"]["pending_review_total"] == 0
    assert workspace_payload["summary"]["attention_required_total"] == 0
    assert workspace_payload["summary"]["amount_with_vat"] == "0.00"
    assert workspace_payload["summary"]["amount_without_vat"] == "0.00"
    assert workspace_payload["summary"]["vat_amount"] == "0.00"
    assert workspace_payload["summary"]["incoming_amount"] == "15.00"
    assert workspace_payload["summary"]["outgoing_amount"] == "15.00"
    assert workspace_payload["summary"]["open_balance"] == "0.00"
    assert len(workspace_payload["settlements"]) == 1
    assert workspace_payload["settlements"][0]["settlement"]["status"] == PoolBatchSettlementStatus.CLOSED
    assert workspace_payload["settlements"][0]["settlement"]["outgoing_amount"] == "15.00"
    assert workspace_payload["settlements"][0]["settlement"]["open_balance"] == "0.00"
    assert workspace_payload["review_queue"]["summary"]["pending_total"] == 0
    assert len(workspace_payload["edge_balances"]) == 1
    assert workspace_payload["edge_balances"][0]["batch_id"] == str(batch.id)
    assert workspace_payload["edge_balances"][0]["edge_id"] == str(edge.id)
    assert workspace_payload["edge_balances"][0]["outgoing_amount"] == "15.00"
    assert workspace_payload["edge_balances"][0]["open_balance"] == "0.00"


@pytest.mark.django_db
def test_apply_pool_factual_review_action_endpoint_resolve_without_change_keeps_open_balance(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    user: User,
) -> None:
    pool, leaf, edge, database = _create_pool_scope(tenant=default_tenant, suffix="review-resolve")
    batch = PoolBatch.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.MANUAL,
        period_start=date(2026, 1, 1),
        source_reference="receipt-q1-resolve",
    )
    settlement = PoolBatchSettlement.objects.create(
        tenant=default_tenant,
        batch=batch,
        status=PoolBatchSettlementStatus.ATTENTION_REQUIRED,
        incoming_amount=Decimal("15.00"),
        outgoing_amount=Decimal("0.00"),
        open_balance=Decimal("15.00"),
        summary={},
        freshness_at=datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc),
    )
    PoolFactualBalanceSnapshot.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch=batch,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat=Decimal("15.00"),
        amount_without_vat=Decimal("12.50"),
        vat_amount=Decimal("2.50"),
        incoming_amount=Decimal("15.00"),
        outgoing_amount=Decimal("0.00"),
        open_balance=Decimal("15.00"),
        freshness_at=datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc),
    )
    PoolFactualBalanceSnapshot.objects.create(
        tenant=default_tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        amount_with_vat=Decimal("-15.00"),
        amount_without_vat=Decimal("-12.50"),
        vat_amount=Decimal("-2.50"),
        incoming_amount=Decimal("0.00"),
        outgoing_amount=Decimal("15.00"),
        open_balance=Decimal("-15.00"),
        freshness_at=datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc),
    )
    PoolFactualSyncCheckpoint.objects.create(
        tenant=default_tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        source_checkpoint_token="cp-review-resolve-001",
        last_synced_at=datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc),
        metadata={
            "freshness_state": "fresh",
            "source_availability": "available",
            "source_availability_detail": "",
        },
    )
    review_item = PoolFactualReviewItem.objects.create(
        tenant=default_tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'review-resolve-sale')",
        delta_payload={
            "amount_with_vat": "15.00",
            "amount_without_vat": "12.50",
            "vat_amount": "2.50",
            "kind": "sale",
        },
        metadata={"raw_organization_id": str(leaf.id)},
    )

    response = authenticated_client.post(
        "/api/v2/pools/factual/review-actions/",
        {
            "review_item_id": str(review_item.id),
            "action": "resolve_without_change",
            "note": "accepted as external-only correction",
            "metadata": {"resolution_code": "NO_ATTRIBUTION_REQUIRED"},
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    review_item.refresh_from_db()

    assert payload["review_item"]["id"] == str(review_item.id)
    assert payload["review_item"]["status"] == "resolved_without_change"
    assert payload["review_queue"]["summary"]["pending_total"] == 0
    assert review_item.status == PoolFactualReviewStatus.RESOLVED_WITHOUT_CHANGE
    assert review_item.batch_id is None
    assert review_item.edge_id is None
    assert review_item.resolved_by_id == user.id
    assert review_item.metadata["last_resolution"]["note"] == "accepted as external-only correction"
    settlement.refresh_from_db()
    assert settlement.status == PoolBatchSettlementStatus.DISTRIBUTED
    assert settlement.incoming_amount == Decimal("15.00")
    assert settlement.outgoing_amount == Decimal("0.00")
    assert settlement.open_balance == Decimal("15.00")
    assert settlement.summary["review_queue"]["summary"]["pending_total"] == 0

    workspace_response = authenticated_client.get(f"/api/v2/pools/factual/workspace/?pool_id={pool.id}")

    assert workspace_response.status_code == 200
    workspace_payload = workspace_response.json()
    assert workspace_payload["summary"]["pending_review_total"] == 0
    assert workspace_payload["summary"]["attention_required_total"] == 0
    assert workspace_payload["summary"]["incoming_amount"] == "15.00"
    assert workspace_payload["summary"]["outgoing_amount"] == "0.00"
    assert workspace_payload["summary"]["open_balance"] == "15.00"
    assert len(workspace_payload["settlements"]) == 1
    assert workspace_payload["settlements"][0]["settlement"]["status"] == PoolBatchSettlementStatus.DISTRIBUTED
    assert workspace_payload["settlements"][0]["settlement"]["outgoing_amount"] == "0.00"
    assert workspace_payload["settlements"][0]["settlement"]["open_balance"] == "15.00"
    assert workspace_payload["review_queue"]["summary"]["pending_total"] == 0
    assert len(workspace_payload["edge_balances"]) == 2
    edge_balances_by_batch = {
        item["batch_id"]: item for item in workspace_payload["edge_balances"]
    }
    assert edge_balances_by_batch[str(batch.id)]["edge_id"] == str(edge.id)
    assert edge_balances_by_batch[str(batch.id)]["incoming_amount"] == "15.00"
    assert edge_balances_by_batch[str(batch.id)]["outgoing_amount"] == "0.00"
    assert edge_balances_by_batch[str(batch.id)]["open_balance"] == "15.00"
    assert edge_balances_by_batch[None]["batch_id"] is None
    assert edge_balances_by_batch[None]["edge_id"] is None
    assert edge_balances_by_batch[None]["incoming_amount"] == "0.00"
    assert edge_balances_by_batch[None]["outgoing_amount"] == "15.00"
    assert edge_balances_by_batch[None]["open_balance"] == "-15.00"


@pytest.mark.django_db
def test_apply_pool_factual_review_action_endpoint_reconcile_resolves_late_correction(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    user: User,
) -> None:
    pool, leaf, _edge, database = _create_pool_scope(tenant=default_tenant, suffix="review-reconcile")
    PoolFactualSyncCheckpoint.objects.create(
        tenant=default_tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        source_checkpoint_token="cp-review-reconcile-001",
        last_synced_at=datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc),
        metadata={
            "freshness_state": "fresh",
            "source_availability": "available",
            "source_availability_detail": "",
        },
    )
    review_item = PoolFactualReviewItem.objects.create(
        tenant=default_tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.LATE_CORRECTION,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_КорректировкаРеализации(guid'review-reconcile-sale')",
        metadata={"delta_payload": {"amount_with_vat": "15.00"}},
    )

    response = authenticated_client.post(
        "/api/v2/pools/factual/review-actions/",
        {
            "review_item_id": str(review_item.id),
            "action": "reconcile",
            "note": "late correction reconciled from API",
            "metadata": {"resolution_code": "MANUAL_RECONCILE"},
        },
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    review_item.refresh_from_db()

    assert payload["review_item"]["id"] == str(review_item.id)
    assert payload["review_item"]["status"] == "reconciled"
    assert payload["review_queue"]["summary"]["pending_total"] == 0
    assert review_item.status == PoolFactualReviewStatus.RECONCILED
    assert review_item.resolved_by_id == user.id
    assert review_item.metadata["last_resolution"]["note"] == "late correction reconciled from API"
    assert review_item.metadata["last_resolution"]["metadata"]["resolution_code"] == "MANUAL_RECONCILE"

    workspace_response = authenticated_client.get(f"/api/v2/pools/factual/workspace/?pool_id={pool.id}")

    assert workspace_response.status_code == 200
    workspace_payload = workspace_response.json()
    assert workspace_payload["summary"]["pending_review_total"] == 0
    assert workspace_payload["review_queue"]["summary"]["pending_total"] == 0
    assert workspace_payload["review_queue"]["summary"]["late_correction_total"] == 0


@pytest.mark.django_db
def test_get_pool_factual_workspace_bootstraps_default_sync_when_checkpoint_missing(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    pool, leaf, _edge, database = _create_pool_scope(tenant=default_tenant, suffix="workspace-bootstrap")
    factual_scope = _build_resolved_factual_scope(
        pool=pool,
        organization_ids=(str(leaf.id),),
        quarter_start=date(2026, 4, 1),
    )

    with patch(
        "apps.intercompany_pools.factual_workspace_runtime.start_pool_factual_sync_workflow"
    ) as start_workflow, patch(
        "apps.intercompany_pools.factual_workspace_runtime.resolve_pool_factual_sync_scope_for_database",
        return_value=factual_scope,
    ):
        def _fake_start(**kwargs):
            checkpoint = kwargs["checkpoint"]
            checkpoint.workflow_status = "running"
            checkpoint.save(update_fields=["workflow_status", "updated_at"])
            return PoolFactualSyncWorkflowStartResult(
                checkpoint=checkpoint,
                execution_id="11111111-1111-1111-1111-111111111111",
                operation_id="22222222-2222-2222-2222-222222222222",
                enqueue_success=True,
                enqueue_status="running",
                enqueue_error=None,
                created_execution=True,
            )

        start_workflow.side_effect = _fake_start

        response = authenticated_client.get(
            f"/api/v2/pools/factual/workspace/?pool_id={pool.id}&quarter_start=2026-04-01"
        )

    assert response.status_code == 200
    checkpoint = PoolFactualSyncCheckpoint.objects.get(
        tenant=default_tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
    )
    assert checkpoint.workflow_status == "running"
    start_workflow.assert_called_once()
    _, kwargs = start_workflow.call_args
    assert str(leaf.id) in kwargs["organization_ids"]
    assert kwargs["account_codes"] == ("62.01", "90.01")
    assert kwargs["movement_kinds"] == ("credit", "debit")
    payload = response.json()
    assert payload["summary"]["checkpoint_total"] == 1


@pytest.mark.django_db
def test_refresh_pool_factual_workspace_force_syncs_current_context_and_returns_running_state(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    pool, leaf, _edge, database = _create_pool_scope(tenant=default_tenant, suffix="workspace-refresh")
    factual_scope = _build_resolved_factual_scope(
        pool=pool,
        organization_ids=(str(leaf.id),),
        quarter_start=date(2026, 4, 1),
    )
    PoolFactualSyncCheckpoint.objects.create(
        tenant=default_tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 4, 1),
        quarter_end=date(2026, 6, 30),
        last_synced_at=datetime(2026, 4, 14, 9, 59, tzinfo=dt_timezone.utc),
        workflow_status="completed",
        metadata={
            "freshness_state": "fresh",
            "freshness_target_seconds": 600,
        },
    )

    with patch(
        "apps.intercompany_pools.factual_workspace_runtime.start_pool_factual_sync_workflow"
    ) as start_workflow, patch(
        "apps.intercompany_pools.factual_workspace_runtime.resolve_pool_factual_sync_scope_for_database",
        return_value=factual_scope,
    ):
        def _fake_start(**kwargs):
            checkpoint = kwargs["checkpoint"]
            checkpoint.workflow_status = "running"
            checkpoint.workflow_execution_id = UUID("11111111-1111-1111-1111-111111111111")
            checkpoint.operation_id = UUID("22222222-2222-2222-2222-222222222222")
            checkpoint.save(
                update_fields=[
                    "workflow_status",
                    "workflow_execution_id",
                    "operation_id",
                    "updated_at",
                ]
            )
            return PoolFactualSyncWorkflowStartResult(
                checkpoint=checkpoint,
                execution_id="11111111-1111-1111-1111-111111111111",
                operation_id="22222222-2222-2222-2222-222222222222",
                enqueue_success=True,
                enqueue_status="running",
                enqueue_error=None,
                created_execution=True,
            )

        start_workflow.side_effect = _fake_start

        response = authenticated_client.post(
            "/api/v2/pools/factual/refresh/",
            {
                "pool_id": str(pool.id),
                "quarter_start": "2026-04-01",
            },
            format="json",
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["activity"] == "active"
    assert payload["polling_tier"] == "active"
    assert payload["poll_interval_seconds"] == 120
    assert payload["freshness_target_seconds"] == 120
    assert payload["checkpoint_total"] == 1
    assert payload["checkpoints_running"] == 1
    assert payload["checkpoints"][0]["workflow_status"] == "running"
    assert payload["checkpoints"][0]["activity"] == "active"
    assert payload["checkpoints"][0]["polling_tier"] == "active"
    start_workflow.assert_called_once()
    assert start_workflow.call_args.kwargs["activity"] == "active"


@pytest.mark.django_db
def test_refresh_pool_factual_workspace_does_not_duplicate_running_checkpoint(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    pool, leaf, _edge, database = _create_pool_scope(tenant=default_tenant, suffix="workspace-refresh-running")
    factual_scope = _build_resolved_factual_scope(
        pool=pool,
        organization_ids=(str(leaf.id),),
        quarter_start=date(2026, 4, 1),
    )
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=default_tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 4, 1),
        quarter_end=date(2026, 6, 30),
        workflow_status="running",
        workflow_execution_id=UUID("11111111-1111-1111-1111-111111111111"),
        operation_id=UUID("22222222-2222-2222-2222-222222222222"),
        metadata={
            "activity": "active",
            "polling_tier": "active",
            "poll_interval_seconds": 120,
            "freshness_target_seconds": 120,
            "freshness_state": "stale",
        },
    )

    with patch(
        "apps.intercompany_pools.factual_workspace_runtime.start_pool_factual_sync_workflow"
    ) as start_workflow, patch(
        "apps.intercompany_pools.factual_workspace_runtime.resolve_pool_factual_sync_scope_for_database",
        return_value=factual_scope,
    ):
        response = authenticated_client.post(
            "/api/v2/pools/factual/refresh/",
            {
                "pool_id": str(pool.id),
                "quarter_start": "2026-04-01",
            },
            format="json",
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["checkpoint_total"] == 1
    assert payload["checkpoints_running"] == 1
    assert payload["checkpoints"][0]["checkpoint_id"] == str(checkpoint.id)
    start_workflow.assert_not_called()


@pytest.mark.django_db
def test_get_pool_factual_workspace_surfaces_read_backlog_in_summary(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    pool, leaf, _edge, database = _create_pool_scope(tenant=default_tenant, suffix="workspace-backlog")
    stale_synced_at = datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc)
    PoolFactualSyncCheckpoint.objects.create(
        tenant=default_tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        source_checkpoint_token="cp-backlog-001",
        last_synced_at=stale_synced_at,
        metadata={
            "freshness_state": "stale",
            "source_availability": "available",
            "source_availability_detail": "",
            "freshness_target_seconds": 120,
        },
    )
    factual_scope = _build_resolved_factual_scope(pool=pool, organization_ids=(str(leaf.id),))

    with patch(
        "apps.intercompany_pools.factual_workspace_runtime.start_pool_factual_sync_workflow"
    ) as start_workflow, patch(
        "apps.intercompany_pools.factual_workspace_runtime.resolve_pool_factual_sync_scope_for_database",
        return_value=factual_scope,
    ):
        def _fake_start(**kwargs):
            checkpoint = kwargs["checkpoint"]
            checkpoint.workflow_status = "running"
            checkpoint.save(update_fields=["workflow_status", "updated_at"])
            return PoolFactualSyncWorkflowStartResult(
                checkpoint=checkpoint,
                execution_id="33333333-3333-3333-3333-333333333333",
                operation_id="44444444-4444-4444-4444-444444444444",
                enqueue_success=True,
                enqueue_status="running",
                enqueue_error=None,
                created_execution=True,
            )

        start_workflow.side_effect = _fake_start

        response = authenticated_client.get(f"/api/v2/pools/factual/workspace/?pool_id={pool.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["checkpoint_total"] == 1
    assert payload["summary"]["backlog_total"] == 1
    assert payload["summary"]["freshness_state"] == "stale"
    assert payload["summary"]["source_availability"] == "available"
