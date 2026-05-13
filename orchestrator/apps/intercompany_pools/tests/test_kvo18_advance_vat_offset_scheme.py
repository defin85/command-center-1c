from __future__ import annotations

import io
import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.intercompany_pools.kvo18_advance_vat_offset_document_plan import (
    KVO18_ADVANCE_VAT_OFFSET_DOCUMENT_PLAN_VERSION,
    build_kvo18_advance_vat_offset_compiled_policy_slots,
    compile_kvo18_advance_vat_offset_document_plan,
)
from apps.intercompany_pools.kvo18_advance_vat_offset_intake import (
    ADVANCE_INVOICE_KVO01_SLOT,
    ADVANCE_OFFSET_KVO18_SLOT,
    CASH_RECEIPT_ORDER_SLOT,
    DECLARATION_EVIDENCE_SLOT,
    KVO18_ADVANCE_VAT_OFFSET_INTAKE_SCHEMA_VERSION,
    KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
    KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS,
    KVO18_ADVANCE_VAT_OFFSET_REQUIRED_INTAKE_FIELDS,
    build_kvo18_advance_vat_offset_intake_schema,
    build_kvo18_advance_vat_offset_policy_config,
    normalize_kvo18_advance_vat_offset_batch,
    normalize_kvo18_advance_vat_offset_intake_rows,
)
from apps.intercompany_pools.kvo18_advance_vat_offset_operator_selection import (
    list_kvo18_advance_vat_offset_operator_schemes,
)
from apps.intercompany_pools.kvo18_advance_vat_offset_preview import (
    KVO18_DUPLICATE_ROW_ID,
    build_kvo18_advance_vat_offset_preview,
)
from apps.intercompany_pools.kvo18_advance_vat_offset_scheme import (
    KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE,
    KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE,
    KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE,
    KVO18_ADVANCE_VAT_OFFSET_TOPOLOGY_TEMPLATE_CODE,
    build_kvo18_advance_vat_offset_document_policy,
    build_kvo18_advance_vat_offset_scheme_metadata,
    build_kvo18_advance_vat_offset_topology_template_payload,
    ensure_kvo18_advance_vat_offset_scheme_assets,
)
from apps.intercompany_pools.models import (
    BindingProfile,
    BindingProfileRevision,
    OrganizationPool,
    PoolSchemaTemplate,
    TopologyTemplate,
)
from apps.intercompany_pools.workflow_binding_attachments_store import (
    upsert_pool_workflow_binding_attachment,
)
from apps.templates.workflow.models import DecisionTable
from apps.tenancy.models import Tenant


def _advance_rows() -> list[dict[str, str]]:
    return [
        {
            "counterparty_ref": "counterparty-001",
            "counterparty_name": "Buyer One",
            "contract_ref": "contract-001",
            "contract_name": "Advance Contract",
            "operation_date": "2026-01-15",
            "amount": "1200.00",
            "vat_rate": "20%",
            "vat_amount": "200.00",
            "currency": "RUB",
            "row_id": "advance-1",
            "source_reference": "upload://advance-1",
        },
        {
            "counterparty_ref": "counterparty-001",
            "counterparty_name": "Buyer One",
            "contract_ref": "contract-001",
            "contract_name": "Advance Contract",
            "operation_date": "2026-01-16",
            "amount": "600.00",
            "vat_rate": "20%",
            "vat_amount": "100.00",
            "currency": "RUB",
            "row_id": "advance-2",
            "source_reference": "upload://advance-2",
        },
    ]


def test_kvo18_scheme_metadata_defines_slots_stages_and_policy() -> None:
    metadata = build_kvo18_advance_vat_offset_scheme_metadata()

    assert metadata["scheme_code"] == KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE
    assert metadata["binding_profile_code"] == KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE
    assert metadata["schema_template_code"] == KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE
    assert metadata["document_policy_slots"] == list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS)
    assert [item["slot_key"] for item in metadata["staged_controls"]] == [
        CASH_RECEIPT_ORDER_SLOT,
        ADVANCE_INVOICE_KVO01_SLOT,
        ADVANCE_OFFSET_KVO18_SLOT,
    ]
    assert metadata["policy"]["technical_realization"]["document_state_after_offset"] == (
        "unposted_after_purchase_book_evidence"
    )
    assert metadata["acceptance_evidence"] == {
        "sales_book_kvo01": True,
        "purchase_book_kvo18": True,
        "declaration_projection": True,
    }


