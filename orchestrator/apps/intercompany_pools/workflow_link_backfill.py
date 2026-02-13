from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from apps.intercompany_pools.models import PoolRun
from apps.templates.workflow.models import WorkflowExecution

ATTEMPT_KIND_INITIAL = "initial"
ATTEMPT_KIND_RETRY = "retry"


@dataclass(frozen=True)
class _ExecutionCandidate:
    id: UUID
    tenant_id: UUID | None
    status: str
    workflow_template_name: str
    input_context: dict[str, Any]
    started_at: Any | None


@dataclass(frozen=True)
class _LineageAttempt:
    execution_id: UUID
    status: str
    workflow_template_name: str
    workflow_run_id: str
    root_workflow_run_id: str
    parent_workflow_run_id: str | None
    attempt_number: int
    attempt_kind: str


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


def _parse_attempt_number(raw_attempt_number: object) -> int | None:
    try:
        value = int(raw_attempt_number)
    except (TypeError, ValueError):
        return None
    if value < 1:
        return None
    return value


def _normalize_workflow_run_id(raw_workflow_run_id: object) -> str | None:
    token = str(raw_workflow_run_id or "").strip()
    if not token:
        return None
    try:
        UUID(token)
    except (TypeError, ValueError, AttributeError):
        return None
    return token


def _normalize_attempt_kind(raw_attempt_kind: object) -> str | None:
    token = str(raw_attempt_kind or "").strip().lower()
    if token in {ATTEMPT_KIND_INITIAL, ATTEMPT_KIND_RETRY}:
        return token
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
                input_context=execution.input_context if isinstance(execution.input_context, dict) else {},
                started_at=execution.started_at,
            )
        )
    return candidates


def _resolve_lineage_candidates(
    *,
    run: PoolRun,
    candidates: list[_ExecutionCandidate],
    stats: PoolRunWorkflowLinkBackfillStats,
) -> list[_ExecutionCandidate]:
    exact_tenant_candidates = [
        candidate for candidate in candidates if candidate.tenant_id == run.tenant_id
    ]
    if exact_tenant_candidates:
        return exact_tenant_candidates

    null_tenant_candidates = [
        candidate for candidate in candidates if candidate.tenant_id is None
    ]
    cross_tenant_candidates = [
        candidate
        for candidate in candidates
        if candidate.tenant_id is not None and candidate.tenant_id != run.tenant_id
    ]
    if null_tenant_candidates and not cross_tenant_candidates:
        return null_tenant_candidates

    if cross_tenant_candidates and not null_tenant_candidates:
        stats.runs_cross_tenant_only += 1
    else:
        stats.runs_ambiguous += 1
    return []


def _candidate_sort_key(candidate: _ExecutionCandidate) -> tuple[int, str, str]:
    context = candidate.input_context if isinstance(candidate.input_context, dict) else {}
    attempt_number = _parse_attempt_number(context.get("attempt_number"))
    attempt_sort = attempt_number if attempt_number is not None else 10**9
    started_at_sort = candidate.started_at.isoformat() if candidate.started_at else ""
    return (attempt_sort, started_at_sort, str(candidate.id))


