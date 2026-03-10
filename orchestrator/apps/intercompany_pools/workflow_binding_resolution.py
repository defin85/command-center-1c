from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from apps.intercompany_pools.workflow_authoring_contract import PoolWorkflowBindingContract

ERROR_CODE_POOL_WORKFLOW_BINDING_INVALID = "POOL_WORKFLOW_BINDING_INVALID"
ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_FOUND = "POOL_WORKFLOW_BINDING_NOT_FOUND"
ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_RESOLVED = "POOL_WORKFLOW_BINDING_NOT_RESOLVED"


@dataclass(slots=True)
class PoolWorkflowBindingResolutionError(Exception):
    code: str
    detail: str
    errors: list[dict[str, Any]]

    def __str__(self) -> str:
        return self.detail


def resolve_pool_workflow_binding_for_run(
    *,
    raw_bindings: Iterable[Any],
    requested_binding_id: str | None,
    direction: str,
    mode: str,
    period_start: date,
) -> PoolWorkflowBindingContract | None:
    bindings = parse_pool_workflow_bindings(raw_bindings)
    if not bindings:
        return None

    # Selector matching is assistive-only and must not auto-resolve a runtime binding.
    if not requested_binding_id:
        return None

    if requested_binding_id:
        selected = next((binding for binding in bindings if binding.binding_id == requested_binding_id), None)
        if selected is None:
            raise PoolWorkflowBindingResolutionError(
                code=ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_FOUND,
                detail=f"Requested pool_workflow_binding_id '{requested_binding_id}' was not found.",
                errors=[{"binding_id": requested_binding_id}],
            )
        if not _is_binding_active_for_period(binding=selected, period_start=period_start):
            raise PoolWorkflowBindingResolutionError(
                code=ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_RESOLVED,
                detail=(
                    f"Requested pool_workflow_binding_id '{requested_binding_id}' is inactive "
                    "or outside the effective period."
                ),
                errors=[_serialize_binding_diagnostic(selected)],
            )
        if not _selector_matches(binding=selected, direction=direction, mode=mode, allow_tagged_binding=True):
            raise PoolWorkflowBindingResolutionError(
                code=ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_RESOLVED,
                detail=(
                    f"Requested pool_workflow_binding_id '{requested_binding_id}' "
                    "does not match the run direction/mode."
                ),
                errors=[_serialize_binding_diagnostic(selected)],
            )
        return selected
    return None


def parse_pool_workflow_bindings(raw_bindings: Iterable[Any]) -> list[PoolWorkflowBindingContract]:
    bindings: list[PoolWorkflowBindingContract] = []
    errors: list[dict[str, Any]] = []
    for index, raw_binding in enumerate(raw_bindings, start=1):
        if not isinstance(raw_binding, dict):
            errors.append(
                {
                    "binding_index": index,
                    "detail": "binding payload must be an object",
                }
            )
            continue
        try:
            bindings.append(PoolWorkflowBindingContract(**raw_binding))
        except Exception as exc:
            errors.append(
                {
                    "binding_index": index,
                    "binding_id": str(raw_binding.get("binding_id") or "").strip() or None,
                    "detail": str(exc),
                }
            )
    if errors:
        raise PoolWorkflowBindingResolutionError(
            code=ERROR_CODE_POOL_WORKFLOW_BINDING_INVALID,
            detail="Stored pool workflow bindings are invalid and cannot be resolved.",
            errors=errors,
        )
    return bindings


def _is_binding_active_for_period(*, binding: PoolWorkflowBindingContract, period_start: date) -> bool:
    if binding.status.value != "active":
        return False
    if period_start < binding.effective_from:
        return False
    if binding.effective_to is not None and period_start > binding.effective_to:
        return False
    return True


def _selector_matches(
    *,
    binding: PoolWorkflowBindingContract,
    direction: str,
    mode: str,
    allow_tagged_binding: bool,
) -> bool:
    selector = binding.selector
    if selector.direction and selector.direction != direction:
        return False
    if selector.mode and selector.mode != mode:
        return False
    if selector.tags and not allow_tagged_binding:
        return False
    return True


def _serialize_binding_diagnostic(binding: PoolWorkflowBindingContract) -> dict[str, Any]:
    return {
        "binding_id": binding.binding_id,
        "pool_id": binding.pool_id,
        "workflow_definition_key": binding.workflow.workflow_definition_key,
        "workflow_revision": binding.workflow.workflow_revision,
        "status": binding.status.value,
        "effective_from": binding.effective_from.isoformat(),
        "effective_to": binding.effective_to.isoformat() if binding.effective_to else None,
        "selector": binding.selector.model_dump(mode="json"),
    }


__all__ = [
    "ERROR_CODE_POOL_WORKFLOW_BINDING_INVALID",
    "ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_FOUND",
    "ERROR_CODE_POOL_WORKFLOW_BINDING_NOT_RESOLVED",
    "PoolWorkflowBindingResolutionError",
    "parse_pool_workflow_bindings",
    "resolve_pool_workflow_binding_for_run",
]
