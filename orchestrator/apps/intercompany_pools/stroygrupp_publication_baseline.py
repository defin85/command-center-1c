from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.databases.models import Database, InfobaseUserMapping

from .document_policy_contract import validate_document_policy_v1
from .metadata_catalog import (
    get_current_snapshot_for_database_scope,
    validate_document_policy_references,
)
from .models import (
    Organization,
    OrganizationPool,
    PoolEdgeVersion,
    PoolMasterBindingCatalogKind,
    PoolMasterBindingSyncStatus,
    PoolMasterContract,
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterItem,
    PoolMasterParty,
    PoolNodeVersion,
)
from .publication_auth_mapping import evaluate_publication_auth_coverage
from .validators import validate_pool_graph
from apps.tenancy.models import Tenant


BASELINE_ID = "stroygrupp_realization_services_v1"
BASELINE_POOL_CODE = "stroygrupp-full-publication-baseline"
BASELINE_POOL_NAME = "STROYGRUPP Full Publication Baseline"
BASELINE_EFFECTIVE_FROM = date(2026, 1, 1)
TARGET_DATABASE_NAME = "stroygrupp_7751284461"
ROOT_ORGANIZATION_NAME = "Общество"
ROOT_ORGANIZATION_INN = "000000000000"
TARGET_ORGANIZATION_NAME = 'ООО "СТРОЙГРУПП"'
TARGET_ORGANIZATION_INN = "7751284461"

STROYGRUPP_ORGANIZATION_REF = "789df375-0873-11ea-a5d4-0c9d92779da8"
PROEKT_ST_COUNTERPARTY_REF = "e28bd6fe-50c9-11f0-904c-bbb30f628b54"
OSNOVNOY_CONTRACT_REF = "f77692fd-50ca-11f0-904c-bbb30f628b54"
PACKING_SERVICE_ITEM_REF = "cf616608-aaef-11ea-b223-b42e99cf3459"
ZERO_GUID = "00000000-0000-0000-0000-000000000000"
STROYGRUPP_BASELINE_DOCUMENT_DATE = "2025-03-13T00:00:00"
STROYGRUPP_BASELINE_SERVICE_LINE_ID = "8cdc13d0-5545-431b-8faa-a80b69494e71"
BASELINE_DATABASE_ODATA_VERIFY_TLS = False


