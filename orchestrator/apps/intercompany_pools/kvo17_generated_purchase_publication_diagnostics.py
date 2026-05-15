from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.databases.models import Database
from apps.databases.odata import (
    ODataDocumentAdapter,
    ODataDocumentTransportError,
    resolve_database_odata_verify_tls,
)

from .kvo17_generated_purchase_document_plan import parse_kvo17_generated_purchase_manifest_payload
from .kvo17_generated_purchase_intake import (
    KVO17_GENERATED_PURCHASE_METADATA_KEY,
    Kvo17GeneratedPurchaseManifest,
    Kvo17GeneratedPurchaseRow,
)
from .publication_verification import (
    _collect_successful_document_refs,
    _guid_literal,
    _resolve_verification_credentials,
)


KVO17_GENERATED_PURCHASE_VERIFICATION_CONTEXT_KEY = "kvo17_generated_purchase"
KVO17_GENERATED_PURCHASE_READBACK_COUNT_MISMATCH = "KVO17_GENERATED_PURCHASE_READBACK_COUNT_MISMATCH"
KVO17_GENERATED_PURCHASE_COLLAPSED_DOCUMENTS = "KVO17_GENERATED_PURCHASE_COLLAPSED_DOCUMENTS"
KVO17_GENERATED_PURCHASE_KVO_MISMATCH = "KVO17_GENERATED_PURCHASE_KVO_MISMATCH"
KVO17_GENERATED_PURCHASE_AMOUNT_MISMATCH = "KVO17_GENERATED_PURCHASE_AMOUNT_MISMATCH"
KVO17_GENERATED_PURCHASE_VAT_MISMATCH = "KVO17_GENERATED_PURCHASE_VAT_MISMATCH"
KVO17_GENERATED_PURCHASE_INVOICE_READBACK_COUNT_MISMATCH = (
    "KVO17_GENERATED_PURCHASE_INVOICE_READBACK_COUNT_MISMATCH"
)
KVO17_GENERATED_PURCHASE_INVOICE_COLLAPSED_DOCUMENTS = (
    "KVO17_GENERATED_PURCHASE_INVOICE_COLLAPSED_DOCUMENTS"
)
KVO17_GENERATED_PURCHASE_INVOICE_LINK_MISMATCH = "KVO17_GENERATED_PURCHASE_INVOICE_LINK_MISMATCH"
KVO17_GENERATED_PURCHASE_MANIFEST_MISSING = "KVO17_GENERATED_PURCHASE_MANIFEST_MISSING"
KVO17_GENERATED_PURCHASE_TARGET_DATABASE_MISSING = "KVO17_GENERATED_PURCHASE_TARGET_DATABASE_MISSING"
KVO17_GENERATED_PURCHASE_TARGET_DATABASE_NOT_FOUND = "KVO17_GENERATED_PURCHASE_TARGET_DATABASE_NOT_FOUND"
KVO17_GENERATED_PURCHASE_SUCCESSFUL_REFS_MISSING = "KVO17_GENERATED_PURCHASE_SUCCESSFUL_REFS_MISSING"
KVO17_GENERATED_PURCHASE_READBACK_FETCH_FAILED = "KVO17_GENERATED_PURCHASE_READBACK_FETCH_FAILED"
KVO17_GENERATED_PURCHASE_MASTER_DATA_UNRESOLVED = "KVO17_GENERATED_PURCHASE_MASTER_DATA_UNRESOLVED"
KVO17_GENERATED_PURCHASE_MASTER_DATA_GATE_FAILED = "KVO17_GENERATED_PURCHASE_MASTER_DATA_GATE_FAILED"
KVO17_GENERATED_PURCHASE_MASTER_DATA_GATE_MISSING = "KVO17_GENERATED_PURCHASE_MASTER_DATA_GATE_MISSING"
KVO17_GENERATED_PURCHASE_EXPECTED_IDENTITY_INVALID = "KVO17_GENERATED_PURCHASE_EXPECTED_IDENTITY_INVALID"

_RECEIPT_ENTITY_NAME = "Document_ПоступлениеТоваровУслуг"
_INVOICE_ENTITY_NAME = "Document_СчетФактураПолученный"
_INVOICE_BASE_TABLE_PART = "ДокументыОснования"
_INVOICE_BASE_TYPE = "StandardODATA.Document_ПоступлениеТоваровУслуг"


