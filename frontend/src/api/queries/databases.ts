/**
 * Databases data fetching with React Query.
 *
 * Provides hooks for:
 * - Fetching databases list (with optional cluster filtering)
 * - Fetching single database details
 * - Executing RAS operations on databases
 * - Installing extensions
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'

import { apiClient } from '../client'
import type { Database } from '../generated/model/database'
import type { Cluster } from '../generated/model/cluster'
import {
  executeOperation,
  type RASOperationType,
  type ExecuteOperationRequest,
  type ExecuteOperationResponse,
} from '../operations'

import { queryKeys, type DatabaseFilters } from './index'

// =============================================================================
// API Response Types
// =============================================================================

export interface DatabaseListResponse {
  databases?: Database[]
  count?: number
  total?: number
}

export interface ClusterDatabasesResponse {
  databases?: Database[]
  cluster?: Cluster
  count?: number
}

export interface DatabaseDetailResponse {
  database?: Database
}

// =============================================================================
// Fetch Functions
// =============================================================================

/**
 * Fetch all databases with optional filters.
 */
export async function fetchDatabases(
  filters?: DatabaseFilters,
  signal?: AbortSignal
): Promise<Database[]> {
  if (filters?.cluster_id) {
    // Fetch databases for a specific cluster
    const response = await apiClient.get<ClusterDatabasesResponse>(
      '/api/v2/clusters/get-cluster-databases/',
      {
        signal,
        params: { cluster_id: filters.cluster_id },
      }
    )
    return response.data.databases || []
  }

  // Fetch all databases
  const response = await apiClient.get<DatabaseListResponse>(
    '/api/v2/databases/list-databases/',
    {
      signal,
      params: filters?.status ? { status: filters.status } : undefined,
    }
  )
  return response.data.databases || []
}

/**
 * Fetch single database by ID.
 */
export async function fetchDatabase(
  id: string,
  signal?: AbortSignal
): Promise<Database | null> {
  const response = await apiClient.get<DatabaseDetailResponse>(
    '/api/v2/databases/get-database/',
    {
      signal,
      params: { database_id: id },
    }
  )
  return response.data.database || null
}

// =============================================================================
// Query Hooks
// =============================================================================

export interface UseDatabasesOptions {
  /** Filters for the query */
  filters?: DatabaseFilters
  /** Refetch interval in milliseconds (default: disabled) */
  refetchInterval?: number | false
  /** Enable/disable the query */
  enabled?: boolean
}

/**
 * React Query hook for fetching databases list.
 *
 * Features:
 * - Supports filtering by cluster_id and status
 * - Automatic AbortController handling
 * - Caching with queryKeys.databases.list
 */
export function useDatabases(options: UseDatabasesOptions = {}) {
  const { filters, refetchInterval = false, enabled = true } = options

  return useQuery({
    queryKey: queryKeys.databases.list(filters),
    queryFn: ({ signal }) => fetchDatabases(filters, signal),
    refetchInterval,
    enabled,
    placeholderData: (previousData) => previousData,
  })
}

export interface UseDatabaseOptions {
  /** Database ID */
  id: string
  /** Enable/disable the query */
  enabled?: boolean
}

/**
 * React Query hook for fetching single database details.
 */
export function useDatabase(options: UseDatabaseOptions) {
  const { id, enabled = true } = options

  return useQuery({
    queryKey: queryKeys.databases.detail(id),
    queryFn: ({ signal }) => fetchDatabase(id, signal),
    enabled: enabled && !!id,
  })
}

// =============================================================================
// Mutation Hooks
// =============================================================================

export interface ExecuteRasOperationParams {
  operationType: RASOperationType
  databaseIds: string[]
  config?: ExecuteOperationRequest['config']
}

/**
 * React Query mutation hook for executing RAS operations.
 *
 * Replaces useDatabaseActions hook with proper React Query integration.
 * Invalidates databases and operations queries on success.
 *
 * @example
 * ```tsx
 * const { mutate, isPending } = useExecuteRasOperation()
 *
 * mutate(
 *   { operationType: 'block_sessions', databaseIds: ['db-1', 'db-2'], config: { message: 'Maintenance' } },
 *   { onSuccess: (data) => console.log('Operation ID:', data.operation_id) }
 * )
 * ```
 */
export function useExecuteRasOperation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (
      params: ExecuteRasOperationParams
    ): Promise<ExecuteOperationResponse> => {
      const response = await executeOperation({
        operation_type: params.operationType,
        database_ids: params.databaseIds,
        config: params.config,
      })
      return response
    },
    onSuccess: (data) => {
      // Show success message
      message.success(data.message)

      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.operations.all })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Operation failed')
    },
  })
}

export interface InstallExtensionParams {
  databaseId: string
  extensionName: string
  extensionPath: string
}

export interface InstallExtensionResponse {
  task_id: string
  operation_id: string
  message: string
  status: string
  queued_count?: number
}

/**
 * React Query mutation hook for installing extension on a single database.
 *
 * @example
 * ```tsx
 * const { mutate, isPending } = useInstallExtension()
 *
 * mutate(
 *   { databaseId: 'db-1', extensionName: 'MyExt.cfe', extensionPath: '/path/to/ext.cfe' },
 *   { onSuccess: (data) => console.log('Operation ID:', data.operation_id) }
 * )
 * ```
 */
export function useInstallExtension() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (
      params: InstallExtensionParams
    ): Promise<InstallExtensionResponse> => {
      const response = await apiClient.post<InstallExtensionResponse>(
        '/api/v2/extensions/install-single/',
        {
          database_id: params.databaseId,
          extension_name: params.extensionName,
          extension_path: params.extensionPath,
        }
      )
      return response.data
    },
    onSuccess: () => {
      // Invalidate databases to refresh installation status
      queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to start installation')
    },
  })
}
