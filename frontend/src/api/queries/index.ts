import type { OperationFilters, DatabaseFilters } from './types'

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
  },
  clusters: {
    all: ['clusters'] as const,
    list: () => [...queryKeys.clusters.all, 'list'] as const,
    detail: (id: string) => [...queryKeys.clusters.all, 'detail', id] as const,
  },
  dashboard: {
    stats: ['dashboard', 'stats'] as const,
  },
} as const

export type { OperationFilters, DatabaseFilters } from './types'

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
