from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.databases.models import Database
from apps.intercompany_pools.kvo17_generated_purchase_document_plan import (
    KVO17_GENERATED_PURCHASE_DOCUMENT_PLAN_VERSION,
    KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SLOT,
    compile_kvo17_generated_purchase_document_plan,
    compile_kvo17_generated_purchase_publication_artifact,
)
from apps.intercompany_pools.document_plan_artifact_contract import (
    build_publication_payload_from_document_plan_artifact,
)
from apps.intercompany_pools.kvo17_generated_purchase_intake import (
    KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
    KVO17_GENERATED_PURCHASE_METADATA_KEY,
    KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION,
    build_kvo17_generated_purchase_manifest,
    build_kvo17_generated_purchase_request_schema,
    validate_kvo17_generated_purchase_manifest_reuse,
)
from apps.intercompany_pools.kvo17_generated_purchase_publication_diagnostics import (
    KVO17_GENERATED_PURCHASE_COLLAPSED_DOCUMENTS,
    KVO17_GENERATED_PURCHASE_INVOICE_LINK_MISMATCH,
    verify_kvo17_generated_purchase_readback,
)
from apps.intercompany_pools.models import (
    Organization,
    OrganizationPool,
    PoolBatch,
    PoolBatchKind,
    PoolBatchSourceType,
    PoolEdgeVersion,
    PoolMasterParty,
    PoolNodeVersion,
    PoolRun,
    PoolRunDirection,
    PoolRunMode,
    PoolSchemaTemplate,
    PoolSchemaTemplateFormat,
)
from apps.intercompany_pools.binding_preview import build_pool_workflow_binding_runtime_bundle
from apps.intercompany_pools.kvo17_purchase_split_scheme import ensure_kvo17_purchase_split_scheme_assets
from apps.intercompany_pools.runtime_template_registry import sync_pool_runtime_template_registry
from apps.intercompany_pools.workflow_binding_attachments_store import upsert_pool_workflow_binding_attachment
from apps.tenancy.models import Tenant, TenantMember


def _request_payload() -> dict[str, object]:
    return {
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "seed": "seed-1",
        "counterparties": [
            {
                "counterparty_ref": "supplier-001",
                "counterparty_name": "Supplier One",
                "counterparty_inn": "7701000001",
            },
            {
                "counterparty_ref": "supplier-002",
                "counterparty_name": "Supplier Two",
                "counterparty_inn": "7701000002",
            },
        ],
        "amount_ranges": [
            {"range_key": "small", "min_amount": "50.00", "max_amount": "100.00", "kvo": "17"},
            {"range_key": "large", "min_amount": "200.00", "max_amount": "300.00", "kvo": "01"},
        ],
    }


def test_kvo17_generated_purchase_request_schema_defines_manifest_contract() -> None:
    schema = build_kvo17_generated_purchase_request_schema()

    assert schema["version"] == KVO17_GENERATED_PURCHASE_REQUEST_SCHEMA_VERSION
    assert schema["manifest_version"] == KVO17_GENERATED_PURCHASE_MANIFEST_VERSION
    assert schema["source_type"] == PoolBatchSourceType.KVO17_GENERATED_PURCHASE
    assert schema["required_fields"] == [
        "period_start",
        "period_end",
        "counterparties",
        "amount_ranges",
        "seed",
    ]
    assert schema["validation"]["amount_ranges"]["count"] == 2
    assert schema["validation"]["kvo"]["supported"] == ["01", "17"]
    assert schema["validation"]["invoice_identity"]["shared_per_counterparty_pair"] is True
    assert "row_fingerprint" in schema["manifest_fields"]
    assert "idempotency_key" in schema["manifest_fields"]


