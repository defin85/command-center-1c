import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '../queryKeys'
import { apiClient } from '../../client'
import type { ArtifactRef } from './refs'
import type { RbacGroupRef } from './roles'
import type { UserRef } from './users'

export type ArtifactPermission = {
  user: UserRef
  artifact: ArtifactRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export type ArtifactGroupPermission = {
  group: RbacGroupRef
  artifact: ArtifactRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export function useArtifactPermissions(
  filters?: { user_id?: number; artifact_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.artifactPermissions(filters),
    queryFn: async (): Promise<{ permissions: ArtifactPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-artifact-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantArtifactPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      user_id: number
      artifact_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: ArtifactPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-artifact-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeArtifactPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { user_id: number; artifact_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-artifact-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useArtifactGroupPermissions(
  filters?: { group_id?: number; artifact_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.groupPermissions.artifacts(filters),
    queryFn: async (): Promise<{ permissions: ArtifactGroupPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-artifact-group-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useGrantArtifactGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      artifact_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: ArtifactGroupPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-artifact-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeArtifactGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; artifact_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-artifact-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

