"""
Internal API v2 views for Go Worker communication.

Action-based API style consistent with public API v2.
All endpoints require X-Internal-Token authentication.

URL prefix: /api/v2/internal/
"""

from .views_artifacts import claim_artifact_purge_job, complete_artifact_purge_job, update_artifact_purge_job
from .views_clusters import update_cluster_health
from .views_databases import get_database_cluster_info, list_databases_for_health_check, update_database_health
from .views_failed_events import cleanup_failed_events, list_pending_failed_events, mark_event_failed, mark_event_replayed
from .views_runtime_settings import list_runtime_settings
from .views_scheduler import complete_scheduler_run, start_scheduler_run
from .views_tasks import complete_task, start_task
from .views_templates import get_template, render_template
from .views_timeline import get_operation_timeline
from .views_workflows import execute_pool_runtime_step_v2, get_workflow_execution, update_workflow_execution_status

__all__ = [
    "claim_artifact_purge_job",
    "cleanup_failed_events",
    "complete_artifact_purge_job",
    "complete_scheduler_run",
    "complete_task",
    "execute_pool_runtime_step_v2",
    "get_database_cluster_info",
    "get_operation_timeline",
    "get_template",
    "get_workflow_execution",
    "list_databases_for_health_check",
    "list_pending_failed_events",
    "list_runtime_settings",
    "mark_event_failed",
    "mark_event_replayed",
    "render_template",
    "start_scheduler_run",
    "start_task",
    "update_artifact_purge_job",
    "update_cluster_health",
    "update_database_health",
    "update_workflow_execution_status",
]
