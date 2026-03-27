from __future__ import annotations

from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model

from apps.databases.models import Database
from apps.intercompany_pools.factual_observability import (
    POOL_FACTUAL_ALERT_FRESHNESS_LAG,
    POOL_FACTUAL_ALERT_LATE_CORRECTION_QUEUE,
    POOL_FACTUAL_ALERT_READ_BACKLOG,
    POOL_FACTUAL_ALERT_UNATTRIBUTED_VOLUME,
    record_pool_factual_rollout_telemetry,
)
from apps.intercompany_pools.factual_failure_isolation import (
    POOL_FACTUAL_FAILURE_ISOLATION_CONTRACT,
    POOL_FACTUAL_OPERATOR_DECISION_PAUSE_INTAKE,
    build_pool_factual_failure_isolation_snapshot,
)
from apps.intercompany_pools.factual_review_queue import (
    FACTUAL_REVIEW_ACTION_ATTRIBUTE,
    apply_pool_factual_review_action,
)
from apps.intercompany_pools.factual_sync_runtime import (
    FactualSyncSourceState,
    build_factual_sales_report_sync_scope,
    mark_factual_sync_checkpoint_success,
)
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSourceType,
    PoolEdgeVersion,
    PoolFactualLane,
    PoolFactualReviewItem,
    PoolFactualReviewReason,
    PoolFactualReviewStatus,
    PoolFactualSyncCheckpoint,
    PoolNodeVersion,
)
from apps.tenancy.models import Tenant


User = get_user_model()


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-telemetry-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-telemetry-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_pool_scope(*, tenant: Tenant, suffix: str) -> tuple[OrganizationPool, Organization, Organization, Database]:
    database = _create_database(tenant=tenant, suffix=suffix)
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-telemetry-pool-{suffix}",
        name=f"Factual Telemetry Pool {suffix}",
    )
    root = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Root {suffix}",
        inn=f"77100000{suffix[:4].zfill(4)}",
    )
    leaf = Organization.objects.create(
        tenant=tenant,
        name=f"Leaf {suffix}",
        inn=f"78100000{suffix[:4].zfill(4)}",
    )
    return pool, root, leaf, database


def _create_edge(*, pool: OrganizationPool, root: Organization, leaf: Organization) -> PoolEdgeVersion:
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
        is_root=False,
    )
    return PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=leaf_node,
        effective_from=date(2026, 1, 1),
        weight="1.0",
    )


@pytest.mark.django_db
def test_record_pool_factual_rollout_telemetry_aggregates_metrics_and_actionable_alerts() -> None:
    tenant = Tenant.objects.create(slug=f"factual-telemetry-{uuid4().hex[:6]}", name="Factual Telemetry")
    pool, root, leaf, database = _create_pool_scope(tenant=tenant, suffix="001")
    now = datetime(2026, 3, 27, 12, 0, tzinfo=dt_timezone.utc)

    PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        last_synced_at=now - timedelta(seconds=30),
        metadata={
            "freshness_target_seconds": 120,
            "freshness_state": "fresh",
            "freshness_at": (now - timedelta(seconds=30)).isoformat(),
            "source_availability": "available",
        },
    )
    PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        last_synced_at=now - timedelta(minutes=15),
        metadata={
            "freshness_target_seconds": 120,
            "freshness_state": "stale",
            "freshness_at": (now - timedelta(minutes=15)).isoformat(),
            "source_availability": "blocked_external_sessions",
        },
    )

    PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'11111111-1111-1111-1111-111111111111')",
        delta_payload={"amount_with_vat": "12.50"},
    )
    PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.LATE_CORRECTION,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_КорректировкаРеализации(guid'22222222-2222-2222-2222-222222222222')",
        delta_payload={"amount_with_vat": "7.25"},
    )

    with (
        patch("apps.intercompany_pools.factual_observability.set_pool_factual_read_metrics") as set_read_metrics,
        patch("apps.intercompany_pools.factual_observability.set_pool_factual_review_metrics") as set_review_metrics,
        patch("apps.intercompany_pools.factual_observability.set_pool_factual_actionable_alerts") as set_alerts,
    ):
        snapshot = record_pool_factual_rollout_telemetry(now=now)

    assert snapshot["read_summary"]["checkpoint_total"] == 2
    assert snapshot["read_summary"]["backlog_total"] == 1
    assert snapshot["read_summary"]["source_state_totals"] == {
        "available": 1,
        "blocked_external_sessions": 1,
    }
    assert snapshot["review_summary"]["pending_totals"] == {
        "unattributed": 1,
        "late_correction": 1,
    }
    assert snapshot["review_summary"]["pending_amounts_with_vat"] == {
        "unattributed": 12.5,
        "late_correction": 7.25,
    }
    assert snapshot["review_summary"]["attention_required_totals"] == {
        "late_correction": 1,
    }

    alert_codes = {alert["code"]: alert for alert in snapshot["alerts"]}
    assert set(alert_codes) == {
        POOL_FACTUAL_ALERT_FRESHNESS_LAG,
        POOL_FACTUAL_ALERT_READ_BACKLOG,
        POOL_FACTUAL_ALERT_UNATTRIBUTED_VOLUME,
        POOL_FACTUAL_ALERT_LATE_CORRECTION_QUEUE,
    }
    assert alert_codes[POOL_FACTUAL_ALERT_FRESHNESS_LAG]["severity"] == "critical"
    assert alert_codes[POOL_FACTUAL_ALERT_READ_BACKLOG]["severity"] == "warning"
    assert alert_codes[POOL_FACTUAL_ALERT_UNATTRIBUTED_VOLUME]["severity"] == "warning"
    assert alert_codes[POOL_FACTUAL_ALERT_LATE_CORRECTION_QUEUE]["severity"] == "critical"
    assert snapshot["failure_isolation"]["contract_version"] == POOL_FACTUAL_FAILURE_ISOLATION_CONTRACT
    assert snapshot["failure_isolation"]["intake"]["state"] == "available"
    assert snapshot["failure_isolation"]["intake"]["auto_disable_allowed"] is False
    assert snapshot["failure_isolation"]["read_projection"]["state"] == "degraded"
    assert snapshot["failure_isolation"]["reconcile_review"]["state"] == "degraded"

    set_read_metrics.assert_called_once()
    assert set_read_metrics.call_args.kwargs["backlog_total"] == 1
    set_review_metrics.assert_called_once()
    assert set_review_metrics.call_args.kwargs["pending_totals"]["unattributed"] == 1
    set_alerts.assert_called_once_with(alerts=snapshot["alerts"])


