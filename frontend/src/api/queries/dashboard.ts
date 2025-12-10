/**
 * Dashboard data fetching with React Query.
 *
 * Fetches operations, databases, and clusters in parallel
 * and provides caching/refetch capabilities.
 */
import { useQuery } from '@tanstack/react-query'

import { apiClient } from '../client'
import type { BatchOperation } from '../generated/model/batchOperation'
import type { Database } from '../generated/model/database'
import type { Cluster } from '../generated/model/cluster'

import { queryKeys } from './index'

// =============================================================================
// API Response Types (v2 action-based API)
// =============================================================================

export interface OperationsResponse {
  operations?: BatchOperation[]
  count?: number
  total?: number
}

export interface DatabasesResponse {
  databases?: Database[]
  count?: number
  total?: number
}

export interface ClustersResponse {
  clusters?: Cluster[]
  count?: number
}

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

/**
 * Fetch all dashboard data in parallel.
 * Returns raw data for statistics calculation.
 */
export async function fetchDashboardData(
  signal?: AbortSignal
): Promise<DashboardRawData> {
  const [operationsRes, databasesRes, clustersRes] = await Promise.all([
    apiClient.get<OperationsResponse>('/api/v2/operations/list-operations/', {
      signal,
      params: { limit: 100 },
    }),
    apiClient.get<DatabasesResponse>('/api/v2/databases/list-databases/', {
      signal,
    }),
    apiClient.get<ClustersResponse>('/api/v2/clusters/list-clusters/', {
      signal,
    }),
  ])

  return {
    operations: operationsRes.data.operations || [],
    databases: databasesRes.data.databases || [],
    clusters: clustersRes.data.clusters || [],
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