def test_kvo17_generated_purchase_manifest_is_deterministic_and_bounds_values() -> None:
    payload = _request_payload()
    manifest = build_kvo17_generated_purchase_manifest(
        request=payload,
        available_counterparty_refs={"supplier-001", "supplier-002"},
    )
    repeated = build_kvo17_generated_purchase_manifest(
        request=payload,
        available_counterparty_refs={"supplier-001", "supplier-002"},
    )

    assert manifest.as_dict() == repeated.as_dict()
    assert manifest.period_start == date(2026, 1, 1)
    assert manifest.period_end == date(2026, 1, 31)
    assert len(manifest.rows) == 4
    assert manifest.normalization_summary()["total_amount_with_vat"] == sum(
        (row.amount for row in manifest.rows),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    rows_by_counterparty = manifest.rows_by_counterparty()
    assert set(rows_by_counterparty) == {"supplier-001", "supplier-002"}
    for rows in rows_by_counterparty.values():
        assert len(rows) == 2
        assert len({row.source_document_number for row in rows}) == 1
        assert len({row.source_document_date for row in rows}) == 1
        assert {row.kvo for row in rows} == {"01", "17"}
        assert {row.range_key for row in rows} == {"small", "large"}
        assert len({row.row_id for row in rows}) == 2
        assert len({row.idempotency_key for row in rows}) == 2
        for row in rows:
            assert date(2026, 1, 1) <= row.source_document_date <= date(2026, 1, 31)
            if row.range_key == "small":
                assert Decimal("50.00") <= row.amount <= Decimal("100.00")
            if row.range_key == "large":
                assert Decimal("200.00") <= row.amount <= Decimal("300.00")
            assert row.as_purchase_split_row()["source_kvo_override"] == row.kvo


def test_kvo17_generated_purchase_manifest_reuse_fails_for_changed_seed() -> None:
    payload = _request_payload()
    manifest = build_kvo17_generated_purchase_manifest(
        request=payload,
        available_counterparty_refs={"supplier-001", "supplier-002"},
    )
    changed_payload = {**payload, "seed": "seed-2"}

    with pytest.raises(ValidationError, match="not reproducible"):
        validate_kvo17_generated_purchase_manifest_reuse(
            request=changed_payload,
            accepted_manifest=manifest.as_dict(),
            available_counterparty_refs={"supplier-001", "supplier-002"},
        )


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda payload: payload.update({"period_end": "2025-12-31"}), "period_end"),
        (lambda payload: payload.update({"counterparties": []}), "counterparty"),
        (
            lambda payload: payload.update(
                {
                    "amount_ranges": [
                        {"range_key": "small", "min_amount": "50.00", "max_amount": "100.00", "kvo": "17"},
                        {"range_key": "large", "min_amount": "200.00", "max_amount": "300.00", "kvo": "17"},
                    ]
                }
            ),
            "distinct KVO",
        ),
        (
            lambda payload: payload.update(
                {
                    "amount_ranges": [
                        {"range_key": "small", "min_amount": "100.00", "max_amount": "50.00", "kvo": "17"},
                        {"range_key": "large", "min_amount": "200.00", "max_amount": "300.00", "kvo": "01"},
                    ]
                }
            ),
            "max_amount",
        ),
    ],
)
def test_kvo17_generated_purchase_manifest_validation(mutator, message: str) -> None:
    payload = _request_payload()
    mutator(payload)

    with pytest.raises(ValidationError, match=message):
        build_kvo17_generated_purchase_manifest(
            request=payload,
            available_counterparty_refs={"supplier-001", "supplier-002"},
        )


def test_kvo17_generated_purchase_manifest_fails_for_stale_counterparty_ref() -> None:
    with pytest.raises(ValidationError, match="stale counterparty refs"):
        build_kvo17_generated_purchase_manifest(
            request=_request_payload(),
            available_counterparty_refs={"supplier-001"},
        )


