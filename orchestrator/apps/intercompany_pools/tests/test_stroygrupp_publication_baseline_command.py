from __future__ import annotations

import io
import json
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.databases.models import Database, InfobaseUserMapping
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolMasterBindingCatalogKind,
    PoolMasterContract,
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterItem,
    PoolMasterParty,
    PoolNodeVersion,
    PoolODataMetadataCatalogSnapshot,
    PoolODataMetadataCatalogSnapshotSource,
)
from apps.intercompany_pools.stroygrupp_publication_baseline import (
    STROYGRUPP_BASELINE_DOCUMENT_DATE,
    STROYGRUPP_BASELINE_SERVICE_LINE_ID,
    ZERO_GUID,
    build_stroygrupp_realization_services_policy,
)
from apps.tenancy.models import Tenant


User = get_user_model()


def _create_database(*, tenant: Tenant, name: str) -> Database:
    return Database.objects.create(
        tenant=tenant,
        name=name,
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="legacy-user",
        password="legacy-pass",
    )


def _create_current_snapshot(*, tenant: Tenant, database: Database) -> None:
    PoolODataMetadataCatalogSnapshot.objects.create(
        tenant=tenant,
        database=database,
        config_name=database.name,
        config_version="",
        extensions_fingerprint="",
        metadata_hash="f" * 64,
        catalog_version="v1:stroygrupp-baseline",
        source=PoolODataMetadataCatalogSnapshotSource.COLD_BOOTSTRAP,
        is_current=True,
        payload={
            "documents": [
                {
                    "entity_name": "Document_РеализацияТоваровУслуг",
                    "display_name": "РеализацияТоваровУслуг",
                    "fields": [
                        {"name": "ВидОперации", "type": "Edm.String", "nullable": False},
                        {"name": "Date", "type": "Edm.DateTime", "nullable": False},
                        {"name": "ТипЦен_Key", "type": "Edm.Guid", "nullable": False},
                        {"name": "Склад_Key", "type": "Edm.Guid", "nullable": False},
                        {"name": "Организация_Key", "type": "Edm.Guid", "nullable": False},
                        {"name": "ПодразделениеОрганизации_Key", "type": "Edm.Guid", "nullable": False},
                        {"name": "Контрагент_Key", "type": "Edm.Guid", "nullable": False},
                        {"name": "ДоговорКонтрагента_Key", "type": "Edm.Guid", "nullable": False},
                        {"name": "СпособЗачетаАвансов", "type": "Edm.String", "nullable": False},
                        {"name": "ВалютаДокумента_Key", "type": "Edm.Guid", "nullable": False},
                        {"name": "КурсВзаиморасчетов", "type": "Edm.Decimal", "nullable": False},
                        {"name": "КратностьВзаиморасчетов", "type": "Edm.Decimal", "nullable": False},
                        {"name": "СуммаВключаетНДС", "type": "Edm.Boolean", "nullable": False},
                        {
                            "name": "СчетУчетаРасчетовСКонтрагентом_Key",
                            "type": "Edm.Guid",
                            "nullable": False,
                        },
                        {
                            "name": "СчетУчетаРасчетовПоАвансам_Key",
                            "type": "Edm.Guid",
                            "nullable": False,
                        },
                        {"name": "СуммаДокумента", "type": "Edm.Decimal", "nullable": False},
                        {"name": "Ответственный_Key", "type": "Edm.Guid", "nullable": False},
                        {"name": "Руководитель_Key", "type": "Edm.Guid", "nullable": False},
                        {"name": "АдресДоставки", "type": "Edm.String", "nullable": False},
                        {"name": "ВидЭлектронногоДокумента", "type": "Edm.String", "nullable": False},
                        {"name": "ЭтоУниверсальныйДокумент", "type": "Edm.Boolean", "nullable": False},
                    ],
                    "table_parts": [
                        {
                            "name": "Услуги",
                            "row_fields": [
                                {"name": "LineNumber", "type": "Edm.Decimal", "nullable": False},
                                {"name": "Номенклатура_Key", "type": "Edm.Guid", "nullable": False},
                                {"name": "Содержание", "type": "Edm.String", "nullable": False},
                                {"name": "Количество", "type": "Edm.Decimal", "nullable": False},
                                {"name": "Цена", "type": "Edm.Decimal", "nullable": False},
                                {"name": "Сумма", "type": "Edm.Decimal", "nullable": False},
                                {"name": "СтавкаНДС", "type": "Edm.String", "nullable": False},
                                {"name": "СуммаНДС", "type": "Edm.Decimal", "nullable": False},
                                {"name": "СчетДоходов_Key", "type": "Edm.Guid", "nullable": False},
                                {"name": "СчетРасходов_Key", "type": "Edm.Guid", "nullable": False},
                                {
                                    "name": "СчетУчетаНДСПоРеализации_Key",
                                    "type": "Edm.Guid",
                                    "nullable": False,
                                },
                                {"name": "Субконто", "type": "Edm.String", "nullable": False},
                                {"name": "Субконто_Type", "type": "Edm.String", "nullable": False},
                                {"name": "СчетНаОплатуПокупателю_Key", "type": "Edm.Guid", "nullable": False},
                                {"name": "ИдентификаторСтрокиГосконтрактаЕИС", "type": "Edm.String", "nullable": False},
                                {"name": "ИдентификаторСтроки", "type": "Edm.String", "nullable": False},
                            ],
                        }
                    ],
                }
            ]
        },
    )


