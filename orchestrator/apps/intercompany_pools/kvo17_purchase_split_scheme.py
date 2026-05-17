from __future__ import annotations

import json
from datetime import date
from typing import Any, Mapping

from django.db import transaction

from apps.databases.models import Database
from apps.templates.workflow.decision_tables import (
    build_decision_table_metadata_context,
    build_decision_table_source_provenance,
    create_decision_table_revision,
)
from apps.templates.workflow.models import DecisionTable, WorkflowTemplate, WorkflowType
from apps.templates.workflow.schema import DAGStructure
from apps.tenancy.models import Tenant

from .binding_profiles_store import (
    create_canonical_binding_profile,
    get_canonical_binding_profile,
    revise_canonical_binding_profile,
)
from .binding_profile_topology_compatibility import (
    strip_execution_pack_topology_compatibility_metadata,
)
from .document_policy_contract import DOCUMENT_POLICY_VERSION, validate_document_policy_v1
from .kvo17_purchase_split_intake import (
    KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
    PURCHASE_KVO01_SLOT,
    PURCHASE_KVO17_SLOT,
    build_kvo17_purchase_split_classifier_config,
    build_kvo17_purchase_split_intake_schema,
)
from .kvo17_generated_purchase_intake import (
    KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
    KVO17_GENERATED_PURCHASE_POLICY_SLOT,
    KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
    KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
)
from .models import (
    BindingProfile,
    BindingProfileRevision,
    PoolODataMetadataCatalogSnapshot,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
    TopologyTemplate,
)
from .metadata_catalog import (
    build_metadata_catalog_api_payload,
    read_existing_metadata_catalog_snapshot,
    validate_document_policy_references,
)
from .topology_template_store import (
    create_topology_template,
    create_topology_template_revision,
    serialize_topology_template,
)
from .topology_template_contract import normalize_topology_template_revision_payload
from .workflow_authoring_contract import build_workflow_definition_ref


KVO17_PURCHASE_SPLIT_SCHEME_CODE = "kvo17-purchase-split"
KVO17_PURCHASE_SPLIT_SCHEME_VERSION = "kvo17_purchase_split_scheme.v1"
KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE = "kvo17-purchase-split-publication"
KVO17_PURCHASE_SPLIT_TOPOLOGY_TEMPLATE_CODE = "kvo17-purchase-split"
KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE = "kvo17-purchase-split-intake"
KVO17_PURCHASE_SPLIT_WORKFLOW_TEMPLATE_NAME = "KVO17 Purchase Split Publication Workflow"
KVO17_PURCHASE_SPLIT_EFFECTIVE_FROM = date(2026, 1, 1)
KVO17_PURCHASE_SPLIT_BINDING_ID = "kvo17_purchase_split"
KVO17_PURCHASE_SPLIT_POLICY_SLOTS = (PURCHASE_KVO01_SLOT, PURCHASE_KVO17_SLOT)
KVO17_GENERATED_PURCHASE_PAIR_SLOT = KVO17_GENERATED_PURCHASE_POLICY_SLOT
KVO17_PURCHASE_SPLIT_BINDING_POLICY_SLOTS = (KVO17_GENERATED_PURCHASE_PAIR_SLOT,)

_DOCUMENT_ENTITY_NAME = "Document_ПоступлениеТоваровУслуг"
_PURCHASE_INVOICE_ENTITY_NAME = "Document_СчетФактураПолученный"
_PURCHASE_INVOICE_BASE_DOCUMENT_TYPE = "StandardODATA.Document_ПоступлениеТоваровУслуг"
_ZERO_GUID = "00000000-0000-0000-0000-000000000000"
_DEFAULT_RUB_CURRENCY_REF = "171b30af-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_COUNTERPARTY_ACCOUNT_REF = "020635ce-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_ADVANCE_ACCOUNT_REF = "020635cf-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_COST_ACCOUNT_REF = "02063686-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_TAX_COST_ACCOUNT_REF = "02063686-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_VAT_ACCOUNT_REF = "02063586-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_WAREHOUSE_REF = "62953111-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_CONTRACT_CANONICAL_ID = "osnovnoy"
_DEFAULT_PURCHASE_ITEM_CANONICAL_ID = "packing-service"


