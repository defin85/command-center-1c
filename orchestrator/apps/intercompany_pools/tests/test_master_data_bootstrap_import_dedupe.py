from __future__ import annotations

from uuid import uuid4

import pytest

from apps.databases.models import Database
from apps.intercompany_pools.master_data_bootstrap_import_service import (
    _apply_binding_row,
    _apply_party_row,
    _load_resolved_canonical_aliases,
)
from apps.intercompany_pools.models import (
    PoolMasterBindingCatalogKind,
    PoolMasterDataBootstrapImportEntityType,
    PoolMasterDataEntityType,
    PoolMasterParty,
)
from apps.tenancy.models import Tenant


def _create_database(*, tenant: Tenant, suffix: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=f"bootstrap-dedupe-{suffix}",
        host="localhost",
        odata_url=f"http://localhost/odata/{suffix}.odata",
        username="admin",
        password="secret",
    )


@pytest.mark.django_db
def test_apply_party_row_uses_dedupe_ingestion_and_returns_canonical_id() -> None:
    tenant = Tenant.objects.create(slug=f"bootstrap-dedupe-party-{uuid4().hex[:6]}", name="Bootstrap Dedupe")

    outcome = _apply_party_row(
        tenant=tenant,
        row={
            "canonical_id": "party-source-a",
            "source_ref": "Ref_Party_A",
            "name": "ООО Единая",
            "full_name": "ООО Единая",
            "inn": "7705005005",
            "kpp": "770501001",
            "is_counterparty": True,
        },
        origin_event_id="evt-party-row",
        job_id="job-1",
    )

    assert outcome.action == "created"
    assert outcome.source_canonical_id == "party-source-a"
    assert outcome.canonical_id == "party-source-a"
    assert PoolMasterParty.objects.filter(tenant=tenant, canonical_id="party-source-a").exists()


@pytest.mark.django_db
def test_apply_binding_row_maps_source_alias_to_resolved_canonical_id() -> None:
    tenant = Tenant.objects.create(slug=f"bootstrap-dedupe-binding-{uuid4().hex[:6]}", name="Bootstrap Binding")
    database = _create_database(tenant=tenant, suffix="binding")
    PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="party-canonical",
        name="Canonical Party",
        is_counterparty=True,
        is_our_organization=False,
    )
    resolved_ids = {
        PoolMasterDataBootstrapImportEntityType.PARTY: {"party-canonical"},
        PoolMasterDataBootstrapImportEntityType.ITEM: set(),
        PoolMasterDataBootstrapImportEntityType.TAX_PROFILE: set(),
        PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT: set(),
        PoolMasterDataBootstrapImportEntityType.CONTRACT: set(),
        PoolMasterDataBootstrapImportEntityType.BINDING: set(),
    }
    resolved_aliases = _load_resolved_canonical_aliases()
    resolved_aliases[PoolMasterDataEntityType.PARTY]["party-source-b"] = "party-canonical"

    outcome = _apply_binding_row(
        tenant=tenant,
        database=database,
        row={
            "entity_type": PoolMasterDataEntityType.PARTY,
            "canonical_id": "party-source-b",
            "ib_ref_key": "ref-binding-001",
            "ib_catalog_kind": PoolMasterBindingCatalogKind.COUNTERPARTY,
        },
        resolved_ids=resolved_ids,
        resolved_aliases=resolved_aliases,
        origin_event_id="evt-binding-row",
        job_id="job-binding-1",
    )

    assert outcome.action == "created"
    assert outcome.source_canonical_id == "party-source-b"
    assert outcome.canonical_id == "party-canonical"
