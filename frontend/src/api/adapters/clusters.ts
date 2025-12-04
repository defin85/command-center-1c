/**
 * Clusters API Adapter.
 *
 * Bridges the gap between the old endpoint-based API and the new
 * generated API from OpenAPI specifications.
 *
 * This adapter:
 * 1. Uses customInstance (same as generated code) for API calls
 * 2. Provides the same function signatures as endpoints/clusters.ts
 * 3. Maps parameters to the v2 action-based endpoints
 *
 * Migration: endpoints/clusters.ts -> adapters/clusters.ts
 */

import { customInstance } from '../mutator'

// Re-export Database type from databases adapter
import type { Database } from './databases'
export type { Database }

// ============================================================================
// Types
// ============================================================================

export interface Cluster {
  id: string
  name: string
  description: string
  ras_server: string
  cluster_service_url: string
  cluster_user?: string
  status: 'active' | 'inactive' | 'error' | 'maintenance'
  status_display: string
  last_sync?: string
  metadata?: Record<string, unknown>
  databases_count?: number
  healthy_databases_count?: number
  created_at: string
  updated_at: string
}

export interface ClusterCreateRequest {
  name: string
  description?: string
  ras_server: string
  cluster_service_url: string
  cluster_user?: string
  cluster_pwd?: string
  status?: string
  metadata?: Record<string, unknown>
}

export interface ClusterUpdateRequest {
  name?: string
  description?: string
  ras_server?: string
  cluster_service_url?: string
  cluster_user?: string
  cluster_pwd?: string
  status?: string
  metadata?: Record<string, unknown>
}

export interface ClusterListResponse {
  clusters: Cluster[]
  count: number
}

export interface ClusterDetailResponse {
  cluster: Cluster
  databases?: unknown[]
  statistics?: {
    total_databases: number
    healthy_databases: number
    databases_by_status: Record<string, number>
  }
}

export interface ClusterSyncResponse {
  cluster_id: string
  status: string
  message: string
  databases_found?: number
}

export interface ClusterDatabasesResponse {
  cluster_id: string
  cluster_name: string
  databases: Database[]
  count: number
  filters?: {
    status?: string
    health_status?: string
  }
}

export interface ClusterDeleteResponse {
  message: string
  cluster_id: string
}

export interface ClusterMutationResponse {
  cluster: Cluster
  message: string
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List all clusters.
 * GET /api/v2/clusters/list-clusters/
 */
export const listClusters = async (params?: {
  status?: string
  ras_server?: string
}): Promise<Cluster[]> => {
  const response = await customInstance<ClusterListResponse>({
    url: '/api/v2/clusters/list-clusters/',
    method: 'GET',
    params,
  })
  return response.clusters ?? []
}

/**
 * Get a single cluster by ID.
 * GET /api/v2/clusters/get-cluster/?cluster_id=X
 */
export const getCluster = async (id: string): Promise<Cluster> => {
  const response = await customInstance<ClusterDetailResponse>({
    url: '/api/v2/clusters/get-cluster/',
    method: 'GET',
    params: { cluster_id: id },
  })
  return response.cluster
}

/**
 * Create a new cluster.
 * POST /api/v2/clusters/create-cluster/
 */
export const createCluster = async (data: ClusterCreateRequest): Promise<Cluster> => {
  const response = await customInstance<ClusterMutationResponse>({
    url: '/api/v2/clusters/create-cluster/',
    method: 'POST',
    data,
  })
  return response.cluster
}

/**
 * Update an existing cluster (full update).
 * PUT /api/v2/clusters/update-cluster/?cluster_id=X
 */
export const updateCluster = async (
  id: string,
  data: ClusterUpdateRequest
): Promise<Cluster> => {
  const response = await customInstance<ClusterMutationResponse>({
    url: '/api/v2/clusters/update-cluster/',
    method: 'PUT',
    params: { cluster_id: id },
    data,
  })
  return response.cluster
}

/**
 * Partially update an existing cluster.
 * POST /api/v2/clusters/update-cluster/?cluster_id=X
 */
export const patchCluster = async (
  id: string,
  data: ClusterUpdateRequest
): Promise<Cluster> => {
  const response = await customInstance<ClusterMutationResponse>({
    url: '/api/v2/clusters/update-cluster/',
    method: 'POST',
    params: { cluster_id: id },
    data,
  })
  return response.cluster
}

/**
 * Delete a cluster.
 * DELETE /api/v2/clusters/delete-cluster/?cluster_id=X
 */
export const deleteCluster = async (id: string, force = false): Promise<void> => {
  await customInstance<ClusterDeleteResponse>({
    url: '/api/v2/clusters/delete-cluster/',
    method: 'DELETE',
    params: { cluster_id: id },
    data: { force },
  })
}

/**
 * Trigger cluster synchronization with RAS.
 * POST /api/v2/clusters/sync-cluster/?cluster_id=X
 */
export const syncCluster = async (id: string): Promise<ClusterSyncResponse> => {
  return customInstance<ClusterSyncResponse>({
    url: '/api/v2/clusters/sync-cluster/',
    method: 'POST',
    params: { cluster_id: id },
  })
}

/**
 * Get databases for a specific cluster.
 * GET /api/v2/clusters/get-cluster-databases/?cluster_id=X
 */
export const getClusterDatabases = async (
  id: string,
  params?: {
    status?: string
    health_status?: string
  }
): Promise<Database[]> => {
  const response = await customInstance<ClusterDatabasesResponse>({
    url: '/api/v2/clusters/get-cluster-databases/',
    method: 'GET',
    params: { cluster_id: id, ...params },
  })
  return response.databases ?? []
}

/**
 * Reset sync status for stuck clusters.
 * POST /api/v2/clusters/reset-sync-status/
 */
export const resetSyncStatus = async (options?: {
  cluster_id?: string
  all?: boolean
}): Promise<{
  message: string
  reset_count: number
  clusters: Array<{ id: string; name: string; old_status: string }>
}> => {
  return customInstance({
    url: '/api/v2/clusters/reset-sync-status/',
    method: 'POST',
    params: options?.cluster_id ? { cluster_id: options.cluster_id } : undefined,
    data: options,
  })
}

// ============================================================================
// Legacy API object (for backward compatibility)
// ============================================================================

/**
 * @deprecated Use individual functions instead.
 * This object maintains backward compatibility with endpoints/clusters.ts
 */
export const clustersApi = {
  list: listClusters,
  get: getCluster,
  create: createCluster,
  update: updateCluster,
  patch: patchCluster,
  delete: deleteCluster,
  sync: syncCluster,
  getDatabases: getClusterDatabases,
  resetSyncStatus,
}

export default clustersApi