def test_kvo17_generated_purchase_document_plan_creates_two_targets_per_counterparty() -> None:
    manifest = build_kvo17_generated_purchase_manifest(
        request=_request_payload(),
        available_counterparty_refs={"supplier-001", "supplier-002"},
    )

    artifact = compile_kvo17_generated_purchase_document_plan(manifest=manifest)

    assert artifact["version"] == KVO17_GENERATED_PURCHASE_DOCUMENT_PLAN_VERSION
    assert artifact["manifest_content_hash"] == manifest.content_hash
    assert artifact["compile_summary"]["selected_counterparties"] == 2
    assert artifact["compile_summary"]["documents_count"] == 4
    assert artifact["collapse_readback_policy"]["required"] is True
    assert artifact["edge_strategy"] == {
        "mode": "single_edge_multi_document_chain",
        "requires_parallel_topology_slots": False,
        "documents_per_counterparty": 2,
        "publication_documents_per_counterparty": 4,
        "slot_key": KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SLOT,
        "source_slots": ["purchase_kvo01", "purchase_kvo17"],
    }
    assert artifact["compile_summary"]["invoice_documents_count"] == 4
    assert artifact["compile_summary"]["publication_documents_count"] == 8
    assert artifact["compile_summary"]["chains_count"] == 2
    assert artifact["branches"]["purchase_kvo01"]["row_count"] == 2
    assert artifact["branches"]["purchase_kvo17"]["row_count"] == 2
    assert len(artifact["counterparty_chains"]) == 2
    assert all(chain["documents_count"] == 2 for chain in artifact["counterparty_chains"])
    assert all(chain["shared_invoice_identity"] is True for chain in artifact["counterparty_chains"])
    for counterparty_ref, rows in manifest.rows_by_counterparty().items():
        targets = [
            target
            for target in artifact["targets"]
            if target["source_supplier_provenance"]["ref"] == counterparty_ref
        ]
        assert len(targets) == 2
        assert {target["kvo"] for target in targets} == {"01", "17"}
        assert len({target["source_document_identity"]["number"] for target in targets}) == 1
        assert len({target["source_document_identity"]["date"] for target in targets}) == 1
        assert len({target["runtime_document_identity"]["idempotency_key"] for target in targets}) == 2
        assert {target["row"]["row_id"] for target in targets} == {row.row_id for row in rows}


