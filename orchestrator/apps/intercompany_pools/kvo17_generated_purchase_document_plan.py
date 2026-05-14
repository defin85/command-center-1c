from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from django.utils import timezone

from .ccpool_traceability import build_ccpool_document_traceability
from .document_plan_artifact_contract import (
    DOCUMENT_PLAN_ARTIFACT_VERSION,
    validate_compiled_document_policy_slots_snapshot,
    validate_document_plan_artifact_v1,
)
from .document_policy_contract import DOCUMENT_POLICY_VERSION
from .kvo17_generated_purchase_intake import (
    KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
    KVO17_GENERATED_PURCHASE_POLICY_SLOTS,
    Kvo17GeneratedPurchaseAmountRange,
    Kvo17GeneratedPurchaseCounterparty,
    Kvo17GeneratedPurchaseManifest,
    Kvo17GeneratedPurchaseRow,
)
from .kvo17_purchase_split_intake import PURCHASE_KVO01_SLOT, PURCHASE_KVO17_SLOT
from .kvo17_purchase_split_scheme import build_kvo17_purchase_split_document_policy
from .models import PoolRun


KVO17_GENERATED_PURCHASE_DOCUMENT_PLAN_VERSION = "kvo17_generated_purchase_document_plan.v1"
KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SLOT = "kvo17_generated_purchase_pair"
KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SOURCE = "kvo17_generated_purchase.single_edge_pair_policy"

_ZERO_GUID = "00000000-0000-0000-0000-000000000000"
_PURCHASE_RECEIPT_ENTITY_NAME = "Document_ПоступлениеТоваровУслуг"
_PURCHASE_INVOICE_ENTITY_NAME = "Document_СчетФактураПолученный"
_PURCHASE_INVOICE_KIND = "НаПоступление"
_PURCHASE_INVOICE_BASE_DOCUMENT_TYPE = "StandardODATA.Document_ПоступлениеТоваровУслуг"
_DEFAULT_PURCHASE_OPERATION = "ПокупкаКомиссия"
_DEFAULT_RUB_CURRENCY_REF = "171b30af-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_COUNTERPARTY_ACCOUNT_REF = "020635ce-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_ADVANCE_ACCOUNT_REF = "020635cf-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_WAREHOUSE_REF = "62953111-54e8-11e9-80ee-0050569f2e9f"
_DEFAULT_PURCHASE_CONTRACT_CANONICAL_ID = "osnovnoy"
_DEFAULT_PURCHASE_ITEM_CANONICAL_ID = "packing-service"


def build_kvo17_generated_purchase_compiled_policy_slots() -> dict[str, dict[str, Any]]:
    slots = {
        slot_key: {
            "decision_table_id": f"kvo17_generated_purchase_{slot_key}_policy",
            "decision_revision": 1,
            "document_policy_source": (
                f"workflow_binding.decision_table:kvo17_generated_purchase_{slot_key}_policy:v1"
            ),
            "document_policy": build_kvo17_purchase_split_document_policy(slot_key=slot_key),
        }
        for slot_key in KVO17_GENERATED_PURCHASE_POLICY_SLOTS
    }
    return validate_compiled_document_policy_slots_snapshot(slots) or {}