def build_kvo17_purchase_split_scheme_metadata() -> dict[str, Any]:
    return {
        "scheme_code": KVO17_PURCHASE_SPLIT_SCHEME_CODE,
        "scheme_version": KVO17_PURCHASE_SPLIT_SCHEME_VERSION,
        "binding_id": KVO17_PURCHASE_SPLIT_BINDING_ID,
        "binding_profile_code": KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE,
        "topology_template_code": KVO17_PURCHASE_SPLIT_TOPOLOGY_TEMPLATE_CODE,
        "schema_template_code": KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE,
        "document_policy_slots": list(KVO17_PURCHASE_SPLIT_POLICY_SLOTS),
        "binding_policy_slots": list(KVO17_PURCHASE_SPLIT_BINDING_POLICY_SLOTS),
        "classifier": build_kvo17_purchase_split_classifier_config(),
        "required_source_provenance": {
            "source_supplier_identity": True,
            "source_document_number": True,
            "source_document_date": True,
            "source_row_identity": True,
        },
        "technical_identity_workaround": {
            "allowed": True,
            "preview_required": True,
            "audit_required": True,
            "original_supplier_remains_declaration_provenance": True,
        },
        "generated_purchase_mode": {
            "supported": True,
            "source_type": KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
            "request_schema_version": KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
            "manifest_version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
            "document_policy_slots": list(KVO17_PURCHASE_SPLIT_BINDING_POLICY_SLOTS),
            "publication_policy_slot": KVO17_GENERATED_PURCHASE_PAIR_SLOT,
            "requires_publication_readback": True,
        },
    }


def build_kvo17_purchase_split_schema_template_payload() -> dict[str, Any]:
    return {
        "code": KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE,
        "name": "KVO17 Purchase Split Intake",
        "format": PoolSchemaTemplateFormat.JSON,
        "is_public": True,
        "is_active": True,
        "schema": build_kvo17_purchase_split_intake_schema(),
        "metadata": build_kvo17_purchase_split_scheme_metadata(),
    }


def build_kvo17_purchase_split_topology_template_payload() -> dict[str, Any]:
    scheme_metadata = build_kvo17_purchase_split_scheme_metadata()
    return {
        "code": KVO17_PURCHASE_SPLIT_TOPOLOGY_TEMPLATE_CODE,
        "name": "KVO17 Purchase Split Topology",
        "description": (
            "Template topology for one supplier source document split into "
            "KVO 01 and KVO 17 purchase branches."
        ),
        "metadata": scheme_metadata,
        "revision": {
            "nodes": [
                {
                    "slot_key": "source_supplier",
                    "label": "Source supplier",
                    "is_root": True,
                    "metadata": {
                        "role": "source_supplier",
                        "provenance_required": True,
                    },
                },
                {
                    "slot_key": PURCHASE_KVO01_SLOT,
                    "label": "Purchase KVO 01 branch",
                    "is_root": False,
                    "metadata": {
                        "role": "purchase_branch",
                        "kvo": "01",
                    },
                },
                {
                    "slot_key": PURCHASE_KVO17_SLOT,
                    "label": "Purchase KVO 17 branch",
                    "is_root": False,
                    "metadata": {
                        "role": "purchase_branch",
                        "kvo": "17",
                    },
                },
            ],
            "edges": [
                {
                    "parent_slot_key": "source_supplier",
                    "child_slot_key": PURCHASE_KVO01_SLOT,
                    "weight": "1",
                    "min_amount": "100.01",
                    "document_policy_key": PURCHASE_KVO01_SLOT,
                    "metadata": {
                        "branch": PURCHASE_KVO01_SLOT,
                        "kvo": "01",
                        "classifier_revision": KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
                    },
                },
                {
                    "parent_slot_key": "source_supplier",
                    "child_slot_key": PURCHASE_KVO17_SLOT,
                    "weight": "1",
                    "max_amount": "100.00",
                    "document_policy_key": PURCHASE_KVO17_SLOT,
                    "metadata": {
                        "branch": PURCHASE_KVO17_SLOT,
                        "kvo": "17",
                        "classifier_revision": KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
                    },
                },
            ],
            "metadata": scheme_metadata,
        },
    }