def verify_kvo17_generated_purchase_publication(
    *,
    run: Any,
    execution_context: Mapping[str, Any],
    publication_results: list[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    context = _resolve_generated_context(run=run)
    if context is None:
        return {"status": "not_applicable", "summary": None, "diagnostics": []}

    try:
        manifest = parse_kvo17_generated_purchase_manifest_payload(payload=context["manifest"])
    except Exception as exc:
        diagnostic = _diagnostic(
            code=KVO17_GENERATED_PURCHASE_MANIFEST_MISSING,
            detail=f"Cannot parse KVO17 generated purchase manifest: {exc}",
            path="run_input.kvo17_generated_purchase.manifest",
        )
        return _build_publication_report(
            diagnostics=[diagnostic],
            preflight={"status": "failed", "diagnostics": [diagnostic], "checks": []},
            readback=None,
            evidence=[],
        )

    diagnostics: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    successful_refs = _collect_successful_document_refs(publication_results=publication_results or [])
    if not successful_refs:
        successful_refs = _collect_successful_document_refs_from_attempts(run=run)

    target_database_ids = _collect_target_database_ids(
        execution_context=execution_context,
        successful_refs=successful_refs,
        publication_results=publication_results or [],
    )
    preflight = _build_preflight_report(
        manifest=manifest,
        execution_context=execution_context,
        target_database_ids=target_database_ids,
        successful_refs=successful_refs,
    )
    diagnostics.extend(preflight["diagnostics"])

    if not target_database_ids:
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_TARGET_DATABASE_MISSING,
                detail="KVO17 generated purchase readback cannot resolve target database.",
                path="pool_runtime_document_plan_artifact.targets",
            )
        )

    readback_documents: list[dict[str, Any]] = []
    readback_invoices: list[dict[str, Any]] = []
    for database_id in target_database_ids:
        database_result = _readback_target_database(
            run=run,
            manifest=manifest,
            database_id=database_id,
            refs_by_document_key=successful_refs.get(database_id) or {},
        )
        diagnostics.extend(database_result["diagnostics"])
        readback_documents.extend(database_result["readback_documents"])
        readback_invoices.extend(database_result["readback_invoices"])
        evidence.extend(database_result["evidence"])

    readback = verify_kvo17_generated_purchase_readback(
        manifest=manifest,
        readback_documents=readback_documents,
        readback_invoices=readback_invoices,
    )
    diagnostics.extend(readback["diagnostics"])
    evidence.extend(readback["evidence"])

    return _build_publication_report(
        diagnostics=diagnostics,
        preflight=preflight,
        readback=readback,
        evidence=evidence,
    )


