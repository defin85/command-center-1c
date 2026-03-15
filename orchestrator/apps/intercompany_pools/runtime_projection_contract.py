from __future__ import annotations

from typing import Any, Mapping

from .document_plan_artifact_contract import validate_document_plan_artifact_v1


POOL_RUNTIME_PROJECTION_VERSION = "pool_runtime_projection.v1"
POOL_RUNTIME_PROJECTION_CONTEXT_KEY = "pool_runtime_projection"
POOL_RUNTIME_PROJECTION_INVALID = "POOL_RUNTIME_PROJECTION_INVALID"


def build_pool_runtime_projection_v1(
    *,
    run,
    plan,
    document_plan_artifact: Mapping[str, Any] | None,
    compiled_document_policy: Mapping[str, Any] | None = None,
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
    return payload


__all__ = [
    "POOL_RUNTIME_PROJECTION_CONTEXT_KEY",
    "POOL_RUNTIME_PROJECTION_INVALID",
    "POOL_RUNTIME_PROJECTION_VERSION",
    "build_pool_runtime_projection_v1",
    "validate_pool_runtime_projection_v1",
]
