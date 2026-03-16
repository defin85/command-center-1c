from __future__ import annotations

from datetime import date
from typing import Any, Mapping
from uuid import uuid4

from apps.templates.workflow.decision_tables import (
    evaluate_decision_table,
    resolve_pinned_decision_table,
)

from .document_plan_artifact_contract import (
    POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND,
    POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING,
    compile_document_plan_artifact_v1,
)
from .document_policy_contract import (
    DOCUMENT_POLICY_METADATA_KEY,
    validate_document_policy_v1,
)
from .distribution_artifact_contract import validate_distribution_artifact_v1
from .models import OrganizationPool, PoolRun, PoolSchemaTemplate
from .run_input_sanitizer import sanitize_run_input_for_runtime_contract
from .runtime_distribution import compute_distribution_runtime_state, load_runtime_topology_for_period
from .runtime_projection_contract import build_pool_runtime_projection_v1
from .runtime_template_registry import sync_pool_runtime_template_registry
from .workflow_authoring_contract import (
    POOL_DOCUMENT_POLICY_SLOT_DUPLICATE,
    PoolWorkflowBindingContract,
    PoolWorkflowBindingDecisionRef,
)
from .workflow_binding_resolution import resolve_pool_workflow_binding_for_run
from .workflow_bindings_store import list_pool_workflow_bindings
from .workflow_compiler import PoolWorkflowRunContext, compile_pool_execution_plan


def compile_binding_document_policy(
    *,
    binding: PoolWorkflowBindingContract,
    pool: OrganizationPool,
    direction: str,
    mode: str,
    period_start: date,
    period_end: date | None,
    run_input: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    (
        _decision_outputs,
        _compiled_document_policy_slots,
        document_policy,
        document_policy_source,
    ) = evaluate_binding_decisions(
        binding=binding,
        pool=pool,
        direction=direction,
        mode=mode,
        period_start=period_start,
        period_end=period_end,
        run_input=run_input,
    )
    return document_policy, document_policy_source


def evaluate_binding_decisions(
    *,
    binding: PoolWorkflowBindingContract,
    pool: OrganizationPool,
    direction: str,
    mode: str,
    period_start: date,
    period_end: date | None,
    run_input: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any], str]:
    decision_inputs = _build_decision_inputs(
        binding=binding,
        pool=pool,
        direction=direction,
        mode=mode,
        period_start=period_start,
        period_end=period_end,
        run_input=run_input,
    )
    decision_outputs: dict[str, Any] = {}
    compiled_document_policy_slots: dict[str, dict[str, Any]] = {}
    compiled_document_policy: dict[str, Any] | None = None
    document_policy_source: str | None = None
    for decision_ref in binding.decisions:
        decision = resolve_pinned_decision_table(
            decision_table_id=decision_ref.decision_table_id,
            decision_revision=decision_ref.decision_revision,
        )
        outputs = evaluate_decision_table(
            decision_table=decision,
            inputs=decision_inputs,
        )
        document_policy = outputs.get("document_policy")
        if decision_ref.decision_key in decision_outputs:
            if not (
                document_policy is not None
                and decision_ref.decision_key == DOCUMENT_POLICY_METADATA_KEY
            ):
                raise ValueError(
                    "Duplicate decision_key in workflow binding decisions: "
                    f"{decision_ref.decision_key}"
                )
        else:
            decision_outputs[decision_ref.decision_key] = (
                outputs.get(decision_ref.decision_key)
                if decision_ref.decision_key in outputs
                else dict(outputs)
            )
        if document_policy is None:
            continue
        validated_document_policy = validate_document_policy_v1(policy=document_policy)
        slot_key = _resolve_binding_slot_key(decision_ref=decision_ref)
        if slot_key in compiled_document_policy_slots:
            raise ValueError(
                f"{POOL_DOCUMENT_POLICY_SLOT_DUPLICATE}: Duplicate slot_key in workflow binding decisions: "
                f"{slot_key}"
            )
        slot_policy_source = (
            "workflow_binding.decision_table:"
            f"{decision.decision_table_id}:v{decision.version_number}"
        )
        compiled_document_policy_slots[slot_key] = {
            "decision_table_id": decision.decision_table_id,
            "decision_revision": decision.version_number,
            "document_policy_source": slot_policy_source,
            "document_policy": validated_document_policy,
        }
        if compiled_document_policy is None:
            compiled_document_policy = validated_document_policy
            document_policy_source = slot_policy_source
    if compiled_document_policy is None or document_policy_source is None:
        raise ValueError("No linked decision table produced a document_policy output.")
    return (
        decision_outputs,
        compiled_document_policy_slots,
        compiled_document_policy,
        document_policy_source,
    )


def _resolve_binding_slot_key(*, decision_ref: PoolWorkflowBindingDecisionRef) -> str:
    resolved = decision_ref.resolved_slot_key()
    if resolved:
        return resolved
    return decision_ref.decision_key


