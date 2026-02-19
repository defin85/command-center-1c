from __future__ import annotations

from typing import Any, Mapping


FORBIDDEN_RUNTIME_OVERRIDE_RUN_INPUT_KEYS = frozenset(
    {
        "distribution_artifact",
        "distribution_artifact_v1",
        "pool_runtime_distribution_artifact",
        "document_plan_artifact",
        "document_plan_artifact_v1",
        "pool_runtime_document_plan_artifact",
        "pool_runtime_publication_payload",
    }
)


def sanitize_run_input_for_runtime_contract(*, run_input: Any) -> dict[str, Any]:
    payload = dict(run_input) if isinstance(run_input, Mapping) else {}
    for key in FORBIDDEN_RUNTIME_OVERRIDE_RUN_INPUT_KEYS:
        payload.pop(key, None)
    return payload
