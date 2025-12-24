/**
 * Clusters API queries and mutations with React Query.
 *
 * Provides caching, automatic refetch, and optimistic updates
 * for cluster management operations.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { Cluster } from '../generated/model/cluster'
import type { ClusterListResponse } from '../generated/model/clusterListResponse'
import type { ClusterSyncResponse } from '../generated/model/clusterSyncResponse'
import type { DiscoverClustersRequest } from '../generated/model/discoverClustersRequest'
import type { DiscoverClustersResponse } from '../generated/model/discoverClustersResponse'
import type { ResetSyncStatusRequest } from '../generated/model/resetSyncStatusRequest'
import type { ResetSyncStatusResponse } from '../generated/model/resetSyncStatusResponse'
import type { SystemConfig } from '../generated/model/systemConfig'

import { apiClient } from '../client'
import { queryKeys } from './index'

// Initialize API client
const api = getV2()

// =============================================================================
// Types
// =============================================================================

// Cluster create/update uses the Cluster type without readonly fields
export type ClusterInput = Omit<
  Cluster,
  'id' | 'status_display' | 'last_sync' | 'databases_count' | 'created_at' | 'updated_at' | 'cluster_pwd_configured'
>
export type ClusterCredentialsUpdateRequest = {
  cluster_id: string
  username?: string
  password?: string
  reset?: boolean
}

export type ClusterCredentialsUpdateResponse = {
  cluster: Cluster
  message: string
}

// =============================================================================
// Fetch Functions
// =============================================================================

async function fetchClusters(): Promise<ClusterListResponse> {
  return api.getClustersListClusters()
}

async function fetchSystemConfig(): Promise<SystemConfig> {
  try {
    return api.getSystemConfig()
  } catch {
    // Use fallback defaults if config endpoint fails
    console.warn('Failed to load system config, using defaults')
    return {
      ras_default_server: 'localhost:1545',
      ras_adapter_url: 'http://localhost:8188',
    }
  }
}

// =============================================================================
// Query Hooks
// =============================================================================

/**
 * Fetch all clusters.
 * Auto-refetches on window focus and provides caching.
 */
export function useClusters() {
  return useQuery({
    queryKey: queryKeys.clusters.list(),
    queryFn: fetchClusters,
    select: (data) => data.clusters ?? [],
  })
}

/**
 * Fetch system configuration (RAS defaults).
 * Caches indefinitely as config rarely changes.
 */
export function useSystemConfig() {
  return useQuery({
    queryKey: ['system', 'config'] as const,
    queryFn: fetchSystemConfig,
    staleTime: Infinity, // Config rarely changes
    retry: false, // Use fallback on error
  })
}

// =============================================================================
// Mutation Hooks
// =============================================================================

/**
 * Create a new cluster.
 * Invalidates cluster list on success.
 */
export function useCreateCluster() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ClusterInput) => api.postClustersCreateCluster(data as Cluster),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.clusters.all })
    },
  })
}

/**
 * Update an existing cluster.
 * Invalidates cluster list on success.
 */
export function useUpdateCluster() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ClusterInput }) =>
      api.putClustersUpdateCluster(data as Cluster, { cluster_id: id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.clusters.all })
    },
  })
}

/**
 * Delete a cluster.
 * Invalidates cluster list on success.
 */
export function useDeleteCluster() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => api.delClustersDeleteCluster({ cluster_id: id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.clusters.all })
    },
  })
}

/**
 * Sync a cluster with RAS.
 * Invalidates cluster list after delay to allow async sync to complete.
 */
export function useSyncCluster() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string): Promise<ClusterSyncResponse> =>
      api.postClustersSyncCluster({ cluster_id: id }),
    onSuccess: () => {
      // Delay invalidation to allow async sync to complete
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: queryKeys.clusters.all })
      }, 1000)
    },
  })
}

/**
 * Reset sync status for a cluster (unstick).
 * Invalidates clusters list on success.
 */
export function useResetClusterSyncStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request?: ResetSyncStatusRequest): Promise<ResetSyncStatusResponse> =>
      api.postClustersResetSyncStatus(request ?? {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.clusters.all })
    },
  })
}

/**
 * Discover clusters on a RAS server.
 * Invalidates cluster list after delay to allow discovery to complete.
 */
export function useDiscoverClusters() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: DiscoverClustersRequest): Promise<DiscoverClustersResponse> =>
      api.postClustersDiscoverClusters(data),
    onSuccess: () => {
      // Delay invalidation to allow discovery to complete
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: queryKeys.clusters.all })
      }, 2000)
    },
  })
}

/**
 * Update cluster credentials (username/password) or reset them.
 */
export function useUpdateClusterCredentials() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: ClusterCredentialsUpdateRequest): Promise<ClusterCredentialsUpdateResponse> => {
      const response = await apiClient.post('/api/v2/clusters/update-credentials/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.clusters.all })
    },
  })
}
