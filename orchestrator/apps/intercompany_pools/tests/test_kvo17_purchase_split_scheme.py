from __future__ import annotations

import io
import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.intercompany_pools.kvo17_purchase_split_intake import (
    KVO17_PURCHASE_SPLIT_INTAKE_SCHEMA_VERSION,
    KVO17_PURCHASE_SPLIT_REQUIRED_INTAKE_FIELDS,
    build_kvo17_purchase_split_classifier_config,
    build_kvo17_purchase_split_intake_schema,
    classify_kvo17_purchase_split_row,
    normalize_kvo17_purchase_split_batch,
    normalize_kvo17_purchase_split_intake_rows,
    validate_kvo17_purchase_split_classifier_config,
)
from apps.intercompany_pools.kvo17_purchase_split_scheme import (
    KVO17_PURCHASE_SPLIT_BINDING_ID,
    KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE,
    KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
    KVO17_PURCHASE_SPLIT_POLICY_SLOTS,
    KVO17_PURCHASE_SPLIT_SCHEME_CODE,
    KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE,
    KVO17_PURCHASE_SPLIT_TOPOLOGY_TEMPLATE_CODE,
    PURCHASE_KVO01_SLOT,
    PURCHASE_KVO17_SLOT,
    build_kvo17_purchase_split_document_policy,
    build_kvo17_purchase_split_scheme_metadata,
    build_kvo17_purchase_split_topology_template_payload,
    ensure_kvo17_purchase_split_scheme_assets,
)
from apps.intercompany_pools.kvo17_purchase_split_preview import (
    KVO17_DUPLICATE_ROW_ID,
    build_kvo17_purchase_split_preview,
)
from apps.intercompany_pools.kvo17_purchase_split_document_plan import (
    KVO17_PURCHASE_SPLIT_DOCUMENT_PLAN_VERSION,
    build_kvo17_purchase_split_compiled_policy_slots,
    compile_kvo17_purchase_split_document_plan,
)
from apps.intercompany_pools.kvo17_generated_purchase_intake import (
    KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
    KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
    KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
)
from apps.intercompany_pools.models import (
    BindingProfile,
    BindingProfileRevision,
    OrganizationPool,
    PoolSchemaTemplate,
    TopologyTemplate,
)
from apps.intercompany_pools.kvo17_purchase_split_operator_selection import (
    list_kvo17_purchase_split_operator_schemes,
)
from apps.intercompany_pools.workflow_binding_attachments_store import (
    upsert_pool_workflow_binding_attachment,
)
from apps.templates.workflow.models import DecisionTable
from apps.tenancy.models import Tenant


def test_kvo17_purchase_split_scheme_metadata_names_required_slots_and_classifier() -> None:
    metadata = build_kvo17_purchase_split_scheme_metadata()

    assert metadata["scheme_code"] == KVO17_PURCHASE_SPLIT_SCHEME_CODE
    assert metadata["binding_id"] == KVO17_PURCHASE_SPLIT_BINDING_ID
    assert metadata["binding_profile_code"] == KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE
    assert metadata["schema_template_code"] == KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE
    assert metadata["document_policy_slots"] == [PURCHASE_KVO01_SLOT, PURCHASE_KVO17_SLOT]
    assert metadata["classifier"]["revision"] == KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION
    assert metadata["classifier"]["currency"] == "RUB"
    assert metadata["classifier"]["threshold_amount"] == "100.00"
    assert metadata["classifier"]["branches"] == {
        "01": PURCHASE_KVO01_SLOT,
        "17": PURCHASE_KVO17_SLOT,
    }
    assert metadata["classifier"]["override_policy"]["tenant_override_surface"]["requires_revision"] is True
    assert metadata["required_source_provenance"]["source_supplier_identity"] is True
    assert metadata["technical_identity_workaround"]["preview_required"] is True
    assert metadata["technical_identity_workaround"]["original_supplier_remains_declaration_provenance"] is True


