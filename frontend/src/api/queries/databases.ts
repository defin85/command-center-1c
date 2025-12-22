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
import { App } from 'antd'

import { getV2 } from '../generated'
import type { BatchInstallResponse } from '../generated/model/batchInstallResponse'
import type { ClusterDatabasesResponse } from '../generated/model/clusterDatabasesResponse'
import type { Database } from '../generated/model/database'
import type { DatabaseDetailResponse } from '../generated/model/databaseDetailResponse'
import type { DatabaseListResponse } from '../generated/model/databaseListResponse'
import { apiClient } from '../client'
import type { SetDatabaseStatusRequest } from '../generated/model/setDatabaseStatusRequest'
import type { SetDatabaseStatusResponse } from '../generated/model/setDatabaseStatusResponse'
import {
  executeOperation,
  type RASOperationType,
  type ExecuteOperationRequest,
  type ExecuteOperationResponse,
} from '../operations'

import { queryKeys, type DatabaseFilters } from './index'

// Initialize API client (generated)
const api = getV2()

async function fetchAllDatabases(
  filters?: DatabaseFilters,
  signal?: AbortSignal
): Promise<Database[]> {
  const limit = 1000
  let offset = 0
  const databases: Database[] = []
  let total: number | null = null

  while (total === null || databases.length < total) {
    const res: DatabaseListResponse = await api.getDatabasesListDatabases(
      {
        limit,
        offset,
        status: filters?.status,
      },
      { signal }
    )
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
    const response: ClusterDatabasesResponse = await api.getClustersGetClusterDatabases(
      { cluster_id: filters.cluster_id, status: filters?.status },
      { signal }
    )
    return response.databases || []
  }

  return fetchAllDatabases(filters, signal)
}

/**
 * Fetch single database by ID.
 */
export async function fetchDatabase(
  id: string,
  signal?: AbortSignal
): Promise<Database | null> {
  const response: DatabaseDetailResponse = await api.getDatabasesGetDatabase({ database_id: id }, { signal })
  return response.database || null
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
  const { message } = App.useApp()

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
  message: string
  batch_id: string
  total: number
  queued: number
  skipped: number
}

export interface BulkHealthCheckParams {
  databaseIds: string[]
}

export interface HealthCheckOperationResponse {
  operation_id: string
  status: string
  total_tasks: number
  message: string
}

export interface SetDatabaseStatusParams {
  databaseIds: string[]
  status: SetDatabaseStatusRequest['status']
  reason?: string
}

function formatInstallExtensionMessage(result: BatchInstallResponse): string {
  const queued = result.queued ?? 0
  const skipped = result.skipped ?? 0
  return `Installation queued: ${queued}, skipped: ${skipped}`
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
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (
      params: InstallExtensionParams
    ): Promise<InstallExtensionResponse> => {
      const result = await api.postExtensionsBatchInstall({
        database_ids: [params.databaseId],
        extension_name: params.extensionName,
        extension_path: params.extensionPath,
      })

      return {
        message: formatInstallExtensionMessage(result),
        batch_id: result.batch_id,
        total: result.total ?? 1,
        queued: result.queued ?? 0,
        skipped: result.skipped ?? 0,
      }
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

export function useHealthCheckDatabase() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (databaseId: string): Promise<HealthCheckOperationResponse> => {
      const response = await apiClient.post<HealthCheckOperationResponse>(
        '/api/v2/databases/health-check/',
        { database_id: databaseId }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
    },
  })
}

export function useBulkHealthCheckDatabases() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: BulkHealthCheckParams): Promise<HealthCheckOperationResponse> => {
      const response = await apiClient.post<HealthCheckOperationResponse>(
        '/api/v2/databases/bulk-health-check/',
        { database_ids: params.databaseIds }
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
    },
  })
}

export function useSetDatabaseStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: SetDatabaseStatusParams): Promise<SetDatabaseStatusResponse> =>
      api.postDatabasesSetStatus({
        database_ids: params.databaseIds,
        status: params.status,
        reason: params.reason ?? '',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
    },
  })
}
