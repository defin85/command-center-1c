from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from apps.databases.models import Database
from apps.intercompany_pools.master_data_errors import (
    MASTER_DATA_BINDING_AMBIGUOUS,
    MASTER_DATA_BINDING_CONFLICT,
    MASTER_DATA_ENTITY_NOT_FOUND,
    MasterDataResolveError,
)
from apps.intercompany_pools.master_data_bindings import upsert_pool_master_data_binding
from apps.intercompany_pools.master_data_registry import (
    POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING,
    POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT,
)
from apps.intercompany_pools.models import (
    PoolMasterBindingCatalogKind,
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"mdm-db-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_party_binding_requires_catalog_kind() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-party-kind", name="MDM Binding Party Kind")
    database = _create_database(tenant=tenant, suffix="party-kind")

    with pytest.raises(ValidationError):
        PoolMasterDataBinding.objects.create(
            tenant=tenant,
            entity_type=PoolMasterDataEntityType.PARTY,
            canonical_id="party-001",
            database=database,
            ib_ref_key="ref-001",
            ib_catalog_kind="",
        )


@pytest.mark.django_db
def test_contract_binding_requires_owner_counterparty_scope() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-contract-owner", name="MDM Binding Contract Owner")
    database = _create_database(tenant=tenant, suffix="contract-owner")

    with pytest.raises(ValidationError):
        PoolMasterDataBinding.objects.create(
            tenant=tenant,
            entity_type=PoolMasterDataEntityType.CONTRACT,
            canonical_id="contract-001",
            database=database,
            ib_ref_key="ref-contract",
            owner_counterparty_canonical_id="",
        )


@pytest.mark.django_db
def test_upsert_pool_master_data_binding_is_idempotent_for_same_scope() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-idempotent", name="MDM Binding Idempotent")
    database = _create_database(tenant=tenant, suffix="idempotent")

    first = upsert_pool_master_data_binding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.PARTY,
        canonical_id="party-001",
        database=database,
        ib_ref_key="party-ref-001",
        ib_catalog_kind=PoolMasterBindingCatalogKind.COUNTERPARTY,
        fingerprint="abc",
    )
    second = upsert_pool_master_data_binding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.PARTY,
        canonical_id="party-001",
        database=database,
        ib_ref_key="party-ref-001",
        ib_catalog_kind=PoolMasterBindingCatalogKind.COUNTERPARTY,
        fingerprint="abc",
    )

    assert first.created is True
    assert first.changed is True
    assert second.created is False
    assert second.changed is False
    assert first.binding.id == second.binding.id
    outbox_rows = list(
        PoolMasterDataSyncOutbox.objects.filter(
            tenant=tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.PARTY,
        )
    )
    assert len(outbox_rows) == 1
    assert outbox_rows[0].status == PoolMasterDataSyncOutboxStatus.PENDING
    assert outbox_rows[0].payload["mutation_kind"] == "binding_upsert"


@pytest.mark.django_db
def test_upsert_pool_master_data_binding_updates_existing_scope() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-update", name="MDM Binding Update")
    database = _create_database(tenant=tenant, suffix="update")

    first = upsert_pool_master_data_binding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-001",
        database=database,
        ib_ref_key="item-ref-001",
        fingerprint="v1",
    )
    second = upsert_pool_master_data_binding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-001",
        database=database,
        ib_ref_key="item-ref-002",
        fingerprint="v2",
    )

    assert first.created is True
    assert second.created is False
    assert second.changed is True
    assert second.binding.ib_ref_key == "item-ref-002"
    assert second.binding.fingerprint == "v2"


@pytest.mark.django_db
def test_upsert_binding_skips_outbox_for_ib_origin_event() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-anti-loop", name="MDM Binding Anti Loop")
    database = _create_database(tenant=tenant, suffix="anti-loop")

    result = upsert_pool_master_data_binding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-anti-loop",
        database=database,
        ib_ref_key="item-ref-anti-loop",
        origin_system="ib",
        origin_event_id="evt-ib-anti-loop-001",
    )

    assert result.created is True
    assert result.changed is True
    assert (
        PoolMasterDataSyncOutbox.objects.filter(
            tenant=tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.ITEM,
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_upsert_binding_skips_outbox_when_registry_disables_outbox_capability() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-outbox-gated", name="MDM Binding Outbox Gated")
    database = _create_database(tenant=tenant, suffix="outbox-gated")

    def _supports(*, entity_type: str, capability: str, include_bootstrap_helpers: bool = False) -> bool:
        if capability == POOL_MASTER_DATA_CAPABILITY_DIRECT_BINDING:
            return True
        if capability == POOL_MASTER_DATA_CAPABILITY_OUTBOX_FANOUT:
            return False
        return True

    with patch(
        "apps.intercompany_pools.master_data_bindings.supports_pool_master_data_capability",
        side_effect=_supports,
    ):
        result = upsert_pool_master_data_binding(
            tenant=tenant,
            entity_type=PoolMasterDataEntityType.ITEM,
            canonical_id="item-outbox-gated",
            database=database,
            ib_ref_key="item-ref-outbox-gated",
        )

    assert result.created is True
    assert result.changed is True
    assert PoolMasterDataSyncOutbox.objects.filter(tenant=tenant, database=database).count() == 0


@pytest.mark.django_db
def test_upsert_binding_requires_origin_event_for_non_cc_origin() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-origin-required", name="MDM Binding Origin Required")
    database = _create_database(tenant=tenant, suffix="origin-required")

    with pytest.raises(ValueError, match="origin_event_id is required for non-CC origin"):
        upsert_pool_master_data_binding(
            tenant=tenant,
            entity_type=PoolMasterDataEntityType.ITEM,
            canonical_id="item-origin-required",
            database=database,
            ib_ref_key="item-ref-origin-required",
            origin_system="ib",
            origin_event_id="",
        )


@pytest.mark.django_db
def test_contract_binding_scope_includes_owner_counterparty() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-contract-scope", name="MDM Binding Contract Scope")
    database = _create_database(tenant=tenant, suffix="contract-scope")

    first = upsert_pool_master_data_binding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.CONTRACT,
        canonical_id="contract-001",
        database=database,
        ib_ref_key="contract-ref-a",
        owner_counterparty_canonical_id="party-a",
    )
    second = upsert_pool_master_data_binding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.CONTRACT,
        canonical_id="contract-001",
        database=database,
        ib_ref_key="contract-ref-b",
        owner_counterparty_canonical_id="party-b",
    )

    assert first.created is True
    assert second.created is True
    assert first.binding.id != second.binding.id