def build_kvo17_purchase_split_document_policy(*, slot_key: str) -> dict[str, Any]:
    if slot_key == PURCHASE_KVO01_SLOT:
        kvo_code = "01"
        chain_id = "purchase_kvo01_receipt"
    elif slot_key == PURCHASE_KVO17_SLOT:
        kvo_code = "17"
        chain_id = "purchase_kvo17_receipt"
    else:
        raise ValueError(f"Unsupported KVO17 purchase split slot '{slot_key}'.")

    return validate_document_policy_v1(
        policy={
            "version": DOCUMENT_POLICY_VERSION,
            "chains": [
                {
                    "chain_id": chain_id,
                    "metadata": {
                        "scheme_code": KVO17_PURCHASE_SPLIT_SCHEME_CODE,
                        "slot_key": slot_key,
                        "kvo": kvo_code,
                        "source_document_identity": {
                            "number": "source_document.number",
                            "date": "source_document.date",
                            "preserve_original": True,
                        },
                        "source_supplier_provenance": {
                            "identity": "source_supplier.identity",
                            "declaration_provenance": True,
                        },
                    },
                    "documents": [
                        {
                            "document_id": f"{slot_key}_receipt",
                            "entity_name": _DOCUMENT_ENTITY_NAME,
                            "document_role": "purchase_receipt",
                            "invoice_mode": "optional",
                            "field_mapping": {
                                "Date": "source_document.date",
                                "Number": "source_document.number",
                                "УдалитьКодВидаОперации": kvo_code,
                                "Организация_Key": "master_data.party.edge.child.organization.ref",
                                "Контрагент_Key": "source_supplier.ref",
                                "ДоговорКонтрагента_Key": "source_supplier.contract_ref",
                                "ВалютаДокумента_Key": "source_document.currency_ref",
                                "СуммаДокумента": "branch.total_amount",
                                "СуммаВключаетНДС": True,
                                "Ответственный_Key": _ZERO_GUID,
                            },
                            "table_parts_mapping": {
                                "Товары": [
                                    {
                                        "LineNumber": "source_row.line_number",
                                        "ИдентификаторСтроки": "source_row.identity",
                                        "Номенклатура_Key": "source_row.item_ref",
                                        "Количество": "source_row.quantity",
                                        "Цена": "source_row.price",
                                        "Сумма": "source_row.amount",
                                        "СтавкаНДС": "source_row.vat_rate",
                                        "СуммаНДС": "source_row.vat_amount",
                                    }
                                ]
                            },
                            "link_rules": {},
                        }
                    ],
                }
            ],
            "metadata": {
                "scheme_code": KVO17_PURCHASE_SPLIT_SCHEME_CODE,
                "slot_key": slot_key,
                "kvo": kvo_code,
                "classifier_revision": KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
                "technical_identity_workaround": {
                    "allowed": True,
                    "preview_required": True,
                    "audit_required": True,
                    "silent_supplier_mutation_allowed": False,
                },
            },
        }
    )