def test_kvo17_purchase_split_intake_schema_defines_required_source_fields() -> None:
    schema = build_kvo17_purchase_split_intake_schema()

    assert schema["version"] == KVO17_PURCHASE_SPLIT_INTAKE_SCHEMA_VERSION
    assert schema["rows_path"] == "rows"
    assert schema["required_fields"] == list(KVO17_PURCHASE_SPLIT_REQUIRED_INTAKE_FIELDS)
    assert schema["columns"]["source_document_number"] == "source_document_number"
    assert schema["columns"]["amount"] == "amount"
    assert schema["columns"]["source_kvo_override"] == "source_kvo_override"
    assert schema["validation"]["fail_closed"] is True
    assert schema["validation"]["row_identity"]["field"] == "row_id"
    assert "row_fingerprint" in schema["provenance"]["preserve_fields"]


def test_kvo17_purchase_split_intake_normalizes_rows_and_preserves_provenance() -> None:
    rows = normalize_kvo17_purchase_split_intake_rows(
        rows=[
            {
                "source_document_number": "UT-42",
                "source_document_date": "2026-01-15",
                "source_supplier_ref": "supplier-001",
                "source_supplier_name": "Supplier One",
                "source_supplier_inn": "7701000001",
                "amount": "100,00",
                "vat_amount": "20.00",
                "vat_rate": "20%",
                "currency": "rub",
                "row_id": "line-1",
                "source_kvo_override": "17",
            }
        ]
    )

    row = rows[0]
    assert row.source_document_number == "UT-42"
    assert row.source_document_date == date(2026, 1, 15)
    assert row.source_supplier_ref == "supplier-001"
    assert row.amount == Decimal("100.00")
    assert row.vat_amount == Decimal("20.00")
    assert row.currency == "RUB"
    assert row.source_kvo_override == "17"
    assert len(row.row_fingerprint) == 64
    assert row.provenance() == {
        "source_document_number": "UT-42",
        "source_document_date": "2026-01-15",
        "source_supplier_ref": "supplier-001",
        "source_supplier_name": "Supplier One",
        "source_supplier_inn": "7701000001",
        "row_id": "line-1",
        "row_fingerprint": row.row_fingerprint,
    }


def test_kvo17_purchase_split_intake_fails_closed_for_missing_identity() -> None:
    with pytest.raises(ValidationError, match="source_document_number"):
        normalize_kvo17_purchase_split_intake_rows(
            rows=[
                {
                    "source_document_number": "",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "100.00",
                    "vat_amount": "20.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-1",
                }
            ]
        )


def test_kvo17_purchase_split_intake_fails_closed_for_ambiguous_override() -> None:
    with pytest.raises(ValidationError, match="source_kvo_override"):
        normalize_kvo17_purchase_split_intake_rows(
            rows=[
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "100.00",
                    "vat_amount": "20.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-1",
                    "source_kvo_override": "99",
                }
            ]
        )


def test_kvo17_purchase_split_classifier_config_is_versioned_and_validated() -> None:
    config = build_kvo17_purchase_split_classifier_config()
    normalized = validate_kvo17_purchase_split_classifier_config(config=config)

    assert normalized["revision"] == KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION
    assert normalized["currency"] == "RUB"
    assert normalized["threshold_amount"] == Decimal("100.00")
    assert normalized["branches"] == {
        "01": PURCHASE_KVO01_SLOT,
        "17": PURCHASE_KVO17_SLOT,
    }
    assert config["override_policy"]["tenant_override_surface"] == {
        "metadata_key": "classifier_override",
        "requires_revision": True,
        "audit_required": True,
    }


def test_kvo17_purchase_split_classifier_routes_threshold_and_preview_data() -> None:
    rows = normalize_kvo17_purchase_split_intake_rows(
        rows=[
            {
                "source_document_number": "UT-42",
                "source_document_date": "2026-01-15",
                "source_supplier_ref": "supplier-001",
                "source_supplier_name": "Supplier One",
                "amount": "100.00",
                "vat_amount": "20.00",
                "vat_rate": "20%",
                "currency": "RUB",
                "row_id": "line-1",
            },
            {
                "source_document_number": "UT-42",
                "source_document_date": "2026-01-15",
                "source_supplier_ref": "supplier-001",
                "source_supplier_name": "Supplier One",
                "amount": "100.01",
                "vat_amount": "20.00",
                "vat_rate": "20%",
                "currency": "RUB",
                "row_id": "line-2",
            },
        ]
    )

    first = classify_kvo17_purchase_split_row(row=rows[0])
    second = classify_kvo17_purchase_split_row(row=rows[1])

    assert (first.branch, first.kvo, first.rule_id) == (
        PURCHASE_KVO17_SLOT,
        "17",
        "amount_lte_100_rub",
    )
    assert (second.branch, second.kvo, second.rule_id) == (
        PURCHASE_KVO01_SLOT,
        "01",
        "amount_gt_100_rub",
    )
    assert first.preview() == {
        "branch": PURCHASE_KVO17_SLOT,
        "kvo": "17",
        "rule_id": "amount_lte_100_rub",
        "classifier_revision": KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
        "amount": "100.00",
        "currency": "RUB",
        "threshold_amount": "100.00",
        "source_kvo_override": None,
    }


