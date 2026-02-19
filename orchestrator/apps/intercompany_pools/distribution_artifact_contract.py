from __future__ import annotations

from typing import Any, Mapping

from .runtime_distribution import DISTRIBUTION_ARTIFACT_VERSION


POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY = "pool_runtime_distribution_artifact"
POOL_DISTRIBUTION_ARTIFACT_INVALID = "POOL_DISTRIBUTION_ARTIFACT_INVALID"

REQUIRED_DISTRIBUTION_ARTIFACT_FIELDS = {
    "version",
    "topology_version_ref",
    "node_totals",
    "edge_allocations",
    "coverage",
    "balance",
    "input_provenance",
}


def validate_distribution_artifact_v1(*, artifact: Any) -> dict[str, Any]:
    if not isinstance(artifact, Mapping):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: distribution_artifact.v1 is missing in execution context"
        )
    artifact_payload = dict(artifact)
    missing_fields = sorted(
        field_name
        for field_name in REQUIRED_DISTRIBUTION_ARTIFACT_FIELDS
        if field_name not in artifact_payload
    )
    if missing_fields:
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: missing required artifact fields: {', '.join(missing_fields)}"
        )
    version = str(artifact_payload.get("version") or "").strip()
    if version != DISTRIBUTION_ARTIFACT_VERSION:
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: unexpected artifact version '{version or '<empty>'}'"
        )
    if not isinstance(artifact_payload.get("coverage"), Mapping):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: field 'coverage' must be an object in distribution_artifact.v1"
        )
    if not isinstance(artifact_payload.get("balance"), Mapping):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: field 'balance' must be an object in distribution_artifact.v1"
        )
    if not isinstance(artifact_payload.get("node_totals"), list):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: field 'node_totals' must be an array in distribution_artifact.v1"
        )
    if not isinstance(artifact_payload.get("edge_allocations"), list):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: field 'edge_allocations' must be an array in distribution_artifact.v1"
        )
    if not isinstance(artifact_payload.get("input_provenance"), Mapping):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: field 'input_provenance' must be an object in distribution_artifact.v1"
        )
    return artifact_payload


def resolve_distribution_artifact_for_downstream_compile(
    *,
    execution_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(execution_context, Mapping) or (
        POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY not in execution_context
    ):
        raise ValueError(
            f"{POOL_DISTRIBUTION_ARTIFACT_INVALID}: distribution_artifact.v1 is required upstream input "
            "for document_plan_artifact compile"
        )

    return validate_distribution_artifact_v1(
        artifact=execution_context.get(POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY)
    )
