from __future__ import annotations

from apps.templates.workflow.models import WorkflowCategory, WorkflowTemplate


WORKFLOW_MANAGEMENT_MODE_USER_AUTHORED = "user_authored"
WORKFLOW_MANAGEMENT_MODE_SYSTEM_MANAGED = "system_managed"

WORKFLOW_VISIBILITY_SURFACE_LIBRARY = "workflow_library"
WORKFLOW_VISIBILITY_SURFACE_RUNTIME_DIAGNOSTICS = "runtime_diagnostics"

WORKFLOW_SYSTEM_MANAGED_READ_ONLY_CODE = "WORKFLOW_SYSTEM_MANAGED_READ_ONLY"
WORKFLOW_SYSTEM_MANAGED_READ_ONLY_REASON = (
    "System-managed runtime workflow projections are read-only and available only through diagnostics surfaces."
)


def is_system_managed_workflow(workflow: WorkflowTemplate) -> bool:
    return (
        workflow.category == WorkflowCategory.SYSTEM
        and not bool(workflow.is_template)
    )


def resolve_workflow_management_mode(workflow: WorkflowTemplate) -> str:
    if is_system_managed_workflow(workflow):
        return WORKFLOW_MANAGEMENT_MODE_SYSTEM_MANAGED
    return WORKFLOW_MANAGEMENT_MODE_USER_AUTHORED


def resolve_workflow_visibility_surface(workflow: WorkflowTemplate) -> str:
    if is_system_managed_workflow(workflow):
        return WORKFLOW_VISIBILITY_SURFACE_RUNTIME_DIAGNOSTICS
    return WORKFLOW_VISIBILITY_SURFACE_LIBRARY


def resolve_workflow_read_only_reason(workflow: WorkflowTemplate) -> str | None:
    if is_system_managed_workflow(workflow):
        return WORKFLOW_SYSTEM_MANAGED_READ_ONLY_REASON
    return None


__all__ = [
    "WORKFLOW_MANAGEMENT_MODE_SYSTEM_MANAGED",
    "WORKFLOW_MANAGEMENT_MODE_USER_AUTHORED",
    "WORKFLOW_SYSTEM_MANAGED_READ_ONLY_CODE",
    "WORKFLOW_SYSTEM_MANAGED_READ_ONLY_REASON",
    "WORKFLOW_VISIBILITY_SURFACE_LIBRARY",
    "WORKFLOW_VISIBILITY_SURFACE_RUNTIME_DIAGNOSTICS",
    "is_system_managed_workflow",
    "resolve_workflow_management_mode",
    "resolve_workflow_read_only_reason",
    "resolve_workflow_visibility_surface",
]