def test_kvo17_generated_purchase_publication_artifact_uses_one_edge_with_two_documents_per_counterparty() -> None:
    manifest = build_kvo17_generated_purchase_manifest(
        request=_request_payload(),
        available_counterparty_refs={"supplier-001", "supplier-002"},
    )
    run = SimpleNamespace(
        id="run-1",
        pool_id="pool-1",
        period_start=date(2026, 1, 1),
        direction=PoolRunDirection.TOP_DOWN,
        run_input={"batch_id": "batch-1"},
    )

    artifact = compile_kvo17_generated_purchase_publication_artifact(
        run=run,
        manifest=manifest,
        target_database_id="database-1",
        target_organization_id="organization-1",
        topology_version_ref="topology-v1",
        target_party_canonical_id="target-party",
    )

    assert artifact["policy_refs"] == [
        {
            "slot_key": KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SLOT,
            "edge_ref": artifact["targets"][0]["chains"][0]["edge_ref"],
            "policy_version": "document_policy.v1",
            "source": "kvo17_generated_purchase.single_edge_pair_policy",
        }
    ]
    assert artifact["compile_summary"]["compiled_edges"] == 1
    assert artifact["compile_summary"]["chains_count"] == 2
    assert artifact["compile_summary"]["documents_count"] == 8
    assert artifact["compile_summary"]["receipt_documents_count"] == 4
    assert artifact["compile_summary"]["invoice_documents_count"] == 4
    chains = artifact["targets"][0]["chains"]
    assert len(chains) == 2
    assert len({tuple(chain["edge_ref"].items()) for chain in chains}) == 1
    for chain in chains:
        documents = chain["documents"]
        assert len(documents) == 4
        receipt_documents = [
            document
            for document in documents
            if document["entity_name"] == "Document_ПоступлениеТоваровУслуг"
        ]
        invoice_documents = [
            document
            for document in documents
            if document["entity_name"] == "Document_СчетФактураПолученный"
        ]
        assert len(receipt_documents) == 2
        assert len(invoice_documents) == 2
        assert [
            document["document_role"]
            for document in documents
        ] == ["purchase", "invoice", "purchase", "invoice"]
        assert {document["field_mapping"]["УдалитьКодВидаОперации"] for document in receipt_documents} == {"01", "17"}
        assert {document["field_mapping"]["КодВидаОперации"] for document in invoice_documents} == {"01", "17"}
        assert len({document["field_mapping"]["Number"] for document in documents}) == 4
        assert len({document["field_mapping"]["Date"] for document in documents}) == 1
        assert len({document["idempotency_key"] for document in documents}) == 4
        assert len({document["field_mapping"]["УдалитьНомерВходящегоСчетаФактуры"] for document in receipt_documents}) == 1
        assert len({document["field_mapping"]["УдалитьДатаВходящегоСчетаФактуры"] for document in receipt_documents}) == 1
        assert len({document["field_mapping"]["НомерВходящегоДокумента"] for document in invoice_documents}) == 1
        assert len({document["field_mapping"]["ДатаВходящегоДокумента"] for document in invoice_documents}) == 1
        receipt_by_id = {document["document_id"]: document for document in receipt_documents}
        for document in receipt_documents:
            fields = document["field_mapping"]
            service_row = document["table_parts_mapping"]["Услуги"][0]
            assert "КодВидаОперации" not in fields
            assert fields["Организация_Key"] == "master_data.party.target-party.organization.ref"
            assert fields["Контрагент_Key"].startswith("master_data.party.supplier-")
            assert fields["ДоговорКонтрагента_Key"].startswith("master_data.contract.osnovnoy.supplier-")
            assert fields["УдалитьДатаВходящегоСчетаФактуры"] == fields["Date"]
            assert service_row["LineNumber"] == "1"
            assert service_row["Номенклатура_Key"] == "master_data.item.packing-service.ref"
            assert service_row["СтавкаНДС"] == "НДС20"
        for document in invoice_documents:
            fields = document["field_mapping"]
            assert document["invoice_mode"] == "required"
            assert document["link_to"] in receipt_by_id
            assert document["link_rules"] == {"depends_on": document["link_to"]}
            assert fields["ВидСчетаФактуры"] == "НаПоступление"
            assert fields["Организация_Key"] == "master_data.party.target-party.organization.ref"
            assert fields["Контрагент_Key"].startswith("master_data.party.supplier-")
            assert fields["ДоговорКонтрагента_Key"].startswith("master_data.contract.osnovnoy.supplier-")
            assert fields["НомерВходящегоДокумента"] in {
                receipt["field_mapping"]["УдалитьНомерВходящегоСчетаФактуры"]
                for receipt in receipt_documents
            }
            assert fields["ДатаВходящегоДокумента"] == fields["Date"]
            base_row = document["table_parts_mapping"]["ДокументыОснования"][0]
            assert base_row == {
                "LineNumber": "1",
                "ДокументОснование": f"{document['link_to']}.ref",
                "ДокументОснование_Type": "StandardODATA.Document_ПоступлениеТоваровУслуг",
            }

    publication_payload = build_publication_payload_from_document_plan_artifact(artifact=artifact)
    payload_chains = publication_payload["pool_runtime"]["document_chains_by_database"]["database-1"]
    assert len(payload_chains) == 2
    assert all(len(chain["documents"]) == 4 for chain in payload_chains)


