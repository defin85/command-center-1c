from __future__ import annotations

from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.master_data_dedupe import (
    MASTER_DATA_DEDUPE_REVIEW_REQUIRED,
    POOL_MASTER_DATA_DEDUPE_ACTION_MARK_DISTINCT,
    MasterDataDedupeReviewRequiredError,
    apply_pool_master_data_dedupe_review_action,
    get_pool_master_data_dedupe_review_item,
    ingest_pool_master_data_source_record,
    require_pool_master_data_dedupe_resolved,
)
from apps.intercompany_pools.models import (
    PoolMasterContract,
    PoolMasterDataDedupeCluster,
    PoolMasterDataDedupeClusterStatus,
    PoolMasterDataDedupeReviewItem,
    PoolMasterDataDedupeReviewStatus,
    PoolMasterDataEntityType,
    PoolMasterDataSourceRecord,
    PoolMasterParty,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"dedupe-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_party_ingest_reuses_single_canonical_cluster_across_infobases() -> None:
    tenant = Tenant.objects.create(slug=f"dedupe-party-{uuid4().hex[:6]}", name="Dedupe Party")
    db_a = _create_database(tenant=tenant, suffix="a")
    db_b = _create_database(tenant=tenant, suffix="b")

    first = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.PARTY,
        source_database=db_a,
        source_ref="Ref_A",
        source_canonical_id="party-a",
        canonical_payload={
            "name": "ООО Ромашка",
            "full_name": "ООО Ромашка",
            "inn": "7701001001",
            "kpp": "770101001",
            "is_our_organization": False,
            "is_counterparty": True,
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-a",
        origin_event_id="evt-party-a",
    )
    second = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.PARTY,
        source_database=db_b,
        source_ref="Ref_B",
        source_canonical_id="party-b",
        canonical_payload={
            "name": "ООО Ромашка",
            "full_name": "ООО Ромашка",
            "inn": "7701001001",
            "kpp": "770101001",
            "is_our_organization": False,
            "is_counterparty": True,
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-b",
        origin_event_id="evt-party-b",
    )

    assert first.blocked is False
    assert second.blocked is False
    assert second.canonical_id == first.canonical_id == "party-a"
    assert first.cluster.id == second.cluster.id
    assert PoolMasterParty.objects.filter(tenant=tenant).count() == 1
    assert PoolMasterDataSourceRecord.objects.filter(cluster_id=first.cluster.id).count() == 2


@pytest.mark.django_db
def test_contract_ingest_creates_review_item_for_ambiguous_match() -> None:
    tenant = Tenant.objects.create(slug=f"dedupe-contract-{uuid4().hex[:6]}", name="Dedupe Contract")
    db_a = _create_database(tenant=tenant, suffix="contract-a")
    db_b = _create_database(tenant=tenant, suffix="contract-b")
    owner = PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-owner",
        name="Owner",
        is_counterparty=True,
        is_our_organization=False,
    )

    first = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.CONTRACT,
        source_database=db_a,
        source_ref="Contract_A",
        source_canonical_id="contract-a",
        canonical_payload={
            "name": "Основной",
            "owner_counterparty_canonical_id": str(owner.canonical_id),
            "number": "01",
            "date": "2026-01-01",
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-a",
        origin_event_id="evt-contract-a",
    )
    second = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.CONTRACT,
        source_database=db_b,
        source_ref="Contract_B",
        source_canonical_id="contract-b",
        canonical_payload={
            "name": "Основной договор",
            "owner_counterparty_canonical_id": str(owner.canonical_id),
            "number": "01",
            "date": "2026-01-01",
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-b",
        origin_event_id="evt-contract-b",
    )

    assert first.blocked is False
    assert second.blocked is True
    assert second.reason_code == MASTER_DATA_DEDUPE_REVIEW_REQUIRED
    cluster = PoolMasterDataDedupeCluster.objects.get(id=first.cluster.id)
    assert cluster.status == PoolMasterDataDedupeClusterStatus.PENDING_REVIEW
    review_item = PoolMasterDataDedupeReviewItem.objects.get(cluster=cluster)
    assert review_item.status == PoolMasterDataDedupeReviewStatus.PENDING
    assert "name" in review_item.conflicting_fields
    assert PoolMasterContract.objects.filter(tenant=tenant).count() == 1