def test_kvo18_intake_schema_defines_required_advance_fields_and_stages() -> None:
    schema = build_kvo18_advance_vat_offset_intake_schema()

    assert schema["version"] == KVO18_ADVANCE_VAT_OFFSET_INTAKE_SCHEMA_VERSION
    assert schema["required_fields"] == list(KVO18_ADVANCE_VAT_OFFSET_REQUIRED_INTAKE_FIELDS)
    assert schema["columns"]["counterparty_ref"] == "counterparty_ref"
    assert schema["columns"]["contract_ref"] == "contract_ref"
    assert schema["columns"]["vat_amount"] == "vat_amount"
    assert schema["validation"]["fail_closed"] is True
    assert schema["validation"]["row_identity"]["field"] == "row_id"
    assert schema["staged_states"][-1] == "declaration_evidence_verified"


def test_kvo18_policy_config_makes_technical_realization_explicit() -> None:
    policy = build_kvo18_advance_vat_offset_policy_config()

    assert policy["revision"] == KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION
    assert policy["amount_rule"]["type"] == "sum_normalized_advance_rows"
    assert policy["technical_realization"]["required"] is True
    assert "operator_preview_confirmed" in policy["technical_realization"]["confirmation_gates"]
    assert policy["declaration_evidence"]["document_creation_alone_is_success"] is False


def test_kvo18_intake_normalizes_rows_and_preserves_lineage() -> None:
    rows = normalize_kvo18_advance_vat_offset_intake_rows(rows=_advance_rows())

    assert rows[0].counterparty_ref == "counterparty-001"
    assert rows[0].contract_ref == "contract-001"
    assert rows[0].operation_date == date(2026, 1, 15)
    assert rows[0].amount == Decimal("1200.00")
    assert rows[0].vat_amount == Decimal("200.00")
    assert rows[0].currency == "RUB"
    assert len(rows[0].row_fingerprint) == 64
    assert rows[0].provenance()["row_id"] == "advance-1"


def test_kvo18_intake_fails_closed_for_missing_contract() -> None:
    row = dict(_advance_rows()[0])
    row["contract_ref"] = ""

    with pytest.raises(ValidationError, match="contract_ref"):
        normalize_kvo18_advance_vat_offset_intake_rows(rows=[row])


def test_kvo18_batch_preview_reports_stages_evidence_and_duplicate_diagnostics() -> None:
    rows = _advance_rows()
    rows[1]["row_id"] = "advance-1"
    batch = normalize_kvo18_advance_vat_offset_batch(
        json_payload={"rows": rows},
        source_reference="upload://advances",
        raw_payload_ref="files/advances.json",
        source_metadata={"upload_id": "upl-kvo18"},
    )

    preview = build_kvo18_advance_vat_offset_preview(batch=batch)

    assert preview.policy_revision == KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION
    assert preview.total_amount == "1800.00"
    assert preview.total_vat_amount == "300.00"
    assert preview.stages[CASH_RECEIPT_ORDER_SLOT]["state"] == "ready"
    assert preview.stages[ADVANCE_INVOICE_KVO01_SLOT]["prerequisites"] == [CASH_RECEIPT_ORDER_SLOT]
    assert preview.stages[ADVANCE_OFFSET_KVO18_SLOT]["produces"] == [
        "technical_realization_ref",
        "technical_realization_final_state",
        "purchase_book_kvo18_evidence",
    ]
    assert preview.evidence_requirements["purchase_book_kvo18_required"] is True
    assert preview.diagnostics[0]["code"] == KVO18_DUPLICATE_ROW_ID
    assert preview.as_dict()["content_hash"] == batch.content_hash


def test_kvo18_document_policies_are_valid_and_stage_specific() -> None:
    policy_by_slot = {
        slot_key: build_kvo18_advance_vat_offset_document_policy(slot_key=slot_key)
        for slot_key in KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS
    }

    assert policy_by_slot[CASH_RECEIPT_ORDER_SLOT]["chains"][0]["documents"][0]["entity_name"] == (
        "Document_ПриходныйКассовыйОрдер"
    )
    assert policy_by_slot[ADVANCE_INVOICE_KVO01_SLOT]["chains"][0]["documents"][0]["field_mapping"][
        "КодВидаОперации"
    ] == "01"
    assert policy_by_slot[ADVANCE_OFFSET_KVO18_SLOT]["metadata"]["technical_realization"][
        "document_state_after_offset"
    ] == "unposted_after_purchase_book_evidence"
    assert policy_by_slot[DECLARATION_EVIDENCE_SLOT]["metadata"]["declaration_evidence"][
        "purchase_book_kvo18_required"
    ] is True