@pytest.mark.django_db
def test_kvo17_generated_runtime_bundle_uses_single_edge_artifact_for_one_target_database() -> None:
    sync_pool_runtime_template_registry()
    tenant = Tenant.objects.create(slug="kvo17-generated-runtime", name="KVO17 Generated Runtime")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code="kvo17-generated-runtime",
        name="KVO17 Generated Runtime",
    )
    database = Database.objects.create(
        tenant=tenant,
        name="kvo17-generated-target",
        host="localhost",
        odata_url="http://localhost/odata/standard.odata",
        username="admin",
        password="secret",
    )
    source_organization = Organization.objects.create(
        tenant=tenant,
        name="KVO17 Source",
        inn="7701000099",
    )
    target_organization = Organization.objects.create(
        tenant=tenant,
        database=database,
        name="KVO17 Target",
        inn="7701000100",
    )
    source_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=source_organization,
        effective_from=date(2026, 1, 1),
        is_root=True,
    )
    target_node = PoolNodeVersion.objects.create(
        pool=pool,
        organization=target_organization,
        effective_from=date(2026, 1, 1),
        is_root=False,
    )
    PoolEdgeVersion.objects.create(
        pool=pool,
        parent_node=source_node,
        child_node=target_node,
        effective_from=date(2026, 1, 1),
        metadata={},
    )
    schema_template = PoolSchemaTemplate.objects.create(
        tenant=tenant,
        code="kvo17-generated-runtime",
        name="KVO17 Generated Runtime",
        format=PoolSchemaTemplateFormat.JSON,
        schema={},
        metadata={},
    )
    assets = ensure_kvo17_purchase_split_scheme_assets(
        tenant=tenant,
        actor_username="runtime-test",
    )
    binding, _ = upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": assets["binding_profile"]["latest_revision_id"],
            "selector": {
                "direction": PoolRunDirection.TOP_DOWN,
                "mode": PoolRunMode.SAFE,
                "tags": ["kvo17-generated"],
            },
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="runtime-test",
    )
    manifest = build_kvo17_generated_purchase_manifest(
        request=_request_payload(),
        available_counterparty_refs={"supplier-001", "supplier-002"},
    )
    run_input = {
        "starting_amount": str(manifest.normalization_summary()["total_amount_with_vat"]),
        "start_organization_id": str(source_organization.id),
        KVO17_GENERATED_PURCHASE_METADATA_KEY: {
            "manifest": manifest.as_dict(),
            "document_plan": compile_kvo17_generated_purchase_document_plan(manifest=manifest),
            "document_plan_version": KVO17_GENERATED_PURCHASE_DOCUMENT_PLAN_VERSION,
            "content_hash": manifest.content_hash,
            "request_hash": manifest.request_hash,
        },
    }
    run = PoolRun.objects.create(
        tenant=tenant,
        pool=pool,
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.SAFE,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        run_input=run_input,
    )

    bundle = build_pool_workflow_binding_runtime_bundle(
        tenant=tenant,
        pool=pool,
        pool_workflow_binding_id=binding["binding_id"],
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.SAFE,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        run_input=run_input,
        schema_template=schema_template,
        run=run,
    )

    artifact = bundle["document_plan_artifact"]
    assert artifact["policy_refs"][0]["slot_key"] == KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SLOT
    assert artifact["targets"][0]["database_id"] == str(database.id)
    assert artifact["compile_summary"]["compiled_edges"] == 1
    assert artifact["compile_summary"]["documents_count"] == 8
    assert artifact["compile_summary"]["receipt_documents_count"] == 4
    assert artifact["compile_summary"]["invoice_documents_count"] == 4
    assert bundle["slot_coverage_summary"]["counts"]["resolved"] == 1
    assert bundle["slot_coverage_summary"]["items"][0]["slot_key"] == KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SLOT
    assert all(len(chain["documents"]) == 4 for chain in artifact["targets"][0]["chains"])


