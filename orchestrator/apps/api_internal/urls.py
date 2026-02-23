"""
URL configuration for Internal API v2.

Action-based API style consistent with public API v2.
All endpoints require X-Internal-Token authentication.

Prefix: /api/v2/internal/
"""

from django.urls import path

from . import views

app_name = 'api_internal'

urlpatterns = [
    # ========================================================================
    # Scheduler Job History
    # ========================================================================
    path(
        'start-scheduler-run',
        views.start_scheduler_run,
        name='start-scheduler-run'
    ),
    path(
        'complete-scheduler-run',
        views.complete_scheduler_run,
        name='complete-scheduler-run'
    ),

    # ========================================================================
    # Task Execution Log
    # ========================================================================
    path(
        'start-task',
        views.start_task,
        name='start-task'
    ),
    path(
        'complete-task',
        views.complete_task,
        name='complete-task'
    ),

    # ========================================================================
    # Database Operations
    # ========================================================================
    path(
        'get-database-cluster-info',
        views.get_database_cluster_info,
        name='get-database-cluster-info'
    ),
    path(
        'list-databases-for-health-check',
        views.list_databases_for_health_check,
        name='list-databases-for-health-check'
    ),
    path(
        'update-database-health',
        views.update_database_health,
        name='update-database-health'
    ),

    # ========================================================================
    # Cluster Operations
    # ========================================================================
    path(
        'update-cluster-health',
        views.update_cluster_health,
        name='update-cluster-health'
    ),

    # ========================================================================
    # Failed Events (Event Replay System)
    # ========================================================================
    path(
        'list-pending-failed-events',
        views.list_pending_failed_events,
        name='list-pending-failed-events'
    ),
    path(
        'mark-event-replayed',
        views.mark_event_replayed,
        name='mark-event-replayed'
    ),
    path(
        'mark-event-failed',
        views.mark_event_failed,
        name='mark-event-failed'
    ),
    path(
        'cleanup-failed-events',
        views.cleanup_failed_events,
        name='cleanup-failed-events'
    ),

    # ========================================================================
    # Templates (for Go Worker Template Engine)
    # ========================================================================
    path(
        'get-template',
        views.get_template,
        name='get-template'
    ),
    path(
        'render-template',
        views.render_template,
        name='render-template'
    ),

    # ========================================================================
    # Workflows (Go Workflow Engine)
    # ========================================================================
    path(
        'workflows/get-execution',
        views.get_workflow_execution,
        name='get-workflow-execution'
    ),
    path(
        'workflows/update-execution-status',
        views.update_workflow_execution_status,
        name='update-workflow-execution-status'
    ),
    path(
        'workflows/execute-pool-runtime-step',
        views.execute_pool_runtime_step_v2,
        name='execute-pool-runtime-step'
    ),
    # Legacy compatibility endpoints for worker history client.
    path(
        'workflow-executions/',
        views.legacy_workflow_executions_collection,
        name='legacy-workflow-executions'
    ),
    path(
        'workflow-executions/<uuid:execution_id>/',
        views.legacy_workflow_execution_detail,
        name='legacy-workflow-execution-detail'
    ),
    path(
        'workflow-transitions/',
        views.legacy_workflow_transitions_collection,
        name='legacy-workflow-transitions'
    ),

    # ========================================================================
    # Timeline (Operation Observability)
    # ========================================================================
    path(
        'get-operation-timeline',
        views.get_operation_timeline,
        name='get-operation-timeline'
    ),

    # ========================================================================
    # Artifacts (purge/TTL)
    # ========================================================================
    path(
        'artifacts/claim-purge-job',
        views.claim_artifact_purge_job,
        name='artifacts-claim-purge-job'
    ),
    path(
        'artifacts/update-purge-job',
        views.update_artifact_purge_job,
        name='artifacts-update-purge-job'
    ),
    path(
        'artifacts/complete-purge-job',
        views.complete_artifact_purge_job,
        name='artifacts-complete-purge-job'
    ),

    # ========================================================================
    # Runtime Settings
    # ========================================================================
    path(
        'runtime-settings',
        views.list_runtime_settings,
        name='runtime-settings'
    ),
]
