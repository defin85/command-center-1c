import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getV2 } from '../generated'
import type { ClusterPermissionListResponse } from '../generated/model/clusterPermissionListResponse'
import type { DatabasePermissionListResponse } from '../generated/model/databasePermissionListResponse'
import type { EffectiveAccessResponse } from '../generated/model/effectiveAccessResponse'
import type { GrantClusterPermissionRequest } from '../generated/model/grantClusterPermissionRequest'
import type { GrantDatabasePermissionRequest } from '../generated/model/grantDatabasePermissionRequest'
import type { RevokeClusterPermissionRequest } from '../generated/model/revokeClusterPermissionRequest'
import type { RevokeDatabasePermissionRequest } from '../generated/model/revokeDatabasePermissionRequest'

import { queryKeys } from './index'

const api = getV2()

export interface ClusterPermissionFilters {
  user_id?: number
  cluster_id?: string
  level?: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
  search?: string
  limit?: number
  offset?: number
}

export interface DatabasePermissionFilters {
  user_id?: number
  database_id?: string
  cluster_id?: string
  level?: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
  search?: string
  limit?: number
  offset?: number
}

export function useClusterPermissions(filters?: ClusterPermissionFilters) {
  return useQuery({
    queryKey: queryKeys.rbac.clusterPermissions(filters),
    queryFn: (): Promise<ClusterPermissionListResponse> => api.getRbacListClusterPermissions(filters),
    select: (data) => data.permissions ?? [],
  })
}

export function useDatabasePermissions(filters?: DatabasePermissionFilters) {
  return useQuery({
    queryKey: queryKeys.rbac.databasePermissions(filters),
    queryFn: (): Promise<DatabasePermissionListResponse> => api.getRbacListDatabasePermissions(filters),
    select: (data) => data.permissions ?? [],
  })
}

export function useEffectiveAccess(userId?: number, includeDatabases: boolean = false) {
  return useQuery({
    queryKey: queryKeys.rbac.effectiveAccess(userId),
    queryFn: (): Promise<EffectiveAccessResponse> =>
      api.getRbacGetEffectiveAccess({
        user_id: userId,
        include_databases: includeDatabases,
        include_clusters: true,
      }),
  })
}

export function useGrantClusterPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: GrantClusterPermissionRequest) => api.postRbacGrantClusterPermission(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeClusterPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: RevokeClusterPermissionRequest) => api.postRbacRevokeClusterPermission(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useGrantDatabasePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: GrantDatabasePermissionRequest) => api.postRbacGrantDatabasePermission(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeDatabasePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: RevokeDatabasePermissionRequest) => api.postRbacRevokeDatabasePermission(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