def build_stroygrupp_realization_services_policy() -> dict[str, Any]:
    return validate_document_policy_v1(
        policy={
            "version": "document_policy.v1",
            "chains": [
                {
                    "chain_id": "stroygrupp_realization_services_baseline",
                    "documents": [
                        {
                            "document_id": "sale",
                            "entity_name": "Document_РеализацияТоваровУслуг",
                            "document_role": "sale",
                            "invoice_mode": "optional",
                            "field_mapping": {
                                "ВидОперации": "Услуги",
                                "Date": STROYGRUPP_BASELINE_DOCUMENT_DATE,
                                "ТипЦен_Key": ZERO_GUID,
                                "Склад_Key": ZERO_GUID,
                                "Организация_Key": "master_data.party.stroygrupp.organization.ref",
                                "ПодразделениеОрганизации_Key": ZERO_GUID,
                                "Контрагент_Key": "master_data.party.proekt-st.counterparty.ref",
                                "ДоговорКонтрагента_Key": "master_data.contract.osnovnoy.proekt-st.ref",
                                "СпособЗачетаАвансов": "Автоматически",
                                "ВалютаДокумента_Key": "171b30af-54e8-11e9-80ee-0050569f2e9f",
                                "КурсВзаиморасчетов": 0,
                                "КратностьВзаиморасчетов": "0",
                                "СуммаВключаетНДС": True,
                                "СчетУчетаРасчетовСКонтрагентом_Key": "020635d6-54e8-11e9-80ee-0050569f2e9f",
                                "СчетУчетаРасчетовПоАвансам_Key": "020635d7-54e8-11e9-80ee-0050569f2e9f",
                                "СуммаДокумента": "allocation.amount",
                                "Ответственный_Key": ZERO_GUID,
                                "Руководитель_Key": ZERO_GUID,
                                "АдресДоставки": "",
                                "ВидЭлектронногоДокумента": "АктВыполненныхРабот",
                                "ЭтоУниверсальныйДокумент": True,
                            },
                            "table_parts_mapping": {
                                "Услуги": [
                                    {
                                        "LineNumber": "1",
                                        "Номенклатура_Key": "master_data.item.packing-service.ref",
                                        "Содержание": "Упаковка/Фасовка товаров на складе",
                                        "Количество": 1,
                                        "Цена": "allocation.amount",
                                        "Сумма": "allocation.amount",
                                        "СтавкаНДС": "НДС20",
                                        "СуммаНДС": 2159472.33,
                                        "СчетДоходов_Key": "02063683-54e8-11e9-80ee-0050569f2e9f",
                                        "СчетРасходов_Key": "02063686-54e8-11e9-80ee-0050569f2e9f",
                                        "СчетУчетаНДСПоРеализации_Key": "02063688-54e8-11e9-80ee-0050569f2e9f",
                                        "Субконто": "62953114-54e8-11e9-80ee-0050569f2e9f",
                                        "Субконто_Type": "StandardODATA.Catalog_НоменклатурныеГруппы",
                                        "СчетНаОплатуПокупателю_Key": ZERO_GUID,
                                        "ИдентификаторСтрокиГосконтрактаЕИС": "",
                                        "ИдентификаторСтроки": STROYGRUPP_BASELINE_SERVICE_LINE_ID,
                                    }
                                ]
                            },
                            "link_rules": {},
                        }
                    ],
                }
            ],
            "completeness_profiles": {
                "minimal_documents_full_payload": {
                    "entities": {
                        "Document_РеализацияТоваровУслуг": {
                            "required_fields": [
                                "ВидОперации",
                                "Date",
                                "ТипЦен_Key",
                                "Склад_Key",
                                "Организация_Key",
                                "ПодразделениеОрганизации_Key",
                                "Контрагент_Key",
                                "ДоговорКонтрагента_Key",
                                "СпособЗачетаАвансов",
                                "ВалютаДокумента_Key",
                                "КурсВзаиморасчетов",
                                "КратностьВзаиморасчетов",
                                "СуммаВключаетНДС",
                                "СчетУчетаРасчетовСКонтрагентом_Key",
                                "СчетУчетаРасчетовПоАвансам_Key",
                                "СуммаДокумента",
                                "Ответственный_Key",
                                "Руководитель_Key",
                                "АдресДоставки",
                                "ВидЭлектронногоДокумента",
                                "ЭтоУниверсальныйДокумент",
                            ],
                            "required_table_parts": {
                                "Услуги": {
                                    "min_rows": 1,
                                    "required_fields": [
                                        "LineNumber",
                                        "Номенклатура_Key",
                                        "Содержание",
                                        "Количество",
                                        "Цена",
                                        "Сумма",
                                        "СтавкаНДС",
                                        "СуммаНДС",
                                        "СчетДоходов_Key",
                                        "СчетРасходов_Key",
                                        "СчетУчетаНДСПоРеализации_Key",
                                        "Субконто",
                                        "Субконто_Type",
                                        "СчетНаОплатуПокупателю_Key",
                                        "ИдентификаторСтрокиГосконтрактаЕИС",
                                        "ИдентификаторСтроки",
                                    ]
                                }
                            },
                        }
                    }
                }
            },
        }
    )