def test_kvo17_generated_purchase_readback_blocks_collapsed_document() -> None:
    manifest = build_kvo17_generated_purchase_manifest(
        request=_request_payload(),
        available_counterparty_refs={"supplier-001", "supplier-002"},
    )
    first_pair = manifest.rows_by_counterparty()["supplier-001"]

    result = verify_kvo17_generated_purchase_readback(
        manifest=manifest,
        readback_documents=[
            {
                "document_ref": "doc-1",
                "counterparty_ref": "supplier-001",
                "source_document_number": first_pair[0].source_document_number,
                "source_document_date": first_pair[0].source_document_date.isoformat(),
                "kvo": first_pair[0].kvo,
                "amount": str(first_pair[0].amount),
            }
        ],
    )

    assert result["status"] == "blocked"
    assert KVO17_GENERATED_PURCHASE_COLLAPSED_DOCUMENTS in {
        diagnostic["code"]
        for diagnostic in result["diagnostics"]
    }


def _readback_documents_for_manifest(manifest) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    receipts: list[dict[str, object]] = []
    invoices: list[dict[str, object]] = []
    for rows in manifest.rows_by_counterparty().values():
        for row in rows:
            receipt_ref = f"receipt-{row.counterparty_ref}-{row.kvo}"
            receipts.append(
                {
                    "document_ref": receipt_ref,
                    "counterparty_ref": row.counterparty_ref,
                    "source_document_number": row.source_document_number,
                    "source_document_date": row.source_document_date.isoformat(),
                    "kvo": row.kvo,
                    "amount": str(row.amount),
                    "vat_amount": str(row.vat_amount),
                }
            )
            invoices.append(
                {
                    "document_ref": f"invoice-{row.counterparty_ref}-{row.kvo}",
                    "counterparty_ref": row.counterparty_ref,
                    "source_document_number": row.source_document_number,
                    "source_document_date": row.source_document_date.isoformat(),
                    "kvo": row.kvo,
                    "amount": str(row.amount),
                    "vat_amount": str(row.vat_amount),
                    "linked_receipt_ref": receipt_ref,
                    "linked_receipt_type": "StandardODATA.Document_ПоступлениеТоваровУслуг",
                }
            )
    return receipts, invoices


def test_kvo17_generated_purchase_readback_verifies_linked_invoices() -> None:
    manifest = build_kvo17_generated_purchase_manifest(
        request=_request_payload(),
        available_counterparty_refs={"supplier-001", "supplier-002"},
    )
    receipts, invoices = _readback_documents_for_manifest(manifest)

    result = verify_kvo17_generated_purchase_readback(
        manifest=manifest,
        readback_documents=receipts,
        readback_invoices=invoices,
    )

    assert result["status"] == "verified"
    assert result["summary"]["readback_documents"] == 4
    assert result["summary"]["readback_invoice_documents"] == 4


def test_kvo17_generated_purchase_readback_blocks_invoice_link_mismatch() -> None:
    manifest = build_kvo17_generated_purchase_manifest(
        request=_request_payload(),
        available_counterparty_refs={"supplier-001", "supplier-002"},
    )
    receipts, invoices = _readback_documents_for_manifest(manifest)
    invoices[0]["linked_receipt_ref"] = "receipt-from-other-row"

    result = verify_kvo17_generated_purchase_readback(
        manifest=manifest,
        readback_documents=receipts,
        readback_invoices=invoices,
    )

    assert result["status"] == "blocked"
    assert KVO17_GENERATED_PURCHASE_INVOICE_LINK_MISMATCH in {
        diagnostic["code"]
        for diagnostic in result["diagnostics"]
    }


