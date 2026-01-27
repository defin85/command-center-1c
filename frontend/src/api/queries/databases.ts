/**
 * Databases data fetching with React Query.
 *
 * Provides hooks for:
 * - Fetching databases list (with optional cluster filtering)
 * - Fetching single database details
 * - Executing RAS operations on databases
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { App } from 'antd'

import { getV2 } from '../generated'
import type { Database } from '../generated/model/database'
import type { DatabaseDetailResponse } from '../generated/model/databaseDetailResponse'
import type { DatabaseExtensionsSnapshotResponse } from '../generated/model/databaseExtensionsSnapshotResponse'
import type { DatabaseListResponse } from '../generated/model/databaseListResponse'
import type { DbmsUserListResponse } from '../generated/model/dbmsUserListResponse'
import type { DbmsUserMapping } from '../generated/model/dbmsUserMapping'
import type { DbmsUserMappingCreate } from '../generated/model/dbmsUserMappingCreate'
import type { DbmsUserMappingUpdate } from '../generated/model/dbmsUserMappingUpdate'
import { apiClient } from '../client'
import type { SetDatabaseStatusRequest } from '../generated/model/setDatabaseStatusRequest'
import type { SetDatabaseStatusResponse } from '../generated/model/setDatabaseStatusResponse'
import {
  executeOperation,
  type RASOperationType,
  type ExecuteOperationRequest,
  type ExecuteOperationResponse,
} from '../operations'

import { queryKeys } from './queryKeys'
import type { DatabaseFilters } from './types'

// Initialize API client (generated)
const api = getV2()

// =============================================================================
// Fetch Functions
// =============================================================================

/**
 * Fetch all databases with optional filters.
 */