def bootstrap_stroygrupp_publication_baseline(
    *,
    tenant_slug: str,
    actor_username: str,
    actor_ib_username: str = "",
    actor_ib_password: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    tenant = Tenant.objects.filter(slug=tenant_slug).first()
    if tenant is None:
        raise ValueError(f"Tenant '{tenant_slug}' not found.")
    database = Database.objects.filter(tenant=tenant, name=TARGET_DATABASE_NAME).first()
    if database is None:
        raise ValueError(f"Database '{TARGET_DATABASE_NAME}' not found in tenant '{tenant_slug}'.")
    root_org = _resolve_root_organization(tenant=tenant)
    target_org = _resolve_target_organization(tenant=tenant, database=database)
    actor = _resolve_actor(username=actor_username)
    service_mapping = _resolve_service_mapping(database=database)

    policy = build_stroygrupp_realization_services_policy()
    snapshot = get_current_snapshot_for_database_scope(tenant_id=str(tenant.id), database=database)
    if snapshot is None:
        raise ValueError(f"Current metadata snapshot is missing for database '{database.id}'.")
    metadata_errors = validate_document_policy_references(policy=policy, snapshot=snapshot)
    if metadata_errors:
        raise ValueError(f"Document policy metadata validation failed: {metadata_errors!r}")

    with transaction.atomic():
        _ensure_database_odata_transport_override(database=database)
        pool, pool_state = _upsert_pool(tenant=tenant)
        _upsert_topology(pool=pool, root_org=root_org, target_org=target_org, policy=policy)
        stroygrupp_party, stroygrupp_state = _upsert_party(
            tenant=tenant,
            canonical_id="stroygrupp",
            name="СТРОЙГРУПП ООО",
            inn=TARGET_ORGANIZATION_INN,
            is_our_organization=True,
            is_counterparty=False,
            metadata={"ib_ref_keys": {str(database.id): {"organization": STROYGRUPP_ORGANIZATION_REF}}},
        )
        proekt_party, proekt_state = _upsert_party(
            tenant=tenant,
            canonical_id="proekt-st",
            name="ПРОЭКТ СТ ООО",
            inn="9701309107",
            is_our_organization=False,
            is_counterparty=True,
            metadata={"ib_ref_keys": {str(database.id): {"counterparty": PROEKT_ST_COUNTERPARTY_REF}}},
        )
        contract, contract_state = _upsert_contract(
            tenant=tenant,
            canonical_id="osnovnoy",
            name="Основной",
            owner_counterparty=proekt_party,
            number="Основной",
            metadata={"ib_ref_keys": {str(database.id): {"proekt-st": OSNOVNOY_CONTRACT_REF}}},
        )
        item, item_state = _upsert_item(
            tenant=tenant,
            canonical_id="packing-service",
            name="Упаковка/Фасовка товаров на складе",
            metadata={"ib_ref_keys": {str(database.id): PACKING_SERVICE_ITEM_REF}},
        )
        target_binding_state = _bind_organization_master_party(
            organization=target_org,
            party=stroygrupp_party,
        )
        binding_states = {
            "organization_party": _upsert_binding(
                tenant=tenant,
                database=database,
                entity_type=PoolMasterDataEntityType.PARTY,
                canonical_id="stroygrupp",
                ib_ref_key=STROYGRUPP_ORGANIZATION_REF,
                ib_catalog_kind=PoolMasterBindingCatalogKind.ORGANIZATION,
            ),
            "counterparty_party": _upsert_binding(
                tenant=tenant,
                database=database,
                entity_type=PoolMasterDataEntityType.PARTY,
                canonical_id="proekt-st",
                ib_ref_key=PROEKT_ST_COUNTERPARTY_REF,
                ib_catalog_kind=PoolMasterBindingCatalogKind.COUNTERPARTY,
            ),
            "contract": _upsert_binding(
                tenant=tenant,
                database=database,
                entity_type=PoolMasterDataEntityType.CONTRACT,
                canonical_id="osnovnoy",
                ib_ref_key=OSNOVNOY_CONTRACT_REF,
                owner_counterparty_canonical_id="proekt-st",
            ),
            "item": _upsert_binding(
                tenant=tenant,
                database=database,
                entity_type=PoolMasterDataEntityType.ITEM,
                canonical_id="packing-service",
                ib_ref_key=PACKING_SERVICE_ITEM_REF,
            ),
        }
        actor_mapping, actor_mapping_state = _ensure_actor_mapping(
            database=database,
            actor=actor,
            service_mapping=service_mapping,
            actor_ib_username=actor_ib_username,
            actor_ib_password=actor_ib_password,
        )
        actor_coverage = evaluate_publication_auth_coverage(
            pool=pool,
            target_date=BASELINE_EFFECTIVE_FROM,
            strategy="actor",
            actor_username=actor.username,
        )
        service_coverage = evaluate_publication_auth_coverage(
            pool=pool,
            target_date=BASELINE_EFFECTIVE_FROM,
            strategy="service",
        )
        blockers = []
        if actor_coverage.has_gaps:
            blockers.append(
                {
                    "code": "ODATA_MAPPING_NOT_CONFIGURED",
                    "detail": (
                        "UI run still requires a dedicated actor InfobaseUserMapping. "
                        "Pass --actor-ib-username/--actor-ib-password or precreate the mapping."
                    ),
                }
            )
        payload = {
            "baseline": BASELINE_ID,
            "dry_run": dry_run,
            "tenant": {"id": str(tenant.id), "slug": tenant.slug},
            "target_database": {"id": str(database.id), "name": database.name},
            "pool": {"id": str(pool.id), "code": pool.code, "state": pool_state},
            "organizations": {
                "root": {"id": str(root_org.id), "name": root_org.name, "inn": root_org.inn},
                "target": {
                    "id": str(target_org.id),
                    "name": target_org.name,
                    "inn": target_org.inn,
                    "master_party_id": str(stroygrupp_party.id),
                    "binding_state": target_binding_state,
                },
            },
            "document_policy": {
                "entity_names": ["Document_РеализацияТоваровУслуг"],
                "metadata_validation_errors": metadata_errors,
            },
            "canonical_entities": {
                "stroygrupp_party": {"id": str(stroygrupp_party.id), "state": stroygrupp_state},
                "proekt_st_party": {"id": str(proekt_party.id), "state": proekt_state},
                "osnovnoy_contract": {"id": str(contract.id), "state": contract_state},
                "packing_service_item": {"id": str(item.id), "state": item_state},
            },
            "bindings": binding_states,
            "auth_mappings": {
                "service_mapping_id": str(service_mapping.id),
                "actor_mapping_id": str(actor_mapping.id) if actor_mapping is not None else "",
                "actor_mapping_state": actor_mapping_state,
                "actor_coverage": _serialize_auth_coverage(actor_coverage),
                "service_coverage": _serialize_auth_coverage(service_coverage),
            },
            "readiness": {
                "ready_for_ui_run": not actor_coverage.has_gaps and not service_coverage.has_gaps,
                "blockers": blockers,
            },
            "generated_at": timezone.now().isoformat(),
        }
        if dry_run:
            transaction.set_rollback(True)
        return payload


def _ensure_database_odata_transport_override(*, database: Database) -> None:
    metadata = dict(database.metadata or {})
    transport = metadata.get("odata_transport")
    next_transport = dict(transport) if isinstance(transport, dict) else {}
    if next_transport.get("verify_tls") is BASELINE_DATABASE_ODATA_VERIFY_TLS:
        return
    next_transport["verify_tls"] = BASELINE_DATABASE_ODATA_VERIFY_TLS
    metadata["odata_transport"] = next_transport
    database.metadata = metadata
    database.save(update_fields=["metadata", "updated_at"])


def _resolve_root_organization(*, tenant: Tenant) -> Organization:
    organization = Organization.objects.filter(tenant=tenant, inn=ROOT_ORGANIZATION_INN).first()
    if organization is None:
        organization = Organization.objects.create(
            tenant=tenant,
            name=ROOT_ORGANIZATION_NAME,
            inn=ROOT_ORGANIZATION_INN,
        )
    return organization


def _resolve_target_organization(*, tenant: Tenant, database: Database) -> Organization:
    organization = Organization.objects.filter(tenant=tenant, database=database).first()
    if organization is None:
        organization = Organization.objects.filter(tenant=tenant, inn=TARGET_ORGANIZATION_INN).first()
    if organization is None:
        organization = Organization.objects.create(
            tenant=tenant,
            database=database,
            name=TARGET_ORGANIZATION_NAME,
            inn=TARGET_ORGANIZATION_INN,
        )
    elif organization.database_id != database.id:
        organization.database = database
        organization.save(update_fields=["database", "updated_at"])
    return organization


def _resolve_actor(*, username: str):
    user = get_user_model().objects.filter(username=username).first()
    if user is None:
        raise ValueError(f"Actor user '{username}' not found.")
    return user


def _resolve_service_mapping(*, database: Database) -> InfobaseUserMapping:
    mappings = list(
        InfobaseUserMapping.objects.filter(
            database=database,
            is_service=True,
            user__isnull=True,
        ).order_by("created_at", "id")[:2]
    )
    if len(mappings) != 1:
        raise ValueError(f"Expected exactly one service InfobaseUserMapping for database '{database.id}'.")
    mapping = mappings[0]
    if not str(mapping.ib_username or "").strip() or not str(mapping.ib_password or "").strip():
        raise ValueError(f"Service InfobaseUserMapping for database '{database.id}' is incomplete.")
    return mapping


def _upsert_pool(*, tenant: Tenant) -> tuple[OrganizationPool, str]:
    pool = OrganizationPool.objects.filter(tenant=tenant, code=BASELINE_POOL_CODE).first()
    if pool is None:
        return (
            OrganizationPool.objects.create(tenant=tenant, code=BASELINE_POOL_CODE, name=BASELINE_POOL_NAME),
            "created",
        )
    if pool.name != BASELINE_POOL_NAME:
        pool.name = BASELINE_POOL_NAME
        pool.save(update_fields=["name", "updated_at"])
        return pool, "updated"
    return pool, "unchanged"


def _upsert_topology(*, pool: OrganizationPool, root_org: Organization, target_org: Organization, policy: dict[str, Any]) -> None:
    PoolEdgeVersion.objects.filter(pool=pool).delete()
    PoolNodeVersion.objects.filter(pool=pool).delete()
    root_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=root_org,
        effective_from=BASELINE_EFFECTIVE_FROM,
        is_root=True,
    )
    target_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=target_org,
        effective_from=BASELINE_EFFECTIVE_FROM,
        is_root=False,
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=root_node,
        child_node=target_node,
        effective_from=BASELINE_EFFECTIVE_FROM,
        weight=Decimal("1"),
        metadata={"document_policy": policy},
    )
    validate_pool_graph(
        node_ids=[str(root_node.id), str(target_node.id)],
        edge_pairs=[(str(root_node.id), str(target_node.id))],
    )


