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
)

app_name = 'api_v2'

urlpatterns = [
    # ========================================================================
    # System
    # ========================================================================
    path('system/health/', system.system_health, name='system-health'),

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

    # ========================================================================
    # Operations
    # ========================================================================
    path('operations/list-operations/', operations.list_operations, name='list-operations'),
    path('operations/get-operation/', operations.get_operation, name='get-operation'),
    path('operations/cancel-operation/', operations.cancel_operation, name='cancel-operation'),

    # ========================================================================
    # Workflows
    # ========================================================================
    path('workflows/list-workflows/', workflows.list_workflows, name='list-workflows'),
    path('workflows/get-workflow/', workflows.get_workflow, name='get-workflow'),
    path('workflows/execute-workflow/', workflows.execute_workflow, name='execute-workflow'),

    # ========================================================================
    # Extensions
    # ========================================================================
    path('extensions/list-extensions/', extensions.list_extensions, name='list-extensions'),
    path('extensions/get-install-status/', extensions.get_install_status, name='get-install-status'),
    path('extensions/retry-installation/', extensions.retry_installation, name='retry-installation'),

    # ========================================================================
    # Service Mesh
    # ========================================================================
    path('service-mesh/get-metrics/', service_mesh.get_metrics, name='get-metrics'),
]
