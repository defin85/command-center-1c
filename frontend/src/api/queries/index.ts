import type { OperationFilters, DatabaseFilters, ClusterFilters, ArtifactFilters } from './types'

export const queryKeys = {
  operations: {
    all: ['operations'] as const,
    list: (filters?: OperationFilters) => [...queryKeys.operations.all, 'list', filters] as const,
    detail: (id: string) => [...queryKeys.operations.all, 'detail', id] as const,
  },
  databases: {
    all: ['databases'] as const,
    list: (filters?: DatabaseFilters) => [...queryKeys.databases.all, 'list', filters] as const,
    detail: (id: string) => [...queryKeys.databases.all, 'detail', id] as const,
    ibUsers: (filters?: { databaseId?: string; search?: string; limit?: number; offset?: number }) => (
      [...queryKeys.databases.all, 'ib-users', filters] as const
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
    effectiveAccess: (userId?: number) => [...queryKeys.rbac.all, 'effective-access', userId] as const,
    users: (filters?: { search?: string; limit?: number; offset?: number }) => (
      [...queryKeys.rbac.all, 'users', filters] as const
    ),
  },
  templates: {
    all: ['templates'] as const,
    list: (filters?: unknown) => [...queryKeys.templates.all, 'list', filters] as const,
  },
  me: {
    all: ['me'] as const,
    current: () => [...queryKeys.me.all, 'current'] as const,
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
  },
} as const

export type { OperationFilters, DatabaseFilters, ClusterFilters, ArtifactFilters } from './types'

// Re-export hooks for convenience
export { useDashboardQuery } from './dashboard'
export {
  useOperations,
  useOperation,
  useCancelOperation,
  fetchOperations,
  fetchOperation,
  cancelOperation,
} from './operations'

export { useOperationTemplates, useSyncTemplatesFromRegistry } from './templates'
export { useMe } from './me'
export { useDlqMessages, useRetryDlqMessage } from './dlq'
export { useTableMetadata } from './ui'
export {
  useInfobaseUsers,
  useCreateInfobaseUser,
  useUpdateInfobaseUser,
  useDeleteInfobaseUser,
} from './databases'
export {
  useArtifacts,
  useArtifactVersions,
  useArtifactAliases,
  useUpsertArtifactAlias,
  useDeleteArtifact,
  useRestoreArtifact,
} from './artifacts'
