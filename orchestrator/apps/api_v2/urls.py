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
    system,
    service_mesh,
    audit,
    events,
    rbac,
    users,
    templates,
    files,
    artifacts,
    timeline,
    dlq,
    runtime_settings,
    ui,
    driver_catalogs,
)

app_name = 'api_v2'

urlpatterns = [
    # ========================================================================
    # System
    # ========================================================================
    path('system/health/', system.SystemHealthView.as_view(), name='system-health'),
    path('system/config/', system.system_config, name='system-config'),
    path('system/me/', system.system_me, name='system-me'),

    # ========================================================================
    # UI Metadata
    # ========================================================================
    path('ui/table-metadata/', ui.get_table_metadata, name='ui-table-metadata'),

    # ========================================================================
    # Databases
    # ========================================================================
    path('databases/list-databases/', databases.list_databases, name='list-databases'),
    path('databases/get-database/', databases.get_database, name='get-database'),
    path('databases/update-credentials/', databases.update_database_credentials, name='update-database-credentials'),
    path('databases/list-ib-users/', databases.list_infobase_users, name='list-infobase-users'),
    path('databases/create-ib-user/', databases.create_infobase_user, name='create-infobase-user'),
    path('databases/update-ib-user/', databases.update_infobase_user, name='update-infobase-user'),
    path('databases/delete-ib-user/', databases.delete_infobase_user, name='delete-infobase-user'),
    path('databases/set-ib-user-password/', databases.set_infobase_user_password, name='set-infobase-user-password'),
    path('databases/reset-ib-user-password/', databases.reset_infobase_user_password, name='reset-infobase-user-password'),
    path('databases/health-check/', databases.health_check, name='database-health-check'),
    path('databases/bulk-health-check/', databases.bulk_health_check, name='bulk-health-check'),
    path('databases/set-status/', databases.set_status, name='set-status'),
    path('databases/stream-ticket/', databases.get_database_stream_ticket, name='database-stream-ticket'),
    path('databases/stream/', databases.database_stream, name='database-stream'),

    # ========================================================================
    # Clusters
    # ========================================================================
    path('clusters/list-clusters/', clusters.list_clusters, name='list-clusters'),
    path('clusters/get-cluster/', clusters.get_cluster, name='get-cluster'),
    path('clusters/sync-cluster/', clusters.sync_cluster, name='sync-cluster'),
    path('clusters/create-cluster/', clusters.create_cluster, name='create-cluster'),
    path('clusters/update-cluster/', clusters.update_cluster, name='update-cluster'),
    path('clusters/update-credentials/', clusters.update_cluster_credentials, name='update-cluster-credentials'),
    path('clusters/delete-cluster/', clusters.delete_cluster, name='delete-cluster'),
    path('clusters/get-cluster-databases/', clusters.get_cluster_databases, name='get-cluster-databases'),
    path('clusters/reset-sync-status/', clusters.reset_sync_status, name='reset-sync-status'),
    path('clusters/discover-clusters/', clusters.discover_clusters, name='discover-clusters'),

    # ========================================================================
    # Operations
    # ========================================================================
    path('operations/list-operations/', operations.list_operations, name='list-operations'),
    path('operations/get-operation/', operations.get_operation, name='get-operation'),
    path('operations/catalog/', operations.get_operation_catalog, name='operations-catalog'),
    path('operations/cli-commands/', operations.get_cli_command_catalog, name='operations-cli-commands'),
    path('operations/driver-commands/', operations.get_driver_commands, name='operations-driver-commands'),
    path('operations/execute/', operations.execute_operation, name='execute-operation'),
    path('operations/execute-ibcmd/', operations.execute_ibcmd_operation, name='execute-ibcmd-operation'),
    path('operations/execute-ibcmd-cli/', operations.execute_ibcmd_cli_operation, name='execute-ibcmd-cli-operation'),
    path('operations/cancel-operation/', operations.cancel_operation, name='cancel-operation'),
    path('operations/stream-ticket/', operations.get_stream_ticket, name='stream-ticket'),
    path('operations/stream-status/', operations.get_stream_status, name='stream-status'),
    path('operations/stream-mux-status/', operations.get_stream_mux_status, name='stream-mux-status'),
    path('operations/stream-subscribe/', operations.subscribe_operation_streams, name='stream-subscribe'),
    path('operations/stream-unsubscribe/', operations.unsubscribe_operation_streams, name='stream-unsubscribe'),
    path('operations/stream-mux-ticket/', operations.get_mux_stream_ticket, name='stream-mux-ticket'),
    path('operations/stream-mux/', operations.operation_stream_mux, name='stream-mux'),
    path('operations/stream/', operations.operation_stream, name='operation-stream'),
    path('operations/get-operation-timeline/', timeline.get_operation_timeline, name='get-operation-timeline'),

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
    # Artifacts (v2 storage)
    # ========================================================================
    path('artifacts/', artifacts.list_artifacts, name='list-artifacts'),
    path('artifacts/create/', artifacts.create_artifact, name='create-artifact'),
    path('artifacts/<uuid:artifact_id>/', artifacts.delete_artifact, name='delete-artifact'),
    path('artifacts/<uuid:artifact_id>/restore/', artifacts.restore_artifact, name='restore-artifact'),
    path('artifacts/<uuid:artifact_id>/versions/', artifacts.list_artifact_versions, name='list-artifact-versions'),
    path('artifacts/<uuid:artifact_id>/versions/upload/', artifacts.upload_artifact_version, name='upload-artifact-version'),
    path('artifacts/<uuid:artifact_id>/versions/<str:version>/download/', artifacts.download_artifact_version, name='download-artifact-version'),
    path('artifacts/<uuid:artifact_id>/aliases/', artifacts.list_artifact_aliases, name='list-artifact-aliases'),
    path('artifacts/<uuid:artifact_id>/aliases/upsert/', artifacts.upsert_artifact_alias, name='upsert-artifact-alias'),

    # ========================================================================
    # RBAC (SPA-primary administration)
    # ========================================================================
    path('rbac/list-cluster-permissions/', rbac.list_cluster_permissions, name='list-cluster-permissions'),
    path('rbac/grant-cluster-permission/', rbac.grant_cluster_permission, name='grant-cluster-permission'),
    path('rbac/revoke-cluster-permission/', rbac.revoke_cluster_permission, name='revoke-cluster-permission'),
    path('rbac/list-database-permissions/', rbac.list_database_permissions, name='list-database-permissions'),
    path('rbac/grant-database-permission/', rbac.grant_database_permission, name='grant-database-permission'),
    path('rbac/revoke-database-permission/', rbac.revoke_database_permission, name='revoke-database-permission'),
    path('rbac/list-users/', rbac.list_users, name='list-users'),
    path('rbac/get-effective-access/', rbac.get_effective_access, name='get-effective-access'),

    # ========================================================================
    # Users (SPA-primary administration)
    # ========================================================================
    path('users/list/', users.list_users, name='users-list'),
    path('users/create/', users.create_user, name='users-create'),
    path('users/update/', users.update_user, name='users-update'),
    path('users/set-password/', users.set_user_password, name='users-set-password'),

    # ========================================================================
    # Templates
    # ========================================================================
    path('templates/list-templates/', templates.list_templates, name='list-templates'),
    path('templates/sync-from-registry/', templates.sync_from_registry, name='sync-from-registry'),
    path('templates/create-template/', templates.create_template, name='create-template'),
    path('templates/update-template/', templates.update_template, name='update-template'),
    path('templates/delete-template/', templates.delete_template, name='delete-template'),

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

    # ========================================================================
    # DLQ (SPA-primary administration)
    # ========================================================================
    path('dlq/list/', dlq.list_dlq, name='dlq-list'),
    path('dlq/get/', dlq.get_dlq, name='dlq-get'),
    path('dlq/retry/', dlq.retry_dlq, name='dlq-retry'),

    # ========================================================================
    # Runtime Settings (SPA-primary administration)
    # ========================================================================
    path('settings/runtime/', runtime_settings.list_runtime_settings, name='runtime-settings'),
    path('settings/runtime/<str:key>/', runtime_settings.update_runtime_setting, name='runtime-settings-update'),

    # ========================================================================
    # Driver Catalogs (SPA-primary administration)
    # ========================================================================
    path('settings/driver-catalogs/', driver_catalogs.list_driver_catalogs, name='driver-catalogs-list'),
    path('settings/driver-catalogs/get/', driver_catalogs.get_driver_catalog, name='driver-catalogs-get'),
    path('settings/driver-catalogs/update/', driver_catalogs.update_driver_catalog, name='driver-catalogs-update'),
    path('settings/driver-catalogs/import-its/', driver_catalogs.import_its_driver_catalog, name='driver-catalogs-import-its'),
    path('settings/driver-catalogs/promote/', driver_catalogs.promote_driver_catalog_base, name='driver-catalogs-promote'),
    path('settings/driver-catalogs/overrides/get/', driver_catalogs.get_driver_catalog_overrides, name='driver-catalogs-overrides-get'),
    path('settings/driver-catalogs/overrides/update/', driver_catalogs.update_driver_catalog_overrides, name='driver-catalogs-overrides-update'),
]