def verify_kvo17_generated_purchase_readback(
    *,
    manifest: Kvo17GeneratedPurchaseManifest,
    readback_documents: list[Mapping[str, Any]],
    readback_invoices: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    invoice_readback_enabled = readback_invoices is not None
    readback_invoices = list(readback_invoices or [])

    rows_by_counterparty = manifest.rows_by_counterparty()
    for counterparty in manifest.counterparties:
        expected_rows = rows_by_counterparty[counterparty.ref]
        invoice_number = expected_rows[0].source_document_number
        invoice_date = expected_rows[0].source_document_date.isoformat()
        documents = [
            dict(document)
            for document in readback_documents
            if _matches_counterparty_invoice(
                document=document,
                counterparty_ref=counterparty.ref,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
            )
        ]
        invoices = [
            dict(document)
            for document in readback_invoices
            if _matches_counterparty_invoice(
                document=document,
                counterparty_ref=counterparty.ref,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
            )
        ]
        evidence.append(
            {
                "counterparty_ref": counterparty.ref,
                "source_document_number": invoice_number,
                "source_document_date": invoice_date,
                "expected_rows": [row.as_dict() for row in expected_rows],
                "readback_documents": documents,
                "readback_invoices": invoices,
            }
        )
        if len(documents) != 2:
            diagnostics.append(
                _diagnostic(
                    code=KVO17_GENERATED_PURCHASE_READBACK_COUNT_MISMATCH,
                    counterparty_ref=counterparty.ref,
                    expected_count=2,
                    actual_count=len(documents),
                    detail="Generated KVO17 readback must contain exactly two receipt documents per counterparty.",
                )
            )
            if len(documents) == 1:
                diagnostics.append(
                    _diagnostic(
                        code=KVO17_GENERATED_PURCHASE_COLLAPSED_DOCUMENTS,
                        counterparty_ref=counterparty.ref,
                        detail="Generated KVO17 readback looks collapsed into one receipt document.",
                    )
                )
            continue

        refs = {_canonical_ref(document.get("document_ref") or document.get("ref") or document.get("id")) for document in documents}
        refs.discard("")
        if len(refs) != 2:
            diagnostics.append(
                _diagnostic(
                    code=KVO17_GENERATED_PURCHASE_COLLAPSED_DOCUMENTS,
                    counterparty_ref=counterparty.ref,
                    detail="Generated KVO17 readback documents do not have two distinct refs.",
                )
            )

        expected_by_kvo = {row.kvo: row for row in expected_rows}
        actual_kvo_values = {_document_kvo(document) for document in documents}
        actual_kvo_values.discard("")
        if actual_kvo_values != set(expected_by_kvo):
            diagnostics.append(
                _diagnostic(
                    code=KVO17_GENERATED_PURCHASE_KVO_MISMATCH,
                    counterparty_ref=counterparty.ref,
                    expected_kvo=sorted(expected_by_kvo),
                    actual_kvo=sorted(actual_kvo_values),
                    detail="Generated KVO17 readback KVO set does not match accepted manifest.",
                )
            )
            continue

        receipt_ref_by_kvo: dict[str, str] = {}
        for document in documents:
            kvo = _document_kvo(document)
            expected_row = expected_by_kvo[kvo]
            receipt_ref_by_kvo[kvo] = _canonical_ref(document.get("document_ref") or document.get("ref") or "")
            if _amount(document.get("amount") or document.get("СуммаДокумента")) != expected_row.amount:
                diagnostics.append(
                    _diagnostic(
                        code=KVO17_GENERATED_PURCHASE_AMOUNT_MISMATCH,
                        counterparty_ref=counterparty.ref,
                        kvo=kvo,
                        expected_amount=str(expected_row.amount),
                        actual_amount=str(document.get("amount") or document.get("СуммаДокумента") or ""),
                        detail="Generated KVO17 readback amount does not match accepted manifest.",
                    )
                )
            if _amount(document.get("vat_amount") or document.get("СуммаНДСДокумента")) not in {None, expected_row.vat_amount}:
                diagnostics.append(
                    _diagnostic(
                        code=KVO17_GENERATED_PURCHASE_VAT_MISMATCH,
                        counterparty_ref=counterparty.ref,
                        kvo=kvo,
                        expected_vat_amount=str(expected_row.vat_amount),
                        actual_vat_amount=str(document.get("vat_amount") or document.get("СуммаНДСДокумента") or ""),
                        detail="Generated KVO17 receipt VAT readback does not match accepted manifest.",
                    )
                )

        if invoice_readback_enabled:
            _verify_invoice_pair(
                diagnostics=diagnostics,
                counterparty_ref=counterparty.ref,
                invoices=invoices,
                expected_by_kvo=expected_by_kvo,
                receipt_ref_by_kvo=receipt_ref_by_kvo,
            )

    blocking = [
        diagnostic
        for diagnostic in diagnostics
        if str(diagnostic.get("severity") or "").strip().lower() == "error"
    ]
    return {
        "status": "blocked" if blocking else "verified",
        "diagnostics": diagnostics,
        "evidence": evidence,
        "summary": {
            "counterparties": len(manifest.counterparties),
            "expected_documents": len(manifest.rows),
            "expected_invoice_documents": len(manifest.rows) if invoice_readback_enabled else 0,
            "readback_documents": len(readback_documents),
            "readback_invoice_documents": len(readback_invoices) if invoice_readback_enabled else 0,
            "blocking_diagnostics": len(blocking),
        },
    }


def _verify_invoice_pair(
    *,
    diagnostics: list[dict[str, Any]],
    counterparty_ref: str,
    invoices: list[Mapping[str, Any]],
    expected_by_kvo: Mapping[str, Kvo17GeneratedPurchaseRow],
    receipt_ref_by_kvo: Mapping[str, str],
) -> None:
    if len(invoices) != 2:
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_INVOICE_READBACK_COUNT_MISMATCH,
                counterparty_ref=counterparty_ref,
                expected_count=2,
                actual_count=len(invoices),
                detail="Generated KVO17 readback must contain two received invoices per counterparty.",
            )
        )
        if len(invoices) == 1:
            diagnostics.append(
                _diagnostic(
                    code=KVO17_GENERATED_PURCHASE_INVOICE_COLLAPSED_DOCUMENTS,
                    counterparty_ref=counterparty_ref,
                    detail="Generated KVO17 invoice readback looks collapsed into one received invoice.",
                )
            )
        return

    refs = {_canonical_ref(invoice.get("document_ref") or invoice.get("ref") or invoice.get("id")) for invoice in invoices}
    refs.discard("")
    if len(refs) != 2:
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_INVOICE_COLLAPSED_DOCUMENTS,
                counterparty_ref=counterparty_ref,
                detail="Generated KVO17 invoices do not have two distinct refs.",
            )
        )

    actual_kvo_values = {_document_kvo(invoice) for invoice in invoices}
    actual_kvo_values.discard("")
    if actual_kvo_values != set(expected_by_kvo):
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_KVO_MISMATCH,
                counterparty_ref=counterparty_ref,
                expected_kvo=sorted(expected_by_kvo),
                actual_kvo=sorted(actual_kvo_values),
                entity_name=_INVOICE_ENTITY_NAME,
                detail="Generated KVO17 invoice KVO set does not match accepted manifest.",
            )
        )
        return

    for invoice in invoices:
        kvo = _document_kvo(invoice)
        expected_row = expected_by_kvo[kvo]
        if _amount(invoice.get("amount") or invoice.get("СуммаДокумента")) != expected_row.amount:
            diagnostics.append(
                _diagnostic(
                    code=KVO17_GENERATED_PURCHASE_AMOUNT_MISMATCH,
                    counterparty_ref=counterparty_ref,
                    kvo=kvo,
                    entity_name=_INVOICE_ENTITY_NAME,
                    expected_amount=str(expected_row.amount),
                    actual_amount=str(invoice.get("amount") or invoice.get("СуммаДокумента") or ""),
                    detail="Generated KVO17 invoice amount does not match accepted manifest.",
                )
            )
        if _amount(invoice.get("vat_amount") or invoice.get("СуммаНДСДокумента")) != expected_row.vat_amount:
            diagnostics.append(
                _diagnostic(
                    code=KVO17_GENERATED_PURCHASE_VAT_MISMATCH,
                    counterparty_ref=counterparty_ref,
                    kvo=kvo,
                    entity_name=_INVOICE_ENTITY_NAME,
                    expected_vat_amount=str(expected_row.vat_amount),
                    actual_vat_amount=str(invoice.get("vat_amount") or invoice.get("СуммаНДСДокумента") or ""),
                    detail="Generated KVO17 invoice VAT amount does not match accepted manifest.",
                )
            )
        expected_receipt_ref = receipt_ref_by_kvo.get(kvo) or ""
        actual_receipt_ref = _canonical_ref(invoice.get("linked_receipt_ref") or invoice.get("ДокументОснование"))
        if not expected_receipt_ref or actual_receipt_ref != expected_receipt_ref:
            diagnostics.append(
                _diagnostic(
                    code=KVO17_GENERATED_PURCHASE_INVOICE_LINK_MISMATCH,
                    counterparty_ref=counterparty_ref,
                    kvo=kvo,
                    entity_name=_INVOICE_ENTITY_NAME,
                    expected_receipt_ref=expected_receipt_ref,
                    actual_receipt_ref=actual_receipt_ref,
                    path=f"{_INVOICE_BASE_TABLE_PART}.ДокументОснование",
                    detail="Generated KVO17 received invoice does not link back to the exact receipt ref.",
                )
            )
        actual_receipt_type = str(invoice.get("linked_receipt_type") or invoice.get("ДокументОснование_Type") or "").strip()
        if actual_receipt_type and actual_receipt_type != _INVOICE_BASE_TYPE:
            diagnostics.append(
                _diagnostic(
                    code=KVO17_GENERATED_PURCHASE_INVOICE_LINK_MISMATCH,
                    counterparty_ref=counterparty_ref,
                    kvo=kvo,
                    entity_name=_INVOICE_ENTITY_NAME,
                    expected_receipt_type=_INVOICE_BASE_TYPE,
                    actual_receipt_type=actual_receipt_type,
                    path=f"{_INVOICE_BASE_TABLE_PART}.ДокументОснование_Type",
                    detail="Generated KVO17 received invoice base document type is not a purchase receipt.",
                )
            )


