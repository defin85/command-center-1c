import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '../queryKeys'
import { apiClient } from '../../client'

const RBAC_STALE_TIME_MS = 5 * 60_000

export function useCanManageRbac(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.rbac.canManage(),
    queryFn: async (): Promise<boolean> => {
      try {
        await apiClient.get('/api/v2/rbac/list-roles/', { params: { limit: 1, offset: 0 } })
        return true
      } catch (error) {
        const status = (error as { response?: { status?: number } })?.response?.status
        if (status === 401 || status === 403) {
          return false
        }
        throw error
      }
    },
    staleTime: RBAC_STALE_TIME_MS,
    refetchOnWindowFocus: false,
    retry: false,
    enabled: options?.enabled ?? true,
  })
}

export type RbacGroupRef = {
  id: number
  name: string
}

export type RbacRole = {
  id: number
  name: string
  users_count: number
  permissions_count: number
  permission_codes: string[]
}

export type RoleListResponse = {
  roles: RbacRole[]
  count: number
  total: number
}

export function useRoles(
  filters?: { search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.roles(filters),
    queryFn: async (): Promise<RoleListResponse> => {
      const response = await apiClient.get('/api/v2/rbac/list-roles/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
    staleTime: RBAC_STALE_TIME_MS,
    refetchOnWindowFocus: false,
  })
}

export function useCreateRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { name: string; reason: string }): Promise<RbacGroupRef> => {
      const response = await apiClient.post('/api/v2/rbac/create-role/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useUpdateRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; name: string; reason: string }): Promise<RbacGroupRef> => {
      const response = await apiClient.post('/api/v2/rbac/update-role/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export function useDeleteRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: { group_id: number; reason: string }): Promise<{ deleted: boolean }> => {
      const response = await apiClient.post('/api/v2/rbac/delete-role/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

export type Capability = {
  code: string
  name: string
  app_label: string
  codename: string
  exists: boolean
}

export type CapabilityListResponse = {
  capabilities: Capability[]
  count: number
}

export function useCapabilities(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.rbac.capabilities(),
    queryFn: async (): Promise<CapabilityListResponse> => {
      const response = await apiClient.get('/api/v2/rbac/list-capabilities/')
      return response.data
    },
    staleTime: RBAC_STALE_TIME_MS,
    refetchOnWindowFocus: false,
    enabled: options?.enabled ?? true,
  })
}

export function useSetRoleCapabilities() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      group_id: number
      permission_codes: string[]
      mode?: 'replace' | 'add' | 'remove'
      reason: string
    }): Promise<{ group: RbacGroupRef; permission_codes: string[] }> => {
      const response = await apiClient.post('/api/v2/rbac/set-role-capabilities/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}
