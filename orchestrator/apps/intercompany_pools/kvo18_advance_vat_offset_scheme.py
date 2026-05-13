from __future__ import annotations

import json
from datetime import date
from typing import Any

from django.db import transaction

from apps.templates.workflow.decision_tables import create_decision_table_revision
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
from .kvo18_advance_vat_offset_intake import (
    ADVANCE_INVOICE_KVO01_SLOT,
    ADVANCE_OFFSET_KVO18_SLOT,
    CASH_RECEIPT_ORDER_SLOT,
    DECLARATION_EVIDENCE_SLOT,
    KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
    KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS,
    build_kvo18_advance_vat_offset_intake_schema,
    build_kvo18_advance_vat_offset_policy_config,
)
from .models import (
    BindingProfile,
    BindingProfileRevision,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
    TopologyTemplate,
)
from .topology_template_contract import normalize_topology_template_revision_payload
from .topology_template_store import (
    create_topology_template,
    create_topology_template_revision,
    serialize_topology_template,
)
from .workflow_authoring_contract import build_workflow_definition_ref


KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE = "kvo18-advance-vat-offset"
KVO18_ADVANCE_VAT_OFFSET_SCHEME_VERSION = "kvo18_advance_vat_offset_scheme.v1"
KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE = "kvo18-advance-vat-offset-publication"
KVO18_ADVANCE_VAT_OFFSET_TOPOLOGY_TEMPLATE_CODE = "kvo18-advance-vat-offset"
KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE = "kvo18-advance-vat-offset-intake"
KVO18_ADVANCE_VAT_OFFSET_WORKFLOW_TEMPLATE_NAME = "KVO18 Advance VAT Offset Workflow"
KVO18_ADVANCE_VAT_OFFSET_EFFECTIVE_FROM = date(2026, 1, 1)
KVO18_ADVANCE_VAT_OFFSET_BINDING_ID = "kvo18_advance_vat_offset"

_CASH_RECEIPT_ORDER_ENTITY_NAME = "Document_ПриходныйКассовыйОрдер"
_ADVANCE_INVOICE_ENTITY_NAME = "Document_СчетФактураВыданный"
_TECHNICAL_REALIZATION_ENTITY_NAME = "Document_РеализацияТоваровУслуг"
_DECLARATION_EVIDENCE_ENTITY_NAME = "Evidence_ДекларацияНДС"
_ZERO_GUID = "00000000-0000-0000-0000-000000000000"


def build_kvo18_advance_vat_offset_scheme_metadata() -> dict[str, Any]:
    return {
        "scheme_code": KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE,
        "scheme_version": KVO18_ADVANCE_VAT_OFFSET_SCHEME_VERSION,
        "binding_id": KVO18_ADVANCE_VAT_OFFSET_BINDING_ID,
        "binding_profile_code": KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE,
        "topology_template_code": KVO18_ADVANCE_VAT_OFFSET_TOPOLOGY_TEMPLATE_CODE,
        "schema_template_code": KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE,
        "document_policy_slots": list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS),
        "policy": build_kvo18_advance_vat_offset_policy_config(),
        "staged_controls": [
            {"slot_key": CASH_RECEIPT_ORDER_SLOT, "label": "Создать ПКО"},
            {"slot_key": ADVANCE_INVOICE_KVO01_SLOT, "label": "Создать СФ на аванс"},
            {"slot_key": ADVANCE_OFFSET_KVO18_SLOT, "label": "Сформировать зачет (КВО 18)"},
        ],
        "required_source_provenance": {
            "counterparty_identity": True,
            "contract_identity": True,
            "operation_date": True,
            "source_row_identity": True,
        },
        "acceptance_evidence": {
            "sales_book_kvo01": True,
            "purchase_book_kvo18": True,
            "declaration_projection": True,
        },
    }


def build_kvo18_advance_vat_offset_schema_template_payload() -> dict[str, Any]:
    return {
        "code": KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE,
        "name": "KVO18 Advance VAT Offset Intake",
        "format": PoolSchemaTemplateFormat.JSON,
        "is_public": True,
        "is_active": True,
        "schema": build_kvo18_advance_vat_offset_intake_schema(),
        "metadata": build_kvo18_advance_vat_offset_scheme_metadata(),
    }


