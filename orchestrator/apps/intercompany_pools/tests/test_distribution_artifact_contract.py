from __future__ import annotations

import pytest

from apps.intercompany_pools.distribution_artifact_contract import (
    POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY,
    resolve_distribution_artifact_for_downstream_compile,
    validate_distribution_artifact_v1,
)
from apps.intercompany_pools.runtime_distribution import DISTRIBUTION_ARTIFACT_VERSION


def _build_distribution_artifact() -> dict[str, object]:
    return {
        "version": DISTRIBUTION_ARTIFACT_VERSION,
        "topology_version_ref": "topology-2026-01-01",
        "node_totals": [],
        "edge_allocations": [],
        "coverage": {"is_full": True, "missing_target_node_ids": []},
        "balance": {
            "is_balanced": True,
            "source_total": "100.00",
            "distributed_total": "100.00",
            "delta": "0.00",
        },
        "input_provenance": {"source_payload_rows_count": 1},
    }


def test_validate_distribution_artifact_v1_accepts_minimal_required_contract() -> None:
    artifact = _build_distribution_artifact()

    payload = validate_distribution_artifact_v1(artifact=artifact)

    assert payload["version"] == DISTRIBUTION_ARTIFACT_VERSION
    assert payload["topology_version_ref"] == "topology-2026-01-01"


def test_validate_distribution_artifact_v1_rejects_missing_required_field() -> None:
    artifact = _build_distribution_artifact()
    artifact.pop("coverage")

    with pytest.raises(ValueError, match="POOL_DISTRIBUTION_ARTIFACT_INVALID"):
        validate_distribution_artifact_v1(artifact=artifact)


def test_resolve_distribution_artifact_for_downstream_compile_requires_upstream_context_key() -> None:
    with pytest.raises(
        ValueError,
        match="distribution_artifact.v1 is required upstream input for document_plan_artifact compile",
    ):
        resolve_distribution_artifact_for_downstream_compile(execution_context={})


def test_resolve_distribution_artifact_for_downstream_compile_returns_validated_artifact() -> None:
    artifact = _build_distribution_artifact()

    payload = resolve_distribution_artifact_for_downstream_compile(
        execution_context={POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY: artifact}
    )

    assert payload["version"] == DISTRIBUTION_ARTIFACT_VERSION


def test_resolve_distribution_artifact_for_downstream_compile_rejects_raw_run_input_bypass() -> None:
    artifact = _build_distribution_artifact()

    with pytest.raises(
        ValueError,
        match="distribution_artifact.v1 is required upstream input for document_plan_artifact compile",
    ):
        resolve_distribution_artifact_for_downstream_compile(
            execution_context={
                "run_input": {
                    POOL_RUNTIME_DISTRIBUTION_ARTIFACT_CONTEXT_KEY: artifact,
                }
            }
        )
