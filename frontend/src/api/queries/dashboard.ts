/**
 * Dashboard data fetching with React Query.
 *
 * Fetches operations, databases, and clusters in parallel
 * and provides caching/refetch capabilities.
 */
import { useQuery } from '@tanstack/react-query'

import type { BatchOperation } from '../generated/model/batchOperation'
import type { Database } from '../generated/model/database'
import type { Cluster } from '../generated/model/cluster'
import type { DatabaseListResponse } from '../generated/model/databaseListResponse'
import { getV2 } from '../generated'

import { queryKeys } from './queryKeys'

// =============================================================================
// Raw Data Type (before statistics calculation)
// =============================================================================

export interface DashboardRawData {
  operations: BatchOperation[]
  databases: Database[]
  clusters: Cluster[]
}

// =============================================================================
// Fetch Function
// =============================================================================

const api = getV2()

async function fetchAllDatabases(signal?: AbortSignal): Promise<Database[]> {
  const limit = 1000
  let offset = 0
  const databases: Database[] = []
  let total: number | null = null

  while (total === null || databases.length < total) {
    const res: DatabaseListResponse = await api.getDatabasesListDatabases({ limit, offset }, { signal })
    const page = res.databases ?? []
    databases.push(...page)

    total = typeof res.total === 'number' ? res.total : databases.length
    const pageCount = typeof res.count === 'number' ? res.count : page.length
    offset += pageCount

    if (page.length === 0) return databases
    if (databases.length >= total) return databases
    if (page.length < limit) return databases
  }

  return databases
}

/**
 * Fetch all dashboard data in parallel.
 * Returns raw data for statistics calculation.
 */
export async function fetchDashboardData(
  signal?: AbortSignal
): Promise<DashboardRawData> {
  const [operationsRes, databases, clustersRes] = await Promise.all([
    api.getOperationsListOperations({ limit: 100 }, { signal }),
    fetchAllDatabases(signal),
    api.getClustersListClusters(undefined, { signal }),
  ])

  return {
    operations: operationsRes.operations || [],
    databases,
    clusters: clustersRes.clusters || [],
  }
}

// =============================================================================
// React Query Hook
// =============================================================================

export interface UseDashboardQueryOptions {
  /** Refetch interval in milliseconds (default: 30000) */
  refetchInterval?: number
  /** Enable/disable the query */
  enabled?: boolean
}

/**
 * React Query hook for dashboard data.
 *
 * Features:
 * - Auto-refetch every 30 seconds (configurable)
 * - Automatic AbortController handling
 * - Caching and background updates
 * - Error handling
 */
export function useDashboardQuery(options: UseDashboardQueryOptions = {}) {
  const { refetchInterval = 30000, enabled = true } = options

  return useQuery({
    queryKey: queryKeys.dashboard.stats,
    queryFn: ({ signal }) => fetchDashboardData(signal),
    refetchInterval,
    enabled,
    // Keep previous data while refetching (prevents loading flicker)
    placeholderData: (previousData) => previousData,
    // Retry failed requests
    retry: 1,
    // Don't refetch on window focus (we have interval)
    refetchOnWindowFocus: false,
  })
}