def build_kvo17_generated_purchase_pair_document_policy() -> dict[str, Any]:
    return validate_document_policy_v1(
        policy={
            "version": DOCUMENT_POLICY_VERSION,
            "chains": [
                {
                    "chain_id": KVO17_GENERATED_PURCHASE_PAIR_SLOT,
                    "metadata": {
                        "scheme_code": KVO17_PURCHASE_SPLIT_SCHEME_CODE,
                        "slot_key": KVO17_GENERATED_PURCHASE_PAIR_SLOT,
                        "source_type": KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
                        "edge_strategy": "single_edge_multi_document_chain",
                    },
                    "documents": [
                        {
                            "document_id": "generated_purchase_receipt",
                            "entity_name": _DOCUMENT_ENTITY_NAME,
                            "document_role": "purchase",
                            "invoice_mode": "optional",
                            "field_mapping": {
                                "ВидОперации": "Услуги",
                                "Date": "allocation.document_date",
                                "Number": "allocation.document_number",
                                "Организация_Key": "allocation.target_organization_key",
                                "ПодразделениеОрганизации_Key": _ZERO_GUID,
                                "Склад_Key": _DEFAULT_PURCHASE_WAREHOUSE_REF,
                                "Контрагент_Key": "allocation.counterparty_key",
                                "ДоговорКонтрагента_Key": "allocation.contract_key",
                                "ВалютаДокумента_Key": _DEFAULT_RUB_CURRENCY_REF,
                                "СуммаДокумента": "allocation.amount",
                                "СуммаВключаетНДС": True,
                                "СчетУчетаРасчетовСКонтрагентом_Key": (
                                    _DEFAULT_PURCHASE_COUNTERPARTY_ACCOUNT_REF
                                ),
                                "СчетУчетаРасчетовПоАвансам_Key": _DEFAULT_PURCHASE_ADVANCE_ACCOUNT_REF,
                                "Ответственный_Key": _ZERO_GUID,
                                "УдалитьКодВидаОперации": "allocation.kvo",
                                "УдалитьНомерВходящегоСчетаФактуры": "allocation.source_document_number",
                                "УдалитьДатаВходящегоСчетаФактуры": "allocation.document_date",
                            },
                            "table_parts_mapping": {
                                "Услуги": [
                                    {
                                        "LineNumber": "1",
                                        "Номенклатура_Key": "allocation.item_key",
                                        "Содержание": "allocation.service_content",
                                        "Количество": 1,
                                        "Цена": "allocation.amount",
                                        "Сумма": "allocation.amount",
                                        "СтавкаНДС": "allocation.vat_rate",
                                        "СуммаНДС": "allocation.vat_amount",
                                        "СчетЗатрат_Key": _DEFAULT_PURCHASE_COST_ACCOUNT_REF,
                                        "СчетЗатратНУ_Key": _DEFAULT_PURCHASE_TAX_COST_ACCOUNT_REF,
                                        "СчетУчетаНДС_Key": _DEFAULT_PURCHASE_VAT_ACCOUNT_REF,
                                        "ИдентификаторСтроки": "allocation.row_id",
                                    }
                                ]
                            },
                            "link_rules": {},
                        },
                        {
                            "document_id": "generated_purchase_invoice",
                            "entity_name": _PURCHASE_INVOICE_ENTITY_NAME,
                            "document_role": "invoice",
                            "invoice_mode": "required",
                            "link_to": "allocation.receipt_document_id",
                            "field_mapping": {
                                "Date": "allocation.document_date",
                                "Number": "allocation.document_number",
                                "Организация_Key": "allocation.target_organization_key",
                                "ВидСчетаФактуры": "НаПоступление",
                                "Контрагент_Key": "allocation.counterparty_key",
                                "ДоговорКонтрагента_Key": "allocation.contract_key",
                                "НомерВходящегоДокумента": "allocation.source_document_number",
                                "ДатаВходящегоДокумента": "allocation.document_date",
                                "Исправление": False,
                                "СчетФактураБезНДС": False,
                                "КодСпособаПолучения": 1,
                                "КодВидаОперации": "allocation.kvo",
                                "СуммаДокумента": "allocation.amount",
                                "СуммаНДСДокумента": "allocation.vat_amount",
                                "ВалютаДокумента_Key": _DEFAULT_RUB_CURRENCY_REF,
                                "Ответственный_Key": _ZERO_GUID,
                                "РучнаяКорректировка": False,
                                "СформированПриВводеНачальныхОстатковНДС": False,
                                "БланкСтрогойОтчетности": False,
                                "ПредставлениеНомера": "allocation.source_document_number",
                                "НДСПредъявленКВычету": False,
                            },
                            "table_parts_mapping": {
                                "ДокументыОснования": [
                                    {
                                        "LineNumber": "1",
                                        "ДокументОснование": "allocation.receipt_document_ref",
                                        "ДокументОснование_Type": _PURCHASE_INVOICE_BASE_DOCUMENT_TYPE,
                                    }
                                ]
                            },
                            "link_rules": {"depends_on": "allocation.receipt_document_id"},
                        },
                    ],
                }
            ],
            "metadata": {
                "scheme_code": KVO17_PURCHASE_SPLIT_SCHEME_CODE,
                "slot_key": KVO17_GENERATED_PURCHASE_PAIR_SLOT,
                "source_type": KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
                "edge_strategy": "single_edge_multi_document_chain",
                "materialization_defaults": {
                    "contract_canonical_id": _DEFAULT_PURCHASE_CONTRACT_CANONICAL_ID,
                    "item_canonical_id": _DEFAULT_PURCHASE_ITEM_CANONICAL_ID,
                },
            },
        }
    )