def compile_kvo17_generated_purchase_document_plan(
    *,
    manifest: Kvo17GeneratedPurchaseManifest,
    compiled_policy_slots: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    policy_slots = validate_compiled_document_policy_slots_snapshot(
        compiled_policy_slots or build_kvo17_generated_purchase_compiled_policy_slots()
    )
    if policy_slots is None:
        raise ValueError("KVO17 generated purchase document plan requires compiled policy slots.")

    missing_slots = [
        slot_key
        for slot_key in KVO17_GENERATED_PURCHASE_POLICY_SLOTS
        if slot_key not in policy_slots
    ]
    if missing_slots:
        raise ValueError(
            "KVO17 generated purchase document plan is missing policy slots: "
            + ", ".join(missing_slots)
        )

    targets = [
        _compile_target(
            row=row,
            policy_slot=policy_slots[_slot_for_kvo(row.kvo)],
        )
        for row in manifest.rows
    ]
    branches = {
        slot_key: _compile_branch(slot_key=slot_key, targets=targets, policy_slot=policy_slots[slot_key])
        for slot_key in KVO17_GENERATED_PURCHASE_POLICY_SLOTS
    }
    counterparty_chains = _compile_counterparty_chains(targets=targets)
    return {
        "version": KVO17_GENERATED_PURCHASE_DOCUMENT_PLAN_VERSION,
        "manifest_version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
        "manifest_content_hash": manifest.content_hash,
        "request_hash": manifest.request_hash,
        "seed": manifest.seed,
        "policy_refs": [
            {
                "slot_key": slot_key,
                "decision_table_id": policy_slots[slot_key]["decision_table_id"],
                "decision_revision": policy_slots[slot_key]["decision_revision"],
                "policy_version": policy_slots[slot_key]["document_policy"]["version"],
                "source": policy_slots[slot_key]["document_policy_source"],
            }
            for slot_key in KVO17_GENERATED_PURCHASE_POLICY_SLOTS
        ],
        "targets": targets,
        "branches": branches,
        "counterparty_chains": counterparty_chains,
        "edge_strategy": {
            "mode": "single_edge_multi_document_chain",
            "requires_parallel_topology_slots": False,
            "documents_per_counterparty": 2,
            "publication_documents_per_counterparty": 4,
            "slot_key": KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SLOT,
            "source_slots": list(KVO17_GENERATED_PURCHASE_POLICY_SLOTS),
        },
        "lineage": _build_lineage(manifest=manifest, targets=targets),
        "collapse_readback_policy": {
            "required": True,
            "expected_documents_per_counterparty": 2,
            "expected_invoice_documents_per_counterparty": 2,
            "shared_invoice_identity_per_counterparty": True,
            "distinct_refs_required": True,
            "distinct_invoice_refs_required": True,
            "distinct_kvo_required": True,
            "fail_closed_on_ambiguous_readback": True,
        },
        "compile_summary": {
            "selected_counterparties": len(manifest.counterparties),
            "targets_count": len(targets),
            "documents_count": len(targets),
            "invoice_documents_count": len(targets),
            "publication_documents_count": len(targets) * 2,
            "chains_count": len(counterparty_chains),
            "branches_count": len(branches),
        },
    }


def compile_kvo17_generated_purchase_publication_artifact(
    *,
    run: PoolRun,
    manifest: Kvo17GeneratedPurchaseManifest,
    target_database_id: str,
    target_organization_id: str,
    topology_version_ref: str,
    compiled_policy_slots: Mapping[str, Any] | None = None,
    target_party_canonical_id: str = "",
) -> dict[str, Any]:
    database_id = str(target_database_id or "").strip()
    organization_id = str(target_organization_id or "").strip()
    topology_ref = str(topology_version_ref or "").strip()
    if not database_id:
        raise ValueError("KVO17_GENERATED_PURCHASE_TARGET_DATABASE_MISSING: target database is required")
    if not organization_id:
        raise ValueError("KVO17_GENERATED_PURCHASE_TARGET_ORGANIZATION_MISSING: target organization is required")
    if not topology_ref:
        topology_ref = f"kvo17_generated_purchase:{manifest.content_hash[:16]}"
    organization_party_canonical_id = (
        str(target_party_canonical_id or "").strip()
        or _normalize_master_data_canonical_id(organization_id)
    )

    edge_ref = {
        "parent_node_id": f"kvo17-generated-source:{manifest.content_hash[:16]}",
        "child_node_id": organization_id,
    }
    chains = [
        _compile_publication_chain(
            run=run,
            rows=rows,
            edge_ref=edge_ref,
            target_organization_id=organization_id,
            target_party_canonical_id=organization_party_canonical_id,
        )
        for _counterparty_ref, rows in sorted(manifest.rows_by_counterparty().items())
    ]
    artifact = {
        "version": DOCUMENT_PLAN_ARTIFACT_VERSION,
        "run_id": str(run.id),
        "distribution_artifact_ref": {
            "version": KVO17_GENERATED_PURCHASE_MANIFEST_VERSION,
            "topology_version_ref": topology_ref,
        },
        "topology_version_ref": topology_ref,
        "policy_refs": [
            {
                "slot_key": KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SLOT,
                "edge_ref": edge_ref,
                "policy_version": DOCUMENT_POLICY_VERSION,
                "source": _build_single_edge_policy_source(compiled_policy_slots=compiled_policy_slots),
            }
        ],
        "targets": [
            {
                "database_id": database_id,
                "chains": chains,
            }
        ],
        "compile_summary": {
            "compiled_edges": 1,
            "targets_count": 1,
            "chains_count": len(chains),
            "documents_count": len(manifest.rows) * 2,
            "receipt_documents_count": len(manifest.rows),
            "invoice_documents_count": len(manifest.rows),
            "compiled_at": timezone.now().isoformat(),
            "selected_counterparties": len(manifest.counterparties),
            "edge_strategy": "single_edge_multi_document_chain",
        },
    }
    return validate_document_plan_artifact_v1(artifact=artifact)


def parse_kvo17_generated_purchase_manifest_payload(
    *,
    payload: Mapping[str, Any],
) -> Kvo17GeneratedPurchaseManifest:
    period_payload = _require_mapping(payload.get("period"), field_name="manifest.period")
    rows_payload = _require_list(payload.get("rows"), field_name="manifest.rows")
    counterparties_payload = _require_list(
        payload.get("counterparties"),
        field_name="manifest.counterparties",
    )
    amount_ranges_payload = _require_list(
        payload.get("amount_ranges"),
        field_name="manifest.amount_ranges",
    )

    return Kvo17GeneratedPurchaseManifest(
        period_start=_parse_date(period_payload.get("start"), field_name="manifest.period.start"),
        period_end=_parse_date(period_payload.get("end"), field_name="manifest.period.end"),
        counterparties=[
            Kvo17GeneratedPurchaseCounterparty(
                ref=_require_string(item.get("ref"), field_name="manifest.counterparties[].ref"),
                name=_require_string(item.get("name"), field_name="manifest.counterparties[].name"),
                inn=str(item.get("inn") or "").strip(),
            )
            for item in (_require_mapping(raw, field_name="manifest.counterparties[]") for raw in counterparties_payload)
        ],
        amount_ranges=[
            Kvo17GeneratedPurchaseAmountRange(
                range_key=_require_string(item.get("range_key"), field_name="manifest.amount_ranges[].range_key"),
                min_amount=_parse_decimal(item.get("min_amount"), field_name="manifest.amount_ranges[].min_amount"),
                max_amount=_parse_decimal(item.get("max_amount"), field_name="manifest.amount_ranges[].max_amount"),
                kvo=_require_string(item.get("kvo"), field_name="manifest.amount_ranges[].kvo"),
            )
            for item in (_require_mapping(raw, field_name="manifest.amount_ranges[]") for raw in amount_ranges_payload)
        ],
        seed=_require_string(payload.get("seed"), field_name="manifest.seed"),
        currency=_require_string(payload.get("currency"), field_name="manifest.currency"),
        vat_rate=_require_string(payload.get("vat_rate"), field_name="manifest.vat_rate"),
        invoice_number_prefix=_require_string(
            payload.get("invoice_number_prefix"),
            field_name="manifest.invoice_number_prefix",
        ),
        request_hash=_require_string(payload.get("request_hash"), field_name="manifest.request_hash"),
        content_hash=_require_string(payload.get("content_hash"), field_name="manifest.content_hash"),
        rows=[
            Kvo17GeneratedPurchaseRow(
                line_no=int(_parse_decimal(item.get("line_no"), field_name="manifest.rows[].line_no")),
                counterparty_ref=_require_string(item.get("counterparty_ref"), field_name="manifest.rows[].counterparty_ref"),
                counterparty_name=str(item.get("counterparty_name") or "").strip(),
                counterparty_inn=str(item.get("counterparty_inn") or "").strip(),
                range_key=_require_string(item.get("range_key"), field_name="manifest.rows[].range_key"),
                kvo=_require_string(item.get("kvo"), field_name="manifest.rows[].kvo"),
                amount=_parse_decimal(item.get("amount"), field_name="manifest.rows[].amount"),
                vat_rate=_require_string(item.get("vat_rate"), field_name="manifest.rows[].vat_rate"),
                vat_amount=_parse_decimal(item.get("vat_amount"), field_name="manifest.rows[].vat_amount"),
                currency=_require_string(item.get("currency"), field_name="manifest.rows[].currency"),
                source_document_number=_require_string(
                    item.get("source_document_number"),
                    field_name="manifest.rows[].source_document_number",
                ),
                source_document_date=_parse_date(
                    item.get("source_document_date"),
                    field_name="manifest.rows[].source_document_date",
                ),
                row_id=_require_string(item.get("row_id"), field_name="manifest.rows[].row_id"),
                row_fingerprint=_require_string(
                    item.get("row_fingerprint"),
                    field_name="manifest.rows[].row_fingerprint",
                ),
                idempotency_key=_require_string(
                    item.get("idempotency_key"),
                    field_name="manifest.rows[].idempotency_key",
                ),
            )
            for item in (_require_mapping(raw, field_name="manifest.rows[]") for raw in rows_payload)
        ],
    )


def _compile_target(
    *,
    row: Kvo17GeneratedPurchaseRow,
    policy_slot: Mapping[str, Any],
) -> dict[str, Any]:
    policy = policy_slot["document_policy"]
    policy_metadata = dict(policy.get("metadata") or {})
    chain, document = _first_policy_document(policy=policy)
    slot_key = _slot_for_kvo(row.kvo)
    shared_invoice_pair_key = "|".join(
        (
            row.counterparty_ref,
            row.source_document_number,
            row.source_document_date.isoformat(),
        )
    )
    return {
        "target_id": row.idempotency_key,
        "slot_key": slot_key,
        "kvo": row.kvo,
        "chain_id": chain.get("chain_id"),
        "document_id": document.get("document_id"),
        "entity_name": document.get("entity_name"),
        "document_role": document.get("document_role"),
        "invoice_mode": document.get("invoice_mode"),
        "source_document_identity": {
            "number": row.source_document_number,
            "date": row.source_document_date.isoformat(),
        },
        "source_supplier_provenance": {
            "ref": row.counterparty_ref,
            "name": row.counterparty_name,
            "inn": row.counterparty_inn,
        },
        "runtime_document_identity": {
            "idempotency_key": row.idempotency_key,
            "runtime_document_key": f"{row.row_id}|{row.row_fingerprint[:16]}",
            "shared_invoice_pair_key": shared_invoice_pair_key,
        },
        "field_mapping": dict(document.get("field_mapping") or {}),
        "table_parts_mapping": dict(document.get("table_parts_mapping") or {}),
        "link_rules": dict(document.get("link_rules") or {}),
        "technical_identity_workaround": {
            **dict(policy_metadata.get("technical_identity_workaround") or {}),
            "visible_in_generated_plan": True,
            "business_invoice_identity_preserved": True,
            "runtime_identity_uses_idempotency_key": True,
        },
        "declaration_export": {
            "source_document_identity": {
                "number": row.source_document_number,
                "date": row.source_document_date.isoformat(),
            },
            "source_supplier_provenance": {
                "ref": row.counterparty_ref,
                "name": row.counterparty_name,
                "inn": row.counterparty_inn,
            },
            "supplier_role": "generated_source_supplier",
        },
        "row": row.as_dict(),
    }


def _compile_branch(
    *,
    slot_key: str,
    targets: list[dict[str, Any]],
    policy_slot: Mapping[str, Any],
) -> dict[str, Any]:
    branch_targets = [
        target
        for target in targets
        if str(target.get("slot_key") or "").strip() == slot_key
    ]
    return {
        "slot_key": slot_key,
        "kvo": "01" if slot_key == PURCHASE_KVO01_SLOT else "17",
        "decision_table_id": policy_slot["decision_table_id"],
        "decision_revision": policy_slot["decision_revision"],
        "document_policy_source": policy_slot["document_policy_source"],
        "row_count": len(branch_targets),
        "documents_count": len(branch_targets),
        "total_amount": _sum_target_amounts(targets=branch_targets),
        "targets": branch_targets,
    }


def _compile_counterparty_chains(*, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for target in targets:
        provenance = target.get("source_supplier_provenance")
        if not isinstance(provenance, Mapping):
            continue
        counterparty_ref = str(provenance.get("ref") or "").strip()
        if counterparty_ref:
            grouped.setdefault(counterparty_ref, []).append(target)

    chains: list[dict[str, Any]] = []
    for counterparty_ref, chain_targets in sorted(grouped.items()):
        ordered_targets = sorted(
            chain_targets,
            key=lambda item: str((item.get("row") or {}).get("range_key") or ""),
        )
        invoice_identities = {
            (
                str(target.get("source_document_identity", {}).get("number") or ""),
                str(target.get("source_document_identity", {}).get("date") or ""),
            )
            for target in ordered_targets
        }
        chains.append(
            {
                "chain_id": f"kvo17_generated_purchase_pair:{counterparty_ref}",
                "slot_key": KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SLOT,
                "counterparty_ref": counterparty_ref,
                "documents_count": len(ordered_targets),
                "shared_invoice_identity": len(invoice_identities) == 1,
                "documents": ordered_targets,
            }
        )
    return chains


def _compile_publication_chain(
    *,
    run: PoolRun,
    rows: list[Kvo17GeneratedPurchaseRow],
    edge_ref: Mapping[str, str],
    target_organization_id: str,
    target_party_canonical_id: str,
) -> dict[str, Any]:
    ordered_rows = sorted(rows, key=lambda item: item.range_key)
    if len(ordered_rows) != 2:
        raise ValueError(
            "KVO17_GENERATED_PURCHASE_COUNTERPARTY_PAIR_INVALID: "
            f"counterparty '{ordered_rows[0].counterparty_ref if ordered_rows else '<empty>'}' "
            "must have exactly two generated rows"
        )
    counterparty_ref = ordered_rows[0].counterparty_ref
    amount = sum((row.amount for row in ordered_rows), Decimal("0.00")).quantize(Decimal("0.01"))
    documents: list[dict[str, Any]] = []
    for row in ordered_rows:
        receipt_document = _compile_publication_receipt_document(
            run=run,
            row=row,
            target_organization_id=target_organization_id,
            target_party_canonical_id=target_party_canonical_id,
        )
        invoice_document = _compile_publication_invoice_document(
            run=run,
            row=row,
            receipt_document_id=receipt_document["document_id"],
            target_organization_id=target_organization_id,
            target_party_canonical_id=target_party_canonical_id,
        )
        documents.extend((receipt_document, invoice_document))
    return {
        "chain_id": f"kvo17_generated_purchase_pair:{counterparty_ref}",
        "edge_ref": dict(edge_ref),
        "policy_source": KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SOURCE,
        "policy_version": DOCUMENT_POLICY_VERSION,
        "allocation": {
            "amount": str(amount),
            "counterparty_ref": counterparty_ref,
            "source_document_number": ordered_rows[0].source_document_number,
            "source_document_date": ordered_rows[0].source_document_date.isoformat(),
        },
        "documents": documents,
    }


def _compile_publication_receipt_document(
    *,
    run: PoolRun,
    row: Kvo17GeneratedPurchaseRow,
    target_organization_id: str,
    target_party_canonical_id: str,
) -> dict[str, Any]:
    document_id = _build_purchase_receipt_document_id(row=row)
    batch_id = str((run.run_input or {}).get("batch_id") or "").strip()
    counterparty_canonical_id = _normalize_master_data_canonical_id(row.counterparty_ref)
    invoice_date = _serialize_odata_date(row.source_document_date)
    document_number = _build_unique_purchase_document_number(row=row)
    traceability = None
    if batch_id and target_organization_id:
        traceability = build_ccpool_document_traceability(
            pool_id=str(run.pool_id),
            run_id=str(run.id),
            batch_id=batch_id,
            organization_id=target_organization_id,
            period_start=run.period_start,
            document_role="purchase",
            direction=run.direction,
            batch_kind="receipt",
        )
    document = {
        "document_id": document_id,
        "entity_name": _PURCHASE_RECEIPT_ENTITY_NAME,
        "document_role": "purchase",
        "invoice_mode": "optional",
        "idempotency_key": row.idempotency_key,
        "field_mapping": {
            "ВидОперации": _DEFAULT_PURCHASE_OPERATION,
            "Date": invoice_date,
            "Number": document_number,
            "Организация_Key": f"master_data.party.{target_party_canonical_id}.organization.ref",
            "ПодразделениеОрганизации_Key": _ZERO_GUID,
            "Склад_Key": _DEFAULT_PURCHASE_WAREHOUSE_REF,
            "Контрагент_Key": f"master_data.party.{counterparty_canonical_id}.counterparty.ref",
            "ДоговорКонтрагента_Key": (
                f"master_data.contract.{_DEFAULT_PURCHASE_CONTRACT_CANONICAL_ID}."
                f"{counterparty_canonical_id}.ref"
            ),
            "ВалютаДокумента_Key": _DEFAULT_RUB_CURRENCY_REF,
            "СуммаДокумента": str(row.amount),
            "СуммаВключаетНДС": True,
            "СчетУчетаРасчетовСКонтрагентом_Key": _DEFAULT_PURCHASE_COUNTERPARTY_ACCOUNT_REF,
            "СчетУчетаРасчетовПоАвансам_Key": _DEFAULT_PURCHASE_ADVANCE_ACCOUNT_REF,
            "Ответственный_Key": _ZERO_GUID,
            "УдалитьКодВидаОперации": row.kvo,
            "УдалитьНомерВходящегоСчетаФактуры": row.source_document_number,
            "УдалитьДатаВходящегоСчетаФактуры": invoice_date,
        },
        "table_parts_mapping": {
            "Услуги": [
                {
                    "LineNumber": "1",
                    "Номенклатура_Key": f"master_data.item.{_DEFAULT_PURCHASE_ITEM_CANONICAL_ID}.ref",
                    "Содержание": f"Услуги поставщика {row.counterparty_name or row.counterparty_ref}",
                    "Количество": 1,
                    "Цена": str(row.amount),
                    "Сумма": str(row.amount),
                    "СтавкаНДС": _normalize_vat_rate(row.vat_rate),
                    "СуммаНДС": str(row.vat_amount),
                    "ИдентификаторСтроки": row.row_id,
                }
            ]
        },
        "link_rules": {},
        "generated_purchase_lineage": row.as_dict(),
        "runtime_document_identity": {
            "idempotency_key": row.idempotency_key,
            "runtime_document_key": f"{row.row_id}|{row.row_fingerprint[:16]}",
            "range_key": row.range_key,
            "kvo": row.kvo,
        },
    }
    if traceability is not None:
        document["traceability"] = traceability
    return document


def _compile_publication_invoice_document(
    *,
    run: PoolRun,
    row: Kvo17GeneratedPurchaseRow,
    receipt_document_id: str,
    target_organization_id: str,
    target_party_canonical_id: str,
) -> dict[str, Any]:
    document_id = f"{receipt_document_id}_invoice"
    batch_id = str((run.run_input or {}).get("batch_id") or "").strip()
    counterparty_canonical_id = _normalize_master_data_canonical_id(row.counterparty_ref)
    invoice_date = _serialize_odata_date(row.source_document_date)
    document_number = _build_unique_purchase_invoice_document_number(row=row)
    traceability = None
    if batch_id and target_organization_id:
        traceability = build_ccpool_document_traceability(
            pool_id=str(run.pool_id),
            run_id=str(run.id),
            batch_id=batch_id,
            organization_id=target_organization_id,
            period_start=run.period_start,
            document_role="purchase",
            direction=run.direction,
            batch_kind="receipt",
        )
    document = {
        "document_id": document_id,
        "entity_name": _PURCHASE_INVOICE_ENTITY_NAME,
        "document_role": "invoice",
        "invoice_mode": "required",
        "idempotency_key": f"{row.idempotency_key}:invoice",
        "link_to": receipt_document_id,
        "field_mapping": {
            "Date": invoice_date,
            "Number": document_number,
            "Организация_Key": f"master_data.party.{target_party_canonical_id}.organization.ref",
            "ВидСчетаФактуры": _PURCHASE_INVOICE_KIND,
            "Контрагент_Key": f"master_data.party.{counterparty_canonical_id}.counterparty.ref",
            "ДоговорКонтрагента_Key": (
                f"master_data.contract.{_DEFAULT_PURCHASE_CONTRACT_CANONICAL_ID}."
                f"{counterparty_canonical_id}.ref"
            ),
            "НомерВходящегоДокумента": row.source_document_number,
            "ДатаВходящегоДокумента": invoice_date,
            "Исправление": False,
            "СчетФактураБезНДС": False,
            "КодСпособаПолучения": 1,
            "КодВидаОперации": row.kvo,
            "СуммаДокумента": str(row.amount),
            "СуммаНДСДокумента": str(row.vat_amount),
            "ВалютаДокумента_Key": _DEFAULT_RUB_CURRENCY_REF,
            "Ответственный_Key": _ZERO_GUID,
            "РучнаяКорректировка": False,
            "СформированПриВводеНачальныхОстатковНДС": False,
            "БланкСтрогойОтчетности": False,
            "ПредставлениеНомера": row.source_document_number,
            "НДСПредъявленКВычету": False,
        },
        "table_parts_mapping": {
            "ДокументыОснования": [
                {
                    "LineNumber": "1",
                    "ДокументОснование": f"{receipt_document_id}.ref",
                    "ДокументОснование_Type": _PURCHASE_INVOICE_BASE_DOCUMENT_TYPE,
                }
            ]
        },
        "link_rules": {"depends_on": receipt_document_id},
        "generated_purchase_lineage": row.as_dict(),
        "runtime_document_identity": {
            "idempotency_key": f"{row.idempotency_key}:invoice",
            "runtime_document_key": f"{row.row_id}|{row.row_fingerprint[:16]}|invoice",
            "range_key": row.range_key,
            "kvo": row.kvo,
            "linked_receipt_document_id": receipt_document_id,
        },
    }
    if traceability is not None:
        document["traceability"] = traceability
    return document


def _build_lineage(
    *,
    manifest: Kvo17GeneratedPurchaseManifest,
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "seed": manifest.seed,
        "request_hash": manifest.request_hash,
        "manifest_content_hash": manifest.content_hash,
        "counterparty_invoice_pairs": [
            {
                "counterparty_ref": counterparty.ref,
                "source_document_number": rows[0].source_document_number,
                "source_document_date": rows[0].source_document_date.isoformat(),
                "row_ids": [row.row_id for row in rows],
                "kvo_values": [row.kvo for row in rows],
            }
            for counterparty, rows in (
                (counterparty, manifest.rows_by_counterparty()[counterparty.ref])
                for counterparty in manifest.counterparties
            )
        ],
        "target_ids": [str(target.get("target_id") or "") for target in targets],
        "policy_slots": list(KVO17_GENERATED_PURCHASE_POLICY_SLOTS),
        "edge_strategy": "single_edge_multi_document_chain",
        "requires_parallel_topology_slots": False,
        "collapse_readback_required": True,
        "purchase_invoice_document_required": True,
        "silent_invoice_identity_mutation_allowed": False,
    }


def _first_policy_document(*, policy: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    for raw_chain in list(policy.get("chains") or []):
        if not isinstance(raw_chain, Mapping):
            continue
        chain = dict(raw_chain)
        for raw_document in list(chain.get("documents") or []):
            if isinstance(raw_document, Mapping):
                return chain, dict(raw_document)
    raise ValueError("KVO17 generated purchase policy slot has no document target.")


def _slot_for_kvo(kvo: str) -> str:
    if kvo == "01":
        return PURCHASE_KVO01_SLOT
    if kvo == "17":
        return PURCHASE_KVO17_SLOT
    raise ValueError(f"Unsupported KVO17 generated purchase KVO '{kvo}'.")


def _sum_target_amounts(*, targets: list[dict[str, Any]]) -> str:
    total = Decimal("0.00")
    for target in targets:
        row = target.get("row")
        if isinstance(row, Mapping):
            total += Decimal(str(row.get("amount") or "0.00"))
    return str(total.quantize(Decimal("0.01")))


def _build_single_edge_policy_source(*, compiled_policy_slots: Mapping[str, Any] | None) -> str:
    slots = validate_compiled_document_policy_slots_snapshot(compiled_policy_slots)
    if not slots:
        return KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SOURCE
    sources = [
        str(slots[slot_key].get("document_policy_source") or "").strip()
        for slot_key in KVO17_GENERATED_PURCHASE_POLICY_SLOTS
        if slot_key in slots
    ]
    sources = [source for source in sources if source]
    if not sources:
        return KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SOURCE
    return f"{KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SOURCE}:{'|'.join(sources)}"


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"KVO17_GENERATED_PURCHASE_MANIFEST_INVALID: {field_name} must be an object")
    return dict(value)


def _require_list(value: Any, *, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"KVO17_GENERATED_PURCHASE_MANIFEST_INVALID: {field_name} must be an array")
    return list(value)


def _require_string(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"KVO17_GENERATED_PURCHASE_MANIFEST_INVALID: {field_name} is required")
    return text


def _parse_date(value: Any, *, field_name: str) -> date:
    text = _require_string(value, field_name=field_name)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"KVO17_GENERATED_PURCHASE_MANIFEST_INVALID: invalid {field_name}") from exc


def _parse_decimal(value: Any, *, field_name: str) -> Decimal:
    text = _require_string(value, field_name=field_name).replace(",", ".")
    try:
        return Decimal(text)
    except Exception as exc:
        raise ValueError(f"KVO17_GENERATED_PURCHASE_MANIFEST_INVALID: invalid {field_name}") from exc


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip().lower()).strip("_") or "range"