def test_build_stroygrupp_realization_services_policy_matches_odata_verified_full_payload_shape() -> None:
    policy = build_stroygrupp_realization_services_policy()

    document = policy["chains"][0]["documents"][0]
    field_mapping = document["field_mapping"]
    row_mapping = document["table_parts_mapping"]["Услуги"][0]

    assert field_mapping["Date"] == STROYGRUPP_BASELINE_DOCUMENT_DATE
    assert field_mapping["ТипЦен_Key"] == ZERO_GUID
    assert field_mapping["Склад_Key"] == ZERO_GUID
    assert field_mapping["ПодразделениеОрганизации_Key"] == ZERO_GUID
    assert field_mapping["КурсВзаиморасчетов"] == 0
    assert field_mapping["КратностьВзаиморасчетов"] == "0"
    assert field_mapping["Ответственный_Key"] == ZERO_GUID
    assert field_mapping["Руководитель_Key"] == ZERO_GUID
    assert field_mapping["АдресДоставки"] == ""

    assert row_mapping["LineNumber"] == "1"
    assert row_mapping["СчетНаОплатуПокупателю_Key"] == ZERO_GUID
    assert row_mapping["ИдентификаторСтрокиГосконтрактаЕИС"] == ""
    assert row_mapping["ИдентификаторСтроки"] == STROYGRUPP_BASELINE_SERVICE_LINE_ID


def _create_default_baseline_prerequisites() -> tuple[Tenant, Database, Organization, Organization, User]:
    tenant = Tenant.objects.create(
        slug=f"baseline-{uuid4().hex[:8]}",
        name="Baseline Tenant",
    )
    database = _create_database(tenant=tenant, name="stroygrupp_7751284461")
    root_org = Organization.objects.create(
        tenant=tenant,
        name="Общество",
        inn="000000000000",
    )
    target_org = Organization.objects.create(
        tenant=tenant,
        database=database,
        name='ООО "СТРОЙГРУПП"',
        inn="7751284461",
    )
    actor = User.objects.create_user(
        username="admin",
        email=f"baseline-admin-{uuid4().hex[:8]}@example.test",
        password="pass",
    )
    InfobaseUserMapping.objects.create(
        database=database,
        user=None,
        ib_username="odata.user",
        ib_password="odata.user",
        is_service=True,
    )
    _create_current_snapshot(tenant=tenant, database=database)
    return tenant, database, root_org, target_org, actor


@pytest.mark.django_db
def test_bootstrap_stroygrupp_publication_baseline_dry_run_reports_plan_without_persisting() -> None:
    tenant, database, root_org, target_org, actor = _create_default_baseline_prerequisites()

    out = io.StringIO()
    call_command(
        "bootstrap_stroygrupp_publication_baseline",
        "--tenant-slug",
        tenant.slug,
        "--actor-username",
        actor.username,
        "--dry-run",
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())

    assert payload["dry_run"] is True
    assert payload["baseline"] == "stroygrupp_realization_services_v1"
    assert payload["pool"]["code"] == "stroygrupp-full-publication-baseline"
    assert payload["target_database"]["id"] == str(database.id)
    assert payload["organizations"]["root"]["id"] == str(root_org.id)
    assert payload["organizations"]["target"]["id"] == str(target_org.id)
    assert payload["document_policy"]["metadata_validation_errors"] == []
    assert payload["auth_mappings"]["actor_mapping_state"] == "missing"
    assert payload["readiness"]["ready_for_ui_run"] is False
    assert payload["readiness"]["blockers"]

    assert not OrganizationPool.objects.filter(tenant=tenant, code="stroygrupp-full-publication-baseline").exists()
    assert not PoolMasterParty.objects.filter(tenant=tenant, canonical_id="stroygrupp").exists()
    assert not PoolMasterParty.objects.filter(tenant=tenant, canonical_id="proekt-st").exists()
    assert not PoolMasterContract.objects.filter(tenant=tenant, canonical_id="osnovnoy").exists()
    assert not PoolMasterItem.objects.filter(tenant=tenant, canonical_id="packing-service").exists()
    assert not PoolMasterDataBinding.objects.filter(tenant=tenant, database=database).exists()
    assert not InfobaseUserMapping.objects.filter(database=database, user=actor).exists()