def ensure_kvo17_purchase_split_workflow_template(*, created_by=None) -> WorkflowTemplate:
    target_dag = {
        "nodes": [
            {
                "id": "normalize_source",
                "name": "Normalize supplier purchase source",
                "type": "operation",
                "template_id": "pool.prepare_input",
            },
            {
                "id": "split_preview",
                "name": "Build KVO split preview",
                "type": "operation",
                "template_id": "pool.kvo17_purchase_split.preview",
            },
            {
                "id": "publish_generated_purchase_pair",
                "name": "Publish generated KVO17 purchase pair",
                "type": "operation",
                "template_id": "pool.publication_odata",
            },
        ],
        "edges": [
            {"from": "normalize_source", "to": "split_preview"},
            {"from": "split_preview", "to": "publish_generated_purchase_pair"},
        ],
    }
    template = (
        WorkflowTemplate.objects.filter(name=KVO17_PURCHASE_SPLIT_WORKFLOW_TEMPLATE_NAME)
        .order_by("-version_number")
        .first()
    )
    if template is not None:
        normalized_dag = _normalize_dag_structure(template.dag_structure)
        if (
            template.workflow_type == WorkflowType.SEQUENTIAL
            and template.is_valid is True
            and template.is_active is True
            and normalized_dag == target_dag
        ):
            return template
        template.workflow_type = WorkflowType.SEQUENTIAL
        template.description = "System workflow for generated KVO17 purchase publication."
        template.dag_structure = target_dag
        template.is_valid = True
        template.is_active = True
        template.save(
            update_fields=[
                "workflow_type",
                "description",
                "dag_structure",
                "is_valid",
                "is_active",
                "updated_at",
            ]
        )
        return template

    return WorkflowTemplate.objects.create(
        name=KVO17_PURCHASE_SPLIT_WORKFLOW_TEMPLATE_NAME,
        description="System workflow for generated KVO17 purchase publication.",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure=target_dag,
        config={"timeout_seconds": 86400, "max_retries": 0},
        is_valid=True,
        is_active=True,
        is_template=False,
        created_by=created_by,
    )


def ensure_kvo17_purchase_split_scheme_assets(
    *,
    tenant: Tenant,
    actor_username: str = "",
    created_by=None,
    target_database: Database | None = None,
) -> dict[str, Any]:
    with transaction.atomic():
        schema_template, schema_state = _ensure_schema_template(tenant=tenant)
        topology_template, topology_state = _ensure_topology_template(
            tenant=tenant,
            actor_username=actor_username,
        )
        workflow_template = ensure_kvo17_purchase_split_workflow_template(created_by=created_by)
        decision_metadata_context, decision_metadata_snapshot = _resolve_decision_metadata_context(
            tenant=tenant,
            actor_username=actor_username,
            target_database=target_database,
        )
        decision_refs = []
        decision_states = {}
        for slot_key in KVO17_PURCHASE_SPLIT_BINDING_POLICY_SLOTS:
            decision, decision_state = _ensure_document_policy_decision(
                slot_key=slot_key,
                created_by=created_by,
                metadata_context=decision_metadata_context,
                metadata_snapshot=decision_metadata_snapshot,
                source_database=target_database,
            )
            decision_refs.append(
                {
                    "decision_table_id": decision.decision_table_id,
                    "decision_key": decision.decision_key,
                    "slot_key": slot_key,
                    "decision_revision": decision.version_number,
                }
            )
            decision_states[slot_key] = decision_state

        profile, profile_state = _ensure_binding_profile(
            tenant=tenant,
            workflow_template=workflow_template,
            decision_refs=decision_refs,
            actor_username=actor_username,
        )

    latest_revision = profile["latest_revision"]
    payload = {
        "scheme": build_kvo17_purchase_split_scheme_metadata(),
        "schema_template": {
            "id": str(schema_template.id),
            "code": schema_template.code,
            "state": schema_state,
        },
        "topology_template": {
            "id": str(topology_template.id),
            "code": topology_template.code,
            "state": topology_state,
            "latest_revision": serialize_topology_template(topology_template)["latest_revision"],
        },
        "workflow_template": {
            "id": str(workflow_template.id),
            "name": workflow_template.name,
            "revision": workflow_template.version_number,
        },
        "document_policy_decisions": {
            slot_key: {
                "decision_table_id": decision_ref["decision_table_id"],
                "decision_revision": decision_ref["decision_revision"],
                "state": decision_states[slot_key],
            }
            for slot_key, decision_ref in zip(
                KVO17_PURCHASE_SPLIT_BINDING_POLICY_SLOTS,
                decision_refs,
                strict=True,
            )
        },
        "binding_profile": {
            "id": profile["binding_profile_id"],
            "code": profile["code"],
            "state": profile_state,
            "latest_revision_id": latest_revision["binding_profile_revision_id"],
            "latest_revision_number": latest_revision["revision_number"],
            "decision_slots": [item["slot_key"] for item in latest_revision["decisions"]],
            "metadata": latest_revision["metadata"],
            "topology_template_compatibility": latest_revision["topology_template_compatibility"],
        },
    }
    if target_database is not None:
        payload["target_database"] = {
            "id": str(target_database.id),
            "name": target_database.name,
            "base_name": target_database.base_name,
        }
        payload["decision_metadata_context"] = dict(decision_metadata_context or {})
    return payload


