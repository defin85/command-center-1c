"""
URL configuration for API v2.

Action-based routing pattern: /{resource}/{action}/
All endpoints require authentication.
"""

from django.urls import path

from .views import (
    databases,
    clusters,
    extensions,
    extensions_flags_policy,
    extensions_manual_operation_bindings,
    extensions_plan_apply,
    operations,
    workflows,
    system,
    runtime_control,
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
    tenants,
    snapshots,
    mappings,
    ui,
    driver_catalogs,
    operation_catalog,
    decisions,
    pool_document_policy_migrations,
    intercompany_pools,
    intercompany_pools_binding_profiles,
    intercompany_pools_topology_templates,
    intercompany_pools_master_data,
    intercompany_pools_master_data_bootstrap,
    intercompany_pools_master_data_sync,
)

app_name = 'api_v2'

urlpatterns = [
    # ========================================================================
    # System
    # ========================================================================
    path('system/health/', system.SystemHealthView.as_view(), name='system-health'),
    path('system/config/', system.system_config, name='system-config'),
    path('system/me/', system.system_me, name='system-me'),
    path('system/bootstrap/', system.system_bootstrap, name='system-bootstrap'),
    path(
        'system/runtime-control/catalog/',
        runtime_control.list_runtime_control_catalog,
        name='system-runtime-control-catalog',
    ),
    path(
        'system/runtime-control/runtimes/<str:runtime_id>/',
        runtime_control.get_runtime_control_runtime,
        name='system-runtime-control-runtime',
    ),
    path(
        'system/runtime-control/runtimes/<str:runtime_id>/actions/',
        runtime_control.list_runtime_control_actions,
        name='system-runtime-control-actions',
    ),
    path(
        'system/runtime-control/runtimes/<str:runtime_id>/desired-state/',
        runtime_control.patch_runtime_control_desired_state,
        name='system-runtime-control-desired-state',
    ),
    path(
        'system/runtime-control/actions/',
        runtime_control.create_runtime_control_action,
        name='system-runtime-control-action-create',
    ),
    path(
        'system/runtime-control/actions/<str:action_id>/',
        runtime_control.get_runtime_control_action,
        name='system-runtime-control-action',
    ),
    path(
        'system/runtime-control/scheduler/jobs/',
        runtime_control.list_runtime_control_scheduler_jobs,
        name='system-runtime-control-scheduler-jobs',
    ),

    # ========================================================================
    # UI Metadata
    # ========================================================================
    path('ui/action-catalog/', ui.get_legacy_action_catalog, name='ui-action-catalog-legacy'),
    path('ui/table-metadata/', ui.get_table_metadata, name='ui-table-metadata'),
    path('ui/operation-exposures/editor-hints/', ui.get_operation_exposure_editor_hints, name='ui-operation-exposure-editor-hints'),
    path('ui/execution-plan/preview/', ui.preview_execution_plan, name='ui-execution-plan-preview'),

    # ========================================================================
    # Databases
    # ========================================================================
    path('databases/list-databases/', databases.list_databases, name='list-databases'),
    path('databases/get-database/', databases.get_database, name='get-database'),
    path('databases/get-extensions-snapshot/', databases.get_extensions_snapshot, name='get-extensions-snapshot'),
    path('databases/get-metadata-management/', databases.get_metadata_management, name='get-metadata-management'),
    path('databases/update-credentials/', databases.update_database_credentials, name='update-database-credentials'),
    path('databases/update-dbms-metadata/', databases.update_dbms_metadata, name='update-dbms-metadata'),
    path('databases/update-ibcmd-connection-profile/', databases.update_ibcmd_connection_profile, name='update-ibcmd-connection-profile'),
    path('databases/reverify-configuration-profile/', databases.reverify_configuration_profile, name='reverify-configuration-profile'),
    path('databases/refresh-metadata-snapshot/', databases.refresh_metadata_snapshot, name='refresh-metadata-snapshot'),
    path('databases/list-ib-users/', databases.list_infobase_users, name='list-infobase-users'),
    path('databases/create-ib-user/', databases.create_infobase_user, name='create-infobase-user'),
    path('databases/update-ib-user/', databases.update_infobase_user, name='update-infobase-user'),
    path('databases/delete-ib-user/', databases.delete_infobase_user, name='delete-infobase-user'),
    path('databases/set-ib-user-password/', databases.set_infobase_user_password, name='set-infobase-user-password'),
    path('databases/reset-ib-user-password/', databases.reset_infobase_user_password, name='reset-infobase-user-password'),
    path('databases/list-dbms-users/', databases.list_dbms_users, name='list-dbms-users'),
    path('databases/create-dbms-user/', databases.create_dbms_user, name='create-dbms-user'),
    path('databases/update-dbms-user/', databases.update_dbms_user, name='update-dbms-user'),
    path('databases/delete-dbms-user/', databases.delete_dbms_user, name='delete-dbms-user'),
    path('databases/set-dbms-user-password/', databases.set_dbms_user_password, name='set-dbms-user-password'),
    path('databases/reset-dbms-user-password/', databases.reset_dbms_user_password, name='reset-dbms-user-password'),
    path('databases/health-check/', databases.health_check, name='database-health-check'),
    path('databases/bulk-health-check/', databases.bulk_health_check, name='bulk-health-check'),
    path('databases/set-status/', databases.set_status, name='set-status'),
    path('databases/stream-ticket/', databases.get_database_stream_ticket, name='database-stream-ticket'),
    path('databases/stream/', databases.database_stream, name='database-stream'),

    # ========================================================================
    # Extensions
    # ========================================================================
    path('extensions/overview/', extensions.get_extensions_overview, name='extensions-overview'),
    path('extensions/overview/databases/', extensions.get_extensions_overview_databases, name='extensions-overview-databases'),
    path('extensions/flags-policy/', extensions_flags_policy.list_extensions_flags_policy, name='extensions-flags-policy-list'),
    path('extensions/flags-policy/adopt/', extensions_flags_policy.adopt_extensions_flags_policy, name='extensions-flags-policy-adopt'),
    path('extensions/flags-policy/<str:extension_name>/', extensions_flags_policy.upsert_extensions_flags_policy, name='extensions-flags-policy-upsert'),
    path(
        'extensions/manual-operation-bindings/',
        extensions_manual_operation_bindings.list_manual_operation_bindings,
        name='extensions-manual-operation-bindings-list',
    ),
    path(
        'extensions/manual-operation-bindings/<str:manual_operation>/',
        extensions_manual_operation_bindings.manual_operation_binding_detail,
        name='extensions-manual-operation-bindings-detail',
    ),
    path('extensions/plan/', extensions_plan_apply.extensions_plan, name='extensions-plan'),
    path('extensions/apply/', extensions_plan_apply.extensions_apply, name='extensions-apply'),

    # ========================================================================
    # Snapshots
    # ========================================================================
    path('snapshots/list/', snapshots.list_snapshots, name='snapshots-list'),
    path('snapshots/get/', snapshots.get_snapshot, name='snapshots-get'),

    # ========================================================================
    # Tenant mappings (MVP)
    # ========================================================================
    path('mappings/get/', mappings.get_mapping_spec, name='mappings-get'),
    path('mappings/upsert/', mappings.upsert_mapping_spec, name='mappings-upsert'),
    path('mappings/preview/', mappings.preview_mapping, name='mappings-preview'),

    # ========================================================================
    # Decisions
    # ========================================================================
    path('decisions/', decisions.decisions_collection, name='decisions-collection'),
    path('decisions/<uuid:decision_id>/', decisions.decision_detail, name='decisions-detail'),

    # ========================================================================
    # Intercompany Pools
    # ========================================================================
    path('pools/', intercompany_pools.list_organization_pools, name='pools-list'),
    path('pools/upsert/', intercompany_pools.upsert_organization_pool, name='pools-upsert'),
    path(
        'pools/binding-profiles/',
        intercompany_pools_binding_profiles.binding_profiles_collection,
        name='pools-binding-profiles-collection',
    ),
    path(
        'pools/binding-profiles/<uuid:binding_profile_id>/',
        intercompany_pools_binding_profiles.binding_profile_detail,
        name='pools-binding-profiles-detail',
    ),
    path(
        'pools/binding-profiles/<uuid:binding_profile_id>/revisions/',
        intercompany_pools_binding_profiles.binding_profile_revisions,
        name='pools-binding-profiles-revisions',
    ),
    path(
        'pools/binding-profiles/<uuid:binding_profile_id>/deactivate/',
        intercompany_pools_binding_profiles.deactivate_binding_profile,
        name='pools-binding-profiles-deactivate',
    ),
    path(
        'pools/topology-templates/',
        intercompany_pools_topology_templates.topology_templates_collection,
        name='pools-topology-templates-collection',
    ),
    path(
        'pools/topology-templates/<uuid:topology_template_id>/revisions/',
        intercompany_pools_topology_templates.topology_template_revisions,
        name='pools-topology-templates-revisions',
    ),
    path(
        'pools/workflow-bindings/',
        intercompany_pools.list_pool_workflow_bindings,
        name='pools-workflow-bindings-list',
    ),
    path(
        'pools/workflow-bindings/upsert/',
        intercompany_pools.upsert_pool_workflow_binding,
        name='pools-workflow-bindings-upsert',
    ),
    path(
        'pools/workflow-bindings/preview/',
        intercompany_pools.preview_pool_workflow_binding,
        name='pools-workflow-bindings-preview',
    ),
    path(
        'pools/workflow-bindings/<str:binding_id>/',
        intercompany_pools.pool_workflow_binding_detail,
        name='pools-workflow-bindings-detail',
    ),
    path('pools/organizations/', intercompany_pools.list_organizations, name='pools-organizations-list'),
    path('pools/organizations/upsert/', intercompany_pools.upsert_organization, name='pools-organizations-upsert'),
    path('pools/organizations/sync/', intercompany_pools.sync_organizations_catalog, name='pools-organizations-sync'),
    path('pools/organizations/<uuid:organization_id>/', intercompany_pools.get_organization, name='pools-organizations-get'),
    path(
        'pools/master-data/registry/',
        intercompany_pools_master_data.inspect_master_data_registry,
        name='pools-master-data-registry',
    ),
    path(
        'pools/master-data/parties/',
        intercompany_pools_master_data.list_master_data_parties,
        name='pools-master-data-parties-list',
    ),
    path(
        'pools/master-data/parties/<uuid:id>/',
        intercompany_pools_master_data.get_master_data_party,
        name='pools-master-data-parties-get',
    ),
    path(
        'pools/master-data/parties/upsert/',
        intercompany_pools_master_data.upsert_master_data_party,
        name='pools-master-data-parties-upsert',
    ),
    path(
        'pools/master-data/items/',
        intercompany_pools_master_data.list_master_data_items,
        name='pools-master-data-items-list',
    ),
    path(
        'pools/master-data/items/<uuid:id>/',
        intercompany_pools_master_data.get_master_data_item,
        name='pools-master-data-items-get',
    ),
    path(
        'pools/master-data/items/upsert/',
        intercompany_pools_master_data.upsert_master_data_item,
        name='pools-master-data-items-upsert',
    ),
    path(
        'pools/master-data/contracts/',
        intercompany_pools_master_data.list_master_data_contracts,
        name='pools-master-data-contracts-list',
    ),
    path(
        'pools/master-data/contracts/<uuid:id>/',
        intercompany_pools_master_data.get_master_data_contract,
        name='pools-master-data-contracts-get',
    ),
    path(
        'pools/master-data/contracts/upsert/',
        intercompany_pools_master_data.upsert_master_data_contract,
        name='pools-master-data-contracts-upsert',
    ),
    path(
        'pools/master-data/tax-profiles/',
        intercompany_pools_master_data.list_master_data_tax_profiles,
        name='pools-master-data-tax-profiles-list',
    ),
    path(
        'pools/master-data/tax-profiles/<uuid:id>/',
        intercompany_pools_master_data.get_master_data_tax_profile,
        name='pools-master-data-tax-profiles-get',
    ),
    path(
        'pools/master-data/tax-profiles/upsert/',
        intercompany_pools_master_data.upsert_master_data_tax_profile,
        name='pools-master-data-tax-profiles-upsert',
    ),
    path(
        'pools/master-data/gl-accounts/',
        intercompany_pools_master_data.list_master_data_gl_accounts,
        name='pools-master-data-gl-accounts-list',
    ),
    path(
        'pools/master-data/gl-accounts/<uuid:id>/',
        intercompany_pools_master_data.get_master_data_gl_account,
        name='pools-master-data-gl-accounts-get',
    ),
    path(
        'pools/master-data/gl-accounts/upsert/',
        intercompany_pools_master_data.upsert_master_data_gl_account,
        name='pools-master-data-gl-accounts-upsert',
    ),
    path(
        'pools/master-data/gl-account-sets/',
        intercompany_pools_master_data.list_master_data_gl_account_sets,
        name='pools-master-data-gl-account-sets-list',
    ),
    path(
        'pools/master-data/gl-account-sets/<uuid:id>/',
        intercompany_pools_master_data.get_master_data_gl_account_set,
        name='pools-master-data-gl-account-sets-get',
    ),
    path(
        'pools/master-data/gl-account-sets/upsert/',
        intercompany_pools_master_data.upsert_master_data_gl_account_set,
        name='pools-master-data-gl-account-sets-upsert',
    ),
    path(
        'pools/master-data/gl-account-sets/<uuid:id>/publish/',
        intercompany_pools_master_data.publish_master_data_gl_account_set,
        name='pools-master-data-gl-account-sets-publish',
    ),
    path(
        'pools/master-data/bindings/',
        intercompany_pools_master_data.list_master_data_bindings,
        name='pools-master-data-bindings-list',
    ),
    path(
        'pools/master-data/bindings/<uuid:id>/',
        intercompany_pools_master_data.get_master_data_binding,
        name='pools-master-data-bindings-get',
    ),
    path(
        'pools/master-data/bindings/upsert/',
        intercompany_pools_master_data.upsert_master_data_binding,
        name='pools-master-data-bindings-upsert',
    ),
    path(
        'pools/master-data/sync-status/',
        intercompany_pools_master_data_sync.list_master_data_sync_status,
        name='pools-master-data-sync-status-list',
    ),
    path(
        'pools/master-data/bootstrap-collections/preflight/',
        intercompany_pools_master_data_bootstrap.preflight_pool_master_data_bootstrap_collection,
        name='pools-master-data-bootstrap-collections-preflight',
    ),
    path(
        'pools/master-data/bootstrap-collections/',
        intercompany_pools_master_data_bootstrap.pool_master_data_bootstrap_collections_endpoint,
        name='pools-master-data-bootstrap-collections',
    ),
    path(
        'pools/master-data/bootstrap-collections/<uuid:id>/',
        intercompany_pools_master_data_bootstrap.get_pool_master_data_bootstrap_collection_endpoint,
        name='pools-master-data-bootstrap-collections-get',
    ),
    path(
        'pools/master-data/bootstrap-import/preflight/',
        intercompany_pools_master_data_bootstrap.preflight_pool_master_data_bootstrap_import,
        name='pools-master-data-bootstrap-import-preflight',
    ),
    path(
        'pools/master-data/bootstrap-import/jobs/',
        intercompany_pools_master_data_bootstrap.pool_master_data_bootstrap_import_jobs_endpoint,
        name='pools-master-data-bootstrap-import-jobs',
    ),
    path(
        'pools/master-data/bootstrap-import/jobs/<uuid:id>/',
        intercompany_pools_master_data_bootstrap.get_pool_master_data_bootstrap_import_job_endpoint,
        name='pools-master-data-bootstrap-import-jobs-get',
    ),
    path(
        'pools/master-data/bootstrap-import/jobs/<uuid:id>/cancel/',
        intercompany_pools_master_data_bootstrap.cancel_pool_master_data_bootstrap_import_job_endpoint,
        name='pools-master-data-bootstrap-import-jobs-cancel',
    ),
    path(
        'pools/master-data/bootstrap-import/jobs/<uuid:id>/retry-failed-chunks/',
        intercompany_pools_master_data_bootstrap.retry_failed_pool_master_data_bootstrap_import_chunks_endpoint,
        name='pools-master-data-bootstrap-import-jobs-retry-failed-chunks',
    ),
    path(
        'pools/master-data/sync-conflicts/',
        intercompany_pools_master_data_sync.list_master_data_sync_conflicts,
        name='pools-master-data-sync-conflicts-list',
    ),
    path(
        'pools/master-data/sync-conflicts/<uuid:id>/retry/',
        intercompany_pools_master_data_sync.retry_master_data_sync_conflict_endpoint,
        name='pools-master-data-sync-conflicts-retry',
    ),
    path(
        'pools/master-data/sync-conflicts/<uuid:id>/reconcile/',
        intercompany_pools_master_data_sync.reconcile_master_data_sync_conflict_endpoint,
        name='pools-master-data-sync-conflicts-reconcile',
    ),
    path(
        'pools/master-data/sync-conflicts/<uuid:id>/resolve/',
        intercompany_pools_master_data_sync.resolve_master_data_sync_conflict_endpoint,
        name='pools-master-data-sync-conflicts-resolve',
    ),
    path(
        'pools/odata-metadata/catalog/',
        intercompany_pools.get_pool_odata_metadata_catalog,
        name='pools-odata-metadata-catalog-get',
    ),
    path(
        'pools/odata-metadata/catalog/refresh/',
        intercompany_pools.refresh_pool_odata_metadata_catalog,
        name='pools-odata-metadata-catalog-refresh',
    ),
    path(
        'pools/<uuid:pool_id>/topology-snapshot/upsert/',
        intercompany_pools.upsert_pool_topology_snapshot,
        name='pools-topology-snapshot-upsert',
    ),
    path(
        'pools/<uuid:pool_id>/topology-snapshots/',
        intercompany_pools.list_pool_topology_snapshots,
        name='pools-topology-snapshots-list',
    ),
    path('pools/<uuid:pool_id>/graph/', intercompany_pools.get_pool_graph, name='pools-graph'),
    path(
        'pools/<uuid:pool_id>/document-policy-migrations/',
        pool_document_policy_migrations.migrate_pool_edge_document_policy,
        name='pools-document-policy-migrations',
    ),
    path(
        'pools/factual/workspace/',
        intercompany_pools.get_pool_factual_workspace,
        name='pools-factual-workspace',
    ),
    path(
        'pools/factual/refresh/',
        intercompany_pools.refresh_pool_factual_workspace,
        name='pools-factual-refresh',
    ),
    path(
        'pools/factual/review-actions/',
        intercompany_pools.apply_pool_factual_review_action_view,
        name='pools-factual-review-actions',
    ),
    path('pools/batches/', intercompany_pools.list_or_create_pool_batches, name='pools-batches'),
    path('pools/runs/', intercompany_pools.create_pool_run, name='pools-run-create'),
    path('pools/runs/<uuid:run_id>/', intercompany_pools.get_pool_run, name='pools-run-get'),
    path(
        'pools/runs/<uuid:run_id>/confirm-publication/',
        intercompany_pools.confirm_pool_run_publication,
        name='pools-run-confirm-publication',
    ),
    path(
        'pools/runs/<uuid:run_id>/abort-publication/',
        intercompany_pools.abort_pool_run_publication,
        name='pools-run-abort-publication',
    ),
    path('pools/runs/<uuid:run_id>/report/', intercompany_pools.get_pool_run_report, name='pools-run-report'),
    path('pools/runs/<uuid:run_id>/retry/', intercompany_pools.retry_pool_run_failed, name='pools-run-retry'),
    path('pools/schema-templates/', intercompany_pools.list_or_create_schema_templates, name='pools-schema-templates'),
    path(
        'pools/schema-templates/<uuid:template_id>/',
        intercompany_pools.update_schema_template,
        name='pools-schema-templates-update',
    ),

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
    path('operations/list-command-shortcuts/', operations.list_driver_command_shortcuts, name='list-command-shortcuts'),
    path('operations/create-command-shortcut/', operations.create_driver_command_shortcut, name='create-command-shortcut'),
    path('operations/delete-command-shortcut/', operations.delete_driver_command_shortcut, name='delete-command-shortcut'),
    path('operations/execute/', operations.execute_operation, name='execute-operation'),
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
    path('artifacts/<uuid:artifact_id>/purge/', artifacts.purge_artifact, name='purge-artifact'),
    path('artifacts/<uuid:artifact_id>/versions/', artifacts.list_artifact_versions, name='list-artifact-versions'),
    path('artifacts/<uuid:artifact_id>/versions/upload/', artifacts.upload_artifact_version, name='upload-artifact-version'),
    path('artifacts/<uuid:artifact_id>/versions/<str:version>/download/', artifacts.download_artifact_version, name='download-artifact-version'),
    path('artifacts/<uuid:artifact_id>/aliases/', artifacts.list_artifact_aliases, name='list-artifact-aliases'),
    path('artifacts/<uuid:artifact_id>/aliases/upsert/', artifacts.upsert_artifact_alias, name='upsert-artifact-alias'),
    path('artifacts/purge-jobs/<uuid:job_id>/', artifacts.get_purge_job, name='get-artifact-purge-job'),

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
    path('rbac/list-users-with-roles/', rbac.list_users_with_roles, name='list-users-with-roles'),
    path('rbac/get-effective-access/', rbac.get_effective_access, name='get-effective-access'),
    path('rbac/list-roles/', rbac.list_roles, name='list-roles'),
    path('rbac/create-role/', rbac.create_role, name='create-role'),
    path('rbac/update-role/', rbac.update_role, name='update-role'),
    path('rbac/delete-role/', rbac.delete_role, name='delete-role'),
    path('rbac/list-capabilities/', rbac.list_capabilities, name='list-capabilities'),
    path('rbac/set-role-capabilities/', rbac.set_role_capabilities, name='set-role-capabilities'),
    path('rbac/get-user-roles/', rbac.get_user_roles, name='get-user-roles'),
    path('rbac/set-user-roles/', rbac.set_user_roles, name='set-user-roles'),
    path('rbac/list-admin-audit/', rbac.list_admin_audit, name='list-admin-audit'),
    path('rbac/ref-clusters/', rbac.ref_clusters, name='ref-clusters'),
    path('rbac/ref-databases/', rbac.ref_databases, name='ref-databases'),
    path('rbac/ref-operation-templates/', rbac.ref_operation_templates, name='ref-operation-templates'),
    path('rbac/ref-workflow-templates/', rbac.ref_workflow_templates, name='ref-workflow-templates'),
    path('rbac/ref-artifacts/', rbac.ref_artifacts, name='ref-artifacts'),
    path('rbac/list-cluster-group-permissions/', rbac.list_cluster_group_permissions, name='list-cluster-group-permissions'),
    path('rbac/grant-cluster-group-permission/', rbac.grant_cluster_group_permission, name='grant-cluster-group-permission'),
    path('rbac/revoke-cluster-group-permission/', rbac.revoke_cluster_group_permission, name='revoke-cluster-group-permission'),
    path('rbac/bulk-grant-cluster-group-permission/', rbac.bulk_grant_cluster_group_permission, name='bulk-grant-cluster-group-permission'),
    path('rbac/bulk-revoke-cluster-group-permission/', rbac.bulk_revoke_cluster_group_permission, name='bulk-revoke-cluster-group-permission'),
    path('rbac/list-database-group-permissions/', rbac.list_database_group_permissions, name='list-database-group-permissions'),
    path('rbac/grant-database-group-permission/', rbac.grant_database_group_permission, name='grant-database-group-permission'),
    path('rbac/revoke-database-group-permission/', rbac.revoke_database_group_permission, name='revoke-database-group-permission'),
    path('rbac/bulk-grant-database-group-permission/', rbac.bulk_grant_database_group_permission, name='bulk-grant-database-group-permission'),
    path('rbac/bulk-revoke-database-group-permission/', rbac.bulk_revoke_database_group_permission, name='bulk-revoke-database-group-permission'),
    path('rbac/list-operation-template-permissions/', rbac.list_operation_template_permissions, name='list-operation-template-permissions'),
    path('rbac/grant-operation-template-permission/', rbac.grant_operation_template_permission, name='grant-operation-template-permission'),
    path('rbac/revoke-operation-template-permission/', rbac.revoke_operation_template_permission, name='revoke-operation-template-permission'),
    path('rbac/list-operation-template-group-permissions/', rbac.list_operation_template_group_permissions, name='list-operation-template-group-permissions'),
    path('rbac/grant-operation-template-group-permission/', rbac.grant_operation_template_group_permission, name='grant-operation-template-group-permission'),
    path('rbac/revoke-operation-template-group-permission/', rbac.revoke_operation_template_group_permission, name='revoke-operation-template-group-permission'),
    path('rbac/bulk-grant-operation-template-group-permission/', rbac.bulk_grant_operation_template_group_permission, name='bulk-grant-operation-template-group-permission'),
    path('rbac/bulk-revoke-operation-template-group-permission/', rbac.bulk_revoke_operation_template_group_permission, name='bulk-revoke-operation-template-group-permission'),
    path('rbac/list-workflow-template-permissions/', rbac.list_workflow_template_permissions, name='list-workflow-template-permissions'),
    path('rbac/grant-workflow-template-permission/', rbac.grant_workflow_template_permission, name='grant-workflow-template-permission'),
    path('rbac/revoke-workflow-template-permission/', rbac.revoke_workflow_template_permission, name='revoke-workflow-template-permission'),
    path('rbac/list-workflow-template-group-permissions/', rbac.list_workflow_template_group_permissions, name='list-workflow-template-group-permissions'),
    path('rbac/grant-workflow-template-group-permission/', rbac.grant_workflow_template_group_permission, name='grant-workflow-template-group-permission'),
    path('rbac/revoke-workflow-template-group-permission/', rbac.revoke_workflow_template_group_permission, name='revoke-workflow-template-group-permission'),
    path('rbac/bulk-grant-workflow-template-group-permission/', rbac.bulk_grant_workflow_template_group_permission, name='bulk-grant-workflow-template-group-permission'),
    path('rbac/bulk-revoke-workflow-template-group-permission/', rbac.bulk_revoke_workflow_template_group_permission, name='bulk-revoke-workflow-template-group-permission'),
    path('rbac/list-artifact-permissions/', rbac.list_artifact_permissions, name='list-artifact-permissions'),
    path('rbac/grant-artifact-permission/', rbac.grant_artifact_permission, name='grant-artifact-permission'),
    path('rbac/revoke-artifact-permission/', rbac.revoke_artifact_permission, name='revoke-artifact-permission'),
    path('rbac/list-artifact-group-permissions/', rbac.list_artifact_group_permissions, name='list-artifact-group-permissions'),
    path('rbac/grant-artifact-group-permission/', rbac.grant_artifact_group_permission, name='grant-artifact-group-permission'),
    path('rbac/revoke-artifact-group-permission/', rbac.revoke_artifact_group_permission, name='revoke-artifact-group-permission'),
    path('rbac/bulk-grant-artifact-group-permission/', rbac.bulk_grant_artifact_group_permission, name='bulk-grant-artifact-group-permission'),
    path('rbac/bulk-revoke-artifact-group-permission/', rbac.bulk_revoke_artifact_group_permission, name='bulk-revoke-artifact-group-permission'),

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
    path('templates/sync-from-registry/', templates.sync_from_registry, name='sync-from-registry'),
    path('templates/pool-runtime-registry/', templates.inspect_pool_runtime_registry, name='templates-pool-runtime-registry'),

    # ========================================================================
    # Unified Operation Catalog
    # ========================================================================
    path('operation-catalog/definitions/', operation_catalog.list_operation_definitions, name='operation-catalog-definitions'),
    path('operation-catalog/definitions/<uuid:definition_id>/', operation_catalog.get_operation_definition, name='operation-catalog-definition-detail'),
    path('operation-catalog/exposures/', operation_catalog.list_operation_exposures, name='operation-catalog-exposures'),
    path('operation-catalog/exposures/<uuid:exposure_id>/', operation_catalog.delete_operation_exposure, name='operation-catalog-exposure-delete'),
    path('operation-catalog/exposures/<uuid:exposure_id>/publish/', operation_catalog.publish_operation_exposure, name='operation-catalog-exposure-publish'),
    path('operation-catalog/validate/', operation_catalog.validate_operation_exposure, name='operation-catalog-validate'),
    path('operation-catalog/migration-issues/', operation_catalog.list_operation_catalog_migration_issues, name='operation-catalog-migration-issues'),

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
    path('settings/runtime-effective/', runtime_settings.list_effective_runtime_settings, name='runtime-settings-effective'),
    path('settings/runtime-overrides/', runtime_settings.list_runtime_setting_overrides, name='runtime-settings-overrides'),
    path('settings/runtime-overrides/<str:key>/', runtime_settings.update_runtime_setting_override, name='runtime-settings-overrides-update'),

    # ========================================================================
    # Tenancy
    # ========================================================================
    path('tenants/list-my-tenants/', tenants.list_my_tenants, name='tenants-list-my-tenants'),
    path('tenants/set-active/', tenants.set_active_tenant, name='tenants-set-active'),

    # ========================================================================
    # Command Schemas Editor (SPA-primary administration)
    # ========================================================================
    path('settings/command-schemas/editor/', driver_catalogs.get_command_schemas_editor_view, name='command-schemas-editor'),
    path('settings/command-schemas/versions/', driver_catalogs.list_command_schema_versions, name='command-schemas-versions'),
    path('settings/command-schemas/validate/', driver_catalogs.validate_command_schemas, name='command-schemas-validate'),
    path('settings/command-schemas/preview/', driver_catalogs.preview_command_schemas, name='command-schemas-preview'),
    path('settings/command-schemas/diff/', driver_catalogs.diff_command_schemas, name='command-schemas-diff'),
    path('settings/command-schemas/audit/', driver_catalogs.list_command_schemas_audit, name='command-schemas-audit'),
    path('settings/command-schemas/base/update/', driver_catalogs.update_command_schemas_base, name='command-schemas-base-update'),
    path('settings/command-schemas/effective/update/', driver_catalogs.update_command_schemas_effective, name='command-schemas-effective-update'),
    path('settings/command-schemas/overrides/update/', driver_catalogs.update_command_schema_overrides, name='command-schemas-overrides-update'),
    path('settings/command-schemas/overrides/rollback/', driver_catalogs.rollback_command_schema_overrides, name='command-schemas-overrides-rollback'),
    path('settings/command-schemas/import-its/', driver_catalogs.import_its_command_schemas, name='command-schemas-import-its'),
    path('settings/command-schemas/promote/', driver_catalogs.promote_command_schemas_base, name='command-schemas-promote'),
]