def _readback_target_database(
    *,
    run: Any,
    manifest: Kvo17GeneratedPurchaseManifest,
    database_id: str,
    refs_by_document_key: Mapping[str, str],
) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    readback_documents: list[dict[str, Any]] = []
    readback_invoices: list[dict[str, Any]] = []
    expected_rows = {row.idempotency_key: row for row in manifest.rows}
    expected_invoice_keys = {f"{row.idempotency_key}:invoice": row for row in manifest.rows}

    missing_keys = sorted(
        [
            key
            for key in [*expected_rows.keys(), *expected_invoice_keys.keys()]
            if not str(refs_by_document_key.get(key) or "").strip()
        ]
    )
    for missing_key in missing_keys:
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_SUCCESSFUL_REFS_MISSING,
                database_id=database_id,
                document_idempotency_key=missing_key,
                detail="Publication result does not contain a successful 1C ref for an expected KVO17 generated document.",
                path="response_summary.successful_document_refs",
            )
        )

    _append_duplicate_ref_diagnostics(
        diagnostics=diagnostics,
        database_id=database_id,
        refs_by_document_key=refs_by_document_key,
        expected_keys=list(expected_rows.keys()),
        code=KVO17_GENERATED_PURCHASE_COLLAPSED_DOCUMENTS,
        entity_name=_RECEIPT_ENTITY_NAME,
    )
    _append_duplicate_ref_diagnostics(
        diagnostics=diagnostics,
        database_id=database_id,
        refs_by_document_key=refs_by_document_key,
        expected_keys=list(expected_invoice_keys.keys()),
        code=KVO17_GENERATED_PURCHASE_INVOICE_COLLAPSED_DOCUMENTS,
        entity_name=_INVOICE_ENTITY_NAME,
    )

    database = Database.objects.filter(id=database_id, tenant_id=getattr(run, "tenant_id", None)).first()
    if database is None:
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_TARGET_DATABASE_NOT_FOUND,
                database_id=database_id,
                detail="KVO17 generated purchase readback target database is not available in the run tenant.",
                path="pool_runtime_document_plan_artifact.targets.database_id",
            )
        )
        return _readback_result(diagnostics=diagnostics)

    try:
        username, password = _resolve_verification_credentials(database=database)
    except ValueError as exc:
        diagnostics.append(
            _diagnostic(
                code=str(exc),
                database_id=database_id,
                detail="KVO17 generated purchase readback requires exactly one service OData mapping.",
                path="$credentials",
            )
        )
        return _readback_result(diagnostics=diagnostics)

    try:
        with ODataDocumentAdapter(
            base_url=str(database.odata_url or ""),
            username=username,
            password=password,
            timeout=database.connection_timeout,
            verify_tls=resolve_database_odata_verify_tls(database=database),
        ) as adapter:
            for document_key, row in expected_rows.items():
                document_ref = str(refs_by_document_key.get(document_key) or "").strip()
                if not document_ref:
                    continue
                payload = _fetch_json_document(
                    adapter=adapter,
                    database_id=database_id,
                    entity_name=_RECEIPT_ENTITY_NAME,
                    document_key=document_key,
                    document_ref=document_ref,
                    diagnostics=diagnostics,
                )
                if payload is None:
                    continue
                readback_documents.append(
                    _build_receipt_readback_document(
                        row=row,
                        document_key=document_key,
                        document_ref=document_ref,
                        payload=payload,
                        database_id=database_id,
                    )
                )

            for document_key, row in expected_invoice_keys.items():
                document_ref = str(refs_by_document_key.get(document_key) or "").strip()
                if not document_ref:
                    continue
                payload = _fetch_json_document(
                    adapter=adapter,
                    database_id=database_id,
                    entity_name=_INVOICE_ENTITY_NAME,
                    document_key=document_key,
                    document_ref=document_ref,
                    diagnostics=diagnostics,
                )
                if payload is None:
                    continue
                base_rows = _fetch_table_part_rows(
                    adapter=adapter,
                    database_id=database_id,
                    entity_name=_INVOICE_ENTITY_NAME,
                    table_part_name=_INVOICE_BASE_TABLE_PART,
                    document_key=document_key,
                    document_ref=document_ref,
                    diagnostics=diagnostics,
                )
                readback_invoices.append(
                    _build_invoice_readback_document(
                        row=row,
                        document_key=document_key,
                        document_ref=document_ref,
                        payload=payload,
                        base_rows=base_rows,
                        database_id=database_id,
                    )
                )
    except ODataDocumentTransportError:
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_READBACK_FETCH_FAILED,
                database_id=database_id,
                detail="KVO17 generated purchase readback failed due to OData transport error.",
                path="$odata",
            )
        )

    evidence.append(
        {
            "database_id": database_id,
            "receipt_refs": {
                key: refs_by_document_key.get(key)
                for key in expected_rows
                if str(refs_by_document_key.get(key) or "").strip()
            },
            "invoice_refs": {
                key: refs_by_document_key.get(key)
                for key in expected_invoice_keys
                if str(refs_by_document_key.get(key) or "").strip()
            },
        }
    )
    return _readback_result(
        diagnostics=diagnostics,
        readback_documents=readback_documents,
        readback_invoices=readback_invoices,
        evidence=evidence,
    )