def _resolve_decision_metadata_context(
    *,
    tenant: Tenant,
    actor_username: str,
    target_database: Database | None,
) -> tuple[dict[str, Any] | None, PoolODataMetadataCatalogSnapshot | None]:
    if target_database is None:
        return None, None

    snapshot, source, resolution, profile = read_existing_metadata_catalog_snapshot(
        tenant_id=str(tenant.id),
        database=target_database,
        requested_by_username=actor_username,
    )
    payload = build_metadata_catalog_api_payload(
        database=target_database,
        snapshot=snapshot,
        source=source,
        resolution=resolution,
        profile=profile,
    )
    metadata_context = build_decision_table_metadata_context(metadata_context=payload)
    if metadata_context is None:
        raise ValueError("KVO17 decision metadata context could not be resolved for target database.")
    return dict(metadata_context), snapshot


def _ensure_schema_template(*, tenant: Tenant) -> tuple[PoolSchemaTemplate, str]:
    payload = build_kvo17_purchase_split_schema_template_payload()
    template = PoolSchemaTemplate.objects.filter(
        tenant=tenant,
        code=payload["code"],
    ).first()
    defaults = {
        "name": payload["name"],
        "format": payload["format"],
        "is_public": payload["is_public"],
        "is_active": payload["is_active"],
        "schema": payload["schema"],
        "metadata": payload["metadata"],
    }
    if template is None:
        return PoolSchemaTemplate.objects.create(
            tenant=tenant,
            code=payload["code"],
            **defaults,
        ), "created"

    changed_fields = []
    for field, value in defaults.items():
        if getattr(template, field) != value:
            setattr(template, field, value)
            changed_fields.append(field)
    if changed_fields:
        template.save(update_fields=[*changed_fields, "updated_at"])
        return template, "updated"
    return template, "unchanged"


def _ensure_topology_template(
    *,
    tenant: Tenant,
    actor_username: str,
) -> tuple[TopologyTemplate, str]:
    payload = build_kvo17_purchase_split_topology_template_payload()
    template = TopologyTemplate.objects.filter(tenant=tenant, code=payload["code"]).first()
    if template is None:
        template = create_topology_template(
            tenant_id=tenant.id,
            code=payload["code"],
            name=payload["name"],
            description=payload["description"],
            metadata=payload["metadata"],
            revision=payload["revision"],
            actor_username=actor_username,
        )
        return template, "created"

    changed_fields = []
    for field in ("name", "description", "metadata"):
        value = payload[field]
        if getattr(template, field) != value:
            setattr(template, field, value)
            changed_fields.append(field)
    if changed_fields:
        template.updated_by = actor_username
        template.save(update_fields=[*changed_fields, "updated_by", "updated_at"])
        template_state = "updated"
    else:
        template_state = "unchanged"

    latest_revision = (
        template.revisions.order_by("-revision_number")
        .only("topology_template_revision_id", "nodes", "edges", "metadata")
        .first()
    )
    desired_revision = payload["revision"]
    desired_nodes, desired_edges = normalize_topology_template_revision_payload(
        nodes=desired_revision["nodes"],
        edges=desired_revision["edges"],
    )
    desired_revision_snapshot = {
        "nodes": desired_nodes,
        "edges": desired_edges,
        "metadata": dict(desired_revision.get("metadata") or {}),
    }
    current_revision = (
        {
            "nodes": list(latest_revision.nodes or []),
            "edges": list(latest_revision.edges or []),
            "metadata": dict(latest_revision.metadata or {}),
        }
        if latest_revision is not None
        else None
    )
    if _canonical_json(current_revision) != _canonical_json(desired_revision_snapshot):
        create_topology_template_revision(
            tenant_id=tenant.id,
            topology_template_id=template.id,
            revision=desired_revision,
            actor_username=actor_username,
        )
        return template, "revised" if template_state == "unchanged" else template_state
    return template, template_state