def test_kvo18_document_plan_covers_stages_lineage_and_idempotency() -> None:
    batch = normalize_kvo18_advance_vat_offset_batch(json_payload={"rows": _advance_rows()})
    preview = build_kvo18_advance_vat_offset_preview(batch=batch)
    artifact = compile_kvo18_advance_vat_offset_document_plan(preview=preview)

    assert artifact["version"] == KVO18_ADVANCE_VAT_OFFSET_DOCUMENT_PLAN_VERSION
    assert artifact["policy_revision"] == KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION
    assert artifact["totals"] == {
        "row_count": 2,
        "total_amount": "1800.00",
        "total_vat_amount": "300.00",
        "currency": "RUB",
    }
    assert [ref["slot_key"] for ref in artifact["policy_refs"]] == list(
        KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS
    )
    assert artifact["stages"][CASH_RECEIPT_ORDER_SLOT]["state"] == "ready"
    assert artifact["stages"][ADVANCE_OFFSET_KVO18_SLOT]["prerequisites"] == [
        ADVANCE_INVOICE_KVO01_SLOT,
        "operator_preview_confirmation",
    ]
    assert artifact["lineage"]["final_acceptance"] == {
        "sales_book_kvo01_required": True,
        "purchase_book_kvo18_required": True,
        "declaration_projection_required": True,
        "document_creation_alone_is_success": False,
    }
    assert artifact["partial_failure_policy"]["silent_partial_offset_allowed"] is False
    assert artifact["idempotency"] == compile_kvo18_advance_vat_offset_document_plan(
        preview=preview
    )["idempotency"]
    assert artifact["compile_summary"] == {
        "slots_count": 4,
        "stages_count": 4,
        "documents_count": 4,
        "diagnostics_count": 0,
    }


def test_kvo18_document_plan_fails_when_policy_slot_is_missing() -> None:
    batch = normalize_kvo18_advance_vat_offset_batch(json_payload={"rows": _advance_rows()})
    preview = build_kvo18_advance_vat_offset_preview(batch=batch)
    slots = build_kvo18_advance_vat_offset_compiled_policy_slots()
    slots.pop(ADVANCE_OFFSET_KVO18_SLOT)

    with pytest.raises(ValueError, match=ADVANCE_OFFSET_KVO18_SLOT):
        compile_kvo18_advance_vat_offset_document_plan(
            preview=preview,
            compiled_policy_slots=slots,
        )


def test_kvo18_topology_template_links_staged_slots_to_policy_slots() -> None:
    payload = build_kvo18_advance_vat_offset_topology_template_payload()

    assert payload["code"] == KVO18_ADVANCE_VAT_OFFSET_TOPOLOGY_TEMPLATE_CODE
    revision = payload["revision"]
    assert [node["slot_key"] for node in revision["nodes"]] == list(
        KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS
    )
    assert [node["slot_key"] for node in revision["nodes"] if node["is_root"]] == [
        CASH_RECEIPT_ORDER_SLOT
    ]
    assert {
        (edge["child_slot_key"], edge["document_policy_key"])
        for edge in revision["edges"]
    } == {
        (ADVANCE_INVOICE_KVO01_SLOT, ADVANCE_INVOICE_KVO01_SLOT),
        (ADVANCE_OFFSET_KVO18_SLOT, ADVANCE_OFFSET_KVO18_SLOT),
        (DECLARATION_EVIDENCE_SLOT, DECLARATION_EVIDENCE_SLOT),
    }


@pytest.mark.django_db
def test_kvo18_operator_selection_exposes_ready_pinned_binding() -> None:
    tenant = Tenant.objects.create(
        slug=f"kvo18-selection-{uuid4().hex[:8]}",
        name="KVO18 Selection",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"kvo18-selection-{uuid4().hex[:8]}",
        name="KVO18 Selection Pool",
    )
    assets = ensure_kvo18_advance_vat_offset_scheme_assets(
        tenant=tenant,
        actor_username="architect",
    )
    binding, _ = upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": assets["binding_profile"]["latest_revision_id"],
            "selector": {"direction": "top_down", "mode": "safe", "tags": ["kvo18"]},
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="architect",
    )

    schemes = list_kvo18_advance_vat_offset_operator_schemes(pool=pool)

    assert schemes == [
        {
            "scheme_code": KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE,
            "schema_template_code": KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE,
            "binding_id": binding["binding_id"],
            "binding_profile_revision_id": assets["binding_profile"]["latest_revision_id"],
            "binding_profile_revision_number": 1,
            "policy_revision": KVO18_ADVANCE_VAT_OFFSET_POLICY_REVISION,
            "document_policy_slots": list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS),
            "source_requirements": {
                "counterparty_identity": True,
                "contract_identity": True,
                "operation_date": True,
                "source_row_identity": True,
            },
            "staged_controls": [
                {"slot_key": CASH_RECEIPT_ORDER_SLOT, "label": "Создать ПКО"},
                {"slot_key": ADVANCE_INVOICE_KVO01_SLOT, "label": "Создать СФ на аванс"},
                {"slot_key": ADVANCE_OFFSET_KVO18_SLOT, "label": "Сформировать зачет (КВО 18)"},
            ],
            "preview_capabilities": {
                "stage_blockers": True,
                "technical_realization_policy": True,
                "book_evidence": True,
                "declaration_readiness": True,
            },
        }
    ]


