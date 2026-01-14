from __future__ import annotations

import uuid
from typing import Any

from apps.artifacts.refs import contains_artifact_ref


def find_purge_blockers(artifact_id: uuid.UUID, limit: int = 50) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    from apps.operations.models import BatchOperation
    from apps.templates.workflow.models import WorkflowExecution
    from apps.artifacts.models import ArtifactUsage

    usage_ops = (
        ArtifactUsage.objects.filter(
            artifact_id=artifact_id,
            operation__isnull=False,
            operation__status__in=[
                BatchOperation.STATUS_PENDING,
                BatchOperation.STATUS_QUEUED,
                BatchOperation.STATUS_PROCESSING,
            ],
        )
        .select_related("operation")
        .order_by("-used_at")
    )
    for usage in usage_ops.iterator():
        op = usage.operation
        if op is None:
            continue
        key = ("batch_operation", str(op.id))
        if key in seen:
            continue
        seen.add(key)
        blockers.append(
            {
                "type": "batch_operation",
                "id": op.id,
                "status": op.status,
                "name": op.name,
                "details": "",
            }
        )
        if len(blockers) >= limit:
            return blockers

    usage_execs = (
        ArtifactUsage.objects.filter(
            artifact_id=artifact_id,
            workflow_execution__isnull=False,
            workflow_execution__status__in=[WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING],
        )
        .select_related("workflow_execution", "workflow_execution__workflow_template")
        .order_by("-used_at")
    )
    for usage in usage_execs.iterator():
        execution = usage.workflow_execution
        if execution is None:
            continue
        key = ("workflow_execution", str(execution.id))
        if key in seen:
            continue
        seen.add(key)
        blockers.append(
            {
                "type": "workflow_execution",
                "id": str(execution.id),
                "status": execution.status,
                "name": execution.workflow_template.name,
                "details": "",
            }
        )
        if len(blockers) >= limit:
            return blockers

    active_ops = BatchOperation.objects.filter(
        status__in=[
            BatchOperation.STATUS_PENDING,
            BatchOperation.STATUS_QUEUED,
            BatchOperation.STATUS_PROCESSING,
        ]
    ).only("id", "name", "status", "payload", "config")

    for op in active_ops.iterator():
        if contains_artifact_ref(op.payload, artifact_id) or contains_artifact_ref(op.config, artifact_id):
            key = ("batch_operation", str(op.id))
            if key in seen:
                continue
            seen.add(key)
            blockers.append(
                {
                    "type": "batch_operation",
                    "id": op.id,
                    "status": op.status,
                    "name": op.name,
                    "details": "",
                }
            )
            if len(blockers) >= limit:
                return blockers

    active_execs = WorkflowExecution.objects.filter(
        status__in=[WorkflowExecution.STATUS_PENDING, WorkflowExecution.STATUS_RUNNING]
    ).select_related("workflow_template").only("id", "status", "workflow_template__name", "input_context")

    for execution in active_execs.iterator():
        if contains_artifact_ref(execution.input_context, artifact_id):
            key = ("workflow_execution", str(execution.id))
            if key in seen:
                continue
            seen.add(key)
            blockers.append(
                {
                    "type": "workflow_execution",
                    "id": str(execution.id),
                    "status": execution.status,
                    "name": execution.workflow_template.name,
                    "details": "",
                }
            )
            if len(blockers) >= limit:
                return blockers

    return blockers


def is_artifact_in_use(artifact_id: uuid.UUID) -> bool:
    return len(find_purge_blockers(artifact_id, limit=1)) > 0