def _upsert_party(**kwargs: Any) -> tuple[PoolMasterParty, str]:
    party = PoolMasterParty.objects.filter(
        tenant=kwargs["tenant"],
        canonical_id=kwargs["canonical_id"],
    ).first()
    return _upsert_model(instance=party or PoolMasterParty(), payload=kwargs)


def _upsert_contract(**kwargs: Any) -> tuple[PoolMasterContract, str]:
    contract = PoolMasterContract.objects.filter(
        tenant=kwargs["tenant"],
        canonical_id=kwargs["canonical_id"],
        owner_counterparty=kwargs["owner_counterparty"],
    ).first()
    return _upsert_model(instance=contract or PoolMasterContract(), payload=kwargs)


def _upsert_item(**kwargs: Any) -> tuple[PoolMasterItem, str]:
    item = PoolMasterItem.objects.filter(
        tenant=kwargs["tenant"],
        canonical_id=kwargs["canonical_id"],
    ).first()
    return _upsert_model(instance=item or PoolMasterItem(), payload=kwargs)


def _bind_organization_master_party(*, organization: Organization, party: PoolMasterParty) -> str:
    if organization.master_party_id == party.id:
        return "unchanged"
    organization.master_party = party
    organization.full_clean()
    organization.save(update_fields=["master_party", "updated_at"])
    return "updated"