def _fetch_json_document(
    *,
    adapter: ODataDocumentAdapter,
    database_id: str,
    entity_name: str,
    document_key: str,
    document_ref: str,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any] | None:
    response = adapter.fetch_document(entity_name=entity_name, entity_id=_guid_literal(document_ref))
    if response.status_code >= 400:
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_READBACK_FETCH_FAILED,
                database_id=database_id,
                entity_name=entity_name,
                document_idempotency_key=document_key,
                detail="KVO17 generated purchase readback could not fetch created document.",
                path="$document",
                http_status=response.status_code,
            )
        )
        return None
    payload = response.json()
    return dict(payload) if isinstance(payload, Mapping) else {}


def _fetch_table_part_rows(
    *,
    adapter: ODataDocumentAdapter,
    database_id: str,
    entity_name: str,
    table_part_name: str,
    document_key: str,
    document_ref: str,
    diagnostics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    response = adapter.fetch_document_table_part(
        entity_name=entity_name,
        entity_id=_guid_literal(document_ref),
        table_part_name=table_part_name,
    )
    if response.status_code >= 400:
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_READBACK_FETCH_FAILED,
                database_id=database_id,
                entity_name=entity_name,
                document_idempotency_key=document_key,
                detail="KVO17 generated purchase readback could not fetch invoice base-document table part.",
                path=table_part_name,
                http_status=response.status_code,
            )
        )
        return []
    payload = response.json()
    if isinstance(payload, Mapping):
        raw_rows = payload.get("value")
    else:
        raw_rows = payload
    if not isinstance(raw_rows, list):
        return []
    return [dict(row) for row in raw_rows if isinstance(row, Mapping)]


def _build_receipt_readback_document(
    *,
    row: Kvo17GeneratedPurchaseRow,
    document_key: str,
    document_ref: str,
    payload: Mapping[str, Any],
    database_id: str,
) -> dict[str, Any]:
    return {
        "database_id": database_id,
        "entity_name": _RECEIPT_ENTITY_NAME,
        "document_idempotency_key": document_key,
        "document_ref": document_ref,
        "counterparty_ref": row.counterparty_ref,
        "source_document_number": (
            payload.get("УдалитьНомерВходящегоСчетаФактуры")
            or payload.get("НомерВходящегоДокумента")
            or ""
        ),
        "source_document_date": (
            payload.get("УдалитьДатаВходящегоСчетаФактуры")
            or payload.get("ДатаВходящегоДокумента")
            or ""
        ),
        "kvo": payload.get("УдалитьКодВидаОперации") or payload.get("КодВидаОперации") or "",
        "amount": payload.get("СуммаДокумента"),
        "vat_amount": payload.get("СуммаНДСДокумента"),
        "posted": payload.get("Posted"),
    }


def _build_invoice_readback_document(
    *,
    row: Kvo17GeneratedPurchaseRow,
    document_key: str,
    document_ref: str,
    payload: Mapping[str, Any],
    base_rows: list[Mapping[str, Any]],
    database_id: str,
) -> dict[str, Any]:
    base_row = dict(base_rows[0]) if base_rows else {}
    return {
        "database_id": database_id,
        "entity_name": _INVOICE_ENTITY_NAME,
        "document_idempotency_key": document_key,
        "document_ref": document_ref,
        "counterparty_ref": row.counterparty_ref,
        "source_document_number": payload.get("НомерВходящегоДокумента") or "",
        "source_document_date": payload.get("ДатаВходящегоДокумента") or "",
        "kvo": payload.get("КодВидаОперации") or "",
        "amount": payload.get("СуммаДокумента"),
        "vat_amount": payload.get("СуммаНДСДокумента"),
        "posted": payload.get("Posted"),
        "linked_receipt_ref": (
            base_row.get("ДокументОснование")
            or base_row.get("ДокументОснование_Key")
            or ""
        ),
        "linked_receipt_type": base_row.get("ДокументОснование_Type") or "",
    }


