import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '../queryKeys'
import { apiClient } from '../../client'
import type { RbacGroupRef } from './roles'

export type UserRef = {
  id: number
  username: string
}

export type UserListResponse = {
  users: UserRef[]
  count: number
  total: number
}

export function useRbacUsers(
  filters?: { search?: string; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.users(filters),
    queryFn: async (): Promise<UserListResponse> => {
      const response = await apiClient.get('/api/v2/rbac/list-users/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export type UserWithRolesRef = {
  id: number
  username: string
  roles: RbacGroupRef[]
}

export type UserWithRolesListResponse = {
  users: UserWithRolesRef[]
  count: number
  total: number
}

export function useRbacUsersWithRoles(
  filters?: { search?: string; role_id?: number; limit?: number; offset?: number },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.rbac.usersWithRoles(filters),
    queryFn: async (): Promise<UserWithRolesListResponse> => {
      const response = await apiClient.get('/api/v2/rbac/list-users-with-roles/', { params: filters })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export type UserRolesResponse = {
  user: UserRef
  roles: RbacGroupRef[]
}

export function useUserRoles(userId?: number, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.rbac.userRoles(userId),
    queryFn: async (): Promise<UserRolesResponse> => {
      const response = await apiClient.get('/api/v2/rbac/get-user-roles/', { params: { user_id: userId } })
      return response.data
    },
    enabled: options?.enabled ?? true,
  })
}

export function useSetUserRoles() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: {
      user_id: number
      group_ids: number[]
      mode?: 'replace' | 'add' | 'remove'
      reason: string
    }): Promise<UserRolesResponse> => {
      const response = await apiClient.post('/api/v2/rbac/set-user-roles/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rbac.all })
    },
  })
}

