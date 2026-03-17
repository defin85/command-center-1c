from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.intercompany_pools.workflow_binding_resolution import (
    ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_FOUND,
    ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_RESOLVED,
    PoolWorkflowBindingResolutionError,
    resolve_pool_workflow_binding_for_run,
)


def _build_binding_payload(
    *,
    binding_id: str | None = None,
    direction: str | None = "bottom_up",
    mode: str | None = "safe",
    tags: list[str] | None = None,
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
    status: str = "active",
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
                "slot_key": "document_policy",
                "decision_revision": 1,
            }
        ],
        "selector": {
            "direction": direction,
            "mode": mode,
            "tags": list(tags or []),
        },
        "effective_from": effective_from,
        "effective_to": effective_to,
        "status": status,
    }


def _build_attachment_payload(
    *,
    binding_id: str | None = None,
    direction: str | None = "bottom_up",
    mode: str | None = "safe",
    tags: list[str] | None = None,
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
    status: str = "active",
) -> dict[str, object]:
    binding = _build_binding_payload(
        binding_id=binding_id,
        direction=direction,
        mode=mode,
        tags=tags,
        effective_from=effective_from,
        effective_to=effective_to,
        status=status,
    )
    return {
        "binding_id": binding["binding_id"],
        "pool_id": binding["pool_id"],
        "binding_profile_id": str(uuid4()),
        "binding_profile_revision_id": "binding-profile-revision-1",
        "binding_profile_revision_number": 2,
        "revision": 4,
        "selector": binding["selector"],
        "effective_from": binding["effective_from"],
        "effective_to": binding["effective_to"],
        "status": binding["status"],
        "resolved_profile": {
            "binding_profile_id": str(uuid4()),
            "code": "services-publication",
            "name": "Services Publication",
            "status": "active",
            "binding_profile_revision_id": "binding-profile-revision-1",
            "binding_profile_revision_number": 2,
            "workflow": binding["workflow"],
            "decisions": binding["decisions"],
            "parameters": {"publication_variant": "full"},
            "role_mapping": {"initiator": "finance"},
        },
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


def test_resolve_pool_workflow_binding_for_run_returns_not_found_for_unknown_binding_id() -> None:
    requested_binding_id = "missing-binding"

    with pytest.raises(PoolWorkflowBindingResolutionError) as exc_info:
        resolve_pool_workflow_binding_for_run(
            raw_bindings=[],
            requested_binding_id=requested_binding_id,
            direction="bottom_up",
            mode="safe",
            period_start=date(2026, 1, 1),
        )

    assert exc_info.value.code == ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_FOUND
    assert exc_info.value.errors == [{"binding_id": requested_binding_id}]


def test_resolve_pool_workflow_binding_for_run_does_not_fallback_from_out_of_scope_attachment() -> None:
    expired_attachment = _build_attachment_payload(
        effective_from="2025-01-01",
        effective_to="2025-12-31",
    )
    matching_attachment = _build_attachment_payload()

    with pytest.raises(PoolWorkflowBindingResolutionError) as exc_info:
        resolve_pool_workflow_binding_for_run(
            raw_bindings=[expired_attachment, matching_attachment],
            requested_binding_id=str(expired_attachment["binding_id"]),
            direction="bottom_up",
            mode="safe",
            period_start=date(2026, 1, 1),
        )

    assert exc_info.value.code == ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_RESOLVED
    assert exc_info.value.errors == [
        {
            "binding_id": expired_attachment["binding_id"],
            "pool_id": expired_attachment["pool_id"],
            "workflow_definition_key": expired_attachment["resolved_profile"]["workflow"]["workflow_definition_key"],
            "workflow_revision": expired_attachment["resolved_profile"]["workflow"]["workflow_revision"],
            "status": "active",
            "effective_from": "2025-01-01",
            "effective_to": "2025-12-31",
            "selector": expired_attachment["selector"],
        }
    ]


def test_resolve_pool_workflow_binding_for_run_accepts_attachment_read_model_payload() -> None:
    attachment = _build_attachment_payload()

    resolved = resolve_pool_workflow_binding_for_run(
        raw_bindings=[attachment],
        requested_binding_id=str(attachment["binding_id"]),
        direction="bottom_up",
        mode="safe",
        period_start=date(2026, 1, 1),
    )

    assert resolved is not None
    assert resolved.binding_id == attachment["binding_id"]
    assert resolved.binding_profile_revision_id == attachment["binding_profile_revision_id"]
    assert resolved.binding_profile_revision_number == attachment["binding_profile_revision_number"]
    assert resolved.revision == attachment["revision"]
    assert resolved.workflow.workflow_revision == 3