@pytest.mark.django_db
def test_require_dedupe_resolved_raises_for_pending_review_cluster() -> None:
    tenant = Tenant.objects.create(slug=f"dedupe-gate-{uuid4().hex[:6]}", name="Dedupe Gate")
    db_a = _create_database(tenant=tenant, suffix="gate-a")
    db_b = _create_database(tenant=tenant, suffix="gate-b")
    first = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
        source_database=db_a,
        source_ref="gl-a",
        source_canonical_id="gl-1001-a",
        canonical_payload={
            "chart_identity": "ChartOfAccounts_Main",
            "code": "10.01",
            "name": "Материалы",
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-a",
        origin_event_id="evt-gl-a",
    )
    second = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
        source_database=db_b,
        source_ref="gl-b",
        source_canonical_id="gl-1001-b",
        canonical_payload={
            "chart_identity": "ChartOfAccounts_Main",
            "code": "10.01",
            "name": "Материалы Основные",
            "config_name": "Accounting Enterprise",
            "config_version": "3.0.1",
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-b",
        origin_event_id="evt-gl-b",
    )

    assert first.blocked is False
    assert second.blocked is True
    with pytest.raises(MasterDataDedupeReviewRequiredError) as exc_info:
        require_pool_master_data_dedupe_resolved(
            tenant_id=str(tenant.id),
            entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
            canonical_id=str(first.canonical_id),
        )

    assert exc_info.value.code == MASTER_DATA_DEDUPE_REVIEW_REQUIRED
    assert exc_info.value.review_item_id


@pytest.mark.django_db
def test_mark_distinct_splits_pending_review_cluster_into_manual_clusters() -> None:
    tenant = Tenant.objects.create(slug=f"dedupe-distinct-{uuid4().hex[:6]}", name="Dedupe Distinct")
    db_a = _create_database(tenant=tenant, suffix="distinct-a")
    db_b = _create_database(tenant=tenant, suffix="distinct-b")

    ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.PARTY,
        source_database=db_a,
        source_ref="party-a",
        source_canonical_id="party-a",
        canonical_payload={
            "name": "ООО Спорная",
            "full_name": "ООО Спорная",
            "inn": "7702002002",
            "kpp": "770201001",
            "is_counterparty": True,
            "is_our_organization": False,
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-a",
        origin_event_id="evt-party-a",
    )
    blocked = ingest_pool_master_data_source_record(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.PARTY,
        source_database=db_b,
        source_ref="party-b",
        source_canonical_id="party-b",
        canonical_payload={
            "name": "ООО Спорная Компания",
            "full_name": "ООО Спорная Компания",
            "inn": "7702002002",
            "kpp": "770201001",
            "is_counterparty": True,
            "is_our_organization": False,
            "metadata": {},
        },
        origin_kind="bootstrap_import",
        origin_ref="job-b",
        origin_event_id="evt-party-b",
    )

    review_item = get_pool_master_data_dedupe_review_item(
        tenant_id=str(tenant.id),
        review_item_id=str(blocked.review_item.id),
    )
    resolved = apply_pool_master_data_dedupe_review_action(
        tenant_id=str(tenant.id),
        review_item_id=str(review_item.id),
        action=POOL_MASTER_DATA_DEDUPE_ACTION_MARK_DISTINCT,
        actor_id=None,
        note="distinct businesses",
    )

    resolved.refresh_from_db()
    assert resolved.status == PoolMasterDataDedupeReviewStatus.RESOLVED_MANUAL
    assert PoolMasterDataSourceRecord.objects.filter(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.PARTY,
    ).count() == 2
    assert PoolMasterDataDedupeCluster.objects.filter(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.PARTY,
        status=PoolMasterDataDedupeClusterStatus.RESOLVED_MANUAL,
    ).count() == 2
    assert PoolMasterParty.objects.filter(tenant=tenant).count() == 2
