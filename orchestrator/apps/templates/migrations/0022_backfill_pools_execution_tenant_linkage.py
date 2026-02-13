from __future__ import annotations

from uuid import UUID

from django.db import migrations


def _parse_pool_run_id(raw_pool_run_id: object) -> UUID | None:
    token = str(raw_pool_run_id or "").strip()
    if not token:
        return None
    try:
        return UUID(token)
    except (TypeError, ValueError, AttributeError):
        return None


def backfill_workflow_execution_pools_tenant_linkage(apps, schema_editor):
    PoolRun = apps.get_model("intercompany_pools", "PoolRun")
    WorkflowExecution = apps.get_model("templates", "WorkflowExecution")

    pool_run_tenant_by_id = {
        pool_run_id: tenant_id
        for pool_run_id, tenant_id in PoolRun.objects.values_list("id", "tenant_id")
    }

    executions = WorkflowExecution.objects.order_by("id")
    for execution in executions.iterator():
        raw_pool_run_id = (
            execution.input_context.get("pool_run_id")
            if isinstance(execution.input_context, dict)
            else None
        )
        if raw_pool_run_id in (None, ""):
            continue
        pool_run_id = _parse_pool_run_id(raw_pool_run_id)
        if pool_run_id is None:
            continue

        expected_tenant_id = pool_run_tenant_by_id.get(pool_run_id)
        if expected_tenant_id is None:
            continue

        update_fields: list[str] = []
        if execution.tenant_id != expected_tenant_id:
            execution.tenant_id = expected_tenant_id
            update_fields.append("tenant")

        if execution.execution_consumer != "pools":
            execution.execution_consumer = "pools"
            update_fields.append("execution_consumer")

        if update_fields:
            execution.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("intercompany_pools", "0011_poolrun_workflow_link_backfill"),
        ("templates", "0021_workflow_execution_tenant_and_consumer"),
    ]

    operations = [
        migrations.RunPython(backfill_workflow_execution_pools_tenant_linkage, migrations.RunPython.noop),
    ]