def test_build_pool_factual_failure_isolation_snapshot_allows_only_explicit_operator_pause() -> None:
    snapshot = build_pool_factual_failure_isolation_snapshot(
        alerts=[
            {"code": POOL_FACTUAL_ALERT_FRESHNESS_LAG, "severity": "critical"},
            {"code": POOL_FACTUAL_ALERT_LATE_CORRECTION_QUEUE, "severity": "critical"},
        ],
        operator_decision=POOL_FACTUAL_OPERATOR_DECISION_PAUSE_INTAKE,
    )

    assert snapshot["contract_version"] == POOL_FACTUAL_FAILURE_ISOLATION_CONTRACT
    assert snapshot["operator_decision"] == POOL_FACTUAL_OPERATOR_DECISION_PAUSE_INTAKE
    assert snapshot["intake"]["state"] == "paused_by_operator"
    assert snapshot["intake"]["auto_disable_allowed"] is False
    assert snapshot["read_projection"]["signals"] == [POOL_FACTUAL_ALERT_FRESHNESS_LAG]
    assert snapshot["reconcile_review"]["signals"] == [POOL_FACTUAL_ALERT_LATE_CORRECTION_QUEUE]


@pytest.mark.django_db
def test_mark_factual_sync_checkpoint_success_refreshes_rollout_telemetry() -> None:
    tenant = Tenant.objects.create(slug=f"factual-telemetry-sync-{uuid4().hex[:6]}", name="Factual Telemetry Sync")
    pool, root, _, database = _create_pool_scope(tenant=tenant, suffix="002")
    checkpoint = PoolFactualSyncCheckpoint.objects.create(
        tenant=tenant,
        pool=pool,
        database=database,
        lane=PoolFactualLane.READ,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
    )
    synced_at = datetime(2026, 3, 27, 13, 0, tzinfo=dt_timezone.utc)
    scope = build_factual_sales_report_sync_scope(
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        organization_ids=[str(root.id)],
        account_codes=["90.01"],
        movement_kinds=["debit"],
    )
    source_state = FactualSyncSourceState(state="available", code="", detail="")

    with patch("apps.intercompany_pools.factual_observability.record_pool_factual_rollout_telemetry") as record_metrics:
        mark_factual_sync_checkpoint_success(
            checkpoint=checkpoint,
            scope=scope,
            source_state=source_state,
            source_checkpoint_token="cp-telemetry",
            synced_at=synced_at,
        )

    record_metrics.assert_called_once_with(now=synced_at)


@pytest.mark.django_db
def test_apply_pool_factual_review_action_refreshes_rollout_telemetry() -> None:
    tenant = Tenant.objects.create(slug=f"factual-telemetry-review-{uuid4().hex[:6]}", name="Factual Telemetry Review")
    pool, root, leaf, _ = _create_pool_scope(tenant=tenant, suffix="003")
    edge = _create_edge(pool=pool, root=root, leaf=leaf)
    batch = PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        start_organization=root,
        source_reference="receipt-telemetry-003",
        raw_payload_ref="files/receipt-telemetry-003.xlsx",
    )
    actor = User.objects.create_user(username=f"factual-telemetry-review-{uuid4().hex[:6]}", password="pass")
    review_item = PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        status=PoolFactualReviewStatus.PENDING,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'33333333-3333-3333-3333-333333333333')",
    )
    resolved_at = datetime(2026, 3, 27, 14, 30, tzinfo=dt_timezone.utc)

    with patch("apps.intercompany_pools.factual_observability.record_pool_factual_rollout_telemetry") as record_metrics:
        apply_pool_factual_review_action(
            review_item_id=str(review_item.id),
            tenant_id=str(tenant.id),
            actor_id=str(actor.id),
            action=FACTUAL_REVIEW_ACTION_ATTRIBUTE,
            batch_id=str(batch.id),
            edge_id=str(edge.id),
            organization_id=str(leaf.id),
            now=resolved_at,
        )

    record_metrics.assert_called_once_with(now=resolved_at)