def _upsert_binding(
    *,
    tenant: Tenant,
    database: Database,
    entity_type: str,
    canonical_id: str,
    ib_ref_key: str,
    ib_catalog_kind: str = "",
    owner_counterparty_canonical_id: str = "",
) -> str:
    binding = PoolMasterDataBinding.objects.filter(
        tenant=tenant,
        database=database,
        entity_type=entity_type,
        canonical_id=canonical_id,
        ib_catalog_kind=ib_catalog_kind,
        owner_counterparty_canonical_id=owner_counterparty_canonical_id,
    ).first()
    payload = {
        "tenant": tenant,
        "database": database,
        "entity_type": entity_type,
        "canonical_id": canonical_id,
        "ib_ref_key": ib_ref_key,
        "ib_catalog_kind": ib_catalog_kind,
        "owner_counterparty_canonical_id": owner_counterparty_canonical_id,
        "sync_status": PoolMasterBindingSyncStatus.UPSERTED,
        "metadata": {"managed_by": BASELINE_ID},
    }
    _, state = _upsert_model(instance=binding or PoolMasterDataBinding(), payload=payload)
    return state


def _ensure_actor_mapping(
    *,
    database: Database,
    actor,
    service_mapping: InfobaseUserMapping,
    actor_ib_username: str,
    actor_ib_password: str,
) -> tuple[InfobaseUserMapping | None, str]:
    mappings = list(
        InfobaseUserMapping.objects.filter(database=database, user=actor).order_by("created_at", "id")[:2]
    )
    if len(mappings) > 1:
        raise ValueError(f"Actor mapping for user '{actor.username}' is ambiguous in database '{database.id}'.")
    mapping = mappings[0] if mappings else None
    normalized_actor_ib_username = str(actor_ib_username or "").strip()
    normalized_actor_ib_password = str(actor_ib_password or "").strip()
    if mapping is None and (not normalized_actor_ib_username or not normalized_actor_ib_password):
        return None, "missing"
    if normalized_actor_ib_username and normalized_actor_ib_username == str(service_mapping.ib_username):
        raise ValueError(
            "Actor IB username must differ from service IB username because database+ib_username is unique."
        )
    payload = {
        "database": database,
        "user": actor,
        "ib_username": normalized_actor_ib_username or str(mapping.ib_username),
        "ib_password": normalized_actor_ib_password or str(mapping.ib_password),
        "ib_display_name": str(service_mapping.ib_display_name or ""),
        "ib_roles": list(mapping.ib_roles if mapping is not None else service_mapping.ib_roles or []),
        "auth_type": mapping.auth_type if mapping is not None else service_mapping.auth_type,
        "is_service": False,
        "notes": f"Bootstrap baseline {BASELINE_ID}",
        "created_by": actor,
        "updated_by": actor,
    }
    return _upsert_model(instance=mapping or InfobaseUserMapping(), payload=payload)


def _upsert_model(*, instance, payload: dict[str, Any]) -> tuple[Any, str]:
    state = "created" if getattr(instance, "pk", None) is None else "unchanged"
    for field_name, value in payload.items():
        if getattr(instance, field_name, None) != value:
            setattr(instance, field_name, value)
            if state != "created":
                state = "updated"
    instance.save()
    return instance, state


def _serialize_auth_coverage(coverage) -> dict[str, Any]:
    return {
        "strategy": coverage.strategy,
        "actor_username": coverage.actor_username,
        "target_database_ids": list(coverage.target_database_ids),
        "missing_database_ids": list(coverage.missing_database_ids),
        "ambiguous_database_ids": list(coverage.ambiguous_database_ids),
        "incomplete_database_ids": list(coverage.incomplete_database_ids),
        "invalid_context": coverage.invalid_context,
        "has_gaps": coverage.has_gaps,
        "resolution_outcome": coverage.resolution_outcome,
    }
