from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from apps.intercompany_pools.models import PoolRun
from apps.templates.workflow.models import WorkflowExecution


@dataclass
class WorkflowExecutionPoolsTenantBackfillStats:
    executions_scanned: int = 0
    executions_with_pool_run_id: int = 0
    executions_invalid_pool_run_id: int = 0
    executions_without_pool_run: int = 0
    executions_already_normalized: int = 0
    executions_updated: int = 0
    tenant_linked: int = 0
    tenant_corrected: int = 0
    consumer_corrected: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "executions_scanned": self.executions_scanned,
            "executions_with_pool_run_id": self.executions_with_pool_run_id,
            "executions_invalid_pool_run_id": self.executions_invalid_pool_run_id,
            "executions_without_pool_run": self.executions_without_pool_run,
            "executions_already_normalized": self.executions_already_normalized,
            "executions_updated": self.executions_updated,
            "tenant_linked": self.tenant_linked,
            "tenant_corrected": self.tenant_corrected,
            "consumer_corrected": self.consumer_corrected,
        }


def _parse_pool_run_id(raw_pool_run_id: object) -> UUID | None:
    token = str(raw_pool_run_id or "").strip()
    if not token:
        return None
    try:
        return UUID(token)
    except (TypeError, ValueError, AttributeError):
        return None


def run_workflow_execution_pools_tenant_backfill() -> WorkflowExecutionPoolsTenantBackfillStats:
    stats = WorkflowExecutionPoolsTenantBackfillStats()
    pool_run_tenant_by_id = {
        pool_run_id: tenant_id
        for pool_run_id, tenant_id in PoolRun.objects.values_list("id", "tenant_id")
    }

    executions = WorkflowExecution.objects.order_by("id")
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

        expected_tenant_id = pool_run_tenant_by_id.get(pool_run_id)
        if expected_tenant_id is None:
            stats.executions_without_pool_run += 1
            continue

        update_fields: list[str] = []
        if execution.tenant_id != expected_tenant_id:
            if execution.tenant_id is None:
                stats.tenant_linked += 1
            else:
                stats.tenant_corrected += 1
            execution.tenant_id = expected_tenant_id
            update_fields.append("tenant")

        if execution.execution_consumer != "pools":
            stats.consumer_corrected += 1
            execution.execution_consumer = "pools"
            update_fields.append("execution_consumer")

        if not update_fields:
            stats.executions_already_normalized += 1
            continue

        execution.save(update_fields=update_fields)
        stats.executions_updated += 1

    return stats
