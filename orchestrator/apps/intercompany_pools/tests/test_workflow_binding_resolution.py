from __future__ import annotations

from datetime import date
from uuid import uuid4

from apps.intercompany_pools.workflow_binding_resolution import (
    resolve_pool_workflow_binding_for_run,
)


def _build_binding_payload(
    *,
    binding_id: str | None = None,
    direction: str | None = "bottom_up",
    mode: str | None = "safe",
    tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "binding_id": binding_id or str(uuid4()),
        "pool_id": str(uuid4()),
        "workflow": {
            "workflow_definition_key": f"workflow-{uuid4().hex[:8]}",
            "workflow_revision_id": str(uuid4()),
            "workflow_revision": 3,
            "workflow_name": "workflow-binding-resolution-test",
        },
        "decisions": [
            {
                "decision_table_id": f"decision-{uuid4().hex[:8]}",
                "decision_key": "document_policy",
                "decision_revision": 1,
            }
        ],
        "selector": {
            "direction": direction,
            "mode": mode,
            "tags": list(tags or []),
        },
        "effective_from": "2026-01-01",
        "status": "active",
    }


def test_resolve_pool_workflow_binding_for_run_requires_explicit_binding_id_for_runtime_resolution() -> None:
    binding = _build_binding_payload()

    resolved = resolve_pool_workflow_binding_for_run(
        raw_bindings=[binding],
        requested_binding_id=None,
        direction="bottom_up",
        mode="safe",
        period_start=date(2026, 1, 1),
    )

    assert resolved is None


def test_resolve_pool_workflow_binding_for_run_still_resolves_requested_binding_id() -> None:
    binding = _build_binding_payload()

    resolved = resolve_pool_workflow_binding_for_run(
        raw_bindings=[binding],
        requested_binding_id=str(binding["binding_id"]),
        direction="bottom_up",
        mode="safe",
        period_start=date(2026, 1, 1),
    )

    assert resolved is not None
    assert resolved.binding_id == binding["binding_id"]