def test_kvo17_purchase_split_classifier_applies_explicit_override() -> None:
    row = normalize_kvo17_purchase_split_intake_rows(
        rows=[
            {
                "source_document_number": "UT-42",
                "source_document_date": "2026-01-15",
                "source_supplier_ref": "supplier-001",
                "source_supplier_name": "Supplier One",
                "amount": "500.00",
                "vat_amount": "100.00",
                "vat_rate": "20%",
                "currency": "RUB",
                "row_id": "line-1",
                "source_kvo_override": "17",
            }
        ]
    )[0]

    classification = classify_kvo17_purchase_split_row(row=row)

    assert (classification.branch, classification.kvo, classification.rule_id) == (
        PURCHASE_KVO17_SLOT,
        "17",
        "source_override_kvo17",
    )


def test_kvo17_purchase_split_classifier_fails_closed_for_invalid_config() -> None:
    config = build_kvo17_purchase_split_classifier_config()
    config["currency"] = "USD"

    with pytest.raises(ValidationError, match="currency"):
        validate_kvo17_purchase_split_classifier_config(config=config)


def test_kvo17_purchase_split_batch_normalization_preserves_row_level_provenance() -> None:
    result = normalize_kvo17_purchase_split_batch(
        json_payload={
            "rows": [
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "100.00",
                    "vat_amount": "20.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-1",
                },
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "250.00",
                    "vat_amount": "50.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-2",
                },
            ]
        },
        source_reference="upload://ut-42",
        raw_payload_ref="files/ut-42.json",
        source_metadata={"upload_id": "upl-42"},
    )

    assert result.source_document_number == "UT-42"
    assert result.source_document_date == date(2026, 1, 15)
    assert result.source_supplier_ref == "supplier-001"
    assert len(result.content_hash) == 64
    assert [row.row_id for row in result.rows] == ["line-1", "line-2"]
    assert [len(row.row_fingerprint) for row in result.rows] == [64, 64]
    assert result.provenance()["rows"] == [row.provenance() for row in result.rows]
    assert result.provenance()["source_metadata"] == {"upload_id": "upl-42"}
    assert result.normalization_summary()["total_amount"] == Decimal("350.00")
    assert result.normalization_summary()["total_vat_amount"] == Decimal("70.00")


def test_kvo17_purchase_split_batch_normalization_fails_closed_for_mixed_source_doc() -> None:
    with pytest.raises(ValidationError, match="one source document"):
        normalize_kvo17_purchase_split_batch(
            json_payload={
                "rows": [
                    {
                        "source_document_number": "UT-42",
                        "source_document_date": "2026-01-15",
                        "source_supplier_ref": "supplier-001",
                        "source_supplier_name": "Supplier One",
                        "amount": "100.00",
                        "vat_amount": "20.00",
                        "vat_rate": "20%",
                        "currency": "RUB",
                        "row_id": "line-1",
                    },
                    {
                        "source_document_number": "UT-43",
                        "source_document_date": "2026-01-15",
                        "source_supplier_ref": "supplier-001",
                        "source_supplier_name": "Supplier One",
                        "amount": "250.00",
                        "vat_amount": "50.00",
                        "vat_rate": "20%",
                        "currency": "RUB",
                        "row_id": "line-2",
                    },
                ]
            }
        )


