from __future__ import annotations

from typing import Any, Mapping

from .document_plan_artifact_contract import (
    POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND,
    POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING,
    validate_compiled_document_policy_slots_snapshot,
    validate_document_plan_artifact_v1,
)


POOL_RUNTIME_PROJECTION_VERSION = "pool_runtime_projection.v1"
POOL_RUNTIME_PROJECTION_CONTEXT_KEY = "pool_runtime_projection"
POOL_RUNTIME_PROJECTION_INVALID = "POOL_RUNTIME_PROJECTION_INVALID"
_SLOT_COVERAGE_STATUSES = {
    "resolved",
    "missing_selector",
    "missing_slot",
    "ambiguous_slot",
    "ambiguous_context",
    "unavailable_context",
}


def build_pool_runtime_projection_v1(
    *,
    run,
    plan,
    document_plan_artifact: Mapping[str, Any] | None,
    compiled_document_policy_slots: Mapping[str, Any] | None = None,
    compiled_document_policy: Mapping[str, Any] | None = None,
    slot_coverage_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validated_artifact = (
        validate_document_plan_artifact_v1(artifact=document_plan_artifact)
        if isinstance(document_plan_artifact, Mapping)
        else None
    )
    policy_refs = (
        list(validated_artifact.get("policy_refs") or [])
        if isinstance(validated_artifact, Mapping)
        else []
    )
    targets = (
        list(validated_artifact.get("targets") or [])
        if isinstance(validated_artifact, Mapping)
        else []
    )
    has_compiled_document_policy = isinstance(compiled_document_policy, Mapping) and bool(
        compiled_document_policy
    )
    normalized_compiled_document_policy_slots = (
        validate_compiled_document_policy_slots_snapshot(compiled_document_policy_slots)
        if isinstance(compiled_document_policy_slots, Mapping)
        else None
    )
    projection = {
        "version": POOL_RUNTIME_PROJECTION_VERSION,
        "run_id": str(run.id),
        "pool_id": str(run.pool_id),
        "direction": run.direction,
        "mode": run.mode,
        "workflow_definition": {
            "plan_key": str(plan.plan_key),
            "template_version": str(plan.template_version),
            "workflow_template_name": str(plan.workflow_template_name),
            "workflow_type": str(plan.workflow_type),
        },
        "workflow_binding": dict(plan.workflow_binding_snapshot or {"binding_mode": "unbound"}),
        "document_policy_projection": {
            "source_mode": (
                "document_plan_artifact"
                if validated_artifact
                else ("compiled_document_policy" if has_compiled_document_policy else "none")
            ),
            "policy_refs": policy_refs,
            "compiled_document_policy_slots": normalized_compiled_document_policy_slots or {},
            "slot_coverage_summary": _normalize_slot_coverage_summary(
                slot_coverage_summary=slot_coverage_summary,
                policy_refs=policy_refs,
                compiled_document_policy_slots=normalized_compiled_document_policy_slots,
            ),
            "policy_refs_count": len(policy_refs) if validated_artifact else (1 if has_compiled_document_policy else 0),
            "targets_count": len(targets),
        },
        "artifacts": {
            "document_plan_artifact_version": (
                str(validated_artifact.get("version") or "")
                if isinstance(validated_artifact, Mapping)
                else None
            ),
            "topology_version_ref": (
                str(validated_artifact.get("topology_version_ref") or "")
                if isinstance(validated_artifact, Mapping)
                else None
            ),
            "distribution_artifact_ref": (
                dict(validated_artifact.get("distribution_artifact_ref") or {})
                if isinstance(validated_artifact, Mapping)
                else None
            ),
        },
        "compile_summary": {
            "steps_count": len(tuple(getattr(plan, "steps", ()))),
            "atomic_publication_steps_count": sum(
                1
                for step in tuple(getattr(plan, "steps", ()))
                if str(getattr(step, "node_id", "") or "").startswith("publication_odata_")
            ),
            "compiled_targets_count": len(targets),
        },
    }
    return validate_pool_runtime_projection_v1(projection=projection)


def validate_pool_runtime_projection_v1(*, projection: Any) -> dict[str, Any]:
    if not isinstance(projection, Mapping):
        raise ValueError(
            f"{POOL_RUNTIME_PROJECTION_INVALID}: pool_runtime_projection must be an object"
        )
    payload = dict(projection)
    version = str(payload.get("version") or "").strip()
    if version != POOL_RUNTIME_PROJECTION_VERSION:
        raise ValueError(
            f"{POOL_RUNTIME_PROJECTION_INVALID}: unexpected projection version '{version or '<empty>'}'"
        )
    for field_name in ("run_id", "pool_id", "direction", "mode"):
        token = str(payload.get(field_name) or "").strip()
        if not token:
            raise ValueError(
                f"{POOL_RUNTIME_PROJECTION_INVALID}: field '{field_name}' is required"
            )
    for field_name in ("workflow_definition", "workflow_binding", "document_policy_projection", "artifacts", "compile_summary"):
        if not isinstance(payload.get(field_name), Mapping):
            raise ValueError(
                f"{POOL_RUNTIME_PROJECTION_INVALID}: field '{field_name}' must be an object"
            )
    workflow_binding = dict(payload["workflow_binding"])
    binding_mode = str(workflow_binding.get("binding_mode") or "").strip()
    if not binding_mode:
        raise ValueError(
            f"{POOL_RUNTIME_PROJECTION_INVALID}: workflow_binding.binding_mode is required"
        )
    document_policy_projection = dict(payload["document_policy_projection"])
    policy_refs_raw = document_policy_projection.get("policy_refs")
    policy_refs = (
        [dict(item) for item in policy_refs_raw if isinstance(item, Mapping)]
        if isinstance(policy_refs_raw, list)
        else []
    )
    compiled_document_policy_slots = (
        validate_compiled_document_policy_slots_snapshot(
            document_policy_projection.get("compiled_document_policy_slots")
        )
        if isinstance(document_policy_projection.get("compiled_document_policy_slots"), Mapping)
        else {}
    )
    document_policy_projection["compiled_document_policy_slots"] = compiled_document_policy_slots or {}
    document_policy_projection["slot_coverage_summary"] = _normalize_slot_coverage_summary(
        slot_coverage_summary=document_policy_projection.get("slot_coverage_summary"),
        policy_refs=policy_refs,
        compiled_document_policy_slots=compiled_document_policy_slots,
    )
    payload["document_policy_projection"] = document_policy_projection
    return payload


def _normalize_slot_coverage_summary(
    *,
    slot_coverage_summary: Mapping[str, Any] | None,
    policy_refs: list[dict[str, Any]],
    compiled_document_policy_slots: Mapping[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    if not isinstance(slot_coverage_summary, Mapping):
        return _build_slot_coverage_summary_from_policy_refs(
            policy_refs=policy_refs,
            compiled_document_policy_slots=compiled_document_policy_slots,
        )

    items_raw = slot_coverage_summary.get("items")
    if not isinstance(items_raw, list):
        return _build_slot_coverage_summary_from_policy_refs(
            policy_refs=policy_refs,
            compiled_document_policy_slots=compiled_document_policy_slots,
        )

    items = [_normalize_slot_coverage_item(item_raw) for item_raw in items_raw]
    counts = _build_empty_slot_coverage_counts()
    for item in items:
        counts[item["coverage"]["status"]] += 1
    return {
        "total_edges": len(items),
        "counts": counts,
        "items": items,
    }


def _build_slot_coverage_summary_from_policy_refs(
    *,
    policy_refs: list[dict[str, Any]],
    compiled_document_policy_slots: Mapping[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    counts = _build_empty_slot_coverage_counts()
    items: list[dict[str, Any]] = []
    normalized_slots = dict(compiled_document_policy_slots or {})

    for index, policy_ref in enumerate(policy_refs):
        edge_ref_raw = policy_ref.get("edge_ref")
        edge_ref = dict(edge_ref_raw) if isinstance(edge_ref_raw, Mapping) else {}
        parent_node_id = str(edge_ref.get("parent_node_id") or "").strip()
        child_node_id = str(edge_ref.get("child_node_id") or "").strip()
        slot_key = str(policy_ref.get("slot_key") or "").strip()
        edge_id = (
            f"{parent_node_id}:{child_node_id}"
            if parent_node_id or child_node_id
            else f"policy-ref-{index}"
        )
        edge_label = (
            f"{parent_node_id or '<unknown>'} -> {child_node_id or '<unknown>'}"
            if parent_node_id or child_node_id
            else edge_id
        )
        source = str(policy_ref.get("source") or "").strip()
        if not slot_key:
            coverage = {
                "code": POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING,
                "status": "missing_selector",
                "label": "Slot required",
                "detail": "Persisted artifact does not include slot_key for this edge.",
            }
        elif normalized_slots and slot_key not in normalized_slots:
            coverage = {
                "code": POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND,
                "status": "missing_slot",
                "label": "Slot missing",
                "detail": f"Persisted slot map does not include slot '{slot_key}'.",
            }
        else:
            slot_projection = normalized_slots.get(slot_key) if normalized_slots else None
            decision_table_id = (
                str(slot_projection.get("decision_table_id") or "").strip()
                if isinstance(slot_projection, Mapping)
                else ""
            )
            decision_revision = (
                str(slot_projection.get("decision_revision") or "").strip()
                if isinstance(slot_projection, Mapping)
                else ""
            )
            coverage = {
                "code": None,
                "status": "resolved",
                "label": "Resolved",
                "detail": (
                    f"{slot_key} -> {decision_table_id} r{decision_revision}"
                    if decision_table_id and decision_revision
                    else (source or slot_key)
                ),
            }
        counts[coverage["status"]] += 1
        items.append(
            {
                "edge_id": edge_id,
                "edge_label": edge_label,
                "slot_key": slot_key,
                "coverage": coverage,
            }
        )

    return {
        "total_edges": len(items),
        "counts": counts,
        "items": items,
    }


def _normalize_slot_coverage_item(item_raw: Any) -> dict[str, Any]:
    if not isinstance(item_raw, Mapping):
        raise ValueError(
            f"{POOL_RUNTIME_PROJECTION_INVALID}: slot_coverage_summary.items[] must be objects"
        )
    item = dict(item_raw)
    edge_id = str(item.get("edge_id") or "").strip()
    edge_label = str(item.get("edge_label") or "").strip()
    slot_key = str(item.get("slot_key") or "").strip()
    if not edge_id or not edge_label:
        raise ValueError(
            f"{POOL_RUNTIME_PROJECTION_INVALID}: slot_coverage_summary items require edge_id and edge_label"
        )
    return {
        "edge_id": edge_id,
        "edge_label": edge_label,
        "slot_key": slot_key,
        "coverage": _normalize_slot_coverage_payload(item.get("coverage")),
    }


def _normalize_slot_coverage_payload(raw_coverage: Any) -> dict[str, Any]:
    if not isinstance(raw_coverage, Mapping):
        raise ValueError(
            f"{POOL_RUNTIME_PROJECTION_INVALID}: slot_coverage_summary coverage must be an object"
        )
    coverage = dict(raw_coverage)
    status = str(coverage.get("status") or "").strip()
    if status not in _SLOT_COVERAGE_STATUSES:
        raise ValueError(
            f"{POOL_RUNTIME_PROJECTION_INVALID}: unexpected slot coverage status '{status or '<empty>'}'"
        )
    label = str(coverage.get("label") or "").strip()
    detail = str(coverage.get("detail") or "").strip()
    if not label or not detail:
        raise ValueError(
            f"{POOL_RUNTIME_PROJECTION_INVALID}: slot coverage label/detail are required"
        )
    raw_code = coverage.get("code")
    code = str(raw_code or "").strip() or None
    return {
        "code": code,
        "status": status,
        "label": label,
        "detail": detail,
    }


def _build_empty_slot_coverage_counts() -> dict[str, int]:
    return {
        "resolved": 0,
        "missing_selector": 0,
        "missing_slot": 0,
        "ambiguous_slot": 0,
        "ambiguous_context": 0,
        "unavailable_context": 0,
    }


__all__ = [
    "POOL_RUNTIME_PROJECTION_CONTEXT_KEY",
    "POOL_RUNTIME_PROJECTION_INVALID",
    "POOL_RUNTIME_PROJECTION_VERSION",
    "build_pool_runtime_projection_v1",
    "validate_pool_runtime_projection_v1",
]
