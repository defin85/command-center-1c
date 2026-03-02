from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.databases.models import Database
from apps.intercompany_pools.master_data_sync_policy import (
    MasterDataSyncPolicyMissingError,
    require_pool_master_data_sync_policy,
    resolve_pool_master_data_sync_policy,
)
from apps.intercompany_pools.models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncPolicy,
    PoolMasterDataSyncScope,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"sync-policy-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_sync_scope_rejects_cross_tenant_database() -> None:
    tenant = Tenant.objects.create(slug="sync-scope-tenant-a", name="Sync Scope Tenant A")
    foreign_tenant = Tenant.objects.create(slug="sync-scope-tenant-b", name="Sync Scope Tenant B")
    foreign_database = _create_database(tenant=foreign_tenant, suffix="foreign")

    with pytest.raises(ValidationError):
        PoolMasterDataSyncScope.objects.create(
            tenant=tenant,
            entity_type=PoolMasterDataEntityType.ITEM,
            database=foreign_database,
            policy=PoolMasterDataSyncPolicy.CC_MASTER,
        )


@pytest.mark.django_db
def test_sync_scope_has_single_tenant_default_per_entity() -> None:
    tenant = Tenant.objects.create(slug="sync-scope-default", name="Sync Scope Default")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        database=None,
        policy=PoolMasterDataSyncPolicy.CC_MASTER,
    )

    with pytest.raises(ValidationError):
        PoolMasterDataSyncScope.objects.create(
            tenant=tenant,
            entity_type=PoolMasterDataEntityType.ITEM,
            database=None,
            policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
        )


@pytest.mark.django_db
def test_sync_scope_has_single_database_override_per_entity() -> None:
    tenant = Tenant.objects.create(slug="sync-scope-db", name="Sync Scope DB")
    database = _create_database(tenant=tenant, suffix="single")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.PARTY,
        database=database,
        policy=PoolMasterDataSyncPolicy.IB_MASTER,
    )

    with pytest.raises(ValidationError):
        PoolMasterDataSyncScope.objects.create(
            tenant=tenant,
            entity_type=PoolMasterDataEntityType.PARTY,
            database=database,
            policy=PoolMasterDataSyncPolicy.CC_MASTER,
        )


@pytest.mark.django_db
def test_resolver_prefers_database_scope_over_tenant_default() -> None:
    tenant = Tenant.objects.create(slug="sync-policy-resolve-db", name="Sync Policy Resolve DB")
    database = _create_database(tenant=tenant, suffix="resolve")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        database=None,
        policy=PoolMasterDataSyncPolicy.CC_MASTER,
    )
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        database=database,
        policy=PoolMasterDataSyncPolicy.BIDIRECTIONAL,
    )

    resolution = resolve_pool_master_data_sync_policy(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.ITEM,
        database_id=str(database.id),
    )

    assert resolution.source == "database_scope"
    assert resolution.policy == PoolMasterDataSyncPolicy.BIDIRECTIONAL
    assert resolution.scope_id is not None


@pytest.mark.django_db
def test_resolver_falls_back_to_tenant_default_scope() -> None:
    tenant = Tenant.objects.create(slug="sync-policy-resolve-default", name="Sync Policy Resolve Default")
    database = _create_database(tenant=tenant, suffix="resolve-default")
    PoolMasterDataSyncScope.objects.create(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.CONTRACT,
        database=None,
        policy=PoolMasterDataSyncPolicy.IB_MASTER,
    )

    resolution = resolve_pool_master_data_sync_policy(
        tenant_id=str(tenant.id),
        entity_type=PoolMasterDataEntityType.CONTRACT,
        database_id=str(database.id),
    )

    assert resolution.source == "tenant_default"
    assert resolution.policy == PoolMasterDataSyncPolicy.IB_MASTER


@pytest.mark.django_db
def test_require_policy_fails_closed_when_scope_is_missing() -> None:
    tenant = Tenant.objects.create(slug="sync-policy-missing", name="Sync Policy Missing")
    database = _create_database(tenant=tenant, suffix="missing")

    with pytest.raises(MasterDataSyncPolicyMissingError) as exc_info:
        require_pool_master_data_sync_policy(
            tenant_id=str(tenant.id),
            entity_type=PoolMasterDataEntityType.TAX_PROFILE,
            database_id=str(database.id),
        )

    assert exc_info.value.code == "MASTER_DATA_SYNC_POLICY_MISSING"
    assert exc_info.value.entity_type == PoolMasterDataEntityType.TAX_PROFILE
    assert exc_info.value.database_id == str(database.id)
