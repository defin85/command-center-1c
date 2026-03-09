from __future__ import annotations

from typing import Any

from apps.runtime_settings.effective import get_effective_runtime_setting
from apps.templates.workflow.authoring_contract import build_workflow_construct_visibility


WORKFLOW_AUTHORING_PHASE_RUNTIME_KEY = "workflows.authoring.phase"

WORKFLOW_AUTHORING_PHASE_LEGACY_TECHNICAL_DAG = "legacy_technical_dag"
WORKFLOW_AUTHORING_PHASE_WORKFLOW_CENTRIC_PREREQUISITE = "workflow_centric_prerequisite"
WORKFLOW_AUTHORING_PHASE_WORKFLOW_CENTRIC_ACTIVE = "workflow_centric_active"

_PHASE_SUMMARIES: dict[str, dict[str, Any]] = {
    WORKFLOW_AUTHORING_PHASE_LEGACY_TECHNICAL_DAG: {
        "phase": WORKFLOW_AUTHORING_PHASE_LEGACY_TECHNICAL_DAG,
        "label": "Legacy technical DAG phase",
        "description": (
            "Workflows remain a technical DAG catalog while workflow-centric analyst "
            "modeling for pools is not yet enabled."
        ),
        "is_prerequisite_platform_phase": False,
        "analyst_surface": "/workflows",
        "rollout_scope": ["technical_workflow_catalog"],
        "deferred_scope": [],
        "follow_up_changes": [],
    },
    WORKFLOW_AUTHORING_PHASE_WORKFLOW_CENTRIC_PREREQUISITE: {
        "phase": WORKFLOW_AUTHORING_PHASE_WORKFLOW_CENTRIC_PREREQUISITE,
        "label": "Workflow-centric prerequisite phase",
        "description": (
            "Workflows are becoming the primary analyst-facing scheme library for pools."
        ),
        "is_prerequisite_platform_phase": True,
        "analyst_surface": "/workflows",
        "rollout_scope": ["pool_distribution", "pool_publication"],
        "deferred_scope": ["extensions.*", "database.ib_user.*"],
        "follow_up_changes": ["add-13-service-workflow-automation"],
    },
    WORKFLOW_AUTHORING_PHASE_WORKFLOW_CENTRIC_ACTIVE: {
        "phase": WORKFLOW_AUTHORING_PHASE_WORKFLOW_CENTRIC_ACTIVE,
        "label": "Workflow-centric active phase",
        "description": (
            "Workflow-centric analyst modeling is active for pools and drives runtime "
            "projection for new scheme authoring."
        ),
        "is_prerequisite_platform_phase": False,
        "analyst_surface": "/workflows",
        "rollout_scope": ["pool_distribution", "pool_publication"],
        "deferred_scope": ["extensions.*", "database.ib_user.*"],
        "follow_up_changes": ["add-13-service-workflow-automation"],
    },
}


def get_workflow_authoring_phase_summary(*, tenant_id: str | None) -> dict[str, Any]:
    effective = get_effective_runtime_setting(WORKFLOW_AUTHORING_PHASE_RUNTIME_KEY, tenant_id)
    raw_phase = str(effective.value or "").strip()
    summary = dict(
        _PHASE_SUMMARIES.get(
            raw_phase,
            _PHASE_SUMMARIES[WORKFLOW_AUTHORING_PHASE_WORKFLOW_CENTRIC_PREREQUISITE],
        )
    )
    summary["construct_visibility"] = build_workflow_construct_visibility().model_dump()
    summary["source"] = effective.source
    return summary