def build_kvo18_advance_vat_offset_topology_template_payload() -> dict[str, Any]:
    scheme_metadata = build_kvo18_advance_vat_offset_scheme_metadata()
    return {
        "code": KVO18_ADVANCE_VAT_OFFSET_TOPOLOGY_TEMPLATE_CODE,
        "name": "KVO18 Advance VAT Offset Topology",
        "description": (
            "Template topology for advance VAT offset: cash receipt order, "
            "advance invoice KVO 01, offset KVO 18, and declaration evidence."
        ),
        "metadata": scheme_metadata,
        "revision": {
            "nodes": [
                {
                    "slot_key": CASH_RECEIPT_ORDER_SLOT,
                    "label": "Cash receipt order",
                    "is_root": True,
                    "metadata": {"role": "cash_receipt_order", "stage": 1},
                },
                {
                    "slot_key": ADVANCE_INVOICE_KVO01_SLOT,
                    "label": "Advance invoice KVO 01",
                    "is_root": False,
                    "metadata": {"role": "advance_invoice", "stage": 2, "kvo": "01"},
                },
                {
                    "slot_key": ADVANCE_OFFSET_KVO18_SLOT,
                    "label": "Advance offset KVO 18",
                    "is_root": False,
                    "metadata": {"role": "advance_offset", "stage": 3, "kvo": "18"},
                },
                {
                    "slot_key": DECLARATION_EVIDENCE_SLOT,
                    "label": "Declaration evidence",
                    "is_root": False,
                    "metadata": {"role": "declaration_evidence", "stage": 4},
                },
            ],
            "edges": [
                {
                    "parent_slot_key": CASH_RECEIPT_ORDER_SLOT,
                    "child_slot_key": ADVANCE_INVOICE_KVO01_SLOT,
                    "weight": "1",
                    "document_policy_key": ADVANCE_INVOICE_KVO01_SLOT,
                    "metadata": {"requires_evidence": "cash_receipt_order_ref", "kvo": "01"},
                },
                {
                    "parent_slot_key": ADVANCE_INVOICE_KVO01_SLOT,
                    "child_slot_key": ADVANCE_OFFSET_KVO18_SLOT,
                    "weight": "1",
                    "document_policy_key": ADVANCE_OFFSET_KVO18_SLOT,
                    "metadata": {"requires_evidence": "sales_book_kvo01_evidence", "kvo": "18"},
                },
                {
                    "parent_slot_key": ADVANCE_OFFSET_KVO18_SLOT,
                    "child_slot_key": DECLARATION_EVIDENCE_SLOT,
                    "weight": "1",
                    "document_policy_key": DECLARATION_EVIDENCE_SLOT,
                    "metadata": {"requires_evidence": "purchase_book_kvo18_evidence"},
                },
            ],
            "metadata": scheme_metadata,
        },
    }


def build_kvo18_advance_vat_offset_document_policy(*, slot_key: str) -> dict[str, Any]:
    if slot_key == CASH_RECEIPT_ORDER_SLOT:
        chain_id = "cash_receipt_order_chain"
        document = _document(
            document_id="cash_receipt_order",
            entity_name=_CASH_RECEIPT_ORDER_ENTITY_NAME,
            document_role="cash_receipt_order",
            field_mapping={
                "Date": "advance_row.operation_date",
                "Контрагент_Key": "advance_row.counterparty_ref",
                "ДоговорКонтрагента_Key": "advance_row.contract_ref",
                "СуммаДокумента": "advance_row.amount",
                "СтавкаНДС": "advance_row.vat_rate",
                "СуммаНДС": "advance_row.vat_amount",
                "ВалютаДокумента_Key": "advance_row.currency_ref",
                "Ответственный_Key": _ZERO_GUID,
            },
        )
    elif slot_key == ADVANCE_INVOICE_KVO01_SLOT:
        chain_id = "advance_invoice_kvo01_chain"
        document = _document(
            document_id="advance_invoice_kvo01",
            entity_name=_ADVANCE_INVOICE_ENTITY_NAME,
            document_role="advance_invoice",
            field_mapping={
                "Date": "cash_receipt_order.date",
                "Основание": "cash_receipt_order.ref",
                "КодВидаОперации": "01",
                "Контрагент_Key": "advance_row.counterparty_ref",
                "ДоговорКонтрагента_Key": "advance_row.contract_ref",
                "СуммаДокумента": "cash_receipt_order.amount",
                "СтавкаНДС": "advance_row.vat_rate",
                "СуммаНДС": "advance_row.vat_amount",
            },
        )
    elif slot_key == ADVANCE_OFFSET_KVO18_SLOT:
        chain_id = "advance_offset_kvo18_chain"
        document = _document(
            document_id="technical_realization_for_offset",
            entity_name=_TECHNICAL_REALIZATION_ENTITY_NAME,
            document_role="technical_realization_for_advance_offset",
            field_mapping={
                "Date": "advance_row.operation_date",
                "Контрагент_Key": "advance_row.counterparty_ref",
                "ДоговорКонтрагента_Key": "advance_row.contract_ref",
                "СуммаДокумента": "policy.technical_realization.amount",
                "СуммаВключаетНДС": True,
                "КодВидаОперации": "18",
                "PostOffsetState": "unposted_after_purchase_book_evidence",
            },
            table_parts_mapping={
                "Товары": [
                    {
                        "LineNumber": "advance_row.line_no",
                        "ИдентификаторСтроки": "advance_row.row_id",
                        "Сумма": "advance_row.amount",
                        "СтавкаНДС": "advance_row.vat_rate",
                        "СуммаНДС": "advance_row.vat_amount",
                    }
                ]
            },
        )
    elif slot_key == DECLARATION_EVIDENCE_SLOT:
        chain_id = "declaration_evidence_chain"
        document = _document(
            document_id="vat_declaration_evidence",
            entity_name=_DECLARATION_EVIDENCE_ENTITY_NAME,
            document_role="declaration_evidence",
            field_mapping={
                "SalesBookKVO01Evidence": "advance_invoice.sales_book_kvo01_evidence",
                "PurchaseBookKVO18Evidence": "advance_offset.purchase_book_kvo18_evidence",
                "DeclarationProjection": "declaration.kvo01_kvo18_projection",
            },
        )
    else:
        raise ValueError(f"Unsupported KVO18 advance VAT offset slot '{slot_key}'.")

    policy_config = build_kvo18_advance_vat_offset_policy_config()
    return validate_document_policy_v1(
        policy={
            "version": DOCUMENT_POLICY_VERSION,
            "chains": [
                {
                    "chain_id": chain_id,
                    "metadata": {
                        "scheme_code": KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE,
                        "slot_key": slot_key,
                        "policy_revision": KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
                        "technical_realization": dict(policy_config["technical_realization"]),
                        "declaration_evidence": dict(policy_config["declaration_evidence"]),
                    },
                    "documents": [document],
                }
            ],
            "metadata": {
                "scheme_code": KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE,
                "slot_key": slot_key,
                "policy_revision": KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
                "technical_realization": dict(policy_config["technical_realization"]),
                "declaration_evidence": dict(policy_config["declaration_evidence"]),
            },
        }
    )