def _normalize_master_data_canonical_id(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_.-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-.")
    return text or "unknown"


def _normalize_vat_rate(value: str) -> str:
    text = str(value or "").strip()
    if text in {"20", "20%"}:
        return "НДС20"
    if text in {"10", "10%"}:
        return "НДС10"
    if text in {"0", "0%"}:
        return "НДС0"
    return text or "НДС20"


def _build_purchase_receipt_document_id(*, row: Kvo17GeneratedPurchaseRow) -> str:
    return f"kvo17_generated_{_normalize_token(row.range_key)}_kvo{row.kvo}_receipt"


def _build_unique_purchase_document_number(*, row: Kvo17GeneratedPurchaseRow) -> str:
    fingerprint = re.sub(r"[^A-Fa-f0-9]+", "", str(row.row_fingerprint or ""))[:6].upper()
    if len(fingerprint) < 6:
        fingerprint = (fingerprint + "000000")[:6]
    return f"K17{row.kvo}{fingerprint}"


def _build_unique_purchase_invoice_document_number(*, row: Kvo17GeneratedPurchaseRow) -> str:
    fingerprint = re.sub(r"[^A-Fa-f0-9]+", "", str(row.row_fingerprint or ""))[:6].upper()
    if len(fingerprint) < 6:
        fingerprint = (fingerprint + "000000")[:6]
    return f"F17{row.kvo}{fingerprint}"


def _serialize_odata_date(value: date) -> str:
    return f"{value.isoformat()}T00:00:00"


__all__ = [
    "KVO17_GENERATED_PURCHASE_DOCUMENT_PLAN_VERSION",
    "KVO17_GENERATED_PURCHASE_SINGLE_EDGE_SLOT",
    "build_kvo17_generated_purchase_compiled_policy_slots",
    "compile_kvo17_generated_purchase_document_plan",
    "compile_kvo17_generated_purchase_publication_artifact",
    "parse_kvo17_generated_purchase_manifest_payload",
]