export async function fetchDatabases(
  filters?: DatabaseFilters,
  signal?: AbortSignal
): Promise<DatabaseListResponse> {
  const filtersParam = filters?.filters ? JSON.stringify(filters.filters) : undefined
  const sortParam = filters?.sort ? JSON.stringify(filters.sort) : undefined

  return api.getDatabasesListDatabases(
    {
      cluster_id: filters?.cluster_id,
      search: filters?.search,
      limit: filters?.limit,
      offset: filters?.offset,
      filters: filtersParam,
      sort: sortParam,
    },
    { signal }
  )
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

/**
 * Fetch latest known extensions snapshot for a database.
 */
export async function fetchDatabaseExtensionsSnapshot(
  id: string,
  signal?: AbortSignal
): Promise<DatabaseExtensionsSnapshotResponse> {
  return api.getDatabasesGetExtensionsSnapshot({ database_id: id }, { signal })
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

export type DatabaseCredentialsUpdateRequest = {
  database_id: string
  username?: string
  password?: string
  reset?: boolean
}

export type DatabaseCredentialsUpdateResponse = {
  database: Database
  message: string
}

export type InfobaseUserRef = {
  id: number
  username: string
}

export type InfobaseUserMapping = {
  id: number
  database_id: string
  user?: InfobaseUserRef | null
  ib_username: string
  ib_display_name?: string | null
  ib_roles: string[]
  ib_password_configured: boolean
  auth_type: 'local' | 'ad' | 'service' | 'other'
  is_service: boolean
  notes?: string
  created_at: string
  updated_at: string
}

export type InfobaseUserListResponse = {
  users: InfobaseUserMapping[]
  count: number
  total: number
}

export type InfobaseUserCreateRequest = {
  database_id: string
  user_id?: number | null
  ib_username: string
  ib_display_name?: string
  ib_roles?: string[]
  ib_password?: string
  auth_type?: InfobaseUserMapping['auth_type']
  is_service?: boolean
  notes?: string
}

export type InfobaseUserUpdateRequest = {
  id: number
  user_id?: number | null
  ib_username?: string
  ib_display_name?: string
  ib_roles?: string[]
  auth_type?: InfobaseUserMapping['auth_type']
  is_service?: boolean
  notes?: string
}

export type InfobaseUserDeleteRequest = {
  id: number
}

export type InfobaseUserDeleteParams = {
  id: number
  databaseId?: string
}

export type InfobaseUserPasswordSetRequest = {
  id: number
  password: string
}

export type InfobaseUsersQuery = {
  databaseId?: string
  search?: string
  authType?: 'local' | 'ad' | 'service' | 'other'
  isService?: boolean
  hasUser?: boolean
  limit?: number
  offset?: number
}

export type DbmsUsersQuery = {
  databaseId?: string
  search?: string
  authType?: 'local' | 'service' | 'other'
  isService?: boolean
  hasUser?: boolean
  limit?: number
  offset?: number
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

export interface UseDatabaseExtensionsSnapshotOptions {
  /** Database ID */
  id: string
  /** Enable/disable the query */
  enabled?: boolean
}

export function useDatabaseExtensionsSnapshot(options: UseDatabaseExtensionsSnapshotOptions) {
  const { id, enabled = true } = options

  return useQuery({
    queryKey: queryKeys.databases.extensionsSnapshot(id),
    queryFn: ({ signal }) => fetchDatabaseExtensionsSnapshot(id, signal),
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

/**
 * Update database OData credentials or reset them.
 */
export function useUpdateDatabaseCredentials() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: DatabaseCredentialsUpdateRequest): Promise<DatabaseCredentialsUpdateResponse> => {
      const response = await apiClient.post('/api/v2/databases/update-credentials/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
    },
  })
}

export function useInfobaseUsers(query: InfobaseUsersQuery) {
  return useQuery({
    queryKey: queryKeys.databases.ibUsers(query),
    queryFn: async ({ signal }): Promise<InfobaseUserListResponse> => {
      const response = await apiClient.get('/api/v2/databases/list-ib-users/', {
        params: {
          database_id: query.databaseId,
          search: query.search,
          auth_type: query.authType,
          is_service: query.isService,
          has_user: query.hasUser,
          limit: query.limit ?? 100,
          offset: query.offset ?? 0,
        },
        signal,
      })
      return response.data
    },
    enabled: Boolean(query.databaseId),
    placeholderData: (previousData) => previousData,
  })
}

export function useDbmsUsers(query: DbmsUsersQuery) {
  return useQuery({
    queryKey: queryKeys.databases.dbmsUsers(query),
    queryFn: async ({ signal }): Promise<DbmsUserListResponse> => {
      const response = await apiClient.get('/api/v2/databases/list-dbms-users/', {
        params: {
          database_id: query.databaseId,
          search: query.search,
          auth_type: query.authType,
          is_service: query.isService,
          has_user: query.hasUser,
          limit: query.limit ?? 100,
          offset: query.offset ?? 0,
        },
        signal,
      })
      return response.data
    },
    enabled: Boolean(query.databaseId),
    placeholderData: (previousData) => previousData,
  })
}

export function useCreateInfobaseUser() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: InfobaseUserCreateRequest): Promise<InfobaseUserMapping> => {
      const response = await apiClient.post('/api/v2/databases/create-ib-user/', payload)
      return response.data
    },
    onSuccess: (data) => {
      message.success(`Infobase user ${data.ib_username} created`)
      queryClient.invalidateQueries({
        queryKey: queryKeys.databases.ibUsers({ databaseId: data.database_id }),
      })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to create infobase user')
    },
  })
}

export type DbmsUserCreateRequest = Omit<DbmsUserMappingCreate, 'db_password'>

export function useCreateDbmsUser() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: DbmsUserCreateRequest): Promise<DbmsUserMapping> => {
      const response = await apiClient.post('/api/v2/databases/create-dbms-user/', payload)
      return response.data
    },
    onSuccess: (data) => {
      message.success(`DBMS user ${data.db_username} created`)
      queryClient.invalidateQueries({
        queryKey: queryKeys.databases.dbmsUsers({ databaseId: data.database_id }),
      })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to create DBMS user mapping')
    },
  })
}

