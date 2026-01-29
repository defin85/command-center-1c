import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '../queryKeys'
import { apiClient } from '../../client'
import type { OperationTemplateRef, WorkflowTemplateRef } from './refs'
import type { RbacGroupRef } from './roles'
import type { UserRef } from './users'

const RBAC_STALE_TIME_MS = 5 * 60_000

export type OperationTemplatePermission = {
  user: UserRef
  template: OperationTemplateRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export type OperationTemplateGroupPermission = {
  group: RbacGroupRef
  template: OperationTemplateRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export function useOperationTemplatePermissions(
  filters?: { user_id?: number; template_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.operationTemplatePermissions(filters),
    queryFn: async (): Promise<{ permissions: OperationTemplatePermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-operation-template-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
    staleTime: RBAC_STALE_TIME_MS,
    refetchOnWindowFocus: false,
  })
}

export function useGrantOperationTemplatePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      user_id: number
      template_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: OperationTemplatePermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-operation-template-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeOperationTemplatePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { user_id: number; template_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-operation-template-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useOperationTemplateGroupPermissions(
  filters?: { group_id?: number; template_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.groupPermissions.operationTemplates(filters),
    queryFn: async (): Promise<{ permissions: OperationTemplateGroupPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-operation-template-group-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
    staleTime: RBAC_STALE_TIME_MS,
    refetchOnWindowFocus: false,
  })
}

export function useGrantOperationTemplateGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      template_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: OperationTemplateGroupPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-operation-template-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeOperationTemplateGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; template_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-operation-template-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export type WorkflowTemplatePermission = {
  user: UserRef
  template: WorkflowTemplateRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export type WorkflowTemplateGroupPermission = {
  group: RbacGroupRef
  template: WorkflowTemplateRef
  level: string
  granted_by?: UserRef | null
  granted_at?: string
  notes?: string
}

export function useWorkflowTemplatePermissions(
  filters?: { user_id?: number; template_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.workflowTemplatePermissions(filters),
    queryFn: async (): Promise<{ permissions: WorkflowTemplatePermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-workflow-template-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
    staleTime: RBAC_STALE_TIME_MS,
    refetchOnWindowFocus: false,
  })
}

export function useGrantWorkflowTemplatePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      user_id: number
      template_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: WorkflowTemplatePermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-workflow-template-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeWorkflowTemplatePermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { user_id: number; template_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-workflow-template-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useWorkflowTemplateGroupPermissions(
  filters?: { group_id?: number; template_id?: string; level?: string; search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.groupPermissions.workflowTemplates(filters),
    queryFn: async (): Promise<{ permissions: WorkflowTemplateGroupPermission[]; count: number; total: number }> => {
      const response = await apiClient.get('/api/v2/rbac/list-workflow-template-group-permissions/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
    staleTime: RBAC_STALE_TIME_MS,
    refetchOnWindowFocus: false,
  })
}

export function useGrantWorkflowTemplateGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      template_id: string
      level: 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
      notes?: string
      reason: string
    }): Promise<{ created: boolean; permission: WorkflowTemplateGroupPermission }> => {
      const response = await apiClient.post('/api/v2/rbac/grant-workflow-template-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useRevokeWorkflowTemplateGroupPermission() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; template_id: string; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/revoke-workflow-template-group-permission/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}