def _build_preflight_report(
    *,
    manifest: Kvo17GeneratedPurchaseManifest,
    execution_context: Mapping[str, Any],
    target_database_ids: list[str],
    successful_refs: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    rows_by_counterparty = manifest.rows_by_counterparty()
    for counterparty in manifest.counterparties:
        rows = rows_by_counterparty[counterparty.ref]
        identity_pairs = {
            (row.source_document_number, row.source_document_date.isoformat())
            for row in rows
        }
        if len(rows) != 2 or len(identity_pairs) != 1 or {row.kvo for row in rows} != {"01", "17"}:
            diagnostics.append(
                _diagnostic(
                    code=KVO17_GENERATED_PURCHASE_EXPECTED_IDENTITY_INVALID,
                    counterparty_ref=counterparty.ref,
                    detail="Accepted KVO17 manifest does not contain one two-row shared invoice identity pair.",
                    path="manifest.rows",
                )
            )

    gate = execution_context.get("pool_runtime_master_data_gate")
    if isinstance(gate, Mapping):
        gate_status = str(gate.get("status") or "").strip().lower()
        checks.append(
            {
                "name": "master_data_gate",
                "status": gate_status,
                "bindings_count": gate.get("bindings_count"),
                "targets_count": gate.get("targets_count"),
            }
        )
        if gate_status not in {"completed", "skipped"}:
            diagnostics.append(
                _diagnostic(
                    code=KVO17_GENERATED_PURCHASE_MASTER_DATA_GATE_FAILED,
                    detail="KVO17 generated purchase publication did not complete target master-data resolution.",
                    path="pool_runtime_master_data_gate.status",
                    gate_status=gate_status,
                )
            )
    elif execution_context.get("pool_runtime_publication_payload") is not None:
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_MASTER_DATA_GATE_MISSING,
                severity="warning",
                detail="KVO17 generated purchase has no persisted master-data gate summary; readback will rely on exact created refs.",
                path="pool_runtime_master_data_gate",
            )
        )

    unresolved_token_paths = _collect_unresolved_publication_master_data_token_paths(
        execution_context.get("pool_runtime_publication_payload")
    )
    if unresolved_token_paths:
        diagnostics.append(
            _diagnostic(
                code=KVO17_GENERATED_PURCHASE_MASTER_DATA_UNRESOLVED,
                detail="KVO17 generated purchase payload still contains unresolved master_data.*.ref tokens.",
                path="pool_runtime_publication_payload",
                unresolved_token_paths=unresolved_token_paths[:32],
            )
        )

    expected_document_keys = {row.idempotency_key for row in manifest.rows}
    expected_invoice_keys = {f"{row.idempotency_key}:invoice" for row in manifest.rows}
    for database_id in target_database_ids:
        refs = successful_refs.get(database_id) or {}
        checks.append(
            {
                "name": "generated_identity_refs",
                "database_id": database_id,
                "expected_receipt_refs": len(expected_document_keys),
                "actual_receipt_refs": len([key for key in expected_document_keys if refs.get(key)]),
                "expected_invoice_refs": len(expected_invoice_keys),
                "actual_invoice_refs": len([key for key in expected_invoice_keys if refs.get(key)]),
                "pre_existing_duplicates_distinguished_by": "successful_document_refs",
            }
        )

    blocking = [item for item in diagnostics if str(item.get("severity") or "") == "error"]
    return {
        "status": "failed" if blocking else "passed",
        "diagnostics": diagnostics,
        "checks": checks,
    }


