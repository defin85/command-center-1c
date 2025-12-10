"""
URL configuration for API v2.

Action-based routing pattern: /{resource}/{action}/
All endpoints require authentication.
"""

from django.urls import path

from .views import (
    databases,
    clusters,
    operations,
    workflows,
    extensions,
    system,
    service_mesh,
    audit,
    events,
    templates,
    files,
)

app_name = 'api_v2'

urlpatterns = [
    # ========================================================================
    # System
    # ========================================================================
    path('system/health/', system.system_health, name='system-health'),
    path('system/config/', system.system_config, name='system-config'),

    # ========================================================================
    # Databases
    # ========================================================================
    path('databases/list-databases/', databases.list_databases, name='list-databases'),
    path('databases/get-database/', databases.get_database, name='get-database'),
    path('databases/health-check/', databases.health_check, name='database-health-check'),
    path('databases/bulk-health-check/', databases.bulk_health_check, name='bulk-health-check'),

    # ========================================================================
    # Clusters
    # ========================================================================
    path('clusters/list-clusters/', clusters.list_clusters, name='list-clusters'),
    path('clusters/get-cluster/', clusters.get_cluster, name='get-cluster'),
    path('clusters/sync-cluster/', clusters.sync_cluster, name='sync-cluster'),
    path('clusters/create-cluster/', clusters.create_cluster, name='create-cluster'),
    path('clusters/update-cluster/', clusters.update_cluster, name='update-cluster'),
    path('clusters/delete-cluster/', clusters.delete_cluster, name='delete-cluster'),
    path('clusters/get-cluster-databases/', clusters.get_cluster_databases, name='get-cluster-databases'),
    path('clusters/reset-sync-status/', clusters.reset_sync_status, name='reset-sync-status'),
    path('clusters/discover-clusters/', clusters.discover_clusters, name='discover-clusters'),

    # ========================================================================
    # Operations
    # ========================================================================
    path('operations/list-operations/', operations.list_operations, name='list-operations'),
    path('operations/get-operation/', operations.get_operation, name='get-operation'),
    path('operations/execute/', operations.execute_operation, name='execute-operation'),
    path('operations/cancel-operation/', operations.cancel_operation, name='cancel-operation'),
    path('operations/stream-ticket/', operations.get_stream_ticket, name='stream-ticket'),
    path('operations/stream/', operations.operation_stream, name='operation-stream'),

    # ========================================================================
    # Workflows
    # ========================================================================
    path('workflows/list-workflows/', workflows.list_workflows, name='list-workflows'),
    path('workflows/get-workflow/', workflows.get_workflow, name='get-workflow'),
    path('workflows/execute-workflow/', workflows.execute_workflow, name='execute-workflow'),
    path('workflows/create-workflow/', workflows.create_workflow, name='create-workflow'),
    path('workflows/update-workflow/', workflows.update_workflow, name='update-workflow'),
    path('workflows/delete-workflow/', workflows.delete_workflow, name='delete-workflow'),
    path('workflows/validate-workflow/', workflows.validate_workflow, name='validate-workflow'),
    path('workflows/clone-workflow/', workflows.clone_workflow, name='clone-workflow'),

    # Workflow Executions (Phase 4)
    path('workflows/list-executions/', workflows.list_executions, name='list-executions'),
    path('workflows/get-execution/', workflows.get_execution, name='get-execution'),
    path('workflows/cancel-execution/', workflows.cancel_execution, name='cancel-execution'),
    path('workflows/get-execution-steps/', workflows.get_execution_steps, name='get-execution-steps'),

    # Workflow Templates for Operations Center (Phase 5.1)
    path('workflows/list-templates/', workflows.list_templates, name='list-workflow-templates'),
    path('workflows/get-template-schema/', workflows.get_template_schema, name='get-template-schema'),

    # ========================================================================
    # Extensions
    # ========================================================================
    path('extensions/list-extensions/', extensions.list_extensions, name='list-extensions'),
    path('extensions/get-install-status/', extensions.get_install_status, name='get-install-status'),
    path('extensions/retry-installation/', extensions.retry_installation, name='retry-installation'),
    path('extensions/batch-install/', extensions.batch_install, name='batch-install'),
    path('extensions/get-install-progress/', extensions.get_install_progress, name='get-install-progress'),
    # Extension Storage (migrated from v1)
    path('extensions/list-storage/', extensions.list_extension_storage, name='list-extension-storage'),
    path('extensions/upload-extension/', extensions.upload_extension, name='upload-extension'),
    path('extensions/delete-extension/', extensions.delete_extension_storage, name='delete-extension-storage'),

    # ========================================================================
    # Templates
    # ========================================================================
    path('templates/list-templates/', templates.list_templates, name='list-templates'),

    # ========================================================================
    # Service Mesh
    # ========================================================================
    path('service-mesh/get-metrics/', service_mesh.get_metrics, name='get-metrics'),
    path('service-mesh/get-history/', service_mesh.get_history, name='get-history'),

    # ========================================================================
    # Audit (Internal API for Go Worker)
    # ========================================================================
    path('audit/log-compensation/', audit.log_compensation, name='log-compensation'),

    # ========================================================================
    # Events (Internal API for failed event storage/replay)
    # ========================================================================
    path('events/store-failed/', events.store_failed_event, name='store-failed-event'),
    path('events/pending/', events.get_pending_events, name='get-pending-events'),

    # ========================================================================
    # Files (Phase 5.1)
    # ========================================================================
    path('files/upload/', files.upload_file, name='upload-file'),
    path('files/download/<uuid:file_id>/', files.download_file, name='download-file'),
    path('files/delete/<uuid:file_id>/', files.delete_file, name='delete-file'),
]