@pytest.mark.django_db
def test_kvo18_operator_selection_hides_binding_without_policy_revision() -> None:
    tenant = Tenant.objects.create(
        slug=f"kvo18-selection-hidden-{uuid4().hex[:8]}",
        name="KVO18 Selection Hidden",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"kvo18-selection-hidden-{uuid4().hex[:8]}",
        name="KVO18 Selection Hidden Pool",
    )
    assets = ensure_kvo18_advance_vat_offset_scheme_assets(
        tenant=tenant,
        actor_username="architect",
    )
    BindingProfileRevision.objects.filter(
        binding_profile_revision_id=assets["binding_profile"]["latest_revision_id"],
    ).update(parameters={"policy_revision": "unexpected"})
    upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": assets["binding_profile"]["latest_revision_id"],
            "selector": {"direction": "top_down", "mode": "safe", "tags": ["kvo18"]},
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="architect",
    )

    assert list_kvo18_advance_vat_offset_operator_schemes(pool=pool) == []


@pytest.mark.django_db
def test_ensure_kvo18_scheme_assets_persists_execution_pack_and_templates() -> None:
    tenant = Tenant.objects.create(
        slug=f"kvo18-scheme-{uuid4().hex[:8]}",
        name="KVO18 Scheme",
    )

    payload = ensure_kvo18_advance_vat_offset_scheme_assets(
        tenant=tenant,
        actor_username="architect",
    )

    assert payload["schema_template"]["code"] == KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE
    assert payload["topology_template"]["code"] == KVO18_ADVANCE_VAT_OFFSET_TOPOLOGY_TEMPLATE_CODE
    assert payload["binding_profile"]["code"] == KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE
    assert payload["binding_profile"]["decision_slots"] == list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS)
    assert payload["binding_profile"]["metadata"]["scheme_code"] == KVO18_ADVANCE_VAT_OFFSET_SCHEME_CODE
    assert payload["binding_profile"]["topology_template_compatibility"] == {
        "status": "compatible",
        "topology_aware_ready": True,
        "covered_slot_keys": list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS),
        "diagnostics": [],
    }

    schema_template = PoolSchemaTemplate.objects.get(
        tenant=tenant,
        code=KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE,
    )
    assert schema_template.metadata["document_policy_slots"] == list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS)
    assert TopologyTemplate.objects.filter(
        tenant=tenant,
        code=KVO18_ADVANCE_VAT_OFFSET_TOPOLOGY_TEMPLATE_CODE,
    ).count() == 1
    assert BindingProfile.objects.filter(
        tenant=tenant,
        code=KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE,
    ).count() == 1
    assert {
        DecisionTable.objects.get(
            decision_table_id=f"kvo18_advance_vat_offset_{slot_key}_policy",
            version_number=1,
        ).rules[0]["outputs"]["document_policy"]["metadata"]["slot_key"]
        for slot_key in KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS
    } == set(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS)

    reapplied = ensure_kvo18_advance_vat_offset_scheme_assets(
        tenant=tenant,
        actor_username="architect",
    )

    assert reapplied["schema_template"]["state"] == "unchanged"
    assert reapplied["topology_template"]["state"] == "unchanged"
    assert reapplied["binding_profile"]["state"] == "unchanged"


@pytest.mark.django_db
def test_bootstrap_kvo18_scheme_dry_run_reports_plan_without_persisting() -> None:
    tenant = Tenant.objects.create(
        slug=f"kvo18-scheme-dry-{uuid4().hex[:8]}",
        name="KVO18 Scheme Dry Run",
    )

    out = io.StringIO()
    call_command(
        "bootstrap_kvo18_advance_vat_offset_scheme",
        "--tenant-slug",
        tenant.slug,
        "--actor-username",
        "architect",
        "--dry-run",
        "--json",
        stdout=out,
    )
    payload = json.loads(out.getvalue())

    assert payload["dry_run"] is True
    assert payload["tenant"]["slug"] == tenant.slug
    assert payload["binding_profile"]["code"] == KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE
    assert payload["binding_profile"]["decision_slots"] == list(KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS)
    assert not PoolSchemaTemplate.objects.filter(
        tenant=tenant,
        code=KVO18_ADVANCE_VAT_OFFSET_SCHEMA_TEMPLATE_CODE,
    ).exists()
    assert not TopologyTemplate.objects.filter(
        tenant=tenant,
        code=KVO18_ADVANCE_VAT_OFFSET_TOPOLOGY_TEMPLATE_CODE,
    ).exists()
    assert not BindingProfile.objects.filter(
        tenant=tenant,
        code=KVO18_ADVANCE_VAT_OFFSET_BINDING_PROFILE_CODE,
    ).exists()