@pytest.mark.django_db
def test_gl_account_binding_requires_chart_identity() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-gl-account-kind", name="MDM Binding GL Account")
    database = _create_database(tenant=tenant, suffix="gl-account-kind")

    with pytest.raises(ValidationError):
        PoolMasterDataBinding.objects.create(
            tenant=tenant,
            entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
            canonical_id="gl-account-001",
            database=database,
            ib_ref_key="ref-gl-account",
            chart_identity="",
        )


@pytest.mark.django_db
def test_gl_account_binding_scope_includes_chart_identity() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-gl-account-scope", name="MDM Binding GL Account Scope")
    database = _create_database(tenant=tenant, suffix="gl-account-scope")

    first = upsert_pool_master_data_binding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
        canonical_id="gl-account-001",
        database=database,
        ib_ref_key="gl-account-ref-a",
        chart_identity="ChartOfAccounts_Main",
    )
    second = upsert_pool_master_data_binding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
        canonical_id="gl-account-001",
        database=database,
        ib_ref_key="gl-account-ref-b",
        chart_identity="ChartOfAccounts_Tax",
    )

    assert first.created is True
    assert second.created is True
    assert first.binding.id != second.binding.id
    assert (
        PoolMasterDataSyncOutbox.objects.filter(
            tenant=tenant,
            database=database,
            entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_upsert_returns_entity_not_found_code_for_unsupported_entity_type() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-unsupported", name="MDM Binding Unsupported")
    database = _create_database(tenant=tenant, suffix="unsupported")

    with pytest.raises(MasterDataResolveError) as exc_info:
        upsert_pool_master_data_binding(
            tenant=tenant,
            entity_type="unsupported",
            canonical_id="entity-001",
            database=database,
            ib_ref_key="ref-unsupported",
        )

    error = exc_info.value
    assert error.code == MASTER_DATA_ENTITY_NOT_FOUND
    assert error.entity_type == "unsupported"
    assert error.canonical_id == "entity-001"
    assert error.target_database_id == str(database.id)
    assert error.to_diagnostic()["error_code"] == MASTER_DATA_ENTITY_NOT_FOUND


@pytest.mark.django_db
def test_upsert_returns_binding_conflict_code_for_invalid_scope() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-conflict", name="MDM Binding Conflict")
    database = _create_database(tenant=tenant, suffix="conflict")

    with pytest.raises(MasterDataResolveError) as exc_info:
        upsert_pool_master_data_binding(
            tenant=tenant,
            entity_type=PoolMasterDataEntityType.PARTY,
            canonical_id="party-001",
            database=database,
            ib_ref_key="party-ref-001",
            ib_catalog_kind="",
        )

    error = exc_info.value
    assert error.code == MASTER_DATA_BINDING_CONFLICT
    assert error.entity_type == PoolMasterDataEntityType.PARTY
    assert error.canonical_id == "party-001"
    assert error.target_database_id == str(database.id)
    assert error.to_diagnostic()["error_code"] == MASTER_DATA_BINDING_CONFLICT


@pytest.mark.django_db
def test_upsert_returns_binding_ambiguous_code_when_scope_has_multiple_matches() -> None:
    tenant = Tenant.objects.create(slug="mdm-bind-ambiguous", name="MDM Binding Ambiguous")
    database = _create_database(tenant=tenant, suffix="ambiguous")
    first = PoolMasterDataBinding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-001",
        database=database,
        ib_ref_key="item-ref-001",
    )
    second = PoolMasterDataBinding(
        tenant=tenant,
        entity_type=PoolMasterDataEntityType.ITEM,
        canonical_id="item-001",
        database=database,
        ib_ref_key="item-ref-002",
    )

    with patch(
        "apps.intercompany_pools.master_data_bindings._load_scope_candidates",
        return_value=[first, second],
    ):
        with pytest.raises(MasterDataResolveError) as exc_info:
            upsert_pool_master_data_binding(
                tenant=tenant,
                entity_type=PoolMasterDataEntityType.ITEM,
                canonical_id="item-001",
                database=database,
                ib_ref_key="item-ref-003",
            )

    error = exc_info.value
    assert error.code == MASTER_DATA_BINDING_AMBIGUOUS
    assert error.entity_type == PoolMasterDataEntityType.ITEM
    assert error.canonical_id == "item-001"
    assert error.target_database_id == str(database.id)
    diagnostic = error.to_diagnostic()
    assert diagnostic["error_code"] == MASTER_DATA_BINDING_AMBIGUOUS
    assert isinstance(diagnostic["errors"], list)
    assert len(diagnostic["errors"]) == 2