def ensure_kvo18_advance_vat_offset_workflow_template(*, created_by=None) -> WorkflowTemplate:
    target_dag = {
        "nodes": [
            {
                "id": "normalize_advance_rows",
                "name": "Normalize KVO18 advance rows",
                "type": "operation",
                "template_id": "pool.kvo18_advance_vat_offset.normalize",
            },
            {
                "id": "create_cash_receipt_order",
                "name": "Create cash receipt order",
                "type": "operation",
                "template_id": "pool.kvo18_advance_vat_offset.cash_receipt_order",
            },
            {
                "id": "create_advance_invoice_kvo01",
                "name": "Create advance invoice KVO 01",
                "type": "operation",
                "template_id": "pool.kvo18_advance_vat_offset.advance_invoice",
            },
            {
                "id": "form_advance_offset_kvo18",
                "name": "Form advance offset KVO 18",
                "type": "operation",
                "template_id": "pool.kvo18_advance_vat_offset.offset",
            },
            {
                "id": "verify_declaration_evidence",
                "name": "Verify declaration evidence",
                "type": "operation",
                "template_id": "pool.kvo18_advance_vat_offset.declaration_evidence",
            },
        ],
        "edges": [
            {"from": "normalize_advance_rows", "to": "create_cash_receipt_order"},
            {"from": "create_cash_receipt_order", "to": "create_advance_invoice_kvo01"},
            {"from": "create_advance_invoice_kvo01", "to": "form_advance_offset_kvo18"},
            {"from": "form_advance_offset_kvo18", "to": "verify_declaration_evidence"},
        ],
    }
    template = (
        WorkflowTemplate.objects.filter(name=KVO18_ADVANCE_VAT_OFFSET_WORKFLOW_TEMPLATE_NAME)
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
        template.description = "System workflow for KVO18 advance VAT offset publication."
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
        name=KVO18_ADVANCE_VAT_OFFSET_WORKFLOW_TEMPLATE_NAME,
        description="System workflow for KVO18 advance VAT offset publication.",
        workflow_type=WorkflowType.SEQUENTIAL,
        dag_structure=target_dag,
        config={"timeout_seconds": 86400, "max_retries": 0},
        is_valid=True,
        is_active=True,
        is_template=False,
        created_by=created_by,
    )