def _ensure_document_policy_decision(
    *,
    slot_key: str,
    created_by=None,
    metadata_context: Mapping[str, Any] | None = None,
    metadata_snapshot: PoolODataMetadataCatalogSnapshot | None = None,
    source_database: Database | None = None,
):
    decision_table_id = f"kvo17_purchase_split_{slot_key}_policy"
    if slot_key == KVO17_GENERATED_PURCHASE_PAIR_SLOT:
        policy = build_kvo17_generated_purchase_pair_document_policy()
        name = "KVO17 generated purchase pair document policy"
        description = "Single-edge receipt and invoice policy for KVO17 generated purchases."
    else:
        policy = build_kvo17_purchase_split_document_policy(slot_key=slot_key)
        name = f"KVO17 purchase split {slot_key} document policy"
        description = f"Document policy slot {slot_key} for {KVO17_PURCHASE_SPLIT_SCHEME_CODE}."
    if metadata_snapshot is not None:
        reference_errors = validate_document_policy_references(
            policy=policy,
            snapshot=metadata_snapshot,
            path_prefix=f"document_policy_decisions.{slot_key}",
        )
        if reference_errors:
            first_error = reference_errors[0]
            raise ValueError(
                str(first_error.get("detail") or "KVO17 document policy references are invalid.")
            )
    source_provenance = {
        "kind": "checked_in_scheme_database_seed" if source_database is not None else "checked_in_scheme_seed",
        "source_path": "orchestrator/apps/intercompany_pools/kvo17_purchase_split_scheme.py",
    }
    if source_database is not None:
        source_provenance["child_database_id"] = str(source_database.id)
    contract = {
        "decision_table_id": decision_table_id,
        "decision_key": "document_policy",
        "name": name,
        "description": description,
        "inputs": [],
        "outputs": [{"name": "document_policy", "value_type": "json", "required": True}],
        "rules": [
            {
                "rule_id": "default",
                "priority": 0,
                "conditions": {},
                "outputs": {"document_policy": policy},
            }
        ],
        "source_provenance": source_provenance,
    }
    if metadata_context is not None:
        contract["metadata_context"] = dict(metadata_context)

    latest = (
        DecisionTable.objects.filter(
            decision_table_id=decision_table_id,
        )
        .order_by("-version_number")
        .first()
    )
    if latest is not None:
        current_contract = {
            "inputs": list(latest.inputs or []),
            "outputs": list(latest.outputs or []),
            "rules": list(latest.rules or []),
        }
        desired_contract = {
            "inputs": contract["inputs"],
            "outputs": contract["outputs"],
            "rules": contract["rules"],
        }
        if metadata_context is None and _canonical_json(current_contract) == _canonical_json(desired_contract):
            return latest, "unchanged"

        current_revision = {
            **current_contract,
            "metadata_context": build_decision_table_metadata_context(
                metadata_context=latest.metadata_context
                if isinstance(latest.metadata_context, Mapping)
                else None
            )
            or {},
            "source_provenance": build_decision_table_source_provenance(
                source_provenance=latest.source_provenance
                if isinstance(latest.source_provenance, Mapping)
                else None
            )
            or {},
        }
        desired_revision = {
            **desired_contract,
            "metadata_context": build_decision_table_metadata_context(
                metadata_context=contract.get("metadata_context")
                if isinstance(contract.get("metadata_context"), Mapping)
                else None
            )
            or {},
            "source_provenance": build_decision_table_source_provenance(
                source_provenance=contract.get("source_provenance")
                if isinstance(contract.get("source_provenance"), Mapping)
                else None
            )
            or {},
        }
        if _canonical_json(current_revision) == _canonical_json(desired_revision):
            return latest, "unchanged"
        return (
            create_decision_table_revision(
                contract=contract,
                created_by=created_by,
                parent_version=latest,
            ),
            "revised",
        )
    return create_decision_table_revision(contract=contract, created_by=created_by), "created"