@pytest.mark.django_db
def test_bootstrap_stroygrupp_publication_baseline_apply_is_idempotent() -> None:
    tenant, database, root_org, target_org, actor = _create_default_baseline_prerequisites()

    out_apply = io.StringIO()
    call_command(
        "bootstrap_stroygrupp_publication_baseline",
        "--tenant-slug",
        tenant.slug,
        "--actor-username",
        actor.username,
        "--actor-ib-username",
        "odata.actor",
        "--actor-ib-password",
        "odata.actor.pass",
        "--json",
        stdout=out_apply,
    )
    payload = json.loads(out_apply.getvalue())

    assert payload["dry_run"] is False
    pool = OrganizationPool.objects.get(tenant=tenant, code="stroygrupp-full-publication-baseline")
    assert pool.name == "STROYGRUPP Full Publication Baseline"

    nodes = list(PoolNodeVersion.objects.filter(pool=pool).select_related("organization").order_by("id"))
    assert len(nodes) == 2
    assert {str(node.organization_id) for node in nodes} == {str(root_org.id), str(target_org.id)}
    assert sum(1 for node in nodes if node.is_root) == 1

    edges = list(PoolEdgeVersion.objects.filter(pool=pool).select_related("parent_node", "child_node"))
    assert len(edges) == 1
    edge = edges[0]
    assert str(edge.parent_node.organization_id) == str(root_org.id)
    assert str(edge.child_node.organization_id) == str(target_org.id)
    policy = edge.metadata["document_policy"]
    assert policy["chains"][0]["documents"][0]["entity_name"] == "Document_РеализацияТоваровУслуг"

    target_org.refresh_from_db(fields=["master_party_id"])
    database.refresh_from_db(fields=["metadata"])
    assert target_org.master_party_id is not None
    assert database.metadata["odata_transport"]["verify_tls"] is False
    stroygrupp_party = PoolMasterParty.objects.get(tenant=tenant, canonical_id="stroygrupp")
    assert target_org.master_party_id == stroygrupp_party.id
    assert stroygrupp_party.metadata["ib_ref_keys"][str(database.id)]["organization"]

    proekt_party = PoolMasterParty.objects.get(tenant=tenant, canonical_id="proekt-st")
    contract = PoolMasterContract.objects.get(tenant=tenant, canonical_id="osnovnoy")
    item = PoolMasterItem.objects.get(tenant=tenant, canonical_id="packing-service")
    assert contract.owner_counterparty_id == proekt_party.id
    assert item.metadata["ib_ref_keys"][str(database.id)]

    bindings = list(
        PoolMasterDataBinding.objects.filter(tenant=tenant, database=database).order_by(
            "entity_type",
            "canonical_id",
            "ib_catalog_kind",
            "owner_counterparty_canonical_id",
        )
    )
    assert len(bindings) == 4
    assert {
        (
            binding.entity_type,
            binding.canonical_id,
            binding.ib_catalog_kind,
            binding.owner_counterparty_canonical_id,
        )
        for binding in bindings
    } == {
        (
            PoolMasterDataEntityType.PARTY,
            "stroygrupp",
            PoolMasterBindingCatalogKind.ORGANIZATION,
            "",
        ),
        (
            PoolMasterDataEntityType.PARTY,
            "proekt-st",
            PoolMasterBindingCatalogKind.COUNTERPARTY,
            "",
        ),
        (
            PoolMasterDataEntityType.CONTRACT,
            "osnovnoy",
            "",
            "proekt-st",
        ),
        (
            PoolMasterDataEntityType.ITEM,
            "packing-service",
            "",
            "",
        ),
    }

    actor_mapping = InfobaseUserMapping.objects.get(database=database, user=actor)
    assert actor_mapping.ib_username == "odata.actor"
    assert actor_mapping.ib_password == "odata.actor.pass"
    assert actor_mapping.is_service is False
    assert payload["readiness"]["ready_for_ui_run"] is True
    assert payload["readiness"]["blockers"] == []

    out_reapply = io.StringIO()
    call_command(
        "bootstrap_stroygrupp_publication_baseline",
        "--tenant-slug",
        tenant.slug,
        "--actor-username",
        actor.username,
        "--actor-ib-username",
        "odata.actor",
        "--actor-ib-password",
        "odata.actor.pass",
        "--json",
        stdout=out_reapply,
    )
    reapply_payload = json.loads(out_reapply.getvalue())
    assert reapply_payload["dry_run"] is False
    assert OrganizationPool.objects.filter(tenant=tenant, code="stroygrupp-full-publication-baseline").count() == 1
    assert PoolEdgeVersion.objects.filter(pool=pool).count() == 1
    assert PoolNodeVersion.objects.filter(pool=pool).count() == 2
    assert PoolMasterParty.objects.filter(tenant=tenant, canonical_id="stroygrupp").count() == 1
    assert PoolMasterParty.objects.filter(tenant=tenant, canonical_id="proekt-st").count() == 1
    assert PoolMasterContract.objects.filter(tenant=tenant, canonical_id="osnovnoy").count() == 1
    assert PoolMasterItem.objects.filter(tenant=tenant, canonical_id="packing-service").count() == 1
    assert PoolMasterDataBinding.objects.filter(tenant=tenant, database=database).count() == 4
    assert InfobaseUserMapping.objects.filter(database=database, user=actor).count() == 1
