from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from django.utils import timezone

from .document_plan_artifact_contract import (
    POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY,
    POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_SLOTS_CONTEXT_KEY,
    POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY,
    POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY,
    build_publication_payload_from_document_plan_artifact,
    compile_document_plan_artifact_v1,
    validate_compiled_document_policy_slots_snapshot,
    validate_document_plan_artifact_v1,
)
from .document_policy_topology_aliases import (
    MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING,
    MASTER_DATA_PARTY_ROLE_MISSING,
    POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID,
    TopologyAwareMasterDataAliasError,
)
from .distribution_artifact_contract import (
    POOL_DISTRIBUTION_ARTIFACT_INVALID,
    POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY,
    resolve_distribution_artifact_for_downstream_compile,
    validate_distribution_artifact_v1,
)
from .master_data_artifact_contract import (
    MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
    POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY,
)
from .master_data_errors import (
    MASTER_DATA_BINDING_AMBIGUOUS,
    MASTER_DATA_BINDING_CONFLICT,
    MASTER_DATA_ENTITY_NOT_FOUND,
    MasterDataResolveError,
)
from .master_data_feature_flags import (
    MasterDataGateConfigInvalidError,
    is_pool_master_data_gate_enabled,
)
from .master_data_gate import (
    collect_master_data_resolution_readiness_blockers,
    execute_master_data_resolve_upsert_gate,
    publication_payload_requires_master_data_resolution,
)
from .kvo18_advance_vat_offset_document_plan import (
    compile_kvo18_advance_vat_offset_document_plan,
)
from .kvo18_advance_vat_offset_intake import KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS
from .kvo18_advance_vat_offset_preview import Kvo18AdvanceVatOffsetPreview
from .kvo17_generated_purchase_intake import KVO17_GENERATED_PURCHASE_METADATA_KEY
from .models import Organization, PoolMasterParty, PoolRun, PoolRunDirection, PoolRunMode
from .organization_party_binding_backfill import (
    REMEDIATION_REASON_AMBIGUOUS_MATCH,
    REMEDIATION_REASON_CANDIDATE_ALREADY_BOUND,
    REMEDIATION_REASON_NO_MATCH,
)
from .runtime_distribution import (
    DISTRIBUTION_ARTIFACT_VERSION,
    build_publication_payload_from_artifact,
    compute_distribution_runtime_state,
    load_runtime_topology_for_period,
)
from .runtime_run_input import build_runtime_run_input


APPROVAL_STATE_NOT_REQUIRED = "not_required"
APPROVAL_STATE_PREPARING = "preparing"
APPROVAL_STATE_AWAITING_APPROVAL = "awaiting_approval"
APPROVAL_STATE_APPROVED = "approved"

PUBLICATION_STEP_STATE_NOT_ENQUEUED = "not_enqueued"
PUBLICATION_STEP_STATE_QUEUED = "queued"
PUBLICATION_STEP_STATE_STARTED = "started"
PUBLICATION_STEP_STATE_COMPLETED = "completed"

_OP_PREPARE_INPUT = "pool.prepare_input"
_OP_DISTRIBUTION_TOP_DOWN = "pool.distribution_calculation.top_down"
_OP_DISTRIBUTION_BOTTOM_UP = "pool.distribution_calculation.bottom_up"
_OP_RECONCILIATION = "pool.reconciliation_report"
_OP_APPROVAL_GATE = "pool.approval_gate"
_OP_MASTER_DATA_GATE = "pool.master_data_gate"
_OP_PUBLICATION = "pool.publication_odata"
_KVO18_ADVANCE_VAT_OFFSET_METADATA_KEY = "kvo18_advance_vat_offset"
_OP_KVO18_NORMALIZE = "pool.kvo18_advance_vat_offset.normalize"
_OP_KVO17_PURCHASE_SPLIT_PREVIEW = "pool.kvo17_purchase_split.preview"
_KVO18_STAGE_SLOT_BY_OPERATION = {
    "pool.kvo18_advance_vat_offset.cash_receipt_order": "cash_receipt_order",
    "pool.kvo18_advance_vat_offset.advance_invoice": "advance_invoice_kvo01",
    "pool.kvo18_advance_vat_offset.offset": "advance_offset_kvo18",
    "pool.kvo18_advance_vat_offset.declaration_evidence": "declaration_evidence",
}
POOL_RUNTIME_PUBLICATION_PATH_DISABLED = "POOL_RUNTIME_PUBLICATION_PATH_DISABLED"
POOL_RUNTIME_RETRY_PAYLOAD_INVALID = "POOL_RUNTIME_RETRY_PAYLOAD_INVALID"
POOL_DISTRIBUTION_BALANCE_MISMATCH = "POOL_DISTRIBUTION_BALANCE_MISMATCH"
POOL_DISTRIBUTION_COVERAGE_GAP = "POOL_DISTRIBUTION_COVERAGE_GAP"
POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_REQUIRED = "POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_REQUIRED"
POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY = "pool_runtime_readiness_blockers"
KVO18_POLICY_SLOT_MISSING = "KVO18_POLICY_SLOT_MISSING"
KVO18_STAGE_TARGET_DATABASE_MISSING = "KVO18_STAGE_TARGET_DATABASE_MISSING"


def execute_pool_runtime_step(
    *,
    operation_type: str,
    rendered_data: dict[str, Any],
    context: dict[str, Any],
    execution: Any,
) -> dict[str, Any]:
    run = _resolve_pool_run(context=context, execution=execution)
    execution_context = execution.input_context if isinstance(getattr(execution, "input_context", None), dict) else {}

    if operation_type == _OP_PREPARE_INPUT:
        return _execute_prepare_input(run=run, execution=execution, execution_context=execution_context)

    if operation_type == _OP_DISTRIBUTION_TOP_DOWN:
        return _execute_distribution_top_down(run=run, execution=execution, execution_context=execution_context)

    if operation_type == _OP_DISTRIBUTION_BOTTOM_UP:
        return _execute_distribution_bottom_up(run=run, execution=execution, execution_context=execution_context)

    if operation_type == _OP_RECONCILIATION:
        return _execute_reconciliation(run=run, execution=execution, execution_context=execution_context)

    if operation_type == _OP_APPROVAL_GATE:
        return _execute_approval_gate(run=run, execution=execution, execution_context=execution_context)

    if operation_type == _OP_MASTER_DATA_GATE:
        return _execute_master_data_gate(
            run=run,
            execution=execution,
            execution_context=execution_context,
        )

    if operation_type == _OP_PUBLICATION:
        return _execute_publication(
            run=run,
            execution=execution,
            execution_context=execution_context,
            rendered_data=rendered_data,
        )

    if operation_type == _OP_KVO18_NORMALIZE or operation_type in _KVO18_STAGE_SLOT_BY_OPERATION:
        return _execute_kvo18_advance_vat_offset_step(
            run=run,
            execution=execution,
            execution_context=execution_context,
            operation_type=operation_type,
        )

    if operation_type == _OP_KVO17_PURCHASE_SPLIT_PREVIEW:
        return _execute_kvo17_purchase_split_preview_step(
            run=run,
            execution=execution,
            execution_context=execution_context,
        )

    raise ValueError(f"POOL_RUNTIME_STEP_UNSUPPORTED: unsupported operation_type '{operation_type}'")