def _build_publication_report(
    *,
    diagnostics: list[dict[str, Any]],
    preflight: Mapping[str, Any],
    readback: Mapping[str, Any] | None,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    blocking = [
        diagnostic
        for diagnostic in diagnostics
        if str(diagnostic.get("severity") or "").strip().lower() == "error"
    ]
    readback_summary = dict(readback.get("summary") or {}) if isinstance(readback, Mapping) else {}
    verified_documents = int(readback_summary.get("readback_documents") or 0) + int(
        readback_summary.get("readback_invoice_documents") or 0
    )
    checked_targets = {
        str(item.get("database_id") or "").strip()
        for item in evidence
        if isinstance(item, Mapping) and str(item.get("database_id") or "").strip()
    }
    return {
        "status": "failed" if blocking else "passed",
        "summary": {
            "checked_targets": len(checked_targets),
            "verified_documents": verified_documents,
            "mismatches_count": len(blocking),
            "mismatches": [_diagnostic_to_mismatch(diagnostic) for diagnostic in blocking],
        },
        "diagnostics": diagnostics,
        "preflight": dict(preflight),
        "readback": dict(readback) if isinstance(readback, Mapping) else None,
        "evidence": evidence,
    }


def _resolve_generated_context(*, run: Any) -> dict[str, Any] | None:
    run_input = getattr(run, "run_input", None)
    if not isinstance(run_input, Mapping):
        return None
    context = run_input.get(KVO17_GENERATED_PURCHASE_METADATA_KEY)
    if not isinstance(context, Mapping):
        return None
    manifest = context.get("manifest")
    if not isinstance(manifest, Mapping):
        raise ValueError("KVO17 generated purchase manifest is missing.")
    return {**dict(context), "manifest": dict(manifest)}


def _collect_target_database_ids(
    *,
    execution_context: Mapping[str, Any],
    successful_refs: Mapping[str, Mapping[str, str]],
    publication_results: list[Mapping[str, Any]],
) -> list[str]:
    database_ids: list[str] = []

    artifact = execution_context.get("pool_runtime_document_plan_artifact")
    if isinstance(artifact, Mapping):
        for raw_target in artifact.get("targets") or []:
            if not isinstance(raw_target, Mapping):
                continue
            database_id = str(raw_target.get("database_id") or "").strip()
            if database_id and database_id not in database_ids:
                database_ids.append(database_id)

    for result in publication_results:
        raw_targets = result.get("target_databases") if isinstance(result, Mapping) else None
        if isinstance(raw_targets, list):
            for raw_database_id in raw_targets:
                database_id = str(raw_database_id or "").strip()
                if database_id and database_id not in database_ids:
                    database_ids.append(database_id)

    for database_id in successful_refs:
        normalized = str(database_id or "").strip()
        if normalized and normalized not in database_ids:
            database_ids.append(normalized)
    return database_ids


def _collect_successful_document_refs_from_attempts(*, run: Any) -> dict[str, dict[str, str]]:
    from .models import PoolPublicationAttempt, PoolPublicationAttemptStatus

    refs_by_database: dict[str, dict[str, str]] = {}
    for attempt in PoolPublicationAttempt.objects.filter(
        run=run,
        status=PoolPublicationAttemptStatus.SUCCESS,
    ):
        response_summary = attempt.response_summary
        if not isinstance(response_summary, Mapping):
            continue
        raw_refs = response_summary.get("successful_document_refs")
        if not isinstance(raw_refs, Mapping):
            continue
        database_refs = refs_by_database.setdefault(str(attempt.target_database_id), {})
        for raw_key, raw_ref in raw_refs.items():
            key = str(raw_key or "").strip()
            ref = str(raw_ref or "").strip()
            if key and ref:
                database_refs[key] = ref
    return refs_by_database


def _append_duplicate_ref_diagnostics(
    *,
    diagnostics: list[dict[str, Any]],
    database_id: str,
    refs_by_document_key: Mapping[str, str],
    expected_keys: list[str],
    code: str,
    entity_name: str,
) -> None:
    refs = [
        _canonical_ref(refs_by_document_key.get(key))
        for key in expected_keys
        if str(refs_by_document_key.get(key) or "").strip()
    ]
    if refs and len(set(refs)) != len(refs):
        diagnostics.append(
            _diagnostic(
                code=code,
                database_id=database_id,
                entity_name=entity_name,
                detail="KVO17 generated publication returned duplicate refs for documents that must stay distinct.",
                path="response_summary.successful_document_refs",
            )
        )


def _readback_result(
    *,
    diagnostics: list[dict[str, Any]],
    readback_documents: list[dict[str, Any]] | None = None,
    readback_invoices: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "diagnostics": diagnostics,
        "readback_documents": readback_documents or [],
        "readback_invoices": readback_invoices or [],
        "evidence": evidence or [],
    }


def _matches_counterparty_invoice(
    *,
    document: Mapping[str, Any],
    counterparty_ref: str,
    invoice_number: str,
    invoice_date: str,
) -> bool:
    document_counterparty = str(
        document.get("counterparty_ref")
        or document.get("source_supplier_ref")
        or document.get("Контрагент_Key")
        or ""
    ).strip()
    document_invoice_number = str(
        document.get("source_document_number")
        or document.get("invoice_number")
        or document.get("УдалитьНомерВходящегоСчетаФактуры")
        or document.get("НомерВходящегоДокумента")
        or ""
    ).strip()
    document_invoice_date = str(
        document.get("source_document_date")
        or document.get("invoice_date")
        or document.get("УдалитьДатаВходящегоСчетаФактуры")
        or document.get("ДатаВходящегоДокумента")
        or ""
    ).strip()
    return (
        document_counterparty == counterparty_ref
        and document_invoice_number == invoice_number
        and document_invoice_date[:10] == invoice_date
    )


def _document_kvo(document: Mapping[str, Any]) -> str:
    return str(
        document.get("kvo")
        or document.get("УдалитьКодВидаОперации")
        or document.get("КодВидаОперации")
        or ""
    ).strip()


def _amount(raw_value: Any) -> Decimal | None:
    value = str(raw_value or "").strip().replace(",", ".")
    if not value:
        return None
    try:
        return Decimal(value).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _canonical_ref(raw_ref: Any) -> str:
    text = str(raw_ref or "").strip()
    if not text:
        return ""
    if text.startswith("guid'") and text.endswith("'"):
        text = text[5:-1]
    if "(guid'" in text and text.endswith("')"):
        text = text.split("(guid'", 1)[1][:-2]
    if text.endswith(".ref"):
        text = text[:-4]
    return text.strip().lower()


def _collect_unresolved_publication_master_data_token_paths(payload: Any) -> list[str]:
    if not isinstance(payload, Mapping):
        return _collect_master_data_token_paths(payload)

    pool_runtime = payload.get("pool_runtime")
    if not isinstance(pool_runtime, Mapping):
        return _collect_master_data_token_paths(payload)

    paths: list[str] = []
    chains_by_database = pool_runtime.get("document_chains_by_database")
    if isinstance(chains_by_database, Mapping):
        for raw_database_id, chains in chains_by_database.items():
            database_id = str(raw_database_id or "").strip()
            if not database_id or not isinstance(chains, list):
                continue
            for chain_index, chain in enumerate(chains):
                if not isinstance(chain, Mapping):
                    continue
                documents = chain.get("documents")
                if not isinstance(documents, list):
                    continue
                for document_index, document in enumerate(documents):
                    if not isinstance(document, Mapping):
                        continue
                    document_path = (
                        "pool_runtime.document_chains_by_database."
                        f"{database_id}[{chain_index}].documents[{document_index}]"
                    )
                    resolved_by_token = _string_mapping(document.get("resolved_master_data_refs"))
                    resolved_by_path = _string_mapping(document.get("resolved_master_data_refs_by_path"))
                    paths.extend(
                        _collect_unresolved_master_data_mapping_token_paths(
                            document.get("field_mapping"),
                            mapping_path="field_mapping",
                            diagnostic_path=f"{document_path}.field_mapping",
                            resolved_by_token=resolved_by_token,
                            resolved_by_path=resolved_by_path,
                        )
                    )
                    paths.extend(
                        _collect_unresolved_master_data_mapping_token_paths(
                            document.get("table_parts_mapping"),
                            mapping_path="table_parts_mapping",
                            diagnostic_path=f"{document_path}.table_parts_mapping",
                            resolved_by_token=resolved_by_token,
                            resolved_by_path=resolved_by_path,
                        )
                    )

    if "documents_by_database" in pool_runtime:
        paths.extend(
            _collect_master_data_token_paths(
                pool_runtime.get("documents_by_database"),
                root_path="pool_runtime.documents_by_database",
            )
        )
    return paths


def _collect_unresolved_master_data_mapping_token_paths(
    payload: Any,
    *,
    mapping_path: str,
    diagnostic_path: str,
    resolved_by_token: Mapping[str, str],
    resolved_by_path: Mapping[str, str],
) -> list[str]:
    paths: list[str] = []

    def _walk(value: Any, current_mapping_path: str, current_diagnostic_path: str) -> None:
        if isinstance(value, str):
            token = value.strip()
            if (
                token.startswith("master_data.")
                and token.endswith(".ref")
                and not str(resolved_by_path.get(current_mapping_path) or "").strip()
                and not str(resolved_by_token.get(token) or "").strip()
            ):
                paths.append(current_diagnostic_path)
            return
        if isinstance(value, Mapping):
            for raw_key, nested in value.items():
                key = str(raw_key or "").strip()
                if not key:
                    continue
                nested_mapping_path = f"{current_mapping_path}.{key}" if current_mapping_path else key
                nested_diagnostic_path = f"{current_diagnostic_path}.{key}" if current_diagnostic_path else key
                _walk(nested, nested_mapping_path, nested_diagnostic_path)
            return
        if isinstance(value, list):
            for index, nested in enumerate(value):
                _walk(
                    nested,
                    f"{current_mapping_path}[{index}]",
                    f"{current_diagnostic_path}[{index}]",
                )

    _walk(payload, mapping_path, diagnostic_path)
    return paths


def _collect_master_data_token_paths(payload: Any, *, root_path: str = "") -> list[str]:
    paths: list[str] = []

    def _walk(value: Any, path: str) -> None:
        if isinstance(value, str):
            if "master_data." in value and value.endswith(".ref"):
                paths.append(path)
            return
        if isinstance(value, Mapping):
            for raw_key, nested in value.items():
                key = str(raw_key or "").strip()
                _walk(nested, f"{path}.{key}" if path else key)
            return
        if isinstance(value, list):
            for index, nested in enumerate(value):
                _walk(nested, f"{path}[{index}]")

    _walk(payload, root_path)
    return paths


def _string_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key or "").strip(): str(item or "").strip()
        for key, item in value.items()
        if str(key or "").strip() and str(item or "").strip()
    }


