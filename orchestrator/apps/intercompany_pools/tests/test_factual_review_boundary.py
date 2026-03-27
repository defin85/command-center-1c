from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model

from apps.databases.models import Database
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSourceType,
    PoolEdgeVersion,
    PoolFactualReviewItem,
    PoolFactualReviewReason,
    PoolNodeVersion,
    PoolRun,
    PoolRunDirection,
)
from apps.tenancy.models import Tenant


User = get_user_model()


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"factual-review-boundary-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/factual-review-boundary-{suffix}.odata",
        username="admin",
        password="secret",
    )


def _create_pool_scope(*, tenant: Tenant, suffix: str) -> tuple[OrganizationPool, Organization, Organization]:
    database = _create_database(tenant=tenant, suffix=suffix)
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"factual-review-boundary-pool-{suffix}",
        name=f"Factual Review Boundary Pool {suffix}",
    )
    root = Organization.objects.create(
        tenant=tenant,
        database=database,
        name=f"Root {suffix}",
        inn=f"77010000{suffix[:4].zfill(4)}",
    )
    leaf = Organization.objects.create(
        tenant=tenant,
        name=f"Leaf {suffix}",
        inn=f"78010000{suffix[:4].zfill(4)}",
    )
    return pool, root, leaf


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


def test_build_factual_review_execution_context_keeps_review_lane_isolated() -> None:
    from apps.intercompany_pools.factual_review_boundary import (
        FACTUAL_REVIEW_PERSISTENCE_TARGETS,
        build_factual_review_execution_context,
    )

    context = build_factual_review_execution_context(
        tenant_id=str(uuid4()),
        pool_id=str(uuid4()),
        actions=["enqueue_manual_review", "attribute", "resolve_without_change"],
        persistence_targets=FACTUAL_REVIEW_PERSISTENCE_TARGETS,
    )

    assert context["subsystem"] == "reconcile_review"
    assert context["lane"] == "review"
    assert context["actions"] == [
        "attribute",
        "enqueue_manual_review",
        "resolve_without_change",
    ]
    assert context["persistence_targets"] == ["pool_factual_review_items"]
    assert context["protected_contracts"] == ["batch_intake_contract", "pool_run_status"]


def test_validate_factual_review_execution_context_rejects_intake_and_run_actions() -> None:
    from apps.intercompany_pools.factual_review_boundary import (
        FACTUAL_REVIEW_BOUNDARY_INVALID,
        validate_factual_review_execution_context,
    )

    with pytest.raises(ValueError, match=FACTUAL_REVIEW_BOUNDARY_INVALID):
        validate_factual_review_execution_context(
            input_context={
                "contract_version": "pool_factual_review_boundary.v1",
                "tenant_id": str(uuid4()),
                "pool_id": str(uuid4()),
                "subsystem": "reconcile_review",
                "lane": "review",
                "actions": ["attribute", "create_run", "kickoff_receipt_run"],
                "persistence_targets": ["pool_factual_review_items"],
                "protected_contracts": ["pool_run_status", "batch_intake_contract"],
            }
        )


@pytest.mark.django_db
def test_review_action_can_link_batch_without_mutating_run_status_or_batch_intake_contract() -> None:
    from apps.intercompany_pools.factual_review_queue import (
        FACTUAL_REVIEW_ACTION_ATTRIBUTE,
        apply_pool_factual_review_action,
    )

    tenant = Tenant.objects.create(slug=f"factual-review-isolation-{uuid4().hex[:6]}", name="Factual Review Isolation")
    pool, root, leaf = _create_pool_scope(tenant=tenant, suffix="001")
    edge = _create_edge(pool=pool, root=root, leaf=leaf)
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.TOP_DOWN,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
    )
    batch = PoolBatch.objects.create(
        tenant=tenant,
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        start_organization=root,
        run=run,
        source_reference="receipt-boundary-001",
        raw_payload_ref="files/receipt-boundary-001.xlsx",
    )
    review_item = PoolFactualReviewItem.objects.create(
        tenant=tenant,
        pool=pool,
        organization=leaf,
        quarter_start=date(2026, 1, 1),
        quarter_end=date(2026, 3, 31),
        reason=PoolFactualReviewReason.UNATTRIBUTED,
        source_document_ref="Document_РеализацияТоваровУслуг(guid'55555555-5555-5555-5555-555555555555')",
    )
    actor = User.objects.create_user(username=f"factual-review-isolation-{uuid4().hex[:6]}", password="pass")

    apply_pool_factual_review_action(
        review_item_id=str(review_item.id),
        tenant_id=str(tenant.id),
        actor_id=str(actor.id),
        action=FACTUAL_REVIEW_ACTION_ATTRIBUTE,
        batch_id=str(batch.id),
        edge_id=str(edge.id),
        organization_id=str(leaf.id),
        note="link unattributed sale to existing batch without changing execution state",
    )

    persisted_run = PoolRun.objects.values(
        "status",
        "runtime_projection_snapshot",
        "publication_summary",
    ).get(id=run.id)
    persisted_batch = PoolBatch.objects.values(
        "source_type",
        "source_reference",
        "raw_payload_ref",
        "run_id",
    ).get(id=batch.id)

    assert persisted_run["status"] == PoolRun.STATUS_DRAFT
    assert persisted_run["runtime_projection_snapshot"] == {}
    assert persisted_run["publication_summary"] == {}
    assert persisted_batch["source_type"] == PoolBatchSourceType.SCHEMA_TEMPLATE_UPLOAD
    assert persisted_batch["source_reference"] == "receipt-boundary-001"
    assert persisted_batch["raw_payload_ref"] == "files/receipt-boundary-001.xlsx"
    assert str(persisted_batch["run_id"]) == str(run.id)
