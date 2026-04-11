export const governanceTiers = ['platform-governed', 'legacy-monitored', 'excluded']
export const routeStateTransports = ['none', 'search-params', 'path-params', 'mixed']
export const detailMobileFallbackKinds = ['none', 'drawer', 'dedicated-route', 'mixed']
export const compactMasterPaneModes = ['compact-selection']

/**
 * Checked-in route governance inventory for operator-facing frontend surfaces.
 *
 * `modulePath` points to the route-entry module used from `src/App.tsx`.
 * Redirect-only helper aliases keep `modulePath: null` and document the redirect target instead.
 */
export const routeGovernanceInventory = [
  {
    routePath: '/login',
    modulePath: 'src/pages/Login/Login.tsx',
    tier: 'excluded',
    exclusionReason: 'public-auth-route',
  },
  {
    routePath: '/forbidden',
    modulePath: 'src/pages/Forbidden/ForbiddenPage.tsx',
    tier: 'excluded',
    exclusionReason: 'public-forbidden-route',
  },
  {
    routePath: '/',
    modulePath: 'src/pages/Dashboard/Dashboard.tsx',
    tier: 'platform-governed',
    lintProfile: 'dashboard-route',
    workspaceKind: 'dashboard',
    stateTransport: 'none',
    detailMobileFallback: 'none',
  },
  {
    routePath: '/clusters',
    modulePath: 'src/pages/Clusters/Clusters.tsx',
    tier: 'platform-governed',
    lintProfile: 'clusters-route',
    workspaceKind: 'management-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/operations',
    modulePath: 'src/pages/Operations/OperationsPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'operations-route',
    workspaceKind: 'catalog-detail',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
    masterPaneGovernance: {
      mode: 'compact-selection',
      reason: 'Operations route master pane must stay a compact operation catalog; dense telemetry grids belong in inspect, timeline, and dedicated secondary surfaces.',
    },
  },
  {
    routePath: '/artifacts',
    modulePath: 'src/pages/Artifacts/ArtifactsPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'privileged-workspace-route',
    workspaceKind: 'catalog-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/databases',
    modulePath: 'src/pages/Databases/Databases.tsx',
    tier: 'platform-governed',
    lintProfile: 'databases-route',
    workspaceKind: 'catalog-detail',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
    masterPaneGovernance: {
      mode: 'compact-selection',
      reason: 'Databases route master pane must stay a compact database catalog; bulk-heavy controls and metadata-dense layouts belong in detail-owned management surfaces.',
    },
  },
  {
    routePath: '/extensions',
    modulePath: 'src/pages/Extensions/Extensions.tsx',
    tier: 'platform-governed',
    lintProfile: 'privileged-workspace-route',
    workspaceKind: 'management-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/installation-monitor',
    modulePath: null,
    tier: 'excluded',
    exclusionReason: 'legacy-route-alias',
    redirectTarget: '/operations?tab=list',
  },
  {
    routePath: '/operation-monitor',
    modulePath: null,
    tier: 'excluded',
    exclusionReason: 'legacy-route-alias',
    redirectTarget: '/operations?tab=monitor',
  },
  {
    routePath: '/system-status',
    modulePath: 'src/pages/SystemStatus/SystemStatus.tsx',
    tier: 'platform-governed',
    lintProfile: 'observability-route',
    workspaceKind: 'diagnostics-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/workflows',
    modulePath: 'src/pages/Workflows/WorkflowList.tsx',
    tier: 'platform-governed',
    lintProfile: 'workflow-list-route',
    workspaceKind: 'catalog-detail',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
    masterPaneGovernance: {
      mode: 'compact-selection',
      reason: 'Workflow library master pane must stay a compact workflow selection catalog; dense diagnostics and primary handoff actions belong in the detail pane or explicit route handoff.',
    },
  },
  {
    routePath: '/workflows/executions',
    modulePath: 'src/pages/Workflows/WorkflowExecutions.tsx',
    tier: 'platform-governed',
    lintProfile: 'workflow-executions-route',
    workspaceKind: 'catalog-detail',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
    masterPaneGovernance: {
      mode: 'compact-selection',
      reason: 'Workflow executions master pane must stay a compact execution catalog; richer node telemetry, cancellation, and workflow handoff belong in the detail pane or execution monitor route.',
    },
  },
  {
    routePath: '/workflows/new',
    modulePath: 'src/pages/Workflows/WorkflowDesigner.tsx',
    tier: 'platform-governed',
    lintProfile: 'workflow-designer-route',
    workspaceKind: 'authoring-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'mixed',
  },
  {
    routePath: '/workflows/:id',
    modulePath: 'src/pages/Workflows/WorkflowDesigner.tsx',
    tier: 'platform-governed',
    lintProfile: 'workflow-designer-route',
    workspaceKind: 'authoring-workspace',
    stateTransport: 'mixed',
    detailMobileFallback: 'mixed',
  },
  {
    routePath: '/workflows/executions/:executionId',
    modulePath: 'src/pages/Workflows/WorkflowMonitor.tsx',
    tier: 'platform-governed',
    lintProfile: 'workflow-monitor-route',
    workspaceKind: 'diagnostics-workspace',
    stateTransport: 'mixed',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/templates',
    modulePath: 'src/pages/Templates/TemplatesPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'templates-route',
    workspaceKind: 'catalog-detail',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
    masterPaneGovernance: {
      mode: 'compact-selection',
      reason: 'Templates route master pane must stay a compact template catalog; provenance, publish posture, and richer execution contract belong in the detail pane or dedicated secondary surfaces.',
    },
  },
  {
    routePath: '/decisions',
    modulePath: 'src/pages/Decisions/DecisionsPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'canonical-page-route',
    workspaceKind: 'catalog-detail',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/pools/templates',
    modulePath: 'src/pages/Pools/PoolSchemaTemplatesPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'pool-schema-templates-route',
    workspaceKind: 'catalog-detail',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/pools/catalog',
    modulePath: 'src/pages/Pools/PoolCatalogPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'pool-catalog-route',
    workspaceKind: 'task-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/pools/topology-templates',
    modulePath: 'src/pages/Pools/PoolTopologyTemplatesPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'topology-templates-route',
    workspaceKind: 'catalog-detail',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
    masterPaneGovernance: {
      mode: 'compact-selection',
      reason: 'Topology templates route master pane must stay a compact reusable template catalog; revision lineage and structural summary belong in the detail pane.',
    },
  },
  {
    routePath: '/pools/execution-packs',
    modulePath: 'src/pages/Pools/PoolBindingProfilesPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'canonical-page-route',
    workspaceKind: 'catalog-detail',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/pools/master-data',
    modulePath: 'src/pages/Pools/PoolMasterDataPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'pool-master-data-route',
    workspaceKind: 'multi-zone-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/pools/factual',
    modulePath: 'src/pages/Pools/PoolFactualPage.tsx',
    tier: 'legacy-monitored',
  },
  {
    routePath: '/pools/runs',
    modulePath: 'src/pages/Pools/PoolRunsPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'pool-runs-route',
    workspaceKind: 'stage-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/service-mesh',
    modulePath: 'src/pages/ServiceMesh/ServiceMeshPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'observability-route',
    workspaceKind: 'realtime-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/rbac',
    modulePath: 'src/pages/RBAC/RBACPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'privileged-workspace-route',
    workspaceKind: 'governance-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/users',
    modulePath: 'src/pages/Users/UsersPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'privileged-workspace-route',
    workspaceKind: 'catalog-detail',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/dlq',
    modulePath: 'src/pages/DLQ/DLQPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'privileged-workspace-route',
    workspaceKind: 'remediation-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/settings/runtime',
    modulePath: 'src/pages/Settings/RuntimeSettingsPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'privileged-workspace-route',
    workspaceKind: 'settings-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/settings/driver-catalogs',
    modulePath: null,
    tier: 'excluded',
    exclusionReason: 'redirect-alias-to-command-schemas',
    redirectTarget: '/settings/command-schemas?mode=raw',
  },
  {
    routePath: '/settings/command-schemas',
    modulePath: 'src/pages/CommandSchemas/CommandSchemasPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'privileged-workspace-route',
    workspaceKind: 'authoring-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
  {
    routePath: '/settings/timeline',
    modulePath: 'src/pages/Settings/TimelineSettingsPage.tsx',
    tier: 'platform-governed',
    lintProfile: 'privileged-workspace-route',
    workspaceKind: 'settings-workspace',
    stateTransport: 'search-params',
    detailMobileFallback: 'drawer',
  },
]

/**
 * Checked-in inventory for shell-backed authoring surfaces that use platform form shells.
 *
 * Entries are file-based because a single module may own several shell lifecycles,
 * while governance currently applies at the module level.
 */
export const shellSurfaceGovernanceInventory = [
  {
    filePath: 'src/components/clusters/DiscoverClustersModal.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/clusters'],
  },
  {
    filePath: 'src/pages/Artifacts/ArtifactDetailsDrawer.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/artifacts'],
  },
  {
    filePath: 'src/pages/Artifacts/ArtifactsCreateModal.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/artifacts'],
  },
  {
    filePath: 'src/pages/Artifacts/ArtifactsPurgeModal.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/artifacts'],
  },
  {
    filePath: 'src/pages/Databases/components/DatabaseCredentialsModal.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/databases'],
  },
  {
    filePath: 'src/pages/Databases/components/DatabaseDbmsMetadataModal.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/databases'],
  },
  {
    filePath: 'src/pages/Databases/components/DatabaseIbcmdConnectionProfileModal.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/databases'],
  },
  {
    filePath: 'src/pages/Databases/components/DatabaseMetadataManagementDrawer.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/databases'],
  },
  {
    filePath: 'src/pages/Databases/components/ExtensionsDrawer.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/databases'],
  },
  {
    filePath: 'src/components/service-mesh/OperationTimelineDrawer.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/service-mesh'],
  },
  {
    filePath: 'src/components/service-mesh/ServiceDetailDrawer.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/service-mesh'],
  },
  {
    filePath: 'src/pages/Decisions/DecisionsPage.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/decisions'],
  },
  {
    filePath: 'src/pages/DLQ/DLQPage.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/dlq'],
  },
  {
    filePath: 'src/pages/Extensions/Extensions.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/extensions'],
  },
  {
    filePath: 'src/pages/Templates/TemplateOperationExposureEditorModal.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/templates'],
  },
  {
    filePath: 'src/pages/Pools/masterData/GLAccountsTab.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/pools/master-data'],
  },
  {
    filePath: 'src/pages/Pools/masterData/GLAccountSetsTab.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/pools/master-data'],
  },
  {
    filePath: 'src/pages/Pools/masterData/SyncLaunchDrawer.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/pools/master-data'],
  },
  {
    filePath: 'src/pages/Pools/PoolBatchIntakeDrawer.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/pools/runs'],
  },
  {
    filePath: 'src/pages/Pools/PoolBindingProfilesEditorModal.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/pools/execution-packs'],
  },
  {
    filePath: 'src/pages/Pools/PoolCatalogRouteCanvas.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/pools/catalog'],
  },
  {
    filePath: 'src/pages/Pools/PoolFactualReviewAttributeModal.tsx',
    tier: 'legacy-monitored',
    shellKinds: ['modal'],
    ownerRoutes: ['/pools/factual'],
  },
  {
    filePath: 'src/pages/Pools/PoolSchemaTemplatesPage.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/pools/templates'],
  },
  {
    filePath: 'src/pages/Pools/PoolTopologyTemplatesEditorDrawer.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/pools/topology-templates'],
  },
  {
    filePath: 'src/pages/Clusters/components/ClusterCredentialsModal.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/clusters'],
  },
  {
    filePath: 'src/pages/Clusters/components/ClusterUpsertModal.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/clusters'],
  },
  {
    filePath: 'src/pages/Settings/RuntimeSettingsPage.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/settings/runtime'],
  },
  {
    filePath: 'src/pages/SystemStatus/SystemStatus.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/system-status'],
  },
  {
    filePath: 'src/pages/Settings/TimelineSettingsPage.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer'],
    ownerRoutes: ['/settings/timeline'],
  },
  {
    filePath: 'src/pages/Users/UsersPage.tsx',
    tier: 'platform-governed',
    shellKinds: ['modal'],
    ownerRoutes: ['/users'],
  },
  {
    filePath: 'src/pages/Workflows/WorkflowDesigner.tsx',
    tier: 'platform-governed',
    shellKinds: ['drawer', 'modal'],
    ownerRoutes: ['/workflows/new', '/workflows/:id'],
  },
]