def _diagnostic(
    *,
    code: str,
    detail: str,
    severity: str = "error",
    **extra: Any,
) -> dict[str, Any]:
    diagnostic = {
        "code": str(code or "").strip(),
        "severity": severity,
        "detail": detail,
    }
    for key, value in extra.items():
        if value is not None and value != "":
            diagnostic[key] = value
    return diagnostic


def _diagnostic_to_mismatch(diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "database_id": str(diagnostic.get("database_id") or "").strip(),
        "entity_name": str(diagnostic.get("entity_name") or "").strip(),
        "document_idempotency_key": str(diagnostic.get("document_idempotency_key") or "").strip(),
        "field_or_table_path": str(diagnostic.get("path") or diagnostic.get("field_or_table_path") or "").strip(),
        "kind": str(diagnostic.get("code") or "").strip(),
    }


__all__ = [
    "KVO17_GENERATED_PURCHASE_AMOUNT_MISMATCH",
    "KVO17_GENERATED_PURCHASE_COLLAPSED_DOCUMENTS",
    "KVO17_GENERATED_PURCHASE_INVOICE_COLLAPSED_DOCUMENTS",
    "KVO17_GENERATED_PURCHASE_INVOICE_LINK_MISMATCH",
    "KVO17_GENERATED_PURCHASE_INVOICE_READBACK_COUNT_MISMATCH",
    "KVO17_GENERATED_PURCHASE_KVO_MISMATCH",
    "KVO17_GENERATED_PURCHASE_READBACK_COUNT_MISMATCH",
    "KVO17_GENERATED_PURCHASE_VERIFICATION_CONTEXT_KEY",
    "verify_kvo17_generated_purchase_publication",
    "verify_kvo17_generated_purchase_readback",
]
