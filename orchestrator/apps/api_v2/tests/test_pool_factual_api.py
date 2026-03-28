from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

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


@pytest.mark.django_db
def test_get_pool_factual_workspace_returns_live_summary_settlements_edges_and_review_queue(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    pool, leaf, edge, database = _create_pool_scope(tenant=default_tenant, suffix="workspace")
    synced_at = datetime(2026, 3, 27, 10, 0, tzinfo=dt_timezone.utc)

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

    response = authenticated_client.get(f"/api/v2/pools/factual/workspace/?pool_id={pool.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["quarter"] == "2026Q1"
    assert payload["summary"]["incoming_amount"] == "170.00"
    assert payload["summary"]["outgoing_amount"] == "115.00"
    assert payload["summary"]["open_balance"] == "55.00"
    assert payload["summary"]["pending_review_total"] == 2
    assert payload["summary"]["attention_required_total"] == 1
    assert payload["summary"]["freshness_state"] == "fresh"
    assert payload["summary"]["source_availability"] == "available"
    assert len(payload["settlements"]) == 2
    assert len(payload["edge_balances"]) == 1
    assert payload["review_queue"]["summary"] == {
        "pending_total": 2,
        "unattributed_total": 1,
        "late_correction_total": 1,
        "attention_required_total": 1,
    }


@pytest.mark.django_db
def test_apply_pool_factual_review_action_endpoint_updates_queue(
    authenticated_client: APIClient,
    default_tenant: Tenant,
    user: User,
) -> None:
    pool, leaf, edge, _ = _create_pool_scope(tenant=default_tenant, suffix="review-action")
    batch = PoolBatch.objects.create(
        tenant=default_tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.MANUAL,
        period_start=date(2026, 1, 1),
        source_reference="receipt-q1",
    )
    review_item = PoolFactualReviewItem.objects.create(
        tenant=default_tenant,
        pool=pool,
        organization=leaf,
        edge=edge,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'review-action-sale')",
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


@pytest.mark.django_db
def test_get_pool_factual_workspace_bootstraps_default_sync_when_checkpoint_missing(
    authenticated_client: APIClient,
    default_tenant: Tenant,
) -> None:
    pool, leaf, _edge, database = _create_pool_scope(tenant=default_tenant, suffix="workspace-bootstrap")

    with patch(
        "apps.intercompany_pools.factual_workspace_runtime.start_pool_factual_sync_workflow"
    ) as start_workflow:
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

        response = authenticated_client.get(f"/api/v2/pools/factual/workspace/?pool_id={pool.id}")

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