def test_kvo17_purchase_split_preview_reports_branch_totals_revision_and_provenance() -> None:
    batch = normalize_kvo17_purchase_split_batch(
        json_payload={
            "rows": [
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "100.00",
                    "vat_amount": "20.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-1",
                },
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "250.00",
                    "vat_amount": "50.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-2",
                },
            ]
        }
    )

    preview = build_kvo17_purchase_split_preview(batch=batch)

    assert preview.classifier_revision == KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION
    assert preview.source_document_identity == {"number": "UT-42", "date": "2026-01-15"}
    assert preview.source_supplier_provenance == {
        "ref": "supplier-001",
        "name": "Supplier One",
    }
    assert preview.branches[PURCHASE_KVO17_SLOT]["row_count"] == 1
    assert preview.branches[PURCHASE_KVO17_SLOT]["total_amount"] == "100.00"
    assert preview.branches[PURCHASE_KVO01_SLOT]["row_count"] == 1
    assert preview.branches[PURCHASE_KVO01_SLOT]["total_amount"] == "250.00"
    assert preview.branches[PURCHASE_KVO01_SLOT]["rows"][0]["classification"]["rule_id"] == "amount_gt_100_rub"
    assert preview.diagnostics == []
    assert preview.as_dict()["content_hash"] == batch.content_hash


def test_kvo17_purchase_split_preview_reports_duplicate_source_diagnostics() -> None:
    batch = normalize_kvo17_purchase_split_batch(
        json_payload={
            "rows": [
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "100.00",
                    "vat_amount": "20.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-1",
                },
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "250.00",
                    "vat_amount": "50.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-1",
                },
            ]
        }
    )

    preview = build_kvo17_purchase_split_preview(batch=batch)

    assert preview.diagnostics == [
        {
            "code": KVO17_DUPLICATE_ROW_ID,
            "severity": "error",
            "field": "row_id",
            "value": "line-1",
            "line_numbers": [1, 2],
            "detail": "Duplicate KVO17 purchase split source row_id.",
        }
    ]


def test_kvo17_purchase_split_document_plan_covers_both_slots_and_preserves_provenance() -> None:
    batch = normalize_kvo17_purchase_split_batch(
        json_payload={
            "rows": [
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "100.00",
                    "vat_amount": "20.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-1",
                },
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "250.00",
                    "vat_amount": "50.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-2",
                },
            ]
        }
    )
    preview = build_kvo17_purchase_split_preview(batch=batch)

    artifact = compile_kvo17_purchase_split_document_plan(preview=preview)

    assert artifact["version"] == KVO17_PURCHASE_SPLIT_DOCUMENT_PLAN_VERSION
    assert artifact["classifier_revision"] == KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION
    assert artifact["source_document_identity"] == {"number": "UT-42", "date": "2026-01-15"}
    assert artifact["source_supplier_provenance"] == {
        "ref": "supplier-001",
        "name": "Supplier One",
    }
    assert artifact["lineage"]["declaration_export"] == {
        "source_document_identity": {"number": "UT-42", "date": "2026-01-15"},
        "source_supplier_provenance": {
            "ref": "supplier-001",
            "name": "Supplier One",
        },
        "supplier_role": "original_declaration_supplier",
    }
    assert artifact["lineage"]["technical_posting_audit"] == {
        "technical_identity_workaround_visible": True,
        "silent_supplier_mutation_allowed": False,
        "original_supplier_remains_declaration_provenance": True,
        "policy_slots": [PURCHASE_KVO01_SLOT, PURCHASE_KVO17_SLOT],
    }
    assert [ref["slot_key"] for ref in artifact["policy_refs"]] == [
        PURCHASE_KVO01_SLOT,
        PURCHASE_KVO17_SLOT,
    ]
    assert set(artifact["branches"]) == {PURCHASE_KVO01_SLOT, PURCHASE_KVO17_SLOT}
    kvo17_document = artifact["branches"][PURCHASE_KVO17_SLOT]["documents"][0]
    assert kvo17_document["field_mapping"]["Number"] == "source_document.number"
    assert kvo17_document["field_mapping"]["Date"] == "source_document.date"
    assert kvo17_document["field_mapping"]["Контрагент_Key"] == "source_supplier.ref"
    assert kvo17_document["source_supplier_provenance"]["ref"] == "supplier-001"
    assert kvo17_document["declaration_export"]["source_supplier_provenance"]["ref"] == "supplier-001"
    assert kvo17_document["declaration_export"]["supplier_role"] == "original_declaration_supplier"
    assert (
        kvo17_document["technical_posting_audit"]["original_supplier_remains_declaration_provenance"]
        is True
    )
    assert kvo17_document["technical_identity_workaround"]["silent_supplier_mutation_allowed"] is False
    assert kvo17_document["rows"][0]["row_id"] == "line-1"
    assert artifact["branches"][PURCHASE_KVO01_SLOT]["row_count"] == 1
    assert artifact["branches"][PURCHASE_KVO17_SLOT]["row_count"] == 1
    assert artifact["compile_summary"] == {
        "slots_count": 2,
        "branches_count": 2,
        "documents_count": 2,
        "diagnostics_count": 0,
    }