def _resolve_pool_run(*, context: dict[str, Any], execution: Any) -> PoolRun:
    pool_run_id = str(context.get("pool_run_id") or "").strip()
    if not pool_run_id:
        raise ValueError("POOL_RUNTIME_CONTEXT_INVALID: missing pool_run_id in workflow context")

    run = PoolRun.objects.filter(id=pool_run_id).first()
    if run is None:
        raise ValueError(f"POOL_RUNTIME_RUN_NOT_FOUND: pool run '{pool_run_id}' was not found")

    execution_id = str(getattr(execution, "id", "") or "").strip()
    if execution_id and run.workflow_execution_id and str(run.workflow_execution_id) != execution_id:
        raise ValueError(
            "POOL_RUNTIME_RUN_LINK_MISMATCH: "
            f"run '{run.id}' is linked to execution '{run.workflow_execution_id}', got '{execution_id}'"
        )

    execution_tenant_id = str(getattr(execution, "tenant_id", "") or "").strip()
    if execution_tenant_id and execution_tenant_id != str(run.tenant_id):
        raise ValueError(
            "POOL_RUNTIME_TENANT_MISMATCH: "
            f"execution tenant '{execution_tenant_id}' does not match run tenant '{run.tenant_id}'"
        )

    return run


def _execute_prepare_input(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    run_input = _run_input(run)
    approval_state = _resolve_approval_state(run=run, execution_context=execution_context)
    publication_step_state = _resolve_publication_step_state(
        run=run,
        approval_state=approval_state,
        execution_context=execution_context,
    )
    approved_at = _resolve_approved_at(run=run, execution_context=execution_context)

    prepared_payload: dict[str, Any] = {
        "direction": run.direction,
        "mode": run.mode,
    }
    source_rows = _source_rows(run_input=run_input)
    if run.direction == PoolRunDirection.TOP_DOWN:
        starting_amount = _parse_decimal(run_input.get("starting_amount"))
        prepared_payload["starting_amount"] = _decimal_to_string(starting_amount)
    else:
        prepared_payload["source_rows_count"] = len(source_rows)
        prepared_payload["source_total_amount"] = _decimal_to_string(_sum_source_amounts(source_rows))
        source_artifact_id = str(run_input.get("source_artifact_id") or "").strip()
        if source_artifact_id:
            prepared_payload["source_artifact_id"] = source_artifact_id

    updates: dict[str, Any] = {
        "approval_state": approval_state,
        "publication_step_state": publication_step_state,
        "pool_runtime_prepared_input": prepared_payload,
    }
    if approved_at is not None:
        updates["approved_at"] = approved_at
    _update_execution_context(execution=execution, updates=updates)

    return {
        "step": "prepare_input",
        "pool_run_id": str(run.id),
        "prepared_input": prepared_payload,
        "approval_state": approval_state,
        "publication_step_state": publication_step_state,
    }


def _execute_kvo17_purchase_split_preview_step(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    run_input = _run_input(run)
    kvo17_context = run_input.get(KVO17_GENERATED_PURCHASE_METADATA_KEY)
    if isinstance(kvo17_context, Mapping):
        distribution_result = _execute_kvo17_generated_distribution_if_available(
            run=run,
            execution=execution,
            execution_context=execution_context,
        )
        if distribution_result is None:
            raise ValueError(
                "KVO17_GENERATED_DOCUMENT_PLAN_REQUIRED: "
                "generated KVO17 preview requires pool_runtime_document_plan_artifact before publication"
            )
        publication_payload = distribution_result.get("publication_payload")
        master_data_resolution: dict[str, Any] | None = None
        preview_execution_context = {
            **execution_context,
            "pool_runtime_publication_payload": publication_payload,
        }
        if publication_payload_requires_master_data_resolution(
            execution_context=preview_execution_context,
        ):
            gate_result = _execute_master_data_gate(
                run=run,
                execution=execution,
                execution_context=preview_execution_context,
            )
            resolved_publication_payload = gate_result.get("publication_payload")
            if isinstance(resolved_publication_payload, Mapping):
                publication_payload = resolved_publication_payload
            summary = gate_result.get("summary")
            if isinstance(summary, Mapping):
                master_data_resolution = dict(summary)
        pool_runtime_payload = (
            publication_payload.get("pool_runtime")
            if isinstance(publication_payload, Mapping)
            else {}
        )
        documents_by_database = (
            pool_runtime_payload.get("documents_by_database")
            if isinstance(pool_runtime_payload, Mapping)
            else {}
        )
        target_database_count = (
            len(documents_by_database)
            if isinstance(documents_by_database, Mapping)
            else 0
        )
        document_plan = (
            dict(kvo17_context.get("document_plan"))
            if isinstance(kvo17_context.get("document_plan"), Mapping)
            else {}
        )
        compile_summary_raw = document_plan.get("compile_summary")
        compile_summary = (
            dict(compile_summary_raw)
            if isinstance(compile_summary_raw, Mapping)
            else {}
        )
        result = {
            "step": "kvo17_purchase_split.preview",
            "status": "ready",
            "source_type": KVO17_GENERATED_PURCHASE_METADATA_KEY,
            "pool_run_id": str(run.id),
            "content_hash": str(kvo17_context.get("content_hash") or "").strip(),
            "document_plan_version": str(kvo17_context.get("document_plan_version") or "").strip(),
            "edge_strategy": dict(document_plan.get("edge_strategy") or {}),
            "compile_summary": compile_summary,
            "publication_payload_prepared": True,
            "target_database_count": target_database_count,
            "documents_count": int(
                compile_summary.get("documents_count")
                or sum(
                    len(documents)
                    for documents in documents_by_database.values()
                    if isinstance(documents, list)
                )
            ),
        }
        if master_data_resolution is not None:
            result["master_data_resolution"] = master_data_resolution
    else:
        result = {
            "step": "kvo17_purchase_split.preview",
            "status": "not_applicable",
            "pool_run_id": str(run.id),
        }
    _update_execution_context(
        execution=execution,
        updates={"kvo17_purchase_split_preview": result},
    )
    return result


def _execute_kvo18_advance_vat_offset_step(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
    operation_type: str,
) -> dict[str, Any]:
    run_input = _run_input(run)
    kvo18_context = run_input.get(_KVO18_ADVANCE_VAT_OFFSET_METADATA_KEY)
    if not isinstance(kvo18_context, Mapping):
        raise ValueError("KVO18_RUNTIME_CONTEXT_MISSING: run_input is missing KVO18 advance VAT offset context")

    if operation_type == _OP_KVO18_NORMALIZE:
        result = {
            "step": "kvo18_advance_vat_offset.normalize",
            "status": "normalized",
            "pool_run_id": str(run.id),
            "policy_revision": str(kvo18_context.get("policy_revision") or "").strip(),
            "content_hash": str(kvo18_context.get("content_hash") or "").strip(),
        }
        _update_execution_context(
            execution=execution,
            updates={"kvo18_advance_vat_offset_normalized": result},
        )
        return result

    stage_slot = _KVO18_STAGE_SLOT_BY_OPERATION[operation_type]
    stages = kvo18_context.get("stages")
    stage = stages.get(stage_slot) if isinstance(stages, Mapping) else None
    if not isinstance(stage, Mapping):
        raise ValueError(f"KVO18_STAGE_CONTEXT_MISSING: stage '{stage_slot}' is missing from KVO18 context")

    stage_intent = str(kvo18_context.get("stage_intent") or "").strip()
    stage_state = str(stage.get("state") or "").strip()
    if stage_intent and stage_intent != stage_slot:
        status = "skipped"
        reason = "stage_intent_mismatch"
    elif stage_state != "ready":
        status = "blocked"
        reason = "prerequisites_not_satisfied"
    else:
        status = "ready"
        reason = ""

    result = {
        "step": f"kvo18_advance_vat_offset.{stage_slot}",
        "status": status,
        "reason": reason,
        "pool_run_id": str(run.id),
        "stage_slot": stage_slot,
        "stage_intent": stage_intent,
        "prerequisites": list(stage.get("prerequisites") or []),
        "produces": list(stage.get("produces") or []),
        "policy_revision": str(kvo18_context.get("policy_revision") or "").strip(),
        "content_hash": str(kvo18_context.get("content_hash") or "").strip(),
    }
    updates: dict[str, Any] = {
        f"kvo18_advance_vat_offset_stage_{stage_slot}": result,
    }
    if status == "ready":
        publication_payload = _build_kvo18_stage_publication_payload(
            run=run,
            run_input=run_input,
            execution_context=execution_context,
            kvo18_context=kvo18_context,
            stage_slot=stage_slot,
        )
        result["publication_payload"] = publication_payload
        updates[f"kvo18_advance_vat_offset_stage_{stage_slot}"] = result
        updates["pool_runtime_publication_payload"] = publication_payload

    _update_execution_context(
        execution=execution,
        updates=updates,
    )
    return result


def _build_kvo18_stage_publication_payload(
    *,
    run: PoolRun,
    run_input: Mapping[str, Any],
    execution_context: Mapping[str, Any],
    kvo18_context: Mapping[str, Any],
    stage_slot: str,
) -> dict[str, Any]:
    policy_slots = validate_compiled_document_policy_slots_snapshot(
        execution_context.get(POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_SLOTS_CONTEXT_KEY)
    )
    missing_slots = [
        slot_key
        for slot_key in KVO18_ADVANCE_VAT_OFFSET_POLICY_SLOTS
        if not isinstance(policy_slots, Mapping) or slot_key not in policy_slots
    ]
    if missing_slots:
        raise ValueError(
            f"{KVO18_POLICY_SLOT_MISSING}: KVO18 stage '{stage_slot}' requires compiled policy slots: "
            + ", ".join(missing_slots)
        )

    preview = _build_kvo18_preview_from_context(kvo18_context=kvo18_context)
    document_plan = compile_kvo18_advance_vat_offset_document_plan(
        preview=preview,
        compiled_policy_slots=policy_slots,
    )
    stage_plan_raw = document_plan.get("stages", {}).get(stage_slot)
    if not isinstance(stage_plan_raw, Mapping):
        raise ValueError(f"KVO18_STAGE_CONTEXT_MISSING: document plan stage '{stage_slot}' is missing")
    stage_plan = dict(stage_plan_raw)
    database_id = _resolve_kvo18_stage_database_id(
        run=run,
        run_input=run_input,
        execution_context=execution_context,
        stage_slot=stage_slot,
    )
    documents_by_database, document_chains_by_database, entity_name = _materialize_kvo18_stage_documents(
        stage_plan=stage_plan,
        document_plan=document_plan,
        database_id=database_id,
        rows=preview.rows,
    )
    return {
        "pool_runtime": {
            "entity_name": entity_name,
            "documents_by_database": documents_by_database,
            "document_chains_by_database": document_chains_by_database,
            "kvo18_stage_slot": stage_slot,
            "kvo18_stage_state": stage_plan.get("state"),
            "kvo18_document_plan_artifact": document_plan,
            "max_attempts": run_input.get("max_attempts"),
            "retry_interval_seconds": run_input.get("retry_interval_seconds"),
            "external_key_field": str(run_input.get("external_key_field") or "").strip(),
        }
    }


def _build_kvo18_preview_from_context(
    *,
    kvo18_context: Mapping[str, Any],
) -> Kvo18AdvanceVatOffsetPreview:
    rows_raw = kvo18_context.get("rows")
    rows = [dict(row) for row in rows_raw if isinstance(row, Mapping)] if isinstance(rows_raw, list) else []
    if not rows:
        raise ValueError("KVO18_RUNTIME_ROWS_MISSING: KVO18 stage publication requires normalized rows")
    total_amount = Decimal("0.00")
    total_vat_amount = Decimal("0.00")
    for row in rows:
        total_amount += _parse_decimal(row.get("amount")) or Decimal("0.00")
        total_vat_amount += _parse_decimal(row.get("vat_amount")) or Decimal("0.00")
    currency = str(rows[0].get("currency") or "RUB").strip() or "RUB"
    stages_raw = kvo18_context.get("stages")
    technical_policy_raw = kvo18_context.get("technical_realization_policy")
    evidence_requirements_raw = kvo18_context.get("evidence_requirements")
    diagnostics_raw = kvo18_context.get("diagnostics")
    return Kvo18AdvanceVatOffsetPreview(
        policy_revision=str(kvo18_context.get("policy_revision") or "").strip(),
        total_amount=_decimal_to_string(total_amount) or "0.00",
        total_vat_amount=_decimal_to_string(total_vat_amount) or "0.00",
        currency=currency,
        row_count=len(rows),
        rows=rows,
        stages=dict(stages_raw) if isinstance(stages_raw, Mapping) else {},
        technical_realization_policy=(
            dict(technical_policy_raw) if isinstance(technical_policy_raw, Mapping) else {}
        ),
        evidence_requirements=(
            dict(evidence_requirements_raw) if isinstance(evidence_requirements_raw, Mapping) else {}
        ),
        diagnostics=(
            [dict(item) for item in diagnostics_raw if isinstance(item, Mapping)]
            if isinstance(diagnostics_raw, list)
            else []
        ),
        content_hash=str(kvo18_context.get("content_hash") or "").strip(),
    )


def _resolve_kvo18_stage_database_id(
    *,
    run: PoolRun,
    run_input: Mapping[str, Any],
    execution_context: Mapping[str, Any],
    stage_slot: str,
) -> str:
    document_plan = _resolve_persisted_document_plan_artifact(
        execution_context=dict(execution_context)
    )
    if document_plan is not None:
        database_id = _resolve_kvo18_database_id_from_document_plan(
            document_plan=document_plan,
            stage_slot=stage_slot,
        )
        if database_id:
            return database_id

    start_organization_id = str(run_input.get("start_organization_id") or "").strip()
    if start_organization_id:
        organization = (
            Organization.objects.filter(
                id=start_organization_id,
                tenant_id=run.tenant_id,
            )
            .only("database_id")
            .first()
        )
        if organization is not None and organization.database_id:
            return str(organization.database_id)

    raise ValueError(
        f"{KVO18_STAGE_TARGET_DATABASE_MISSING}: KVO18 stage '{stage_slot}' requires a target database"
    )


def _resolve_kvo18_database_id_from_document_plan(
    *,
    document_plan: Mapping[str, Any],
    stage_slot: str,
) -> str:
    policy_edge_refs = {
        (
            str(ref.get("edge_ref", {}).get("parent_node_id") or "").strip(),
            str(ref.get("edge_ref", {}).get("child_node_id") or "").strip(),
        )
        for ref in document_plan.get("policy_refs", [])
        if isinstance(ref, Mapping) and str(ref.get("slot_key") or "").strip() == stage_slot
    }
    targets = document_plan.get("targets")
    if not isinstance(targets, list):
        return ""
    for target in targets:
        if not isinstance(target, Mapping):
            continue
        database_id = str(target.get("database_id") or "").strip()
        chains = target.get("chains")
        if not database_id or not isinstance(chains, list):
            continue
        for chain in chains:
            if not isinstance(chain, Mapping):
                continue
            edge_ref = chain.get("edge_ref")
            edge_key = (
                str(edge_ref.get("parent_node_id") or "").strip(),
                str(edge_ref.get("child_node_id") or "").strip(),
            ) if isinstance(edge_ref, Mapping) else ("", "")
            if edge_key in policy_edge_refs:
                return database_id
    return ""


def _materialize_kvo18_stage_documents(
    *,
    stage_plan: Mapping[str, Any],
    document_plan: Mapping[str, Any],
    database_id: str,
    rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], str]:
    documents_by_database: dict[str, list[dict[str, Any]]] = {database_id: []}
    document_chains_by_database: dict[str, list[dict[str, Any]]] = {database_id: []}
    entity_name = ""
    policy_version = _resolve_kvo18_stage_policy_version(
        document_plan=document_plan,
        stage_slot=str(stage_plan.get("slot_key") or "").strip(),
    )
    for document in list(stage_plan.get("documents") or []):
        if not isinstance(document, Mapping):
            continue
        chain_documents: list[dict[str, Any]] = []
        for row in rows:
            payload = _materialize_kvo18_document_payload(document=document, row=row)
            if not entity_name:
                entity_name = str(document.get("entity_name") or "").strip()
            documents_by_database[database_id].append(payload)
            chain_documents.append(
                {
                    "document_id": str(document.get("document_id") or "").strip(),
                    "entity_name": str(document.get("entity_name") or "").strip(),
                    "document_role": str(document.get("document_role") or "").strip(),
                    "idempotency_key": _build_kvo18_stage_document_idempotency_key(
                        document_plan=document_plan,
                        stage_slot=str(stage_plan.get("slot_key") or "").strip(),
                        row=row,
                        document=document,
                    ),
                    "invoice_mode": str(document.get("invoice_mode") or "").strip(),
                    "field_mapping": dict(document.get("field_mapping") or {}),
                    "table_parts_mapping": dict(document.get("table_parts_mapping") or {}),
                    "link_rules": dict(document.get("link_rules") or {}),
                    "payload": payload,
                    "row_lineage": dict(row.get("lineage") or {}),
                }
            )
        if chain_documents:
            document_chains_by_database[database_id].append(
                {
                    "chain_id": str(document.get("chain_id") or "").strip(),
                    "policy_source": str(stage_plan.get("document_policy_source") or "").strip(),
                    "policy_version": policy_version,
                    "allocation": {
                        "amount": _decimal_to_string(
                            sum(
                                (_parse_decimal(row.get("amount")) or Decimal("0.00"))
                                for row in rows
                            )
                        ),
                    },
                    "documents": chain_documents,
                }
            )
    return documents_by_database, document_chains_by_database, entity_name


def _materialize_kvo18_document_payload(
    *,
    document: Mapping[str, Any],
    row: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    field_mapping = document.get("field_mapping")
    if isinstance(field_mapping, Mapping):
        for raw_field_name, raw_mapping in field_mapping.items():
            field_name = str(raw_field_name or "").strip()
            if not field_name:
                continue
            resolved_value, is_resolved = _resolve_kvo18_mapping_value(raw_mapping, row=row)
            if is_resolved:
                payload[field_name] = resolved_value
    table_parts_mapping = document.get("table_parts_mapping")
    if isinstance(table_parts_mapping, Mapping):
        for raw_table_name, raw_rows in table_parts_mapping.items():
            table_name = str(raw_table_name or "").strip()
            if not table_name or not isinstance(raw_rows, list):
                continue
            compiled_rows: list[dict[str, Any]] = []
            for raw_row in raw_rows:
                if not isinstance(raw_row, Mapping):
                    continue
                compiled_row: dict[str, Any] = {}
                for raw_column_name, raw_mapping in raw_row.items():
                    column_name = str(raw_column_name or "").strip()
                    if not column_name:
                        continue
                    resolved_value, is_resolved = _resolve_kvo18_mapping_value(raw_mapping, row=row)
                    if is_resolved:
                        compiled_row[column_name] = resolved_value
                if compiled_row:
                    compiled_rows.append(compiled_row)
            if compiled_rows:
                payload[table_name] = compiled_rows
    return payload


def _resolve_kvo18_mapping_value(
    value: Any,
    *,
    row: Mapping[str, Any],
) -> tuple[Any, bool]:
    if isinstance(value, Mapping):
        payload: dict[str, Any] = {}
        for raw_key, raw_item in value.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            resolved_value, is_resolved = _resolve_kvo18_mapping_value(raw_item, row=row)
            if is_resolved:
                payload[key] = resolved_value
        return payload, bool(payload)
    if isinstance(value, list):
        items: list[Any] = []
        for raw_item in value:
            resolved_value, is_resolved = _resolve_kvo18_mapping_value(raw_item, row=row)
            if is_resolved:
                items.append(resolved_value)
        return items, bool(items)
    if isinstance(value, str):
        token = value.strip()
        if token == "":
            return "", True
        if token.startswith("advance_row."):
            return _resolve_kvo18_row_token(row=row, token=token.removeprefix("advance_row."))
        if token == "policy.technical_realization.amount":
            return str(row.get("amount") or "").strip(), True
        if token.startswith(("cash_receipt_order.", "advance_invoice.", "advance_offset.", "declaration.")):
            return None, False
        return token, True
    if value is None:
        return None, False
    return value, True


def _resolve_kvo18_row_token(
    *,
    row: Mapping[str, Any],
    token: str,
) -> tuple[Any, bool]:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return None, False
    if normalized_token == "counterparty_ref":
        counterparty = row.get("counterparty")
        if isinstance(counterparty, Mapping):
            value = str(counterparty.get("ref") or "").strip()
            return value, bool(value)
    if normalized_token == "contract_ref":
        contract = row.get("contract")
        if isinstance(contract, Mapping):
            value = str(contract.get("ref") or "").strip()
            return value, bool(value)
    if normalized_token == "currency_ref":
        value = str(row.get("currency") or "").strip()
        return value, bool(value)
    value = row.get(normalized_token)
    if value is None:
        return None, False
    return value, True


def _resolve_kvo18_stage_policy_version(
    *,
    document_plan: Mapping[str, Any],
    stage_slot: str,
) -> str:
    policy_refs = document_plan.get("policy_refs")
    if isinstance(policy_refs, list):
        for policy_ref in policy_refs:
            if not isinstance(policy_ref, Mapping):
                continue
            if str(policy_ref.get("slot_key") or "").strip() == stage_slot:
                return str(policy_ref.get("policy_version") or "").strip()
    return ""


def _build_kvo18_stage_document_idempotency_key(
    *,
    document_plan: Mapping[str, Any],
    stage_slot: str,
    row: Mapping[str, Any],
    document: Mapping[str, Any],
) -> str:
    idempotency = document_plan.get("idempotency")
    lineage_ref = (
        str(idempotency.get("lineage_revision_ref") or "").strip()
        if isinstance(idempotency, Mapping)
        else ""
    )
    return ":".join(
        [
            "kvo18-stage",
            lineage_ref or str(document_plan.get("content_hash") or "").strip(),
            stage_slot,
            str(row.get("row_fingerprint") or row.get("row_id") or "").strip(),
            str(document.get("document_id") or "").strip(),
        ]
    )


def _execute_distribution_top_down(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    return _execute_distribution_calculation(
        run=run,
        execution=execution,
        expected_direction=PoolRunDirection.TOP_DOWN,
        execution_context=execution_context,
    )


def _execute_distribution_bottom_up(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    return _execute_distribution_calculation(
        run=run,
        execution=execution,
        expected_direction=PoolRunDirection.BOTTOM_UP,
        execution_context=execution_context,
    )


def _execute_reconciliation(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    distribution_artifact = resolve_distribution_artifact_for_downstream_compile(
        execution_context=execution_context
    )
    coverage_payload = distribution_artifact.get("coverage")
    coverage = dict(coverage_payload) if isinstance(coverage_payload, Mapping) else {}
    balance_payload = distribution_artifact.get("balance")
    balance = dict(balance_payload) if isinstance(balance_payload, Mapping) else {}

    if not bool(balance.get("is_balanced")):
        delta = _decimal_to_string(_parse_decimal(balance.get("delta")))
        source_total = _decimal_to_string(_parse_decimal(balance.get("source_total")))
        distributed_total = _decimal_to_string(_parse_decimal(balance.get("distributed_total")))
        raise ValueError(
            f"{POOL_DISTRIBUTION_BALANCE_MISMATCH}: "
            f"source_total={source_total}, distributed_total={distributed_total}, delta={delta}"
        )

    if not bool(coverage.get("is_full")):
        missing_nodes_raw = coverage.get("missing_target_node_ids")
        missing_nodes = (
            [str(node_id).strip() for node_id in missing_nodes_raw if str(node_id).strip()]
            if isinstance(missing_nodes_raw, list)
            else []
        )
        missing_nodes_text = ", ".join(missing_nodes) if missing_nodes else "unknown"
        raise ValueError(
            f"{POOL_DISTRIBUTION_COVERAGE_GAP}: missing publish-target nodes: {missing_nodes_text}"
        )

    document_plan_artifact = _resolve_persisted_document_plan_artifact(
        execution_context=execution_context
    )
    if document_plan_artifact is None:
        compiled_document_policy_slots = _resolve_compiled_document_policy_slots_for_execution_context(
            execution_context=execution_context
        )
        compiled_document_policy = _resolve_compiled_document_policy_for_execution_context(
            execution_context=execution_context
        )
        document_policy_source = _resolve_document_policy_source_for_execution_context(
            execution_context=execution_context
        )
        if (
            _has_workflow_binding_context(execution_context)
            and compiled_document_policy_slots is None
        ):
            raise ValueError(
                f"{POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_REQUIRED}: "
                "compiled document policy slots are required for workflow-bound reconciliation"
            )
        publication_payload = build_publication_payload_from_artifact(
            artifact=distribution_artifact,
            run_input=_run_input(run),
        )
        topology = load_runtime_topology_for_period(run=run)
        try:
            document_plan_artifact = compile_document_plan_artifact_v1(
                run=run,
                distribution_artifact=distribution_artifact,
                topology=topology,
                compiled_document_policy_slots=compiled_document_policy_slots,
                compiled_document_policy=compiled_document_policy,
                document_policy_source=document_policy_source,
            )
        except ValueError as exc:
            blocker = _build_readiness_blocker_from_error(exc)
            if blocker is not None:
                _update_execution_context(
                    execution=execution,
                    updates={POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: [blocker]},
                )
            raise
        if document_plan_artifact is not None:
            publication_payload = build_publication_payload_from_document_plan_artifact(
                artifact=document_plan_artifact,
                run_input=_run_input(run),
            )
    else:
        publication_payload = build_publication_payload_from_document_plan_artifact(
            artifact=document_plan_artifact,
            run_input=_run_input(run),
        )
    locked_retry_payload = _resolve_locked_retry_publication_payload(
        execution_context=execution_context
    )
    if locked_retry_payload is not None:
        publication_payload = locked_retry_payload
    report: dict[str, Any] = {
        "run_direction": run.direction,
        "distribution_artifact_version": distribution_artifact.get("version"),
        "topology_version_ref": distribution_artifact.get("topology_version_ref"),
        "balanced": True,
        "coverage_full": True,
        "missing_target_node_ids": [],
        "source_total_amount": balance.get("source_total"),
        "distributed_total_amount": balance.get("distributed_total"),
        "delta": balance.get("delta"),
        "status": "ok",
        "generated_at": timezone.now().isoformat(),
    }

    execution_updates: dict[str, Any] = {
        "pool_runtime_reconciliation": report,
        "pool_runtime_publication_payload": publication_payload,
        POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: [],
    }
    if document_plan_artifact is not None:
        execution_updates[POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY] = document_plan_artifact

    _update_execution_context(
        execution=execution,
        updates=execution_updates,
    )
    response = {
        "step": "reconciliation_report",
        "pool_run_id": str(run.id),
        "report": report,
        "distribution_artifact": distribution_artifact,
        "publication_payload": publication_payload,
    }
    if document_plan_artifact is not None:
        response["document_plan_artifact"] = document_plan_artifact
    return response


def _resolve_persisted_document_plan_artifact(
    *,
    execution_context: dict[str, Any],
) -> dict[str, Any] | None:
    artifact_raw = execution_context.get(POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY)
    if artifact_raw is None:
        return None
    return validate_document_plan_artifact_v1(artifact=artifact_raw)


def _resolve_compiled_document_policy_for_execution_context(
    *,
    execution_context: dict[str, Any],
) -> dict[str, Any] | None:
    raw_policy = execution_context.get(POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY)
    if not isinstance(raw_policy, Mapping):
        return None
    return dict(raw_policy)


def _resolve_compiled_document_policy_slots_for_execution_context(
    *,
    execution_context: dict[str, Any],
) -> dict[str, dict[str, Any]] | None:
    return validate_compiled_document_policy_slots_snapshot(
        execution_context.get(POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_SLOTS_CONTEXT_KEY)
    )


def _resolve_document_policy_source_for_execution_context(
    *,
    execution_context: dict[str, Any],
) -> str | None:
    source = str(execution_context.get(POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY) or "").strip()
    return source or None


def _has_workflow_binding_context(execution_context: dict[str, Any]) -> bool:
    binding = execution_context.get("pool_workflow_binding")
    return isinstance(binding, Mapping) and bool(binding)


def _execute_distribution_calculation(
    *,
    run: PoolRun,
    execution: Any,
    expected_direction: str,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    if run.direction != expected_direction:
        raise ValueError(
            "POOL_DISTRIBUTION_DIRECTION_MISMATCH: "
            f"run direction '{run.direction}' does not match operation direction '{expected_direction}'"
        )

    generated_result = _execute_kvo17_generated_distribution_if_available(
        run=run,
        execution=execution,
        execution_context=execution_context,
    )
    if generated_result is not None:
        return generated_result

    runtime_state = compute_distribution_runtime_state(run=run, run_input=_run_input(run))
    summary_payload = runtime_state.get("summary")
    distribution_summary = dict(summary_payload) if isinstance(summary_payload, Mapping) else {}
    artifact_payload = runtime_state.get("artifact")
    distribution_artifact = validate_distribution_artifact_v1(artifact=artifact_payload)
    publication_payload_raw = runtime_state.get("publication_payload")
    publication_payload = (
        dict(publication_payload_raw)
        if isinstance(publication_payload_raw, Mapping)
        else build_publication_payload_from_artifact(
            artifact=distribution_artifact,
            run_input=_run_input(run),
        )
    )
    locked_retry_payload = _resolve_locked_retry_publication_payload(
        execution_context=execution_context
    )
    if locked_retry_payload is not None:
        publication_payload = locked_retry_payload
    if not publication_payload:
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: publication_payload is missing for distribution artifact"
        )

    _update_execution_context(
        execution=execution,
        updates={
            "pool_runtime_distribution": distribution_summary,
            POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY: distribution_artifact,
            "pool_runtime_publication_payload": publication_payload,
        },
    )
    return {
        "step": "distribution_calculation",
        "pool_run_id": str(run.id),
        "distribution": distribution_summary,
        "distribution_artifact": distribution_artifact,
        "publication_payload": publication_payload,
    }


def _execute_kvo17_generated_distribution_if_available(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any] | None:
    run_input = _run_input(run)
    if not isinstance(run_input.get(KVO17_GENERATED_PURCHASE_METADATA_KEY), Mapping):
        return None
    document_plan_artifact = _resolve_persisted_document_plan_artifact(
        execution_context=execution_context
    )
    if document_plan_artifact is None:
        return None

    distribution_artifact = _build_kvo17_generated_distribution_artifact(
        run=run,
        document_plan_artifact=document_plan_artifact,
    )
    distribution_summary = {
        "status": "generated",
        "direction": run.direction,
        "topology_version_ref": distribution_artifact["topology_version_ref"],
        "source_total": distribution_artifact["balance"]["source_total"],
        "distributed_total": distribution_artifact["balance"]["distributed_total"],
        "coverage_full": True,
        "edge_strategy": "single_edge_multi_document_chain",
    }
    publication_payload = build_publication_payload_from_document_plan_artifact(
        artifact=document_plan_artifact,
        run_input=run_input,
    )
    locked_retry_payload = _resolve_locked_retry_publication_payload(
        execution_context=execution_context
    )
    if locked_retry_payload is not None:
        publication_payload = locked_retry_payload

    _update_execution_context(
        execution=execution,
        updates={
            "pool_runtime_distribution": distribution_summary,
            POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY: distribution_artifact,
            "pool_runtime_publication_payload": publication_payload,
        },
    )
    return {
        "step": "distribution_calculation",
        "pool_run_id": str(run.id),
        "distribution": distribution_summary,
        "distribution_artifact": distribution_artifact,
        "publication_payload": publication_payload,
    }


def _build_kvo17_generated_distribution_artifact(
    *,
    run: PoolRun,
    document_plan_artifact: Mapping[str, Any],
) -> dict[str, Any]:
    targets = document_plan_artifact.get("targets")
    target = targets[0] if isinstance(targets, list) and targets else {}
    chains = target.get("chains") if isinstance(target, Mapping) else []
    database_id = str(target.get("database_id") or "").strip() if isinstance(target, Mapping) else ""
    topology_ref = str(document_plan_artifact.get("topology_version_ref") or "").strip()

    total_amount = Decimal("0.00")
    edge_allocations: list[dict[str, Any]] = []
    target_node_ids: set[str] = set()
    if isinstance(chains, list):
        for chain in chains:
            if not isinstance(chain, Mapping):
                continue
            allocation = chain.get("allocation")
            amount = _parse_decimal(allocation.get("amount") if isinstance(allocation, Mapping) else None)
            amount = amount if amount is not None else Decimal("0.00")
            total_amount += amount
            edge_ref = chain.get("edge_ref") if isinstance(chain.get("edge_ref"), Mapping) else {}
            parent_node_id = str(edge_ref.get("parent_node_id") or "").strip()
            child_node_id = str(edge_ref.get("child_node_id") or "").strip()
            if child_node_id:
                target_node_ids.add(child_node_id)
            edge_allocations.append(
                {
                    "parent_node_id": parent_node_id,
                    "child_node_id": child_node_id,
                    "amount": _decimal_to_string(amount),
                    "weight": "1.00",
                    "min_amount": "0.00",
                    "max_amount": "0.00",
                }
            )

    total_text = _decimal_to_string(total_amount)
    node_totals = [
        {
            "node_id": node_id,
            "organization_id": node_id,
            "database_id": database_id,
            "is_root": False,
            "amount": total_text,
        }
        for node_id in sorted(target_node_ids)
    ]
    artifact = {
        "version": DISTRIBUTION_ARTIFACT_VERSION,
        "direction": run.direction,
        "topology_version_ref": topology_ref,
        "node_totals": node_totals,
        "edge_allocations": edge_allocations,
        "coverage": {
            "publish_target_node_ids": sorted(target_node_ids),
            "covered_target_node_ids": sorted(target_node_ids),
            "missing_target_node_ids": [],
            "is_full": True,
        },
        "balance": {
            "source_total": total_text,
            "distributed_total": total_text,
            "delta": "0.00",
            "tolerance": "0.00",
            "is_balanced": True,
        },
        "diagnostics": [
            {
                "code": "kvo17_generated_single_edge_distribution",
                "status": "info",
                "detail": "Generated KVO17 publication uses manifest rows instead of topology branch slots.",
            }
        ],
        "input_provenance": {
            "source_type": KVO17_GENERATED_PURCHASE_METADATA_KEY,
            "document_plan_artifact_version": str(document_plan_artifact.get("version") or "").strip(),
        },
    }
    return validate_distribution_artifact_v1(artifact=artifact)


def _execute_approval_gate(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    if run.mode == PoolRunMode.UNSAFE:
        approval_state = APPROVAL_STATE_NOT_REQUIRED
        publication_step_state = PUBLICATION_STEP_STATE_QUEUED
        awaiting_approval = False
    elif _resolve_approved_at(run=run, execution_context=execution_context) is not None:
        approval_state = APPROVAL_STATE_APPROVED
        publication_step_state = PUBLICATION_STEP_STATE_QUEUED
        awaiting_approval = False
    else:
        approval_state = APPROVAL_STATE_AWAITING_APPROVAL
        publication_step_state = PUBLICATION_STEP_STATE_NOT_ENQUEUED
        awaiting_approval = True

    updates = {
        "approval_state": approval_state,
        "publication_step_state": publication_step_state,
    }
    approved_at = _resolve_approved_at(run=run, execution_context=execution_context)
    if approved_at is not None:
        updates["approved_at"] = approved_at
    _update_execution_context(execution=execution, updates=updates)

    return {
        "step": "approval_gate",
        "pool_run_id": str(run.id),
        "approval_state": approval_state,
        "publication_step_state": publication_step_state,
        "awaiting_approval": awaiting_approval,
    }


def _execute_publication(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
    rendered_data: dict[str, Any],
) -> dict[str, Any]:
    _ = (run, execution, execution_context, rendered_data)
    raise ValueError(
        f"{POOL_RUNTIME_PUBLICATION_PATH_DISABLED}: "
        "publication OData side effects are disabled in orchestrator pool-domain runtime"
    )


def _execute_master_data_gate(
    *,
    run: PoolRun,
    execution: Any,
    execution_context: dict[str, Any],
) -> dict[str, Any]:
    requires_resolution = publication_payload_requires_master_data_resolution(
        execution_context=execution_context,
    )
    try:
        gate_enabled = is_pool_master_data_gate_enabled(
            tenant_id=str(run.tenant_id),
            fail_closed_on_invalid=True,
        )
    except MasterDataGateConfigInvalidError as exc:
        diagnostic = exc.to_diagnostic()
        summary = {
            "status": "failed",
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "error_code": exc.code,
            "detail": exc.detail,
            "diagnostic": diagnostic,
        }
        _update_execution_context(
            execution=execution,
            updates={"pool_runtime_master_data_gate": summary},
        )
        diagnostic_json = json.dumps(
            diagnostic,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        raise ValueError(f"{exc.code}: diagnostic={diagnostic_json}") from exc

    if not gate_enabled and not requires_resolution:
        summary = {
            "status": "skipped",
            "reason": "feature_disabled",
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "targets_count": 0,
            "bindings_count": 0,
        }
        _update_execution_context(
            execution=execution,
            updates={
                "pool_runtime_master_data_gate": summary,
                POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: [],
            },
        )
        return {
            "step": "master_data_gate",
            "pool_run_id": str(run.id),
            "summary": summary,
        }

    readiness_blockers = _collect_master_data_readiness_blockers(
        run=run,
        execution_context=execution_context,
    )
    if readiness_blockers:
        primary_blocker = readiness_blockers[0]
        error_code = str(primary_blocker.get("code") or "").strip() or MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING
        detail = str(primary_blocker.get("detail") or "").strip() or "Master-data readiness blocked publication."
        diagnostic = _build_master_data_gate_blocked_diagnostic(
            readiness_blockers=readiness_blockers,
            error_code=error_code,
        )
        summary = {
            "status": "failed",
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "error_code": error_code,
            "detail": detail,
            "diagnostic": diagnostic,
        }
        _update_execution_context(
            execution=execution,
            updates={
                "pool_runtime_master_data_gate": summary,
                POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: readiness_blockers,
            },
        )
        diagnostic_json = json.dumps(
            diagnostic,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        raise ValueError(f"{error_code}: diagnostic={diagnostic_json}")

    try:
        gate_result = execute_master_data_resolve_upsert_gate(
            run=run,
            execution_context=execution_context,
        )
    except MasterDataResolveError as exc:
        diagnostic = exc.to_diagnostic()
        summary = {
            "status": "failed",
            "mode": MASTER_DATA_GATE_MODE_RESOLVE_UPSERT,
            "error_code": exc.code,
            "detail": exc.detail,
            "diagnostic": diagnostic,
        }
        readiness_blockers = [_build_readiness_blocker_from_master_data_error(exc)]
        _update_execution_context(
            execution=execution,
            updates={
                "pool_runtime_master_data_gate": summary,
                POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: readiness_blockers,
            },
        )
        diagnostic_json = json.dumps(
            diagnostic,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        raise ValueError(f"{exc.code}: diagnostic={diagnostic_json}") from exc

    publication_payload = gate_result.get("publication_payload")
    binding_artifact = gate_result.get("binding_artifact")
    summary = (
        dict(gate_result.get("summary"))
        if isinstance(gate_result.get("summary"), Mapping)
        else {}
    )
    summary.setdefault("status", "completed")
    summary.setdefault("mode", MASTER_DATA_GATE_MODE_RESOLVE_UPSERT)

    updates = {
        "pool_runtime_publication_payload": publication_payload,
        POOL_RUNTIME_MASTER_DATA_BINDING_ARTIFACT_CONTEXT_KEY: binding_artifact,
        "pool_runtime_master_data_gate": summary,
        POOL_RUNTIME_READINESS_BLOCKERS_CONTEXT_KEY: [],
    }
    _update_execution_context(execution=execution, updates=updates)
    return {
        "step": "master_data_gate",
        "pool_run_id": str(run.id),
        "summary": summary,
        "publication_payload": publication_payload,
        "master_data_binding_artifact": binding_artifact,
    }


def _collect_master_data_readiness_blockers(
    *,
    run: PoolRun,
    execution_context: dict[str, Any],
) -> list[dict[str, Any]]:
    blockers = [
        *_collect_missing_master_party_binding_blockers(run=run),
        *collect_master_data_resolution_readiness_blockers(
            run=run,
            execution_context=execution_context,
        ),
    ]
    return _sort_readiness_blockers(blockers)


def _collect_missing_master_party_binding_blockers(*, run: PoolRun) -> list[dict[str, Any]]:
    try:
        topology = load_runtime_topology_for_period(run=run)
    except ValueError as exc:
        message = str(exc)
        if message.startswith("POOL_DISTRIBUTION_INPUT_INVALID") or message.startswith("POOL_DISTRIBUTION_GRAPH_INVALID"):
            return []
        raise
    raw_node_models = topology.get("node_models")
    if not isinstance(raw_node_models, Mapping):
        return []
    node_models = dict(raw_node_models)

    raw_target_node_ids = topology.get("publish_target_node_ids")
    if not isinstance(raw_target_node_ids, list):
        return []

    organization_ids: set[str] = set()
    for raw_node_id in raw_target_node_ids:
        node_id = str(raw_node_id or "").strip()
        if not node_id:
            continue
        node = node_models.get(node_id)
        if node is None:
            continue
        organization_id = str(getattr(node, "organization_id", "") or "").strip()
        if organization_id:
            organization_ids.add(organization_id)

    if not organization_ids:
        return []

    organizations = Organization.objects.filter(
        tenant_id=run.tenant_id,
        id__in=organization_ids,
    ).only("id", "name", "inn", "database_id", "master_party_id")

    bound_party_ids = {
        str(value)
        for value in Organization.objects.filter(tenant_id=run.tenant_id)
        .exclude(master_party_id__isnull=True)
        .values_list("master_party_id", flat=True)
    }

    missing: list[dict[str, Any]] = []
    for organization in organizations:
        if organization.master_party_id is not None:
            continue
        candidate_parties = _find_master_party_candidates_for_organization(organization=organization)
        remediation_reason = REMEDIATION_REASON_NO_MATCH
        if len(candidate_parties) > 1:
            remediation_reason = REMEDIATION_REASON_AMBIGUOUS_MATCH
        elif len(candidate_parties) == 1 and str(candidate_parties[0].id) in bound_party_ids:
            remediation_reason = REMEDIATION_REASON_CANDIDATE_ALREADY_BOUND
        elif len(candidate_parties) == 1:
            remediation_reason = "candidate_available"
        missing.append(
            {
                "code": MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING,
                "detail": "Missing Organization->Party binding for publication target organization.",
                "kind": "organization_party_binding_missing",
                "organization_id": str(organization.id),
                "database_id": str(organization.database_id) if organization.database_id else "",
                "diagnostic": {
                    "organization_name": str(organization.name or ""),
                    "organization_inn": str(organization.inn or ""),
                    "remediation_reason": remediation_reason,
                    "candidate_party_ids": [str(item.id) for item in candidate_parties],
                    "candidate_party_canonical_ids": [
                        str(item.canonical_id) for item in candidate_parties
                    ],
                },
            }
        )

    missing.sort(
        key=lambda item: (
            str(item.get("database_id") or ""),
            item.get("organization_id", ""),
        )
    )
    return missing


def _find_master_party_candidates_for_organization(*, organization: Organization) -> list[PoolMasterParty]:
    inn = str(organization.inn or "").strip()
    if not inn:
        return []

    candidates = PoolMasterParty.objects.filter(
        tenant_id=organization.tenant_id,
        inn=inn,
        is_our_organization=True,
    )
    kpp = str(organization.kpp or "").strip()
    if kpp:
        candidates = candidates.filter(kpp=kpp)
    return list(candidates.order_by("canonical_id", "id"))


def _build_master_data_gate_blocked_diagnostic(
    *,
    readiness_blockers: list[dict[str, Any]],
    error_code: str,
) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {
        "error_code": error_code,
        "blockers_count": len(readiness_blockers),
    }
    primary_diagnostic = readiness_blockers[0].get("diagnostic")
    if isinstance(primary_diagnostic, Mapping):
        diagnostic.update(dict(primary_diagnostic))
    primary_entity_type = str(readiness_blockers[0].get("entity_name") or "").strip()
    primary_database_id = str(readiness_blockers[0].get("database_id") or "").strip()
    if primary_entity_type and "entity_type" not in diagnostic:
        diagnostic["entity_type"] = primary_entity_type
    if primary_database_id and "target_database_id" not in diagnostic:
        diagnostic["target_database_id"] = primary_database_id

    missing_organization_bindings: list[dict[str, Any]] = []
    for blocker in readiness_blockers:
        if str(blocker.get("code") or "").strip() != MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING:
            continue
        row = {
            "organization_id": blocker.get("organization_id"),
            "database_id": blocker.get("database_id"),
        }
        blocker_diagnostic = blocker.get("diagnostic")
        if isinstance(blocker_diagnostic, Mapping):
            if "organization_name" in blocker_diagnostic:
                row["name"] = blocker_diagnostic.get("organization_name")
            if "organization_inn" in blocker_diagnostic:
                row["inn"] = blocker_diagnostic.get("organization_inn")
            if "remediation_reason" in blocker_diagnostic:
                row["remediation_reason"] = blocker_diagnostic.get("remediation_reason")
            if "candidate_party_ids" in blocker_diagnostic:
                row["candidate_party_ids"] = blocker_diagnostic.get("candidate_party_ids")
            if "candidate_party_canonical_ids" in blocker_diagnostic:
                row["candidate_party_canonical_ids"] = blocker_diagnostic.get("candidate_party_canonical_ids")
        missing_organization_bindings.append(row)

    if missing_organization_bindings:
        diagnostic["missing_count"] = len(missing_organization_bindings)
        diagnostic["missing_organization_bindings"] = missing_organization_bindings

    return diagnostic


def _build_readiness_blocker_from_master_data_error(exc: MasterDataResolveError) -> dict[str, Any]:
    blocker: dict[str, Any] = {
        "code": exc.code,
        "detail": exc.detail,
        "diagnostic": exc.to_diagnostic(),
    }
    if exc.code == MASTER_DATA_ENTITY_NOT_FOUND:
        blocker["kind"] = "canonical_entity_missing"
    elif exc.code == MASTER_DATA_BINDING_AMBIGUOUS:
        blocker["kind"] = "binding_ambiguous"
    elif exc.code == MASTER_DATA_BINDING_CONFLICT:
        blocker["kind"] = "binding_conflict"
    if exc.entity_type:
        blocker["entity_name"] = exc.entity_type
    if exc.canonical_id:
        blocker["field_or_table_path"] = exc.canonical_id
    if exc.target_database_id:
        blocker["database_id"] = exc.target_database_id
    return blocker


def _sort_readiness_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    code_priority = {
        MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING: 0,
        MASTER_DATA_PARTY_ROLE_MISSING: 5,
        POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID: 8,
        MASTER_DATA_BINDING_CONFLICT: 10,
        MASTER_DATA_BINDING_AMBIGUOUS: 20,
        MASTER_DATA_ENTITY_NOT_FOUND: 30,
    }
    return sorted(
        blockers,
        key=lambda blocker: (
            code_priority.get(str(blocker.get("code") or "").strip(), 100),
            str(blocker.get("kind") or ""),
            str(blocker.get("database_id") or ""),
            str(blocker.get("organization_id") or ""),
            str(blocker.get("entity_name") or ""),
            str(blocker.get("field_or_table_path") or ""),
            str(blocker.get("detail") or ""),
        ),
    )


def _resolve_locked_retry_publication_payload(
    *,
    execution_context: dict[str, Any],
) -> dict[str, Any] | None:
    retry_settings_raw = execution_context.get("pool_runtime_retry_settings")
    retry_settings = dict(retry_settings_raw) if isinstance(retry_settings_raw, Mapping) else {}
    if not bool(retry_settings.get("use_retry_subset_payload")):
        return None

    payload_raw = execution_context.get("pool_runtime_publication_payload")
    if not isinstance(payload_raw, Mapping):
        raise ValueError(
            f"{POOL_RUNTIME_RETRY_PAYLOAD_INVALID}: "
            "pool_runtime_publication_payload is required when use_retry_subset_payload=true"
        )
    publication_payload = dict(payload_raw)
    pool_runtime_payload = publication_payload.get("pool_runtime")
    if not isinstance(pool_runtime_payload, Mapping):
        raise ValueError(
            f"{POOL_RUNTIME_RETRY_PAYLOAD_INVALID}: "
            "pool_runtime_publication_payload.pool_runtime must be an object"
        )
    documents_by_database = pool_runtime_payload.get("documents_by_database")
    if not isinstance(documents_by_database, Mapping):
        raise ValueError(
            f"{POOL_RUNTIME_RETRY_PAYLOAD_INVALID}: "
            "pool_runtime_publication_payload.pool_runtime.documents_by_database must be an object"
        )
    return publication_payload


def _build_readiness_blocker_from_error(exc: ValueError) -> dict[str, Any] | None:
    if isinstance(exc, TopologyAwareMasterDataAliasError):
        return exc.to_blocker()

    message = str(exc).strip()
    if ":" not in message:
        return None
    raw_code, raw_detail = message.split(":", 1)
    code = raw_code.strip()
    detail = raw_detail.strip()
    if not code:
        return None

    blocker: dict[str, Any] = {
        "code": code,
        "detail": detail,
    }
    entity_marker = "for entity '"
    if entity_marker in detail:
        entity_name = detail.split(entity_marker, 1)[1].split("'", 1)[0].strip()
        if entity_name:
            blocker["entity_name"] = entity_name
    table_marker = ".table_parts_mapping."
    if table_marker in detail:
        table_part_name = detail.split(table_marker, 1)[1].split("[", 1)[0].split(" ", 1)[0].strip()
        if table_part_name:
            blocker["field_or_table_path"] = table_part_name
    field_marker = ".field_mapping."
    if "field_or_table_path" not in blocker and field_marker in detail:
        field_name = detail.split(field_marker, 1)[1].split(" ", 1)[0].strip()
        if field_name:
            blocker["field_or_table_path"] = field_name
    return blocker


def _run_input(run: PoolRun) -> dict[str, Any]:
    return build_runtime_run_input(run=run)


def _source_rows(*, run_input: dict[str, Any]) -> list[dict[str, Any]]:
    source_payload = run_input.get("source_payload")
    if isinstance(source_payload, list):
        return [dict(item) for item in source_payload if isinstance(item, Mapping)]
    if isinstance(source_payload, Mapping):
        rows = source_payload.get("rows")
        if isinstance(rows, list):
            return [dict(item) for item in rows if isinstance(item, Mapping)]
    return []


def _sum_source_amounts(source_rows: list[dict[str, Any]]) -> Decimal | None:
    total = Decimal("0")
    has_amounts = False
    for row in source_rows:
        amount = _parse_decimal(row.get("amount"))
        if amount is None:
            continue
        total += amount
        has_amounts = True
    if not has_amounts:
        return None
    return total


def _resolve_approval_state(*, run: PoolRun, execution_context: dict[str, Any]) -> str:
    if run.mode == PoolRunMode.UNSAFE:
        return APPROVAL_STATE_NOT_REQUIRED
    if _resolve_approved_at(run=run, execution_context=execution_context) is not None:
        return APPROVAL_STATE_APPROVED
    raw_state = str(execution_context.get("approval_state") or "").strip().lower()
    if raw_state in {APPROVAL_STATE_PREPARING, APPROVAL_STATE_AWAITING_APPROVAL, APPROVAL_STATE_APPROVED}:
        return raw_state
    return APPROVAL_STATE_PREPARING


def _resolve_publication_step_state(
    *,
    run: PoolRun,
    approval_state: str,
    execution_context: dict[str, Any],
) -> str:
    raw_state = str(execution_context.get("publication_step_state") or "").strip().lower()
    if raw_state in {
        PUBLICATION_STEP_STATE_NOT_ENQUEUED,
        PUBLICATION_STEP_STATE_QUEUED,
        PUBLICATION_STEP_STATE_STARTED,
        PUBLICATION_STEP_STATE_COMPLETED,
    }:
        return raw_state
    if run.mode == PoolRunMode.SAFE and approval_state != APPROVAL_STATE_APPROVED:
        return PUBLICATION_STEP_STATE_NOT_ENQUEUED
    return PUBLICATION_STEP_STATE_QUEUED


def _resolve_approved_at(*, run: PoolRun, execution_context: dict[str, Any]) -> str | None:
    context_value = execution_context.get("approved_at")
    if isinstance(context_value, str) and context_value.strip():
        return context_value.strip()
    if context_value is not None and not isinstance(context_value, str):
        return str(context_value)
    if run.publication_confirmed_at is not None:
        return run.publication_confirmed_at.isoformat()
    return None


def _update_execution_context(*, execution: Any, updates: dict[str, Any]) -> None:
    if not updates:
        return
    current = execution.input_context if isinstance(getattr(execution, "input_context", None), dict) else {}
    next_context = dict(current)
    changed = False
    for key, value in updates.items():
        if next_context.get(key) != value:
            next_context[key] = value
            changed = True
    if not changed:
        return
    execution.input_context = next_context
    execution.save(update_fields=["input_context"])


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")