@pytest.mark.django_db
def test_normalize_pool_batch_intake_builds_kvo17_generated_purchase_batch() -> None:
    from apps.intercompany_pools.batch_intake_normalization import normalize_pool_batch_intake

    tenant = Tenant.objects.create(slug="kvo17-generated", name="KVO17 Generated")
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code="kvo17-generated",
        name="KVO17 Generated",
    )
    PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="supplier-001",
        name="Supplier One",
        inn="7701000001",
        is_counterparty=True,
    )
    PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="supplier-002",
        name="Supplier Two",
        inn="7701000002",
        is_counterparty=True,
    )

    result = normalize_pool_batch_intake(
        pool=pool,
        batch_kind=PoolBatchKind.RECEIPT,
        source_type=PoolBatchSourceType.KVO17_GENERATED_PURCHASE,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        json_payload=_request_payload(),
        source_reference="kvo17-generated-preview",
    )

    metadata = result.provenance.source_metadata[KVO17_GENERATED_PURCHASE_METADATA_KEY]
    assert result.provenance.source_type == PoolBatchSourceType.KVO17_GENERATED_PURCHASE
    assert result.provenance.content_hash == metadata["content_hash"]
    assert result.normalization_summary["processed_rows"] == 4
    assert result.normalization_summary["kvo17_generated_manifest_version"] == KVO17_GENERATED_PURCHASE_MANIFEST_VERSION
    assert [line.external_id for line in result.lines] == [
        row["row_id"]
        for row in metadata["manifest"]["rows"]
    ]
    assert metadata["document_plan"]["compile_summary"]["documents_count"] == 4
    assert metadata["readback_policy"]["fail_closed_on_ambiguous_readback"] is True


@pytest.mark.django_db
def test_create_pool_batch_accepts_kvo17_generated_purchase_source_type() -> None:
    from apps.api_v2.tests.test_intercompany_pool_runs import (
        _create_batch_backed_top_down_scope,
    )
    from apps.intercompany_pools.kvo17_purchase_split_scheme import ensure_kvo17_purchase_split_scheme_assets
    from apps.intercompany_pools.workflow_binding_attachments_store import upsert_pool_workflow_binding_attachment

    tenant = Tenant.objects.create(slug="kvo17-generated-api", name="KVO17 Generated API")
    user = User.objects.create_user(username="kvo17-generated-api", password="pass")
    TenantMember.objects.create(tenant=tenant, user=user, role=TenantMember.ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_CC1C_TENANT_ID=str(tenant.id))
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code="kvo17-generated-api",
        name="KVO17 Generated API",
    )
    assets = ensure_kvo17_purchase_split_scheme_assets(
        tenant=tenant,
        actor_username="kvo17-generated-api",
    )
    binding, _ = upsert_pool_workflow_binding_attachment(
        pool=pool,
        workflow_binding={
            "binding_profile_revision_id": assets["binding_profile"]["latest_revision_id"],
            "selector": {"direction": PoolRunDirection.TOP_DOWN, "mode": PoolRunMode.SAFE, "tags": ["kvo17-generated"]},
            "effective_from": "2026-01-01",
            "status": "active",
        },
        actor_username="kvo17-generated-api",
    )
    start_organization, _, _ = _create_batch_backed_top_down_scope(
        tenant=tenant,
        pool=pool,
    )
    PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="supplier-001",
        name="Supplier One",
        inn="7701000001",
        is_counterparty=True,
    )
    PoolMasterParty.objects.create(
        tenant=tenant,
        canonical_id="supplier-002",
        name="Supplier Two",
        inn="7701000002",
        is_counterparty=True,
    )

    preview_response = client.post(
        "/api/v2/pools/kvo17-generated-purchase/preview/",
        {
            "pool_id": str(pool.id),
            "pool_workflow_binding_id": binding["binding_id"],
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "json_payload": _request_payload(),
        },
        format="json",
    )

    assert preview_response.status_code == 200, preview_response.json()
    preview_payload = preview_response.json()
    assert preview_payload["manifest"]["summary"]["processed_rows"] == 4
    assert preview_payload["document_plan"]["compile_summary"]["documents_count"] == 4

    with patch(
        "apps.api_v2.views.intercompany_pools.start_pool_run_workflow_execution",
        side_effect=lambda *args, **kwargs: SimpleNamespace(run=kwargs["run"]),
    ):
        response = client.post(
            "/api/v2/pools/batches/",
            {
                "pool_id": str(pool.id),
                "batch_kind": PoolBatchKind.RECEIPT,
                "source_type": PoolBatchSourceType.KVO17_GENERATED_PURCHASE,
                "pool_workflow_binding_id": binding["binding_id"],
                "start_organization_id": str(start_organization.id),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "source_reference": "kvo17-generated-preview",
                "source_metadata": {
                    KVO17_GENERATED_PURCHASE_METADATA_KEY: {
                        "accepted_manifest": preview_payload["manifest"],
                    },
                },
                "json_payload": _request_payload(),
            },
            format="json",
        )

    assert response.status_code == 201, response.json()
    payload = response.json()
    batch = PoolBatch.objects.get(id=payload["batch"]["id"])
    run = PoolRun.objects.get(id=payload["run"]["id"])

    assert batch.source_type == PoolBatchSourceType.KVO17_GENERATED_PURCHASE
    assert batch.schema_template_id is None
    assert batch.normalization_summary["processed_rows"] == 4
    batch_context = batch.source_metadata[KVO17_GENERATED_PURCHASE_METADATA_KEY]
    run_context = run.run_input[KVO17_GENERATED_PURCHASE_METADATA_KEY]
    assert batch_context["content_hash"] == preview_payload["content_hash"]
    assert batch_context["accepted_preview"]["provided"] is True
    assert run_context["content_hash"] == batch_context["content_hash"]
    assert run_context["manifest"]["content_hash"] == batch_context["manifest"]["content_hash"]
    assert run_context["document_plan"]["compile_summary"]["documents_count"] == 4
    assert run_context["readback_policy"]["required"] is True