def _build_lineage_attempts(candidates: list[_ExecutionCandidate]) -> list[_LineageAttempt]:
    ordered_candidates = sorted(candidates, key=_candidate_sort_key)
    attempts: list[_LineageAttempt] = []
    previous_workflow_run_id: str | None = None
    next_attempt_number = 1
    root_workflow_run_id: str | None = None

    for candidate in ordered_candidates:
        context = candidate.input_context if isinstance(candidate.input_context, dict) else {}
        workflow_run_id = str(candidate.id)
        explicit_root = _normalize_workflow_run_id(context.get("root_workflow_run_id"))
        if root_workflow_run_id is None:
            root_workflow_run_id = explicit_root or workflow_run_id

        explicit_attempt_number = _parse_attempt_number(context.get("attempt_number"))
        attempt_number = explicit_attempt_number if explicit_attempt_number is not None else next_attempt_number
        if attempt_number < next_attempt_number:
            attempt_number = next_attempt_number

        if previous_workflow_run_id is None:
            attempt_number = 1
            attempt_kind = ATTEMPT_KIND_INITIAL
            parent_workflow_run_id = None
        else:
            attempt_kind = _normalize_attempt_kind(context.get("attempt_kind")) or ATTEMPT_KIND_RETRY
            parent_workflow_run_id = (
                _normalize_workflow_run_id(context.get("parent_workflow_run_id"))
                or previous_workflow_run_id
            )

        attempts.append(
            _LineageAttempt(
                execution_id=candidate.id,
                status=candidate.status,
                workflow_template_name=candidate.workflow_template_name,
                workflow_run_id=workflow_run_id,
                root_workflow_run_id=root_workflow_run_id,
                parent_workflow_run_id=parent_workflow_run_id,
                attempt_number=attempt_number,
                attempt_kind=attempt_kind,
            )
        )
        previous_workflow_run_id = workflow_run_id
        next_attempt_number = attempt_number + 1

    return attempts


def _backfill_execution_lineage_metadata(
    *,
    run_id: UUID,
    candidate_by_id: dict[UUID, _ExecutionCandidate],
    lineage_attempts: list[_LineageAttempt],
) -> None:
    for attempt in lineage_attempts:
        candidate = candidate_by_id.get(attempt.execution_id)
        if candidate is None:
            continue
        context = dict(candidate.input_context if isinstance(candidate.input_context, dict) else {})
        expected_context = {
            "pool_run_id": str(run_id),
            "workflow_run_id": attempt.workflow_run_id,
            "root_workflow_run_id": attempt.root_workflow_run_id,
            "parent_workflow_run_id": attempt.parent_workflow_run_id,
            "attempt_number": attempt.attempt_number,
            "attempt_kind": attempt.attempt_kind,
        }
        changed = False
        for key, expected_value in expected_context.items():
            if key not in context or context.get(key) != expected_value:
                context[key] = expected_value
                changed = True

        if changed:
            WorkflowExecution.objects.filter(id=attempt.execution_id).update(input_context=context)


def run_pool_run_workflow_link_backfill() -> PoolRunWorkflowLinkBackfillStats:
    stats = PoolRunWorkflowLinkBackfillStats()
    execution_candidates = _build_execution_candidates(stats=stats)
    runs = PoolRun.objects.select_related("tenant").order_by("id")

    for run in runs.iterator():
        stats.runs_scanned += 1
        if run.workflow_execution_id is not None:
            stats.runs_already_linked += 1

        candidates = execution_candidates.get(run.id) or []
        if not candidates:
            stats.runs_without_candidate += 1
            continue

        lineage_candidates = _resolve_lineage_candidates(run=run, candidates=candidates, stats=stats)
        if not lineage_candidates:
            continue

        lineage_attempts = _build_lineage_attempts(lineage_candidates)
        if not lineage_attempts:
            continue

        candidate_by_id = {candidate.id: candidate for candidate in lineage_candidates}
        _backfill_execution_lineage_metadata(
            run_id=run.id,
            candidate_by_id=candidate_by_id,
            lineage_attempts=lineage_attempts,
        )

        active_attempt = lineage_attempts[-1]
        was_unlinked = run.workflow_execution_id is None
        update_fields: list[str] = []

        if run.workflow_execution_id != active_attempt.execution_id:
            run.workflow_execution_id = active_attempt.execution_id
            update_fields.append("workflow_execution_id")
        if run.workflow_status != active_attempt.status:
            run.workflow_status = active_attempt.status
            update_fields.append("workflow_status")
        if run.execution_backend != "workflow_core":
            run.execution_backend = "workflow_core"
            update_fields.append("execution_backend")
        if active_attempt.workflow_template_name and run.workflow_template_name != active_attempt.workflow_template_name:
            run.workflow_template_name = active_attempt.workflow_template_name
            update_fields.append("workflow_template_name")

        if update_fields:
            update_fields.append("updated_at")
            run.save(update_fields=update_fields)
        if was_unlinked and run.workflow_execution_id is not None:
            stats.runs_linked += 1

    return stats
