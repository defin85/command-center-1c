import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { App } from 'antd'

import { apiClient } from '../client'
import { queryKeys } from './index'

export type UserSummary = {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_staff: boolean
  is_superuser: boolean
  is_active: boolean
  last_login: string | null
  date_joined: string
}

export type UserListResponse = {
  users: UserSummary[]
  count: number
  total: number
}

export type UserListFilters = {
  search?: string
  username?: string
  email?: string
  is_staff?: boolean
  is_superuser?: boolean
  is_active?: boolean
  limit?: number
  offset?: number
}

export type UserCreateRequest = {
  username: string
  password: string
  email?: string
  first_name?: string
  last_name?: string
  is_staff?: boolean
  is_superuser?: boolean
  is_active?: boolean
}

export type UserUpdateRequest = {
  id: number
  username?: string
  email?: string
  first_name?: string
  last_name?: string
  is_staff?: boolean
  is_superuser?: boolean
  is_active?: boolean
}

export type UserPasswordRequest = {
  id: number
  password: string
}

export function useUsers(filters: UserListFilters, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.users.list(filters),
    queryFn: async (): Promise<UserListResponse> => {
      const response = await apiClient.get('/api/v2/users/list/', { params: filters })
      return response.data
    },
    placeholderData: (previousData) => previousData,
    enabled: options?.enabled ?? true,
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: UserCreateRequest): Promise<UserSummary> => {
      const response = await apiClient.post('/api/v2/users/create/', payload)
      return response.data
    },
    onSuccess: (data) => {
      message.success(`User ${data.username} created`)
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to create user')
    },
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: UserUpdateRequest): Promise<UserSummary> => {
      const response = await apiClient.post('/api/v2/users/update/', payload)
      return response.data
    },
    onSuccess: (data) => {
      message.success(`User ${data.username} updated`)
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to update user')
    },
  })
}

export function useSetUserPassword() {
  const queryClient = useQueryClient()
  const { message } = App.useApp()

  return useMutation({
    mutationFn: async (payload: UserPasswordRequest): Promise<UserSummary> => {
      const response = await apiClient.post('/api/v2/users/set-password/', payload)
      return response.data
    },
    onSuccess: (data) => {
      message.success(`Password updated for ${data.username}`)
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all })
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to set password')
    },
  })
}