def test_kvo17_purchase_split_document_plan_is_deterministic() -> None:
    batch = normalize_kvo17_purchase_split_batch(
        json_payload={
            "rows": [
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "100.00",
                    "vat_amount": "20.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-1",
                }
            ]
        }
    )
    preview = build_kvo17_purchase_split_preview(batch=batch)
    slots = build_kvo17_purchase_split_compiled_policy_slots()

    assert compile_kvo17_purchase_split_document_plan(
        preview=preview,
        compiled_policy_slots=slots,
    ) == compile_kvo17_purchase_split_document_plan(
        preview=preview,
        compiled_policy_slots=slots,
    )


def test_kvo17_purchase_split_document_plan_fails_when_policy_slot_is_missing() -> None:
    batch = normalize_kvo17_purchase_split_batch(
        json_payload={
            "rows": [
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "100.00",
                    "vat_amount": "20.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-1",
                }
            ]
        }
    )
    preview = build_kvo17_purchase_split_preview(batch=batch)
    slots = build_kvo17_purchase_split_compiled_policy_slots()
    slots.pop(PURCHASE_KVO17_SLOT)

    with pytest.raises(ValueError, match=PURCHASE_KVO17_SLOT):
        compile_kvo17_purchase_split_document_plan(
            preview=preview,
            compiled_policy_slots=slots,
        )


def test_kvo17_purchase_split_document_plan_idempotency_changes_with_classifier_revision() -> None:
    batch = normalize_kvo17_purchase_split_batch(
        json_payload={
            "rows": [
                {
                    "source_document_number": "UT-42",
                    "source_document_date": "2026-01-15",
                    "source_supplier_ref": "supplier-001",
                    "source_supplier_name": "Supplier One",
                    "amount": "100.00",
                    "vat_amount": "20.00",
                    "vat_rate": "20%",
                    "currency": "RUB",
                    "row_id": "line-1",
                }
            ]
        }
    )
    preview_v1 = build_kvo17_purchase_split_preview(batch=batch)
    config_v2 = build_kvo17_purchase_split_classifier_config()
    config_v2["revision"] = "kvo17_purchase_split_classifier.v2"
    preview_v2 = build_kvo17_purchase_split_preview(batch=batch, classifier_config=config_v2)

    artifact_v1_first = compile_kvo17_purchase_split_document_plan(preview=preview_v1)
    artifact_v1_second = compile_kvo17_purchase_split_document_plan(preview=preview_v1)
    artifact_v2 = compile_kvo17_purchase_split_document_plan(preview=preview_v2)

    assert artifact_v1_first["idempotency"] == artifact_v1_second["idempotency"]
    assert artifact_v1_first["idempotency"]["source_document_key"] == "UT-42|2026-01-15|supplier-001"
    assert artifact_v1_first["idempotency"]["classifier_revision"] == KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION
    assert artifact_v2["idempotency"]["classifier_revision"] == "kvo17_purchase_split_classifier.v2"
    assert (
        artifact_v1_first["idempotency"]["idempotency_key"]
        != artifact_v2["idempotency"]["idempotency_key"]
    )
    assert (
        artifact_v1_first["idempotency"]["lineage_revision_ref"]
        != artifact_v2["idempotency"]["lineage_revision_ref"]
    )