export const routeGovernancePathSet = new Set(routeGovernanceInventory.map((entry) => entry.routePath))
export const shellSurfaceFilePathSet = new Set(shellSurfaceGovernanceInventory.map((entry) => entry.filePath))

export const platformGovernedRouteInventory = routeGovernanceInventory.filter(
  (entry) => entry.tier === 'platform-governed'
)

export const compactMasterPaneRouteInventory = routeGovernanceInventory.filter(
  (entry) => entry.modulePath && entry.masterPaneGovernance?.mode === 'compact-selection'
)

export const platformGovernedRouteModulesByLintProfile = platformGovernedRouteInventory.reduce(
  (acc, entry) => {
    if (!entry.lintProfile || !entry.modulePath) {
      return acc
    }
    const files = acc[entry.lintProfile] ?? []
    files.push(entry.modulePath)
    acc[entry.lintProfile] = files
    return acc
  },
  {}
)

export function getRouteModulesByLintProfile(lintProfile) {
  return [...(platformGovernedRouteModulesByLintProfile[lintProfile] ?? [])].sort()
}

const compactMasterPaneGovernanceByModulePath = compactMasterPaneRouteInventory.reduce(
  (acc, entry) => {
    if (!entry.modulePath) {
      return acc
    }
    acc[entry.modulePath] = entry.masterPaneGovernance
    return acc
  },
  {}
)

export function getCompactMasterPaneGovernance(modulePath) {
  return compactMasterPaneGovernanceByModulePath[modulePath] ?? null
}
