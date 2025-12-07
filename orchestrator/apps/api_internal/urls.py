"""
URL configuration for Internal API.

All endpoints require X-Internal-Token authentication.
Prefix: /api/internal/
"""

from django.urls import path

from . import views

app_name = 'api_internal'

urlpatterns = [
    # ========================================================================
    # Scheduler Job History
    # ========================================================================
    path(
        'scheduler/runs/start',
        views.scheduler_run_start,
        name='scheduler-run-start'
    ),
    path(
        'scheduler/runs/<int:run_id>/complete',
        views.scheduler_run_complete,
        name='scheduler-run-complete'
    ),

    # ========================================================================
    # Task Execution Log
    # ========================================================================
    path(
        'tasks/start',
        views.task_start,
        name='task-start'
    ),
    path(
        'tasks/<int:log_id>/complete',
        views.task_complete,
        name='task-complete'
    ),

    # ========================================================================
    # Database Credentials (for OData)
    # ========================================================================
    path(
        'databases/<str:database_id>/credentials',
        views.database_credentials,
        name='database-credentials'
    ),
    path(
        'databases/health-check-list/',
        views.DatabasesForHealthCheckView.as_view(),
        name='databases-health-check-list'
    ),

    # ========================================================================
    # Health Status Updates
    # ========================================================================
    path(
        'databases/<str:database_id>/health',
        views.database_health_update,
        name='database-health-update'
    ),
    path(
        'clusters/<uuid:cluster_id>/health',
        views.cluster_health_update,
        name='cluster-health-update'
    ),

    # ========================================================================
    # Failed Events (Event Replay System)
    # ========================================================================
    path(
        'failed-events/pending',
        views.failed_events_pending,
        name='failed-events-pending'
    ),
    path(
        'failed-events/<int:event_id>/replayed',
        views.failed_event_replayed,
        name='failed-event-replayed'
    ),
    path(
        'failed-events/<int:event_id>/failed',
        views.failed_event_failed,
        name='failed-event-failed'
    ),
    path(
        'failed-events/cleanup',
        views.failed_events_cleanup,
        name='failed-events-cleanup'
    ),
]