export function useUpdateInfobaseUser() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: InfobaseUserUpdateRequest): Promise<InfobaseUserMapping> => {
      const response = await apiClient.post('/api/v2/databases/update-ib-user/', payload)
      return response.data
    },
    onSuccess: (data) => {
      message.success(`Infobase user ${data.ib_username} updated`)
      queryClient.invalidateQueries({
        queryKey: queryKeys.databases.ibUsers({ databaseId: data.database_id }),
      })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to update infobase user')
    },
  })
}

export function useUpdateDbmsUser() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: DbmsUserMappingUpdate): Promise<DbmsUserMapping> => {
      const response = await apiClient.post('/api/v2/databases/update-dbms-user/', payload)
      return response.data
    },
    onSuccess: (data) => {
      message.success(`DBMS user ${data.db_username} updated`)
      queryClient.invalidateQueries({
        queryKey: queryKeys.databases.dbmsUsers({ databaseId: data.database_id }),
      })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to update DBMS user mapping')
    },
  })
}

export function useDeleteInfobaseUser() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: InfobaseUserDeleteParams): Promise<{ message: string }> => {
      const response = await apiClient.post('/api/v2/databases/delete-ib-user/', { id: payload.id })
      return response.data
    },
    onSuccess: (_data, variables) => {
      message.success('Infobase user deleted')
      if (variables.databaseId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.databases.ibUsers({ databaseId: variables.databaseId }),
        })
      } else {
        queryClient.invalidateQueries({ queryKey: queryKeys.databases.ibUsers(undefined) })
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to delete infobase user')
    },
  })
}

export function useDeleteDbmsUser() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: { id: number; databaseId?: string }): Promise<void> => {
      await apiClient.post('/api/v2/databases/delete-dbms-user/', { id: payload.id })
    },
    onSuccess: (_data, variables) => {
      message.success('DBMS user mapping deleted')
      if (variables.databaseId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.databases.dbmsUsers({ databaseId: variables.databaseId }),
        })
      } else {
        queryClient.invalidateQueries({ queryKey: queryKeys.databases.dbmsUsers(undefined) })
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.databases.all })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to delete DBMS user mapping')
    },
  })
}

export function useSetInfobaseUserPassword() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: InfobaseUserPasswordSetRequest): Promise<InfobaseUserMapping> => {
      const response = await apiClient.post('/api/v2/databases/set-ib-user-password/', payload)
      return response.data
    },
    onSuccess: (data) => {
      message.success(`Password updated for ${data.ib_username}`)
      queryClient.invalidateQueries({
        queryKey: queryKeys.databases.ibUsers({ databaseId: data.database_id }),
      })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to set infobase user password')
    },
  })
}

export function useSetDbmsUserPassword() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: { id: number; password: string }): Promise<DbmsUserMapping> => {
      const response = await apiClient.post('/api/v2/databases/set-dbms-user-password/', payload)
      return response.data
    },
    onSuccess: (data) => {
      message.success(`Password updated for ${data.db_username}`)
      queryClient.invalidateQueries({
        queryKey: queryKeys.databases.dbmsUsers({ databaseId: data.database_id }),
      })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to set DBMS user password')
    },
  })
}

export function useResetInfobaseUserPassword() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: { id: number; databaseId: string }): Promise<{ message: string }> => {
      const response = await apiClient.post('/api/v2/databases/reset-ib-user-password/', { id: payload.id })
      return response.data
    },
    onSuccess: (_data, variables) => {
      message.success('Password reset')
      queryClient.invalidateQueries({
        queryKey: queryKeys.databases.ibUsers({ databaseId: variables.databaseId }),
      })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to reset infobase user password')
    },
  })
}

export function useResetDbmsUserPassword() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: { id: number; databaseId: string }): Promise<void> => {
      await apiClient.post('/api/v2/databases/reset-dbms-user-password/', { id: payload.id })
    },
    onSuccess: (_data, variables) => {
      message.success('Password reset')
      queryClient.invalidateQueries({
        queryKey: queryKeys.databases.dbmsUsers({ databaseId: variables.databaseId }),
      })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to reset DBMS user password')
    },
  })
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
