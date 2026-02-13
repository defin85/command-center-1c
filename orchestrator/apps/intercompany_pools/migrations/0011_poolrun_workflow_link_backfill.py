from __future__ import annotations

from collections import defaultdict
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


def _resolve_candidate(
    *,
    run_tenant_id,
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    exact_tenant_candidates = [candidate for candidate in candidates if candidate.get("tenant_id") == run_tenant_id]
    if len(exact_tenant_candidates) == 1:
        return exact_tenant_candidates[0]
    if len(exact_tenant_candidates) > 1:
        return None

    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    if candidate.get("tenant_id") is None:
        return candidate
    return None


def backfill_pool_run_workflow_links(apps, schema_editor):
    PoolRun = apps.get_model("intercompany_pools", "PoolRun")
    WorkflowExecution = apps.get_model("templates", "WorkflowExecution")

    candidates_by_run_id: dict[UUID, list[dict[str, object]]] = defaultdict(list)
    executions = (
        WorkflowExecution.objects.filter(execution_consumer="pools")
        .select_related("workflow_template")
        .order_by("id")
    )

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
        candidates_by_run_id[pool_run_id].append(
            {
                "id": execution.id,
                "tenant_id": execution.tenant_id,
                "status": execution.status,
                "workflow_template_name": str(execution.workflow_template.name or "").strip(),
            }
        )

    runs = PoolRun.objects.filter(workflow_execution_id__isnull=True).order_by("id")
    for run in runs.iterator():
        candidates = candidates_by_run_id.get(run.id) or []
        if not candidates:
            continue
        selected_candidate = _resolve_candidate(
            run_tenant_id=run.tenant_id,
            candidates=candidates,
        )
        if selected_candidate is None:
            continue

        run.workflow_execution_id = selected_candidate["id"]
        run.workflow_status = str(selected_candidate.get("status") or "")
        run.execution_backend = "workflow_core"
        update_fields = ["workflow_execution_id", "workflow_status", "execution_backend", "updated_at"]

        candidate_template_name = str(selected_candidate.get("workflow_template_name") or "").strip()
        if candidate_template_name and not run.workflow_template_name:
            run.workflow_template_name = candidate_template_name
            update_fields.append("workflow_template_name")

        run.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("templates", "0021_workflow_execution_tenant_and_consumer"),
        ("intercompany_pools", "0010_poolruncommandoutbox"),
    ]

    operations = [
        migrations.RunPython(backfill_pool_run_workflow_links, migrations.RunPython.noop),
    ]