@pytest.mark.django_db
def test_kvo17_purchase_split_operator_selection_exposes_ready_pinned_binding() -> None:
    tenant = Tenant.objects.create(
        slug=f"kvo17-selection-{uuid4().hex[:8]}",
        name="KVO17 Selection",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"kvo17-selection-{uuid4().hex[:8]}",
        name="KVO17 Selection Pool",
    )
    assets = ensure_kvo17_purchase_split_scheme_assets(
        tenant=tenant,
        actor_username="architect",
    )
    binding, _ = upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": assets["binding_profile"]["latest_revision_id"],
            "selector": {"direction": "top_down", "mode": "safe", "tags": ["kvo17"]},
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="architect",
    )

    schemes = list_kvo17_purchase_split_operator_schemes(pool=pool)

    assert schemes == [
        {
            "scheme_code": KVO17_PURCHASE_SPLIT_SCHEME_CODE,
            "schema_template_code": KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE,
            "binding_id": binding["binding_id"],
            "binding_profile_revision_id": assets["binding_profile"]["latest_revision_id"],
            "binding_profile_revision_number": 1,
            "classifier_revision": KVO17_PURCHASE_SPLIT_CLASSIFIER_REVISION,
            "document_policy_slots": [PURCHASE_KVO01_SLOT, PURCHASE_KVO17_SLOT],
            "source_requirements": {
                "source_supplier_identity": True,
                "source_document_number": True,
                "source_document_date": True,
                "source_row_identity": True,
            },
            "preview_capabilities": {
                "branch_totals": True,
                "duplicate_source_diagnostics": True,
                "source_document_identity": True,
                "source_supplier_provenance": True,
            },
            "generated_purchase_mode": {
                "available": True,
                "source_type": KVO17_GENERATED_PURCHASE_SOURCE_TYPE,
                "request_schema_version": KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
                "manifest_version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
                "document_policy_slots": [PURCHASE_KVO01_SLOT, PURCHASE_KVO17_SLOT],
                "blocking_diagnostics": [],
            },
        }
    ]


@pytest.mark.django_db
def test_kvo17_purchase_split_operator_selection_hides_binding_without_classifier_revision() -> None:
    tenant = Tenant.objects.create(
        slug=f"kvo17-selection-hidden-{uuid4().hex[:8]}",
        name="KVO17 Selection Hidden",
    )
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code=f"kvo17-selection-hidden-{uuid4().hex[:8]}",
        name="KVO17 Selection Hidden Pool",
    )
    assets = ensure_kvo17_purchase_split_scheme_assets(
        tenant=tenant,
        actor_username="architect",
    )
    BindingProfileRevision.objects.filter(
        binding_profile_revision_id=assets["binding_profile"]["latest_revision_id"],
    ).update(parameters={"classifier_revision": "unexpected"})
    upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": assets["binding_profile"]["latest_revision_id"],
            "selector": {"direction": "top_down", "mode": "safe", "tags": ["kvo17"]},
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="architect",
    )

    assert list_kvo17_purchase_split_operator_schemes(pool=pool) == []


def test_kvo17_purchase_split_topology_template_links_edges_to_policy_slots() -> None:
    payload = build_kvo17_purchase_split_topology_template_payload()

    assert payload["code"] == KVO17_PURCHASE_SPLIT_TOPOLOGY_TEMPLATE_CODE
    revision = payload["revision"]
    assert [node["slot_key"] for node in revision["nodes"]] == [
        "source_supplier",
        PURCHASE_KVO01_SLOT,
        PURCHASE_KVO17_SLOT,
    ]
    assert [node["slot_key"] for node in revision["nodes"] if node["is_root"]] == ["source_supplier"]
    assert {
        (edge["child_slot_key"], edge["document_policy_key"], edge["metadata"]["kvo"])
        for edge in revision["edges"]
    } == {
        (PURCHASE_KVO01_SLOT, PURCHASE_KVO01_SLOT, "01"),
        (PURCHASE_KVO17_SLOT, PURCHASE_KVO17_SLOT, "17"),
    }


def test_kvo17_purchase_split_document_policies_are_valid_and_preserve_provenance() -> None:
    for slot_key, expected_kvo in ((PURCHASE_KVO01_SLOT, "01"), (PURCHASE_KVO17_SLOT, "17")):
        policy = build_kvo17_purchase_split_document_policy(slot_key=slot_key)

        assert policy["version"] == "document_policy.v1"
        assert policy["metadata"]["slot_key"] == slot_key
        assert policy["metadata"]["kvo"] == expected_kvo
        assert policy["metadata"]["technical_identity_workaround"]["silent_supplier_mutation_allowed"] is False
        chain = policy["chains"][0]
        document = chain["documents"][0]
        assert chain["metadata"]["source_document_identity"]["preserve_original"] is True
        assert chain["metadata"]["source_supplier_provenance"]["declaration_provenance"] is True
        assert document["field_mapping"]["КодВидаОперации"] == expected_kvo
        assert document["field_mapping"]["Date"] == "source_document.date"
        assert document["field_mapping"]["Number"] == "source_document.number"
        assert document["field_mapping"]["Контрагент_Key"] == "source_supplier.ref"
        assert document["field_mapping"]["Организация_Key"] == "master_data.party.edge.child.organization.ref"