def _ensure_binding_profile(
    *,
    tenant: Tenant,
    workflow_template: WorkflowTemplate,
    decision_refs: list[dict[str, Any]],
    actor_username: str,
) -> tuple[dict[str, Any], str]:
    revision = {
        "workflow": build_workflow_definition_ref(workflow_template=workflow_template).model_dump(
            mode="json",
            exclude_none=True,
        ),
        "decisions": decision_refs,
        "parameters": {
            "scheme_code": KVO17_PURCHASE_SPLIT_SCHEME_CODE,
            "classifier_revision": KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
            "binding_id": KVO17_PURCHASE_SPLIT_BINDING_ID,
            "generated_purchase_supported": True,
            "generated_purchase_source_type": KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
            "generated_purchase_request_schema_version": KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
            "generated_purchase_manifest_version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
        },
        "role_mapping": {
            "source_supplier": "topology:source_supplier",
            "kvo17_generated_purchase_pair": f"policy:{KVO17_GENERATED_PURCHASE_PAIR_SLOT}",
        },
        "metadata": build_kvo17_purchase_split_scheme_metadata(),
    }
    profile = BindingProfile.objects.filter(
        tenant=tenant,
        code=KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE,
    ).first()
    if profile is None:
        return (
            create_canonical_binding_profile(
                tenant=tenant,
                binding_profile={
                    "code": KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE,
                    "name": "KVO17 Generated Purchase Publication",
                    "description": "Reusable execution pack for generated KVO17 purchase publication.",
                    "revision": revision,
                },
                actor_username=actor_username,
            ),
            "created",
        )

    latest = (
        BindingProfileRevision.objects.filter(profile=profile)
        .order_by("-revision_number")
        .first()
    )
    if latest is None:
        raise ValueError(f"Binding profile '{profile.id}' has no revisions.")

    current_revision = {
        "workflow": {
            "workflow_definition_key": latest.workflow_definition_key,
            "workflow_revision_id": latest.workflow_revision_id,
            "workflow_revision": latest.workflow_revision,
            "workflow_name": latest.workflow_name,
        },
        "decisions": list(latest.decisions if isinstance(latest.decisions, list) else []),
        "parameters": dict(latest.parameters if isinstance(latest.parameters, dict) else {}),
        "role_mapping": dict(latest.role_mapping if isinstance(latest.role_mapping, dict) else {}),
        "metadata": strip_execution_pack_topology_compatibility_metadata(
            latest.metadata if isinstance(latest.metadata, dict) else {}
        ),
    }
    desired_revision = dict(revision)
    desired_revision["workflow"] = {
        key: value
        for key, value in dict(desired_revision["workflow"]).items()
        if key != "contract_version"
    }
    if _canonical_json(current_revision) == _canonical_json(desired_revision):
        return get_canonical_binding_profile(tenant=tenant, binding_profile_id=str(profile.id)), "unchanged"
    return (
        revise_canonical_binding_profile(
            tenant=tenant,
            binding_profile_id=str(profile.id),
            revision=revision,
            actor_username=actor_username,
        ),
        "revised",
    )


def _normalize_dag_structure(value: Any) -> dict[str, Any]:
    if isinstance(value, DAGStructure):
        return value.model_dump(mode="json")
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(value, dict):
        return dict(value)
    return {}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


__all__ = [
    "KVO17_PURCHASE_SPLIT_BINDING_ID",
    "KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE",
    "KVO17_PURCHASE_SPLIT_BINDING_POLICY_SLOTS",
    "KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION",
    "KVO17_GENERATED_PURCHASE_PAIR_SLOT",
    "KVO17_PURCHASE_SPLIT_POLICY_SLOTS",
    "KVO17_PURCHASE_SPLIT_SCHEME_CODE",
    "KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE",
    "KVO17_PURCHASE_SPLIT_TOPOLOGY_TEMPLATE_CODE",
    "PURCHASE_KVO01_SLOT",
    "PURCHASE_KVO17_SLOT",
    "build_kvo17_generated_purchase_pair_document_policy",
    "build_kvo17_purchase_split_document_policy",
    "build_kvo17_purchase_split_scheme_metadata",
    "build_kvo17_purchase_split_schema_template_payload",
    "build_kvo17_purchase_split_topology_template_payload",
    "ensure_kvo17_purchase_split_scheme_assets",
    "ensure_kvo17_purchase_split_workflow_template",
]
