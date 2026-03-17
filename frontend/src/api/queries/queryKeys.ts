import type { OperationFilters, DatabaseFilters, ClusterFilters, ArtifactFilters } from './types'

export const queryKeys = {
  commandShortcuts: {
    all: ['command-shortcuts'] as const,
    byDriver: (driver: string) => [...queryKeys.commandShortcuts.all, driver] as const,
  },
  driverCommands: {
    all: ['driver-commands'] as const,
    byDriver: (driver: string) => [...queryKeys.driverCommands.all, driver] as const,
  },
  operations: {
    all: ['operations'] as const,
    list: (filters?: OperationFilters) => [...queryKeys.operations.all, 'list', filters] as const,
    detail: (id: string) => [...queryKeys.operations.all, 'detail', id] as const,
  },
  databases: {
    all: ['databases'] as const,
    list: (filters?: DatabaseFilters) => [...queryKeys.databases.all, 'list', filters] as const,
    detail: (id: string) => [...queryKeys.databases.all, 'detail', id] as const,
    extensionsSnapshot: (id: string) => [...queryKeys.databases.all, 'extensions-snapshot', id] as const,
    metadataManagement: (id: string) => [...queryKeys.databases.all, 'metadata-management', id] as const,
    ibUsers: (filters?: { databaseId?: string; search?: string; limit?: number; offset?: number }) => (
      [...queryKeys.databases.all, 'ib-users', filters] as const
    ),
    dbmsUsers: (filters?: { databaseId?: string; search?: string; limit?: number; offset?: number }) => (
      [...queryKeys.databases.all, 'dbms-users', filters] as const
    ),
  },
  clusters: {
    all: ['clusters'] as const,
    list: (filters?: ClusterFilters) => [...queryKeys.clusters.all, 'list', filters] as const,
    detail: (id: string) => [...queryKeys.clusters.all, 'detail', id] as const,
  },
  rbac: {
    all: ['rbac'] as const,
    clusterPermissions: (filters?: unknown) => [...queryKeys.rbac.all, 'cluster', filters] as const,
    databasePermissions: (filters?: unknown) => [...queryKeys.rbac.all, 'database', filters] as const,
    operationTemplatePermissions: (filters?: unknown) => [...queryKeys.rbac.all, 'operation-template', filters] as const,
    workflowTemplatePermissions: (filters?: unknown) => [...queryKeys.rbac.all, 'workflow-template', filters] as const,
    artifactPermissions: (filters?: unknown) => [...queryKeys.rbac.all, 'artifact', filters] as const,
    effectiveAccess: (filters?: unknown) => [...queryKeys.rbac.all, 'effective-access', filters] as const,
    canManage: () => [...queryKeys.rbac.all, 'can-manage'] as const,
    users: (filters?: { search?: string; limit?: number; offset?: number }) => (
      [...queryKeys.rbac.all, 'users', filters] as const
    ),
    usersWithRoles: (filters?: { search?: string; role_id?: number; limit?: number; offset?: number }) => (
      [...queryKeys.rbac.all, 'users-with-roles', filters] as const
    ),
    roles: (filters?: { search?: string; limit?: number; offset?: number }) => (
      [...queryKeys.rbac.all, 'roles', filters] as const
    ),
    capabilities: () => [...queryKeys.rbac.all, 'capabilities'] as const,
    userRoles: (userId?: number) => [...queryKeys.rbac.all, 'user-roles', userId] as const,
    audit: (filters?: unknown) => [...queryKeys.rbac.all, 'audit', filters] as const,
    refs: {
      clusters: (filters?: unknown) => [...queryKeys.rbac.all, 'ref-clusters', filters] as const,
      databases: (filters?: unknown) => [...queryKeys.rbac.all, 'ref-databases', filters] as const,
      operationTemplates: (filters?: unknown) => [...queryKeys.rbac.all, 'ref-operation-templates', filters] as const,
      workflowTemplates: (filters?: unknown) => [...queryKeys.rbac.all, 'ref-workflow-templates', filters] as const,
      artifacts: (filters?: unknown) => [...queryKeys.rbac.all, 'ref-artifacts', filters] as const,
    },
    groupPermissions: {
      clusters: (filters?: unknown) => [...queryKeys.rbac.all, 'cluster-groups', filters] as const,
      databases: (filters?: unknown) => [...queryKeys.rbac.all, 'database-groups', filters] as const,
      operationTemplates: (filters?: unknown) => [...queryKeys.rbac.all, 'operation-template-groups', filters] as const,
      workflowTemplates: (filters?: unknown) => [...queryKeys.rbac.all, 'workflow-template-groups', filters] as const,
      artifacts: (filters?: unknown) => [...queryKeys.rbac.all, 'artifact-groups', filters] as const,
    },
  },
  templates: {
    all: ['templates'] as const,
    list: (filters?: unknown) => [...queryKeys.templates.all, 'list', filters] as const,
  },
  me: {
    all: ['me'] as const,
    current: () => [...queryKeys.me.all, 'current'] as const,
  },
  commandSchemas: {
    all: ['command-schemas'] as const,
    canManage: () => [...queryKeys.commandSchemas.all, 'can-manage'] as const,
  },
  dlq: {
    all: ['dlq'] as const,
    list: (filters?: unknown) => [...queryKeys.dlq.all, 'list', filters] as const,
  },
  dashboard: {
    stats: ['dashboard', 'stats'] as const,
  },
  artifacts: {
    all: ['artifacts'] as const,
    list: (filters?: ArtifactFilters) => [...queryKeys.artifacts.all, 'list', filters] as const,
    versions: (artifactId: string) => [...queryKeys.artifacts.all, 'versions', artifactId] as const,
    aliases: (artifactId: string) => [...queryKeys.artifacts.all, 'aliases', artifactId] as const,
    purgeJob: (jobId: string) => [...queryKeys.artifacts.all, 'purge-job', jobId] as const,
  },
  users: {
    all: ['users'] as const,
    list: (filters?: unknown) => [...queryKeys.users.all, 'list', filters] as const,
  },
  extensions: {
    all: ['extensions'] as const,
    overview: (filters?: unknown) => [...queryKeys.extensions.all, 'overview', filters] as const,
    overviewDatabases: (filters?: unknown) => [...queryKeys.extensions.all, 'overview-databases', filters] as const,
    manualOperationBindings: () => [...queryKeys.extensions.all, 'manual-operation-bindings'] as const,
  },
  tenants: {
    all: ['tenants'] as const,
    my: () => [...queryKeys.tenants.all, 'my'] as const,
  },
  poolBindingProfiles: {
    all: ['pool-binding-profiles'] as const,
    list: () => [...queryKeys.poolBindingProfiles.all, 'list'] as const,
    detail: (bindingProfileId: string) => [...queryKeys.poolBindingProfiles.all, 'detail', bindingProfileId] as const,
  },
} as const

export type { OperationFilters, DatabaseFilters, ClusterFilters, ArtifactFilters } from './types'