@pytest.mark.django_db
def test_create_pool_batch_rejects_kvo17_generated_purchase_without_binding_capability() -> None:
    from apps.api_v2.tests.test_intercompany_pool_runs import (
        _build_pool_workflow_binding_payload,
        _create_batch_backed_top_down_scope,
        _prepare_pool_runtime_bindings,
    )

    tenant = Tenant.objects.create(slug="kvo17-generated-api-blocked", name="KVO17 Generated API Blocked")
    user = User.objects.create_user(username="kvo17-generated-api-blocked", password="pass")
    TenantMember.objects.create(tenant=tenant, user=user, role=TenantMember.ROLE_ADMIN)
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_CC1C_TENANT_ID=str(tenant.id))
    pool = OrganizationPool.objects.create(
        tenant=tenant,
        code="kvo17-generated-api-blocked",
        name="KVO17 Generated API Blocked",
    )
    binding = _build_pool_workflow_binding_payload(
        pool=pool,
        workflow_definition_key="generic-receipt-publication",
        workflow_revision=1,
        direction=PoolRunDirection.TOP_DOWN,
        mode=PoolRunMode.SAFE,
    )
    binding = _prepare_pool_runtime_bindings(
        tenant=tenant,
        pool=pool,
        bindings=[binding],
        period_start=date(2026, 1, 1),
        actor=user,
    )[0][0]
    start_organization, _, _ = _create_batch_backed_top_down_scope(
        tenant=tenant,
        pool=pool,
    )
    for ref, name in (("supplier-001", "Supplier One"), ("supplier-002", "Supplier Two")):
        PoolMasterParty.objects.create(
            tenant=tenant,
            canonical_id=ref,
            name=name,
            is_counterparty=True,
        )

    response = client.post(
        "/api/v2/pools/batches/",
        {
            "pool_id": str(pool.id),
            "batch_kind": PoolBatchKind.RECEIPT,
            "source_type": PoolBatchSourceType.KVO17_GENERATED_PURCHASE,
            "pool_workflow_binding_id": binding["binding_id"],
            "start_organization_id": str(start_organization.id),
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "json_payload": _request_payload(),
        },
        format="json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "KVO17_GENERATED_PURCHASE_BINDING_UNSUPPORTED"
    assert payload["errors"][0]["code"] == "KVO17_GENERATED_PURCHASE_CAPABILITY_MISSING"
