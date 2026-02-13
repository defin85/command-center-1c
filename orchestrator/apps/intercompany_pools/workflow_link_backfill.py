from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from apps.intercompany_pools.models import PoolRun
from apps.templates.workflow.models import WorkflowExecution


@dataclass(frozen=True)
class _ExecutionCandidate:
    id: UUID
    tenant_id: UUID | None
    status: str
    workflow_template_name: str


@dataclass
class PoolRunWorkflowLinkBackfillStats:
    executions_scanned: int = 0
    executions_with_pool_run_id: int = 0
    executions_invalid_pool_run_id: int = 0
    runs_scanned: int = 0
    runs_already_linked: int = 0
    runs_linked: int = 0
    runs_without_candidate: int = 0
    runs_ambiguous: int = 0
    runs_cross_tenant_only: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "executions_scanned": self.executions_scanned,
            "executions_with_pool_run_id": self.executions_with_pool_run_id,
            "executions_invalid_pool_run_id": self.executions_invalid_pool_run_id,
            "runs_scanned": self.runs_scanned,
            "runs_already_linked": self.runs_already_linked,
            "runs_linked": self.runs_linked,
            "runs_without_candidate": self.runs_without_candidate,
            "runs_ambiguous": self.runs_ambiguous,
            "runs_cross_tenant_only": self.runs_cross_tenant_only,
        }


def _parse_pool_run_id(raw_pool_run_id: object) -> UUID | None:
    token = str(raw_pool_run_id or "").strip()
    if not token:
        return None
    try:
        return UUID(token)
    except (TypeError, ValueError, AttributeError):
        return None


def _build_execution_candidates(
    *,
    stats: PoolRunWorkflowLinkBackfillStats,
) -> dict[UUID, list[_ExecutionCandidate]]:
    candidates: dict[UUID, list[_ExecutionCandidate]] = defaultdict(list)
    executions = (
        WorkflowExecution.objects.filter(execution_consumer="pools")
        .select_related("workflow_template")
        .order_by("id")
    )
    for execution in executions.iterator():
        stats.executions_scanned += 1
        raw_pool_run_id = (
            execution.input_context.get("pool_run_id")
            if isinstance(execution.input_context, dict)
            else None
        )
        if raw_pool_run_id in (None, ""):
            continue
        pool_run_id = _parse_pool_run_id(raw_pool_run_id)
        if pool_run_id is None:
            stats.executions_invalid_pool_run_id += 1
            continue
        stats.executions_with_pool_run_id += 1
        candidates[pool_run_id].append(
            _ExecutionCandidate(
                id=execution.id,
                tenant_id=execution.tenant_id,
                status=execution.status,
                workflow_template_name=str(execution.workflow_template.name or "").strip(),
            )
        )
    return candidates


def _resolve_candidate(
    *,
    run: PoolRun,
    candidates: list[_ExecutionCandidate],
    stats: PoolRunWorkflowLinkBackfillStats,
) -> _ExecutionCandidate | None:
    exact_tenant_candidates = [candidate for candidate in candidates if candidate.tenant_id == run.tenant_id]
    if len(exact_tenant_candidates) == 1:
        return exact_tenant_candidates[0]
    if len(exact_tenant_candidates) > 1:
        stats.runs_ambiguous += 1
        return None

    null_tenant_candidates = [candidate for candidate in candidates if candidate.tenant_id is None]
    if len(candidates) == 1 and len(null_tenant_candidates) == 1:
        return null_tenant_candidates[0]

    if null_tenant_candidates:
        stats.runs_ambiguous += 1
    else:
        stats.runs_cross_tenant_only += 1
    return None


def run_pool_run_workflow_link_backfill() -> PoolRunWorkflowLinkBackfillStats:
    stats = PoolRunWorkflowLinkBackfillStats()
    execution_candidates = _build_execution_candidates(stats=stats)
    runs = PoolRun.objects.select_related("tenant").order_by("id")

    for run in runs.iterator():
        stats.runs_scanned += 1
        if run.workflow_execution_id is not None:
            stats.runs_already_linked += 1
            continue

        candidates = execution_candidates.get(run.id) or []
        if not candidates:
            stats.runs_without_candidate += 1
            continue

        selected_candidate = _resolve_candidate(run=run, candidates=candidates, stats=stats)
        if selected_candidate is None:
            continue

        run.workflow_execution_id = selected_candidate.id
        run.workflow_status = selected_candidate.status
        run.execution_backend = "workflow_core"

        update_fields = ["workflow_execution_id", "workflow_status", "execution_backend", "updated_at"]
        if selected_candidate.workflow_template_name and not run.workflow_template_name:
            run.workflow_template_name = selected_candidate.workflow_template_name
            update_fields.append("workflow_template_name")

        run.save(update_fields=update_fields)
        stats.runs_linked += 1

    return stats