@pytest.mark.django_db
def test_ensure_kvo17_purchase_split_scheme_assets_persists_execution_pack_and_templates() -> None:
    tenant = Tenant.objects.create(
        slug=f"kvo17-scheme-{uuid4().hex[:8]}",
        name="KVO17 Scheme",
    )

    payload = ensure_kvo17_purchase_split_scheme_assets(
        tenant=tenant,
        actor_username="architect",
    )

    assert payload["schema_template"]["code"] == KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE
    assert payload["topology_template"]["code"] == KVO17_PURCHASE_SPLIT_TOPOLOGY_TEMPLATE_CODE
    assert payload["binding_profile"]["code"] == KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE
    assert payload["binding_profile"]["decision_slots"] == list(KVO17_PURCHASE_SPLIT_POLICY_SLOTS)
    assert payload["binding_profile"]["metadata"]["scheme_code"] == KVO17_PURCHASE_SPLIT_SCHEME_CODE
    assert payload["binding_profile"]["topology_template_compatibility"] == {
        "status": "compatible",
        "topology_aware_ready": True,
        "covered_slot_keys": list(KVO17_PURCHASE_SPLIT_POLICY_SLOTS),
        "diagnostics": [],
    }

    schema_template = PoolSchemaTemplate.objects.get(tenant=tenant, code=KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE)
    assert schema_template.metadata["document_policy_slots"] == list(KVO17_PURCHASE_SPLIT_POLICY_SLOTS)
    assert TopologyTemplate.objects.filter(tenant=tenant, code=KVO17_PURCHASE_SPLIT_TOPOLOGY_TEMPLATE_CODE).count() == 1
    assert BindingProfile.objects.filter(tenant=tenant, code=KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE).count() == 1
    assert {
        DecisionTable.objects.get(
            decision_table_id=f"kvo17_purchase_split_{slot_key}_policy",
            version_number=1,
        ).rules[0]["outputs"]["document_policy"]["metadata"]["kvo"]
        for slot_key in KVO17_PURCHASE_SPLIT_POLICY_SLOTS
    } == {"01", "17"}

    reapplied = ensure_kvo17_purchase_split_scheme_assets(
        tenant=tenant,
        actor_username="architect",
    )

    assert reapplied["schema_template"]["state"] == "unchanged"
    assert reapplied["topology_template"]["state"] == "unchanged"
    assert reapplied["binding_profile"]["state"] == "unchanged"
    assert PoolSchemaTemplate.objects.filter(tenant=tenant, code=KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE).count() == 1
    assert TopologyTemplate.objects.filter(tenant=tenant, code=KVO17_PURCHASE_SPLIT_TOPOLOGY_TEMPLATE_CODE).count() == 1
    assert BindingProfile.objects.filter(tenant=tenant, code=KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE).count() == 1


@pytest.mark.django_db
def test_bootstrap_kvo17_purchase_split_scheme_dry_run_reports_plan_without_persisting() -> None:
    tenant = Tenant.objects.create(
        slug=f"kvo17-scheme-dry-{uuid4().hex[:8]}",
        name="KVO17 Scheme Dry Run",
    )

    out = io.StringIO()
    call_command(
        "bootstrap_kvo17_purchase_split_scheme",
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
    assert payload["binding_profile"]["code"] == KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE
    assert payload["binding_profile"]["decision_slots"] == list(KVO17_PURCHASE_SPLIT_POLICY_SLOTS)
    assert not PoolSchemaTemplate.objects.filter(tenant=tenant, code=KVO17_PURCHASE_SPLIT_SCHEMA_TEMPLATE_CODE).exists()
    assert not TopologyTemplate.objects.filter(tenant=tenant, code=KVO17_PURCHASE_SPLIT_TOPOLOGY_TEMPLATE_CODE).exists()
    assert not BindingProfile.objects.filter(tenant=tenant, code=KVO17_PURCHASE_SPLIT_BINDING_PROFILE_CODE).exists()