def build_pool_workflow_binding_runtime_bundle(
    *,
    tenant,
    pool: OrganizationPool,
    pool_workflow_binding_id: str | None = None,
    direction: str,
    mode: str,
    period_start: date,
    period_end: date | None,
    run_input: Mapping[str, Any] | None,
    schema_template: PoolSchemaTemplate,
    run: PoolRun | None = None,
    workflow_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_binding = _resolve_runtime_workflow_binding(
        pool=pool,
        pool_workflow_binding_id=pool_workflow_binding_id,
        workflow_binding=workflow_binding,
        direction=direction,
        mode=mode,
        period_start=period_start,
    )

    sanitized_run_input = sanitize_run_input_for_runtime_contract(run_input=dict(run_input or {}))
    sync_pool_runtime_template_registry()
    preview_run = run or PoolRun(
        id=uuid4(),
        tenant=tenant,
        pool=pool,
        direction=direction,
        mode=mode,
        period_start=period_start,
        period_end=period_end,
        run_input=sanitized_run_input,
    )
    distribution_state = compute_distribution_runtime_state(
        run=preview_run,
        run_input=sanitized_run_input,
    )
    distribution_artifact = validate_distribution_artifact_v1(
        artifact=distribution_state.get("artifact"),
    )
    topology = load_runtime_topology_for_period(run=preview_run)
    (
        decision_outputs,
        compiled_document_policy_slots,
        compiled_document_policy,
        document_policy_source,
    ) = evaluate_binding_decisions(
        binding=resolved_binding,
        pool=pool,
        direction=direction,
        mode=mode,
        period_start=period_start,
        period_end=period_end,
        run_input=sanitized_run_input,
    )
    document_plan_artifact = compile_document_plan_artifact_v1(
        run=preview_run,
        distribution_artifact=distribution_artifact,
        topology=topology,
        compiled_document_policy_slots=compiled_document_policy_slots,
        compiled_document_policy=compiled_document_policy,
        document_policy_source=document_policy_source,
    )
    slot_coverage_summary = _build_slot_coverage_summary(
        topology=topology,
        compiled_document_policy_slots=compiled_document_policy_slots,
    )
    plan = compile_pool_execution_plan(
        schema_template=schema_template,
        run_context=PoolWorkflowRunContext(
            pool_id=str(pool.id),
            period_start=period_start,
            period_end=period_end,
            direction=direction,
            mode=mode,
            run_input=sanitized_run_input,
            document_plan_artifact=document_plan_artifact,
            workflow_binding=resolved_binding.model_dump(mode="json"),
        ),
    )
    runtime_projection = build_pool_runtime_projection_v1(
        run=preview_run,
        plan=plan,
        document_plan_artifact=document_plan_artifact,
        compiled_document_policy_slots=compiled_document_policy_slots,
        compiled_document_policy=compiled_document_policy,
        slot_coverage_summary=slot_coverage_summary,
    )
    return {
        "workflow_binding": resolved_binding.model_dump(mode="json"),
        "decision_outputs": decision_outputs,
        "compiled_document_policy_slots": compiled_document_policy_slots,
        "compiled_document_policy": compiled_document_policy,
        "document_policy_source": document_policy_source,
        "document_plan_artifact": document_plan_artifact,
        "slot_coverage_summary": slot_coverage_summary,
        "plan": plan,
        "runtime_projection": runtime_projection,
        "run_input": sanitized_run_input,
    }


def build_pool_workflow_binding_preview(
    *,
    tenant,
    pool: OrganizationPool,
    pool_workflow_binding_id: str,
    direction: str,
    mode: str,
    period_start: date,
    period_end: date | None,
    run_input: Mapping[str, Any] | None,
    schema_template: PoolSchemaTemplate,
) -> dict[str, Any]:
    bundle = build_pool_workflow_binding_runtime_bundle(
        tenant=tenant,
        pool=pool,
        pool_workflow_binding_id=pool_workflow_binding_id,
        direction=direction,
        mode=mode,
        period_start=period_start,
        period_end=period_end,
        run_input=run_input,
        schema_template=schema_template,
        run=None,
    )
    return {
        "workflow_binding": bundle["workflow_binding"],
        "compiled_document_policy_slots": bundle["compiled_document_policy_slots"],
        "compiled_document_policy": bundle["compiled_document_policy"],
        "slot_coverage_summary": bundle["slot_coverage_summary"],
        "runtime_projection": bundle["runtime_projection"],
    }


def _resolve_runtime_workflow_binding(
    *,
    pool: OrganizationPool,
    pool_workflow_binding_id: str | None,
    workflow_binding: Mapping[str, Any] | None,
    direction: str,
    mode: str,
    period_start: date,
) -> PoolWorkflowBindingContract:
    requested_binding_id = str(pool_workflow_binding_id or "").strip() or None
    if workflow_binding is not None:
        try:
            explicit_binding = PoolWorkflowBindingContract(**dict(workflow_binding))
        except Exception as exc:
            raise ValueError(
                f"POOL_WORKFLOW_BINDING_INVALID: explicit workflow binding payload is invalid ({exc})"
            ) from exc
        if explicit_binding.pool_id != str(pool.id):
            raise ValueError(
                "POOL_WORKFLOW_BINDING_INVALID: explicit workflow binding pool_id does not match pool."
            )
        if requested_binding_id and explicit_binding.binding_id != requested_binding_id:
            raise ValueError(
                "POOL_WORKFLOW_BINDING_INVALID: explicit workflow binding does not match "
                "pool_workflow_binding_id."
            )
        return explicit_binding

    resolved_binding = resolve_pool_workflow_binding_for_run(
        raw_bindings=list_pool_workflow_bindings(pool=pool),
        requested_binding_id=requested_binding_id,
        direction=direction,
        mode=mode,
        period_start=period_start,
    )
    if resolved_binding is None:
        raise ValueError("POOL_WORKFLOW_BINDING_REQUIRED: pool_workflow_binding_id is required.")
    return resolved_binding


def _build_decision_inputs(
    *,
    binding: PoolWorkflowBindingContract,
    pool: OrganizationPool,
    direction: str,
    mode: str,
    period_start: date,
    period_end: date | None,
    run_input: Mapping[str, Any] | None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    if isinstance(binding.parameters, dict):
        inputs.update(binding.parameters)
    if isinstance(run_input, Mapping):
        for key, value in run_input.items():
            inputs.setdefault(str(key), value)
    inputs.update(
        {
            "pool_id": str(pool.id),
            "direction": direction,
            "mode": mode,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat() if period_end else None,
            "workflow_definition_key": binding.workflow.workflow_definition_key,
            "workflow_revision": binding.workflow.workflow_revision,
        }
    )
    return inputs


def _build_slot_coverage_summary(
    *,
    topology: Mapping[str, Any],
    compiled_document_policy_slots: Mapping[str, Any],
) -> dict[str, Any]:
    counts = {
        "resolved": 0,
        "missing_selector": 0,
        "missing_slot": 0,
        "ambiguous_slot": 0,
        "ambiguous_context": 0,
        "unavailable_context": 0,
    }
    edge_models_raw = topology.get("edge_models")
    node_models_raw = topology.get("node_models")
    if not isinstance(edge_models_raw, Mapping) or not isinstance(node_models_raw, Mapping):
        return {
            "total_edges": 0,
            "counts": counts,
            "items": [],
        }

    items: list[dict[str, Any]] = []
    sorted_edges = sorted(
        (
            (str(parent_node_id), str(child_node_id), edge_model)
            for (parent_node_id, child_node_id), edge_model in edge_models_raw.items()
        ),
        key=lambda item: (item[0], item[1]),
    )
    for parent_node_id, child_node_id, edge_model in sorted_edges:
        edge_metadata = edge_model.metadata if isinstance(getattr(edge_model, "metadata", None), Mapping) else {}
        slot_key = str(edge_metadata.get("document_policy_key") or "").strip()
        if not slot_key:
            coverage = {
                "code": POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING,
                "status": "missing_selector",
                "label": "Slot required",
                "detail": "Set edge.metadata.document_policy_key to resolve publication slot coverage.",
            }
        else:
            slot_projection = compiled_document_policy_slots.get(slot_key)
            if not isinstance(slot_projection, Mapping):
                coverage = {
                    "code": POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND,
                    "status": "missing_slot",
                    "label": "Slot missing",
                    "detail": f"Selected binding does not pin slot '{slot_key}'.",
                }
            else:
                decision_table_id = str(slot_projection.get("decision_table_id") or "").strip()
                decision_revision = str(slot_projection.get("decision_revision") or "").strip()
                coverage = {
                    "code": None,
                    "status": "resolved",
                    "label": "Resolved",
                    "detail": (
                        f"{slot_key} -> {decision_table_id} r{decision_revision}"
                        if decision_table_id and decision_revision
                        else slot_key
                    ),
                }
        counts[str(coverage["status"])] += 1
        items.append(
            {
                "edge_id": str(getattr(edge_model, "id", "") or f"{parent_node_id}:{child_node_id}"),
                "edge_label": _build_topology_edge_label(
                    node_models=node_models_raw,
                    parent_node_id=parent_node_id,
                    child_node_id=child_node_id,
                ),
                "slot_key": slot_key,
                "coverage": coverage,
            }
        )
    return {
        "total_edges": len(items),
        "counts": counts,
        "items": items,
    }


def _build_topology_edge_label(
    *,
    node_models: Mapping[str, Any],
    parent_node_id: str,
    child_node_id: str,
) -> str:
    parent_node = node_models.get(parent_node_id)
    child_node = node_models.get(child_node_id)
    parent_label = str(
        getattr(parent_node.organization, "name", None)
        if getattr(parent_node, "organization", None) is not None
        else (getattr(parent_node, "name", None) or parent_node_id)
    ).strip() or parent_node_id
    child_label = str(
        getattr(child_node.organization, "name", None)
        if getattr(child_node, "organization", None) is not None
        else (getattr(child_node, "name", None) or child_node_id)
    ).strip() or child_node_id
    return f"{parent_label} -> {child_label}"

__all__ = [
    "build_pool_workflow_binding_preview",
    "build_pool_workflow_binding_runtime_bundle",
    "compile_binding_document_policy",
    "evaluate_binding_decisions",
]
