import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '../queryKeys'
import { apiClient } from '../../client'
import type { ClusterRef, DatabaseRef } from './refs'
import type { RbacGroupRef } from './roles'
import type { UserRef } from './users'

export type ClusterGroupPermission = {
  group: RbacGroupRef
  cluster: ClusterRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export type DatabaseGroupPermission = {
  group: RbacGroupRef
  database: DatabaseRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export type BulkUpsertResult = {
  created: number
  updated: number
  skipped: number
  total: number
}

export type BulkDeleteResult = {
  deleted: number
  skipped: number
  total: number
}

export function useClusterGroupPermissions(
  filters?: { group_id?: number; cluster_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.groupPermissions.clusters(filters),
    queryFn: async (): Promise<{ permissions: ClusterGroupPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-cluster-group-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantClusterGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      cluster_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: ClusterGroupPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-cluster-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeClusterGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; cluster_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-cluster-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useBulkGrantClusterGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      cluster_ids: string[]
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<BulkUpsertResult> => {
      const response = await apiClient.post('/api/v2/rbac/bulk-grant-cluster-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useBulkRevokeClusterGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; cluster_ids: string[]; reason: string }): Promise<BulkDeleteResult> => {
      const response = await apiClient.post('/api/v2/rbac/bulk-revoke-cluster-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useDatabaseGroupPermissions(
  filters?: {
    group_id?: number
    database_id?: string
    cluster_id?: string
    level?: string
    search?: string
    limit?: number
    offset?: number
  },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.groupPermissions.databases(filters),
    queryFn: async (): Promise<{ permissions: DatabaseGroupPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-database-group-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantDatabaseGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      database_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: DatabaseGroupPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-database-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeDatabaseGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; database_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-database-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useBulkGrantDatabaseGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      database_ids: string[]
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<BulkUpsertResult> => {
      const response = await apiClient.post('/api/v2/rbac/bulk-grant-database-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useBulkRevokeDatabaseGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; database_ids: string[]; reason: string }): Promise<BulkDeleteResult> => {
      const response = await apiClient.post('/api/v2/rbac/bulk-revoke-database-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