def ensure_kvo18_advance_vat_offset_scheme_assets(
    *,
    tenant: Tenant,
    actor_username: str = "",
    created_by=None,
) -> dict[str, Any]:
    with transaction.atomic():
        schema_template, schema_state = _ensure_schema_template(tenant=tenant)
        topology_template, topology_state = _ensure_topology_template(
            tenant=tenant,
            actor_username=actor_username,
        )
        workflow_template = ensure_kvo18_advance_vat_offset_workflow_template(created_by=created_by)
        decision_refs = []
        decision_states = {}
        for slot_key in KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS:
            decision, decision_state = _ensure_document_policy_decision(
                slot_key=slot_key,
                created_by=created_by,
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
    return {
        "scheme": build_kvo18_advance_vat_offset_scheme_metadata(),
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
                KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS,
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


def _document(
    *,
    document_id: str,
    entity_name: str,
    document_role: str,
    field_mapping: dict[str, Any],
    table_parts_mapping: dict[str, Any] | None = None,
    link_rules: dict[str, Any] | None = None,
    invoice_mode: str = "optional",
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "entity_name": entity_name,
        "document_role": document_role,
        "field_mapping": field_mapping,
        "table_parts_mapping": dict(table_parts_mapping or {}),
        "link_rules": dict(link_rules or {}),
        "invoice_mode": invoice_mode,
    }


def _ensure_schema_template(*, tenant: Tenant) -> tuple[PoolSchemaTemplate, str]:
    payload = build_kvo18_advance_vat_offset_schema_template_payload()
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
    payload = build_kvo18_advance_vat_offset_topology_template_payload()
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


def _ensure_document_policy_decision(*, slot_key: str, created_by=None):
    decision_table_id = f"kvo18_advance_vat_offset_{slot_key}_policy"
    existing = (
        DecisionTable.objects.filter(
            decision_table_id=decision_table_id,
            version_number=1,
        )
        .order_by("-created_at")
        .first()
    )
    policy = build_kvo18_advance_vat_offset_document_policy(slot_key=slot_key)
    contract = {
        "decision_table_id": decision_table_id,
        "decision_key": "document_policy",
        "name": f"KVO18 advance VAT offset {slot_key} document policy",
        "description": f"Document policy slot {slot_key} for {KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE}.",
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
        "source_provenance": {
            "kind": "checked_in_scheme_seed",
            "source_path": "orchestrator/apps/intercompany_pools/kvo18_advance_vat_offset_scheme.py",
        },
    }
    if existing is not None:
        current_contract = {
            "inputs": list(existing.inputs or []),
            "outputs": list(existing.outputs or []),
            "rules": list(existing.rules or []),
        }
        desired_contract = {
            "inputs": contract["inputs"],
            "outputs": contract["outputs"],
            "rules": contract["rules"],
        }
        if _canonical_json(current_contract) == _canonical_json(desired_contract):
            return existing, "unchanged"
        latest = (
            DecisionTable.objects.filter(
                decision_table_id=decision_table_id,
            )
            .order_by("-version_number")
            .first()
        )
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
            "scheme_code": KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE,
            "policy_revision": KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
            "binding_id": KVO18_ADVANCE_VAT_OFFSET_BINDING_ID,
        },
        "role_mapping": {
            "cash_receipt_order": f"topology:{CASH_RECEIPT_ORDER_SLOT}",
            "advance_invoice_kvo01": f"topology:{ADVANCE_INVOICE_KVO01_SLOT}",
            "advance_offset_kvo18": f"topology:{ADVANCE_OFFSET_KVO18_SLOT}",
            "declaration_evidence": f"topology:{DECLARATION_EVIDENCE_SLOT}",
        },
        "metadata": build_kvo18_advance_vat_offset_scheme_metadata(),
    }
    profile = BindingProfile.objects.filter(
        tenant=tenant,
        code=KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE,
    ).first()
    if profile is None:
        return (
            create_canonical_binding_profile(
                tenant=tenant,
                binding_profile={
                    "code": KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE,
                    "name": "KVO18 Advance VAT Offset Publication",
                    "description": "Reusable execution pack for KVO18 advance VAT offset publication.",
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
    "ADVANCE_INVOICE_KVO01_SLOT",
    "ADVANCE_OFFSET_KVO18_SLOT",
    "CASH_RECEIPT_ORDER_SLOT",
    "DECLARATION_EVIDENCE_SLOT",
    "KVO18_ADVANCE_VAT_OFFSET_BINDING_ID",
    "KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE",
    "KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION",
    "KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS",
    "KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE",
    "KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE",
    "KVO18_ADVANCE_VAT_OFFSET_TOPOLOGY_TEMPLATE_CODE",
    "build_kvo18_advance_vat_offset_document_policy",
    "build_kvo18_advance_vat_offset_scheme_metadata",
    "build_kvo18_advance_vat_offset_schema_template_payload",
    "build_kvo18_advance_vat_offset_topology_template_payload",
    "ensure_kvo18_advance_vat_offset_scheme_assets",
    "ensure_kvo18_advance_vat_offset_workflow_template",
]
